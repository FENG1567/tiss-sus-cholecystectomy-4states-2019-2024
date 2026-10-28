# Runtime and execution

## Core analysis

The core and extension calculations use Python's standard library. The code
requires Python 3.10 or later; it was tested with CPython 3.12.14. A separate
run with `python -S` succeeded without site packages or `PYTHONPATH`.

```sh
python scripts/reproduce.py --out out_core
```

The default run requires all committed inputs, including
`data/extensions/joint_counts_known.csv`. The explicit development fallback
for an absent joint-count table is `--use-supplied-H --core-only`; it does not
independently reselect H.

## Optional CIHA analysis

The pinned NumPy version requires **Python 3.12 or later**. A separate virtual
environment can be used without changing a system installation:

```sh
python -m venv .venv
# Activate .venv using the command appropriate for your operating system.
python -m pip install -r requirements-ciha.txt
python scripts/reproduce.py --out out_ciha --ciha
```

The original compatibility check used Python 3.12.5, NumPy 2.5.2 and pandas
2.3.3. An additional complete reproduction passed on Python 3.12.14, NumPy
2.5.2 and pandas 3.0.1, with the same numerical results. The requirements file
retains the first tested package versions.

CIHA outputs are written to a new `ciha/` subdirectory. For repeated runs use
a fresh `--out` directory; the CIHA module does not overwrite an existing one.

## Optional figures

R 4.3.1 and the versions in `requirements-R.csv` were tested. The plotting
script requires Cairo PDF capability. Install the listed package versions
with:

```sh
Rscript --vanilla install_R_dependencies.R
```

Installation from source may require the platform's R build tools and the
system libraries used by Cairo, `ragg` and `svglite`. The direct package
versions are recorded; this is not a lockfile for every transitive dependency.
The original plots use Arial. Font files are not redistributed; font
substitution on another operating system may change line wrapping and other
visual details without changing the numerical panels.

Run every packaged analysis and figure in one command after dependencies are
available:

```sh
python scripts/reproduce.py --out out_full --ciha --figures --rscript Rscript
```

If Rscript is not on PATH, pass its local executable path with `--rscript` or
set `R_SCRIPT`. Windows PowerShell users can quote a path containing spaces,
for example `--rscript "C:\Program Files\R\R-4.3.1\bin\Rscript.exe"`.
