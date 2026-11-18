"""Read and analyze one self-contained collection run, never the frozen archive."""

import json
import math
from pathlib import Path
import re
import time

import pandas as pd

from . import data, metrics, outputs
from .settings import LABELS


def load_run(input_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, int, list[dict]]:
    # Use the saved pool, selected IDs, trial target, and model parameters from this run only.
    config_path = input_dir / "collection_config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(config, dict) or config.get("template_version") != 2 or config.get("pool_file") != "stimuli.csv":
        raise ValueError("Expected a version-2 collection run with its own stimuli.csv snapshot")
    if config.get("response_coding") != "canonical":
        raise ValueError("Collected runs must explicitly use canonical response coding")
    target, ids, models = config.get("trials_per_condition"), config.get("item_ids"), config.get("models")
    if not isinstance(target, int) or isinstance(target, bool) or target < 1:
        raise ValueError("The run's trials_per_condition must be a positive integer")
    if not isinstance(ids, list) or not ids or any(not isinstance(item, str) or not item.strip() for item in ids):
        raise ValueError("The run must contain a nonempty item_ids list")
    if len(set(ids)) != len(ids) or not isinstance(models, dict) or not models:
        raise ValueError("The run must have unique item IDs and a nonempty model configuration")
    pool_path = input_dir / "stimuli.csv"
    if data.sha256(pool_path) != config.get("pool_sha256"):
        raise ValueError("Collected-run stimulus snapshot checksum mismatch")
    pool = data.read_pool(pool_path)
    missing = set(ids) - set(pool["item_id"])
    if missing:
        raise ValueError(f"Selected items are missing from the saved pool: {sorted(missing)}")
    pool = pool.set_index("item_id").loc[ids].reset_index()
    entries, arms = [], set()
    for model, settings in models.items():
        if not re.fullmatch(r"[A-Za-z0-9._-]+", model):
            raise ValueError("Run model IDs must not contain path separators")
        if not isinstance(settings, dict) or not isinstance(settings.get("parameters"), dict):
            raise ValueError(f"Missing saved parameters for {model}")
        parameters = settings["parameters"]
        if "temperature" in parameters:
            temperature = parameters["temperature"]
            if (
                not isinstance(temperature, (int, float)) or isinstance(temperature, bool)
                or not math.isfinite(temperature) or not 0 <= temperature <= 2
            ):
                raise ValueError(f"Invalid saved temperature for {model}")
            arm = str(temperature)
        else:
            arm = "fixed"
        arms.add(arm)
        entries.append({
            "role": "responses", "path": [f"raw_{model}_commercial.csv"],
            "model_id": model, "experiment": "collection", "arm": arm,
            "response_coding": "canonical",
        })
    raw = data.load_responses(input_dir, {"files": entries}, pool, {"collection": arms})
    trials = pd.to_numeric(raw["trial_no"], errors="raise")
    if not trials.between(1, target).all() or trials.mod(1).ne(0).any():
        raise ValueError("Collected-run trial numbers must be integer slots within the saved target")
    valid = raw["parsed_response"].isin(LABELS)
    slots = raw.loc[valid, ["model_id", "item_id", "condition"]].assign(trial=trials[valid])
    if slots.duplicated().any():
        raise ValueError("Duplicate successful trial slots in the selected run")
    if "requested_temperature" not in raw or not raw["requested_temperature"].eq(raw["arm"]).all():
        raise ValueError("Recorded temperatures differ from the selected run's saved parameters")
    paths = [config_path, pool_path, *(input_dir.joinpath(*entry["path"]) for entry in entries)]
    checks = [
        {"file": path.name, "sha256": data.sha256(path), "bytes": path.stat().st_size}
        for path in paths
    ]
    return raw, pool, target, checks


def run(input_dir: Path, output: Path) -> tuple[Path, ...]:
    # Fresh observations get their own metrics and results, not archived paper comparisons.
    started = time.perf_counter()
    raw, pool, target, checks = load_run(input_dir)
    selected = data.select_trials(raw, target)
    items, exclusions, quality = metrics.build_item_metrics(raw, selected, {"collection": pool}, target)
    summary = metrics.summarize(items, ["model_id", "arm"])
    tables = {"model_summary.csv": summary, "data_quality.csv": quality, "excluded_items.csv": exclusions}
    outputs.write_results(output, selected, items, tables, checks)
    metadata = {
        **outputs.environment_metadata(),
        "input_directory": str(input_dir), "trials_per_condition": target,
        "raw_rows": len(raw), "selected_rows": len(selected), "complete_item_pairs": len(items),
        "runtime_seconds": round(time.perf_counter() - started, 3), "live_api_calls": 0,
    }
    (output / "logs" / "run_metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    report = f"""# Collected-run analysis

Only observations from the selected collection run are summarized below.

Input: `{input_dir}`. Target: {target} valid trials per order.
Complete model-item pairs: {len(items)}. Incomplete pairs excluded: {len(exclusions)}.

{outputs.markdown_table(summary)}

See [quality](tables/data_quality.csv) and [exclusions](tables/excluded_items.csv).
The saved stimulus snapshot defines A/B orientation. Invalid attempts are not
abstentions, and missing trials are never filled. The study's fixed 200-item
Bonferroni denominator is retained.

This analysis is separate from the archived paper reproduction. Paper
comparisons, archived robustness analyses, resampling, and archived figures
are not generated for new runs. Input file hashes are recorded in the logs.
"""
    (output / "REPLICATION_REPORT.md").write_text(report, encoding="utf-8")
    print(f"Analyzed only this run: {len(raw)} attempts, {len(items)} complete model-item pairs.")
    print(f"Excluded {len(exclusions)} incomplete pairs. API calls: 0.")
    return (output / "tables" / "model_summary.csv",)
