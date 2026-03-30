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


def _to_float(value: str | None) -> float:
    if value is None:
        return 0.0
    text = str(value).strip()
    if not text:
        return 0.0
    text = text.replace("%", "").replace("−", "-").replace("–", "-")
    if text.lower() in {"n/a", "na", "none", "null", "false", "true"}:
        return 0.0

    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        text = text.replace(",", ".")

    try:
        return float(text)
    except ValueError:
        match = re.search(r"-?\d+(?:\.\d+)?", text)
        return float(match.group(0)) if match else 0.0


def _clamp01(value: float) -> float:
    return max(0.0, min(value, 1.0))


def _scale(value: float, lo: float, hi: float) -> float:
    if hi <= lo:
        return 0.0
    return _clamp01((value - lo) / (hi - lo))


def _as_ratio(value: float) -> float:
    if value <= 0:
        return 0.0
    if value > 1.0:
        return _clamp01(value / 100.0)
    return _clamp01(value)


def _load_rules(rules_path: Path) -> tuple[list[str], list[int], list[int]]:
    with rules_path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f, delimiter=";"))

    if not rows:
        raise ValueError(f"Rules file is empty: {rules_path}")

    tendencies = rows[0]
    norm_row = next((row for row in rows if row and row[0].startswith("NBA Norm:")), None)
    cap_row = next(
        (row for row in rows if row and row[0].startswith("Absolute Cap:")),
        next((row for row in rows if row and row[0].startswith("Cap:")), None),
    )

    if norm_row is None or cap_row is None:
        raise ValueError(
            "Rules file must contain both 'NBA Norm:' and an absolute cap row ('Absolute Cap:' or 'Cap:')."
        )

    defaults: list[int] = []
    caps: list[int] = []
    for i, _tendency in enumerate(tendencies):
        norm_cell = norm_row[i] if i < len(norm_row) else ""
        cap_cell = cap_row[i] if i < len(cap_row) else ""

        default_value = _parse_numeric_hint(norm_cell)
        cap_value = _parse_numeric_hint(cap_cell)

        if default_value is None:
            default_value = 50
        if cap_value is None:
            cap_value = 100

        default_value = max(0, min(default_value, 100))
        cap_value = max(0, min(cap_value, 100))
        defaults.append(min(default_value, cap_value))
        caps.append(cap_value)

    return tendencies, defaults, caps


def _iter_attribute_files(root: Path, pattern: str) -> Iterable[Path]:
    files = sorted(root.glob(pattern))
    if not files:
        raise FileNotFoundError(
            f"No attribute source files matched pattern '{pattern}' in {root}"
        )
    return files


def _calculate_tendencies(row: dict[str, str], tendencies: list[str], defaults: list[int], caps: list[int]) -> list[int]:
    def raw(name: str) -> float:
        return _to_float(row.get(name, ""))

    def ratio(name: str) -> float:
        return _as_ratio(raw(name))

    usg = ratio("advanced_usg_percent")
    ast_pct = ratio("advanced_ast_percent")
    tov_pct = ratio("advanced_tov_percent")
    stl_pct = ratio("advanced_stl_percent")
    blk_pct = ratio("advanced_blk_percent")
    orb_pct = ratio("advanced_orb_percent")

    ft_rate = ratio("advanced_f_tr")
    three_rate = ratio("advanced_x3p_ar")

    rim_rate = ratio("shooting_percent_fga_from_x0_3_range")
    short_rate = ratio("shooting_percent_fga_from_x3_10_range")
    mid_rate = ratio("shooting_percent_fga_from_x10_16_range") + ratio("shooting_percent_fga_from_x16_3p_range")
    three_share = ratio("shooting_percent_fga_from_x3p_range")

    assist2 = ratio("shooting_percent_assisted_x2p_fg")
    assist3 = ratio("shooting_percent_assisted_x3p_fg")
    dunk_share = ratio("shooting_percent_dunks_of_fga")
    corner3_share = ratio("shooting_percent_corner_3s_of_3pa")

    pullup_freq = ratio("pbp_features_pullup_freq")
    pullup2_freq = ratio("pbp_features_pullup_2_freq")
    pullup3_freq = ratio("pbp_features_pullup_3_freq")
    stepback_freq = ratio("pbp_features_stepback_freq")
    stepback2_freq = ratio("pbp_features_stepback_2_freq")
    stepback3_freq = ratio("pbp_features_stepback_3_freq")
    fade_freq = ratio("pbp_features_fadeaway_freq")
    hook_freq = ratio("pbp_features_hook_freq")

    per100_pts = raw("per_100_pts_per_100_poss")
    per100_fta = raw("per_100_fta_per_100_poss")
    per100_tov = raw("per_100_tov_per_100_poss")
    per100_pf = raw("per_100_pf_per_100_poss")

    dbpm = raw("advanced_dbpm")
    age = raw("age")
    height = raw("player_info_ht_in_in")

    pg_share = ratio("play_by_play_pg_percent")
    sg_share = ratio("play_by_play_sg_percent")
    sf_share = ratio("play_by_play_sf_percent")
    pf_share = ratio("play_by_play_pf_percent")
    c_share = ratio("play_by_play_c_percent")

    guard_share = _clamp01(pg_share + sg_share)
    wing_share = _clamp01(sf_share + 0.5 * sg_share)
    big_share = _clamp01(pf_share + c_share)

    age_youth = _clamp01((32.0 - age) / 14.0)
    height_scale = _scale(height, 72.0, 84.0)

    shot_volume = _scale(per100_pts, 8.0, 40.0)
    attack_rate = _scale(per100_fta, 1.0, 14.0)
    turnover_pressure = _scale(per100_tov, 0.5, 7.0)
    foul_pressure = _scale(per100_pf, 1.0, 7.0)

    onball_creation = _clamp01(0.45 * pullup_freq + 0.35 * stepback_freq + 0.20 * usg + 0.15 * ast_pct)
    drive_pressure = _clamp01(0.45 * rim_rate + 0.25 * ft_rate + 0.20 * usg + 0.15 * dunk_share + 0.20 * attack_rate)
    post_presence = _clamp01(0.55 * big_share + 0.45 * hook_freq + 0.35 * fade_freq + 0.20 * rim_rate)

    values: dict[str, float] = {
        "Shot": _clamp01(0.65 * shot_volume + 0.35 * _scale(usg, 0.10, 0.35)),
        "Touch": _clamp01(0.50 * _scale(ast_pct, 0.04, 0.35) + 0.50 * _scale(usg, 0.10, 0.35)),
        "Shot Close": _clamp01(short_rate * 1.5 + rim_rate * 0.35),
        "Shot Under": _clamp01(rim_rate * 1.5 + dunk_share * 0.4),
        "Shot Mid": _clamp01(mid_rate * 1.8 + fade_freq * 0.35),
        "Spot-Up Mid": _clamp01(mid_rate * (1.0 - pullup2_freq) * 2.0 + assist2 * 0.20),
        "Off-Screen Mid": _clamp01(mid_rate * 1.1 + guard_share * 0.2 + (1.0 - assist2) * 0.1),
        "Shot 3": _clamp01(three_share * 1.8 + three_rate * 0.30),
        "Spot-Up 3": _clamp01(three_share * (1.0 - pullup3_freq) * 2.0 + corner3_share * 0.6 + assist3 * 0.25),
        "Off-Screen 3": _clamp01(three_share * 1.0 + pullup3_freq * 0.3 + guard_share * 0.25),
        "Contested Mid": _clamp01(mid_rate * 0.60 + onball_creation * 0.80),
        "Contested 3": _clamp01(three_share * 0.50 + pullup3_freq * 0.90 + stepback3_freq * 0.80),
        "Step-Back Mid": _clamp01(stepback2_freq * 2.3 + mid_rate * 0.30),
        "Step-Back 3": _clamp01(stepback3_freq * 2.9 + three_share * 0.20),
        "Spin Jumper": _clamp01(fade_freq * 0.9 + hook_freq * 0.5 + mid_rate * 0.2),
        "Transition Pull-Up 3": _clamp01(pullup3_freq * 1.2 + three_share * 0.55 + guard_share * 0.15),
        "Dribble Pull-Up Mid": _clamp01(pullup2_freq * 2.3 + mid_rate * 0.25),
        "Dribble Pull-Up 3": _clamp01(pullup3_freq * 2.6 + three_share * 0.20),
        "Drive": drive_pressure,
        "Spot-Up Drive": _clamp01(drive_pressure * 0.75 + (1.0 - pullup_freq) * 0.20 + guard_share * 0.10),
        "Off-Screen Drive": _clamp01(drive_pressure * 0.70 + guard_share * 0.20 + rim_rate * 0.20),
        "Use Glass": _clamp01(big_share * 0.55 + rim_rate * 0.30 + height_scale * 0.20),
        "Step Through": _clamp01(post_presence * 0.60 + drive_pressure * 0.20 + big_share * 0.20),
        "Spin Layup": _clamp01(guard_share * 0.30 + drive_pressure * 0.55 + onball_creation * 0.35),
        "Eurostep": _clamp01(guard_share * 0.40 + drive_pressure * 0.55 + onball_creation * 0.25),
        "Hop Step": _clamp01(drive_pressure * 0.45 + onball_creation * 0.45 + big_share * 0.10),
        "Floater": _clamp01(short_rate * 0.75 + guard_share * 0.35 + pullup2_freq * 0.25),
        "Standing Dunk": _clamp01(dunk_share * 1.60 + big_share * 0.50 + rim_rate * 0.20),
        "Driving Dunk": _clamp01(dunk_share * 1.50 + drive_pressure * 0.60),
        "Flashy Dunk": _clamp01(dunk_share * 0.80 + drive_pressure * 0.35 + age_youth * 0.35),
        "Alley-Oop": _clamp01(dunk_share * 0.90 + drive_pressure * 0.25 + big_share * 0.15),
        "Putback": _clamp01(orb_pct * 2.4 + big_share * 0.25),
        "Crash": _clamp01(orb_pct * 1.8 + big_share * 0.35 + drive_pressure * 0.10),
        "Drive Right": _clamp01(0.45 + 0.15 * onball_creation - 0.05 * big_share),
        "Triple Threat Pump Fake": _clamp01(mid_rate * 0.40 + three_share * 0.30 + onball_creation * 0.30),
        "Triple Threat Jab Step": _clamp01(mid_rate * 0.30 + three_share * 0.20 + onball_creation * 0.50),
        "Triple Threat Idle": _clamp01(big_share * 0.45 + (1.0 - onball_creation) * 0.50),
        "Triple Threat Shoot": _clamp01(three_share * 0.45 + mid_rate * 0.35 + usg * 0.20),
        "Set Up Size-Up": _clamp01(onball_creation * 1.00),
        "Set Up Hesitation": _clamp01(onball_creation * 0.90 + drive_pressure * 0.20),
        "No Setup Dribble": _clamp01(1.0 - onball_creation * 0.90),
        "Drive Crossover": _clamp01(onball_creation * 0.75 + guard_share * 0.25),
        "Drive Double Crossover": _clamp01(onball_creation * 0.65 + guard_share * 0.30),
        "Drive Spin": _clamp01(onball_creation * 0.35 + drive_pressure * 0.30 + big_share * 0.20),
        "Drive Half Spin": _clamp01(onball_creation * 0.30 + drive_pressure * 0.25),
        "Drive Step Back": _clamp01(stepback_freq * 1.20 + onball_creation * 0.30),
        "Drive Behind Back": _clamp01(onball_creation * 0.55 + guard_share * 0.25),
        "Drive Hesitation": _clamp01(onball_creation * 0.55 + drive_pressure * 0.20),
        "Drive In & Out": _clamp01(onball_creation * 0.55 + drive_pressure * 0.15),
        "No Drive Dribble Move": _clamp01(1.0 - (0.70 * onball_creation + 0.10 * guard_share)),
        "Attack Strong Drive": _clamp01(drive_pressure * 0.60 + big_share * 0.35 + ft_rate * 0.30),
        "Dish": _clamp01(_scale(ast_pct, 0.04, 0.35) * 1.20 + drive_pressure * 0.20),
        "Flashy Pass": _clamp01(_scale(ast_pct, 0.04, 0.35) * 0.80 + turnover_pressure * 0.30 + age_youth * 0.30),
        "Alley-Oop Pass": _clamp01(_scale(ast_pct, 0.04, 0.35) * 0.95 + drive_pressure * 0.35),
        "Roll vs Pop": _clamp01(three_share * 0.90 + mid_rate * 0.30 - rim_rate * 0.20),
        "Spot vs Cut": _clamp01(three_share * 0.80 + assist3 * 0.25 - rim_rate * 0.20),
        "ISO vs Elite": _clamp01(onball_creation * 0.75 + _scale(usg, 0.10, 0.35) * 0.40 - 0.20),
        "ISO vs Good": _clamp01(onball_creation * 0.80 + _scale(usg, 0.10, 0.35) * 0.45 - 0.10),
        "ISO vs Average": _clamp01(onball_creation * 0.85 + _scale(usg, 0.10, 0.35) * 0.50),
        "ISO vs Poor": _clamp01(onball_creation * 0.90 + _scale(usg, 0.10, 0.35) * 0.55 + 0.05),
        "Play Discipline": _clamp01((1.0 - turnover_pressure) * 0.70 + _scale(ast_pct, 0.04, 0.35) * 0.30),
        "Post Up": _clamp01(post_presence * 1.10 + big_share * 0.25),
        "Post Back Down": _clamp01(post_presence * 0.90 + big_share * 0.45),
        "Post Aggressive Back Down": _clamp01(post_presence * 0.70 + big_share * 0.45 + drive_pressure * 0.20),
        "Post Face Up": _clamp01(post_presence * 0.50 + mid_rate * 0.60 + onball_creation * 0.25),
        "Post Spin": _clamp01(post_presence * 0.50 + onball_creation * 0.25 + hook_freq * 0.80),
        "Post Drive": _clamp01(post_presence * 0.45 + drive_pressure * 0.45),
        "Post Drop Step": _clamp01(post_presence * 0.75 + big_share * 0.35),
        "Shoot From Post": _clamp01(post_presence * 0.45 + mid_rate * 0.60 + hook_freq * 0.20 + fade_freq * 0.30),
        "Post Hook Left": _clamp01(hook_freq * 2.40 + post_presence * 0.30),
        "Post Hook Right": _clamp01(hook_freq * 2.40 + post_presence * 0.30),
        "Post Fade Left": _clamp01(fade_freq * 2.20 + mid_rate * 0.35 + post_presence * 0.20),
        "Post Fade Right": _clamp01(fade_freq * 2.20 + mid_rate * 0.35 + post_presence * 0.20),
        "Post Shimmy": _clamp01((fade_freq + hook_freq) * 1.10 + onball_creation * 0.20),
        "Post Hop Shot": _clamp01(fade_freq * 1.40 + mid_rate * 0.40),
        "Post Step Back": _clamp01(stepback2_freq * 1.40 + post_presence * 0.30 + mid_rate * 0.20),
        "Post Up & Under": _clamp01(post_presence * 0.50 + hook_freq * 0.60 + rim_rate * 0.20),
        "Take Charge": _clamp01(_scale(dbpm, -3.0, 4.0) * 0.60 + wing_share * 0.20 + big_share * 0.20),
        "Foul": _clamp01(foul_pressure * 0.80 + (stl_pct + blk_pct) * 0.40),
        "Hard Foul": _clamp01(foul_pressure * 0.70 + big_share * 0.20 + _scale(age, 20.0, 36.0) * 0.10),
        "Pass Interception": _clamp01(_scale(stl_pct, 0.005, 0.040) * 1.20 + wing_share * 0.20),
        "On-Ball Steal": _clamp01(_scale(stl_pct, 0.005, 0.040) * 1.10 + guard_share * 0.25),
        "Block": _clamp01(_scale(blk_pct, 0.005, 0.080) * 1.30 + big_share * 0.40 + height_scale * 0.20),
        "Contest Shot": _clamp01(_scale(blk_pct, 0.005, 0.080) * 0.70 + _scale(stl_pct, 0.005, 0.040) * 0.30 + big_share * 0.30 + wing_share * 0.20),
    }

    output: list[int] = []
    for i, tendency in enumerate(tendencies):
        calc = values.get(tendency)
        if calc is None:
            calc = _clamp01((defaults[i] / 100.0) * (0.85 + 0.30 * _scale(usg, 0.08, 0.35)))

        blended = _clamp01(0.25 * (defaults[i] / 100.0) + 0.75 * calc)
        cap_ratio = _clamp01(caps[i] / 100.0)
        final_ratio = min(blended, cap_ratio)
        output.append(int(round(final_ratio * 100)))

    return output


def generate(output_path: Path, root: Path, rules_filename: str, pattern: str) -> None:
    rules_path = root / rules_filename
    if not rules_path.exists():
        raise FileNotFoundError(f"Rules file not found: {rules_path}")

    tendencies, defaults, caps = _load_rules(rules_path)

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
                    tendency_values = _calculate_tendencies(row, tendencies, defaults, caps)
                    writer.writerow(id_values + tendency_values)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Generate stat-based tendencies for all era-split attribute_source CSV files "
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
