# CIHA–SIH aggregate reproduction

This optional module reproduces the separate CIHA–SIH descriptive comparison
from pre-aggregated hospital-stratum counts. It belongs to a different analysis
context from the repository's TISS–SUS comparison; it adds no observations to
the TISS sample and does not change the core tables.

## Scope and data boundary

The packaged input contains 33,972 aggregate cells and 148,037 counted records
across two years, sources, hospitals, and frozen analysis categories. It has
no patient, AIH, event, or admission identifier. It is not a patient-level
dataset, and the counts must not be interpreted as unique patients.

The CIHA aggregate source snapshot used for the frozen run has SHA-256
`a13546f56014ddf665f6affa5a2764863327a306b7521f6e1c5f7eae44ffa47f`. For this
package, only the hospital-key column is relabelled: distinct original CNES
keys were sorted lexicographically across the full input and assigned
`H000001`, `H000002`, and so on. Row order, every other field, each count, and
the order of hospital clusters used by the bootstrap are preserved. The
one-to-one reverse mapping and original hospital keys are not included. These
are relabelled cluster IDs, not a guarantee of anonymity. The packaged input
SHA-256 is `dd7944ef74be35d90420b489e767c430be6957fca0aa022e5d2fb673ba605306`;
`data/ciha/input_manifest.json` records the row, count, and cluster checks.

The package reproduces the frozen aggregate analysis from that input. It does
not reproduce extraction from the original CIHA/SIH raw files: the exact raw
extractor snapshot used in the source run is not part of this package. No raw
records are distributed or read by this module. Derived data remain subject to
upstream source access and reuse terms; this package grants no additional
rights over them.

## Run

The optional CIHA module requires Python 3.12 or later because NumPy 2.5.2
requires Python 3.12 or later. The pinned versions were tested with Python
3.12.5, NumPy 2.5.2, and pandas 2.3.3. An additional compatibility run with
the bundled Python 3.12.14, NumPy 2.5.2, and pandas 3.0.1 also matched the
frozen numeric outputs exactly; this does not change the pinned dependencies.
Install the optional dependencies from the repository root:

```powershell
py -3.12 -m pip install -r requirements-ciha.txt
```

If the full repository inputs are installed, the integrated runner can build
the core package and this optional module together:

```powershell
py -3.12 scripts\reproduce.py --out out --ciha
```

To run only the CIHA module from the repository root:

```powershell
py -3.12 -c "from pathlib import Path; from src.ciha import run; run(Path('.'), Path('out'))"
```

The CIHA hook writes to `out/ciha/` and refuses to overwrite an existing
`out/ciha/` directory. Install the listed optional dependencies before using
the `--ciha` flag. The standard-library TISS core remains importable without
them.

## Frozen analysis and outputs

The calculation uses the engine in `src/ciha_engine.py`. It recomputes all
eight branches for 2019 and 2024: the main K80 clinical stratification,
no-sex and P-source sex-swap sensitivities, same-hospital-year and
same-hospital-quarter comparisons, K80.0, all indications, and the
cross-year common-hospital branch. All 16 branch-year rows are retained.

The frozen support gate requires at least 30 common hospitals, at least 30
supported hospitals, and at least 80% coverage in each source within common
hospitals. Branches that fail retain their status, reason, counts, and coverage
but have blank estimates and confidence intervals. The primary main-K80
clinical branch fails the coverage gate in both years; its numeric result
fields remain blank. The reported intervals use 2,000 hospital-cluster
bootstrap replicates with seed 20261024 and fixed common-hospital support. No
attempt is made to change the gate or seed to obtain a desired direction.

The target denominator contains counts for the two fixed cholecystectomy
procedure codes only: L is the laparoscopy-specific code and O is the general
cholecystectomy code. Sources P and S denote CIHA private-plan-source records
and SIH records. The frozen age groups are 18–39, 40–59, 60–79, and 80+;
unknown age and unsupported values do not enter age-stratified common cells
but remain in the stated target denominators. The raw published sex values 1
and 3 are kept as unlabeled categories under a same-code-across-source working
assumption. They are not converted to male/female. The P-only 1/3 swap is a
prespecified sensitivity branch. Unknown sex can enter the no-sex branch
because that branch does not stratify on sex.

The eight branches define their target and common-cell dimensions as follows:

| Branch | Target and common-cell dimensions |
| --- | --- |
| `main_k80_clinical` | K80 diagnosis; hospital × age × raw sex × K80 diagnosis group |
| `main_no_sex` | Same K80 target; hospital × age × K80 diagnosis group |
| `main_sex_swap_p` | Same K80 target with only P-source sex codes 1 and 3 swapped; hospital × age × raw sex × K80 diagnosis group |
| `same_hospital_year` | Same K80 target; hospital only, so clinical composition is not standardized |
| `same_hospital_quarter` | Same K80 target; hospital × actual discharge quarter; unknown quarter is outside common cells |
| `k800_clinical` | K80.0 target; hospital × age × raw sex |
| `all_indication_clinical` | All diagnosis groups, including unknown; hospital × age × raw sex |
| `main_crossyear_common_hospitals` | Same K80 target and cells as the main clinical branch, restricted to the intersection of the two years' main-branch common hospitals |

Within a branch's paired common cells, the source-specific rates are weighted
by the equal-source mixture of their cell distributions:

```text
w_s = 0.5 × N_Ps / N_PH + 0.5 × N_Ss / N_SH
rate_P = Σ(w_s × L_Ps / N_Ps)
rate_S = Σ(w_s × L_Ss / N_Ss)
delta = rate_P − rate_S
```

Here `N_Ps` and `N_Ss` are the source counts in cell `s`, `N_PH` and `N_SH`
are total counts in the retained paired cells, and `L` is the laparoscopy-
specific count. For each eligible branch, the bootstrap draws the entire
common-hospital universe with replacement, including hospitals with no
retained common cells; it keeps the initial common-cell support set fixed,
recomputes the mixture weights for each draw, and uses the linear 2.5th and
97.5th percentiles. An interval is published only when all 2,000 replicates
are valid.

Outputs include:

- `branch_summary.csv`: all 16 rows and every frozen status, denominator,
  support, estimate, and interval field.
- `table_s10a_gate_status.csv`: all 16 branch-year eligibility and support-gate
  statuses, reasons, hospital support counts, coverage, and bootstrap status.
- `table_s10b_estimates_and_intervals.csv`: only the five passing branch-year
  rows with reportable point estimates and intervals.
- `table_s10c_record_denominators.csv`: all 16 rows with the six source-specific
  total-eligible, common-hospital, and supported denominators; their coverage
  fractions; and the related hospital counts and gate status.
- `layer_support_diagnostics.csv`: supported cells keyed by relabelled
  `study_cluster_id`.

The frozen table `data/ciha/reference_branch_summary.csv` is read only after
all estimates have been computed. Every branch-year row is compared against
that table: status and descriptive text exactly, integer denominators exactly,
and all nonblank numeric gate, coverage, estimate, and interval fields within
absolute tolerance `1e-9`. The original input and reference hashes are listed
in `data/ciha/reference_provenance.json`.
A mismatch is reported with field-level diagnostics; the calculation is not
altered to force the frozen values.

## Interpretation

The outcome is the share of records carrying the laparoscopy-specific code
among records carrying either of two fixed cholecystectomy codes. The general
cholecystectomy comparator code does not establish an open approach. The
reported difference is a descriptive coding-composition difference between
CIHA private-plan-source records and SIH records. It is not an insurance or
treatment effect, clinical benefit, appropriateness measure, or causal
estimate. Hospital bootstrap intervals reflect hospital resampling under the
frozen support set and do not address missingness, coding error, clinical
confounding, or source-window differences.
