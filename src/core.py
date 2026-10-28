"""Rebuild the accepted four-state TISS–SUS tables from aggregate inputs.

The arithmetic follows the MIT-licensed reconstruction code in the source
supporting-data bundle. This portable module additionally rebuilds Table 1,
checks both frozen Table 2 references, and can independently reselect common
support from the known age/sex/urgency count lattice.

This is aggregate reproduction. It does not re-extract raw records, validate
clinical phenotype, or infer causal effects or statistical significance.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from fractions import Fraction
from itertools import product
from pathlib import Path
from typing import Any


PROJECT_ID = "TISS_SUS_CHOLECYSTECTOMY_4UF_2019_2024_STANDARDIZED_V1"
STATE_ORDER = ("AM", "PE", "RS", "SP")
YEAR_ORDER = ("2019", "2024")
SOURCE_ORDER = ("TISS", "SUS")
AGE_POOLS = ("<20", "20–39", "40–59", "60–79", "80+")
SEX_LEVELS = ("F", "M")
URGENCY_LEVELS = ("elective", "emergency")
NUMERIC_TOLERANCE = 1e-9
EXPECTED_TOTALS = {
    "TISS_strict_N": 129_137,
    "SUS_strict_N": 190_976,
    "TISS_A_outside_N": 10_974,
}

TABLE1_FIELDS = (
    "uf",
    "year",
    "source",
    "strict_N_records",
    "qualified_quantity_ambiguous_A_records_outside_N",
    "female_records",
    "female_percent",
    "emergency_records",
    "emergency_percent",
    "age_under_20_records",
    "age_under_20_percent",
)
TABLE2_FIELDS = (
    "uf",
    "year",
    "TISS_lap_percent_standardized",
    "SUS_lap_percent_standardized",
    "standardized_gap_pp_TISS_minus_SUS",
    "standardized_measurement_scenario_gap_lower_pp",
    "standardized_measurement_scenario_gap_upper_pp",
    "TISS_H_coverage_percent_of_all_strict_N",
    "SUS_H_coverage_percent_of_all_strict_N",
    "H_strata_count",
)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: tuple[str, ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _integer(row: dict[str, str], column: str, context: str) -> int:
    value = row.get(column, "")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Expected an integer in {context}.{column}; got {value!r}") from exc
    if parsed < 0:
        raise ValueError(f"Expected a non-negative integer in {context}.{column}")
    return parsed


def _fraction(row: dict[str, str], column: str, context: str) -> Fraction:
    value = row.get(column, "")
    try:
        return Fraction(value)
    except (TypeError, ValueError, ZeroDivisionError) as exc:
        raise ValueError(f"Expected a numeric value in {context}.{column}; got {value!r}") from exc


def _float(value: Fraction | int) -> float:
    return float(value)


def _check_numeric(reference: dict[str, str], column: str, value: Fraction | int,
                   context: str, tolerance: float = NUMERIC_TOLERANCE) -> None:
    try:
        expected = float(reference[column])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"Missing or non-numeric reference {context}.{column}") from exc
    actual = float(value)
    if abs(actual - expected) > tolerance:
        raise ValueError(
            f"{context}.{column} differs from the frozen reference: "
            f"reconstructed={actual:.16g}, reference={expected:.16g}, "
            f"tolerance={tolerance:g}"
        )


def _assert_unique(rows: list[dict[str, str]], key_fields: tuple[str, ...], name: str) -> None:
    seen: set[tuple[str, ...]] = set()
    for row in rows:
        key = tuple(row[field] for field in key_fields)
        if key in seen:
            raise ValueError(f"Duplicate key in {name}: {key}")
        seen.add(key)


def _key(row: dict[str, str]) -> tuple[str, str]:
    return row["uf"], row["year"]


def _load_supplied_h(reference_h: list[dict[str, str]]) -> list[dict[str, Any]]:
    strata = []
    for row in reference_h:
        strata.append({
            "uf": row["uf"],
            "year": row["year"],
            "age_pool": row["age_pool"],
            "sex": row["sex"],
            "urgency": row["urgency"],
            "TISS_strict_N": _integer(row, "TISS_strict_N", "H_STRATA"),
            "TISS_L": _integer(row, "TISS_L", "H_STRATA"),
            "TISS_O": _integer(row, "TISS_O", "H_STRATA"),
            "TISS_B": _integer(row, "TISS_B", "H_STRATA"),
            "TISS_A_outside_N": _integer(row, "TISS_A_outside_N", "H_STRATA"),
            "SUS_strict_N": _integer(row, "SUS_strict_N", "H_STRATA"),
            "SUS_L": _integer(row, "SUS_L", "H_STRATA"),
            "SUS_O": _integer(row, "SUS_O", "H_STRATA"),
            "SUS_B": _integer(row, "SUS_B", "H_STRATA"),
            "SUS_A_outside_N": _integer(row, "SUS_A_outside_N", "H_STRATA"),
        })
    return strata


def _reselect_h(joint_path: Path, reference_h: list[dict[str, str]],
                expected_cells: set[tuple[str, str]]) -> list[dict[str, Any]]:
    joint = _read_csv(joint_path)
    required = ("source", "uf", "year", "age_pool", "sex", "urgency", "L", "O", "B", "N", "A")
    if not joint:
        raise ValueError("joint_counts_known.csv is empty")
    missing_columns = [name for name in required if name not in joint[0]]
    if missing_columns:
        raise ValueError(f"joint_counts_known.csv is missing columns: {missing_columns}")
    _assert_unique(
        joint,
        ("source", "uf", "year", "age_pool", "sex", "urgency"),
        "joint_counts_known.csv",
    )

    expected_keys = {
        (source, uf, year, age, sex, urgency)
        for uf, year in expected_cells
        for source, age, sex, urgency in product(
            SOURCE_ORDER, AGE_POOLS, SEX_LEVELS, URGENCY_LEVELS
        )
    }
    actual_keys = {
        (row["source"], row["uf"], row["year"], row["age_pool"], row["sex"], row["urgency"])
        for row in joint
    }
    if actual_keys != expected_keys:
        missing = sorted(expected_keys - actual_keys)[:5]
        extra = sorted(actual_keys - expected_keys)[:5]
        raise ValueError(
            "joint_counts_known.csv must cover the complete known-dimension lattice "
            f"with explicit zeros; missing={missing}, unexpected={extra}"
        )

    values: dict[tuple[str, str, str, str, str], dict[str, dict[str, int]]] = {}
    for row in joint:
        source = row["source"]
        if source not in SOURCE_ORDER:
            raise ValueError(f"Unexpected source label in joint_counts_known.csv: {source!r}")
        uf, year = row["uf"], row["year"]
        if (uf, year) not in expected_cells:
            raise ValueError(f"Unexpected state-year in joint_counts_known.csv: {(uf, year)}")
        if row["age_pool"] not in AGE_POOLS:
            raise ValueError(f"Unexpected age_pool label: {row['age_pool']!r}")
        if row["sex"] not in SEX_LEVELS:
            raise ValueError(f"Unexpected known sex label: {row['sex']!r}")
        if row["urgency"] not in URGENCY_LEVELS:
            raise ValueError(f"Unexpected known urgency label: {row['urgency']!r}")
        counts = {name: _integer(row, name, "joint_counts_known.csv") for name in ("L", "O", "B", "N", "A")}
        if counts["N"] != counts["L"] + counts["O"] + counts["B"]:
            raise ValueError(f"joint_counts_known.csv violates N=L+O+B for {(source, uf, year, row['age_pool'], row['sex'], row['urgency'])}")
        if source == "SUS" and counts["A"] != 0:
            raise ValueError("SUS A must be encoded as 0; this table has no TISS-style quantity-ambiguous pool")
        group_key = (uf, year, row["age_pool"], row["sex"], row["urgency"])
        values.setdefault(group_key, {})[source] = counts

    retained: list[dict[str, Any]] = []
    for uf, year in sorted(expected_cells, key=lambda item: (STATE_ORDER.index(item[0]), YEAR_ORDER.index(item[1]))):
        for age, sex, urgency in product(AGE_POOLS, SEX_LEVELS, URGENCY_LEVELS):
            group_key = (uf, year, age, sex, urgency)
            tiss = values[group_key]["TISS"]
            sus = values[group_key]["SUS"]
            if tiss["N"] >= 20 and sus["N"] >= 20:
                retained.append({
                    "uf": uf,
                    "year": year,
                    "age_pool": age,
                    "sex": sex,
                    "urgency": urgency,
                    "TISS_strict_N": tiss["N"],
                    "TISS_L": tiss["L"],
                    "TISS_O": tiss["O"],
                    "TISS_B": tiss["B"],
                    "TISS_A_outside_N": tiss["A"],
                    "SUS_strict_N": sus["N"],
                    "SUS_L": sus["L"],
                    "SUS_O": sus["O"],
                    "SUS_B": sus["B"],
                    "SUS_A_outside_N": sus["A"],
                })

    selected_by_key = {tuple(row[field] for field in ("uf", "year", "age_pool", "sex", "urgency")): row for row in retained}
    reference_by_key = {
        tuple(row[field] for field in ("uf", "year", "age_pool", "sex", "urgency")): row
        for row in reference_h
    }
    if set(selected_by_key) != set(reference_by_key):
        missing = sorted(set(reference_by_key) - set(selected_by_key))[:5]
        extra = sorted(set(selected_by_key) - set(reference_by_key))[:5]
        raise ValueError(f"Reselected H membership differs from published H; missing={missing}, extra={extra}")
    for key, selected in selected_by_key.items():
        frozen = reference_by_key[key]
        for column in (
            "TISS_strict_N", "TISS_L", "TISS_O", "TISS_B", "TISS_A_outside_N",
            "SUS_strict_N", "SUS_L", "SUS_O", "SUS_B", "SUS_A_outside_N",
        ):
            expected = _integer(frozen, column, "H_STRATA")
            if selected[column] != expected:
                raise ValueError(
                    f"Reselected H count differs from H_STRATA for {key}.{column}: "
                    f"{selected[column]} != {expected}"
                )
    return retained


def _build_table1(baseline: list[dict[str, str]], age: list[dict[str, str]],
                  sex: list[dict[str, str]], urgency: list[dict[str, str]]) -> list[dict[str, Any]]:
    _assert_unique(baseline, ("source", "uf", "year"), "BASELINE_COUNTS_16.csv")
    expected_keys = {
        (source, uf, year)
        for source in SOURCE_ORDER
        for uf in STATE_ORDER
        for year in YEAR_ORDER
    }
    baseline_by_key = {(row["source"], row["uf"], row["year"]): row for row in baseline}
    if len(baseline) != 16 or set(baseline_by_key) != expected_keys:
        raise ValueError("BASELINE_COUNTS_16.csv must contain exactly the 16 expected source-state-year cells")
    baseline_n = {
        key: _integer(row, "strict_N_records", "BASELINE_COUNTS_16.csv")
        for key, row in baseline_by_key.items()
    }

    age_base = {"<1", "1-4", "5-9", "10-14", "15-19", "20-29", "30-39",
                "40-49", "50-59", "60-69", "70-79", "80+"}
    allowed_categories = {
        "AGE_ORIGINAL_BAND_DESCRIPTIVES.csv": {
            "TISS": age_base | {"Unknown"},
            "SUS": age_base | {"Unmapped"},
        },
        "SEX_DESCRIPTIVES.csv": {
            "TISS": {"F", "M", "unknown"},
            "SUS": {"F", "M"},
        },
        "URGENCY_DESCRIPTIVES.csv": {
            "TISS": {"elective", "emergency", "unknown"},
            "SUS": {"elective", "emergency", "unmapped"},
        },
    }
    expected_dimensions = {
        "AGE_ORIGINAL_BAND_DESCRIPTIVES.csv": "original_age_band",
        "SEX_DESCRIPTIVES.csv": "sex_group",
        "URGENCY_DESCRIPTIVES.csv": "urgency_group",
    }

    def counts_by_category(rows: list[dict[str, str]], file_name: str) -> dict[tuple[str, str, str], dict[str, int]]:
        output: dict[tuple[str, str, str], dict[str, int]] = defaultdict(dict)
        for row in rows:
            key = (row["source"], row["uf"], row["year"])
            if key not in expected_keys:
                raise ValueError(f"Unexpected source-state-year cell in {file_name}: {key}")
            if row.get("dimension") != expected_dimensions[file_name]:
                raise ValueError(
                    f"Unexpected dimension in {file_name} for {key}: {row.get('dimension')!r}"
                )
            category = row["category"]
            if category not in allowed_categories[file_name][row["source"]]:
                raise ValueError(f"Unexpected category in {file_name} for {key}: {category!r}")
            if category in output[key]:
                raise ValueError(f"Duplicate category in {file_name}: {key + (category,)}")
            output[key][category] = _integer(row, "N_strict_records", file_name)
        if set(output) != expected_keys:
            missing = sorted(expected_keys - set(output))
            extra = sorted(set(output) - expected_keys)
            raise ValueError(
                f"{file_name} must contain every baseline source-state-year cell; "
                f"missing={missing}, unexpected={extra}"
            )
        for key, categories in output.items():
            total = sum(categories.values())
            if total != baseline_n[key]:
                raise ValueError(
                    f"{file_name} category counts do not partition strict N for {key}: "
                    f"categories={total}, baseline={baseline_n[key]}"
                )
        return output

    age_counts = counts_by_category(age, "AGE_ORIGINAL_BAND_DESCRIPTIVES.csv")
    sex_counts = counts_by_category(sex, "SEX_DESCRIPTIVES.csv")
    urgency_counts = counts_by_category(urgency, "URGENCY_DESCRIPTIVES.csv")
    age_under_20 = {"<1", "1-4", "5-9", "10-14", "15-19"}
    results: list[dict[str, Any]] = []
    for row in baseline:
        source, uf, year = row["source"], row["uf"], row["year"]
        key = (source, uf, year)
        n = _integer(row, "strict_N_records", "BASELINE_COUNTS_16.csv")
        female_n = sex_counts.get(key, {}).get("F", 0)
        emergency_n = urgency_counts.get(key, {}).get("emergency", 0)
        under20_n = sum(age_counts.get(key, {}).get(category, 0) for category in age_under_20)
        for label, value in (("female", female_n), ("emergency", emergency_n), ("age_under_20", under20_n)):
            if value > n:
                raise ValueError(f"{label} count exceeds strict N for {key}")
        ambiguous: int | str = (
            _integer(row, "qualified_quantity_ambiguous_A_records_outside_N", "BASELINE_COUNTS_16.csv")
            if source == "TISS" else "NA"
        )
        results.append({
            "uf": uf,
            "year": year,
            "source": source,
            "strict_N_records": n,
            "qualified_quantity_ambiguous_A_records_outside_N": ambiguous,
            "female_records": female_n,
            "female_percent": _float(Fraction(100 * female_n, n)),
            "emergency_records": emergency_n,
            "emergency_percent": _float(Fraction(100 * emergency_n, n)),
            "age_under_20_records": under20_n,
            "age_under_20_percent": _float(Fraction(100 * under20_n, n)),
        })
    return results


def _reconstruct(baseline: list[dict[str, str]], strata: list[dict[str, Any]],
                 expected_state: list[dict[str, str]], expected_scenarios: list[dict[str, str]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    _assert_unique(baseline, ("source", "uf", "year"), "BASELINE_COUNTS_16.csv")
    _assert_unique(expected_state, ("uf", "year"), "STATE_YEAR_TABLE_8.csv")
    _assert_unique(expected_scenarios, ("uf", "year"), "MEASUREMENT_SCENARIOS_8.csv")
    baseline_by_key = {(row["uf"], row["year"], row["source"]): row for row in baseline}
    state_by_key = {_key(row): row for row in expected_state}
    scenario_by_key = {_key(row): row for row in expected_scenarios}
    expected_cells = set(state_by_key)
    if set(scenario_by_key) != expected_cells:
        raise ValueError("STATE_YEAR_TABLE_8 and MEASUREMENT_SCENARIOS_8 state-year rows differ")

    _require(len(baseline) == 16, f"Expected 16 baseline rows; found {len(baseline)}")
    _require(len(expected_state) == 8, f"Expected 8 state-year rows; found {len(expected_state)}")
    _require(all(row.get("project_id") == PROJECT_ID for row in expected_state), "Unexpected project_id in state-year reference")
    _require(expected_cells == {(uf, year) for uf in STATE_ORDER for year in YEAR_ORDER}, "State-year reference does not match the four-state 2019/2024 design")

    # Check source-specific baseline partitions and project totals before estimation.
    totals = {"TISS_strict_N": 0, "SUS_strict_N": 0, "TISS_A_outside_N": 0}
    for row in baseline:
        source = row["source"]
        if source not in SOURCE_ORDER:
            raise ValueError(f"Unexpected source label in baseline: {source!r}")
        l_count = _integer(row, "lap_only_L_records", "BASELINE_COUNTS_16.csv")
        o_count = _integer(row, "open_only_O_records", "BASELINE_COUNTS_16.csv")
        b_count = _integer(row, "dual_coded_B_records", "BASELINE_COUNTS_16.csv")
        n_count = _integer(row, "strict_N_records", "BASELINE_COUNTS_16.csv")
        if n_count != l_count + o_count + b_count:
            raise ValueError(f"Baseline violates N=L+O+B for {(source, row['uf'], row['year'])}")
        totals[f"{source}_strict_N"] += n_count
        if source == "TISS":
            ambiguous = _integer(row, "qualified_quantity_ambiguous_A_records_outside_N", "BASELINE_COUNTS_16.csv")
            totals["TISS_A_outside_N"] += ambiguous
    if totals != EXPECTED_TOTALS:
        raise ValueError(f"Aggregate totals differ from the accepted project totals: {totals}")

    strata_by_cell: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    _assert_unique(strata, ("uf", "year", "age_pool", "sex", "urgency"), "selected H strata")
    for row in strata:
        key = (row["uf"], row["year"])
        if key not in expected_cells:
            raise ValueError(f"Unexpected selected H cell: {key}")
        for source in SOURCE_ORDER:
            n = row[f"{source}_strict_N"]
            l_count, o_count, b_count = (row[f"{source}_{column}"] for column in ("L", "O", "B"))
            if n < 20:
                raise ValueError(f"Selected H stratum has {source} N < 20: {key, row['age_pool'], row['sex'], row['urgency']}")
            if n != l_count + o_count + b_count:
                raise ValueError(f"H stratum violates {source} N=L+O+B: {key, row['age_pool'], row['sex'], row['urgency']}")
        strata_by_cell[key].append(row)

    table2: list[dict[str, Any]] = []
    detailed: list[dict[str, Any]] = []
    weighted_h: list[dict[str, Any]] = []
    for uf, year in sorted(expected_cells, key=lambda item: (STATE_ORDER.index(item[0]), YEAR_ORDER.index(item[1]))):
        hs = strata_by_cell[(uf, year)]
        if not hs:
            raise ValueError(f"No H strata for {(uf, year)}")
        total_tiss_h = sum(row["TISS_strict_N"] for row in hs)
        total_sus_h = sum(row["SUS_strict_N"] for row in hs)
        weights = [
            (Fraction(row["TISS_strict_N"], total_tiss_h) + Fraction(row["SUS_strict_N"], total_sus_h)) / 2
            for row in hs
        ]
        if sum(weights, Fraction(0)) != 1:
            raise ValueError(f"Exact equal-source weights do not sum to one for {(uf, year)}")
        for row, weight in zip(hs, weights):
            weighted_h.append({
                "uf": uf,
                "year": year,
                "age_pool": row["age_pool"],
                "sex": row["sex"],
                "urgency": row["urgency"],
                **{
                    f"{source}_{field}": row[f"{source}_{field}"]
                    for source in SOURCE_ORDER
                    for field in ("strict_N", "L", "O", "B", "A_outside_N")
                },
                "equal_source_weight_fraction": str(weight),
                "equal_source_weight_0to1": float(weight),
            })

        sums = {name: Fraction(0) for name in (
            "tiss", "sus", "tiss_lower", "tiss_upper", "sus_lower", "sus_upper"
        )}
        for row, weight in zip(hs, weights):
            tiss_n = row["TISS_strict_N"]
            sus_n = row["SUS_strict_N"]
            tiss_l, tiss_b, tiss_a = row["TISS_L"], row["TISS_B"], row["TISS_A_outside_N"]
            sus_l, sus_b = row["SUS_L"], row["SUS_B"]
            sums["tiss"] += weight * Fraction(tiss_l, tiss_n)
            sums["sus"] += weight * Fraction(sus_l, sus_n)
            sums["tiss_lower"] += weight * Fraction(tiss_l, tiss_n + tiss_a)
            sums["tiss_upper"] += weight * Fraction(tiss_l + tiss_b + tiss_a, tiss_n + tiss_a)
            sums["sus_lower"] += weight * Fraction(sus_l, sus_n)
            sums["sus_upper"] += weight * Fraction(sus_l + sus_b, sus_n)

        tiss_base = baseline_by_key[(uf, year, "TISS")]
        sus_base = baseline_by_key[(uf, year, "SUS")]
        tiss_all_n = _integer(tiss_base, "strict_N_records", "BASELINE_COUNTS_16.csv")
        sus_all_n = _integer(sus_base, "strict_N_records", "BASELINE_COUNTS_16.csv")
        tiss_all_l = _integer(tiss_base, "lap_only_L_records", "BASELINE_COUNTS_16.csv")
        sus_all_l = _integer(sus_base, "lap_only_L_records", "BASELINE_COUNTS_16.csv")
        tiss_coverage = Fraction(total_tiss_h, tiss_all_n) * 100
        sus_coverage = Fraction(total_sus_h, sus_all_n) * 100
        tiss_all_fraction = Fraction(tiss_all_l, tiss_all_n)
        sus_all_fraction = Fraction(sus_all_l, sus_all_n)
        tiss_same_h_fraction = Fraction(sum(row["TISS_L"] for row in hs), total_tiss_h)
        sus_same_h_fraction = Fraction(sum(row["SUS_L"] for row in hs), total_sus_h)
        crude_gap = (Fraction(tiss_all_l, tiss_all_n) - Fraction(sus_all_l, sus_all_n)) * 100
        same_h_gap = (tiss_same_h_fraction - sus_same_h_fraction) * 100
        lower_gap = (sums["tiss_lower"] - sums["sus_upper"]) * 100
        upper_gap = (sums["tiss_upper"] - sums["sus_lower"]) * 100
        metrics: dict[str, Fraction | int] = {
            "H_strata_count": len(hs),
            "TISS_N_in_H_records": total_tiss_h,
            "SUS_N_in_H_records": total_sus_h,
            "TISS_lap_percent_standardized": sums["tiss"] * 100,
            "SUS_lap_percent_standardized": sums["sus"] * 100,
            "standardized_gap_pp_TISS_minus_SUS": (sums["tiss"] - sums["sus"]) * 100,
            "standardized_measurement_scenario_gap_lower_pp": lower_gap,
            "standardized_measurement_scenario_gap_upper_pp": upper_gap,
            "TISS_H_coverage_percent_of_all_strict_N": tiss_coverage,
            "SUS_H_coverage_percent_of_all_strict_N": sus_coverage,
            "TISS_H_coverage_fraction_of_all_strict_N_0to1": Fraction(total_tiss_h, tiss_all_n),
            "SUS_H_coverage_fraction_of_all_strict_N_0to1": Fraction(total_sus_h, sus_all_n),
            "TISS_lap_fraction_all_records_0to1": tiss_all_fraction,
            "TISS_lap_percent_all_records": tiss_all_fraction * 100,
            "SUS_lap_fraction_all_records_0to1": sus_all_fraction,
            "SUS_lap_percent_all_records": sus_all_fraction * 100,
            "TISS_lap_fraction_same_H_0to1": tiss_same_h_fraction,
            "TISS_lap_percent_same_H": tiss_same_h_fraction * 100,
            "SUS_lap_fraction_same_H_0to1": sus_same_h_fraction,
            "SUS_lap_percent_same_H": sus_same_h_fraction * 100,
            "all_records_crude_gap_pp_TISS_minus_SUS": crude_gap,
            "same_H_crude_gap_pp_TISS_minus_SUS": same_h_gap,
            "TISS_lap_fraction_standardized_0to1": sums["tiss"],
            "SUS_lap_fraction_standardized_0to1": sums["sus"],
            "TISS_scenario_lower_fraction": sums["tiss_lower"],
            "TISS_scenario_upper_fraction": sums["tiss_upper"],
            "SUS_scenario_lower_fraction": sums["sus_lower"],
            "SUS_scenario_upper_fraction": sums["sus_upper"],
            "TISS_A_in_H_records": sum(row["TISS_A_outside_N"] for row in hs),
            "TISS_A_total_outside_N": _integer(tiss_base, "qualified_quantity_ambiguous_A_records_outside_N", "BASELINE_COUNTS_16.csv"),
        }

        state_reference = state_by_key[(uf, year)]
        compare_state_columns = (
            "H_strata_count", "TISS_N_in_H_records", "SUS_N_in_H_records",
            "TISS_lap_percent_standardized", "SUS_lap_percent_standardized",
            "TISS_lap_fraction_standardized_0to1", "SUS_lap_fraction_standardized_0to1",
            "TISS_lap_fraction_all_records_0to1", "TISS_lap_percent_all_records",
            "SUS_lap_fraction_all_records_0to1", "SUS_lap_percent_all_records",
            "TISS_lap_fraction_same_H_0to1", "TISS_lap_percent_same_H",
            "SUS_lap_fraction_same_H_0to1", "SUS_lap_percent_same_H",
            "standardized_gap_pp_TISS_minus_SUS",
            "standardized_measurement_scenario_gap_lower_pp",
            "standardized_measurement_scenario_gap_upper_pp",
            "TISS_H_coverage_percent_of_all_strict_N",
            "SUS_H_coverage_percent_of_all_strict_N",
            "TISS_H_coverage_fraction_of_all_strict_N_0to1",
            "SUS_H_coverage_fraction_of_all_strict_N_0to1",
            "all_records_crude_gap_pp_TISS_minus_SUS",
            "same_H_crude_gap_pp_TISS_minus_SUS",
            "TISS_A_in_H_records", "TISS_A_total_outside_N",
        )
        for column in compare_state_columns:
            reference_column = {
                "TISS_A_total_outside_N": "TISS_A_qualified_quantity_ambiguous_records_outside_N",
            }.get(column, column)
            _check_numeric(state_reference, reference_column, metrics[column], f"STATE_YEAR_TABLE_8[{uf},{year}]")

        for source in SOURCE_ORDER:
            source_base = baseline_by_key[(uf, year, source)]
            reference_fields = {
                "lap_only_L_records": f"{source}_L_records",
                "open_only_O_records": f"{source}_O_records",
                "dual_coded_B_records": f"{source}_B_dual_coded_records",
                "strict_N_records": f"{source}_N_strict_records",
            }
            for source_column, reference_column in reference_fields.items():
                _check_numeric(
                    state_reference,
                    reference_column,
                    _integer(source_base, source_column, "BASELINE_COUNTS_16.csv"),
                    f"STATE_YEAR_TABLE_8[{uf},{year}]",
                )
            if source == "TISS":
                _check_numeric(
                    state_reference,
                    "TISS_A_qualified_quantity_ambiguous_records_outside_N",
                    _integer(source_base, "qualified_quantity_ambiguous_A_records_outside_N", "BASELINE_COUNTS_16.csv"),
                    f"STATE_YEAR_TABLE_8[{uf},{year}]",
                )
        high_coverage = (Fraction(total_tiss_h, tiss_all_n) >= Fraction(4, 5) and
                         Fraction(total_sus_h, sus_all_n) >= Fraction(4, 5))
        if state_reference["high_coverage_common_support_both_sources_ge_80pct"].strip().lower() != str(high_coverage).lower():
            raise ValueError(f"Common-support coverage gate differs from the frozen reference for {(uf, year)}")

        scenario_reference = scenario_by_key[(uf, year)]
        scenario_checks = {
            "TISS_A_total_outside_N": metrics["TISS_A_total_outside_N"],
            "TISS_A_within_H": metrics["TISS_A_in_H_records"],
            "H_strata_count": metrics["H_strata_count"],
            "TISS_N_in_H": metrics["TISS_N_in_H_records"],
            "SUS_N_in_H": metrics["SUS_N_in_H_records"],
            "TISS_scenario_lower_fraction_0to1": metrics["TISS_scenario_lower_fraction"],
            "TISS_scenario_lower_percent": metrics["TISS_scenario_lower_fraction"] * 100,
            "TISS_scenario_upper_fraction_0to1": metrics["TISS_scenario_upper_fraction"],
            "TISS_scenario_upper_percent": metrics["TISS_scenario_upper_fraction"] * 100,
            "SUS_scenario_lower_fraction_0to1": metrics["SUS_scenario_lower_fraction"],
            "SUS_scenario_lower_percent": metrics["SUS_scenario_lower_fraction"] * 100,
            "SUS_scenario_upper_fraction_0to1": metrics["SUS_scenario_upper_fraction"],
            "SUS_scenario_upper_percent": metrics["SUS_scenario_upper_fraction"] * 100,
            "gap_lower_pp_TISS_minus_SUS": metrics["standardized_measurement_scenario_gap_lower_pp"],
            "gap_upper_pp_TISS_minus_SUS": metrics["standardized_measurement_scenario_gap_upper_pp"],
            "strict_standardized_gap_pp": metrics["standardized_gap_pp_TISS_minus_SUS"],
        }
        for column, value in scenario_checks.items():
            _check_numeric(scenario_reference, column, value, f"MEASUREMENT_SCENARIOS_8[{uf},{year}]")
        if scenario_reference["scenario_is_confidence_interval"].strip().lower() != "false":
            raise ValueError(f"The frozen scenario is incorrectly labeled as a confidence interval for {(uf, year)}")
        if scenario_reference["scenario_is_bound_on_all_bias"].strip().lower() != "false":
            raise ValueError(f"The frozen scenario is incorrectly labeled as a bound on all bias for {(uf, year)}")
        classification = "all_positive" if lower_gap > 0 else (
            "all_negative" if upper_gap < 0 else "crosses_zero"
        )
        if scenario_reference["scenario_classification"] != classification:
            raise ValueError(f"Scenario classification differs from the frozen reference for {(uf, year)}")
        if state_reference["measurement_scenario_status"] != classification:
            raise ValueError(f"State-year scenario status differs from the frozen reference for {(uf, year)}")

        numeric_row = {name: _float(value) if isinstance(value, Fraction) else value for name, value in metrics.items()}
        detailed.append({"uf": uf, "year": year, **numeric_row})
        table2.append({
            "uf": uf,
            "year": year,
            "TISS_lap_percent_standardized": _float(metrics["TISS_lap_percent_standardized"]),
            "SUS_lap_percent_standardized": _float(metrics["SUS_lap_percent_standardized"]),
            "standardized_gap_pp_TISS_minus_SUS": _float(metrics["standardized_gap_pp_TISS_minus_SUS"]),
            "standardized_measurement_scenario_gap_lower_pp": _float(metrics["standardized_measurement_scenario_gap_lower_pp"]),
            "standardized_measurement_scenario_gap_upper_pp": _float(metrics["standardized_measurement_scenario_gap_upper_pp"]),
            "TISS_H_coverage_percent_of_all_strict_N": _float(metrics["TISS_H_coverage_percent_of_all_strict_N"]),
            "SUS_H_coverage_percent_of_all_strict_N": _float(metrics["SUS_H_coverage_percent_of_all_strict_N"]),
            "H_strata_count": metrics["H_strata_count"],
        })

    return table2, detailed, weighted_h


def run(repo_root: Path, out_root: Path, use_supplied_h: bool = False) -> dict[str, Any]:
    """Run the core aggregate reconstruction and write the four comparison tables."""
    repo_root = repo_root.resolve()
    out_root = out_root.resolve()
    data = repo_root / "core" / "reference"
    baseline = _read_csv(data / "BASELINE_COUNTS_16.csv")
    reference_h = _read_csv(data / "H_STRATA.csv")
    expected_state = _read_csv(data / "STATE_YEAR_TABLE_8.csv")
    expected_scenarios = _read_csv(data / "MEASUREMENT_SCENARIOS_8.csv")
    expected_cells = {(row["uf"], row["year"]) for row in expected_state}
    joint_path = repo_root / "data" / "extensions" / "joint_counts_known.csv"
    if joint_path.is_file():
        strata = _reselect_h(joint_path, reference_h, expected_cells)
        independent_h_reselection = True
    elif use_supplied_h:
        strata = _load_supplied_h(reference_h)
        independent_h_reselection = False
    else:
        raise FileNotFoundError(
            "The default core reproduction requires data/extensions/joint_counts_known.csv "
            "to independently reselect H. For a temporary aggregate-only development run, "
            "pass --use-supplied-H; the top-level runner also requires the extension module, "
            "so pair this with --core-only."
        )

    table1 = _build_table1(
        baseline,
        _read_csv(data / "AGE_ORIGINAL_BAND_DESCRIPTIVES.csv"),
        _read_csv(data / "SEX_DESCRIPTIVES.csv"),
        _read_csv(data / "URGENCY_DESCRIPTIVES.csv"),
    )
    table2, comparisons, weighted_h = _reconstruct(baseline, strata, expected_state, expected_scenarios)
    if len(table1) != 16 or len(table2) != 8 or len(strata) != 123:
        raise ValueError("Reconstructed table/H row counts differ from the accepted contract")

    core_out = out_root / "core"
    _write_csv(core_out / "table1_source_composition.csv", table1, TABLE1_FIELDS)
    _write_csv(core_out / "table2_standardized_results.csv", table2, TABLE2_FIELDS)
    detail_fields = ("uf", "year", *[name for name in comparisons[0] if name not in ("uf", "year")])
    _write_csv(core_out / "reconstructed_comparisons.csv", comparisons, detail_fields)
    weighted_h_fields = (
        "uf", "year", "age_pool", "sex", "urgency",
        "TISS_strict_N", "TISS_L", "TISS_O", "TISS_B", "TISS_A_outside_N",
        "SUS_strict_N", "SUS_L", "SUS_O", "SUS_B", "SUS_A_outside_N",
        "equal_source_weight_fraction", "equal_source_weight_0to1",
    )
    _write_csv(core_out / "reselected_H_strata_with_weights.csv", weighted_h, weighted_h_fields)

    return {"independent_h_reselection": independent_h_reselection}
