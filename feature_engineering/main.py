from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
FEATURE_ENGINEERING_DIR = REPO_ROOT / "feature_engineering"
PRIMARY_BOUNDARY_STEPS_DIR = FEATURE_ENGINEERING_DIR / "steps" / "primary_boundaries"
WALKABILITY_STEPS_DIR = FEATURE_ENGINEERING_DIR / "steps" / "walkability"

DATA_DIR = REPO_ROOT / "data" / "feature_engineering"
INPUTS_DIR = DATA_DIR / "inputs"
INTERMEDIATE_DIR = DATA_DIR / "intermediate"
OUTPUTS_DIR = DATA_DIR / "outputs"


PRIMARY_BOUNDARY_SCRIPTS = {
    "build_primary_school_boundaries": PRIMARY_BOUNDARY_STEPS_DIR / "build_primary_school_boundaries.py",
    "classify_good_schools": PRIMARY_BOUNDARY_STEPS_DIR / "classify_good_schools.py",
    "build_school_boundary_layers": PRIMARY_BOUNDARY_STEPS_DIR / "build_school_boundary_layers.py",
    "build_shopping_centre_layers": PRIMARY_BOUNDARY_STEPS_DIR / "build_shopping_centre_layers.py",
    "build_mrt_exit_layers": PRIMARY_BOUNDARY_STEPS_DIR / "build_mrt_exit_layers.py",
    "build_hdb_building_layers": PRIMARY_BOUNDARY_STEPS_DIR / "build_hdb_building_layers.py",
    "build_resale_school_features_onemap": PRIMARY_BOUNDARY_STEPS_DIR / "build_resale_school_features_onemap.py",
    "build_resale_school_buffer_features_osmnx": PRIMARY_BOUNDARY_STEPS_DIR / "build_resale_school_buffer_features_osmnx.py",
    "generate_resale_descriptive_analysis": PRIMARY_BOUNDARY_STEPS_DIR / "generate_resale_descriptive_analysis.py",
}

BOUNDARY_PIPELINE = [
    "build_primary_school_boundaries",
    "classify_good_schools",
    "build_school_boundary_layers",
    "build_shopping_centre_layers",
    "build_mrt_exit_layers",
    "build_hdb_building_layers",
]


def ensure_data_dirs() -> None:
    INPUTS_DIR.mkdir(parents=True, exist_ok=True)
    INTERMEDIATE_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)


def run_python_script(script_path: Path, args: list[str] | None = None) -> None:
    command = [sys.executable, str(script_path), *(args or [])]
    subprocess.run(command, cwd=REPO_ROOT, check=True)


def sync_outputs() -> None:
    ensure_data_dirs()

    for source_dir in [
        PRIMARY_BOUNDARY_STEPS_DIR / "outputs",
        WALKABILITY_STEPS_DIR / "outputs",
    ]:
        if not source_dir.exists():
            continue
        for source_path in source_dir.rglob("*"):
            if source_path.is_dir():
                continue
            relative_path = source_path.relative_to(source_dir)
            destination = OUTPUTS_DIR / relative_path
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, destination)


def run_step(step_name: str) -> None:
    if step_name not in PRIMARY_BOUNDARY_SCRIPTS:
        available = ", ".join(sorted(PRIMARY_BOUNDARY_SCRIPTS))
        raise SystemExit(f"Unknown step '{step_name}'. Available steps: {available}")
    run_python_script(PRIMARY_BOUNDARY_SCRIPTS[step_name])


def run_pipeline() -> None:
    for step_name in BOUNDARY_PIPELINE:
        run_step(step_name)
    sync_outputs()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Feature engineering pipeline coordinator")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("sync-outputs", help="Copy step outputs into data/feature_engineering/outputs")

    run_step_parser = subparsers.add_parser("run-step", help="Run one primary-boundary feature step")
    run_step_parser.add_argument("step_name", choices=sorted(PRIMARY_BOUNDARY_SCRIPTS))

    subparsers.add_parser("run-pipeline", help="Run the current boundary pipeline and sync outputs")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "sync-outputs":
        sync_outputs()
    elif args.command == "run-step":
        run_step(args.step_name)
    elif args.command == "run-pipeline":
        run_pipeline()


if __name__ == "__main__":
    main()
