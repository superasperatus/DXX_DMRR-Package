# 05 - Tests

Automated tests check the analysis rules and the collection-to-analysis workflow.
Run them from the package root:

```powershell
python -m unittest discover -s 05_tests -v
```

Tests cover A/B decoding, complete-pair selection, metric edge cases, checksums,
explicit dataset selection, a small synthetic collection-to-processing run,
collection output protection, retries, and resume checks.
Provider calls are mocked; no API account or live collection is required.

The unit tests run independently of pre-generated result CSVs. To check a
specific generated result against reference values, use the commands below.

## Choose a CSV to check

After archive processing, choose the comparison to test:

```powershell
python 05_tests\check_csv.py --csv 04_results\tables\table6_comparison.csv
python 05_tests\check_csv.py --csv 04_results\tables\table11_comparison.csv
```

[check_csv.py](check_csv.py) recalculates matches using each comparison row's
paper value and rounding tolerance. Table 11 has known disagreements, so that
choice reports the differences and exits with status 1. This is the expected
result for the archived temperature comparison, not a processing failure.

For a collected-run summary or another result CSV, choose an expected CSV too:

```powershell
python 05_tests\check_csv.py --csv "path\to\actual.csv" --expected "path\to\expected.csv"
```

Replace both example paths. Expected-file comparison checks exact values,
column order, and row order. Status 0 means a match, 1 means a difference, and
2 means invalid input. Processing prints suggested commands, but never chooses
an expected file for new observations.
