from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.config import SKILL_NER_MODEL, SKILL_NER_THRESHOLD
from app.database import employee_skills, engine, project_requirements, skill_aliases


def normalize_skill(value: str) -> str:
    return re.sub(r"[^a-z0-9+#.]+", " ", value.casefold()).strip()


@dataclass(frozen=True)
class SkillMention:
    skill: str
    surface_form: str
    start: int
    end: int
    confidence: float
    source: str


class SkillExtractor:
    """Skill NER with a configurable fine-tuned transformer and alias fallback."""

    def __init__(self) -> None:
        self.aliases: dict[str, str] = {}
        self._model: Any | None = None
        self._tokenizer: Any | None = None
        self.model_error: str | None = None
        self._load_aliases()
        if SKILL_NER_MODEL:
            self._load_model()

    @property
    def model_status(self) -> str:
        if self._model is not None:
            return f"transformer:{SKILL_NER_MODEL}"
        return "alias-matcher" if not self.model_error else "alias-matcher (transformer unavailable)"

    def _load_aliases(self) -> None:
        try:
            with engine.connect() as connection:
                for skill, alias in connection.execute(
                    select(skill_aliases.c.skill, skill_aliases.c.alias)
                ):
                    if skill and alias:
                        self.aliases[normalize_skill(alias)] = skill
                for (skill,) in connection.execute(
                    select(project_requirements.c.required_skill).distinct()
                ):
                    if skill:
                        self.aliases.setdefault(normalize_skill(skill), skill)
                for (skill,) in connection.execute(
                    select(employee_skills.c.skill).distinct()
                ):
                    if skill:
                        self.aliases.setdefault(normalize_skill(skill), skill)
        except SQLAlchemyError:
            # A first-run local database has no tables until the CSV seeder runs.
            self.model_error = "Skill catalog is not loaded yet."
        self.aliases = {key: value for key, value in self.aliases.items() if key}
        self.aliases.setdefault("scikit learn", "Scikit-learn")
        self.aliases.setdefault("sklearn", "Scikit-learn")
        self.aliases.setdefault("containerization", "Docker")
        self.aliases.setdefault("containers", "Docker")

    def _load_model(self) -> None:
        try:
            from transformers import AutoModelForTokenClassification, AutoTokenizer

            self._tokenizer = AutoTokenizer.from_pretrained(
                SKILL_NER_MODEL, use_fast=True
            )
            if not self._tokenizer.is_fast:
                raise ValueError("Skill NER requires a fast tokenizer with character offsets.")
            self._model = AutoModelForTokenClassification.from_pretrained(SKILL_NER_MODEL)
            self._model.eval()
        except (ImportError, OSError, ValueError) as exc:
            self.model_error = str(exc)
            self._model = None
            self._tokenizer = None

    def extract(self, text: str) -> list[SkillMention]:
        if not text.strip():
            return []
        mentions = self._extract_aliases(text)
        if self._model is not None:
            mentions.extend(self._extract_transformer(text))
        return self._deduplicate(mentions)

    def _extract_aliases(self, text: str) -> list[SkillMention]:
        matches: list[SkillMention] = []
        for alias, skill in sorted(self.aliases.items(), key=lambda item: -len(item[0])):
            pattern = re.compile(
                rf"(?<![\w+#.]){re.escape(alias)}(?![\w+#.])", re.IGNORECASE
            )
            for match in pattern.finditer(text):
                matches.append(
                    SkillMention(
                        skill=skill,
                        surface_form=match.group(0),
                        start=match.start(),
                        end=match.end(),
                        confidence=1.0,
                        source="alias",
                    )
                )
        return matches

    def _extract_transformer(self, text: str) -> list[SkillMention]:
        import torch

        encoded = self._tokenizer(
            text,
            return_offsets_mapping=True,
            return_tensors="pt",
            truncation=True,
            max_length=512,
        )
        offsets = encoded.pop("offset_mapping")[0].tolist()
        with torch.inference_mode():
            logits = self._model(**encoded).logits[0]
            probabilities = torch.softmax(logits, dim=-1)
            scores, label_ids = probabilities.max(dim=-1)
        id_to_label = self._model.config.id2label
        mentions: list[SkillMention] = []
        active_start: int | None = None
        active_end = 0
        active_score = 0.0

        def close_mention() -> None:
            nonlocal active_start, active_end, active_score
            if active_start is not None and active_end > active_start:
                surface = text[active_start:active_end]
                mentions.append(
                    SkillMention(
                        skill=surface.strip(),
                        surface_form=surface,
                        start=active_start,
                        end=active_end,
                        confidence=active_score,
                        source="transformer",
                    )
                )
            active_start = None
            active_end = 0
            active_score = 0.0

        for (start, end), label_id, score in zip(
            offsets, label_ids.tolist(), scores.tolist()
        ):
            if start == end:
                continue
            label = id_to_label.get(int(label_id), "O").upper()
            if label in {"O", "LABEL_0"} or score < SKILL_NER_THRESHOLD:
                close_mention()
                continue
            tag = label.split("-", 1)
            prefix = tag[0]
            entity_type = tag[-1] if len(tag) > 1 else ""
            if entity_type not in {"SKILL", "TECH", "TECHNOLOGY"}:
                close_mention()
                continue
            if prefix in {"B", "S", "U"} or active_start is None:
                close_mention()
                active_start, active_end, active_score = start, end, score
            elif prefix in {"I", "E", "L"}:
                active_end = end
                active_score = min(active_score, score)
                if prefix in {"E", "L"}:
                    close_mention()
        close_mention()
        return mentions

    def _deduplicate(self, mentions: list[SkillMention]) -> list[SkillMention]:
        best: dict[tuple[str, int, int], SkillMention] = {}
        for mention in mentions:
            key = (normalize_skill(mention.skill), mention.start, mention.end)
            previous = best.get(key)
            if previous is None or mention.confidence > previous.confidence:
                best[key] = mention
        # A longer alias wins if aliases overlap (e.g. "machine learning" in
        # "machine learning engineer"), while distinct nested skills remain.
        ordered = sorted(best.values(), key=lambda item: (item.start, -(item.end - item.start)))
        accepted: list[SkillMention] = []
        for mention in ordered:
            if any(
                mention.start < current.end
                and current.start < mention.end
                and mention.start != current.start
                for current in accepted
            ):
                continue
            accepted.append(mention)
        return accepted


extractor = SkillExtractor()


def extract_skills(text: str) -> list[dict[str, Any]]:
    return [mention.__dict__ for mention in extractor.extract(text)]
