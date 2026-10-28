# TISS–SUS cholecystectomy code composition

Project ID: `TISS_SUS_CHOLECYSTECTOMY_4UF_2019_2024_STANDARDIZED_V1`.

This package reproduces the reported aggregate comparison for Amazonas (AM),
Pernambuco (PE), Rio Grande do Sul (RS), and São Paulo (SP), in 2019 and 2024.
It is limited to code composition in administrative records. TISS counts are
events; SIH/SUS counts are authorizations. They are not unique-patient counts.

## Reproduce the tables

Python 3.10 or later is required. The core uses only the Python standard
library; `requirements.txt` documents that there are no third-party Python
packages.

From the repository root on Windows:

```powershell
python scripts\reproduce.py --out out
```

On macOS or Linux:

```sh
python3 scripts/reproduce.py --out out
```

The default run requires `data/extensions/joint_counts_known.csv`. It
reselects the common-support set from all known age-pool × sex × urgency cells,
retaining a stratum only when each source has at least 20 strict records. It
then compares each selected cell and its counts with the published
`core/reference/H_STRATA.csv` before calculating estimates. Unknown or
unmapped joint dimensions are excluded from that input, not assigned to
invented cross-classifications.

Outputs are written under the selected `--out` directory:

- `core/table1_source_composition.csv`: 16 rows rebuilt from baseline, age,
  sex, and urgency aggregate counts. Percentages use each source-specific
  strict N as the denominator.
- `core/table2_standardized_results.csv`: eight reconstructed rows for the
  standardized shares, gaps, conditional scenario endpoints, and H coverage.
- `core/reselected_H_strata_with_weights.csv`: 123 strata reselected from the
  known-joint counts, with source L/O/B/N/A counts and exact plus decimal H
  weights for reconstructing the stratum-level supplement table.
- `core/reconstructed_comparisons.csv`: unrounded numeric reconstruction
  compared with both frozen state-year and measurement-scenario references at
  absolute tolerance `1e-9`.
- `extensions/`: standard-run H, A, source-flow, and secondary aggregate checks
  from `src/extensions.py`.
- `figures/`: figure files in PDF, PNG, and SVG when figures are requested.

The optional `--ciha` flag runs the separate CIHA/SIH aggregate bootstrap
reproduction and writes its results under `ciha/`. Install its extra Python
packages first with `python -m pip install -r requirements-ciha.txt`. The
default core reproduction does not install or import these optional packages.
For the combined figure and CIHA run, add both `--figures` and `--ciha` to the
command above.

`--use-supplied-H` is an explicit development fallback for running before the
known-joint table is available. It uses the accepted `H_STRATA.csv` directly
and skips independent H reselection. Because the extension module also requires
the known-joint table, a top-level run without that table must use both
`--use-supplied-H --core-only`. This skips the extension checks.

## Reproduce the figures

The local figure build was tested with R 4.3.1, Cairo PDF support, Arial, and
the pinned packages in `requirements-R.csv`. Install the listed package
versions with:

```sh
Rscript --vanilla install_R_dependencies.R
```

The runner accepts Rscript through `--rscript`, `R_SCRIPT`, or `PATH`. On
Windows, use the installed executable path, for example:

```powershell
python scripts\reproduce.py --out out --figures --rscript (Get-Command Rscript).Source
```

If Rscript is not on `PATH`, pass its installed executable path or set the
`R_SCRIPT` environment variable to that path. The example above uses the
currently available Rscript command and does not assume an installation
directory or R version.

On macOS or Linux:

```sh
python3 scripts/reproduce.py --out ./out --figures --rscript "$(command -v Rscript)"
```

The current revision script builds Figures 1–5 and S1–S5, ten figure
compositions in total, each exported in PDF, PNG, and SVG. The repository
distributes the R source, aggregate CSV inputs, and 22 panel-data reference
CSVs; the rendered image files are produced when the script is run.

To install or inspect the tested R package set, see `requirements-R.csv` and
`install_R_dependencies.R`. R 4.3.1 and the listed package versions were
tested; other R or package versions have not been tested in this package build.

## Estimands and interpretation

The strict source-specific denominator is `N = L + O + B`, where L is
laparoscopy-family only, O is comparator-family only, and B is dual-coded.
O does not clinically verify an open approach, and B does not confirm a
conversion. Qualified quantity-ambiguous TISS records (A) are outside strict
N and appear in the stated coding scenarios.

The common-support set H uses age pool × known sex × elective/emergency. Within
each state-year, each stratum's target weight is one half the sum of the
TISS-specific and SUS-specific proportions in H. Exact rational arithmetic is
used before converting results for CSV output. The calculations reconstruct
all eight standardized gaps and compare them against `STATE_YEAR_TABLE_8.csv`
and `MEASUREMENT_SCENARIOS_8.csv`.

The fixed-H scenario range reclassifies ambiguous TISS quantities and
dual-coded records using the documented endpoint formulas. The range is a
conditional coding scenario, not a confidence interval, not a causal effect,
and not a bound on all bias. The SP 2024 range includes zero (approximately
−1.57 to 10.67 percentage points); this is not a statistical uncertainty
interval. No p-values or statistical significance claims are generated.

The aggregate package does not contain raw records and does not claim a
clinical chart validation or an independent re-extraction of source data.
Unknown covariate combinations remain outside the known-joint table; full
source-specific denominators and coverage continue to come from the baseline
aggregate counts.

## Data, code license, and citation

The reproduction code is MIT-licensed; see `LICENSE`. The derived aggregate
inputs remain subject to their upstream source access and reuse terms. See
`DATA_SOURCES.md` for scope and attribution. The package does not include raw
ANS or DATASUS records and grants no additional rights over upstream data.

Authors listed in the current paper are in `CITATION.cff`. The public
repository is https://github.com/FENG1567/tiss-sus-cholecystectomy-4states-2019-2024.
See `CODE_AVAILABILITY.md` for the manuscript-ready statement and `v1.0.0`
for the versioned code snapshot.

## File and result guide

See [the file-selection and completion guide](整理与补齐说明_中文.md), [runtime instructions](docs/ENVIRONMENT.md), [input definitions](docs/INPUTS.md), and the [result-to-code map](docs/RESULTS_MAP.csv).
