"""Verify archived inputs, restore answer orientation, and select valid trials."""

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .settings import CONDITIONS, EXPECTED_ARMS, KEYS, LABELS


def sha256(path: Path) -> str:
    # Hash in chunks so checking an input does not load it all into memory.
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def verify_inputs(root: Path, manifest_path: Path | None = None) -> tuple[dict, list[dict]]:
    # Stop before analysis if any archived input differs from its manifest.
    path = manifest_path if manifest_path is not None else root / "02_output" / "input_manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    checks = []
    for entry in manifest["files"]:
        parts = entry["path"]
        if not parts or any(part in ("", ".", "..") or "/" in part or "\\" in part for part in parts):
            raise ValueError(f"Unsafe manifest path: {parts}")
        path = root.joinpath(*parts)
        actual = sha256(path)
        if actual != entry["sha256"]:
            raise ValueError(f"Input checksum mismatch: {path.name}. Restore the archived input.")
        checks.append({"file": "/".join(parts), "sha256": actual, "bytes": path.stat().st_size})
    return manifest, checks


def read_pool(path: Path) -> pd.DataFrame:
    # Preserve text and convert only the documented A/B-randomization flag.
    pool = pd.read_csv(path, dtype=str, keep_default_na=False)
    required = {
        "item_id", "source", "bias_category", "question_full",
        "option_A_text", "option_B_text", "ab_flipped",
    }
    if not required.issubset(pool.columns):
        raise ValueError(f"Missing stimulus columns in {path.name}: {sorted(required - set(pool.columns))}")
    if pool.empty or pool["item_id"].eq("").any() or pool["item_id"].duplicated().any():
        raise ValueError(f"Empty or duplicate item IDs in {path.name}")
    if not pool["ab_flipped"].isin(["True", "False"]).all():
        raise ValueError(f"Unexpected ab_flipped coding in {path.name}")
    pool["ab_flipped"] = pool["ab_flipped"].eq("True")
    return pool


def load_pools(root: Path) -> dict[str, pd.DataFrame]:
    # Check that robustness subsets contain the same metadata as the main pool.
    directory = root / "01_collection" / "stimuli"
    main = read_pool(directory / "pool_final_200.csv")
    prompt = read_pool(directory / "robustness_prompt_subsample.csv")
    temperature = read_pool(directory / "robustness_temp10_subsample.csv")
    if (len(main), len(prompt), len(temperature)) != (200, 20, 40):
        raise ValueError("Unexpected archived stimulus-pool sizes")
    for subset in (prompt, temperature):
        original = main.set_index("item_id").loc[subset["item_id"]].reset_index()
        if not original.equals(subset.reset_index(drop=True)):
            raise ValueError("Subsample metadata differ from the main stimulus pool")
    return {
        "main": main, "prompt": prompt,
        "temperature_original": temperature, "temperature_v2": temperature,
    }


def restore_choices(frame: pd.DataFrame, pool: pd.DataFrame) -> pd.DataFrame:
    # Undo legacy BA storage once, then undo the separate original-item flip.
    result = frame.copy()
    unknown = set(result["parsed_response"]) - LABELS - {"INVALID"}
    if unknown:
        raise ValueError(f"Unknown parsed responses: {sorted(unknown)}")
    if not result["response_coding"].isin(["legacy_position", "canonical"]).all():
        raise ValueError("Unknown response_coding; refusing to guess the A/B orientation")
    if not result["condition"].isin(CONDITIONS).all():
        raise ValueError("Unknown order condition")
    metadata = pool.set_index("item_id")
    missing = set(result["item_id"]) - set(metadata.index)
    if missing:
        raise ValueError(f"Responses refer to unknown items: {sorted(missing)}")
    result["choice_pool"] = result["parsed_response"]
    swap = (
        result["response_coding"].eq("legacy_position")
        & result["condition"].eq("BA")
        & result["parsed_response"].isin(["A", "B"])
    )
    result.loc[swap, "choice_pool"] = result.loc[swap, "parsed_response"].map({"A": "B", "B": "A"})
    result["choice_original"] = result["choice_pool"]
    swap_original = result["item_id"].map(metadata["ab_flipped"]) & result["choice_pool"].isin(["A", "B"])
    result.loc[swap_original, "choice_original"] = result.loc[swap_original, "choice_pool"].map(
        {"A": "B", "B": "A"}
    )
    return result


def load_responses(
    root: Path, manifest: dict, pool: pd.DataFrame,
    expected_arms: dict[str, set[str]] | None = None,
) -> pd.DataFrame:
    # Read attempts without reparsing answers or changing the archived files.
    required = {
        "item_id", "model_id", "condition", "trial_no", "raw_response",
        "parsed_response", "timestamp", "error",
    }
    allowed_arms = EXPECTED_ARMS if expected_arms is None else expected_arms
    frames = []
    for entry in manifest["files"]:
        if entry["role"] != "responses":
            continue
        path = root.joinpath(*entry["path"])
        frame = pd.read_csv(path, dtype=str, keep_default_na=False)
        if not required.issubset(frame.columns):
            raise ValueError(f"Missing response columns in {path.name}")
        if frame.empty or set(frame["model_id"]) != {entry["model_id"]}:
            raise ValueError(f"Unexpected model ID or empty response file: {path.name}")
        frame["experiment"] = entry["experiment"]
        if entry.get("arm_column"):
            if entry["arm_column"] not in frame:
                raise ValueError(f"Missing {entry['arm_column']} in {path.name}")
            frame["arm"] = frame[entry["arm_column"]]
        else:
            frame["arm"] = entry["arm"]
        if entry["experiment"] not in allowed_arms or not set(frame["arm"]).issubset(allowed_arms[entry["experiment"]]):
            raise ValueError(f"Unexpected experiment arm in {path.name}")
        if entry["response_coding"] == "canonical" and "response_coding" not in frame:
            raise ValueError(f"Missing canonical response coding in {path.name}")
        if "response_coding" in frame and not frame["response_coding"].eq(entry["response_coding"]).all():
            raise ValueError(f"Inconsistent response coding in {path.name}")
        frame["response_coding"] = entry["response_coding"]
        frame["source_file"] = path.name
        frame["source_row"] = np.arange(1, len(frame) + 1)
        if frame["timestamp"].eq("").any():
            raise ValueError(f"Missing timestamps in {path.name}")
        pd.to_datetime(frame["timestamp"], format="ISO8601", errors="raise")
        frames.append(frame)
    if not frames:
        raise ValueError("The manifest contains no response files")
    return restore_choices(pd.concat(frames, ignore_index=True), pool)


def select_trials(raw: pd.DataFrame, target: int = 50) -> pd.DataFrame:
    # Keep the first valid attempts chronologically; never fill missing trials.
    if target < 1:
        raise ValueError("target must be positive")
    valid = raw.loc[raw["parsed_response"].isin(LABELS)].copy()
    if valid["error"].ne("").any():
        raise ValueError("A supposedly valid response has an error; resolve the inconsistency")
    valid = valid.sort_values(["timestamp", "source_file", "source_row"], kind="stable")
    cells = KEYS + ["condition"]
    valid = valid.groupby(cells, sort=False).head(target).copy()
    valid["analysis_trial_no"] = valid.groupby(cells, sort=False).cumcount() + 1
    return valid
