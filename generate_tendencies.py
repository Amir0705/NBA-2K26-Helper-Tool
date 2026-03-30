#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path
from typing import Iterable


RANGE_PATTERN = re.compile(r"(\d+)\s*[\-–]\s*(\d+)")
NUMBER_PATTERN = re.compile(r"(\d+)")


def _parse_numeric_hint(cell: str) -> int | None:
    if not cell:
        return None
    range_match = RANGE_PATTERN.search(cell)
    if range_match:
        lo, hi = int(range_match.group(1)), int(range_match.group(2))
        return round((lo + hi) / 2)
    numbers = NUMBER_PATTERN.findall(cell)
    if numbers:
        return int(numbers[-1])
    return None


def _load_rules(rules_path: Path) -> tuple[list[str], list[int]]:
    with rules_path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f, delimiter=";"))

    if not rows:
        raise ValueError(f"Rules file is empty: {rules_path}")

    tendencies = rows[0]
    norm_row = next((row for row in rows if row and row[0].startswith("NBA Norm:")), None)
    cap_row = next(
        (row for row in rows if row and row[0].startswith("Absolute Cap:")), None
    )

    if norm_row is None or cap_row is None:
        raise ValueError(
            "Rules file must contain both 'NBA Norm:' and 'Absolute Cap:' rows."
        )

    defaults: list[int] = []
    for i, _tendency in enumerate(tendencies):
        norm_cell = norm_row[i] if i < len(norm_row) else ""
        cap_cell = cap_row[i] if i < len(cap_row) else ""
        default_value = _parse_numeric_hint(norm_cell)
        cap_value = _parse_numeric_hint(cap_cell)
        if default_value is None:
            default_value = 0
        if cap_value is None:
            cap_value = 100
        defaults.append(max(0, min(default_value, cap_value, 100)))

    return tendencies, defaults


def _iter_attribute_files(root: Path, pattern: str) -> Iterable[Path]:
    files = sorted(root.glob(pattern))
    if not files:
        raise FileNotFoundError(
            f"No attribute source files matched pattern '{pattern}' in {root}"
        )
    return files


def generate(output_path: Path, root: Path, rules_filename: str, pattern: str) -> None:
    rules_path = root / rules_filename
    if not rules_path.exists():
        raise FileNotFoundError(f"Rules file not found: {rules_path}")

    tendencies, defaults = _load_rules(rules_path)

    id_columns = [
        "era_start",
        "era_end",
        "season_start",
        "season_label",
        "player_id",
        "player_name",
        "team_abbr",
        "position",
    ]

    with output_path.open("w", encoding="utf-8", newline="") as out_f:
        writer = csv.writer(out_f)
        writer.writerow(id_columns + tendencies)

        for attribute_file in _iter_attribute_files(root, pattern):
            with attribute_file.open("r", encoding="utf-8-sig", newline="") as in_f:
                reader = csv.DictReader(in_f, delimiter=";")
                missing_cols = [c for c in id_columns if c not in (reader.fieldnames or [])]
                if missing_cols:
                    raise ValueError(
                        f"File {attribute_file.name} is missing required columns: {missing_cols}"
                    )

                for row in reader:
                    id_values = [row.get(c, "") for c in id_columns]
                    writer.writerow(id_values + defaults)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Generate baseline tendencies for all era-split attribute_source CSV files "
            "using Copilot_Optimized_ATD_Tendencies rules."
        )
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("."),
        help="Repository/data root directory (default: current directory)",
    )
    parser.add_argument(
        "--rules",
        default="Copilot_Optimized_ATD_Tendencies.csv",
        help="Rules CSV filename (default: Copilot_Optimized_ATD_Tendencies.csv)",
    )
    parser.add_argument(
        "--pattern",
        default="attribute_source_*.csv",
        help="Glob pattern for era-split attribute source files (default: attribute_source_*.csv)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("generated_tendencies.csv"),
        help="Output CSV path (default: generated_tendencies.csv)",
    )

    args = parser.parse_args()
    root = args.root.resolve()
    output = args.output if args.output.is_absolute() else (root / args.output)

    generate(output_path=output, root=root, rules_filename=args.rules, pattern=args.pattern)
    print(f"Generated: {output}")


if __name__ == "__main__":
    main()
