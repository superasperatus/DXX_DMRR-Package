"""Optional collection template. Defaults to a plan with no API calls or writes."""

import argparse
from pathlib import Path
import sys

# Allow direct execution as well as python -m 01_collection.main.
if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    __package__ = Path(__file__).resolve().parent.name

from .config import MODELS, ROOT
from .storage import read_items


def positive_int(value: str) -> int:
    # Reject invalid trial counts before any collection can begin.
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return number


def main(argv: list[str] | None = None) -> int:
    # Parse the plan first; load API code only after explicit live opt-in.
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Print a plan only (the default)")
    mode.add_argument("--execute", action="store_true", help="Explicitly opt into billable API calls")
    parser.add_argument("--model", default="all", choices=["all", *MODELS])
    parser.add_argument("--pool", type=Path, default=ROOT / "01_collection" / "stimuli" / "pool_final_200.csv")
    parser.add_argument("--items", type=positive_int, help="Use only the first N supplied items")
    parser.add_argument("--trials", type=positive_int, default=50)
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--max-attempts", type=positive_int, default=3)
    parser.add_argument("--output", type=Path, help="Explicit run folder; reuse it to resume. Default: a new timestamped folder.")
    args = parser.parse_args(argv)
    if not 0 <= args.temperature <= 2:
        parser.error("--temperature must be between 0 and 2")
    models = list(MODELS) if args.model == "all" else [args.model]
    items = read_items(args.pool)
    if args.items is not None:
        if args.items > len(items):
            parser.error("--items exceeds the supplied stimulus pool")
        items = items[:args.items]
    slots = len(models) * len(items) * 2 * args.trials
    print(f"Plan: {len(models)} models x {len(items)} items x 2 orders x {args.trials} trials = {slots:,} valid slots.")
    if not args.execute:
        print("DRY RUN ONLY: no network requests, credentials, or output writes.")
        print("Add your models and endpoints in 01_collection/config.py; keep keys in environment variables.")
        print("o4-mini is a fixed-temperature control: no temperature parameter will be sent.")
        return 0
    import requests

    from .api import validate_live_configuration
    from .run import collect_model
    from .storage import prepare_output

    print(f"LIVE OPT-IN: up to {slots * args.max_attempts:,} requests including retries; provider charges may apply.")
    validate_live_configuration(models)
    output = prepare_output(args, models, items)
    print(f"Run folder: {output}")
    print(f'Process this run: python "{ROOT / "03_processing" / "main.py"}" --input "{output}"')
    with requests.Session() as session:
        unresolved = sum(collect_model(session, args, model, items, output) for model in models)
    print(f"Collection ended; unresolved trial slots: {unresolved}. Partial attempts remain in {output.name}.")
    return 1 if unresolved else 0


if __name__ == "__main__":
    raise SystemExit(main())
