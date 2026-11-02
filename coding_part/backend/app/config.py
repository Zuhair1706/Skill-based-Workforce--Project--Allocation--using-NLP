from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = BACKEND_DIR.parents[1]
load_dotenv(BACKEND_DIR / ".env")


def csv_path(folder: str, filename: str) -> Path:
    return REPO_DIR / folder / filename


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"sqlite:///{(BACKEND_DIR / 'workforce.db').as_posix()}",
)
SKILL_NER_MODEL = os.getenv("SKILL_NER_MODEL", "").strip()
SKILL_NER_THRESHOLD = float(os.getenv("SKILL_NER_THRESHOLD", "0.55"))
MAX_CANDIDATES = max(100, int(os.getenv("MAX_CANDIDATES", "3000")))
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
    if origin.strip()
]
