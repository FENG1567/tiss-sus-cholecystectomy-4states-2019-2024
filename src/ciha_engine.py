"""Exact-stratum descriptive comparison for pre-aggregated CIHA/SIH counts.

The engine accepts counts only. It does not ingest patient rows, resolve source
semantics, or make causal/treatment-effect claims. See README_ENGINE_CN.md for
the frozen branch and denominator definitions.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Optional, Sequence

import numpy as np
import pandas as pd


INPUT_COLUMNS = [
    "year",
    "source",
    "cnes",
    "age_band",
    "sex",
    "diag_group",
    "discharge_quarter",
    "procedure",
    "n",
]
SOURCES = ("P", "S")
YEARS = (2019, 2024)
AGE_BANDS = ("18-39", "40-59", "60-79", "80+")
# These values are exact raw strata. M/F are retained solely for synthetic
# backwards-compatible fixtures; real rows must use the unlabelled 1/3 codes.
SEX_CODES = ("1", "3", "M", "F")
DIAG_K80 = ("K800", "K80_other")
QUARTERS = ("1", "2", "3", "4")
HOSPITAL_MIN = 30
COVERAGE_MIN = 0.80
DEFAULT_BOOTSTRAP_REPS = 2000
DEFAULT_SEED = 20261024

BRANCHES: Mapping[str, tuple[str, tuple[str, ...], str]] = {
    "main_k80_clinical": (
        "成年人、K80主诊断、两固定操作码；性别按发布原码1/3作同值跨源分类假设；精确层为医院×年龄×性别原码×K80诊断组",
        ("age_band", "sex", "diag_group"),
        "主K80临床层（发布性别原码）",
    ),
    "main_no_sex": (
        "同主K80母集；不按性别分层；精确层为医院×年龄×K80诊断组",
        ("age_band", "diag_group"),
        "主K80去性别敏感性层",
    ),
    "main_sex_swap_p": (
        "同主K80母集；P来源仅交换性别原码1/3后按主层比较；unknown不变",
        ("age_band", "sex", "diag_group"),
        "主K80仅P来源1/3对调敏感性层",
    ),
    "same_hospital_year": (
        "主K80母集；精确层仅医院",
        (),
        "同院年粗分层（描述性，未统一临床构成）",
    ),
    "same_hospital_quarter": (
        "主K80母集；精确层为医院×实际出院季度",
        ("discharge_quarter",),
        "同院季度粗层（未统一临床构成）",
    ),
    "k800_clinical": (
        "成年人、K80.0主诊断、两固定操作码；精确层为医院×年龄×发布性别原码",
        ("age_band", "sex"),
        "K80.0补充分支",
    ),
    "all_indication_clinical": (
        "成年人、全部主诊断、两固定操作码；精确层为医院×年龄×发布性别原码",
        ("age_band", "sex"),
        "全部适应证测量/边界分支",
    ),
    "main_crossyear_common_hospitals": (
        "主K80母集；医院限2019与2024主分支共同医院集合交集；精确层为医院×年龄×发布性别原码×K80诊断组",
        ("age_band", "sex", "diag_group"),
        "两年主共同医院交集补充分支",
    ),
}


@dataclass
class AnalysisOutput:
    """Summary rows and cell-level support counts; no patient-level material."""

    summary: pd.DataFrame
    support_diagnostics: pd.DataFrame


def _normalize_input(frame: pd.DataFrame, *, allow_synthetic_mf: bool = False) -> pd.DataFrame:
    if not isinstance(frame, pd.DataFrame):
        raise TypeError("输入必须是 pandas.DataFrame 的集计长表。")
    if list(frame.columns) != INPUT_COLUMNS:
        missing = [c for c in INPUT_COLUMNS if c not in frame.columns]
        extra = [c for c in frame.columns if c not in INPUT_COLUMNS]
        raise ValueError(
            "输入列必须严格等于冻结schema且顺序一致；"
            f"缺少={missing}, 多余={extra}, 实际顺序={list(frame.columns)}"
        )

    out = frame.copy()
    year = pd.to_numeric(out["year"], errors="coerce")
    if year.isna().any() or not np.isfinite(year.to_numpy(dtype=float)).all():
        raise ValueError("year 必须是非缺失整数。")
    if ((year % 1) != 0).any():
        raise ValueError("year 必须是整数。")
    out["year"] = year.astype("int64")
    invalid_years = sorted(set(out["year"].tolist()) - set(YEARS))
    if invalid_years:
        raise ValueError(f"仅允许冻结年份 {YEARS}；发现 {invalid_years}。")

    source = out["source"].astype("string").str.strip()
    if source.isna().any() or not source.isin(SOURCES).all():
        raise ValueError("source 只能为 P 或 S，且不能缺失。")
    out["source"] = source.astype(str)

    cnes = out["cnes"].astype("string").str.strip()
    cnes = cnes.mask(cnes.isna() | cnes.eq(""), pd.NA)
    out["cnes"] = cnes

    categories = {
        "age_band": (AGE_BANDS, "unknown"),
        "diag_group": (("K800", "K80_other", "nonK80", "unknown"), "unknown"),
        "procedure": (("L", "O"), None),
    }
    for column, (allowed, missing_value) in categories.items():
        value = out[column].astype("string").str.strip()
        if missing_value is not None:
            value = value.mask(value.isna() | value.eq(""), missing_value)
        if value.isna().any() or not value.isin(allowed).all():
            observed = sorted(value.dropna().unique().tolist())
            raise ValueError(f"{column} 不符合冻结类别；允许={allowed}，发现={observed}。")
        out[column] = value.astype(str)

    sex = out["sex"].astype("string").str.strip()
    sex = sex.replace({"1.0": "1", "3.0": "3"})
    if not allow_synthetic_mf and sex.isin(("M", "F")).any():
        raise ValueError("正式输入性别只能使用未标注发布原码 1/3/unknown；M/F 仅供合成测试兼容。")
    allowed_sex_codes = SEX_CODES if allow_synthetic_mf else ("1", "3")
    accepted_sex = sex.isin((*allowed_sex_codes, "unknown"))
    sex = sex.mask(sex.isna() | sex.eq("") | ~accepted_sex, "unknown")
    out["sex"] = sex.astype(str)

    quarter_raw = out["discharge_quarter"].astype("string").str.strip()
    quarter = pd.Series("unknown", index=out.index, dtype="string")
    known = ~(quarter_raw.isna() | quarter_raw.eq("") | quarter_raw.eq("unknown"))
    if known.any():
        qnum = pd.to_numeric(quarter_raw.loc[known], errors="coerce")
        if qnum.isna().any() or ((qnum % 1) != 0).any() or not qnum.isin([1, 2, 3, 4]).all():
            raise ValueError("discharge_quarter 只能为 1–4 或 unknown。")
        quarter.loc[known] = qnum.astype(int).astype(str)
    out["discharge_quarter"] = quarter.astype(str)

    n = pd.to_numeric(out["n"], errors="coerce")
    if n.isna().any() or not np.isfinite(n.to_numpy(dtype=float)).all():
        raise ValueError("n 必须是非缺失、有限的非负整数。")
    if (n < 0).any() or ((n % 1) != 0).any():
        raise ValueError("n 必须是非负整数。")
    if (n > np.iinfo(np.int64).max).any():
        raise ValueError("n 超出 int64 可表示范围。")
    out["n"] = n.astype("int64")
    return out


def _target_for_branch(year_frame: pd.DataFrame, branch: str) -> pd.DataFrame:
    if branch in (
        "main_k80_clinical",
        "main_no_sex",
        "main_sex_swap_p",
        "same_hospital_year",
        "same_hospital_quarter",
        "main_crossyear_common_hospitals",
    ):
        return year_frame.loc[year_frame["diag_group"].isin(DIAG_K80)].copy()
    if branch == "k800_clinical":
        return year_frame.loc[year_frame["diag_group"].eq("K800")].copy()
    if branch == "all_indication_clinical":
        return year_frame.copy()
    raise KeyError(f"未知分支: {branch}")


def _support_filter(target: pd.DataFrame, dimensions: Sequence[str]) -> pd.DataFrame:
    keep = target["cnes"].notna()
    if "age_band" in dimensions:
        keep &= target["age_band"].isin(AGE_BANDS)
    if "sex" in dimensions:
        keep &= target["sex"].isin(SEX_CODES)
    if "diag_group" in dimensions:
        keep &= target["diag_group"].isin(DIAG_K80)
    if "discharge_quarter" in dimensions:
        keep &= target["discharge_quarter"].isin(QUARTERS)
    return target.loc[keep & target["n"].gt(0)].copy()


def _aggregate_support(target: pd.DataFrame, dimensions: Sequence[str], common_hospitals: set[str]) -> pd.DataFrame:
    cell_columns = ["cnes", *dimensions]
    eligible = _support_filter(target, dimensions)
    eligible = eligible.loc[eligible["cnes"].isin(common_hospitals)]
    cells: Optional[pd.DataFrame] = None
    for source in SOURCES:
        for procedure in ("L", "O"):
            part = eligible.loc[(eligible["source"].eq(source)) & (eligible["procedure"].eq(procedure))]
            grouped = (
                part.groupby(cell_columns, as_index=False, sort=False, dropna=False)["n"]
                .sum()
                .rename(columns={"n": f"{procedure}_{source}"})
            )
            cells = grouped if cells is None else cells.merge(grouped, on=cell_columns, how="outer", sort=False)

    if cells is None:
        cells = pd.DataFrame(columns=cell_columns)
    for column in ("L_P", "O_P", "L_S", "O_S"):
        if column not in cells.columns:
            cells[column] = 0
        cells[column] = cells[column].fillna(0).astype("int64")
    cells["N_P"] = cells["L_P"] + cells["O_P"]
    cells["N_S"] = cells["L_S"] + cells["O_S"]
    cells = cells.loc[cells["N_P"].gt(0) & cells["N_S"].gt(0)].copy()
    return cells.reset_index(drop=True)


def _estimate(cells: pd.DataFrame) -> tuple[float, float, float]:
    n_p = cells["N_P"].to_numpy(dtype=np.float64)
    n_s = cells["N_S"].to_numpy(dtype=np.float64)
    total_p = float(n_p.sum())
    total_s = float(n_s.sum())
    if total_p <= 0 or total_s <= 0:
        raise ValueError("共同层支持总数必须在两源均大于0。")
    weights = 0.5 * n_p / total_p + 0.5 * n_s / total_s
    p_p = cells["L_P"].to_numpy(dtype=np.float64) / n_p
    p_s = cells["L_S"].to_numpy(dtype=np.float64) / n_s
    # Convex averages are in [0, 1]; clamp only floating-point boundary drift
    # so all-positive/all-zero outcomes remain exactly 1/0 in exported results.
    rate_p = 1.0 if np.all(p_p == 1.0) else 0.0 if np.all(p_p == 0.0) else float(np.clip(np.dot(weights, p_p), 0.0, 1.0))
    rate_s = 1.0 if np.all(p_s == 1.0) else 0.0 if np.all(p_s == 0.0) else float(np.clip(np.dot(weights, p_s), 0.0, 1.0))
    return rate_p, rate_s, rate_p - rate_s


def _cluster_bootstrap(
    cells: pd.DataFrame,
    *,
    hospital_universe: set[str],
    repetitions: int,
    seed: int,
) -> tuple[float, float, int]:
    """Percentile interval from hospital resampling of the fixed support cells."""
    if repetitions < 1:
        raise ValueError("bootstrap repetitions 必须至少为1。")
    hospitals = sorted(str(hospital) for hospital in hospital_universe)
    if not hospitals:
        return float("nan"), float("nan"), 0
    hospital_index = {hospital: i for i, hospital in enumerate(hospitals)}
    row_hospital = cells["cnes"].astype(str).map(hospital_index).to_numpy(dtype=np.int64)
    p_n = cells["N_P"].to_numpy(dtype=np.float64)
    s_n = cells["N_S"].to_numpy(dtype=np.float64)
    p_l = cells["L_P"].to_numpy(dtype=np.float64)
    s_l = cells["L_S"].to_numpy(dtype=np.float64)

    rng = np.random.default_rng(seed)
    deltas: list[float] = []
    for _ in range(repetitions):
        sampled = rng.integers(0, len(hospitals), size=len(hospitals))
        multiplicity = np.bincount(sampled, minlength=len(hospitals))
        cell_multiplicity = multiplicity[row_hospital].astype(np.float64)
        active = cell_multiplicity > 0
        if not active.any():
            continue
        p_weighted_n = p_n[active] * cell_multiplicity[active]
        s_weighted_n = s_n[active] * cell_multiplicity[active]
        p_total = float(p_weighted_n.sum())
        s_total = float(s_weighted_n.sum())
        if p_total <= 0 or s_total <= 0:
            continue
        weights = 0.5 * p_weighted_n / p_total + 0.5 * s_weighted_n / s_total
        p_cell_rates = p_l[active] / p_n[active]
        s_cell_rates = s_l[active] / s_n[active]
        rate_p = 1.0 if np.all(p_cell_rates == 1.0) else 0.0 if np.all(p_cell_rates == 0.0) else float(np.clip(np.dot(weights, p_cell_rates), 0.0, 1.0))
        rate_s = 1.0 if np.all(s_cell_rates == 1.0) else 0.0 if np.all(s_cell_rates == 0.0) else float(np.clip(np.dot(weights, s_cell_rates), 0.0, 1.0))
        delta = rate_p - rate_s
        deltas.append(delta)
    if not deltas:
        return float("nan"), float("nan"), 0
    lower, upper = np.quantile(np.asarray(deltas), [0.025, 0.975], method="linear")
    return float(lower), float(upper), len(deltas)


def _hospital_sets(target: pd.DataFrame) -> tuple[set[str], set[str], set[str]]:
    positive = target.loc[target["n"].gt(0) & target["cnes"].notna()]
    p_hospitals = set(positive.loc[positive["source"].eq("P"), "cnes"].astype(str).unique())
    s_hospitals = set(positive.loc[positive["source"].eq("S"), "cnes"].astype(str).unique())
    return p_hospitals, s_hospitals, p_hospitals & s_hospitals


def _source_total(target: pd.DataFrame, source: str) -> int:
    return int(target.loc[target["source"].eq(source), "n"].sum())


def _source_hospital_count(target: pd.DataFrame, source: str) -> int:
    return int(target.loc[target["source"].eq(source) & target["n"].gt(0), "cnes"].dropna().nunique())


def _analyze_branch(
    target: pd.DataFrame,
    *,
    branch: str,
    year: int,
    dimensions: Sequence[str],
    target_definition: str,
    stratum_definition: str,
    common_hospital_override: Optional[set[str]],
    bootstrap_reps: int,
    seed: int,
) -> tuple[dict, pd.DataFrame, set[str]]:
    p_hospitals, s_hospitals, derived_common = _hospital_sets(target)
    common_hospitals = derived_common if common_hospital_override is None else set(common_hospital_override)
    in_common = target.loc[target["cnes"].isin(common_hospitals)] if common_hospitals else target.iloc[0:0]
    n_state = {src: _source_total(target, src) for src in SOURCES}
    n_common = {src: _source_total(in_common, src) for src in SOURCES}
    cells = _aggregate_support(target, dimensions, common_hospitals)
    n_support = {"P": int(cells["N_P"].sum()), "S": int(cells["N_S"].sum())}
    common_hospital_coverage = {
        src: (n_common[src] / n_state[src] if n_state[src] else float("nan")) for src in SOURCES
    }
    support_common_coverage = {
        src: (n_support[src] / n_common[src] if n_common[src] else float("nan")) for src in SOURCES
    }
    support_state_coverage = {
        src: (n_support[src] / n_state[src] if n_state[src] else float("nan")) for src in SOURCES
    }
    support_hospitals = int(cells["cnes"].nunique()) if not cells.empty else 0

    reasons = []
    if n_state["P"] == 0:
        reasons.append("no_P_target")
    if n_state["S"] == 0:
        reasons.append("no_S_target")
    if len(common_hospitals) < HOSPITAL_MIN:
        reasons.append(f"common_hospitals_below_{HOSPITAL_MIN}")
    if support_hospitals < HOSPITAL_MIN:
        reasons.append(f"supported_hospitals_below_{HOSPITAL_MIN}")
    for src in SOURCES:
        coverage = support_common_coverage[src]
        if not np.isfinite(coverage) or coverage + 1e-12 < COVERAGE_MIN:
            reasons.append(f"{src}_support_coverage_below_{COVERAGE_MIN:.0%}")

    gate_pass = not reasons
    row = {
        "branch": branch,
        "year": year,
        "target_definition": target_definition,
        "stratum_definition": stratum_definition,
        "gate_status": "pass" if gate_pass else "fail",
        "gate_reasons": ";".join(reasons),
        "state_n_p": n_state["P"],
        "state_n_s": n_state["S"],
        "state_hospitals_p": _source_hospital_count(target, "P"),
        "state_hospitals_s": _source_hospital_count(target, "S"),
        "common_hospitals_n": len(common_hospitals),
        "common_hospitals_over_state_hospitals_p": (
            len(common_hospitals) / len(p_hospitals) if p_hospitals else float("nan")
        ),
        "common_hospitals_over_state_hospitals_s": (
            len(common_hospitals) / len(s_hospitals) if s_hospitals else float("nan")
        ),
        "common_hospital_n_p": n_common["P"],
        "common_hospital_n_s": n_common["S"],
        "common_hospital_coverage_state_p": common_hospital_coverage["P"],
        "common_hospital_coverage_state_s": common_hospital_coverage["S"],
        "support_layer_n": len(cells),
        "supported_hospitals_n": support_hospitals,
        "support_n_p": n_support["P"],
        "support_n_s": n_support["S"],
        "support_coverage_common_hospital_p": support_common_coverage["P"],
        "support_coverage_common_hospital_s": support_common_coverage["S"],
        "support_coverage_state_p": support_state_coverage["P"],
        "support_coverage_state_s": support_state_coverage["S"],
        "bootstrap_repetitions_requested": bootstrap_reps,
        "bootstrap_seed": seed,
        "bootstrap_cluster_hospitals_n": len(common_hospitals),
        "bootstrap_valid_repetitions": 0,
        "bootstrap_method": "hospital_cluster_percentile",
        "bootstrap_interval_status": "not_run_support_gate_fail",
        "bootstrap_diagnostic": "",
        "rate_p": float("nan"),
        "rate_s": float("nan"),
        "delta_p_minus_s": float("nan"),
        "delta_percentage_points": float("nan"),
        "ci95_lower": float("nan"),
        "ci95_upper": float("nan"),
        "ci95_lower_percentage_points": float("nan"),
        "ci95_upper_percentage_points": float("nan"),
    }
    if gate_pass:
        rate_p, rate_s, delta = _estimate(cells)
        ci_lower, ci_upper, valid_reps = _cluster_bootstrap(
            cells,
            hospital_universe=common_hospitals,
            repetitions=bootstrap_reps,
            seed=seed,
        )
        row.update(
            {
                "rate_p": rate_p,
                "rate_s": rate_s,
                "delta_p_minus_s": delta,
                "delta_percentage_points": delta * 100.0,
                "ci95_lower": ci_lower,
                "ci95_upper": ci_upper,
                "bootstrap_valid_repetitions": valid_reps,
            }
        )
        if valid_reps == bootstrap_reps:
            row.update(
                {
                    "ci95_lower_percentage_points": ci_lower * 100.0,
                    "ci95_upper_percentage_points": ci_upper * 100.0,
                    "bootstrap_interval_status": "published_all_repetitions_valid",
                }
            )
        else:
            # Keep the point estimate and support diagnostics, but do not
            # publish a percentile interval from a selectively valid subset.
            row["ci95_lower"] = float("nan")
            row["ci95_upper"] = float("nan")
            row["bootstrap_interval_status"] = "not_published_incomplete_repetitions"
            row["bootstrap_diagnostic"] = (
                f"valid={valid_reps};requested={bootstrap_reps};inspect_support_and_resampling"
            )

    diagnostics_columns = ["cnes", "age_band", "sex", "diag_group", "discharge_quarter"]
    diag = pd.DataFrame(index=range(len(cells)))
    diag["branch"] = branch
    diag["year"] = year
    for col in diagnostics_columns:
        diag[col] = cells[col].astype(str).to_numpy() if col in cells.columns else ""
    diag["support_n_p"] = cells["N_P"].to_numpy(dtype=np.int64) if not cells.empty else pd.Series(dtype="int64")
    diag["support_n_s"] = cells["N_S"].to_numpy(dtype=np.int64) if not cells.empty else pd.Series(dtype="int64")
    diag["gate_status"] = "pass" if gate_pass else "fail"
    return row, diag, derived_common


def analyze_counts(
    frame: pd.DataFrame,
    *,
    bootstrap_reps: int = DEFAULT_BOOTSTRAP_REPS,
    seed: int = DEFAULT_SEED,
    allow_synthetic_mf: bool = False,
) -> AnalysisOutput:
    """Run all frozen branches against aggregated counts for 2019 and 2024.

    ``bootstrap_reps`` is injectable to support small unit tests. The frozen
    production default is 2,000 with seed 20261024. M/F compatibility may be
    explicitly enabled for synthetic fixtures only; the CLI never enables it.
    """
    if bootstrap_reps < 1:
        raise ValueError("bootstrap_reps 必须至少为1。")
    data = _normalize_input(frame, allow_synthetic_mf=allow_synthetic_mf)
    summaries: list[dict] = []
    diagnostics: list[pd.DataFrame] = []
    main_common_by_year: dict[int, set[str]] = {}

    for year in YEARS:
        year_frame = data.loc[data["year"].eq(year)].copy()
        for branch in (
            "main_k80_clinical",
            "main_no_sex",
            "main_sex_swap_p",
            "same_hospital_year",
            "same_hospital_quarter",
            "k800_clinical",
            "all_indication_clinical",
        ):
            target = _target_for_branch(year_frame, branch)
            if branch == "main_sex_swap_p":
                swap = {"1": "3", "3": "1"}
                p_rows = target["source"].eq("P")
                target.loc[p_rows, "sex"] = target.loc[p_rows, "sex"].replace(swap)
            definition, dimensions, stratum_label = BRANCHES[branch]
            row, diag, derived_common = _analyze_branch(
                target,
                branch=branch,
                year=year,
                dimensions=dimensions,
                target_definition=definition,
                stratum_definition=stratum_label,
                common_hospital_override=None,
                bootstrap_reps=bootstrap_reps,
                seed=seed,
            )
            summaries.append(row)
            diagnostics.append(diag)
            if branch == "main_k80_clinical":
                main_common_by_year[year] = derived_common

    cross_year_hospitals = main_common_by_year.get(YEARS[0], set()) & main_common_by_year.get(YEARS[1], set())
    branch = "main_crossyear_common_hospitals"
    definition, dimensions, stratum_label = BRANCHES[branch]
    for year in YEARS:
        year_frame = data.loc[data["year"].eq(year)].copy()
        target = _target_for_branch(year_frame, branch)
        row, diag, _ = _analyze_branch(
            target,
            branch=branch,
            year=year,
            dimensions=dimensions,
            target_definition=definition,
            stratum_definition=stratum_label,
            common_hospital_override=cross_year_hospitals,
            bootstrap_reps=bootstrap_reps,
            seed=seed,
        )
        summaries.append(row)
        diagnostics.append(diag)

    summary_frame = pd.DataFrame(summaries)
    support_frame = (
        pd.concat(diagnostics, ignore_index=True)
        if diagnostics
        else pd.DataFrame(
            columns=[
                "branch",
                "year",
                "cnes",
                "age_band",
                "sex",
                "diag_group",
                "discharge_quarter",
                "support_n_p",
                "support_n_s",
                "gate_status",
            ]
        )
    )
    return AnalysisOutput(summary=summary_frame, support_diagnostics=support_frame)


def _run_cli(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="CIHA-SIH 冻结精确分层描述比较引擎")
    parser.add_argument("--input", required=True, help="严格冻结schema的集计CSV")
    parser.add_argument("--output-dir", required=True, help="新建且必须不存在的输出目录")
    args = parser.parse_args(argv)
    input_path = Path(args.input).expanduser().resolve()
    output_path = Path(args.output_dir).expanduser().resolve()
    if not input_path.is_file():
        parser.error(f"输入文件不存在或不是文件: {input_path}")
    if output_path.exists():
        parser.error(f"为避免覆盖，输出目录必须不存在: {output_path}")

    counts = pd.read_csv(input_path, dtype={"cnes": "string", "sex": "string"})
    result = analyze_counts(counts)
    output_path.mkdir(parents=True, exist_ok=False)
    result.summary.to_csv(output_path / "branch_summary.csv", index=False, encoding="utf-8-sig")
    result.support_diagnostics.to_csv(
        output_path / "layer_support_diagnostics.csv", index=False, encoding="utf-8-sig"
    )
    print(f"完成：{output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_run_cli())
