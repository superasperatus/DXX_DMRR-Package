"""Estimate item-bootstrap intervals and repeated-trial subsampling error."""

import numpy as np
import pandas as pd

from .settings import CONDITIONS, MEAN_METRICS, MODELS


def bootstrap_intervals(items: pd.DataFrame, draws: int, seed: int) -> pd.DataFrame:
    # Resample defined item values, not individual response attempts.
    rng = np.random.default_rng(seed)
    records = []
    for model in MODELS:
        group = items.loc[items["model_id"].eq(model)]
        for metric, column in MEAN_METRICS.items():
            values = group[column].dropna().to_numpy(dtype=float)
            if len(values) == 0:
                raise ValueError(f"No defined observations for {model}: {column}")
            sampled = values[rng.integers(0, len(values), size=(draws, len(values)))].mean(axis=1)
            low, high = np.quantile(sampled, [0.025, 0.975])
            records.append({
                "model_id": model, "metric": metric, "n_defined_items": len(values),
                "estimate": float(values.mean()), "ci_low": float(low), "ci_high": float(high),
                "bootstrap_draws": draws, "seed": seed,
            })
    return pd.DataFrame(records)


def trial_precision(selected: pd.DataFrame, items: pd.DataFrame, draws: int, seed: int) -> pd.DataFrame:
    # Subsample without replacement; the full realized archive is the reference.
    rng = np.random.default_rng(seed)
    records = []
    sizes = (5, 10, 25)
    for model in MODELS:
        ids = sorted(items.loc[items["model_id"].eq(model), "item_id"])
        trials = selected.loc[
            selected["experiment"].eq("main") & selected["model_id"].eq(model)
            & selected["item_id"].isin(ids)
        ].sort_values("analysis_trial_no")
        cells = {
            key: group["choice_original"].map({"A": 1.0, "B": -1.0, "N": 0.0}).to_numpy()
            for key, group in trials.groupby(["item_id", "condition"])
        }
        data = np.array([[cells[(item, condition)] for condition in CONDITIONS] for item in ids])
        reference = np.abs(data.mean(axis=(1, 2)))
        errors: dict[int, list[tuple[float, float]]] = {size: [] for size in sizes}
        for _ in range(draws):
            order = rng.random(data.shape).argsort(axis=2)
            shuffled = np.take_along_axis(data, order, axis=2)
            for size in sizes:
                estimate = np.abs(shuffled[:, :, :size].mean(axis=(1, 2)))
                difference = estimate - reference
                errors[size].append((
                    float(np.abs(difference).mean()), float(np.sqrt(np.square(difference).mean()))
                ))
        for size in sizes:
            values = np.asarray(errors[size])
            low, high = np.quantile(values[:, 0], [0.025, 0.975])
            records.append({
                "model_id": model, "trials_per_condition": size, "n_items": len(ids),
                "mean_absolute_error": float(values[:, 0].mean()),
                "mae_draw_p025": float(low), "mae_draw_p975": float(high),
                "root_mean_squared_error": float(values[:, 1].mean()),
                "resample_draws": draws, "seed": seed,
            })
    return pd.DataFrame(records)
