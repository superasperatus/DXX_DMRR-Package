"""Compute item-level metrics and equally weighted model summaries."""

from functools import lru_cache

import numpy as np
import pandas as pd
from scipy.stats import binomtest

from .settings import CONDITIONS, KEYS, LABELS, MEAN_METRICS


@lru_cache(maxsize=None)
def directional_pvalue(n_a: int, n_b: int) -> float:
    # Reuse exact tests for repeated count pairs; abstentions are not directions.
    if n_a + n_b == 0:
        return float("nan")
    return float(binomtest(n_a, n_a + n_b, p=0.5, alternative="two-sided").pvalue)


def metrics_from_counts(ab: tuple[int, int, int], ba: tuple[int, int, int]) -> dict:
    # Both (A, N, B) triples must already use the same semantic orientation.
    counts = np.asarray([ab, ba])
    if counts.shape != (2, 3) or (counts < 0).any() or not np.equal(counts, np.floor(counts)).all():
        raise ValueError("Expected two nonnegative integer (A, N, B) triples")
    totals = counts.sum(axis=1)
    if totals[0] == 0 or totals[0] != totals[1]:
        raise ValueError("AB and BA must have equal, positive trial counts")
    b_ab, b_ba = (counts[:, 0] - counts[:, 2]) / totals
    n_a, n_n, n_b = (int(value) for value in counts.sum(axis=0))
    n_total = n_a + n_n + n_b
    directional = n_a + n_b
    b_corr = float((b_ab + b_ba) / 2)
    pbi = float((b_ab - b_ba) / 2)
    rvi_incl = 1 - max(n_a, n_n, n_b) / n_total
    rvi_excl = 1 - max(n_a, n_b) / directional if directional else float("nan")
    pvalue = directional_pvalue(n_a, n_b)
    return {
        "n_A": n_a, "n_N": n_n, "n_B": n_b, "n_directional": directional,
        "B_AB": float(b_ab), "B_BA": float(b_ba),
        "Bcorr": b_corr, "abs_Bcorr": abs(b_corr),
        "PBI": pbi, "abs_PBI": abs(pbi), "AR": n_n / n_total,
        "RVI_incl": rvi_incl, "RVI_excl": rvi_excl,
        "RVI_gap": rvi_incl - rvi_excl,
        "directional_pvalue": pvalue,
        "directional_significant": bool(directional and pvalue < 0.05 / 200),
    }


def analyze_group(key: tuple, counts: pd.DataFrame, pool: pd.DataFrame, target: int) -> tuple[list, list]:
    # Explicit zero-count cells expose incomplete items instead of losing them.
    metadata = pool.set_index("item_id").sort_index()
    index = pd.MultiIndex.from_product([metadata.index, CONDITIONS], names=["item_id", "condition"])
    counts = counts.reindex(index=index, columns=["A", "N", "B"], fill_value=0)
    pairs = counts.to_numpy().reshape(len(metadata), 2, 3)
    records, exclusions = [], []
    for item, (ab, ba) in zip(metadata.itertuples(), pairs):
        identity = dict(zip(KEYS, (*key, item.Index)))
        n_ab, n_ba = int(ab.sum()), int(ba.sum())
        if n_ab != target or n_ba != target:
            exclusions.append({
                **identity, "n_AB": n_ab, "n_BA": n_ba,
                "reason": "Incomplete AB/BA pair; no imputation or synthetic replacement",
            })
            continue
        records.append({
            **identity, "source": item.source, "bias_category": item.bias_category,
            **metrics_from_counts(tuple(ab), tuple(ba)),
        })
    return records, exclusions


def build_item_metrics(
    raw: pd.DataFrame, selected: pd.DataFrame,
    pools: dict[str, pd.DataFrame], target: int = 50,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    # Group trials once, rather than rescanning the entire dataset for each model.
    counts = (
        selected.groupby(KEYS + ["condition", "choice_original"])
        .size().unstack("choice_original", fill_value=0)
        .reindex(columns=["A", "N", "B"], fill_value=0)
    )
    groups = {key: group.droplevel(KEYS[:3]) for key, group in counts.groupby(KEYS[:3])}
    empty = pd.DataFrame(columns=["A", "N", "B"])
    records, exclusions, quality = [], [], []
    for key, source in raw.groupby(KEYS[:3], sort=True):
        experiment, arm, model = key
        pool = pools[experiment]
        if not set(source["item_id"]).issubset(set(pool["item_id"])):
            raise ValueError(f"{experiment}: responses outside its documented subsample")
        group_counts = groups.get(key, empty)
        complete, incomplete = analyze_group(key, group_counts, pool, target)
        records.extend(complete)
        exclusions.extend(incomplete)
        valid = int(source["parsed_response"].isin(LABELS).sum())
        retained = int(group_counts.to_numpy().sum())
        quality.append({
            "experiment": experiment, "arm": arm, "model_id": model,
            "raw_rows": len(source), "valid_rows": valid,
            "invalid_rows": len(source) - valid,
            "trimmed_valid_rows": valid - retained, "selected_rows": retained,
            "complete_items": len(complete), "excluded_items": len(pool) - len(complete),
            "analysis_rows": len(complete) * target * 2,
        })
    if not records:
        raise ValueError("No complete model-item pairs remain")
    return (
        pd.DataFrame(records),
        pd.DataFrame(exclusions, columns=KEYS + ["n_AB", "n_BA", "reason"]),
        pd.DataFrame(quality),
    )


def summarize(items: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    # Give each complete item equal weight; omit only metric-specific undefined values.
    records = []
    for key, group in items.groupby(by, sort=True):
        values = key if isinstance(key, tuple) else (key,)
        records.append({
            **dict(zip(by, values)),
            "n_items": len(group),
            "n_directional_items": int(group["n_directional"].gt(0).sum()),
            **{name: float(group[column].mean()) for name, column in MEAN_METRICS.items()},
            "significant_items": int(group["directional_significant"].sum()),
        })
    return pd.DataFrame(records)
