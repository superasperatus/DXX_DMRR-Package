# 03 - Offline processing

A single processing entry point handles both the study archive and new collection
runs. Select the input folder explicitly. From the package root, reproduce the
archive with:

```powershell
python 03_processing\main.py --input 02_output
```

[main.py](main.py) selects the workflow from metadata in the chosen folder.
It analyzes only that dataset.

## Supplied archive

Select the folder containing `input_manifest.json`. The archive workflow in
[archive.py](archive.py):

1. Verifies [stimulus pools](../01_collection/stimuli) and
   [saved responses](../02_output/README.md), restores A/B orientation, and selects
   the first 50 valid trials per order.
2. Excludes incomplete pairs, calculates metrics, and compares with paper values.
3. Runs seeded resampling, then writes [04_results](../04_results/README.md).

No collection module is imported and no API is called.

## New collected run

Select the individual folder printed by collection, containing
`collection_config.json`, `stimuli.csv`, and response CSVs. For example, replace
`<run-folder>` with the actual name:

```powershell
python 03_processing\main.py --input "02_output\new_runs\<run-folder>"
```

[runs.py](runs.py) uses that run's saved pool, selected items, model parameters,
canonical coding, and configured number of trials. It writes core model/item
metrics, quality, exclusions, a report, and input-file hashes under
`04_results/<run-folder>`. It does not import collection code, read archived
responses, compare new data with paper values, or run the archive extensions.

Use `--output <folder>` to choose another results directory. Inputs cannot be
overwritten, and an existing results folder belonging to another dataset is
rejected. New-run processing requires version-2 collection metadata and the
saved pool snapshot.

## CSV checks

After processing, the script prints candidate CSV paths and copyable check
commands. Choose which CSV to check with [check_csv.py](../05_tests/check_csv.py).
Paper-comparison files include their expected values and rounding tolerances.
Other files require a user-supplied `--expected` CSV.

| Module | Responsibility |
| --- | --- |
| [settings.py](settings.py) | Shared model IDs, labels, and grouping keys. |
| [data.py](data.py) | Input validation, response decoding, and trial selection. |
| [metrics.py](metrics.py) | Complete-pair metrics and grouped summaries. |
| [checks.py](checks.py) | Paper comparisons and paired robustness. |
| [resampling.py](resampling.py) | Bootstrap intervals and trial subsampling. |
| [plots.py](plots.py) | One function per figure. |
| [outputs.py](outputs.py) | CSVs, the report, and execution metadata. |

Resampling options apply to the supplied archive only. Use `--help` for options;
help needs only Python's standard library.
