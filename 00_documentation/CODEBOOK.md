# Data dictionary

This codebook describes the input data and generated variables. Data files are UTF-8
CSVs with headers or JSON. Empty fields in generated numeric CSVs represent
undefined or missing values, not zeros. The archived CSVs preserve the original
bytes, including quoted multiline text; use a CSV reader to count observations.

## Stimuli

Location: `01_collection/stimuli`. Unit: one benchmark-derived item.

| Column | Meaning |
| --- | --- |
| `item_id` | Study item identifier such as `ITEM_001`; stable join key. |
| `source` | Benchmark-source abbreviation exactly as stored in the supplied pool. |
| `bias_category` | One of the pool's eight social-group categories. |
| `question_full` | Complete scenario and question passed to the model. |
| `option_A_text` | Text associated with the pool's semantic A label. |
| `option_B_text` | Text associated with the pool's semantic B label. |
| `ab_flipped` | Literal `True`/`False`: whether initial pool construction exchanged the original alternatives. Not the AB/BA presentation condition. |

The main pool has 200 items. The two fixed subsamples contain 20 prompt-
robustness and 40 temperature-robustness items. The pipeline checks their
metadata against the main pool. Correct-answer and stereotype-consistent
labels are **not present** and must not be inferred from `ab_flipped`.

## Archived response attempts

Locations: `02_output/raw/main`, `prompt`, `temperature_original`, `temperature_v2`.
Unit: one archived request/response attempt. A valid trial slot can have
multiple attempted rows; historical trial numbers are not assumed unique.

| Column | Meaning / values |
| --- | --- |
| `item_id` | Foreign key to the relevant stimulus pool. |
| `model_id` | One of the six commercial-model identifiers. |
| `condition` | `AB`: A shown first; `BA`: B shown first. Semantic letters remain attached to their alternatives. |
| `trial_no` | Original collector's trial-slot number; retries/parallel execution can repeat numbers. Not the analysis selection key. |
| `raw_response` | Original recorded answer, empty output, or error text; preserve verbatim. |
| `parsed_response` | `A`, `B`, `N`, or `INVALID`. In these legacy files BA directional labels were exchanged during collection. |
| `prompt_tokens` | Provider-reported prompt-token count as archived; historical missing/error values may be zero. |
| `completion_tokens` | Provider-reported completion-token count as archived; not a verified billing amount. |
| `latency_s` | Recorded request duration in seconds. |
| `timestamp` | ISO timestamp from the legacy collector's local clock; no verified timezone. Used only for within-cell chronological selection. |
| `error` | Error description, or empty string for a valid observation. |
| `prompt_variant` | Prompt files only: `V1` baseline, `V2` formal, `V3` minimal. |
| `temperature` | V2 files only: requested `0.2`, `0.7`, `1.0`, or `fixed`. Requested does not prove provider-effective decoding. |

`N` means the model gave the substantive abstention response "Cannot be
determined"; it is not a request error or an unparseable answer.

## Source notes and manifest

`02_output/raw/notes` contains the supplied main and robustness exclusion notes.

| Column | Meaning |
| --- | --- |
| `model_id`, `item_id`, `condition` | Affected cell. |
| `valid_count` | Historical valid responses recorded for that incomplete cell. |
| `reason` | Historical exclusion explanation, such as content filtering. |
| `check` | Robustness notes only: which check the note concerns. |

The notes record historical exclusions. The analysis determines completeness
directly from the response rows rather than relying on these notes.

`02_output/input_manifest.json` lists each included CSV with:

- `path`: portable list of path components within this package.
- `source_path`: original workspace-relative components for copied inputs.
- `role`: `responses`, `stimuli`, `notes`, or numerical `reference`.
- `sha256`, `bytes`, `rows`: immutable-source audit.
- For responses: `experiment`, `model_id`, `response_coding`, and either
  a fixed `arm` or the original `arm_column`.
- For references: a source description instead of an original data path.

## Selected trials

Generated file: `04_results/derived/selected_valid_trials.csv`.
Unit: one selected valid archived response; partial items are still present
here and are excluded at the subsequent paired-metric stage.

It preserves original response columns and adds:

| Column | Meaning |
| --- | --- |
| `experiment` | `main`, `prompt`, `temperature_original`, or `temperature_v2`. |
| `arm` | Experiment-specific nominal temperature or prompt-variant label. |
| `response_coding` | `legacy_position` for the supplied archive. |
| `source_file` | Original response filename. |
| `source_row` | One-based original CSV data-record number, excluding the header; stable tie-breaker. |
| `choice_pool` | Archived BA storage exchange undone once. |
| `choice_original` | Pool's original A/B randomization also undone where `ab_flipped=True`. |
| `analysis_trial_no` | Chronological retained valid trial, 1--50 within experiment/arm/model/item/condition. |

Columns specific to other source experiments are empty where inapplicable.

## Item metrics

Count examples below describe the supplied 50-trial archive. For a selected
collected run, counts and score denominators use `trials_per_condition` from
that run's configuration instead.

Generated file: `04_results/derived/item_metrics.csv`.
Unit: one **complete** experiment/arm/model/item pair, with 50 observations per
order. `experiment`, `arm`, `model_id`, and `item_id` jointly identify a row.
`source` and `bias_category` are joined from the stimulus metadata.

| Column | Meaning / range |
| --- | --- |
| `n_A`, `n_N`, `n_B` | Counts in original-item orientation pooled across the two orders; sum to 100. |
| `n_directional` | `n_A+n_B`; 0--100. |
| `B_AB`, `B_BA` | Condition-specific `(A-B)/50`, already in the same original-item orientation; -1--1. |
| `Bcorr` | Mean of the two condition scores; -1--1. Positive favors original A, not necessarily a stereotype. |
| `abs_Bcorr` | Absolute corrected directional consistency; 0--1. |
| `PBI` | Half the difference of the two condition scores; -1--1. |
| `abs_PBI` | Absolute order-associated position index; 0--1. |
| `AR` | Pooled abstention proportion; 0--1. |
| `RVI_incl` | One minus the largest pooled A/N/B proportion; 0--2/3. |
| `RVI_excl` | One minus the largest directional A/B proportion; 0--1/2; missing if all abstain. |
| `RVI_gap` | Inclusive minus exclusive RVI; can be negative; missing if all abstain. |
| `directional_pvalue` | Two-sided exact binomial p-value for A versus B among directional responses; missing if none. |
| `directional_significant` | Boolean: defined p-value strictly below 0.00025. |

## Generated summary tables

See [the output map](OUTPUT_MAP.md) for all filenames.

- `n_items`: available complete items; includes all-abstention items.
- `n_directional_items`: items with at least one A or B response.
- `mean_*`: unweighted mean of the named item metric, excluding only undefined
  values for that metric.
- `significant_items`: count of `directional_significant=True`.
- `n_paired_items`: intersection used for a two-arm comparison.
- `spearman_r`, `spearman_pvalue`: item-level rank-correlation estimate and
  two-sided p-value; missing for insufficient variation.
- `rank_status`: `estimated` or `insufficient variation`.
- `left_arm`, `right_arm`: compared prompt/temperature arms.
- `mean_abs_Bcorr_07`, `mean_abs_Bcorr_10`, `shift`: means on the same paired
  original-temperature items and hot-minus-baseline difference.
- `interpretation`: flag for the unverified o4-mini nominal contrast.

Comparison tables contain `model_id`, `metric`, `reproduced`, transcribed
`paper`, `difference` (reproduced minus paper), `rounding_tolerance`, and
`matches_paper_precision`. The reference CSVs contain the displayed paper
numbers under their corresponding metric names.

Bootstrap tables add `metric`, `n_defined_items`, `estimate`, `ci_low`,
`ci_high`, `bootstrap_draws`, and `seed`. Intervals are percentile intervals
over item-resampled means.

Precision tables add `trials_per_condition`, `mean_absolute_error`,
`mae_draw_p025`, `mae_draw_p975`, `root_mean_squared_error`, `resample_draws`,
and `seed`, all measured against the realized full-trial `abs_Bcorr`.

## Data-quality tables

`data_quality.csv`: one experiment/arm/model row.

| Column | Meaning |
| --- | --- |
| `raw_rows` | All archived attempts. |
| `valid_rows`, `invalid_rows` | Counts before chronological trimming. |
| `trimmed_valid_rows` | Excess valid attempts beyond the first 50 per cell. |
| `selected_rows` | Valid retained responses, including incomplete item pairs. |
| `complete_items`, `excluded_items` | Complete/incomplete item counts within the applicable fixed pool. |
| `analysis_rows` | Responses contributing to paired metrics: `complete_items*100` for the archive, or `complete_items*2*trials_per_condition` for a new run. |

`excluded_items.csv` identifies each omitted experiment/arm/model/item, its
`n_AB`, `n_BA`, and explicit `reason`. Incomplete observations remain traceable
through selected trials and immutable raw records.

## Optional collection outputs

The optional collector creates a separate dataset for each new run. To analyze
one, select its individual folder with `--input`.
Each run contains version-2 `collection_config.json`, a `stimuli.csv` snapshot
whose SHA-256 must match the configuration, and response CSVs. The configuration
lists the chosen item IDs, trial target, models, and provider parameters.
The response schema additionally includes:

| Column | Meaning |
| --- | --- |
| `response_coding` | Always `canonical`: model's semantic letter is not exchanged in BA. |
| `requested_temperature` | Requested numeric value or `fixed`; not an inferred provider setting. |
| `provider_model` | Provider-returned model label, if available. |
| `provider_response_id` | Provider-returned response identifier, if available. |
| `system_fingerprint` | Optional provider fingerprint, otherwise blank. |
| `finish_reason` | Provider's termination/filtering reason, if available. |

New token counts remain blank if absent rather than claiming zero usage.
New timestamps are UTC with an explicit offset. Every attempt is flushed to
CSV; missing successful slots can be resumed under an identical saved run
configuration.

Fresh results use `model_summary.csv`, `data_quality.csv`, and
`excluded_items.csv`, plus derived trials/item metrics. Their metadata identifies
the selected input folder, and their logs record the input files' hashes.
Paper comparisons and archive-resampling outputs are only generated when
processing the included archive.
