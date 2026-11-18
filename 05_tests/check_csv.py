"""Check a chosen paper-comparison CSV, or compare a chosen CSV with an expected CSV."""

import argparse
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    # There is no default results file: the caller explicitly chooses what to test.
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, required=True, help="Generated CSV to check")
    parser.add_argument("--expected", type=Path, help="Expected CSV for an exact row/column/value comparison")
    args = parser.parse_args(argv)
    import numpy as np
    import pandas as pd

    try:
        actual = pd.read_csv(args.csv, keep_default_na=False)
        if actual.empty:
            raise ValueError("The selected CSV has no data rows")
        print(f"Checking: {args.csv.resolve()}")
        if args.expected is not None:
            expected = pd.read_csv(args.expected, keep_default_na=False)
            try:
                pd.testing.assert_frame_equal(actual, expected, check_dtype=False, check_exact=True)
            except AssertionError as error:
                print(f"FAIL: differs from {args.expected.resolve()}\n{error}")
                return 1
            print(f"PASS: matches {args.expected.resolve()}")
            return 0
        required = {"model_id", "metric", "reproduced", "paper", "rounding_tolerance", "matches_paper_precision"}
        if not required.issubset(actual.columns):
            raise ValueError("For a non-comparison CSV, supply --expected <expected.csv>; no reference is chosen automatically")
        if actual.duplicated(["model_id", "metric"]).any():
            raise ValueError("Comparison CSV contains duplicate model/metric rows")
        reproduced = pd.to_numeric(actual["reproduced"], errors="raise")
        paper = pd.to_numeric(actual["paper"], errors="raise")
        tolerance = pd.to_numeric(actual["rounding_tolerance"], errors="raise")
        if not np.isfinite(tolerance).all() or tolerance.lt(0).any():
            raise ValueError("Comparison tolerances must be finite and nonnegative")
        matches = np.isfinite(reproduced) & np.isfinite(paper) & (reproduced - paper).abs().le(tolerance + 1e-12)
        reported = actual["matches_paper_precision"].map({True: True, False: False, "True": True, "False": False})
        if reported.isna().any() or reported.ne(matches).any():
            raise ValueError("Stored match flags disagree with the comparison values")
        print(f"{'PASS' if matches.all() else 'FAIL'}: {int(matches.sum())}/{len(matches)} cells match the paper.")
        return 0 if matches.all() else 1
    except (OSError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    raise SystemExit(main())
