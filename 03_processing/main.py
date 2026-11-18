"""Analyze an explicitly selected archive or collected-run folder, without API calls."""

import argparse
import json
from pathlib import Path
import sys

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    __package__ = Path(__file__).resolve().parent.name

from .settings import ROOT


def positive_int(value: str) -> int:
    # Reject empty archive resampling runs before loading scientific libraries.
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return number


def main(argv: list[str] | None = None) -> None:
    # Metadata in the chosen folder selects the workflow; never fall back to the archive.
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Archive folder (02_output) or one collected-run folder")
    parser.add_argument("--output", type=Path, help="Results folder; defaults to 04_results for the archive or 04_results/<run-name>")
    resampling = parser.add_argument_group("archive-only resampling")
    resampling.add_argument("--bootstrap-draws", type=positive_int, default=1000)
    resampling.add_argument("--precision-draws", type=positive_int, default=300)
    resampling.add_argument("--seed", type=int, default=42)
    args = parser.parse_args(argv)
    input_dir = args.input.resolve()
    archive = (input_dir / "input_manifest.json").is_file()
    collected = (input_dir / "collection_config.json").is_file()
    if archive == collected:
        parser.error("Choose one dataset folder containing input_manifest.json OR collection_config.json, not a parent of several runs")
    if collected and (args.bootstrap_draws, args.precision_draws, args.seed) != (1000, 300, 42):
        parser.error("Resampling options apply to the archive only; collected runs produce core item/model metrics")
    output = args.output.resolve() if args.output is not None else ROOT / "04_results"
    if collected and args.output is None:
        output /= input_dir.name
    package = input_dir.parent if archive else ROOT
    protected = (
        input_dir, package / "01_collection" / "stimuli",
        package / "00_documentation" / "references", package / "02_output" / "raw",
    )
    if output in (ROOT, package) or output in input_dir.parents or any(output == path or path in output.parents for path in protected):
        parser.error("Results must be outside the input dataset and study-input directories")
    if collected and output == ROOT / "04_results":
        parser.error("Choose a per-run results folder, not the shared archive results root")
    try:
        metadata_path = output / "logs" / "run_metadata.json"
        if output.exists() and any(output.iterdir()):
            if metadata_path.is_file():
                previous = json.loads(metadata_path.read_text(encoding="utf-8")).get("input_directory")
                if previous != str(input_dir) and not (archive and previous is None and output == ROOT / "04_results"):
                    parser.error("Results belong to another dataset; choose a different --output folder")
            elif not (archive and output == ROOT / "04_results"):
                parser.error("Nonempty results folder has no dataset metadata; choose another --output folder")
        print(f"Input dataset: {input_dir}")
        print(f"Results: {output}")
        if archive:
            from .archive import run

            csv_paths = run(input_dir, output, args.bootstrap_draws, args.precision_draws, args.seed)
        else:
            from .runs import run

            csv_paths = run(input_dir, output)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print("CSV checking is your choice. Available checks:")
    checker = ROOT / "05_tests" / "check_csv.py"
    for path in csv_paths:
        expected = "" if archive else ' --expected "<your-expected.csv>"'
        print(f'  python "{checker}" --csv "{path}"{expected}')
    if archive:
        print("Table 11 has documented mismatches; checking it reports them and exits nonzero.")


if __name__ == "__main__":
    main()
