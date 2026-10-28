"""Reproduce secondary aggregate checks from packaged sufficient statistics."""

from __future__ import annotations

import csv
from collections import defaultdict
from fractions import Fraction
from pathlib import Path
from typing import Any


TOLERANCE = 1e-9
AGE_POOLS = ("<20", "20–39", "40–59", "60–79", "80+")
SEXES = ("F", "M")
URGENCIES = ("elective", "emergency")
SOURCES = ("TISS", "SUS")
STATES = ("AM", "PE", "RS", "SP")
YEARS = ("2019", "2024")
FAMILIES = ("lap_only", "open_only", "both")
COUNT_FIELDS = ("L", "O", "B", "N", "A")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, fieldnames: tuple[str, ...], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _integer(row: dict[str, str], field: str) -> int:
    value = row.get(field, "")
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Expected integer in {field}: {value!r}") from exc
    if result < 0:
        raise ValueError(f"Expected nonnegative integer in {field}: {value!r}")
    return result


def _fraction(value: str) -> Fraction:
    return Fraction(value)


def _float_close(left: Fraction | float, right: str | float | int, tolerance: float = TOLERANCE) -> bool:
    left_float = float(left)
    right_float = float(right)
    return abs(left_float - right_float) <= tolerance


def _add_error(errors: list[str], message: str) -> None:
    errors.append(message)


def _index_known(rows: list[dict[str, str]]) -> dict[tuple[str, str, str, str, str, str], dict[str, int]]:
    indexed: dict[tuple[str, str, str, str, str, str], dict[str, int]] = {}
    for row in rows:
        key = (row["source"], row["uf"], row["year"], row["age_pool"], row["sex"], row["urgency"])
        if key in indexed:
            raise ValueError(f"Duplicate known-count row for {key}")
        if row["source"] not in SOURCES or row["uf"] not in STATES or row["year"] not in YEARS:
            raise ValueError(f"Unexpected known-count lattice key: {key}")
        if row["age_pool"] not in AGE_POOLS or row["sex"] not in SEXES or row["urgency"] not in URGENCIES:
            raise ValueError(f"Unexpected known-count category: {key}")
        counts = {field: _integer(row, field) for field in COUNT_FIELDS}
        if counts["N"] != counts["L"] + counts["O"] + counts["B"]:
            raise ValueError(f"N does not equal L+O+B for {key}")
        indexed[key] = counts
    expected = {
        (source, uf, year, age, sex, urgency)
        for source in SOURCES
        for uf in STATES
        for year in YEARS
        for age in AGE_POOLS
        for sex in SEXES
        for urgency in URGENCIES
    }
    if set(indexed) != expected:
        missing = len(expected - set(indexed))
        extra = len(set(indexed) - expected)
        raise ValueError(f"Known-count lattice must contain 320 unique rows (missing={missing}, extra={extra})")
    return indexed


def _stratum_key(row: dict[str, str]) -> tuple[str, str, str, str, str]:
    return row["uf"], row["year"], row["age_pool"], row["sex"], row["urgency"]


def _source_cell(indexed: dict[tuple[str, str, str, str, str, str], dict[str, int]], source: str, key: tuple[str, str, str, str, str]) -> dict[str, int]:
    uf, year, age_pool, sex, urgency = key
    return indexed[(source, uf, year, age_pool, sex, urgency)]


def _canonical_flow_dispositions(row: dict[str, str], source: str) -> int:
    if source == "TISS":
        fields = (
            "TISS_no_CONS_match",
            "TISS_CONS_projection_conflict",
            "TISS_CONS_structurally_invalid",
            "TISS_unqualified_target_code",
            "TISS_zero_only_target",
            "TISS_A",
            "TISS_strict_lap_only",
            "TISS_strict_open_only",
            "TISS_strict_both",
        )
    else:
        fields = (
            "SUS_zero_only_target",
            "SUS_A",
            "SUS_strict_lap_only",
            "SUS_strict_open_only",
            "SUS_strict_both",
        )
    return sum(_integer(row, field) for field in fields)


def run(repo: Path, out: Path) -> None:
    """Run independent numeric checks for packaged secondary aggregate data.

    `repo` is the reproduction package root; `out` is the output root used by
    the main reproduction runner. Raises on any mismatch; returns None on success.
    """
    repo = Path(repo)
    out = Path(out)
    data_dir = repo / "data" / "extensions"
    reference_dir = repo / "core" / "reference"
    output_dir = out / "extensions"
    output_dir.mkdir(parents=True, exist_ok=True)

    known_path = data_dir / "joint_counts_known.csv"
    known_rows = _read_csv(known_path)
    known = _index_known(known_rows)
    expected_row_count = len(SOURCES) * len(STATES) * len(YEARS) * len(AGE_POOLS) * len(SEXES) * len(URGENCIES)

    h_reference = _read_csv(reference_dir / "H_STRATA.csv")
    h_map = {_stratum_key(row): row for row in h_reference}
    if len(h_map) != len(h_reference):
        raise ValueError("H_STRATA.csv contains duplicate stratum keys")
    selected_h = {
        key
        for key in {
            (uf, year, age, sex, urgency)
            for uf in STATES
            for year in YEARS
            for age in AGE_POOLS
            for sex in SEXES
            for urgency in URGENCIES
        }
        if _source_cell(known, "TISS", key)["N"] >= 20 and _source_cell(known, "SUS", key)["N"] >= 20
    }
    errors: list[str] = []
    h_keys_match = selected_h == set(h_map)
    if not h_keys_match:
        _add_error(errors, f"H reselection key mismatch: selected={len(selected_h)} reference={len(h_map)}")
    if len(selected_h) != 123 or len(h_map) != 123:
        _add_error(errors, f"The frozen H guard is 123 strata; selected={len(selected_h)}, reference={len(h_map)}")

    h_numeric_matches = True
    for key in sorted(selected_h):
        reference = h_map.get(key)
        if reference is None:
            h_numeric_matches = False
            continue
        tiss = _source_cell(known, "TISS", key)
        sus = _source_cell(known, "SUS", key)
        expected_counts = {
            "TISS_strict_N": tiss["N"], "TISS_L": tiss["L"], "TISS_O": tiss["O"], "TISS_B": tiss["B"], "TISS_A_outside_N": tiss["A"],
            "SUS_strict_N": sus["N"], "SUS_L": sus["L"], "SUS_O": sus["O"], "SUS_B": sus["B"], "SUS_A_outside_N": sus["A"],
        }
        for field, observed in expected_counts.items():
            if _integer(reference, field) != observed:
                h_numeric_matches = False
                _add_error(errors, f"H count mismatch for {key} {field}: reference={reference[field]} known={observed}")
    if not h_numeric_matches and h_keys_match:
        _add_error(errors, "At least one reselected H cell does not match H_STRATA.csv counts")

    baseline_rows = _read_csv(reference_dir / "BASELINE_COUNTS_16.csv")
    baseline_map = {(row["source"], row["uf"], row["year"]): row for row in baseline_rows}

    state_rows = _read_csv(reference_dir / "STATE_YEAR_TABLE_8.csv")
    state_map = {(row["uf"], row["year"]): row for row in state_rows}
    state_output_rows: list[dict[str, Any]] = []
    state_estimates_match = True
    baseline_reconciliation = True
    for uf in STATES:
        for year in YEARS:
            total_counts = {
                source: {field: 0 for field in COUNT_FIELDS}
                for source in SOURCES
            }
            h_strata = [key for key in selected_h if key[:2] == (uf, year)]
            h_counts = {
                source: {field: 0 for field in COUNT_FIELDS}
                for source in SOURCES
            }
            for age in AGE_POOLS:
                for sex in SEXES:
                    for urgency in URGENCIES:
                        key = (uf, year, age, sex, urgency)
                        for source in SOURCES:
                            cell = _source_cell(known, source, key)
                            for field in COUNT_FIELDS:
                                total_counts[source][field] += cell[field]
                            if key in selected_h:
                                for field in COUNT_FIELDS:
                                    h_counts[source][field] += cell[field]

            source_baseline_fields = {"N": "strict_N_records", "L": "lap_only_L_records", "O": "open_only_O_records", "B": "dual_coded_B_records", "A": "qualified_quantity_ambiguous_A_records_outside_N"}
            for source in SOURCES:
                baseline = baseline_map[(source, uf, year)]
                for field, ref_field in source_baseline_fields.items():
                    all_value = _integer(baseline, ref_field)
                    known_value = total_counts[source][field]
                    if known_value > all_value:
                        baseline_reconciliation = False
                        _add_error(errors, f"Known {source} {field} exceeds baseline for {uf} {year}")
                if h_counts[source]["N"] > _integer(baseline, source_baseline_fields["N"]):
                    baseline_reconciliation = False
                    _add_error(errors, f"H {source} N exceeds all-strata N for {uf} {year}")

            tiss_h_n = h_counts["TISS"]["N"]
            sus_h_n = h_counts["SUS"]["N"]
            weights: dict[tuple[str, str, str, str, str], Fraction] = {}
            for key in h_strata:
                tiss_n = _source_cell(known, "TISS", key)["N"]
                sus_n = _source_cell(known, "SUS", key)["N"]
                weights[key] = Fraction(1, 2) * (Fraction(tiss_n, tiss_h_n) + Fraction(sus_n, sus_h_n))
                if _fraction(h_map[key]["equal_source_weight_fraction"]) != weights[key]:
                    state_estimates_match = False
                    _add_error(errors, f"Equal-source weight differs from H_STRATA.csv for {key}")
            weight_sum = sum(weights.values(), Fraction(0, 1))
            if weight_sum != 1:
                state_estimates_match = False
                _add_error(errors, f"Equal-source weights do not sum to one for {uf} {year}")

            tiss_fraction = sum(
                weights[key] * Fraction(_source_cell(known, "TISS", key)["L"], _source_cell(known, "TISS", key)["N"])
                for key in h_strata
            )
            sus_fraction = sum(
                weights[key] * Fraction(_source_cell(known, "SUS", key)["L"], _source_cell(known, "SUS", key)["N"])
                for key in h_strata
            )
            gap_pp = 100 * (tiss_fraction - sus_fraction)
            reference = state_map[(uf, year)]
            estimate_fields = (
                ("TISS_lap_fraction_standardized_0to1", tiss_fraction),
                ("SUS_lap_fraction_standardized_0to1", sus_fraction),
                ("standardized_gap_pp_TISS_minus_SUS", gap_pp),
            )
            for field, calculated in estimate_fields:
                if not _float_close(calculated, reference[field]):
                    state_estimates_match = False
                    _add_error(errors, f"Independent strict estimate differs from STATE_YEAR_TABLE_8 for {uf} {year} {field}")
            if len(h_strata) != _integer(reference, "H_strata_count"):
                state_estimates_match = False
                _add_error(errors, f"H stratum count differs from STATE_YEAR_TABLE_8 for {uf} {year}")
            for source, count_field, reference_field in (
                ("TISS", "N", "TISS_N_in_H_records"),
                ("SUS", "N", "SUS_N_in_H_records"),
                ("TISS", "A", "TISS_A_in_H_records"),
                ("SUS", "A", "SUS_A_in_H_records"),
            ):
                if h_counts[source][count_field] != _integer(reference, reference_field):
                    state_estimates_match = False
                    _add_error(errors, f"H {source} {count_field} differs from STATE_YEAR_TABLE_8 for {uf} {year}")

            state_output_rows.append({
                "uf": uf,
                "year": year,
                "H_strata_count": len(h_strata),
                "TISS_N_in_H": tiss_h_n,
                "TISS_A_in_H": h_counts["TISS"]["A"],
                "SUS_N_in_H": sus_h_n,
                "SUS_A_in_H": h_counts["SUS"]["A"],
                "equal_source_weight_sum": float(weight_sum),
                "TISS_standardized_strict_fraction": float(tiss_fraction),
                "SUS_standardized_strict_fraction": float(sus_fraction),
                "strict_gap_pp_TISS_minus_SUS": float(gap_pp),
            })

    _write_csv(
        output_dir / "state_year_reproduction.csv",
        ("uf", "year", "H_strata_count", "TISS_N_in_H", "TISS_A_in_H", "SUS_N_in_H", "SUS_A_in_H", "equal_source_weight_sum", "TISS_standardized_strict_fraction", "SUS_standardized_strict_fraction", "strict_gap_pp_TISS_minus_SUS"),
        state_output_rows,
    )

    a_breakdown_rows = _read_csv(reference_dir / "A_breakdown_TISS.csv")
    a_breakdown_n = sum(_integer(row, "n") for row in a_breakdown_rows)
    missing_a = sum(_integer(row, "n") for row in a_breakdown_rows if row["exclusive_quantity_exception"] == "missing_any")
    malformed_a = sum(_integer(row, "n") for row in a_breakdown_rows if row["exclusive_quantity_exception"] == "malformed_any")
    a_breakdown_matches = (a_breakdown_n, missing_a, malformed_a) == (10974, 10967, 7)
    if not a_breakdown_matches:
        _add_error(errors, f"TISS A breakdown guard mismatch: total={a_breakdown_n}, missing={missing_a}, malformed={malformed_a}")

    package_a_rows = _read_csv(data_dir / "package_A_by_H.csv")
    package_a_totals = _read_csv(data_dir / "package_A_eligible_totals_8.csv")
    package_a_by_h: dict[tuple[str, str, str, str, str], dict[str, int]] = defaultdict(lambda: {family: 0 for family in FAMILIES})
    h_set = set(h_map)
    package_a_schema_ok = True
    for row in package_a_rows:
        key = _stratum_key(row)
        family = row["code_family"]
        if key not in h_set or family not in FAMILIES:
            package_a_schema_ok = False
            _add_error(errors, f"Package A by-H row is outside H or has unknown family: {key} {family}")
            continue
        package_a_by_h[key][family] += _integer(row, "eligible_A_n")

    package_a_total_map = {(row["uf"], row["year"]): row for row in package_a_totals}
    package_a_reference = _read_csv(reference_dir / "package_code_presence_aux_8.csv")
    package_a_reference_map = {(row["uf"], row["year"]): row for row in package_a_reference}
    package_a_output_rows: list[dict[str, Any]] = []
    package_a_matches = len(package_a_total_map) == 8 and len(package_a_reference_map) == 8
    eligible_all_sum = eligible_inside_sum = 0
    for uf in STATES:
        for year in YEARS:
            key = (uf, year)
            totals = package_a_total_map.get(key)
            reference = package_a_reference_map.get(key)
            if totals is None or reference is None:
                package_a_matches = False
                _add_error(errors, f"Missing package A eligibility summary for {uf} {year}")
                continue
            total = _integer(totals, "eligible_A_total")
            inside = _integer(totals, "eligible_A_inside_H")
            outside = _integer(totals, "eligible_A_outside_H_or_unmapped")
            family_total = {family: _integer(totals, f"{family}_A_total") for family in FAMILIES}
            family_inside = {family: _integer(totals, f"{family}_A_inside_H") for family in FAMILIES}
            h_family_sum = {family: 0 for family in FAMILIES}
            for stratum in h_set:
                if stratum[:2] == key:
                    for family in FAMILIES:
                        h_family_sum[family] += package_a_by_h[stratum][family]
            if total != sum(family_total.values()) or inside != sum(family_inside.values()) or outside != total - inside:
                package_a_matches = False
                _add_error(errors, f"Package A family totals do not close for {uf} {year}")
            if h_family_sum != family_inside:
                package_a_matches = False
                _add_error(errors, f"Package A by-H rows do not match eligibility totals for {uf} {year}")
            eligible_all_sum += total
            eligible_inside_sum += inside
            for field, calculated in (
                ("eligible_A_total", total),
                ("eligible_A_inside_H", inside),
                ("eligible_A_outside_H_or_unmapped", outside),
                ("lap_only_all_eligible_A", family_total["lap_only"]),
                ("open_only_all_eligible_A", family_total["open_only"]),
                ("both_all_eligible_A", family_total["both"]),
                ("lap_only_inside_H", family_inside["lap_only"]),
                ("open_only_inside_H", family_inside["open_only"]),
                ("both_inside_H", family_inside["both"]),
            ):
                if _integer(reference, field) != calculated:
                    package_a_matches = False
                    _add_error(errors, f"Package A count differs from reference for {uf} {year} {field}")

            aux_numerator = Fraction(0, 1)
            strict_tiss_independent = Fraction(0, 1)
            strict_sus_independent = Fraction(0, 1)
            for stratum in sorted(s for s in h_set if s[:2] == key):
                w = _fraction(h_map[stratum]["equal_source_weight_fraction"])
                tiss = _source_cell(known, "TISS", stratum)
                sus = _source_cell(known, "SUS", stratum)
                family_counts = package_a_by_h[stratum]
                a_total = sum(family_counts.values())
                aux_numerator += w * Fraction(tiss["L"] + family_counts["lap_only"], tiss["N"] + a_total)
                strict_tiss_independent += w * Fraction(tiss["L"], tiss["N"])
                strict_sus_independent += w * Fraction(sus["L"], sus["N"])
            # Per-stratum package-A ratios are weighted using the frozen H
            # equal-source composition; each denominator includes that
            # stratum's eligible package-A rows.
            aux_tiss = aux_numerator
            if not _float_close(strict_tiss_independent, reference["TISS_strict_standardized_fraction"]):
                package_a_matches = False
                _add_error(errors, f"Independent strict TISS fraction differs in package A comparison for {uf} {year}")
            if not _float_close(strict_sus_independent, reference["SUS_strict_standardized_fraction"]):
                package_a_matches = False
                _add_error(errors, f"Independent strict SUS fraction differs in package A comparison for {uf} {year}")
            aux_gap_pp = 100 * (aux_tiss - strict_sus_independent)
            if not _float_close(aux_tiss, reference["TISS_package_A_auxiliary_standardized_fraction"]):
                package_a_matches = False
                _add_error(errors, f"Recomputed package-A auxiliary TISS fraction differs for {uf} {year}")
            if not _float_close(100 * (strict_tiss_independent - strict_sus_independent), reference["strict_TISS_minus_SUS_gap_pp"]):
                package_a_matches = False
                _add_error(errors, f"Strict gap differs in package A comparison for {uf} {year}")
            if not _float_close(aux_gap_pp, reference["auxiliary_TISS_minus_SUS_gap_pp"]):
                package_a_matches = False
                _add_error(errors, f"Auxiliary gap differs for {uf} {year}")
            package_a_output_rows.append({
                "uf": uf,
                "year": year,
                "eligible_A_total": total,
                "eligible_A_inside_H": inside,
                "eligible_A_outside_H_or_unmapped": outside,
                "TISS_strict_standardized_fraction": float(strict_tiss_independent),
                "TISS_package_A_auxiliary_standardized_fraction": float(aux_tiss),
                "SUS_strict_standardized_fraction": float(strict_sus_independent),
                "strict_gap_pp_TISS_minus_SUS": float(100 * (strict_tiss_independent - strict_sus_independent)),
                "auxiliary_gap_pp_TISS_minus_SUS": float(aux_gap_pp),
            })
    if eligible_all_sum != 3038 or eligible_inside_sum != 3026:
        package_a_matches = False
        _add_error(errors, f"Package A total guard mismatch: total={eligible_all_sum}, inside_H={eligible_inside_sum}")
    _write_csv(
        output_dir / "package_A_reproduction.csv",
        ("uf", "year", "eligible_A_total", "eligible_A_inside_H", "eligible_A_outside_H_or_unmapped", "TISS_strict_standardized_fraction", "TISS_package_A_auxiliary_standardized_fraction", "SUS_strict_standardized_fraction", "strict_gap_pp_TISS_minus_SUS", "auxiliary_gap_pp_TISS_minus_SUS"),
        package_a_output_rows,
    )

    flow_rows = _read_csv(data_dir / "flow_counts_16.csv")
    flow_map = {(row["source"], row["uf"], row["year"]): row for row in flow_rows}
    flow_matches = len(flow_map) == 16
    flow_output_rows: list[dict[str, Any]] = []
    for uf in STATES:
        for year in YEARS:
            state_year_h = [key for key in selected_h if key[:2] == (uf, year)]
            h_totals = {
                source: sum(_source_cell(known, source, key)["N"] for key in state_year_h)
                for source in SOURCES
            }
            for source in SOURCES:
                row = flow_map.get((source, uf, year))
                baseline = baseline_map[(source, uf, year)]
                if row is None:
                    flow_matches = False
                    _add_error(errors, f"Missing flow summary for {source} {uf} {year}")
                    continue
                candidate = _integer(row, "flow_candidate_count")
                reported_dispositions = _integer(row, "flow_disposition_sum")
                recomputed_dispositions = _canonical_flow_dispositions(row, source)
                difference = _integer(row, "flow_difference")
                closed = row["flow_closed"].strip().lower() == "true"
                if recomputed_dispositions != candidate or reported_dispositions != candidate or difference != 0 or not closed:
                    flow_matches = False
                    _add_error(errors, f"Candidate-flow closure failed for {source} {uf} {year}")
                if source == "TISS":
                    if _integer(row, "TISS_A") != _integer(row, "TISS_A_quantity_ambiguous"):
                        flow_matches = False
                        _add_error(errors, f"TISS A flow counts differ for {uf} {year}")
                    strict_n = sum(_integer(row, f"TISS_strict_{suffix}") for suffix in ("lap_only", "open_only", "both"))
                    baseline_n = _integer(baseline, "strict_N_records")
                    sp_capture = 0
                    rd_main_only = 0
                    sp_fraction: float | str = ""
                else:
                    if _integer(row, "SUS_A") != _integer(row, "SUS_target_quantity_ambiguous"):
                        flow_matches = False
                        _add_error(errors, f"SUS A flow counts differ for {uf} {year}")
                    strict_n = sum(_integer(row, f"SUS_strict_{suffix}") for suffix in ("lap_only", "open_only", "both"))
                    baseline_n = _integer(baseline, "strict_N_records")
                    sp_capture = _integer(row, "SUS_retained_SP_only_union_captures")
                    rd_main_only = _integer(row, "SUS_RD_main_only_strict_N")
                    union_n = sp_capture + rd_main_only
                    if union_n != strict_n:
                        flow_matches = False
                        _add_error(errors, f"RD-only plus SP-only union captures do not equal SUS strict N for {uf} {year}")
                    sp_fraction = (sp_capture / union_n) if union_n else 0.0
                if strict_n != baseline_n:
                    flow_matches = False
                    _add_error(errors, f"Flow L/O/B strict N does not match baseline for {source} {uf} {year}")
                if h_totals[source] > strict_n:
                    flow_matches = False
                    _add_error(errors, f"H N exceeds strict N for {source} {uf} {year}")
                flow_output_rows.append({
                    "source": source,
                    "uf": uf,
                    "year": year,
                    "flow_candidate_count": candidate,
                    "recomputed_exclusive_disposition_sum": recomputed_dispositions,
                    "reported_disposition_sum": reported_dispositions,
                    "flow_difference": difference,
                    "flow_closed": closed,
                    "strict_N_from_LOB": strict_n,
                    "baseline_strict_N": baseline_n,
                    "H_strict_N": h_totals[source],
                    "SUS_RD_main_only_strict_N": rd_main_only if source == "SUS" else "",
                    "SUS_SP_only_union_captures": sp_capture if source == "SUS" else "",
                    "SUS_SP_only_fraction_of_strict_N": sp_fraction,
                })
    _write_csv(
        output_dir / "flow_validation.csv",
        ("source", "uf", "year", "flow_candidate_count", "recomputed_exclusive_disposition_sum", "reported_disposition_sum", "flow_difference", "flow_closed", "strict_N_from_LOB", "baseline_strict_N", "H_strict_N", "SUS_RD_main_only_strict_N", "SUS_SP_only_union_captures", "SUS_SP_only_fraction_of_strict_N"),
        flow_output_rows,
    )

    # Recalculate the prior urgency-stratified contrasts from their published
    # aggregate counts. Fractions and gaps in the input CSV are comparison
    # targets only; they are never used as calculation inputs.
    urgency_reference_rows = _read_csv(reference_dir / "PRIOR_URGENCY_CONTRASTS_16.csv")
    expected_urgency_keys = {
        (uf, year, urgency)
        for uf in STATES
        for year in YEARS
        for urgency in URGENCIES
    }
    urgency_descriptive_rows = _read_csv(reference_dir / "URGENCY_DESCRIPTIVES.csv")
    urgency_descriptive_map: dict[tuple[str, str, str, str], dict[str, str]] = {}
    urgency_descriptives_match = True
    for row in urgency_descriptive_rows:
        if row.get("dimension") != "urgency_group" or row.get("category") not in URGENCIES:
            continue
        descriptive_key = (row["source"], row["uf"], row["year"], row["category"])
        if descriptive_key in urgency_descriptive_map:
            urgency_descriptives_match = False
            _add_error(errors, f"URGENCY_DESCRIPTIVES.csv contains duplicate urgency row for {descriptive_key}")
        urgency_descriptive_map[descriptive_key] = row
    expected_urgency_descriptive_keys = {
        (source, uf, year, urgency)
        for source in SOURCES
        for uf in STATES
        for year in YEARS
        for urgency in URGENCIES
    }
    if set(urgency_descriptive_map) != expected_urgency_descriptive_keys:
        urgency_descriptives_match = False
        _add_error(errors, f"URGENCY_DESCRIPTIVES.csv urgency key set mismatch: expected={len(expected_urgency_descriptive_keys)} observed={len(urgency_descriptive_map)}")
    urgency_keys: set[tuple[str, str, str]] = set()
    urgency_output_rows: list[dict[str, Any]] = []
    urgency_counts_valid = True
    urgency_semantics_valid = True
    urgency_reference_matches = len(urgency_reference_rows) == 16
    if len(urgency_reference_rows) != 16:
        _add_error(errors, f"PRIOR_URGENCY_CONTRASTS_16.csv must contain 16 rows; found {len(urgency_reference_rows)}")
    for row in urgency_reference_rows:
        key = (row["uf"], row["year"], row["urgency_canonical"])
        if key in urgency_keys:
            urgency_reference_matches = False
            _add_error(errors, f"Duplicate prior urgency contrast row for {key}")
        urgency_keys.add(key)
        if key not in expected_urgency_keys:
            urgency_reference_matches = False
            _add_error(errors, f"Unexpected prior urgency contrast key: {key}")

        tiss_counts = {field: _integer(row, f"TISS_{field}") for field in ("L", "O", "B", "N")}
        sus_counts = {field: _integer(row, f"SUS_{field}") for field in ("L", "O", "B", "N")}
        if tiss_counts["N"] != tiss_counts["L"] + tiss_counts["O"] + tiss_counts["B"]:
            urgency_counts_valid = False
            _add_error(errors, f"Prior urgency TISS N does not equal L+O+B for {key}")
        if sus_counts["N"] != sus_counts["L"] + sus_counts["O"] + sus_counts["B"]:
            urgency_counts_valid = False
            _add_error(errors, f"Prior urgency SUS N does not equal L+O+B for {key}")
        if tiss_counts["N"] == 0 or sus_counts["N"] == 0:
            urgency_counts_valid = False
            _add_error(errors, f"Prior urgency fractions require nonzero denominators for {key}")
            continue

        for source, counts in (("TISS", tiss_counts), ("SUS", sus_counts)):
            descriptive = urgency_descriptive_map.get((source, row["uf"], row["year"], row["urgency_canonical"]))
            if descriptive is None:
                urgency_descriptives_match = False
                _add_error(errors, f"Missing current urgency descriptive counts for {source} {key}")
                continue
            descriptive_fields = {
                "L": "L_lap_only_records",
                "O": "O_open_only_records",
                "B": "B_dual_coded_records",
                "N": "N_strict_records",
            }
            for field, descriptive_field in descriptive_fields.items():
                current_count = _integer(descriptive, descriptive_field)
                if counts[field] != current_count:
                    urgency_descriptives_match = False
                    _add_error(errors, f"Prior urgency count differs from URGENCY_DESCRIPTIVES.csv for {source} {key} {field}: prior={counts[field]} current={current_count}")

        tiss_fraction = Fraction(tiss_counts["L"], tiss_counts["N"])
        sus_fraction = Fraction(sus_counts["L"], sus_counts["N"])
        gap_pp = 100 * (tiss_fraction - sus_fraction)
        for field, calculated in (
            ("TISS_lap_fraction_0to1", tiss_fraction),
            ("TISS_lap_percent", 100 * tiss_fraction),
            ("SUS_lap_fraction_0to1", sus_fraction),
            ("SUS_lap_percent", 100 * sus_fraction),
            ("gap_pp_TISS_minus_SUS", gap_pp),
        ):
            if not _float_close(calculated, row[field]):
                urgency_reference_matches = False
                _add_error(errors, f"Recomputed prior urgency value differs for {key} {field}")

        if row.get("gap_unit", "") != "percentage points":
            urgency_semantics_valid = False
            _add_error(errors, f"Prior urgency gap unit is not percentage points for {key}")
        for field in ("joint_age_sex_standardized", "measurement_scenario_recomputed_within_stratum"):
            if row.get(field, "").strip().lower() != "false":
                urgency_semantics_valid = False
                _add_error(errors, f"Prior urgency semantic flag {field} must remain false for {key}")
        if row.get("counts_match_prior_accepted_descriptives", "").strip().lower() != "true":
            urgency_semantics_valid = False
            _add_error(errors, f"Prior urgency accepted-descriptive count flag must remain true for {key}")

        urgency_output_rows.append({
            "uf": row["uf"],
            "year": row["year"],
            "urgency_original_label": row["urgency_original_label"],
            "urgency_canonical": row["urgency_canonical"],
            **{f"TISS_{field}": tiss_counts[field] for field in ("L", "O", "B", "N")},
            "TISS_lap_fraction_0to1_recomputed": float(tiss_fraction),
            "TISS_lap_percent_recomputed": float(100 * tiss_fraction),
            **{f"SUS_{field}": sus_counts[field] for field in ("L", "O", "B", "N")},
            "SUS_lap_fraction_0to1_recomputed": float(sus_fraction),
            "SUS_lap_percent_recomputed": float(100 * sus_fraction),
            "gap_pp_TISS_minus_SUS_recomputed": float(gap_pp),
            "gap_unit": row["gap_unit"],
            "denominator_definition": row["denominator_definition"],
            "joint_age_sex_standardized": row["joint_age_sex_standardized"],
            "measurement_scenario_recomputed_within_stratum": row["measurement_scenario_recomputed_within_stratum"],
            "counts_match_prior_accepted_descriptives": row["counts_match_prior_accepted_descriptives"],
            "interpretation": row["interpretation"],
        })
    if urgency_keys != expected_urgency_keys:
        urgency_reference_matches = False
        _add_error(errors, f"Prior urgency key set mismatch: expected={len(expected_urgency_keys)} observed={len(urgency_keys)}")
    urgency_matches = urgency_reference_matches and urgency_counts_valid and urgency_semantics_valid and urgency_descriptives_match
    _write_csv(
        output_dir / "urgency_reproduction.csv",
        ("uf", "year", "urgency_original_label", "urgency_canonical", "TISS_L", "TISS_O", "TISS_B", "TISS_N", "TISS_lap_fraction_0to1_recomputed", "TISS_lap_percent_recomputed", "SUS_L", "SUS_O", "SUS_B", "SUS_N", "SUS_lap_fraction_0to1_recomputed", "SUS_lap_percent_recomputed", "gap_pp_TISS_minus_SUS_recomputed", "gap_unit", "denominator_definition", "joint_age_sex_standardized", "measurement_scenario_recomputed_within_stratum", "counts_match_prior_accepted_descriptives", "interpretation"),
        urgency_output_rows,
    )

    # The RD-only sensitivity retains the current primary TISS counts while
    # using the separately captured prior SUS RD-only counts. Its crude gap is
    # compared with an all-record baseline gap recomputed from BASELINE_COUNTS_16.
    rd_reference_rows = _read_csv(reference_dir / "PRIOR_RD_ONLY_SENSITIVITY_8.csv")
    rd_reference_map: dict[tuple[str, str], dict[str, str]] = {}
    rd_only_schema_valid = len(rd_reference_rows) == 8
    rd_only_tiss_counts_match_baseline = True
    rd_only_reference_matches = len(rd_reference_rows) == 8
    rd_only_output_rows: list[dict[str, Any]] = []
    if len(rd_reference_rows) != 8:
        _add_error(errors, f"PRIOR_RD_ONLY_SENSITIVITY_8.csv must contain 8 rows; found {len(rd_reference_rows)}")
    for row in rd_reference_rows:
        key = (row["uf"], row["year"])
        if key in rd_reference_map:
            rd_only_reference_matches = False
            _add_error(errors, f"Duplicate RD-only sensitivity row for {key}")
        rd_reference_map[key] = row
    expected_rd_keys = {(uf, year) for uf in STATES for year in YEARS}
    if set(rd_reference_map) != expected_rd_keys:
        rd_only_reference_matches = False
        _add_error(errors, f"RD-only sensitivity key set mismatch: expected={len(expected_rd_keys)} observed={len(rd_reference_map)}")

    for uf in STATES:
        for year in YEARS:
            key = (uf, year)
            row = rd_reference_map.get(key)
            if row is None:
                continue
            tiss_counts = {field: _integer(row, f"TISS_primary_{field}") for field in ("L", "O", "B", "N")}
            sus_rd_counts = {field: _integer(row, f"SUS_RD_only_{field}") for field in ("L", "O", "B", "N")}
            if tiss_counts["N"] != tiss_counts["L"] + tiss_counts["O"] + tiss_counts["B"]:
                rd_only_schema_valid = False
                _add_error(errors, f"RD-only TISS primary N does not equal L+O+B for {key}")
            if sus_rd_counts["N"] != sus_rd_counts["L"] + sus_rd_counts["O"] + sus_rd_counts["B"]:
                rd_only_schema_valid = False
                _add_error(errors, f"SUS RD-only N does not equal L+O+B for {key}")
            baseline_tiss = baseline_map[("TISS", uf, year)]
            baseline_sus = baseline_map[("SUS", uf, year)]
            baseline_fields = {
                "L": "lap_only_L_records",
                "O": "open_only_O_records",
                "B": "dual_coded_B_records",
                "N": "strict_N_records",
            }
            for field, baseline_field in baseline_fields.items():
                expected_count = _integer(baseline_tiss, baseline_field)
                if tiss_counts[field] != expected_count:
                    rd_only_tiss_counts_match_baseline = False
                    _add_error(errors, f"RD-only TISS primary count differs from BASELINE_COUNTS_16 for {key} {field}")

            if tiss_counts["N"] == 0 or sus_rd_counts["N"] == 0:
                rd_only_schema_valid = False
                _add_error(errors, f"RD-only fractions require nonzero denominators for {key}")
                continue
            tiss_fraction = Fraction(tiss_counts["L"], tiss_counts["N"])
            sus_rd_fraction = Fraction(sus_rd_counts["L"], sus_rd_counts["N"])
            rd_only_gap_pp = 100 * (tiss_fraction - sus_rd_fraction)
            baseline_tiss_fraction = Fraction(_integer(baseline_tiss, "lap_only_L_records"), _integer(baseline_tiss, "strict_N_records"))
            baseline_sus_fraction = Fraction(_integer(baseline_sus, "lap_only_L_records"), _integer(baseline_sus, "strict_N_records"))
            baseline_primary_gap_pp = 100 * (baseline_tiss_fraction - baseline_sus_fraction)
            rd_only_change_pp = rd_only_gap_pp - baseline_primary_gap_pp
            for field, calculated in (
                ("prior_all_record_primary_gap_pp", baseline_primary_gap_pp),
                ("RD_only_gap_pp_TISS_minus_SUS", rd_only_gap_pp),
                ("RD_only_change_from_prior_primary_gap_pp", rd_only_change_pp),
            ):
                if not _float_close(calculated, row[field]):
                    rd_only_reference_matches = False
                    _add_error(errors, f"Recomputed RD-only value differs for {key} {field}")

            if row.get("this_is_primary_standardization_target", "").strip().lower() != "false":
                rd_only_schema_valid = False
                _add_error(errors, f"RD-only sensitivity must remain outside the primary standardization target for {key}")
            if row.get("independent_replication", "").strip().lower() != "false":
                rd_only_schema_valid = False
                _add_error(errors, f"RD-only sensitivity must remain marked as non-independent replication for {key}")
            rd_only_output_rows.append({
                "uf": uf,
                "year": year,
                **{f"TISS_primary_{field}": tiss_counts[field] for field in ("L", "O", "B", "N")},
                "TISS_primary_lap_fraction_0to1_recomputed": float(tiss_fraction),
                **{f"SUS_RD_only_{field}": sus_rd_counts[field] for field in ("L", "O", "B", "N")},
                "SUS_RD_only_lap_fraction_0to1_recomputed": float(sus_rd_fraction),
                "baseline_primary_all_gap_pp_TISS_minus_SUS_recomputed": float(baseline_primary_gap_pp),
                "RD_only_crude_gap_pp_TISS_minus_SUS_recomputed": float(rd_only_gap_pp),
                "RD_only_change_from_baseline_primary_gap_pp_recomputed": float(rd_only_change_pp),
                "SUS_RD_capture_basis_note": "Different capture basis; SUS RD-only N is not equated to the full SUS baseline or SP-only union captures.",
                "RD_only_definition": row["RD_only_definition"],
                "this_is_primary_standardization_target": row["this_is_primary_standardization_target"],
                "independent_replication": row["independent_replication"],
                "interpretation": row["interpretation"],
            })
    rd_only_matches = rd_only_reference_matches and rd_only_tiss_counts_match_baseline and rd_only_schema_valid
    _write_csv(
        output_dir / "rd_only_reproduction.csv",
        ("uf", "year", "TISS_primary_L", "TISS_primary_O", "TISS_primary_B", "TISS_primary_N", "TISS_primary_lap_fraction_0to1_recomputed", "SUS_RD_only_L", "SUS_RD_only_O", "SUS_RD_only_B", "SUS_RD_only_N", "SUS_RD_only_lap_fraction_0to1_recomputed", "baseline_primary_all_gap_pp_TISS_minus_SUS_recomputed", "RD_only_crude_gap_pp_TISS_minus_SUS_recomputed", "RD_only_change_from_baseline_primary_gap_pp_recomputed", "SUS_RD_capture_basis_note", "RD_only_definition", "this_is_primary_standardization_target", "independent_replication", "interpretation"),
        rd_only_output_rows,
    )

    if errors:
        raise RuntimeError("; ".join(errors))
    return None
