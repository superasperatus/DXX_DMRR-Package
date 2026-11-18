"""Collect missing trial slots, recording every attempt and bounded retry."""

from argparse import Namespace
import csv
from datetime import datetime, timezone
from pathlib import Path
import sys
import time

import requests

from .api import request_once
from .config import FIELDS, FIXED_TEMPERATURE_MODELS
from .prompts import build_prompt
from .storage import completed_trials


def collect_pair(
    session: requests.Session, args: Namespace, model: str, item: dict,
    condition: str, done: set[tuple[str, str, int]], writer: csv.DictWriter,
) -> int:
    # Build the prompt once; bound retries and stop a filtered cell without padding.
    prompt = build_prompt(item, condition)
    unresolved = 0
    blocked = False
    for trial in range(1, args.trials + 1):
        if (item["item_id"], condition, trial) in done:
            continue
        if blocked:
            unresolved += 1
            continue
        for attempt in range(args.max_attempts):
            started = time.perf_counter()
            result, status = request_once(session, model, prompt, args.temperature)
            record = {
                **dict.fromkeys(FIELDS, ""),
                "model_id": model, "parsed_response": "INVALID",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "latency_s": round(time.perf_counter() - started, 3),
                "response_coding": "canonical",
                "requested_temperature": "fixed" if model in FIXED_TEMPERATURE_MODELS else args.temperature,
                **result,
                "item_id": item["item_id"], "condition": condition, "trial_no": trial,
            }
            writer.writerow(record)
            if status == "fatal":
                raise RuntimeError(f"{model}: {record['error']}; stopping, partial data preserved")
            if status in ("valid", "blocked"):
                blocked = status == "blocked"
                break
            if attempt + 1 < args.max_attempts:
                time.sleep(min(2 ** attempt, 30))
        if status != "valid":
            unresolved += 1
            print(
                f"INCOMPLETE: {model} {item['item_id']} {condition} trial {trial}: {record['error']}",
                file=sys.stderr,
            )
    return unresolved


def collect_model(
    session: requests.Session, args: Namespace, model: str,
    items: list[dict], output: Path,
) -> int:
    # Line buffering writes each attempt immediately, including before a fatal error.
    path = output / f"raw_{model}_commercial.csv"
    done = completed_trials(path, model, {item["item_id"] for item in items}, args.trials)
    needs_header = not path.exists()
    unresolved = 0
    with path.open("a", encoding="utf-8", newline="", buffering=1) as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        if needs_header:
            writer.writeheader()
        for item in items:
            for condition in ("AB", "BA"):
                unresolved += collect_pair(session, args, model, item, condition, done, writer)
    return unresolved


