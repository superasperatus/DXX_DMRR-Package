"""Shared model IDs, response labels, and archive grouping keys."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODELS = (
    "gpt-4.1", "gpt-4.1-mini", "gpt-4o", "o4-mini",
    "Llama-3.3-70B-Instruct", "Phi-4",
)
LABELS = {"A", "B", "N"}
CONDITIONS = ("AB", "BA")
KEYS = ["experiment", "arm", "model_id", "item_id"]
MEAN_METRICS = {
    "mean_abs_Bcorr": "abs_Bcorr",
    "mean_AR": "AR",
    "mean_RVI_incl": "RVI_incl",
    "mean_RVI_excl": "RVI_excl",
    "mean_RVI_gap": "RVI_gap",
    "mean_abs_PBI": "abs_PBI",
}
EXPECTED_ARMS = {
    "main": {"0.7"},
    "prompt": {"V1", "V2", "V3"},
    "temperature_original": {"1.0"},
    "temperature_v2": {"0.2", "0.7", "1.0", "fixed"},
}
