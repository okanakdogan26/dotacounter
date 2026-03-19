from __future__ import annotations

import json
import subprocess
import sys

from import_dotabuff_data import DATASET_PATH, merge_payload


def read_clipboard() -> str:
    try:
        result = subprocess.run(
            ["pbpaste"],
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        print("pbpaste command not found.")
        raise SystemExit(1)
    except subprocess.CalledProcessError as exc:
        print(f"Failed to read clipboard: {exc}")
        raise SystemExit(1)

    return result.stdout


def main() -> int:
    raw = read_clipboard()
    if not raw.strip():
        print("Clipboard is empty.")
        return 1

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"Clipboard does not contain valid JSON: {exc}")
        return 1

    merged_count = merge_payload(payload)
    print(f"Merged {merged_count} hero entries into {DATASET_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
