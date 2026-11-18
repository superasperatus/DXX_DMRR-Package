"""Render the four offline figures from computed metrics and tables."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd

from .settings import MODELS


def plot_overview(summary: pd.DataFrame, output: Path) -> None:
    # Show the three main response tendencies on a common 0--1 scale.
    labels = [model.replace("-Instruct", "") for model in MODELS]
    ordered = summary.set_index("model_id").loc[list(MODELS)]
    fig, axes = plt.subplots(1, 3, figsize=(13, 4), layout="constrained")
    for ax, metric, title in zip(
        axes, ("mean_abs_Bcorr", "mean_AR", "mean_abs_PBI"),
        ("Directional consistency |Bcorr|", "Abstention rate", "Position effect |PBI|"),
    ):
        ax.barh(labels, ordered[metric], color="#35689a")
        ax.invert_yaxis()
        ax.set_title(title, fontsize=11)
        ax.set_xlim(0, 1)
        ax.grid(axis="x", alpha=0.2)
    fig.suptitle("Archived commercial/API responses: Table 6 subset")
    fig.savefig(output / "commercial_overview.png", dpi=160)
    plt.close(fig)


def plot_volatility(items: pd.DataFrame, output: Path) -> None:
    # Color by abstention to expose the metrics' shared-count relationship.
    fig, axes = plt.subplots(2, 3, figsize=(11, 6), layout="constrained")
    for model, ax in zip(MODELS, axes.flat):
        group = items.loc[items["model_id"].eq(model)]
        scatter = ax.scatter(group["abs_Bcorr"], group["RVI_incl"], c=group["AR"], s=10, vmin=0, vmax=1)
        ax.set(title=model.replace("-Instruct", ""), xlim=(0, 1), ylim=(0, 0.7))
        ax.set_xlabel("|Bcorr|")
        ax.set_ylabel("RVI inclusive")
    fig.colorbar(scatter, ax=list(axes.flat), label="Abstention rate")
    fig.suptitle("Directional consistency, volatility, and abstention")
    fig.savefig(output / "bias_volatility.png", dpi=160)
    plt.close(fig)


def plot_precision(precision: pd.DataFrame, output: Path) -> None:
    # Compare smaller trial samples with the realized 50-trial reference.
    fig, ax = plt.subplots(figsize=(8, 4.5), layout="constrained")
    for model in MODELS:
        group = precision.loc[precision["model_id"].eq(model)]
        ax.plot(group["trials_per_condition"], group["mean_absolute_error"], marker="o", label=model)
    ax.set(
        xlabel="Retained trials per order condition",
        ylabel="Mean absolute error in |Bcorr|",
        title="Subsampling archived trials against the realized 50-trial reference",
        xticks=[5, 10, 25],
    )
    ax.legend(fontsize=8)
    ax.grid(alpha=0.2)
    fig.savefig(output / "trial_precision.png", dpi=160)
    plt.close(fig)


def plot_temperature(v2: pd.DataFrame, output: Path) -> None:
    # Exclude o4-mini's fixed control from the requested-temperature curves.
    fig, ax = plt.subplots(figsize=(8, 4.5), layout="constrained")
    for model in MODELS:
        group = v2.loc[v2["model_id"].eq(model) & v2["arm"].ne("fixed")]
        if not group.empty:
            ax.plot(group["arm"].astype(float), group["mean_abs_Bcorr"], marker="o", label=model)
    ax.set(
        xlabel="Requested temperature", ylabel="Mean |Bcorr|",
        title="Later temperature-v2 archive: requested-temperature profiles",
        xticks=[0.2, 0.7, 1.0],
    )
    ax.legend(fontsize=8)
    ax.grid(alpha=0.2)
    fig.savefig(output / "temperature_v2.png", dpi=160)
    plt.close(fig)


