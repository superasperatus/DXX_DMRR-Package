"""Write derived data, tables, the report, and execution metadata."""

import importlib.metadata
import json
import os
from pathlib import Path
import platform

import pandas as pd


def write_csv(frame: pd.DataFrame, path: Path) -> None:
    # Use stable formatting and leave undefined numeric values blank.
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, float_format="%.10g", na_rep="", lineterminator="\n")


def write_results(
    output: Path, selected: pd.DataFrame, items: pd.DataFrame,
    tables: dict[str, pd.DataFrame], checks: list[dict],
) -> None:
    # Save derived evidence separately from immutable raw inputs.
    for name, frame in tables.items():
        write_csv(frame, output / "tables" / name)
    write_csv(selected, output / "derived" / "selected_valid_trials.csv")
    write_csv(items, output / "derived" / "item_metrics.csv")
    write_csv(pd.DataFrame(checks), output / "logs" / "verified_inputs.csv")


def markdown_table(frame: pd.DataFrame) -> str:
    # Format the key model summaries without adding a Markdown-table dependency.
    columns = ["model_id", "n_items", "mean_abs_Bcorr", "mean_AR", "mean_RVI_gap", "mean_abs_PBI", "significant_items"]
    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join("---" for _ in columns) + " |"]
    for row in frame[columns].itertuples(index=False, name=None):
        values = [f"{value:.3f}" if isinstance(value, float) else str(value) for value in row]
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def write_report(
    output: Path, tables: dict[str, pd.DataFrame],
    seed: int, bootstrap_draws: int, precision_draws: int,
) -> None:
    # Report agreement and disagreement explicitly, without changing either result.
    primary = tables["table6_comparison.csv"]
    temperature = tables["table11_comparison.csv"]
    quality = tables["data_quality.csv"]
    main = quality.loc[quality["experiment"].eq("main")]
    root = Path(__file__).resolve().parents[1]
    # Windows cannot make relative links across drives.
    if root.drive.casefold() != output.drive.casefold():
        script = (root / "03_processing" / "main.py").as_uri()
        docs = (root / "00_documentation").as_uri()
    else:
        script = os.path.relpath(root / "03_processing" / "main.py", output).replace("\\", "/")
        docs = os.path.relpath(root / "00_documentation", output).replace("\\", "/")
    report = f"""# Offline reproduction report

The analyses below are reproduced from archived commercial/API-model responses.
This report is generated from the included data; no new model responses
are collected.

## Table 6: commercial models

**{int(primary["matches_paper_precision"].sum())}/{len(primary)} reference cells match at the paper's displayed precision.**
Continuous values allow half a unit of rounding; counts must match exactly.

{markdown_table(tables["table6_commercial.csv"])}

Archived attempts: {int(main["raw_rows"].sum()):,}. Selected valid responses:
{int(main["selected_rows"].sum()):,}. Complete-pair analysis:
{int(main["analysis_rows"].sum()):,}. See [quality](tables/data_quality.csv) and
[exclusions](tables/excluded_items.csv).

## Table 11: original temperature check

**{int(temperature["matches_paper_precision"].sum())}/{len(temperature)} reference cells match.**
[The comparison table](tables/table11_comparison.csv) reports every difference.
The available archive does not recover every manuscript value under the
complete-pair rules.
The later temperature-v2 archive is separate; o4-mini is not a verified
temperature contrast.

## Resampling and limits

Bootstrap: {bootstrap_draws} draws. Trial precision: {precision_draws} draws at
5, 10, and 25 trials per condition. Seed: {seed}.
These are provided as additional analyses, not reproductions of the article's
supplementary tables.
Directional consistency alone is not evidence of stereotyping.
Undefined exclusive-volatility values remain missing, not zero.

Run [03_processing/main.py]({script}) with `--input 02_output` from the package root.
See [methodology]({docs}/METHODOLOGY.md) and [output map]({docs}/OUTPUT_MAP.md).
"""
    (output / "REPLICATION_REPORT.md").write_text(report, encoding="utf-8")


def environment_metadata() -> dict:
    # Share the installed environment record across archive and new-run results.
    return {
        "python": platform.python_version(), "platform": platform.system(),
        "packages": {
            name: importlib.metadata.version(name)
            for name in ("numpy", "pandas", "scipy", "matplotlib", "requests")
        },
    }


def write_metadata(
    output: Path, tables: dict[str, pd.DataFrame], verified_files: int,
    runtime: float, seed: int, bootstrap_draws: int, precision_draws: int, input_dir: Path,
) -> dict:
    # Record the actual execution environment, not an assumed environment.
    primary = tables["table6_comparison.csv"]
    temperature = tables["table11_comparison.csv"]
    metadata = {
        **environment_metadata(),
        "seed": seed, "bootstrap_draws": bootstrap_draws, "precision_draws": precision_draws,
        "verified_input_files": verified_files, "runtime_seconds": round(runtime, 3),
        "live_api_calls": 0,
        "table6_matches": int(primary["matches_paper_precision"].sum()),
        "table6_reference_cells": len(primary),
        "table11_matches": int(temperature["matches_paper_precision"].sum()),
        "table11_reference_cells": len(temperature),
        "input_directory": str(input_dir),
    }
    (output / "logs" / "run_metadata.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )
    return metadata
