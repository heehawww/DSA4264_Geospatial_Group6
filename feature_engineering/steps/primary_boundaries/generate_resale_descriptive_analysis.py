#!/usr/bin/env python
"""Generate descriptive analysis outputs for resale flats feature dataset."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


def first_existing(columns: Iterable[str], candidates: list[str]) -> list[str]:
    cols = set(columns)
    return [c for c in candidates if c in cols]


def save_bar_plot(
    data: pd.DataFrame,
    x_col: str,
    y_col: str,
    title: str,
    xlabel: str,
    ylabel: str,
    output_path: Path,
    rotate_x: int = 0,
    figsize: tuple[int, int] = (12, 6),
) -> None:
    fig, ax = plt.subplots(figsize=figsize)
    ax.bar(data[x_col].astype(str), data[y_col], color="#2b8cbe")
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    if rotate_x:
        ax.tick_params(axis="x", rotation=rotate_x)
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def save_hist_plot(
    series: pd.Series,
    title: str,
    xlabel: str,
    output_path: Path,
    bins: int = 50,
    figsize: tuple[int, int] = (10, 6),
) -> None:
    fig, ax = plt.subplots(figsize=figsize)
    ax.hist(series.dropna(), bins=bins, color="#31a354", alpha=0.9, edgecolor="white")
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel("Count")
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def save_boxplot_by_group(
    df: pd.DataFrame,
    group_col: str,
    value_col: str,
    title: str,
    ylabel: str,
    output_path: Path,
    figsize: tuple[int, int] = (12, 6),
) -> None:
    work = df[[group_col, value_col]].dropna().copy()
    order = (
        work.groupby(group_col)[value_col]
        .median()
        .sort_values()
        .index.tolist()
    )
    data = [work.loc[work[group_col] == g, value_col].to_numpy() for g in order]

    fig, ax = plt.subplots(figsize=figsize)
    labels = [str(x) for x in order]
    try:
        ax.boxplot(data, tick_labels=labels, showfliers=False)
    except TypeError:
        ax.boxplot(data, labels=labels, showfliers=False)
    ax.set_title(title)
    ax.set_xlabel(group_col)
    ax.set_ylabel(ylabel)
    ax.tick_params(axis="x", rotation=35)
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def create_overall_price_stats(df: pd.DataFrame) -> pd.DataFrame:
    s = pd.to_numeric(df["resale_price"], errors="coerce").dropna()
    stats = {
        "count": int(s.count()),
        "mean": float(s.mean()),
        "median": float(s.median()),
        "std": float(s.std()),
        "min": float(s.min()),
        "p10": float(s.quantile(0.10)),
        "p25": float(s.quantile(0.25)),
        "p75": float(s.quantile(0.75)),
        "p90": float(s.quantile(0.90)),
        "p95": float(s.quantile(0.95)),
        "p99": float(s.quantile(0.99)),
        "max": float(s.max()),
    }
    return pd.DataFrame([stats])


def create_by_flat_type_price_stats(df: pd.DataFrame) -> pd.DataFrame:
    g = (
        df.groupby("flat_type", dropna=False)["resale_price"]
        .agg(["count", "mean", "median", "std", "min", "max"])
        .reset_index()
    )
    q = (
        df.groupby("flat_type", dropna=False)["resale_price"]
        .quantile([0.10, 0.25, 0.75, 0.90])
        .unstack()
        .reset_index()
        .rename(columns={0.10: "p10", 0.25: "p25", 0.75: "p75", 0.90: "p90"})
    )
    out = g.merge(q, on="flat_type", how="left")
    out = out.sort_values("count", ascending=False)
    return out


def create_distribution_table(df: pd.DataFrame, col: str) -> pd.DataFrame:
    out = (
        df[col]
        .fillna("Unknown")
        .astype(str)
        .value_counts(dropna=False)
        .rename_axis(col)
        .reset_index(name="count")
    )
    out["pct"] = out["count"] / out["count"].sum()
    return out


def create_numeric_factor_distribution(
    df: pd.DataFrame,
    factor_cols: list[str],
) -> pd.DataFrame:
    frames = []
    for col in factor_cols:
        if col not in df.columns:
            continue
        w = df[[col, "resale_price"]].copy()
        w[col] = pd.to_numeric(w[col], errors="coerce")
        w = w.dropna(subset=[col])
        if w.empty:
            continue
        tmp = (
            w.groupby(col)["resale_price"]
            .agg(count="size", mean_price="mean", median_price="median")
            .reset_index()
            .rename(columns={col: "value"})
        )
        tmp.insert(0, "factor", col)
        tmp["pct"] = tmp["count"] / tmp["count"].sum()
        frames.append(tmp)
    if not frames:
        return pd.DataFrame(columns=["factor", "value", "count", "pct", "mean_price", "median_price"])
    out = pd.concat(frames, ignore_index=True)
    return out


def create_numeric_summary(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    rows = []
    for col in cols:
        if col not in df.columns:
            continue
        s = pd.to_numeric(df[col], errors="coerce").dropna()
        if s.empty:
            continue
        rows.append(
            {
                "column": col,
                "count": int(s.count()),
                "mean": float(s.mean()),
                "median": float(s.median()),
                "std": float(s.std()),
                "min": float(s.min()),
                "p25": float(s.quantile(0.25)),
                "p75": float(s.quantile(0.75)),
                "max": float(s.max()),
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Descriptive investigation for resale flats dataset")
    parser.add_argument(
        "--input-csv",
        default=str(
            Path(__file__).resolve().parent / "outputs" / "resale_flats_with_school_buffer_counts.csv"
        ),
        help="Input resale feature CSV",
    )
    parser.add_argument(
        "--output-dir",
        default=str(
            Path(__file__).resolve().parent / "outputs" / "descriptive_investigation"
        ),
        help="Output directory for tables and plots",
    )
    parser.add_argument(
        "--top-n-town",
        type=int,
        default=20,
        help="Number of towns for top-town plot",
    )
    args = parser.parse_args()

    input_csv = Path(args.input_csv)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not input_csv.exists():
        raise FileNotFoundError(f"Input CSV not found: {input_csv}")

    print("Loading dataset...")
    df = pd.read_csv(input_csv)

    # Core typing.
    for col in [
        "resale_price",
        "floor_area_sqm",
        "nearest_mall_walking_distance_m",
        "nearest_mrt_walking_distance_m",
        "malls_within_10min_walk",
        "mrt_unique_lines_within_10min_walk",
        "school_count_1km",
        "good_school_count_1km",
        "school_count_2km",
        "good_school_count_2km",
    ]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["resale_price"]).copy()
    df["town"] = df.get("town", pd.Series(index=df.index, dtype=object)).fillna("Unknown").astype(str)
    df["flat_type"] = df.get("flat_type", pd.Series(index=df.index, dtype=object)).fillna("Unknown").astype(str)

    # a) Location distribution.
    print("Computing location distribution...")
    town_dist = create_distribution_table(df, "town")
    town_price = (
        df.groupby("town")["resale_price"]
        .agg(town_median_price="median", town_mean_price="mean")
        .reset_index()
    )
    town_dist = town_dist.merge(town_price, on="town", how="left")
    town_dist.to_csv(out_dir / "a_location_distribution_town.csv", index=False, encoding="utf-8-sig")

    # b) Flat type distribution.
    print("Computing flat type distribution...")
    flat_dist = create_distribution_table(df, "flat_type")
    flat_price = (
        df.groupby("flat_type")["resale_price"]
        .agg(flat_type_median_price="median", flat_type_mean_price="mean")
        .reset_index()
    )
    flat_dist = flat_dist.merge(flat_price, on="flat_type", how="left")
    flat_dist.to_csv(out_dir / "b_flat_type_distribution.csv", index=False, encoding="utf-8-sig")

    # c) Cost distribution overall and by flat type.
    print("Computing cost distribution...")
    overall_price = create_overall_price_stats(df)
    overall_price.to_csv(out_dir / "c1_price_distribution_overall.csv", index=False, encoding="utf-8-sig")

    by_flat_type_price = create_by_flat_type_price_stats(df)
    by_flat_type_price.to_csv(out_dir / "c2_price_distribution_by_flat_type.csv", index=False, encoding="utf-8-sig")

    # d) Number of lines close to estate.
    print("Computing MRT-line proximity distribution...")
    mrt_col = "mrt_unique_lines_within_10min_walk"
    if mrt_col in df.columns:
        mrt_lines_dist = (
            df.groupby(mrt_col)["resale_price"]
            .agg(count="size", mean_price="mean", median_price="median")
            .reset_index()
            .sort_values(mrt_col)
        )
        mrt_lines_dist["pct"] = mrt_lines_dist["count"] / mrt_lines_dist["count"].sum()
    else:
        mrt_lines_dist = pd.DataFrame(columns=[mrt_col, "count", "mean_price", "median_price", "pct"])
    mrt_lines_dist.to_csv(out_dir / "d_mrt_lines_within_10min_distribution.csv", index=False, encoding="utf-8-sig")

    # e) Other relevant factors.
    print("Computing other factor summaries...")
    other_discrete_factors = [
        "malls_within_10min_walk",
        "school_count_1km",
        "good_school_count_1km",
        "school_count_2km",
        "good_school_count_2km",
    ]
    other_factor_dist = create_numeric_factor_distribution(df, other_discrete_factors)
    other_factor_dist.to_csv(out_dir / "e1_other_discrete_factor_distributions.csv", index=False, encoding="utf-8-sig")

    continuous_factors = [
        "floor_area_sqm",
        "nearest_mall_walking_distance_m",
        "nearest_mrt_walking_distance_m",
    ]
    other_cont_summary = create_numeric_summary(df, continuous_factors)
    other_cont_summary.to_csv(out_dir / "e2_other_continuous_factor_summary.csv", index=False, encoding="utf-8-sig")

    corr_cols = first_existing(
        df.columns,
        ["resale_price"] + other_discrete_factors + continuous_factors,
    )
    corr_df = df[corr_cols].corr(numeric_only=True)
    corr_df.to_csv(out_dir / "e3_correlation_matrix.csv", encoding="utf-8-sig")

    if "month" in df.columns:
        monthly = (
            df.groupby("month")["resale_price"]
            .agg(count="size", mean_price="mean", median_price="median")
            .reset_index()
            .sort_values("month")
        )
        monthly.to_csv(out_dir / "e4_monthly_price_trend.csv", index=False, encoding="utf-8-sig")

    # Plots.
    print("Generating plots...")
    top_town = town_dist.head(args.top_n_town)
    save_bar_plot(
        top_town,
        x_col="town",
        y_col="count",
        title=f"Top {args.top_n_town} Towns by Resale Transaction Count",
        xlabel="Town",
        ylabel="Count",
        output_path=out_dir / "plot_a_town_distribution_top.png",
        rotate_x=40,
        figsize=(13, 6),
    )

    save_bar_plot(
        flat_dist,
        x_col="flat_type",
        y_col="count",
        title="Flat Type Distribution",
        xlabel="Flat Type",
        ylabel="Count",
        output_path=out_dir / "plot_b_flat_type_distribution.png",
        rotate_x=30,
        figsize=(10, 6),
    )

    save_hist_plot(
        df["resale_price"],
        title="Resale Price Distribution (All Flats)",
        xlabel="Resale Price (SGD)",
        output_path=out_dir / "plot_c1_price_hist_all.png",
        bins=80,
        figsize=(11, 6),
    )

    save_boxplot_by_group(
        df,
        group_col="flat_type",
        value_col="resale_price",
        title="Resale Price Distribution by Flat Type",
        ylabel="Resale Price (SGD)",
        output_path=out_dir / "plot_c2_price_box_by_flat_type.png",
        figsize=(12, 6),
    )

    if not mrt_lines_dist.empty:
        mrt_plot = mrt_lines_dist.rename(columns={mrt_col: "lines"})
        save_bar_plot(
            mrt_plot,
            x_col="lines",
            y_col="count",
            title="Unique MRT Lines Within 10-Min Walk (800m)",
            xlabel="Unique MRT line count",
            ylabel="Transaction count",
            output_path=out_dir / "plot_d_mrt_lines_distribution.png",
            rotate_x=0,
            figsize=(9, 5),
        )

    malls_col = "malls_within_10min_walk"
    if malls_col in df.columns:
        malls_dist = (
            df.groupby(malls_col)["resale_price"]
            .size()
            .reset_index(name="count")
            .sort_values(malls_col)
        )
        save_bar_plot(
            malls_dist,
            x_col=malls_col,
            y_col="count",
            title="Malls Within 10-Min Walk (800m)",
            xlabel="Mall count",
            ylabel="Transaction count",
            output_path=out_dir / "plot_e_malls_within_10min_distribution.png",
            rotate_x=0,
            figsize=(9, 5),
        )

    print("Done.")
    print(f"Input rows analysed: {len(df)}")
    print(f"Saved outputs to: {out_dir}")
    print("Key files:")
    print(f"- {out_dir / 'a_location_distribution_town.csv'}")
    print(f"- {out_dir / 'b_flat_type_distribution.csv'}")
    print(f"- {out_dir / 'c1_price_distribution_overall.csv'}")
    print(f"- {out_dir / 'c2_price_distribution_by_flat_type.csv'}")
    print(f"- {out_dir / 'd_mrt_lines_within_10min_distribution.csv'}")
    print(f"- {out_dir / 'e1_other_discrete_factor_distributions.csv'}")
    print(f"- {out_dir / 'e2_other_continuous_factor_summary.csv'}")
    print(f"- {out_dir / 'e3_correlation_matrix.csv'}")


if __name__ == "__main__":
    main()
