# 04 - Processed results

The generated tables, figures, and report are included for inspection before
running the code. Regenerate them with
[03_processing/main.py](../03_processing/main.py) rather than editing them by hand.

From the package root, `python 03_processing\main.py --input 02_output`
recreates the archive outputs below. Selecting an individual collection run
instead creates a separate `04_results/<run-folder>` containing its core
metrics, derived data, quality/exclusions, and report. Archive files are not
substituted for the selected run.

- [REPLICATION_REPORT.md](REPLICATION_REPORT.md): results and limitations.
- [tables](tables): commercial results, paper comparisons, and robustness.
- [figures](figures): four visualizations from the calculated metrics.
- `derived`: selected valid trials and complete item metrics.
- `logs`: input-hash audit, environment versions, and run metadata.

Derived data and logs are Git-ignored and recreated from the selected inputs.
Processing prints commands for checking a result CSV of your choice.
Next: [05_tests](../05_tests/README.md).
