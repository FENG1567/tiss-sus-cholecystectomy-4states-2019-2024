options(stringsAsFactors = FALSE, scipen = 999, warn = 1)
invisible(try(Sys.setlocale("LC_CTYPE", ".UTF-8"), silent = TRUE))

suppressPackageStartupMessages({
  library(ggplot2)
  library(patchwork)
  library(dplyr)
  library(tidyr)
})

if (!capabilities("cairo")) stop("R cairo graphics support is required for PDF export.")
required_packages <- c("ggplot2", "patchwork", "dplyr", "tidyr", "svglite", "ragg", "scales")
missing_packages <- required_packages[!vapply(required_packages, requireNamespace, logical(1), quietly = TRUE)]
if (length(missing_packages)) stop(paste("Missing R packages:", paste(missing_packages, collapse = ", ")))

cli_args <- commandArgs(trailingOnly = TRUE)
if (length(cli_args) != 2L) {
  stop("Usage: Rscript plot_figures.R <reference_csv_dir> <output_dir>")
}

reference_dir <- normalizePath(cli_args[[1]], winslash = "/", mustWork = TRUE)
output_dir <- cli_args[[2]]
dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)
output_dir <- normalizePath(output_dir, winslash = "/", mustWork = TRUE)
figure_dir <- file.path(output_dir, "exports")
dir.create(figure_dir, recursive = TRUE, showWarnings = FALSE)

input_files <- c(
  "STATE_YEAR_TABLE_8.csv",
  "BASELINE_COUNTS_16.csv",
  "H_STRATA.csv",
  "MEASUREMENT_SCENARIOS_8.csv",
  "PRIOR_URGENCY_CONTRASTS_16.csv",
  "PRIOR_RD_ONLY_SENSITIVITY_8.csv",
  "MONTHLY_DESCRIPTIVES_PRIOR.csv",
  "AGE_ORIGINAL_BAND_DESCRIPTIVES.csv",
  "SEX_DESCRIPTIVES.csv",
  "FEASIBILITY_GATES.csv",
  "CONDITIONAL_GEOGRAPHY_8.csv",
  "CLINICAL_K80_DESCRIPTIVES.csv",
  "A_breakdown_TISS.csv",
  "package_code_presence_aux_8.csv"
)
missing_inputs <- input_files[!file.exists(file.path(reference_dir, input_files))]
if (length(missing_inputs)) stop(paste("Missing reference CSV files:", paste(missing_inputs, collapse = ", ")))
read_evidence <- function(filename) {
  read.csv(file.path(reference_dir, filename), check.names = FALSE,
           stringsAsFactors = FALSE, fileEncoding = "UTF-8")
}

state_order <- c("AM", "PE", "RS", "SP")
year_order <- c(2019, 2024)
source_order <- c("TISS", "SUS")
state_names <- c(
  AM = "Amazonas",
  PE = "Pernambuco",
  RS = "Rio Grande do Sul",
  SP = "São Paulo"
)
cell_levels <- unlist(lapply(state_order, function(uf) {
  paste0(unname(state_names[uf]), " (", uf, ") · ", year_order)
}), use.names = FALSE)
group_levels <- unlist(lapply(cell_levels, function(cell) {
  paste0(cell, " · ", source_order)
}), use.names = FALSE)
source_colours <- c(TISS = "#286F70", SUS = "#D28B38")
code_colours <- c("Lap-only (L)" = "#286F70", "Comparator-family only (O)" = "#D28B38", "Both (B)" = "#737F89")
sex_colours <- c(F = "#286F70", M = "#D28B38", unknown = "#A4AAAE")

theme_nature_contract <- function(base_size = 6.6) {
  theme_classic(base_size = base_size, base_family = "Arial") +
    theme(
      axis.line = element_line(linewidth = 0.32, colour = "#202020"),
      axis.ticks = element_line(linewidth = 0.30, colour = "#202020"),
      axis.title = element_text(size = base_size),
      axis.text = element_text(size = base_size - 0.6, colour = "#202020"),
      legend.title = element_text(size = base_size - 0.1),
      legend.text = element_text(size = base_size - 0.5),
      strip.text = element_text(size = base_size - 0.1, face = "bold", colour = "#202020"),
      strip.background = element_blank(),
      plot.title = element_text(size = base_size + 0.4, face = "bold", colour = "#202020"),
      plot.subtitle = element_text(size = base_size - 0.4, colour = "#444444"),
      plot.tag = element_text(size = 8, face = "bold", colour = "#202020"),
      panel.grid.major.x = element_line(linewidth = 0.18, colour = "#E7E9EA"),
      panel.grid.major.y = element_blank(),
      panel.grid.minor = element_blank(),
      panel.spacing = grid::unit(3.5, "mm"),
      legend.key.height = grid::unit(3.2, "mm"),
      legend.key.width = grid::unit(4.5, "mm"),
      plot.margin = margin(3, 4, 3, 4, unit = "mm")
    )
}
theme_set(theme_nature_contract())

add_cell_labels <- function(data) {
  data$state_name <- factor(unname(state_names[as.character(data$uf)]),
                            levels = unname(state_names[state_order]))
  data$year_f <- factor(data$year, levels = year_order)
  data$cell_label <- factor(
    paste0(as.character(data$state_name), " (", data$uf, ") · ", data$year),
    levels = cell_levels
  )
  if ("source" %in% names(data)) {
    data$group_label <- factor(
      paste0(as.character(data$cell_label), " · ", data$source),
      levels = group_levels
    )
  }
  data
}
fmt1 <- function(x) sprintf("%.1f", x)
fmt2 <- function(x) sprintf("%.2f", x)
as_bool <- function(x) {
  if (is.logical(x)) return(x)
  tolower(trimws(as.character(x))) %in% c("true", "t", "1")
}
label_cell_axis <- function() scale_y_discrete(limits = rev(cell_levels), drop = FALSE)
label_group_axis <- function() scale_y_discrete(limits = rev(group_levels), drop = FALSE)

state_year <- read_evidence("STATE_YEAR_TABLE_8.csv")
baseline <- read_evidence("BASELINE_COUNTS_16.csv")
h_strata <- read_evidence("H_STRATA.csv")
scenarios <- read_evidence("MEASUREMENT_SCENARIOS_8.csv")
urgency <- read_evidence("PRIOR_URGENCY_CONTRASTS_16.csv")
rd_only <- read_evidence("PRIOR_RD_ONLY_SENSITIVITY_8.csv")
monthly <- read_evidence("MONTHLY_DESCRIPTIVES_PRIOR.csv")
age <- read_evidence("AGE_ORIGINAL_BAND_DESCRIPTIVES.csv")
sex <- read_evidence("SEX_DESCRIPTIVES.csv")
feasibility <- read_evidence("FEASIBILITY_GATES.csv")
geography <- read_evidence("CONDITIONAL_GEOGRAPHY_8.csv")
clinical <- read_evidence("CLINICAL_K80_DESCRIPTIVES.csv")

if (nrow(state_year) != 8L || nrow(baseline) != 16L || nrow(scenarios) != 8L ||
    nrow(urgency) != 16L || nrow(rd_only) != 8L || nrow(h_strata) < 1L) {
  stop("Frozen primary evidence row counts do not match the figure contract.")
}
if (any(baseline$strict_N_records <= 0)) stop("Log-scaled record counts must be strictly positive.")
if (any(is.na(as_bool(baseline$strict_N_equals_L_plus_O_plus_B))) ||
    any(!as_bool(baseline$strict_N_equals_L_plus_O_plus_B)) ||
    any(state_year$equal_source_weights_sum_exact != 1) ||
    any(as_bool(scenarios$scenario_is_confidence_interval))) {
  stop("A frozen denominator, weighting, or scenario classification check failed.")
}
baseline <- add_cell_labels(baseline)
state_year <- add_cell_labels(state_year)
scenarios <- add_cell_labels(scenarios)
urgency <- add_cell_labels(urgency)
rd_only <- add_cell_labels(rd_only)
clinical <- add_cell_labels(clinical)
geography <- add_cell_labels(geography)

# Figure 1: source-specific volumes, strict coded composition, and TISS-only A share.
fig1a_data <- baseline[, c("evidence_id", "source", "uf", "year", "state_name", "cell_label",
                           "strict_N_records", "unit", "accepted_baseline_match")]

fig1b_data <- tidyr::pivot_longer(
  baseline,
  cols = c("lap_only_L_records", "open_only_O_records", "dual_coded_B_records"),
  names_to = "recorded_code_class", values_to = "records"
)
fig1b_data$code_label <- factor(
  fig1b_data$recorded_code_class,
  levels = c("lap_only_L_records", "open_only_O_records", "dual_coded_B_records"),
  labels = c("Lap-only (L)", "Comparator-family only (O)", "Both (B)")
)
fig1b_data$share_percent_of_strict_N <- 100 * fig1b_data$records / fig1b_data$strict_N_records

fig1c_data <- state_year[, c("evidence_id", "uf", "year", "state_name", "cell_label",
                             "TISS_N_strict_records",
                             "TISS_A_qualified_quantity_ambiguous_records_outside_N")]
names(fig1c_data)[names(fig1c_data) == "TISS_A_qualified_quantity_ambiguous_records_outside_N"] <- "A_outside_N_records"
fig1c_data$A_share_percent_of_N_plus_A <-
  100 * fig1c_data$A_outside_N_records /
  (fig1c_data$TISS_N_strict_records + fig1c_data$A_outside_N_records)

p1a <- ggplot(fig1a_data, aes(x = source, y = strict_N_records, colour = source)) +
  geom_point(size = 1.8) +
  geom_text(aes(y = strict_N_records * 1.4, label = scales::comma(strict_N_records)),
            vjust = 0, size = 1.8, show.legend = FALSE) +
  facet_grid(state_name ~ year, switch = "y") +
  scale_colour_manual(values = source_colours, guide = "none") +
  scale_y_log10(breaks = c(1000, 10000, 100000), labels = scales::label_comma(),
                limits = c(900, 120000), expand = expansion(mult = c(0.01, 0.05))) +
  labs(title = "Strict record volume", x = NULL,
       y = "Source-specific strict N records (log scale)") +
  theme(axis.text.x = element_text(size = 5.8),
        strip.text.y.left = element_text(angle = 0),
        panel.grid.major.y = element_line(linewidth = 0.18, colour = "#E7E9EA"))

b_labels <- baseline[, c("source", "uf", "year", "state_name", "cell_label", "dual_coded_B_records")]
b_labels$top_label <- paste0("B=", b_labels$dual_coded_B_records)
p1b <- ggplot(fig1b_data, aes(x = source, y = share_percent_of_strict_N, fill = code_label)) +
  geom_col(width = 0.68, colour = "white", linewidth = 0.12,
           position = position_stack(reverse = TRUE)) +
  geom_text(data = b_labels, aes(x = source, y = 106, label = top_label),
            inherit.aes = FALSE, size = 1.8) +
  facet_grid(state_name ~ year, switch = "y") +
  scale_fill_manual(values = code_colours, name = "Recorded procedure-code class") +
  scale_y_continuous(limits = c(0, 113), breaks = c(0, 25, 50, 75, 100),
                     labels = function(x) paste0(x, "%"), expand = c(0, 0)) +
  labs(title = "L/O/B composition within strict N", x = NULL,
       y = "Percent of source-specific strict N") +
  theme(axis.text.x = element_text(size = 5.8),
        strip.text.y.left = element_text(angle = 0),
        panel.grid.major.y = element_line(linewidth = 0.18, colour = "#E7E9EA"),
        legend.position = "bottom", legend.box = "horizontal")

p1c <- ggplot(fig1c_data, aes(x = A_share_percent_of_N_plus_A, y = cell_label)) +
  geom_segment(aes(x = 0, xend = A_share_percent_of_N_plus_A,
                   y = cell_label, yend = cell_label),
               linewidth = 0.55, colour = "#A6B7B8") +
  geom_point(size = 2.0, colour = source_colours[["TISS"]]) +
  geom_text(aes(label = paste0(fmt1(A_share_percent_of_N_plus_A), "%")),
            hjust = -0.18, size = 1.8, colour = "#202020") +
  label_cell_axis() +
  scale_x_continuous(limits = c(0, 28), breaks = seq(0, 25, by = 5),
                     labels = function(x) paste0(x, "%")) +
  labs(title = "Qualified TISS target events with quantity ambiguity (A)",
       subtitle = "A is a defined category outside strict N; denominator N + A",
       x = "Percent of TISS N+A records", y = NULL) +
  theme(axis.text.y = element_text(size = 5.7), panel.grid.major.x = element_line())

fig1 <- ((p1a | p1b) / p1c) +
  plot_layout(heights = c(1.35, 1), guides = "collect") +
  plot_annotation(tag_levels = "a") &
  theme(plot.tag = element_text(size = 8, face = "bold"), legend.position = "bottom")

# Figure 2: standardized source fractions and the corresponding primary gap.
fig2a_data <- bind_rows(
  data.frame(evidence_id = state_year$evidence_id, uf = state_year$uf, year = state_year$year,
             state_name = state_year$state_name, cell_label = state_year$cell_label,
             source = "TISS", standardized_fraction_percent = state_year$TISS_lap_percent_standardized,
             strict_N_in_H = state_year$TISS_N_in_H_records),
  data.frame(evidence_id = state_year$evidence_id, uf = state_year$uf, year = state_year$year,
             state_name = state_year$state_name, cell_label = state_year$cell_label,
             source = "SUS", standardized_fraction_percent = state_year$SUS_lap_percent_standardized,
             strict_N_in_H = state_year$SUS_N_in_H_records)
)
fig2b_data <- state_year[, c("evidence_id", "uf", "year", "state_name", "cell_label",
                             "standardized_gap_pp_TISS_minus_SUS", "difference_unit",
                             "TISS_N_in_H_records", "SUS_N_in_H_records")]

p2a <- ggplot(fig2a_data, aes(x = standardized_fraction_percent, y = cell_label, colour = source)) +
  geom_point(position = position_dodge(width = 0.55), size = 1.85) +
  geom_text(aes(x = standardized_fraction_percent + 3,
                label = fmt1(standardized_fraction_percent)),
            position = position_dodge(width = 0.55), hjust = 0,
            size = 1.8, show.legend = FALSE) +
  label_cell_axis() +
  scale_colour_manual(values = source_colours, name = "Source") +
  scale_x_continuous(limits = c(0, 108), breaks = c(0, 25, 50, 75, 100),
                     labels = function(x) paste0(x, "%")) +
  labs(title = "Standardized source fractions", x = "Standardized L-only share (%)",
       y = NULL) +
  theme(axis.text.y = element_text(size = 5.4), legend.position = "bottom")

p2b <- ggplot(fig2b_data, aes(x = standardized_gap_pp_TISS_minus_SUS, y = cell_label)) +
  geom_segment(aes(x = 0, xend = standardized_gap_pp_TISS_minus_SUS,
                   y = cell_label, yend = cell_label),
               linewidth = 0.55, colour = "#A6B7B8") +
  geom_point(size = 2.0, colour = "#2D4652") +
  geom_text(aes(label = fmt1(standardized_gap_pp_TISS_minus_SUS)),
            nudge_x = 3, hjust = 0, size = 1.8, colour = "#202020") +
  label_cell_axis() +
  scale_x_continuous(limits = c(0, 95), breaks = c(0, 25, 50, 75),
                     labels = function(x) paste0(x, " pp")) +
  labs(title = "Primary standardized gap", x = "TISS minus SUS (percentage points)",
       y = NULL) +
  theme(axis.text.y = element_blank(), axis.ticks.y = element_blank())

fig2 <- (p2a | p2b) +
  plot_layout(widths = c(1.2, 0.9), guides = "collect") +
  plot_annotation(tag_levels = "a") &
  theme(plot.tag = element_text(size = 8, face = "bold"), legend.position = "bottom")

# Figure 3: three gap definitions and common-support coverage.
fig3a_data <- tidyr::pivot_longer(
  state_year,
  cols = c("all_records_crude_gap_pp_TISS_minus_SUS",
           "same_H_crude_gap_pp_TISS_minus_SUS",
           "standardized_gap_pp_TISS_minus_SUS"),
  names_to = "estimand", values_to = "gap_pp"
)
fig3a_data$estimand_label <- factor(
  fig3a_data$estimand,
  levels = c("all_records_crude_gap_pp_TISS_minus_SUS",
             "same_H_crude_gap_pp_TISS_minus_SUS",
             "standardized_gap_pp_TISS_minus_SUS"),
  labels = c("All-record crude", "Same-H crude", "Standardized")
)
fig3b_data <- bind_rows(
  data.frame(evidence_id = state_year$evidence_id, uf = state_year$uf, year = state_year$year,
             state_name = state_year$state_name, cell_label = state_year$cell_label,
             source = "TISS", coverage_percent = state_year$TISS_H_coverage_percent_of_all_strict_N,
             H_records = state_year$TISS_N_in_H_records, strict_N_records = state_year$TISS_N_strict_records),
  data.frame(evidence_id = state_year$evidence_id, uf = state_year$uf, year = state_year$year,
             state_name = state_year$state_name, cell_label = state_year$cell_label,
             source = "SUS", coverage_percent = state_year$SUS_H_coverage_percent_of_all_strict_N,
             H_records = state_year$SUS_N_in_H_records, strict_N_records = state_year$SUS_N_strict_records)
)

p3a <- ggplot(fig3a_data, aes(x = estimand_label, y = gap_pp, colour = estimand_label)) +
  geom_point(size = 1.55) +
  geom_text(aes(label = fmt1(gap_pp)), vjust = -0.75, size = 1.8, show.legend = FALSE) +
  facet_grid(state_name ~ year_f, switch = "y") +
  scale_colour_manual(values = c("All-record crude" = "#465B67",
                                 "Same-H crude" = "#A08E68",
                                 "Standardized" = "#286F70"), guide = "none") +
  scale_y_continuous(limits = c(0, 120), breaks = c(0, 50, 100),
                     labels = function(x) paste0(x, " pp"), expand = expansion(mult = c(0.02, 0.03))) +
  labs(title = "Gap under three denominator and support definitions",
       x = NULL, y = "TISS minus SUS (percentage points)") +
  theme(axis.text.x = element_text(size = 5.1, angle = 0, vjust = 0.5),
        strip.text.y.left = element_text(angle = 0),
        panel.grid.major.y = element_line(linewidth = 0.18, colour = "#E7E9EA"))

p3b <- ggplot(fig3b_data, aes(x = coverage_percent, y = cell_label, colour = source)) +
  geom_point(position = position_dodge(width = 0.55), size = 1.8) +
  geom_text(aes(x = coverage_percent + 3, label = fmt1(coverage_percent)),
            position = position_dodge(width = 0.55), hjust = 0,
            size = 1.8, show.legend = FALSE) +
  label_cell_axis() +
  scale_colour_manual(values = source_colours, name = "Source") +
  scale_x_continuous(limits = c(0, 109), breaks = c(0, 50, 80, 100),
                     labels = function(x) paste0(x, "%")) +
  labs(title = "Observed strict N within jointly supported H",
       x = "Share of each source-specific strict N", y = NULL) +
  theme(axis.text.y = element_text(size = 5.4), legend.position = "bottom")

fig3 <- (p3a / p3b) + plot_layout(heights = c(1.05, 0.9)) +
  plot_annotation(tag_levels = "a") & theme(plot.tag = element_text(size = 8, face = "bold"))

# Figure 4: conditional fixed-H measurement scenarios and strict-standardized points.
fig4_source_data <- bind_rows(
  data.frame(evidence_id = scenarios$evidence_id, uf = scenarios$uf, year = scenarios$year,
             state_name = scenarios$state_name, cell_label = scenarios$cell_label, source = "TISS",
             scenario_lower_percent = scenarios$TISS_scenario_lower_percent,
             scenario_upper_percent = scenarios$TISS_scenario_upper_percent,
             strict_standardized_percent = state_year$TISS_lap_percent_standardized,
             strict_N_in_H = scenarios$TISS_N_in_H),
  data.frame(evidence_id = scenarios$evidence_id, uf = scenarios$uf, year = scenarios$year,
             state_name = scenarios$state_name, cell_label = scenarios$cell_label, source = "SUS",
             scenario_lower_percent = scenarios$SUS_scenario_lower_percent,
             scenario_upper_percent = scenarios$SUS_scenario_upper_percent,
             strict_standardized_percent = state_year$SUS_lap_percent_standardized,
             strict_N_in_H = scenarios$SUS_N_in_H)
)
fig4_source_data$cell_y <- 9 - match(as.character(fig4_source_data$cell_label), cell_levels)
fig4_source_data$y_source <- fig4_source_data$cell_y + ifelse(fig4_source_data$source == "TISS", 0.15, -0.15)
fig4_gap_data <- data.frame(
  evidence_id = scenarios$evidence_id, uf = scenarios$uf, year = scenarios$year,
  state_name = scenarios$state_name, cell_label = scenarios$cell_label,
  scenario_lower_gap_pp = scenarios$gap_lower_pp_TISS_minus_SUS,
  scenario_upper_gap_pp = scenarios$gap_upper_pp_TISS_minus_SUS,
  strict_standardized_gap_pp = scenarios$strict_standardized_gap_pp,
  scenario_classification = scenarios$scenario_classification,
  scenario_is_confidence_interval = scenarios$scenario_is_confidence_interval,
  unit = scenarios$unit
)
fig4_gap_data$cell_y <- 9 - match(as.character(fig4_gap_data$cell_label), cell_levels)

p4a <- ggplot(fig4_source_data) +
  geom_segment(aes(x = scenario_lower_percent, xend = scenario_upper_percent,
                   y = y_source, yend = y_source, colour = source), linewidth = 1.15) +
  geom_point(aes(x = strict_standardized_percent, y = y_source, colour = source),
             shape = 18, size = 2.0) +
  geom_text(aes(x = strict_standardized_percent, y = y_source,
                label = fmt1(strict_standardized_percent)),
            hjust = -0.18, size = 1.8, show.legend = FALSE) +
  scale_colour_manual(values = source_colours, name = "Source") +
  scale_y_continuous(breaks = 8:1, labels = cell_levels, limits = c(0.5, 8.5),
                     expand = c(0, 0)) +
  scale_x_continuous(limits = c(0, 112), breaks = c(0, 25, 50, 75, 100),
                     labels = function(x) paste0(x, "%")) +
  labs(title = "Source fractions under conservative fixed-H A/B coding scenarios",
       subtitle = "TISS A and dual-coded B assigned to L-only or comparator-family-only (O); known codes are disregarded",
       x = "L-only fraction under the stated coding scenarios", y = NULL) +
  theme(axis.text.y = element_text(size = 5.5), legend.position = "bottom")

p4b <- ggplot(fig4_gap_data) +
  geom_vline(xintercept = 0, linetype = "dashed", linewidth = 0.35, colour = "#60686B") +
  geom_segment(aes(x = scenario_lower_gap_pp, xend = scenario_upper_gap_pp,
                   y = cell_y, yend = cell_y), linewidth = 1.1, colour = "#9AA7AA") +
  geom_point(aes(x = scenario_lower_gap_pp, y = cell_y), shape = 21, size = 1.4,
             fill = "white", colour = "#78868A", stroke = 0.35) +
  geom_point(aes(x = scenario_upper_gap_pp, y = cell_y), shape = 21, size = 1.4,
             fill = "white", colour = "#78868A", stroke = 0.35) +
  geom_point(aes(x = strict_standardized_gap_pp, y = cell_y), shape = 23, size = 2.0,
             fill = "#2D4652", colour = "#2D4652") +
  geom_text(aes(x = strict_standardized_gap_pp, y = cell_y,
                label = fmt1(strict_standardized_gap_pp)),
            nudge_x = 3.5, hjust = 0, size = 1.8) +
  scale_y_continuous(breaks = 8:1, labels = cell_levels, limits = c(0.5, 8.5),
                     expand = c(0, 0)) +
  scale_x_continuous(limits = c(-7, 98), breaks = c(0, 25, 50, 75),
                     labels = function(x) paste0(x, " pp")) +
  labs(title = "TISS–SUS gap under conservative fixed-H A/B coding scenarios",
       subtitle = "Ranges are scenario outputs, not confidence intervals; diamonds show the strict standardized gap",
       x = "Percentage points", y = NULL) +
  theme(axis.text.y = element_text(size = 5.5))

fig4 <- (p4a / p4b) + plot_layout(heights = c(1, 1)) +
  plot_annotation(tag_levels = "a") & theme(plot.tag = element_text(size = 8, face = "bold"))

# Figure 5: urgency-stratum contrasts and the RD-main-operation-only sensitivity.
fig5a_data <- urgency[, c("uf", "year", "state_name", "cell_label",
                          "urgency_original_label", "urgency_canonical", "TISS_N", "TISS_L",
                          "SUS_N", "SUS_L", "TISS_lap_percent", "SUS_lap_percent",
                          "gap_pp_TISS_minus_SUS", "gap_unit", "denominator_definition",
                          "joint_age_sex_standardized", "counts_match_prior_accepted_descriptives",
                          "source_sha256", "interpretation")]
fig5a_data$source_evidence_file <- "PRIOR_URGENCY_CONTRASTS_16.csv"
fig5a_data$year_f <- factor(fig5a_data$year, levels = year_order)
fig5a_data$urgency_canonical <- factor(fig5a_data$urgency_canonical,
                                       levels = c("elective", "emergency"))
fig5b_data <- rd_only[, c("uf", "year", "state_name", "cell_label",
                          "TISS_primary_N", "SUS_RD_only_N", "prior_all_record_primary_gap_pp",
                          "RD_only_gap_pp_TISS_minus_SUS", "RD_only_change_from_prior_primary_gap_pp",
                          "RD_only_definition", "this_is_primary_standardization_target",
                          "source_sha256", "independent_replication", "interpretation")]
fig5b_data$source_evidence_file <- "PRIOR_RD_ONLY_SENSITIVITY_8.csv"
fig5b_long <- bind_rows(
  data.frame(fig5b_data[, c("uf", "year", "state_name", "cell_label")],
             contrast = "Primary union-coded SUS basis", gap_pp = fig5b_data$prior_all_record_primary_gap_pp),
  data.frame(fig5b_data[, c("uf", "year", "state_name", "cell_label")],
             contrast = "SUS RD-main-only sensitivity", gap_pp = fig5b_data$RD_only_gap_pp_TISS_minus_SUS)
)

p5a <- ggplot(fig5a_data, aes(x = urgency_canonical, y = gap_pp_TISS_minus_SUS,
                              colour = urgency_canonical)) +
  geom_point(size = 1.75) +
  geom_text(aes(label = fmt1(gap_pp_TISS_minus_SUS)), vjust = -0.75,
            size = 1.8, show.legend = FALSE) +
  facet_grid(state_name ~ year_f, switch = "y") +
  scale_colour_manual(values = c(elective = "#286F70", emergency = "#D28B38"), guide = "none") +
  scale_y_continuous(limits = c(0, 120), breaks = c(0, 50, 100),
                     labels = function(x) paste0(x, " pp")) +
  scale_x_discrete(labels = c(elective = "Elective", emergency = "Emergency")) +
  labs(title = "Within-urgency recorded-code gaps",
       subtitle = "Each source denominator is N = L + O + B; not joint age–sex standardized",
       x = NULL, y = "TISS minus SUS (percentage points)") +
  theme(axis.text.x = element_text(size = 5.5),
        strip.text.y.left = element_text(angle = 0),
        panel.grid.major.y = element_line(linewidth = 0.18, colour = "#E7E9EA"))

p5b <- ggplot(fig5b_long, aes(x = gap_pp, y = cell_label, colour = contrast)) +
  geom_point(position = position_dodge(width = 0.55), size = 1.8) +
  geom_text(aes(label = fmt1(gap_pp)), position = position_dodge(width = 0.55),
            hjust = -0.18, size = 1.8, show.legend = FALSE) +
  label_cell_axis() +
  scale_colour_manual(values = c("Primary union-coded SUS basis" = "#465B67",
                                 "SUS RD-main-only sensitivity" = "#D28B38"),
                      name = "SUS coding basis",
                      labels = c("Primary union-coded SUS basis" = "Primary union-coded",
                                 "SUS RD-main-only sensitivity" = "RD-main-only")) +
  scale_x_continuous(limits = c(0, 98), breaks = c(0, 25, 50, 75),
                     labels = function(x) paste0(x, " pp")) +
  labs(title = "SUS RD-only sensitivity",
       subtitle = "TISS primary strict N retained; SUS RD-main-operation-only sensitivity; all-record crude gaps",
       x = "TISS minus SUS (percentage points)", y = NULL) +
  theme(axis.text.y = element_text(size = 5.4), legend.position = "bottom")

fig5 <- (p5a / p5b) + plot_layout(heights = c(1.1, 0.9)) +
  plot_annotation(tag_levels = "a") & theme(plot.tag = element_text(size = 8, face = "bold"))

# Supplementary Figure S1: monthly counts on the accepted basis for each source.
s1_data <- monthly[
  (monthly$source == "TISS" & monthly$analysis_basis == "primary_strict") |
    (monthly$source == "SUS" & monthly$analysis_basis == "primary_union_coded_record_ascertainment"),
]
s1_data$month_number <- as.integer(substr(s1_data$label, 6, 7))
s1_data$month_label <- factor(s1_data$month_number, levels = 1:12, labels = month.abb)
s1_data <- add_cell_labels(s1_data)
month_coverage <- aggregate(month_number ~ source + uf + year, s1_data,
                            function(x) length(unique(x)))
if (nrow(s1_data) != 192L || nrow(month_coverage) != 16L || any(month_coverage$month_number != 12L)) {
  stop("Source-specific monthly descriptions do not contain 12 observed month bins per state-year.")
}

plot_month_source <- function(source_code, source_title) {
  data <- s1_data[s1_data$source == source_code, ]
  ggplot(data, aes(x = month_number, y = N, group = interaction(uf, year))) +
    geom_line(linewidth = 0.45, colour = source_colours[[source_code]]) +
    geom_point(size = 0.9, colour = source_colours[[source_code]]) +
    facet_grid(state_name ~ year_f, scales = "free_y", switch = "y") +
    scale_x_continuous(breaks = 1:12, labels = month.abb, limits = c(1, 12)) +
    scale_y_continuous(labels = scales::label_comma()) +
    labs(title = source_title, x = "Calendar month", y = "Monthly records on source-specific basis") +
    theme(axis.text.x = element_text(size = 5.1),
          strip.text.y.left = element_text(angle = 0),
          panel.grid.major.y = element_line(linewidth = 0.18, colour = "#E7E9EA"))
}
pS1a <- plot_month_source("TISS", "TISS monthly strict N")
pS1b <- plot_month_source("SUS", "SUS monthly primary union-coded records")
figS1 <- (pS1a / pS1b) + plot_layout(heights = c(1, 1)) +
  plot_annotation(tag_levels = "a") & theme(plot.tag = element_text(size = 8, face = "bold"))

# Supplementary Figure S2: full original age categories and recorded sex categories.
age_categories <- c("<1", "1-4", "5-9", "10-14", "15-19", "20-29", "30-39",
                    "40-49", "50-59", "60-69", "70-79", "80+", "Unknown", "Unmapped")
age_group_totals <- aggregate(N_strict_records ~ source + uf + year, age, sum)
baseline_check <- merge(baseline[, c("source", "uf", "year", "strict_N_records")],
                        age_group_totals, by = c("source", "uf", "year"), all = TRUE)
if (any(is.na(baseline_check$N_strict_records)) ||
    any(baseline_check$strict_N_records != baseline_check$N_strict_records)) {
  stop("Age-category totals do not reconcile to source-specific strict N.")
}
age_groups <- unique(age[, c("source", "uf", "year")])
age_grid <- merge(age_groups, data.frame(category = age_categories), by = NULL)
age_full <- merge(age_grid,
                  age[, c("source", "uf", "year", "category", "N_strict_records")],
                  by = c("source", "uf", "year", "category"), all.x = TRUE, sort = FALSE)
age_full$N_strict_records[is.na(age_full$N_strict_records)] <- 0L
age_full <- merge(age_full, baseline[, c("source", "uf", "year", "strict_N_records")],
                  by = c("source", "uf", "year"), all.x = TRUE, sort = FALSE)
age_full$share_percent_of_strict_N <- 100 * age_full$N_strict_records / age_full$strict_N_records
age_full$category <- factor(age_full$category, levels = age_categories)
age_full <- add_cell_labels(age_full)

sex_categories <- c("F", "M", "unknown")
sex_group_totals <- aggregate(N_strict_records ~ source + uf + year, sex, sum)
baseline_sex_check <- merge(baseline[, c("source", "uf", "year", "strict_N_records")],
                            sex_group_totals, by = c("source", "uf", "year"), all = TRUE)
if (any(is.na(baseline_sex_check$N_strict_records)) ||
    any(baseline_sex_check$strict_N_records != baseline_sex_check$N_strict_records)) {
  stop("Sex-category totals do not reconcile to source-specific strict N.")
}
sex_grid <- merge(unique(sex[, c("source", "uf", "year")]),
                  data.frame(category = sex_categories), by = NULL)
sex_full <- merge(sex_grid,
                  sex[, c("source", "uf", "year", "category", "N_strict_records")],
                  by = c("source", "uf", "year", "category"), all.x = TRUE, sort = FALSE)
sex_full$N_strict_records[is.na(sex_full$N_strict_records)] <- 0L
sex_full <- merge(sex_full, baseline[, c("source", "uf", "year", "strict_N_records")],
                  by = c("source", "uf", "year"), all.x = TRUE, sort = FALSE)
sex_full$share_percent_of_strict_N <- 100 * sex_full$N_strict_records / sex_full$strict_N_records
sex_full$category <- factor(sex_full$category, levels = sex_categories)
sex_full <- add_cell_labels(sex_full)

pS2a <- ggplot(age_full, aes(x = category, y = group_label,
                             fill = share_percent_of_strict_N)) +
  geom_tile(colour = "white", linewidth = 0.13) +
  label_group_axis() +
  scale_fill_gradient(low = "#F1F5F4", high = "#286F70", name = "% of strict N") +
  labs(title = "Original age-band composition", x = "Recorded age category", y = NULL) +
  theme(axis.text.y = element_text(size = 5.1),
        axis.text.x = element_text(size = 5.0, angle = 42, hjust = 1),
        panel.grid = element_blank(), legend.position = "right")

pS2b <- ggplot(sex_full, aes(x = share_percent_of_strict_N, y = group_label, fill = category)) +
  geom_col(width = 0.78) +
  label_group_axis() +
  scale_fill_manual(values = sex_colours, breaks = sex_categories,
                    labels = c("F" = "F", "M" = "M", "unknown" = "Unknown"),
                    name = "Recorded sex category") +
  scale_x_continuous(limits = c(0, 100.000001), breaks = c(0, 25, 50, 75, 100),
                     labels = function(x) paste0(x, "%")) +
  labs(title = "Recorded sex-category composition", x = "Percent of source-specific strict N", y = NULL) +
  theme(axis.text.y = element_text(size = 5.1), legend.position = "bottom")
figS2 <- (pS2a / pS2b) + plot_layout(heights = c(1.35, 0.9)) +
  plot_annotation(tag_levels = "a") & theme(plot.tag = element_text(size = 8, face = "bold"))

# Supplementary Figure S3: diagnosis-format coverage and the clinical-gate boundary.
figS3a_data <- clinical[, c("evidence_id", "uf", "year", "source", "state_name", "cell_label",
                            "recorded_diagnosis_format_valid_n",
                            "recorded_diagnosis_format_valid_percent",
                            "strict_N_denominator_records", "diagnosis_semantics_compatible",
                            "clinical_cohort_claim_allowed")]
figS3b_data <- clinical[, c("evidence_id", "uf", "year", "source", "state_name", "cell_label",
                            "lap_only_diagnosis_format_valid_percent", "lap_only_n",
                            "open_only_diagnosis_format_valid_percent", "open_only_n",
                            "absolute_lap_open_coverage_gap_pp", "lap_open_gate_status",
                            "clinical_cohort_claim_allowed")]

pS3a <- ggplot(figS3a_data, aes(x = recorded_diagnosis_format_valid_percent,
                                y = cell_label, colour = source)) +
  geom_point(position = position_dodge(width = 0.55), size = 1.8) +
  geom_text(aes(x = recorded_diagnosis_format_valid_percent + 3,
                label = fmt1(recorded_diagnosis_format_valid_percent)),
            position = position_dodge(width = 0.55), hjust = 0,
            size = 1.8, show.legend = FALSE) +
  label_cell_axis() +
  scale_colour_manual(values = source_colours, name = "Source") +
  scale_x_continuous(limits = c(0, 111), breaks = c(0, 25, 50, 75, 100),
                     labels = function(x) paste0(x, "%")) +
  labs(title = "Recorded diagnosis-format validity",
       x = "Percent of source-specific strict N", y = NULL) +
  theme(axis.text.y = element_text(size = 5.4), legend.position = "bottom")

assessed_s3 <- figS3b_data[is.finite(figS3b_data$absolute_lap_open_coverage_gap_pp), ]
pS3b <- ggplot(assessed_s3, aes(x = absolute_lap_open_coverage_gap_pp,
                                y = cell_label, colour = source)) +
  geom_point(position = position_dodge(width = 0.55), size = 1.8) +
  geom_text(aes(x = absolute_lap_open_coverage_gap_pp + 3,
                label = fmt1(absolute_lap_open_coverage_gap_pp)),
            position = position_dodge(width = 0.55), hjust = 0,
            size = 1.8, show.legend = FALSE) +
  label_cell_axis() +
  scale_colour_manual(values = source_colours, name = "Source") +
  scale_x_continuous(limits = c(0, 112), breaks = c(0, 25, 50, 75, 100),
                     labels = function(x) paste0(x, " pp")) +
  labs(title = "Absolute L-only vs comparator-family-only format-coverage difference",
       subtitle = "No point is drawn where the gate was not assessable",
       x = "Absolute coverage difference (percentage points)", y = NULL) +
  theme(axis.text.y = element_text(size = 5.4), legend.position = "bottom")
figS3 <- (pS3a / pS3b) + plot_layout(heights = c(1, 1)) +
  plot_annotation(tag_levels = "a") & theme(plot.tag = element_text(size = 8, face = "bold"))

# Supplementary Figure S4: conditional RD6 geography support and available contrasts.
figS4a_data <- bind_rows(
  data.frame(evidence_id = geography$evidence_id, uf = geography$uf, year = geography$year,
             state_name = geography$state_name, cell_label = geography$cell_label, source = "TISS",
             municipality_H_coverage_percent = geography$municipality_only_TISS_H_coverage_percent,
             source_specific_strict_N = state_year$TISS_N_strict_records,
             H_strata = geography$municipality_only_H_strata,
             both_sources_ge_80pct = geography$municipality_only_both_sources_ge_80pct,
             conditional_label = geography$conditional_label,
             main_geography_status = geography$main_geography_status),
  data.frame(evidence_id = geography$evidence_id, uf = geography$uf, year = geography$year,
             state_name = geography$state_name, cell_label = geography$cell_label, source = "SUS",
             municipality_H_coverage_percent = geography$municipality_only_SUS_H_coverage_percent,
             source_specific_strict_N = state_year$SUS_N_strict_records,
             H_strata = geography$municipality_only_H_strata,
             both_sources_ge_80pct = geography$municipality_only_both_sources_ge_80pct,
             conditional_label = geography$conditional_label,
             main_geography_status = geography$main_geography_status)
)
figS4b_data <- geography[as_bool(geography$municipality_only_both_sources_ge_80pct) &
                         is.finite(geography$municipality_only_standardized_gap_pp),
                         c("evidence_id", "uf", "year", "state_name", "cell_label",
                           "conditional_label", "municipality_only_H_strata",
                           "municipality_only_TISS_H_coverage_percent",
                           "municipality_only_SUS_H_coverage_percent",
                           "municipality_only_standardized_gap_pp",
                           "geography_is_same_hospital_comparison", "main_geography_status")]
if (nrow(figS4b_data) != 2L || any(figS4b_data$uf != "SP") ||
    any(as_bool(figS4b_data$geography_is_same_hospital_comparison))) {
  stop("The conditional RD6 geography panel failed its stated support/interpretation gate.")
}

pS4a <- ggplot(figS4a_data, aes(x = municipality_H_coverage_percent,
                                y = cell_label, colour = source)) +
  geom_vline(xintercept = 80, linetype = "dashed", linewidth = 0.35, colour = "#70787A") +
  geom_point(position = position_dodge(width = 0.55), size = 1.8) +
  geom_text(aes(label = fmt1(municipality_H_coverage_percent)),
            position = position_dodge(width = 0.55), hjust = -0.18,
            size = 1.8, show.legend = FALSE) +
  label_cell_axis() +
  scale_colour_manual(values = source_colours, name = "Source") +
  scale_x_continuous(limits = c(0, 110), breaks = c(0, 25, 50, 80, 100),
                     labels = function(x) paste0(x, "%")) +
  labs(title = "Municipality-only H support under conditional RD6 convention",
       subtitle = "Dashed line marks the 80% per-source support threshold",
       x = "Share of source-specific strict N in jointly supported H", y = NULL) +
  theme(axis.text.y = element_text(size = 5.4), legend.position = "bottom")

pS4b <- ggplot(figS4b_data, aes(x = municipality_only_standardized_gap_pp,
                                y = cell_label)) +
  geom_vline(xintercept = 0, linetype = "dashed", linewidth = 0.35, colour = "#70787A") +
  geom_point(size = 2.0, colour = "#2D4652") +
  geom_text(aes(label = fmt1(municipality_only_standardized_gap_pp)),
            nudge_x = 0.5, hjust = 0, size = 1.8) +
  scale_y_discrete(limits = rev(as.character(figS4b_data$cell_label))) +
  scale_x_continuous(limits = c(-2, 24), breaks = c(0, 5, 10, 15, 20),
                     labels = function(x) paste0(x, " pp")) +
  labs(title = "Conditional RD6 municipality-only standardized gap",
       subtitle = "Only São Paulo cells met ≥80% support in both sources",
       x = "TISS minus SUS (percentage points)", y = NULL) +
  theme(axis.text.y = element_text(size = 5.5))
figS4 <- (pS4a / pS4b) + plot_layout(heights = c(1, 0.7)) +
  plot_annotation(tag_levels = "a") & theme(plot.tag = element_text(size = 8, face = "bold"))

# Supplementary Figure S5: TISS A detail and a fixed-H code-presence auxiliary.
a_breakdown_data <- read_evidence("A_breakdown_TISS.csv")
auxiliary_data <- read_evidence("package_code_presence_aux_8.csv")
if (nrow(a_breakdown_data) != 30L || any(a_breakdown_data$n < 0) || nrow(auxiliary_data) != 8L) {
  stop("The TISS A decomposition or package-code auxiliary has unexpected rows or counts.")
}
a_totals <- aggregate(n ~ uf + year, a_breakdown_data, sum)
expected_a_totals <- state_year[, c("uf", "year", "TISS_A_qualified_quantity_ambiguous_records_outside_N")]
names(expected_a_totals)[[3]] <- "expected_A"
a_total_check <- merge(a_totals, expected_a_totals, by = c("uf", "year"), all = TRUE)
if (nrow(a_total_check) != 8L || any(is.na(a_total_check$n)) ||
    any(a_total_check$n != a_total_check$expected_A)) {
  stop("A decomposition counts do not reconcile to the frozen TISS A totals.")
}

family_labels <- c(
  lap_only = "Lap-only (L)",
  open_only = "Comparator-family only (O)",
  both = "Both (B)"
)
package_labels <- c(
  package_no_all_target_rows = "No on all qualified rows",
  package_yes_all_target_rows = "Yes on all qualified rows",
  package_yes_mixed_with_no_or_unknown = "Yes mixed with no/unknown"
)
quantity_labels <- c(
  malformed_any = "Malformed quantity",
  missing_any = "Missing quantity"
)
breakdown_levels <- c(
  "No on all qualified rows · Malformed quantity",
  "Yes on all qualified rows · Missing quantity",
  "Yes mixed with no/unknown · Missing quantity"
)
a_breakdown_data$family_label <- factor(
  unname(family_labels[a_breakdown_data$qualified_target_code_family]),
  levels = unname(family_labels[c("lap_only", "open_only", "both")])
)
a_breakdown_data$breakdown_label <- factor(
  paste(unname(package_labels[a_breakdown_data$IND_PACOTE_group]),
        unname(quantity_labels[a_breakdown_data$exclusive_quantity_exception]), sep = " · "),
  levels = breakdown_levels
)
a_breakdown_data$state_year_label <- factor(
  paste0(a_breakdown_data$uf, "\n", a_breakdown_data$year),
  levels = unlist(lapply(state_order, function(uf) paste0(uf, "\n", year_order)), use.names = FALSE)
)
a_display_grid <- tidyr::complete(
  a_breakdown_data,
  family_label = factor(unname(family_labels[c("lap_only", "open_only", "both")]),
                        levels = unname(family_labels[c("lap_only", "open_only", "both")])),
  breakdown_label = factor(breakdown_levels, levels = breakdown_levels),
  state_year_label = factor(
    unlist(lapply(state_order, function(uf) paste0(uf, "\n", year_order)), use.names = FALSE),
    levels = unlist(lapply(state_order, function(uf) paste0(uf, "\n", year_order)), use.names = FALSE)
  ),
  fill = list(n = 0L)
)
a_observed_plot_data <- data.frame(
  uf = a_breakdown_data$uf,
  year = a_breakdown_data$year,
  target_code_family = as.character(a_breakdown_data$family_label),
  package_flag_group = as.character(unname(package_labels[a_breakdown_data$IND_PACOTE_group])),
  quantity_exception_class = as.character(unname(quantity_labels[a_breakdown_data$exclusive_quantity_exception])),
  event_count = as.numeric(a_breakdown_data$n),
  stringsAsFactors = FALSE
)
a_display_plot_data <- data.frame(
  state_year = as.character(a_display_grid$state_year_label),
  target_code_family = as.character(a_display_grid$family_label),
  package_and_quantity_group = as.character(a_display_grid$breakdown_label),
  event_count = as.numeric(a_display_grid$n),
  stringsAsFactors = FALSE
)

pS5a <- ggplot(a_display_grid, aes(x = state_year_label, y = breakdown_label,
                                   fill = log10(n + 1))) +
  geom_tile(colour = "white", linewidth = 0.28) +
  geom_text(aes(label = scales::comma(n)), size = 1.8, colour = "#202020") +
  facet_grid(family_label ~ ., scales = "free_y", space = "free_y", drop = TRUE) +
  scale_fill_gradient(
    low = "#F3F6F5", high = "#286F70", name = "Events\nlog10(n + 1)",
    breaks = log10(c(0, 1, 10, 100, 1000, 10000) + 1),
    labels = c("0", "1", "10", "100", "1,000", "10,000")
  ) +
  labs(title = "TISS A events by code family, package flag and quantity exception",
       subtitle = "Only missing and malformed quantity classes were observed; zero means no events in that cell",
       x = "State-year", y = NULL) +
  theme(axis.text.x = element_text(size = 5.3, lineheight = 0.9),
        axis.text.y = element_text(size = 5.1),
        strip.text.y = element_text(size = 5.5, face = "bold"),
        panel.spacing.y = grid::unit(1.3, "mm"),
        legend.position = "right")

auxiliary_data$cell_label <- factor(
  paste0(unname(state_names[auxiliary_data$uf]), " (", auxiliary_data$uf, ") · ", auxiliary_data$year),
  levels = cell_levels
)
auxiliary_data$strict_gap_pp <- as.numeric(auxiliary_data$strict_TISS_minus_SUS_gap_pp)
auxiliary_data$auxiliary_gap_pp <- as.numeric(auxiliary_data$auxiliary_TISS_minus_SUS_gap_pp)
auxiliary_data$auxiliary_gap_change_pp <- auxiliary_data$auxiliary_gap_pp - auxiliary_data$strict_gap_pp
if (any(as.numeric(auxiliary_data$frozen_H_weight_sum) != 1) ||
    any(as.numeric(auxiliary_data$SUS_A) != 0) ||
    any(as.numeric(auxiliary_data$eligible_A_inside_H) +
        as.numeric(auxiliary_data$eligible_A_outside_H_or_unmapped) !=
        as.numeric(auxiliary_data$eligible_A_total))) {
  stop("The package-code auxiliary failed its frozen-H, SUS A, or event-accounting checks.")
}
strict_gap_reference <- state_year[, c("uf", "year", "standardized_gap_pp_TISS_minus_SUS")]
auxiliary_check <- merge(auxiliary_data, strict_gap_reference, by = c("uf", "year"), all = TRUE)
if (nrow(auxiliary_check) != 8L ||
    any(abs(auxiliary_check$strict_gap_pp -
            auxiliary_check$standardized_gap_pp_TISS_minus_SUS) > 1e-8)) {
  stop("The strict comparison in the auxiliary file differs from the frozen primary standardized gap.")
}
auxiliary_data$cell_y <- 9 - match(as.character(auxiliary_data$cell_label), cell_levels)
auxiliary_plot_data <- data.frame(
  uf = auxiliary_data$uf,
  year = auxiliary_data$year,
  cell_label = as.character(auxiliary_data$cell_label),
  eligible_package_A_code_presence_events = as.numeric(auxiliary_data$eligible_A_total),
  eligible_events_within_original_H = as.numeric(auxiliary_data$eligible_A_inside_H),
  eligible_events_outside_or_unmapped_to_H = as.numeric(auxiliary_data$eligible_A_outside_H_or_unmapped),
  eligible_laparoscopy_only_code_family_events = as.numeric(auxiliary_data$lap_only_all_eligible_A),
  eligible_comparator_family_only_code_family_events = as.numeric(auxiliary_data$open_only_all_eligible_A),
  eligible_dual_coded_events = as.numeric(auxiliary_data$both_all_eligible_A),
  eligible_laparoscopy_only_code_family_events_within_H = as.numeric(auxiliary_data$lap_only_inside_H),
  eligible_comparator_family_only_code_family_events_within_H = as.numeric(auxiliary_data$open_only_inside_H),
  eligible_dual_coded_events_within_H = as.numeric(auxiliary_data$both_inside_H),
  original_H_weight_sum = as.numeric(auxiliary_data$frozen_H_weight_sum),
  TISS_strict_standardized_fraction = as.numeric(auxiliary_data$TISS_strict_standardized_fraction),
  TISS_package_code_presence_auxiliary_fraction = as.numeric(auxiliary_data$TISS_package_A_auxiliary_standardized_fraction),
  SUS_strict_standardized_fraction = as.numeric(auxiliary_data$SUS_strict_standardized_fraction),
  strict_gap_pp = auxiliary_data$strict_gap_pp,
  package_code_presence_auxiliary_gap_pp = auxiliary_data$auxiliary_gap_pp,
  auxiliary_minus_strict_gap_pp = auxiliary_data$auxiliary_gap_change_pp,
  SUS_A = as.numeric(auxiliary_data$SUS_A),
  stringsAsFactors = FALSE
)
auxiliary_long <- bind_rows(
  data.frame(cell_label = auxiliary_data$cell_label, cell_y = auxiliary_data$cell_y - 0.11,
             estimate = "Strict standardized", gap_pp = auxiliary_data$strict_gap_pp),
  data.frame(cell_label = auxiliary_data$cell_label, cell_y = auxiliary_data$cell_y + 0.11,
             estimate = "Package-code-preserving auxiliary", gap_pp = auxiliary_data$auxiliary_gap_pp)
)
auxiliary_long$estimate <- factor(auxiliary_long$estimate,
                                  levels = c("Strict standardized", "Package-code-preserving auxiliary"))

pS5b <- ggplot(auxiliary_long, aes(x = gap_pp, y = cell_y, colour = estimate, shape = estimate)) +
  geom_segment(data = auxiliary_data,
               aes(x = strict_gap_pp, xend = auxiliary_gap_pp, y = cell_y, yend = cell_y),
               inherit.aes = FALSE, linewidth = 0.55, colour = "#A6B7B8") +
  geom_point(size = 1.9) +
  geom_text(data = auxiliary_data,
            aes(x = 101, y = cell_y,
                label = paste0(fmt2(strict_gap_pp), " / ", fmt2(auxiliary_gap_pp))),
            inherit.aes = FALSE, hjust = 0, size = 1.8, colour = "#202020") +
  scale_colour_manual(values = c("Strict standardized" = "#465B67",
                                 "Package-code-preserving auxiliary" = "#286F70"),
                      name = "Estimate") +
  scale_shape_manual(values = c("Strict standardized" = 16,
                                "Package-code-preserving auxiliary" = 18),
                     name = "Estimate") +
  scale_y_continuous(breaks = 8:1, labels = cell_levels, limits = c(0.5, 8.5),
                     expand = c(0, 0)) +
  scale_x_continuous(limits = c(0, 121), breaks = c(0, 25, 50, 75, 100),
                     labels = function(x) paste0(x, " pp")) +
  labs(title = "Fixed-H standardized gaps with package-code-preserving auxiliary",
       subtitle = "Labels give strict / auxiliary gaps (pp) using unchanged H and weights",
       x = "TISS minus SUS standardized gap (percentage points)", y = NULL) +
  theme(axis.text.y = element_text(size = 5.5), legend.position = "bottom")

figS5 <- (pS5a / pS5b) + plot_layout(heights = c(1.2, 0.9)) +
  plot_annotation(tag_levels = "a") & theme(plot.tag = element_text(size = 8, face = "bold"))

render_figure <- function(plot, stem, width_mm, height_mm, dpi = 600) {
  cat("Rendering", stem, "at", width_mm, "x", height_mm, "mm.\n")
  width_in <- width_mm / 25.4
  height_in <- height_mm / 25.4
  svg_path <- file.path(figure_dir, paste0(stem, ".svg"))
  pdf_path <- file.path(figure_dir, paste0(stem, ".pdf"))
  png_path <- file.path(figure_dir, paste0(stem, ".png"))

  svglite::svglite(svg_path, width = width_in, height = height_in, bg = "white")
  tryCatch(print(plot), finally = grDevices::dev.off())
  grDevices::cairo_pdf(pdf_path, width = width_in, height = height_in,
                       family = "Arial", onefile = TRUE, bg = "white")
  tryCatch(print(plot), finally = grDevices::dev.off())
  ragg::agg_png(png_path, width = width_in, height = height_in,
                units = "in", res = dpi, background = "white")
  tryCatch(print(plot), finally = grDevices::dev.off())
  outputs <- c(svg_path, pdf_path, png_path)
  if (any(!file.exists(outputs)) || any(file.info(outputs)$size < 1000)) {
    stop(paste("An export is missing or unexpectedly small for", stem))
  }
  invisible(outputs)
}

figure_contract <- data.frame(
  file_stem = c("Figure_1_records_and_code_composition", "Figure_2_standardized_fractions_and_gap",
                "Figure_3_gap_definitions_and_H_coverage", "Figure_4_conditional_measurement_scenarios",
                "Figure_5_urgency_and_RD_only_sensitivity", "Figure_S1_monthly_record_counts",
                "Figure_S2_age_and_sex_distribution", "Figure_S3_diagnosis_format_feasibility",
                "Figure_S4_conditional_RD6_geography_support",
                "Figure_S5_A_decomposition_and_code_preserving_auxiliary"),
  stringsAsFactors = FALSE
)

render_figure(fig1, figure_contract$file_stem[1], 183, 185)
render_figure(fig2, figure_contract$file_stem[2], 183, 145)
render_figure(fig3, figure_contract$file_stem[3], 183, 150)
render_figure(fig4, figure_contract$file_stem[4], 183, 185)
render_figure(fig5, figure_contract$file_stem[5], 183, 185)
render_figure(figS1, figure_contract$file_stem[6], 183, 185)
render_figure(figS2, figure_contract$file_stem[7], 183, 190)
render_figure(figS3, figure_contract$file_stem[8], 183, 150)
render_figure(figS4, figure_contract$file_stem[9], 183, 145)
render_figure(figS5, figure_contract$file_stem[10], 183, 200)

export_count <- length(list.files(figure_dir, pattern = "\\.(pdf|png|svg)$"))
if (export_count != 30L) {
  stop(paste("Figure export count mismatch:", export_count, "rendered files."))
}
cat("Created", nrow(figure_contract), "figure compositions and", export_count, "exports.\n")
