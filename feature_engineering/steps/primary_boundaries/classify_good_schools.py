#!/usr/bin/env python
"""Classify primary schools into good vs normal by overall subscription rates.

Rule:
- Good schools = top N (default 59) by oversubscription score.
- Oversubscription score is computed as total applicants / total vacancies
  across 2A, 2B, 2C, 2C(S) phase ratios in schools.csv.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any, Optional, Tuple

import pandas as pd


def parse_ratio(value: Any) -> Optional[Tuple[int, int, float]]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    m = re.fullmatch(r"(\d+)\s*/\s*(\d+)", text)
    if not m:
        return None
    a = int(m.group(1))
    v = int(m.group(2))
    if v <= 0:
        return None
    return a, v, a / v


def normalize_name(name: Any) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(name).upper())


def join_key(name: Any) -> str:
    # Helps align names like "CATHOLIC HIGH SCHOOL (PRIMARY)" with
    # "CATHOLIC HIGH SCHOOL" from school location sources.
    key = normalize_name(name)
    if key.endswith("PRIMARY"):
        key = key[: -len("PRIMARY")]
    return key


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Classify good schools by overall subscription rates"
    )
    repo_root = Path(__file__).resolve().parents[3]
    parser.add_argument(
        "--school-ratio-csv",
        default=str(repo_root / "primary_school_scrape" / "schools.csv"),
        help="Path to school oversubscription source file",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=59,
        help="Top N schools classified as good",
    )
    parser.add_argument(
        "--output-dir",
        default=str(Path(__file__).resolve().parent / "outputs"),
        help="Output directory",
    )
    args = parser.parse_args()

    src = Path(args.school_ratio_csv)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not src.exists():
        raise FileNotFoundError(f"School ratio CSV not found: {src}")

    df = pd.read_csv(src)

    ratio_cols = ["Phase_2A_Ratio", "Phase_2B_ratio", "Phase_2C_ratio", "Phase_2C_sup_ratio"]
    rows = []
    for _, row in df.iterrows():
        applicants = 0
        vacancies = 0
        for col in ratio_cols:
            parsed = parse_ratio(row.get(col))
            if parsed:
                a, v, _ = parsed
                applicants += a
                vacancies += v

        score = (applicants / vacancies) if vacancies > 0 else float("nan")
        rows.append(
            {
                "school_name": row["Name"],
                "join_key": join_key(row["Name"]),
                "overall_subscription_rates": score,
                "applicants_total": applicants,
                "vacancies_total": vacancies,
            }
        )

    ranking = pd.DataFrame(rows).dropna(subset=["overall_subscription_rates"]).copy()
    ranking = ranking.sort_values(
        ["overall_subscription_rates", "applicants_total"],
        ascending=[False, False],
    ).reset_index(drop=True)
    ranking["rank"] = ranking.index + 1
    ranking["is_good_school"] = ranking["rank"] <= int(args.top_n)
    ranking["school_tier"] = ranking["is_good_school"].map({True: "Good", False: "Normal"})

    all_out = out_dir / "overall_subscription_rates.csv"
    good_out = out_dir / "good_primary_schools.csv"
    normal_out = out_dir / "normal_schools_others.csv"
    legacy_all_out = out_dir / "school_oversubscription_ranking.csv"
    legacy_good_out = out_dir / "good_schools_top59.csv"

    ranking.to_csv(all_out, index=False, encoding="utf-8-sig")
    ranking.to_csv(legacy_all_out, index=False, encoding="utf-8-sig")
    ranking[ranking["is_good_school"]].to_csv(good_out, index=False, encoding="utf-8-sig")
    ranking[ranking["is_good_school"]].to_csv(legacy_good_out, index=False, encoding="utf-8-sig")
    ranking[~ranking["is_good_school"]].to_csv(normal_out, index=False, encoding="utf-8-sig")

    print("Done.")
    print(f"Total ranked schools: {len(ranking)}")
    print(f"Good schools (top {args.top_n}): {(ranking['is_good_school']).sum()}")
    print(f"Saved overall subscription rates: {all_out}")
    print(f"Saved good schools: {good_out}")
    print(f"Saved normal schools: {normal_out}")


if __name__ == "__main__":
    main()
