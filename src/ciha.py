"""Optional aggregate-only CIHA/SIH reproduction hook.

The module stays standard-library-only at import time. NumPy and pandas are
needed only when the optional CIHA reproduction is requested.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any


ORIGINAL_AGGREGATE_SHA256 = "a13546f56014ddf665f6affa5a2764863327a306b7521f6e1c5f7eae44ffa47f"
REFERENCE_SOURCE_SHA256 = "f94ca5a280142afe457be707c6384642f2cd2cc6e1bf6b7cd4f8bcbaf8681d63"
REFERENCE_TOLERANCE = 1e-9
EXPECTED_BRANCH_ROWS = 16
EXPECTED_REPORTABLE_INTERVALS = 5


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _is_blank(value: Any) -> bool:
    if value is None:
        return True
    try:
        import pandas as pd

        if pd.isna(value):
            return True
    except (ImportError, TypeError, ValueError):
        pass
    return isinstance(value, str) and not value.strip()


def _number(value: Any, context: str) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Expected a numeric value in {context}; got {value!r}") from exc
    if not math.isfinite(parsed):
        raise ValueError(f"Expected a finite numeric value in {context}; got {value!r}")
    return parsed


def _compare_reference(actual, reference_path: Path) -> dict[str, Any]:
    """Compare completed calculations with the frozen result table.

    The reference is read only here, after ``analyze_counts`` has completed; it
    never supplies values to the calculation.
    """
    import pandas as pd

    reference = pd.read_csv(reference_path, dtype="string", keep_default_na=False, encoding="utf-8-sig")
    actual = actual.reset_index(drop=True)
    actual_columns = list(actual.columns)
    reference_columns = list(reference.columns)
    mismatches: list[dict[str, Any]] = []
    if actual_columns != reference_columns:
        mismatches.append({"kind": "columns", "actual": actual_columns, "reference": reference_columns})
    if len(actual) != len(reference):
        mismatches.append({"kind": "row_count", "actual": len(actual), "reference": len(reference)})
    if mismatches:
        return {
            "matched": False,
            "tolerance": REFERENCE_TOLERANCE,
            "exact_fields_checked": [],
            "numeric_fields_checked": [],
            "mismatch_count": len(mismatches),
            "mismatches": mismatches,
        }

    exact_fields = (
        "branch",
        "target_definition",
        "stratum_definition",
        "gate_status",
        "gate_reasons",
        "bootstrap_method",
        "bootstrap_interval_status",
        "bootstrap_diagnostic",
    )
    integer_fields = {
        "year",
        "state_n_p",
        "state_n_s",
        "state_hospitals_p",
        "state_hospitals_s",
        "common_hospitals_n",
        "common_hospital_n_p",
        "common_hospital_n_s",
        "support_layer_n",
        "supported_hospitals_n",
        "support_n_p",
        "support_n_s",
        "bootstrap_repetitions_requested",
        "bootstrap_seed",
        "bootstrap_cluster_hospitals_n",
        "bootstrap_valid_repetitions",
    }
    numeric_fields = [
        column for column in actual_columns
        if column not in exact_fields and column not in integer_fields
    ]
    for row_index in range(len(actual)):
        for column in exact_fields:
            actual_value = "" if _is_blank(actual.at[row_index, column]) else str(actual.at[row_index, column])
            reference_value = str(reference.at[row_index, column])
            if actual_value != reference_value:
                mismatches.append({
                    "kind": "exact_value",
                    "row": row_index,
                    "field": column,
                    "actual": actual_value,
                    "reference": reference_value,
                })
        for column in integer_fields:
            actual_value = actual.at[row_index, column]
            reference_value = reference.at[row_index, column]
            if _is_blank(actual_value) or _is_blank(reference_value):
                if _is_blank(actual_value) != _is_blank(reference_value):
                    mismatches.append({
                        "kind": "integer_blankness",
                        "row": row_index,
                        "field": column,
                        "actual_blank": _is_blank(actual_value),
                        "reference_blank": _is_blank(reference_value),
                    })
                continue
            try:
                parsed_actual = int(actual_value)
                parsed_reference = int(str(reference_value))
            except (TypeError, ValueError):
                mismatches.append({
                    "kind": "integer_parse",
                    "row": row_index,
                    "field": column,
                    "actual": str(actual_value),
                    "reference": str(reference_value),
                })
                continue
            if parsed_actual != parsed_reference:
                mismatches.append({
                    "kind": "integer_value",
                    "row": row_index,
                    "field": column,
                    "actual": parsed_actual,
                    "reference": parsed_reference,
                })
        for column in numeric_fields:
            actual_value = actual.at[row_index, column]
            reference_value = reference.at[row_index, column]
            if _is_blank(actual_value) or _is_blank(reference_value):
                if _is_blank(actual_value) != _is_blank(reference_value):
                    mismatches.append({
                        "kind": "numeric_blankness",
                        "row": row_index,
                        "field": column,
                        "actual_blank": _is_blank(actual_value),
                        "reference_blank": _is_blank(reference_value),
                    })
                continue
            try:
                parsed_actual = _number(actual_value, f"actual[{row_index}].{column}")
                parsed_reference = _number(reference_value, f"reference[{row_index}].{column}")
            except ValueError as exc:
                mismatches.append({"kind": "numeric_parse", "row": row_index, "field": column, "error": str(exc)})
                continue
            difference = abs(parsed_actual - parsed_reference)
            if difference > REFERENCE_TOLERANCE:
                mismatches.append({
                    "kind": "numeric_value",
                    "row": row_index,
                    "field": column,
                    "actual": parsed_actual,
                    "reference": parsed_reference,
                    "absolute_difference": difference,
                })

    max_abs_difference: dict[str, float] = {}
    numeric_value_count: dict[str, int] = {}
    for column in numeric_fields:
        differences = []
        for row_index in range(len(actual)):
            av = actual.at[row_index, column]
            rv = reference.at[row_index, column]
            if not _is_blank(av) and not _is_blank(rv):
                differences.append(abs(_number(av, column) - _number(rv, column)))
        numeric_value_count[column] = len(differences)
        max_abs_difference[column] = max(differences, default=0.0)

    return {
        "matched": not mismatches,
        "tolerance": REFERENCE_TOLERANCE,
        "row_count": len(actual),
        "exact_fields_checked": list(exact_fields),
        "integer_fields_checked": sorted(integer_fields),
        "numeric_fields_checked": numeric_fields,
        "numeric_nonblank_values_checked": numeric_value_count,
        "maximum_absolute_difference_by_numeric_field": max_abs_difference,
        "mismatch_count": len(mismatches),
        "mismatches": mismatches[:50],
    }


def _write_frame(frame, path: Path, *, rename_cluster_id: bool = False) -> None:
    output = frame.copy()
    if rename_cluster_id and "cnes" in output.columns:
        output = output.rename(columns={"cnes": "study_cluster_id"})
    output.to_csv(path, index=False, encoding="utf-8", na_rep="")


def _write_supplementary_tables(summary, output_dir: Path) -> dict[str, dict[str, Any]]:
    """Write the three manuscript tables with their frozen row scopes."""
    table_s10a_fields = [
        "branch", "year", "target_definition", "stratum_definition", "gate_status", "gate_reasons",
        "state_hospitals_p", "state_hospitals_s", "common_hospitals_n", "support_layer_n",
        "supported_hospitals_n", "support_coverage_common_hospital_p", "support_coverage_common_hospital_s",
        "bootstrap_interval_status", "bootstrap_valid_repetitions",
    ]
    table_s10b_fields = [
        "branch", "year", "target_definition", "stratum_definition", "gate_status", "rate_p", "rate_s",
        "delta_p_minus_s", "delta_percentage_points", "ci95_lower", "ci95_upper",
        "ci95_lower_percentage_points", "ci95_upper_percentage_points", "bootstrap_repetitions_requested",
        "bootstrap_seed", "bootstrap_cluster_hospitals_n", "bootstrap_valid_repetitions",
        "bootstrap_method", "bootstrap_interval_status",
    ]
    table_s10c_fields = [
        "branch", "year", "gate_status", "gate_reasons", "state_n_p", "state_n_s",
        "common_hospital_n_p", "common_hospital_n_s", "support_n_p", "support_n_s",
        "common_hospital_coverage_state_p", "common_hospital_coverage_state_s",
        "support_coverage_common_hospital_p", "support_coverage_common_hospital_s",
        "support_coverage_state_p", "support_coverage_state_s", "state_hospitals_p", "state_hospitals_s",
        "common_hospitals_n", "common_hospitals_over_state_hospitals_p",
        "common_hospitals_over_state_hospitals_s", "supported_hospitals_n", "support_layer_n",
    ]

    estimates = summary.loc[
        summary["gate_status"].eq("pass")
        & summary["bootstrap_interval_status"].eq("published_all_repetitions_valid")
    ].copy()
    if len(summary) != EXPECTED_BRANCH_ROWS or len(estimates) != EXPECTED_REPORTABLE_INTERVALS:
        raise ValueError("Supplementary CIHA tables require 16 branch-year rows and exactly 5 reportable pass rows")
    if not estimates["bootstrap_valid_repetitions"].eq(2000).all():
        raise ValueError("S10B may include only pass rows with all 2,000 bootstrap replicates valid")

    tables = {
        "table_s10a_gate_status.csv": summary[table_s10a_fields],
        "table_s10b_estimates_and_intervals.csv": estimates[table_s10b_fields],
        "table_s10c_record_denominators.csv": summary[table_s10c_fields],
    }
    metadata: dict[str, dict[str, Any]] = {}
    for filename, frame in tables.items():
        _write_frame(frame, output_dir / filename)
        metadata[filename] = {"rows": int(len(frame)), "columns": list(frame.columns)}
    return metadata


def run(repo_root: Path, out_root: Path) -> None:
    """Reproduce all frozen CIHA/SIH branches into ``out_root / 'ciha'``."""
    repo_root = Path(repo_root).expanduser().resolve()
    out_root = Path(out_root).expanduser().resolve()
    input_path = repo_root / "data" / "ciha" / "engine_counts_relabelled.csv"
    input_manifest_path = repo_root / "data" / "ciha" / "input_manifest.json"
    reference_path = repo_root / "data" / "ciha" / "reference_branch_summary.csv"
    provenance_path = repo_root / "data" / "ciha" / "reference_provenance.json"
    engine_path = repo_root / "src" / "ciha_engine.py"
    if not input_path.is_file() or not input_manifest_path.is_file() or not reference_path.is_file() or not provenance_path.is_file():
        raise FileNotFoundError("CIHA aggregate input, manifests, and frozen reference table must be present under data/ciha/")
    if not engine_path.is_file():
        raise FileNotFoundError("The frozen CIHA calculation module src/ciha_engine.py is missing")

    try:
        import numpy as np
        import pandas as pd
    except ImportError as exc:
        raise RuntimeError(
            "The optional CIHA reproduction requires the versions in requirements-ciha.txt. "
            "Install them with: python -m pip install -r requirements-ciha.txt"
        ) from exc

    manifest = _read_json(input_manifest_path)
    provenance = _read_json(provenance_path)
    actual_input_hash = _sha256(input_path)
    reference_hash = _sha256(reference_path)
    if actual_input_hash != manifest.get("sha256"):
        raise ValueError("Packaged CIHA input SHA-256 does not match data/ciha/input_manifest.json")
    if manifest.get("original_aggregate_sha256") != ORIGINAL_AGGREGATE_SHA256:
        raise ValueError("Original aggregate source hash does not match the frozen source-run provenance")
    if reference_hash != REFERENCE_SOURCE_SHA256 or provenance.get("frozen_reference_sha256") != REFERENCE_SOURCE_SHA256:
        raise ValueError("Frozen CIHA reference table SHA-256 does not match its provenance record")

    counts = pd.read_csv(input_path, dtype={"cnes": "string", "sex": "string"}, encoding="utf-8")
    if len(counts) != int(manifest.get("rows", -1)):
        raise ValueError("Packaged CIHA input row count does not match its manifest")
    if int(counts["n"].sum()) != int(manifest.get("count_total", -1)):
        raise ValueError("Packaged CIHA input count total does not match its manifest")
    cluster_ids = sorted(counts["cnes"].dropna().astype(str).unique().tolist())
    expected_cluster_ids = [f"H{i:06d}" for i in range(1, len(cluster_ids) + 1)]
    if cluster_ids != expected_cluster_ids or len(cluster_ids) != int(manifest.get("study_cluster_count", -1)):
        raise ValueError("Study-cluster labels must be the complete H000001... sequence declared in the manifest")

    # Compute from counts alone. Frozen outputs are loaded only after this call.
    from src.ciha_engine import DEFAULT_BOOTSTRAP_REPS, DEFAULT_SEED, analyze_counts

    analysis = analyze_counts(counts)
    summary = analysis.summary.reset_index(drop=True)
    if len(summary) != EXPECTED_BRANCH_ROWS:
        raise RuntimeError(f"Expected {EXPECTED_BRANCH_ROWS} frozen branch-year rows; computed {len(summary)}")
    reportable = summary["bootstrap_interval_status"].eq("published_all_repetitions_valid")
    reportable_count = int(reportable.sum())
    if not summary.loc[reportable, "bootstrap_valid_repetitions"].eq(DEFAULT_BOOTSTRAP_REPS).all():
        raise RuntimeError("A reportable bootstrap interval does not contain the requested number of valid draws")
    if DEFAULT_BOOTSTRAP_REPS != 2000 or DEFAULT_SEED != 20261024:
        raise RuntimeError("Frozen CIHA bootstrap defaults differ from 2,000 repetitions and seed 20261024")

    # Reference comparison is deliberately downstream of all estimates.
    reference_check = _compare_reference(summary, reference_path)
    branch_rows_invariant = len(summary) == EXPECTED_BRANCH_ROWS
    reportable_count_invariant = reportable_count == EXPECTED_REPORTABLE_INTERVALS
    primary_blank_invariant = True
    for year in (2019, 2024):
        primary = summary.loc[summary["branch"].eq("main_k80_clinical") & summary["year"].eq(year)]
        if len(primary) != 1:
            primary_blank_invariant = False
            continue
        row = primary.iloc[0]
        values = (row["rate_p"], row["rate_s"], row["delta_p_minus_s"], row["ci95_lower"], row["ci95_upper"])
        primary_blank_invariant &= row["gate_status"] == "fail" and all(_is_blank(value) for value in values)

    if not (reference_check["matched"]
            and branch_rows_invariant
            and reportable_count_invariant
            and primary_blank_invariant):
        raise RuntimeError(
            "CIHA reproduction did not match the frozen reference. "
            "Results were not altered to force a match."
        )

    if out_root.exists() and not out_root.is_dir():
        raise NotADirectoryError(f"Output root is not a directory: {out_root}")
    ciha_out = out_root / "ciha"
    ciha_out.mkdir(parents=True, exist_ok=False)
    _write_frame(summary, ciha_out / "branch_summary.csv")
    _write_supplementary_tables(summary, ciha_out)
    _write_frame(analysis.support_diagnostics, ciha_out / "layer_support_diagnostics.csv", rename_cluster_id=True)
    return None
