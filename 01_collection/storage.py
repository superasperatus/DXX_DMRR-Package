"""Validate stimuli and keep resumable new runs separate from frozen data."""

from argparse import Namespace
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

from .config import FIELDS, MODELS, ROOT, SYSTEM_PROMPT, parameters_for


def read_items(path: Path) -> list[dict[str, str]]:
    # Accept a stimulus CSV only when every required field and item ID is present.
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {
            "item_id", "source", "bias_category", "question_full",
            "option_A_text", "option_B_text", "ab_flipped",
        }
        if not required.issubset(reader.fieldnames or []):
            raise ValueError(f"Missing stimulus columns in {path.name}")
        items = list(reader)
    if not items or any(
        not isinstance(item.get(key), str) or not item[key].strip()
        for item in items for key in required
    ):
        raise ValueError("The stimulus file is empty or has missing required values")
    if len({item["item_id"] for item in items}) != len(items):
        raise ValueError("Duplicate stimulus item IDs")
    if any(item["ab_flipped"] not in ("True", "False") for item in items):
        raise ValueError("Stimulus ab_flipped values must be True or False")
    return items


def run_description(args: Namespace, models: list[str], items: list[dict[str, str]]) -> dict:
    # Resume checks compare experimental settings, never credential values.
    return {
        "template_version": 2,
        "pool_file": "stimuli.csv",
        "pool_sha256": hashlib.sha256(args.pool.read_bytes()).hexdigest(),
        "item_ids": [item["item_id"] for item in items],
        "trials_per_condition": args.trials,
        "system_prompt": SYSTEM_PROMPT, "response_coding": "canonical",
        "models": {
            model: {
                "endpoint": MODELS[model]["endpoint"],
                "key_env": MODELS[model]["key_env"], "auth": MODELS[model]["auth"],
                "parameters": parameters_for(model, args.temperature),
            }
            for model in models
        },
    }


def prepare_output(args: Namespace, models: list[str], items: list[dict[str, str]]) -> Path:
    # Keep new observations outside the frozen inputs and reject mixed runs.
    output = args.output.resolve() if args.output is not None else None
    protected = (
        (ROOT / "02_output" / "raw").resolve(),
        (ROOT / "01_collection" / "stimuli").resolve(),
        (ROOT / "00_documentation" / "references").resolve(),
    )
    if output is not None and (output == ROOT or any(output == path or path in output.parents for path in protected)):
        raise ValueError("Choose a new-run directory, not the package root or a study-input directory")
    description = run_description(args, models, items)
    if output is None:
        parent = ROOT / "02_output" / "new_runs"
        parent.mkdir(parents=True, exist_ok=True)
        prefix = datetime.now(timezone.utc).strftime("run_%Y%m%dT%H%M%SZ_")
        output = Path(tempfile.mkdtemp(prefix=prefix, dir=parent))
    manifest = output / "collection_config.json"
    snapshot = output / "stimuli.csv"
    if manifest.exists():
        if json.loads(manifest.read_text(encoding="utf-8")) != description:
            raise ValueError("Existing run configuration differs; choose another --output directory")
        if not snapshot.is_file() or hashlib.sha256(snapshot.read_bytes()).hexdigest() != description["pool_sha256"]:
            raise ValueError("Saved stimulus snapshot is missing or changed; refusing to resume")
    elif output.exists() and any(output.iterdir()):
        raise ValueError("Nonempty output directory has no run manifest; choose another directory")
    output.mkdir(parents=True, exist_ok=True)
    if not manifest.exists():
        shutil.copyfile(args.pool, snapshot)
        manifest.write_text(json.dumps(description, indent=2) + "\n", encoding="utf-8")
    return output


def completed_trials(path: Path, model: str, item_ids: set[str], target: int) -> set[tuple[str, str, int]]:
    # Retry only missing successful slots; duplicate successes signal damaged data.
    done = set()
    if not path.exists():
        return done
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != FIELDS:
            raise ValueError(f"Incompatible existing output schema: {path.name}")
        for row in reader:
            key = (row["item_id"], row["condition"], int(row["trial_no"]))
            if (
                row["model_id"] != model or key[0] not in item_ids
                or key[1] not in ("AB", "BA") or not 1 <= key[2] <= target
                or row["response_coding"] != "canonical"
                or row["parsed_response"] not in ("A", "B", "N", "INVALID")
            ):
                raise ValueError(f"Incompatible existing trial in {path.name}")
            if row["parsed_response"] in ("A", "B", "N"):
                if key in done:
                    raise ValueError(f"Duplicate valid trial in {path.name}: {key}")
                done.add(key)
    return done
