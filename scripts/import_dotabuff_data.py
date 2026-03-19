from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATASET_PATH = ROOT / "data" / "dotabuff_worst_versus.json"


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def save_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def merge_payload(import_payload: dict) -> int:
    dataset = load_json(DATASET_PATH)

    dataset.setdefault("heroes", {})
    dataset["updated_at"] = import_payload.get("updated_at", dataset.get("updated_at"))

    hero_entries = import_payload.get("heroes", {})
    if not isinstance(hero_entries, dict):
        print("Import file must contain a 'heroes' object.")
        return 1

    merged_count = 0
    for enemy_hero, rows in hero_entries.items():
        if not isinstance(rows, list):
            print(f"Skipping invalid rows for hero: {enemy_hero}")
            continue

        normalized_rows = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            if not {"hero", "disadvantage_pct", "win_rate_pct", "matches"}.issubset(row.keys()):
                continue
            normalized_rows.append(
                {
                    "hero": row["hero"],
                    "disadvantage_pct": row["disadvantage_pct"],
                    "win_rate_pct": row["win_rate_pct"],
                    "matches": row["matches"],
                }
            )

        dataset["heroes"][enemy_hero] = normalized_rows
        merged_count += 1

    dataset["heroes"] = dict(sorted(dataset["heroes"].items()))
    save_json(DATASET_PATH, dataset)
    return merged_count


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python3 scripts/import_dotabuff_data.py <import-file.json>")
        return 1

    import_path = Path(sys.argv[1]).resolve()
    if not import_path.exists():
        print(f"Import file not found: {import_path}")
        return 1

    merged_count = merge_payload(load_json(import_path))
    print(f"Merged {merged_count} hero entries into {DATASET_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
