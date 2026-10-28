#!/usr/bin/env python3
"""Export compact known-dimension TISS/SUS joint counts from frozen JSONs.

The source JSONs are user-supplied inputs. This tool never copies them into the
repository and does not emit patient, event, municipality, or diagnosis keys.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


STATES = ("AM", "PE", "RS", "SP")
YEARS = ("2019", "2024")
AGE_POOLS = ("<20", "20–39", "40–59", "60–79", "80+")
SEXES = ("F", "M")
URGENCIES = ("elective", "emergency")
SOURCES = ("TISS", "SUS")
FIELDS = ("source", "uf", "year", "age_pool", "sex", "urgency", "L", "O", "B", "N", "A")
UNKNOWN_DIMENSION_VALUES = {"Unknown", "Unmapped", "unknown", "unmapped", None}

AGE_MAP = {
    "<1": "<20",
    "1-4": "<20",
    "5-9": "<20",
    "10-14": "<20",
    "15-19": "<20",
    "20-29": "20–39",
    "30-39": "20–39",
    "40-49": "40–59",
    "50-59": "40–59",
    "60-69": "60–79",
    "70-79": "60–79",
    "80+": "80+",
}
SEX_MAP = {"F": "F", "M": "M", "Feminino": "F", "Masculino": "M"}
URGENCY_MAP = {
    "elective": "elective",
    "emergency": "emergency",
    "Eletivo": "elective",
    "Urgência/Emergência": "emergency",
}

FLOW_FIELDS = (
    "flow_candidate_count",
    "flow_disposition_sum",
    "flow_difference",
    "flow_closed",
    "TISS_no_CONS_match",
    "TISS_CONS_projection_conflict",
    "TISS_CONS_structurally_invalid",
    "TISS_unqualified_target_code",
    "TISS_zero_only_target",
    "TISS_A_quantity_ambiguous",
    "TISS_strict_lap_only",
    "TISS_strict_open_only",
    "TISS_strict_both",
    "TISS_A",
    "SUS_target_quantity_ambiguous",
    "SUS_zero_only_target",
    "SUS_strict_lap_only",
    "SUS_strict_open_only",
    "SUS_strict_both",
    "SUS_A",
    "SUS_RD_main_only_strict_N",
    "SUS_retained_SP_only_union_captures",
    "SUS_RD_coded_candidates_removed_under_union_exclusions",
    "SUS_RD_only_vs_union_closure_closed",
)
FLOW_FIELDS = ("source", "uf", "year", *FLOW_FIELDS)


def safe_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a nonnegative integer")
    return value


def classify_source(data: dict[str, Any]) -> str | None:
    years = data.get("years")
    years_result = data.get("years_result")
    if isinstance(years, dict) and all(year in years for year in YEARS):
        return "TISS"
    if isinstance(years_result, dict) and all(year in years_result for year in YEARS):
        return "SUS"
    return None


def joint_cells(data: dict[str, Any], source: str, year: str) -> list[dict[str, Any]]:
    if source == "TISS":
        rows = data["years"][year]["joint_fields"]["joint_cells"]
    else:
        rows = data["years_result"][year]["joint_cells"]
    if not isinstance(rows, list):
        raise ValueError(f"{source} {data.get('uf')} {year} joint_cells is not a list")
    return rows


def normalized_dimensions(row: dict[str, Any]) -> tuple[str, str, str] | None:
    age = row.get("age")
    sex = row.get("sex")
    urgency = row.get("urgency")
    # Unknown dimension levels are intentionally omitted: their cross-products
    # cannot be reconstructed from aggregates that retain only known levels.
    if age in UNKNOWN_DIMENSION_VALUES or sex in UNKNOWN_DIMENSION_VALUES or urgency in UNKNOWN_DIMENSION_VALUES:
        return None
    if age not in AGE_MAP:
        raise ValueError(f"Unrecognized source age category: {age!r}")
    if sex not in SEX_MAP:
        raise ValueError(f"Unrecognized source sex category: {sex!r}")
    if urgency not in URGENCY_MAP:
        raise ValueError(f"Unrecognized source urgency category: {urgency!r}")
    return AGE_MAP[age], SEX_MAP[sex], URGENCY_MAP[urgency]


def collect_joint_inputs(sources_root: Path) -> dict[tuple[str, str, str, str, str, str], dict[str, int]]:
    if not sources_root.is_dir():
        raise ValueError(f"--sources-root must be a directory: {sources_root}")
    values: dict[tuple[str, str, str, str, str, str], dict[str, int]] = defaultdict(
        lambda: {"L": 0, "O": 0, "B": 0, "N": 0, "A": 0}
    )
    found: set[tuple[str, str]] = set()

    for path in sorted(sources_root.glob("*.json")):
        raw_bytes = path.read_bytes()
        try:
            data = json.loads(raw_bytes.decode("utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        source = classify_source(data)
        uf = data.get("uf")
        if source is None or uf not in STATES:
            continue
        pair = (source, uf)
        if pair in found:
            raise ValueError(f"Multiple frozen joint aggregates found for {source} {uf}")
        found.add(pair)
        if data.get("source") and str(data["source"]).upper() not in (source, f"{source} ADMINISTRATIVE AGGREGATE"):
            # The outer structural signature is authoritative; preserve a clear
            # failure if a recognized source file contradicts its own metadata.
            source_label = str(data["source"]).upper()
            if source not in source_label:
                raise ValueError(f"Source metadata conflicts with {source} structure in {path.name}")

        for year in YEARS:
            for row in joint_cells(data, source, year):
                n = safe_int(row.get("N"), "N")
                lap = safe_int(row.get("lap_only"), "lap_only")
                opn = safe_int(row.get("open_only"), "open_only")
                both = safe_int(row.get("both"), "both")
                ambiguous = safe_int(row.get("A", 0) if source == "TISS" else 0, "A")
                if n != lap + opn + both:
                    raise ValueError(f"Source joint row violates N=L+O+B for {source} {uf} {year}")
                dims = normalized_dimensions(row)
                if dims is None:
                    continue
                age_pool, sex, urgency = dims
                key = (source, uf, year, age_pool, sex, urgency)
                aggregate = values[key]
                aggregate["N"] += n
                aggregate["L"] += lap
                aggregate["O"] += opn
                aggregate["B"] += both
                aggregate["A"] += ambiguous

    expected_pairs = {(source, uf) for source in SOURCES for uf in STATES}
    missing = sorted(expected_pairs - found)
    if missing:
        raise ValueError(f"Missing frozen source aggregates for: {missing}")

    for source in SOURCES:
        for uf in STATES:
            for year in YEARS:
                for age_pool in AGE_POOLS:
                    for sex in SEXES:
                        for urgency in URGENCIES:
                            key = (source, uf, year, age_pool, sex, urgency)
                            row = values[key]
                            if row["N"] != row["L"] + row["O"] + row["B"]:
                                raise ValueError(f"Aggregated row violates N=L+O+B: {key}")
    return values


def export_joint_counts(values: dict[tuple[str, str, str, str, str, str], dict[str, int]], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        for source in SOURCES:
            for uf in STATES:
                for year in YEARS:
                    for age_pool in AGE_POOLS:
                        for sex in SEXES:
                            for urgency in URGENCIES:
                                key = (source, uf, year, age_pool, sex, urgency)
                                writer.writerow({"source": source, "uf": uf, "year": year, "age_pool": age_pool, "sex": sex, "urgency": urgency, **values[key]})


def export_package_a_inputs(package_a_json: Path, output_dir: Path, h_strata_path: Path) -> dict[str, Any]:
    data = json.loads(package_a_json.read_bytes().decode("utf-8-sig"))
    states = data["states"]
    with h_strata_path.open("r", newline="", encoding="utf-8-sig") as handle:
        h_rows = list(csv.DictReader(handle))
    frozen_h_keys = {
        (row["uf"], row["year"], row["age_pool"], row["sex"], row["urgency"])
        for row in h_rows
    }
    by_h_fields = ("uf", "year", "age_pool", "sex", "urgency", "code_family", "eligible_A_n")
    totals_fields = (
        "uf", "year", "eligible_A_total", "eligible_A_inside_H", "eligible_A_outside_H_or_unmapped",
        "lap_only_A_total", "open_only_A_total", "both_A_total",
        "lap_only_A_inside_H", "open_only_A_inside_H", "both_A_inside_H",
    )
    by_h_rows: list[dict[str, Any]] = []
    totals_rows: list[dict[str, Any]] = []
    for uf in STATES:
        state = states[uf]
        for year in YEARS:
            item = state["years"][year]["package_A_code_presence_selector"]
            all_by_family = item["eligible_A_by_code_family"]
            inside_by_family = {family: 0 for family in ("lap_only", "open_only", "both")}
            for row in item["by_H_stratum_and_code_family"]:
                family = row["code_family"]
                if family not in inside_by_family:
                    raise ValueError(f"Unexpected package A code family: {family!r}")
                n = safe_int(row["n"], "package A by-H n")
                h_key = (uf, year, row["age_pool"], row["sex"], row["urgency"])
                if h_key in frozen_h_keys:
                    by_h_rows.append({
                        "uf": uf,
                        "year": year,
                        "age_pool": row["age_pool"],
                        "sex": row["sex"],
                        "urgency": row["urgency"],
                        "code_family": family,
                        "eligible_A_n": n,
                    })
                    inside_by_family[family] += n
                else:
                    continue
            eligible_total = safe_int(item["eligible_A_total"], "eligible_A_total")
            eligible_inside = sum(inside_by_family.values())
            totals = {
                "eligible_A_total": eligible_total,
                "eligible_A_inside_H": eligible_inside,
                "eligible_A_outside_H_or_unmapped": eligible_total - eligible_inside,
            }
            if totals["eligible_A_total"] != sum(safe_int(all_by_family.get(f, 0), f"{f}_A_total") for f in inside_by_family):
                raise ValueError(f"Package A total does not equal code-family totals for {uf} {year}")
            if totals["eligible_A_outside_H_or_unmapped"] != totals["eligible_A_total"] - totals["eligible_A_inside_H"]:
                raise ValueError(f"Package A outside-H total is inconsistent for {uf} {year}")
            totals_rows.append({
                "uf": uf,
                "year": year,
                **totals,
                "lap_only_A_total": safe_int(all_by_family.get("lap_only", 0), "lap_only_A_total"),
                "open_only_A_total": safe_int(all_by_family.get("open_only", 0), "open_only_A_total"),
                "both_A_total": safe_int(all_by_family.get("both", 0), "both_A_total"),
                "lap_only_A_inside_H": inside_by_family["lap_only"],
                "open_only_A_inside_H": inside_by_family["open_only"],
                "both_A_inside_H": inside_by_family["both"],
            })

    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / "package_A_by_H.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=by_h_fields)
        writer.writeheader()
        writer.writerows(sorted(by_h_rows, key=lambda r: (r["uf"], r["year"], r["age_pool"], r["sex"], r["urgency"], r["code_family"])))
    with (output_dir / "package_A_eligible_totals_8.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=totals_fields)
        writer.writeheader()
        writer.writerows(sorted(totals_rows, key=lambda r: (r["uf"], r["year"])))
    return {
        "relative_filename": "tiss_package_a_source.json",
        "rows_package_A_by_H": len(by_h_rows),
        "rows_package_A_eligible_totals": len(totals_rows),
        "inside_H_definition": "reapplied exact H_STRATA.csv keys; both-source strict N >= 20",
    }


def export_flow_counts(flow_csv: Path, output_path: Path) -> dict[str, Any]:
    with flow_csv.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        source_fieldnames = list(reader.fieldnames or ())
        source_fields = set(source_fieldnames)
        missing = sorted(set(FLOW_FIELDS) - source_fields)
        if missing:
            raise ValueError(f"flow_counts_16.csv lacks required aggregate fields: {missing}")
        rows = list(reader)
    if len(rows) != 16:
        raise ValueError(f"Expected 16 flow rows, found {len(rows)}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    # Retain the aggregate candidate and disposition counts used by S12 while
    # dropping its long unit-description cell. This source has no row keys.
    output_fields = [field for field in source_fieldnames if field != "flow_candidate_unit"]
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=output_fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in output_fields})
    return {"relative_filename": "flow_counts_16.csv", "rows": len(rows)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources-root", required=True, type=Path, help="Directory containing the eight frozen TISS/SUS aggregate JSONs")
    parser.add_argument("--out", required=True, type=Path, help="Output path for joint_counts_known.csv")
    parser.add_argument("--package-a-json", type=Path, help="Optional aggregate TISS JSON used to export compact package-A sufficient statistics")
    parser.add_argument("--flow-counts", type=Path, help="Optional 16-row aggregate flow CSV to package for extension checks")
    parser.add_argument("--h-strata", type=Path, help="Optional H_STRATA.csv path (defaults to the package reference file adjacent to --out)")
    args = parser.parse_args()

    values = collect_joint_inputs(args.sources_root)
    export_joint_counts(values, args.out)
    exported = ["joint_counts_known.csv"]
    if args.package_a_json:
        h_strata_path = args.h_strata or args.out.parent.parent.parent / "core" / "reference" / "H_STRATA.csv"
        if not h_strata_path.exists():
            raise ValueError("--package-a-json requires H_STRATA.csv; pass --h-strata or place --out under repository/data/extensions")
        export_package_a_inputs(args.package_a_json, args.out.parent, h_strata_path)
        exported.append("package_A_by_H.csv")
        exported.append("package_A_eligible_totals_8.csv")
    if args.flow_counts:
        export_flow_counts(args.flow_counts, args.out.parent / "flow_counts_16.csv")
        exported.append("flow_counts_16.csv")
    print(f"exported: {', '.join(exported)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
