#!/usr/bin/env python3
"""Run the portable core reconstruction, optional extensions, and figures."""

from __future__ import annotations

import argparse
import importlib
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.core import PROJECT_ID, run as run_core  # noqa: E402


def _find_rscript(explicit: str | None) -> str:
    candidate = explicit or os.environ.get("R_SCRIPT") or shutil.which("Rscript")
    if not candidate:
        raise RuntimeError(
            "Rscript was not found. Use --rscript <path>, set R_SCRIPT, or add Rscript to PATH."
        )
    resolved = shutil.which(candidate) if not Path(candidate).exists() else candidate
    if not resolved:
        raise RuntimeError(f"Rscript executable was not found: {candidate}")
    return str(resolved)


def _run_figures(reference_dir: Path, out_root: Path, explicit_rscript: str | None) -> dict[str, Any]:
    rscript = _find_rscript(explicit_rscript)
    figure_script = REPO_ROOT / "plotting" / "plot_figures.R"
    figure_out = out_root / "figures"
    figure_out.mkdir(parents=True, exist_ok=True)
    command = [rscript, "--vanilla", str(figure_script), str(reference_dir), str(figure_out)]
    result = subprocess.run(command, check=False, text=True, capture_output=True)
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    if result.returncode != 0:
        raise RuntimeError(f"Figure reproduction failed with Rscript exit code {result.returncode}")
    export_dir = figure_out / "exports"
    rendered = len(list(export_dir.glob("*.pdf")))
    if rendered != 10:
        raise RuntimeError(f"Figure rendering failed: found {rendered} PDF compositions.")
    return {
        "figure_compositions": rendered,
        "render_formats": ["PDF", "PNG", "SVG"],
        "output_subdirectory": "figures",
    }


def _run_extension_hook(out_root: Path) -> dict[str, Any]:
    extension_file = REPO_ROOT / "src" / "extensions.py"
    if not extension_file.is_file():
        raise RuntimeError("The default reproduction requires src/extensions.py; use --core-only to skip it explicitly.")
    module = importlib.import_module("src.extensions")
    runner = getattr(module, "run", None)
    if not callable(runner):
        raise RuntimeError("src/extensions.py must expose run(repo_root, out_root)")
    runner(REPO_ROOT, out_root)
    return {}


def _run_ciha_hook(out_root: Path) -> dict[str, Any]:
    ciha_file = REPO_ROOT / "src" / "ciha.py"
    if not ciha_file.is_file():
        raise RuntimeError("--ciha was requested but src/ciha.py is not present")
    module = importlib.import_module("src.ciha")
    runner = getattr(module, "run", None)
    if not callable(runner):
        raise RuntimeError("src/ciha.py must expose run(repo_root, out_root)")
    runner(REPO_ROOT, out_root)
    return {}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Reproduce the four-state 2019/2024 TISS–SUS aggregate tables."
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=REPO_ROOT / "out",
        help="Output directory (default: repository out/).",
    )
    parser.add_argument(
        "--figures",
        action="store_true",
        help="Also render the 10 figures and 22 panel-data CSVs with R.",
    )
    parser.add_argument(
        "--rscript",
        help="Rscript executable; defaults to R_SCRIPT environment variable, then PATH.",
    )
    parser.add_argument(
        "--use-supplied-H",
        action="store_true",
        help="Development fallback: use H_STRATA.csv if joint_counts_known.csv is absent; pair with --core-only.",
    )
    parser.add_argument(
        "--ciha",
        action="store_true",
        help="Also run the optional aggregate CIHA/SIH bootstrap extension (requires its optional dependencies).",
    )
    parser.add_argument(
        "--core-only",
        action="store_true",
        help="Development option: skip src/extensions.py. The default run includes core and extensions.",
    )
    args = parser.parse_args()
    out_root = args.out.expanduser().resolve()
    out_root.mkdir(parents=True, exist_ok=True)

    core_report = run_core(REPO_ROOT, out_root, use_supplied_h=args.use_supplied_H)
    if not args.core_only:
        _run_extension_hook(out_root)
    if args.figures:
        _run_figures(REPO_ROOT / "core" / "reference", out_root, args.rscript)
    if args.ciha:
        _run_ciha_hook(out_root)
    print(f"core: completed (independent H reselection: {core_report['independent_h_reselection']})")
    print(f"extensions: {'completed' if not args.core_only else 'not requested'}")
    print(f"figures: {'completed' if args.figures else 'not requested'}")
    print(f"ciha: {'completed' if args.ciha else 'not requested'}")
    print(f"output: {out_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
