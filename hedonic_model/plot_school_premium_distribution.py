#!/usr/bin/env python3
"""Plot school-specific RDD premiums by school group."""

from __future__ import annotations

import argparse
from pathlib import Path

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np
import pandas as pd


def normalise_bool(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.lower().isin({"true", "1", "yes"})


def load_school_groups(buffers_geojson: Path) -> pd.DataFrame:
    buffers = gpd.read_file(buffers_geojson)[["school_name", "is_good_school"]].copy()
    buffers["is_good_school"] = normalise_bool(buffers["is_good_school"])
    buffers["school_group"] = np.where(buffers["is_good_school"], "good", "non_good")
    return buffers[["school_name", "school_group"]].drop_duplicates()


def prepare_plot_df(
    results_csv: Path,
    buffers_geojson: Path,
    bandwidth_m: int,
    specification: str,
    premium_column: str,
) -> pd.DataFrame:
    df = pd.read_csv(results_csv)
    if "Unnamed: 7" in df.columns:
        df = df.drop(columns=["Unnamed: 7"])

    df = df.loc[(df["bandwidth_m"] == bandwidth_m) & (df["specification"] == specification)].copy()
    if df.empty:
        raise ValueError(f"No rows found for bandwidth={bandwidth_m} and specification={specification}.")

    if "school_group" not in df.columns:
        groups = load_school_groups(buffers_geojson)
        df = df.merge(groups, left_on="boundary_school_name", right_on="school_name", how="left")
        df = df.drop(columns=["school_name"])

    missing_group = df["school_group"].isna().sum()
    if missing_group:
        raise ValueError(f"{missing_group} school rows could not be matched to a school_group.")

    if premium_column not in df.columns:
        raise ValueError(f"Premium column '{premium_column}' not found in {results_csv}.")

    df = df[["boundary_school_name", "school_group", premium_column]].dropna().copy()
    return df


def build_plot(plot_df: pd.DataFrame, premium_column: str, output_png: Path) -> pd.DataFrame:
    group_order = ["non_good", "good"]
    x_positions = {"non_good": 0, "good": 1}
    colors = {"non_good": "#94a3b8", "good": "#1d4ed8"}
    labels = {"non_good": "Non-good schools", "good": "Good schools"}

    rng = np.random.default_rng(42)
    fig, ax = plt.subplots(figsize=(9, 6))

    summaries: list[dict[str, float | str | int]] = []
    for group in group_order:
        subset = plot_df.loc[plot_df["school_group"] == group].copy()
        if subset.empty:
            continue

        x = np.full(len(subset), x_positions[group], dtype=float)
        jitter = rng.uniform(-0.12, 0.12, size=len(subset))
        ax.scatter(
            x + jitter,
            subset[premium_column],
            s=46,
            alpha=0.75,
            color=colors[group],
            edgecolors="white",
            linewidths=0.5,
            label=labels[group],
        )

        mean_value = float(subset[premium_column].mean())
        ax.hlines(
            y=mean_value,
            xmin=x_positions[group] - 0.22,
            xmax=x_positions[group] + 0.22,
            color=colors[group],
            linewidth=3,
        )
        ax.text(
            x_positions[group],
            mean_value,
            f"Mean: {mean_value:,.0f}",
            ha="center",
            va="bottom",
            fontsize=10,
            color=colors[group],
            bbox={"boxstyle": "round,pad=0.2", "facecolor": "white", "edgecolor": "none", "alpha": 0.9},
        )

        summaries.append(
            {
                "school_group": group,
                "n_schools": int(len(subset)),
                "mean_premium": mean_value,
                "median_premium": float(subset[premium_column].median()),
            }
        )

    ax.axhline(0, color="#334155", linewidth=1, linestyle="--", alpha=0.7)
    ax.set_xticks([x_positions[group] for group in group_order])
    ax.set_xticklabels([labels[group] for group in group_order])
    ax.set_ylabel("Estimated premium at local mean price (S$)")
    ax.set_title("School-specific local boundary premiums\nControlled RDD at 100m bandwidth")
    ax.grid(axis="y", linestyle=":", alpha=0.4)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    fig.tight_layout()
    output_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_png, dpi=200, bbox_inches="tight")
    plt.close(fig)

    return pd.DataFrame(summaries)


def main() -> None:
    parser = argparse.ArgumentParser(description="Plot school-specific RDD premiums by school group")
    parser.add_argument(
        "--results-csv",
        default="hedonic_model/rdd_outputs/school_specific_rdd_results.csv",
        help="CSV with school-specific RDD results",
    )
    parser.add_argument(
        "--buffers-geojson",
        default="primary_boundaries/outputs/primary_school_boundaries_buffer_1km.geojson",
        help="School buffer file used to recover school groups if needed",
    )
    parser.add_argument(
        "--bandwidth-m",
        type=int,
        default=100,
        help="Bandwidth to plot",
    )
    parser.add_argument(
        "--specification",
        default="controlled",
        choices=["controlled", "uncontrolled"],
        help="RDD specification to plot",
    )
    parser.add_argument(
        "--premium-column",
        default="cutoff_price_jump_sgd_at_local_mean_price",
        help="Premium column to plot",
    )
    parser.add_argument(
        "--output-png",
        default="hedonic_model/rdd_outputs/school_premium_distribution_100m_controlled.png",
        help="Output path for the figure",
    )
    parser.add_argument(
        "--output-summary-csv",
        default="hedonic_model/rdd_outputs/school_premium_distribution_100m_controlled_summary.csv",
        help="Output path for summary statistics used in the figure",
    )
    args = parser.parse_args()

    plot_df = prepare_plot_df(
        results_csv=Path(args.results_csv),
        buffers_geojson=Path(args.buffers_geojson),
        bandwidth_m=args.bandwidth_m,
        specification=args.specification,
        premium_column=args.premium_column,
    )
    summary_df = build_plot(
        plot_df=plot_df,
        premium_column=args.premium_column,
        output_png=Path(args.output_png),
    )
    summary_df.to_csv(Path(args.output_summary_csv), index=False)

    print(summary_df.to_string(index=False))
    print(f"Wrote figure to {args.output_png}")


if __name__ == "__main__":
    main()
