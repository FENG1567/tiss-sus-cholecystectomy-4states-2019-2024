# Inputs and units

The principal comparison uses four states (AM, PE, RS and SP) and the complete
2019 and 2024 administrative years. TISS events and SIH/SUS authorizations are
different administrative units. Counts are not linked people.

## Principal sufficient statistics

`data/extensions/joint_counts_known.csv` has 320 rows. Its keys are `source`,
`uf`, `year`, `age_pool`, `sex` and `urgency`. Each row contains nonnegative
integer `L`, `O`, `B`, `N` and `A` counts, with `N=L+O+B`.

- `L`: laparoscopic-code-family only.
- `O`: comparator-code-family only; not clinical confirmation of an open
  operative approach.
- `B`: both families recorded; not confirmation of conversion.
- `A`: qualified TISS quantity-ambiguous events outside strict N. SUS has no
  corresponding pool in this analysis; its A field is encoded as zero.

The finite known-category lattice includes explicit zeros for unobserved
known combinations. Unknown or unmapped cross-products are not inferred.
The all-record strict denominators and missing-category marginals are supplied
separately in the baseline and demographic CSVs under `core/reference/`.

The default code retains only joint strata with N at least 20 in each source,
reconstructs the equal-source weights, and compares the resulting 123 strata
with the saved reference. Coverage uses the full baseline strict N, including
records outside the known lattice or common support. Percentage-point
differences use TISS minus SUS.

`package_A_by_H.csv` contains code-family counts for the defined package-only,
missing-quantity subgroup. The auxiliary calculation uses the same H and
weights as the strict comparison. State-year total eligibility is separate
from eligibility within H. `flow_counts_16.csv` retains source-specific
candidate and disposition counts; these validate arithmetic closure rather
than redoing record linkage from raw files.

## CIHA input

`data/ciha/engine_counts_relabelled.csv` is a separate hospital-stratum count
table. It has 33,972 rows and columns `year`, `source`, `cnes`, `age_band`,
`sex`, `diag_group`, `discharge_quarter`, `procedure` and `n`. In this shared
file the column named `cnes` holds study cluster keys H000001–H000454, not
original CNES codes. Their ordering preserves the original bootstrap grouping
order; no reverse map is included. Rows with a blank cluster key retain the
missing-key category and are excluded from hospital grouping by the reproduction
engine. 
P and S are the CIHA and SIH source populations defined in the separate
analysis. Raw sex codes remain category labels. Neither these records nor
their denominators are added to the TISS principal sample. See
`CIHA_REPRODUCTION.md` for all 16 branch-year definitions and fixed bootstrap
rules.

## Metadata and provenance

`data/metadata/procedure_and_field_crosswalk.csv` describes 31 code or field
entries with official source URLs, source versions, locators and hashes.
`sigtap_2019_2024_monthly_codes.csv` records the 24 monthly study archives.
`variable_field_map.csv` describes the source fields and their analysis roles.
The upstream official documents are accessed through their source links;
their full spreadsheets and raw records are not redistributed here.

The aggregate exporter uses relative file names. Normal reproduction consumes
only committed aggregate CSVs; the external extraction JSONs are needed only
to rerun that exporter.