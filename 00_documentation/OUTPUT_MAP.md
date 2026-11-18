# Input-code-output map

The workflow below links each result to its inputs and analysis code.
Run [03_processing/main.py](../03_processing/main.py) with `--input 02_output`
to regenerate the archive outputs. This workflow does not import the optional
[collector](../01_collection/main.py).

## Workflow

```text
01_collection/stimuli + 02_output: manifest and archives
            |
       data.py: verify_inputs / load_pools / load_responses
            |
       data.py: restore_choices / select_trials
            |
       metrics.py: build_item_metrics / metrics_from_counts
            |
       archive.py: summaries + checks.py + resampling.py
            |
       04_results: CSVs, figures, report, audit
```

## Tables

Paths below are relative to the package root.
These are archive outputs. Selecting a collected-run folder instead invokes
[runs.py](../03_processing/runs.py) and writes `model_summary.csv`, quality,
exclusions, derived data, and a report under that run's results folder. The
collector's pool snapshot and run configuration supply the new-run design.

Paper reference inputs live in [documentation/references](references), not in
the collection-output directory. CSV checks are explicit user choices through
[check_csv.py](../05_tests/check_csv.py).

| Output | Main generating function | Interpretation |
| --- | --- | --- |
| [table6_commercial.csv](../04_results/tables/table6_commercial.csv) | [summarize](../03_processing/metrics.py) | Six commercial rows corresponding to paper Table 6, with additional RVI means and directional-item counts. |
| [table6_comparison.csv](../04_results/tables/table6_comparison.csv) | [compare_reference](../03_processing/checks.py) | All 36 numerical cells checked against displayed Table 6 values. |
| [table11_temperature.csv](../04_results/tables/table11_temperature.csv) | [original_temperature_table](../03_processing/checks.py) | Complete-pair original nominal temperature contrast on the fixed 40-item subset. |
| [table11_comparison.csv](../04_results/tables/table11_comparison.csv) | [compare_reference](../03_processing/checks.py) | All 24 commercial Table 11 reference cells, including differences from the manuscript. |
| [by_category.csv](../04_results/tables/by_category.csv) | [summarize](../03_processing/metrics.py) | Commercial metrics by model and social-group category; not a verbatim reconstruction of all category tables. |
| [prompt_robustness.csv](../04_results/tables/prompt_robustness.csv) | [summarize](../03_processing/metrics.py) | Main metrics for each prompt variant on the fixed 20-item subset. |
| [prompt_rank_correlations.csv](../04_results/tables/prompt_rank_correlations.csv) | [paired_robustness](../03_processing/checks.py) | Within-model item-rank correlations between wording variants. |
| [temperature_v2.csv](../04_results/tables/temperature_v2.csv) | [summarize](../03_processing/metrics.py) | Separate later temperature-v2 data, including the fixed o4-mini control. |
| [temperature_v2_rank_correlations.csv](../04_results/tables/temperature_v2_rank_correlations.csv) | [paired_robustness](../03_processing/checks.py) | Comparisons among genuinely varied requested temperatures; excludes the fixed control. |
| [bootstrap_intervals.csv](../04_results/tables/bootstrap_intervals.csv) | [bootstrap_intervals](../03_processing/resampling.py) | Seeded item-bootstrap intervals, included as an additional analysis rather than a reproduction of Supplementary Table T10. |
| [trial_precision.csv](../04_results/tables/trial_precision.csv) | [trial_precision](../03_processing/resampling.py) | Error after retaining fewer archived trials; reference is the realized 50-per-condition result. |
| [data_quality.csv](../04_results/tables/data_quality.csv) | [build_item_metrics](../03_processing/metrics.py) | Raw/valid/trimmed/analyzed counts by experiment, arm, and model. |
| [excluded_items.csv](../04_results/tables/excluded_items.csv) | [build_item_metrics](../03_processing/metrics.py) | Every incomplete item excluded from paired calculations. |

## Figures

Each figure has its own function in [plots.py](../03_processing/plots.py).
These figures summarize the calculated metrics. Their layout is
specific to this package rather than a reproduction of the article's figures.

| Output | Content |
| --- | --- |
| [commercial_overview.png](../04_results/figures/commercial_overview.png) | Main directional consistency, abstention, and position effect. |
| [bias_volatility.png](../04_results/figures/bias_volatility.png) | Shared-count directional-consistency/volatility geometry, colored by abstention. |
| [trial_precision.png](../04_results/figures/trial_precision.png) | Sampling error from using 5, 10, or 25 trials per order. |
| [temperature_v2.png](../04_results/figures/temperature_v2.png) | Later requested-temperature profiles for the five configurable models. |

## Derived data and execution records

- `04_results/derived/selected_valid_trials.csv`: retained trials with source-row and
  orientation traceability, before complete-item exclusion.
- `04_results/derived/item_metrics.csv`: all complete item-level metric rows.
- `04_results/logs/verified_inputs.csv`: hashes checked on this execution.
- `04_results/logs/run_metadata.json`: actual Python/library versions, runtime,
  resampling settings, and reference-match counts.
- [REPLICATION_REPORT.md](../04_results/REPLICATION_REPORT.md): readable generated
  summary and limitations.

Intermediate data and logs are intentionally Git-ignored; processing recreates
them from included raw evidence.

## Not reproduced

The local-model rows and local-versus-commercial inferential comparisons are
not generated. Neither are screening/inter-rater statistics, MMLU associations,
or supplementary accuracy/stereotype convergence results requiring unavailable
labels. The bootstrap and trial-precision summaries are additional analyses.
Together, these boundaries define the commercial-archive scope of this package.
