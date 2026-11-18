"""Compare computed results with paper references and paired archive arms."""

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from .settings import MODELS


def compare_reference(actual: pd.DataFrame, reference: pd.DataFrame, metrics: dict[str, int]) -> pd.DataFrame:
    # Compare computed values only after analysis, allowing the paper's rounding.
    if actual["model_id"].duplicated().any() or reference["model_id"].duplicated().any():
        raise ValueError("Reference comparison requires unique model rows")
    if set(actual["model_id"]) != set(reference["model_id"]):
        raise ValueError("Actual and reference model sets differ")
    indexed = actual.set_index("model_id")
    records = []
    for row in reference.to_dict("records"):
        for metric, decimals in metrics.items():
            value = float(indexed.loc[row["model_id"], metric])
            target = float(row[metric])
            tolerance = 0.0 if decimals == 0 else 0.5 * 10 ** -decimals
            records.append({
                "model_id": row["model_id"], "metric": metric,
                "reproduced": value, "paper": target, "difference": value - target,
                "rounding_tolerance": tolerance,
                "matches_paper_precision": bool(
                    np.isfinite(value) and abs(value - target) <= tolerance + 1e-12
                ),
            })
    return pd.DataFrame(records)


def rank_stats(left: pd.Series, right: pd.Series) -> dict:
    # Compare the same items; a constant profile has no defined rank correlation.
    shared = pd.concat([left.rename("left"), right.rename("right")], axis=1).dropna()
    if len(shared) < 3 or shared["left"].nunique() < 2 or shared["right"].nunique() < 2:
        return {
            "n_paired_items": len(shared), "spearman_r": float("nan"),
            "spearman_pvalue": float("nan"), "rank_status": "insufficient variation",
        }
    result = spearmanr(shared["left"], shared["right"])
    return {
        "n_paired_items": len(shared), "spearman_r": float(result.statistic),
        "spearman_pvalue": float(result.pvalue), "rank_status": "estimated",
    }


def paired_robustness(items: pd.DataFrame, experiment: str, comparisons: tuple) -> pd.DataFrame:
    # Pair item scores across prompt or temperature arms, separately for each model.
    records = []
    subset = items.loc[items["experiment"].eq(experiment)]
    for model in MODELS:
        arms = {
            arm: group.set_index("item_id")["abs_Bcorr"]
            for arm, group in subset.loc[subset["model_id"].eq(model)].groupby("arm")
        }
        for left, right in comparisons:
            if left in arms and right in arms:
                records.append({
                    "model_id": model, "left_arm": left, "right_arm": right,
                    **rank_stats(arms[left], arms[right]),
                })
    return pd.DataFrame(records)


def original_temperature_table(items: pd.DataFrame, temperature_pool: pd.DataFrame) -> pd.DataFrame:
    # Use the shared complete-item intersection for both temperature means.
    records = []
    expected_ids = set(temperature_pool["item_id"])
    for model in MODELS:
        model_items = items.loc[items["model_id"].eq(model)]
        base = model_items.loc[
            model_items["experiment"].eq("main") & model_items["item_id"].isin(expected_ids)
        ].set_index("item_id")["abs_Bcorr"]
        hot = model_items.loc[
            model_items["experiment"].eq("temperature_original")
        ].set_index("item_id")["abs_Bcorr"]
        shared = sorted(set(base.index) & set(hot.index))
        if not shared:
            raise ValueError(f"No paired original-temperature items for {model}")
        mean_base, mean_hot = float(base.loc[shared].mean()), float(hot.loc[shared].mean())
        records.append({
            "model_id": model,
            "mean_abs_Bcorr_07": mean_base, "mean_abs_Bcorr_10": mean_hot,
            "shift": mean_hot - mean_base,
            **rank_stats(base, hot),
            "interpretation": (
                "Unverified nominal contrast; o4-mini does not support requested temperature"
                if model == "o4-mini" else "Paired complete archived items"
            ),
        })
    return pd.DataFrame(records)
