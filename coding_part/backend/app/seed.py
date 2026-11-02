from __future__ import annotations

from app.database import seed_database


if __name__ == "__main__":
    counts = seed_database()
    for table, count in counts.items():
        print(f"Loaded {count:,} rows into {table}")
