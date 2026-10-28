# Aggregate inputs and source terms

The study period is the complete calendar years 2019 and 2024 in Amazonas (AM),
Pernambuco (PE), Rio Grande do Sul (RS), and São Paulo (SP). TISS inputs
represent source-specific administrative events from Brazil's supplementary
health information exchange. SIH/SUS inputs represent hospital
authorizations (AIHs) recorded in the Unified Health System. The comparison is
of recorded procedure-code composition and does not claim unique people,
verified procedures, or clinically confirmed approach.

Official source access pages:

- ANS TISS open-data directory: <https://dadosabertos.ans.gov.br/FTP/PDA/TISS/>.
- DATASUS SIH/SUS hospital production information: <https://datasus.saude.gov.br/acesso-a-informacao/producao-hospitalar-sih-sus/>.
- CIHA transfer portal for the optional, separate extension: <https://datasus.saude.gov.br/transferencia-de-arquivos/>.
- SIGTAP official download page for procedure code definitions: <https://wiki.datasus.gov.br/sigtap/index.php/Download>.

This repository contains derived aggregate counts only. It does not contain
source event-level or authorization-level records, record identifiers, or raw
DATASUS/ANS extracts.

The 15 CSVs directly under `core/reference/` come from the accepted
2026-10-27 supporting-data bundle. `URGENCY_DESCRIPTIVES.csv` is taken from its
reproducibility aggregate source-data directory. `core/reference/figure_panels/`
contains the 22 frozen derived plot-data tables used as independent figure
panel checks. The included `data/extensions/joint_counts_known.csv` contains
known age-pool × sex × urgency count sufficient statistics and is required by
the default core runner. Rows with unknown or unmapped joint dimensions are
not supplied or reconstructed.

Code is MIT-licensed under `LICENSE`. That code license does not grant rights
over upstream ANS, DATASUS, SIH/SUS, or other third-party data. Users remain
responsible for checking the applicable source access and reuse terms before
using underlying records. Derived aggregate files are included for transparent
reproduction of this manuscript's reported summaries; no broader data license
is asserted here.

Source units differ: TISS rows count administrative events and SIH/SUS rows
count authorizations. The two totals are not counts of unique people and must
not be summed as if they were.
