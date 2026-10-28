# Supplementary aggregate reproduction

The extension tables support the known age/sex/urgency comparison, TISS package-code-presence sensitivity, and candidate-flow checks. They contain aggregate counts only. The normal reproduction run uses the packaged CSVs; the original aggregate JSONs are not needed at runtime.

## Packaged inputs

`data/extensions/joint_counts_known.csv` contains 320 rows: TISS and SUS × four states × 2019 and 2024 × five published age pools × F/M × elective/emergency. Its schema is `source,uf,year,age_pool,sex,urgency,L,O,B,N,A`.

The exporter pools original age bands into the five labels in `core/reference/H_STRATA.csv`, maps the source sex and urgency labels to the published labels, and sums the source `lap_only`, `open_only`, `both`, and `N` counts. TISS `A` counts are retained, including cells where `N=0`; SUS `A` is zero because the SUS joint aggregate does not define that field. Rows with an unknown or unmapped age, sex, or urgency are omitted. A missing combination within the finite known-category lattice is emitted as an explicit zero row; the exporter does not infer unknown cross-products.

`data/extensions/package_A_by_H.csv` contains positive eligible package-A counts by frozen H stratum and code family. The exporter joins each source stratum key to the exact keys in `H_STRATA.csv` before writing this file. `package_A_eligible_totals_8.csv` records each state/year total and its counts inside and outside the frozen H set. The eligible package-A selector requires all qualified target rows to have `IND_PACOTE=1` and missing quantity fields, with no other quantity state. Across the eight state/year cells this selector identifies 3,038 eligible records, of which 3,026 are in the fixed 123-stratum H set and 12 are outside or unmapped.

`data/extensions/flow_counts_16.csv` preserves the aggregate count and disposition fields from the 16 candidate-flow rows; it omits only the descriptive candidate-unit text. No individual event IDs are included. `core/reference/A_breakdown_TISS.csv` contains the separate TISS quantity-exception breakdown: 10,974 records total, 10,967 with missing quantities and 7 with malformed quantities. These A-breakdown counts are distinct from the package-code-presence selector above.

## Numeric checks

`src/extensions.py::run(repo, out)` independently selects H using `TISS N >= 20` and `SUS N >= 20`, then verifies that all 123 selected keys and the per-cell L/O/B/N/A counts match `H_STRATA.csv`. It checks the full source-cell totals against `BASELINE_COUNTS_16.csv`; the known-dimension totals cannot exceed those baselines.

For each state/year, strict fractions are recomputed with exact rational arithmetic. For H cell *i*, the fixed equal-source weight is

`w_i = 1/2 × (TISS_N_i / TISS_N_H + SUS_N_i / SUS_N_H)`.

The strict estimates are `Σ w_i × TISS_L_i/TISS_N_i` and `Σ w_i × SUS_L_i/SUS_N_i`. The resulting eight estimates and percentage-point gaps are compared with `STATE_YEAR_TABLE_8.csv` at an absolute tolerance of `1e-9`.

The package-A auxiliary estimate keeps the same H keys and weights. Within each H cell it uses `(TISS_L + package_A_lap_only) / (TISS_N + package_A_lap_only + package_A_open_only + package_A_both)`. The module recomputes the per-state/year counts and estimates from the compact stratum and eligibility tables, then compares them with `package_code_presence_aux_8.csv` at `1e-9` tolerance.

Two earlier descriptive contrasts are also recalculated from their frozen count columns. `PRIOR_URGENCY_CONTRASTS_16.csv` supplies TISS and SUS L/O/B/N counts for elective and emergency strata; the module independently calculates each source's crude `L/N` fraction, percentage, and TISS-minus-SUS gap, then compares all three values with the stored reference columns at `1e-9` tolerance. Each source/state/year/urgency count is checked against the corresponding `URGENCY_DESCRIPTIVES.csv` row. These strata have source-specific denominators and exclude unknown or unmapped urgency, so their known-category totals need not equal all-urgency totals. The contrasts are not joint age-sex standardized and are not a recomputation of a measurement scenario.

`PRIOR_RD_ONLY_SENSITIVITY_8.csv` supplies TISS primary L/O/B/N counts and the separately captured SUS RD-only L/O/B/N counts. TISS primary counts must match the current TISS rows in `BASELINE_COUNTS_16.csv`. The module calculates the crude RD-only gap from those TISS counts and SUS RD-only counts, then calculates the change against an all-record primary gap independently recomputed from the TISS and full-SUS baseline counts. The stored gap and change columns are comparison targets only. SUS RD-only uses a different capture basis, so its N is checked against its own L+O+B counts but is not forced to equal full-SUS N or SP-only union captures. This sensitivity is not the primary standardization target and is not an independent replication.

For candidate flow, the module verifies the exclusive disposition sum against each candidate count, the reported closure fields, `N=L+O+B`, and the 16 baseline rows. It also reports the SUS SP-only share as `SP-only union captures / (RD-main-only strict N + SP-only union captures)`; that denominator equals SUS strict N in the packaged rows. This is a numeric reproduction check, not a clinical-validity assessment.

The module writes `extensions/state_year_reproduction.csv`, `extensions/package_A_reproduction.csv`, `extensions/flow_validation.csv`, `extensions/urgency_reproduction.csv`, and `extensions/rd_only_reproduction.csv` under the reproduction output directory. Any row, count, semantic-flag, or numeric mismatch stops the run with an error.

## Re-exporting sufficient statistics

Python 3.10 or newer is sufficient; the exporter uses only the standard library. The eight frozen TISS/SUS joint aggregate JSONs can be re-exported with:

```text
python tools/export_sufficient_statistics.py \
  --sources-root /path/to/frozen_sources \
  --out data/extensions/joint_counts_known.csv
```

To refresh the optional package-A and candidate-flow inputs from their aggregate source files, add:

```text
  --package-a-json /path/to/tiss_package_a_source.json \
  --flow-counts /path/to/flow_counts_16.csv
```

When `--out` is under `repository/data/extensions`, the exporter finds the package's `core/reference/H_STRATA.csv` for package-A filtering. Otherwise pass its location with `--h-strata`. Input files stay at their supplied locations; only the compact CSVs are written into the repository.
