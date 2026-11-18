"""Reproduce the four frozen archive experiments and compare with the paper."""

from pathlib import Path
import time

def run(
    input_dir: Path, output: Path, bootstrap_draws: int, precision_draws: int, seed: int,
) -> tuple[Path, ...]:
    # Delay scientific imports so --help works without installing dependencies.
    import pandas as pd

    from . import checks, data, metrics, outputs, plots, resampling

    root = input_dir.parent
    started = time.perf_counter()
    # Verify the archive and retain genuine, complete response pairs.
    manifest, input_checks = data.verify_inputs(root, input_dir / "input_manifest.json")
    pools = data.load_pools(root)
    raw = data.load_responses(root, manifest, pools["main"])
    selected = data.select_trials(raw)
    items, exclusions, quality = metrics.build_item_metrics(raw, selected, pools)
    # References check the calculated results; they never supply observations.
    main_items = items.loc[items["experiment"].eq("main")]
    primary = metrics.summarize(main_items, ["model_id"])
    temperature = checks.original_temperature_table(items, pools["temperature_original"])
    references = root / "00_documentation" / "references"
    results = {
        "table6_commercial.csv": primary,
        "table6_comparison.csv": checks.compare_reference(
            primary, pd.read_csv(references / "table6_reference.csv"),
            {"n_items": 0, "mean_abs_Bcorr": 3, "mean_AR": 3,
             "mean_RVI_gap": 3, "mean_abs_PBI": 3, "significant_items": 0},
        ),
        "table11_temperature.csv": temperature,
        "table11_comparison.csv": checks.compare_reference(
            temperature, pd.read_csv(references / "table11_reference.csv"),
            {"mean_abs_Bcorr_07": 3, "mean_abs_Bcorr_10": 3, "shift": 3, "spearman_r": 2},
        ),
        "by_category.csv": metrics.summarize(main_items, ["model_id", "bias_category"]),
        "bootstrap_intervals.csv": resampling.bootstrap_intervals(main_items, bootstrap_draws, seed),
        "trial_precision.csv": resampling.trial_precision(selected, main_items, precision_draws, seed),
        "data_quality.csv": quality,
        "excluded_items.csv": exclusions,
        "prompt_robustness.csv": metrics.summarize(
            items.loc[items["experiment"].eq("prompt")], ["model_id", "arm"]
        ),
        "prompt_rank_correlations.csv": checks.paired_robustness(
            items, "prompt", (("V1", "V2"), ("V1", "V3"), ("V2", "V3"))
        ),
        "temperature_v2.csv": metrics.summarize(
            items.loc[items["experiment"].eq("temperature_v2")], ["model_id", "arm"]
        ),
        "temperature_v2_rank_correlations.csv": checks.paired_robustness(
            items, "temperature_v2", (("0.2", "0.7"), ("0.7", "1.0"), ("0.2", "1.0"))
        ),
    }

    # All generated files belong to results, separate from the archived inputs.
    outputs.write_results(output, selected, items, results, input_checks)
    figures = output / "figures"
    figures.mkdir(parents=True, exist_ok=True)
    plots.plot_overview(primary, figures)
    plots.plot_volatility(main_items, figures)
    plots.plot_precision(results["trial_precision.csv"], figures)
    plots.plot_temperature(results["temperature_v2.csv"], figures)
    outputs.write_report(output, results, seed, bootstrap_draws, precision_draws)
    metadata = outputs.write_metadata(
        output, results, len(input_checks), time.perf_counter() - started,
        seed, bootstrap_draws, precision_draws, input_dir,
    )
    print(f"Verified {len(input_checks)} inputs; analyzed {len(items):,} model-item-arm pairs.")
    print(f"Table 6: {metadata['table6_matches']}/{metadata['table6_reference_cells']} reference cells match.")
    print(f"Table 11: {metadata['table11_matches']}/{metadata['table11_reference_cells']} reference cells match.")
    if metadata["table11_matches"] != metadata["table11_reference_cells"]:
        print(f"NOTICE: temperature discrepancies are documented in {output / 'REPLICATION_REPORT.md'}.")
    print(f"Completed offline in {metadata['runtime_seconds']:.1f}s. API calls: 0.")
    if metadata["table6_matches"] != metadata["table6_reference_cells"]:
        raise RuntimeError("Primary reproduction check failed; inspect table6_comparison.csv")
    return tuple(output / "tables" / name for name in ("table6_comparison.csv", "table11_comparison.csv"))
