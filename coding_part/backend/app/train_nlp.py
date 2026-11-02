from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any

from app.config import csv_path


def _training_examples() -> list[dict[str, Any]]:
    projects_file = csv_path("projects dataset", "projects_30_v2.csv")
    annotations_file = csv_path("projects dataset", "project_skill_annotations.csv")
    with projects_file.open(encoding="utf-8-sig", newline="") as handle:
        descriptions = {
            row["project_id"]: row["project_description"]
            for row in csv.DictReader(handle)
        }
    annotations: dict[str, list[tuple[int, int]]] = {}
    with annotations_file.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            annotations.setdefault(row["project_id"], []).append(
                (int(row["char_start"]), int(row["char_end"]))
            )
    return [
        {"text": descriptions[project_id], "entities": entities}
        for project_id, entities in annotations.items()
        if project_id in descriptions
    ]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fine-tune a BERT/RoBERTa token classifier on skill span annotations."
    )
    parser.add_argument("--base-model", default="bert-base-cased")
    parser.add_argument("--output-dir", default="models/skill-ner")
    parser.add_argument("--epochs", type=float, default=8)
    args = parser.parse_args()

    import torch
    from transformers import (
        AutoModelForTokenClassification,
        AutoTokenizer,
        Trainer,
        TrainingArguments,
    )

    examples = _training_examples()
    if not examples:
        raise ValueError("No annotation examples were found in project_skill_annotations.csv.")
    labels = {"O": 0, "B-SKILL": 1, "I-SKILL": 2}
    tokenizer = AutoTokenizer.from_pretrained(args.base_model, use_fast=True)
    if not tokenizer.is_fast:
        raise ValueError("The selected model must provide a fast tokenizer.")

    class SkillDataset(torch.utils.data.Dataset):
        def __init__(self) -> None:
            self.items = []
            for example in examples:
                encoded = tokenizer(
                    example["text"],
                    truncation=True,
                    max_length=512,
                    padding="max_length",
                    return_offsets_mapping=True,
                )
                offsets = encoded.pop("offset_mapping")
                tags = []
                for start, end in offsets:
                    label = labels["O"]
                    if start != end:
                        for entity_start, entity_end in example["entities"]:
                            if start < entity_end and entity_start < end:
                                label = labels["B-SKILL"] if start <= entity_start else labels["I-SKILL"]
                                break
                    tags.append(label if start != end else -100)
                encoded["labels"] = tags
                self.items.append(encoded)

        def __len__(self) -> int:
            return len(self.items)

        def __getitem__(self, index: int) -> dict[str, torch.Tensor]:
            return {
                key: torch.tensor(value)
                for key, value in self.items[index].items()
                if key in {"input_ids", "attention_mask", "token_type_ids", "labels"}
            }

    model = AutoModelForTokenClassification.from_pretrained(
        args.base_model,
        num_labels=len(labels),
        id2label={value: key for key, value in labels.items()},
        label2id=labels,
    )
    output_dir = Path(args.output_dir)
    training = TrainingArguments(
        output_dir=str(output_dir),
        num_train_epochs=args.epochs,
        learning_rate=3e-5,
        per_device_train_batch_size=8,
        weight_decay=0.01,
        save_strategy="epoch",
        logging_steps=10,
        report_to=[],
    )
    Trainer(model=model, args=training, train_dataset=SkillDataset()).train()
    model.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)
    print(f"Saved fine-tuned skill NER model to {output_dir.resolve()}")


if __name__ == "__main__":
    main()
