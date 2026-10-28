#!/usr/bin/env Rscript
# Install the tested R package versions listed in requirements-R.csv.

script_arg <- grep("^--file=", commandArgs(trailingOnly = FALSE), value = TRUE)
if (!length(script_arg)) stop("Run this installer with Rscript so its package file can be located.")
script_path <- normalizePath(sub("^--file=", "", script_arg[[1]]), mustWork = TRUE)
packages_file <- file.path(dirname(script_path), "requirements-R.csv")
if (!file.exists(packages_file)) stop("Could not locate requirements-R.csv next to this script.")

requirements <- read.csv(packages_file, stringsAsFactors = FALSE, check.names = FALSE)
requirements <- requirements[requirements$component != "R", , drop = FALSE]
if (!requireNamespace("remotes", quietly = TRUE)) {
  install.packages("remotes", repos = "https://cloud.r-project.org")
}
for (i in seq_len(nrow(requirements))) {
  package <- requirements$component[[i]]
  version <- requirements$version_tested[[i]]
  installed <- if (requireNamespace(package, quietly = TRUE)) {
    as.character(utils::packageVersion(package))
  } else {
    NA_character_
  }
  if (!identical(installed, version)) {
    message("Installing ", package, " ", version, " (current: ", installed, ")")
    remotes::install_version(
      package,
      version = version,
      repos = "https://cloud.r-project.org",
      upgrade = "never"
    )
  }
}
message("Installed package versions requested in requirements-R.csv.")
message("R 4.3.1 with Cairo and Arial was the local test environment; other runtimes are not yet verified.")
