#!/usr/bin/env python3
"""Build a static school distribution map split by Good vs Not Good schools."""

from __future__ import annotations

import re
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]

INPUT_SCHOOL_POINTS = REPO_ROOT / "primary_boundaries" / "outputs" / "primary_school_landuse_join_points.geojson"
INPUT_SCHOOL_RANKING = REPO_ROOT / "primary_boundaries" / "outputs" / "overall_subscription_rates.csv"
INPUT_PLANNING_BOUNDARY = REPO_ROOT / "primary_boundaries" / "inputs" / "MasterPlan2019PlanningAreaBoundaryNoSea.geojson"

OUTPUT_STATIC_MAP = REPO_ROOT / "docs" / "assets" / "figures" / "school_location_distribution_map_static.png"


def normalize_school_name(value: object) -> str:
    text = "" if value is None else str(value)
    return re.sub(r"[^A-Z0-9]", "", text.upper())


def parse_bool(value: object) -> bool:
    text = str(value).strip().lower()
    return text in {"true", "1", "yes", "y"}


def main() -> None:
    points = gpd.read_file(INPUT_SCHOOL_POINTS)
    points["join_key"] = points["school_name"].map(normalize_school_name)

    ranking = pd.read_csv(INPUT_SCHOOL_RANKING)
    ranking["join_key"] = ranking["join_key"].astype(str).str.strip().str.upper()
    ranking["is_good_school_bool"] = ranking["is_good_school"].map(parse_bool)
    ranking = ranking[["join_key", "is_good_school_bool"]].drop_duplicates()

    merged = points.merge(ranking, on="join_key", how="left")
    merged["is_good_school_bool"] = merged["is_good_school_bool"].map(
        lambda value: bool(value) if pd.notna(value) else False
    )

    planning = gpd.read_file(INPUT_PLANNING_BOUNDARY)[["geometry"]]
    planning = planning[planning.geometry.notna() & ~planning.geometry.is_empty].copy()

    good = merged[merged["is_good_school_bool"]].copy()
    not_good = merged[~merged["is_good_school_bool"]].copy()

    fig, ax = plt.subplots(figsize=(10, 8))
    planning.plot(ax=ax, facecolor="#f5f5f5", edgecolor="#b0bec5", linewidth=0.4)
    if not not_good.empty:
        not_good.plot(ax=ax, color="#1e88e5", markersize=12, alpha=0.8, label=f"Not good ({len(not_good)})")
    if not good.empty:
        good.plot(ax=ax, color="#2e7d32", markersize=16, alpha=0.9, label=f"Good ({len(good)})")

    ax.set_title("Primary School Distribution (Good vs Not Good)", fontsize=12)
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_aspect("equal")
    ax.legend(loc="lower left", frameon=True)
    fig.tight_layout()

    OUTPUT_STATIC_MAP.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUTPUT_STATIC_MAP, dpi=180)
    plt.close(fig)

    print(f"Wrote static map: {OUTPUT_STATIC_MAP}")
    print(f"Good schools: {len(good)}")
    print(f"Not good schools: {len(not_good)}")


if __name__ == "__main__":
    main()
