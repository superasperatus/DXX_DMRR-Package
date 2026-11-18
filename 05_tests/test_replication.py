from argparse import Namespace
import contextlib
import csv
from importlib import import_module
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Numbered packages use importlib because names starting with digits are not identifiers.
api = import_module("01_collection.api")
config = import_module("01_collection.config")
collector = import_module("01_collection.main")
prompts = import_module("01_collection.prompts")
collection_run = import_module("01_collection.run")
storage = import_module("01_collection.storage")
checks = import_module("03_processing.checks")
data = import_module("03_processing.data")
metrics_module = import_module("03_processing.metrics")
processor = import_module("03_processing.main")
run_inputs = import_module("03_processing.runs")
csv_checker = import_module("05_tests.check_csv")
result_outputs = import_module("03_processing.outputs")


class AnalysisTests(unittest.TestCase):
    def test_archive_report_supports_an_external_results_directory(self):
        counts = metrics_module.metrics_from_counts((1, 0, 0), (1, 0, 0))
        summary = metrics_module.summarize(pd.DataFrame([{"model_id": "M", **counts}]), ["model_id"])
        comparison = pd.DataFrame({"matches_paper_precision": [True]})
        quality = pd.DataFrame({"experiment": ["main"], "raw_rows": [2], "selected_rows": [2], "analysis_rows": [2]})
        tables = {
            "table6_commercial.csv": summary, "table6_comparison.csv": comparison,
            "table11_comparison.csv": comparison, "data_quality.csv": quality,
        }
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            result_outputs.write_report(output, tables, 42, 1, 1)
            self.assertTrue((output / "REPLICATION_REPORT.md").is_file())

    def test_ba_storage_is_decoded_once_and_original_flip_is_separate(self):
        pool = pd.DataFrame({"item_id": ["I1"], "ab_flipped": [True]})
        frame = pd.DataFrame({
            "item_id": ["I1"] * 4,
            "condition": ["AB", "BA", "BA", "BA"],
            "parsed_response": ["A", "B", "A", "N"],
            "response_coding": ["legacy_position", "legacy_position", "canonical", "legacy_position"],
        })
        restored = data.restore_choices(frame, pool)
        self.assertEqual(restored["choice_pool"].tolist(), ["A", "A", "A", "N"])
        self.assertEqual(restored["choice_original"].tolist(), ["B", "B", "B", "N"])
        bad = frame.assign(response_coding="unknown")
        with self.assertRaisesRegex(ValueError, "refusing to guess"):
            data.restore_choices(bad, pool)

    def test_pooled_metrics_and_position_correction(self):
        metrics = metrics_module.metrics_from_counts((40, 10, 0), (45, 5, 0))
        self.assertAlmostEqual(metrics["Bcorr"], 0.85)
        self.assertAlmostEqual(metrics["PBI"], -0.05)
        self.assertAlmostEqual(metrics["AR"], 0.15)
        self.assertAlmostEqual(metrics["RVI_incl"], 0.15)
        self.assertEqual(metrics["RVI_excl"], 0)
        self.assertAlmostEqual(metrics["RVI_gap"], 0.15)
        self.assertTrue(metrics["directional_significant"])
        reversed_counts = metrics_module.metrics_from_counts((0, 10, 40), (0, 5, 45))
        self.assertAlmostEqual(reversed_counts["Bcorr"], -metrics["Bcorr"])
        self.assertAlmostEqual(reversed_counts["RVI_gap"], metrics["RVI_gap"])

    def test_all_abstentions_and_negative_gap_are_not_silently_zeroed(self):
        abstention = metrics_module.metrics_from_counts((0, 50, 0), (0, 50, 0))
        self.assertEqual(abstention["AR"], 1)
        self.assertEqual(abstention["RVI_incl"], 0)
        self.assertTrue(np.isnan(abstention["RVI_excl"]))
        self.assertTrue(np.isnan(abstention["RVI_gap"]))
        self.assertTrue(np.isnan(abstention["directional_pvalue"]))
        self.assertFalse(abstention["directional_significant"])
        negative = metrics_module.metrics_from_counts((3, 45, 2), (2, 45, 3))
        self.assertAlmostEqual(negative["RVI_gap"], -0.4)
        with self.assertRaisesRegex(ValueError, "equal"):
            metrics_module.metrics_from_counts((1, 0, 0), (2, 0, 0))

    def test_selection_rejects_invalids_trims_extras_and_excludes_partial_item(self):
        rows = []
        for item, condition, count in (("I1", "AB", 51), ("I1", "BA", 50), ("I2", "AB", 50), ("I2", "BA", 49)):
            for trial in range(count):
                rows.append({
                    "experiment": "main", "arm": "0.7", "model_id": "M",
                    "item_id": item, "condition": condition,
                    "parsed_response": "A", "choice_original": "A", "error": "",
                    "timestamp": f"2026-01-01T00:00:{trial:02d}", "source_file": "raw.csv",
                    "source_row": len(rows) + 1,
                })
        rows.append({**rows[0], "parsed_response": "INVALID", "choice_original": "INVALID", "error": "failure"})
        raw = pd.DataFrame(rows)
        selected = data.select_trials(raw)
        pool = pd.DataFrame({"item_id": ["I1", "I2"], "source": ["demo"] * 2, "bias_category": ["demo"] * 2})
        items, excluded, quality = metrics_module.build_item_metrics(raw, selected, {"main": pool})
        self.assertEqual(items["item_id"].tolist(), ["I1"])
        self.assertEqual(excluded[["item_id", "n_AB", "n_BA"]].values.tolist(), [["I2", 50, 49]])
        self.assertEqual(quality.iloc[0]["trimmed_valid_rows"], 1)
        self.assertEqual(quality.iloc[0]["invalid_rows"], 1)
        kept_ab = selected.loc[selected["item_id"].eq("I1") & selected["condition"].eq("AB")]
        self.assertEqual(kept_ab["source_row"].max(), 50)

    def test_paper_check_uses_display_precision_not_fitted_values(self):
        reference = pd.DataFrame({"model_id": ["M"], "value": [0.853], "count": [178]})
        actual = pd.DataFrame({"model_id": ["M"], "value": [0.8525], "count": [179]})
        comparison = checks.compare_reference(actual, reference, {"value": 3, "count": 0})
        self.assertEqual(comparison["matches_paper_precision"].tolist(), [True, False])

    def test_grouped_metrics_preserve_models_with_no_valid_trials_in_the_audit(self):
        rows = [
            {
                "experiment": "main", "arm": "0.7", "model_id": "M", "item_id": "I1",
                "condition": condition, "trial_no": trial,
                "parsed_response": "A", "choice_original": "A", "error": "",
                "timestamp": f"2026-01-01T00:00:0{trial}", "source_file": "raw.csv",
                "source_row": index,
            }
            for index, (condition, trial) in enumerate(
                ((condition, trial) for condition in ("AB", "BA") for trial in (1, 2)), 1
            )
        ]
        rows.append({
            **rows[0], "model_id": "FILTERED", "parsed_response": "INVALID",
            "choice_original": "INVALID", "error": "Provider content filter",
        })
        raw = pd.DataFrame(rows)
        selected = data.select_trials(raw, target=2)
        pool = pd.DataFrame({"item_id": ["I1"], "source": ["demo"], "bias_category": ["demo"]})
        items, excluded, quality = metrics_module.build_item_metrics(
            raw, selected, {"main": pool}, target=2
        )
        self.assertEqual(items["model_id"].tolist(), ["M"])
        self.assertEqual(excluded[["model_id", "n_AB", "n_BA"]].values.tolist(), [["FILTERED", 0, 0]])
        audit = quality.set_index("model_id")
        self.assertEqual(audit.loc["M", "selected_rows"], 4)
        self.assertEqual(
            audit.loc["FILTERED", ["raw_rows", "invalid_rows", "selected_rows", "complete_items"]].tolist(),
            [1, 1, 0, 0],
        )

    def test_checksum_verification_detects_modified_input(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "02_output").mkdir()
            path = root / "02_output" / "input.csv"
            path.write_text("original", encoding="utf-8")
            manifest = {"files": [{"path": ["02_output", "input.csv"], "sha256": data.sha256(path)}]}
            (root / "02_output" / "input_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            data.verify_inputs(root)
            path.write_text("modified", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                data.verify_inputs(root)

class EntryPointTests(unittest.TestCase):
    def test_processing_requires_an_explicit_input(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
            processor.main([])
        self.assertEqual(error.exception.code, 2)

    def test_processing_help_works_without_scientific_packages(self):
        result = subprocess.run(
            [sys.executable, "-I", "-S", str(ROOT / "03_processing" / "main.py"), "--help"],
            cwd=ROOT.parent, capture_output=True, text=True, check=True,
        )
        self.assertIn("--bootstrap-draws", result.stdout)
        self.assertIn("--precision-draws", result.stdout)

    def test_numbered_processing_module_exposes_the_cli(self):
        result = subprocess.run(
            [sys.executable, "-m", "03_processing.main", "--help"],
            cwd=ROOT, capture_output=True, text=True, check=True,
        )
        self.assertIn("--bootstrap-draws", result.stdout)
        self.assertIn("--precision-draws", result.stdout)

    def test_collection_entry_points_are_dry_run_from_another_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "new-run"
            commands = (
                ([str(ROOT / "01_collection" / "main.py")], directory),
                (["-m", "01_collection.main"], ROOT),
            )
            for command, working_directory in commands:
                with self.subTest(command=command):
                    result = subprocess.run(
                        [
                            sys.executable, *command, "--dry-run", "--model", "gpt-4.1",
                            "--items", "1", "--trials", "1", "--output", str(output),
                        ],
                        cwd=working_directory, capture_output=True, text=True, check=True,
                    )
                    self.assertIn("= 2 valid slots.", result.stdout)
                    self.assertIn("DRY RUN ONLY", result.stdout)
                    self.assertFalse(output.exists())


class CollectionTemplateTests(unittest.TestCase):
    def test_default_runs_are_distinct_self_contained_and_explicitly_resumable(self):
        with tempfile.TemporaryDirectory() as directory:
            args = Namespace(
                output=None, pool=ROOT / "01_collection" / "stimuli" / "pool_final_200.csv",
                trials=2, temperature=0.2,
            )
            items = storage.read_items(args.pool)[:1]
            with patch.object(storage, "ROOT", Path(directory)):
                first = storage.prepare_output(args, ["gpt-4.1"], items)
                second = storage.prepare_output(args, ["gpt-4.1"], items)
                self.assertNotEqual(first, second)
                self.assertEqual((first / "stimuli.csv").read_bytes(), args.pool.read_bytes())
                args.output = first
                self.assertEqual(storage.prepare_output(args, ["gpt-4.1"], items), first)
                (first / "stimuli.csv").write_text("changed", encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "snapshot"):
                    storage.prepare_output(args, ["gpt-4.1"], items)

    def test_collection_requires_metadata_needed_for_processing(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "pool.csv"
            path.write_text("item_id,question_full,option_A_text,option_B_text\nI1,Choose,A,B\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Missing stimulus columns"):
                storage.read_items(path)

    def test_default_and_explicit_dry_run_never_construct_a_network_session(self):
        with patch.object(collection_run.requests, "Session") as session, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(collector.main(["--items", "1", "--trials", "1"]), 0)
            self.assertEqual(collector.main(["--dry-run", "--model", "gpt-4.1"]), 0)
        session.assert_not_called()

    def test_live_opt_in_with_blank_endpoints_fails_before_network(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "new-run"
            with patch.object(collection_run.requests, "Session") as session, contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaisesRegex(ValueError, "add your own HTTPS endpoint"):
                    collector.main([
                        "--execute", "--model", "gpt-4.1", "--items", "1",
                        "--trials", "1", "--output", str(output),
                    ])
            session.assert_not_called()
            self.assertFalse(output.exists())

    def test_collection_refuses_archived_inputs(self):
        for output in (
            ROOT / "02_output" / "raw",
            ROOT / "02_output" / "raw" / "main",
            ROOT / "01_collection" / "stimuli",
            ROOT / "01_collection" / "stimuli" / "new-run",
            ROOT / "00_documentation" / "references",
        ):
            with self.subTest(output=output), self.assertRaisesRegex(ValueError, "Choose a new-run directory"):
                storage.prepare_output(Namespace(output=output), ["gpt-4.1"], [])

    def test_order_changes_presentation_not_semantic_labels(self):
        item = {"question_full": "Choose a material.", "option_A_text": "Glass", "option_B_text": "Wood"}
        prompt = prompts.build_prompt(item, "BA")
        self.assertLess(prompt.index("Option B: Wood"), prompt.index("Option A: Glass"))
        self.assertEqual(prompts.parse_response("A"), "A")
        self.assertEqual(prompts.parse_response("Cannot be determined"), "N")
        self.assertEqual(prompts.parse_response("A or B"), "INVALID")
        self.assertNotIn("temperature", config.parameters_for("o4-mini", 0.2))
        self.assertEqual(config.parameters_for("gpt-4.1", 0.2)["temperature"], 0.2)

    def test_http_400_is_not_automatically_classified_as_content_filter(self):
        session = Mock()
        session.post.return_value = Mock(
            ok=False, status_code=400,
            json=Mock(return_value={"error": {"code": "invalid_parameter"}}),
        )
        with patch.dict(os.environ, {"AZURE_OPENAI_API_KEY": "test-placeholder-not-a-credential"}):
            record, status = api.request_once(session, "gpt-4.1", "demo", 0.7)
        self.assertEqual(status, "fatal")
        self.assertEqual(record["error"], "HTTP 400")
        session.post.return_value.json.return_value = {"error": {"code": "content_filter"}}
        with patch.dict(os.environ, {"AZURE_OPENAI_API_KEY": "test-placeholder-not-a-credential"}):
            _, status = api.request_once(session, "gpt-4.1", "demo", 0.7)
        self.assertEqual(status, "blocked")

    def test_canonical_ba_response_is_not_swapped_and_resume_detects_duplicates(self):
        session = Mock()
        session.post.return_value = Mock(ok=True, json=Mock(return_value={
            "choices": [{"message": {"content": "A"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 1}, "model": "provider-model",
        }))
        with patch.dict(os.environ, {"AZURE_OPENAI_API_KEY": "test-placeholder-not-a-credential"}):
            record, status = api.request_once(session, "gpt-4.1", "BA demo", 0.7)
        self.assertEqual((record["parsed_response"], status), ("A", "valid"))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "raw.csv"
            row = {
                **dict.fromkeys(config.FIELDS, ""),
                "model_id": "gpt-4.1", "item_id": "I1", "condition": "BA",
                "trial_no": 1, "parsed_response": "A", "response_coding": "canonical",
            }
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=config.FIELDS)
                writer.writeheader()
                writer.writerow(row)
                writer.writerow(row)
            with self.assertRaisesRegex(ValueError, "Duplicate valid trial"):
                storage.completed_trials(path, "gpt-4.1", {"I1"}, 50)

    def test_collection_pair_retries_preserves_attempts_and_skips_completed_slots(self):
        args = Namespace(trials=2, max_attempts=2, temperature=0.7)
        item = {"item_id": "I1", "question_full": "Choose.", "option_A_text": "Glass", "option_B_text": "Wood"}
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=config.FIELDS)
        writer.writeheader()
        responses = [
            ({"error": "Timeout"}, "retry"),
            ({"raw_response": "A", "parsed_response": "A", "error": ""}, "valid"),
        ]
        with patch.object(collection_run, "request_once", side_effect=responses), patch.object(collection_run.time, "sleep"):
            unresolved = collection_run.collect_pair(
                Mock(), args, "gpt-4.1", item, "AB", {("I1", "AB", 1)}, writer
            )
        rows = list(csv.DictReader(io.StringIO(output.getvalue())))
        self.assertEqual(unresolved, 0)
        self.assertEqual([row["trial_no"] for row in rows], ["2", "2"])
        self.assertEqual([row["parsed_response"] for row in rows], ["INVALID", "A"])
        self.assertTrue(all(row["response_coding"] == "canonical" for row in rows))

    def test_filtered_pair_stops_requests_and_reports_every_unresolved_slot(self):
        args = Namespace(trials=3, max_attempts=2, temperature=0.7)
        item = {"item_id": "I1", "question_full": "Choose.", "option_A_text": "Glass", "option_B_text": "Wood"}
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=config.FIELDS)
        writer.writeheader()
        with patch.object(collection_run, "request_once", side_effect=[
            ({"error": "Provider content filter"}, "blocked")
        ]), contextlib.redirect_stderr(io.StringIO()):
            unresolved = collection_run.collect_pair(Mock(), args, "gpt-4.1", item, "BA", set(), writer)
        self.assertEqual(unresolved, 3)
        self.assertEqual(len(list(csv.DictReader(io.StringIO(output.getvalue())))), 1)


class CollectedRunTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        pool = self.root / "pool.csv"
        items = [
            {
                "item_id": item, "source": "demo", "bias_category": "demo",
                "question_full": "Choose.", "option_A_text": "Glass", "option_B_text": "Wood",
                "ab_flipped": "False",
            }
            for item in ("I1", "I2")
        ]
        with pool.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(items[0]))
            writer.writeheader()
            writer.writerows(items)
        args = Namespace(pool=pool, output=self.root / "run", trials=2, temperature=0.2)
        self.input = storage.prepare_output(args, ["gpt-4.1"], items)
        self.output = self.root / "results"
        self.raw = self.input / "raw_gpt-4.1_commercial.csv"
        with self.raw.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=config.FIELDS)
            writer.writeheader()
            for index, (item, condition, trial, answer) in enumerate((
                ("I1", "AB", 1, "A"), ("I1", "AB", 2, "A"),
                ("I1", "BA", 1, "B"), ("I1", "BA", 2, "B"), ("I2", "AB", 1, "A"),
            ), 1):
                writer.writerow({
                    **dict.fromkeys(config.FIELDS, ""),
                    "model_id": "gpt-4.1", "item_id": item, "condition": condition,
                    "trial_no": trial, "raw_response": answer, "parsed_response": answer,
                    "response_coding": "canonical", "requested_temperature": 0.2,
                    "timestamp": f"2026-01-01T00:00:{index:02d}+00:00",
                })

    def test_selected_collection_folder_is_processed_without_reading_the_archive(self):
        with patch.object(data, "verify_inputs", side_effect=AssertionError("Archive must not be used")), contextlib.redirect_stdout(io.StringIO()) as stdout:
            processor.main(["--input", str(self.input), "--output", str(self.output)])
        summary = pd.read_csv(self.output / "tables" / "model_summary.csv", dtype={"arm": str})
        self.assertEqual(summary["model_id"].tolist(), ["gpt-4.1"])
        self.assertEqual(summary["arm"].tolist(), ["0.2"])
        self.assertEqual(summary.iloc[0]["n_items"], 1)
        self.assertEqual(summary.iloc[0]["mean_abs_Bcorr"], 0)
        self.assertEqual(summary.iloc[0]["mean_abs_PBI"], 1)
        excluded = pd.read_csv(self.output / "tables" / "excluded_items.csv")
        self.assertEqual(excluded[["item_id", "n_AB", "n_BA"]].values.tolist(), [["I2", 1, 0]])
        self.assertIn(str(self.input), stdout.getvalue())
        self.assertIn("--expected", stdout.getvalue())
        self.assertFalse((self.output / "tables" / "table6_comparison.csv").exists())

    def test_changed_snapshot_is_rejected(self):
        with (self.input / "stimuli.csv").open("a", encoding="utf-8") as handle:
            handle.write("\n")
        with self.assertRaisesRegex(ValueError, "checksum mismatch"):
            run_inputs.load_run(self.input)

    def test_results_cannot_contain_the_input_dataset(self):
        with contextlib.redirect_stderr(io.StringIO()) as stderr, self.assertRaises(SystemExit) as error:
            processor.main(["--input", str(self.input), "--output", str(self.root)])
        self.assertEqual(error.exception.code, 2)
        self.assertIn("outside the input dataset", stderr.getvalue())

    def test_duplicate_successful_slots_are_rejected(self):
        with self.raw.open(encoding="utf-8", newline="") as handle:
            row = next(csv.DictReader(handle))
        with self.raw.open("a", encoding="utf-8", newline="") as handle:
            csv.DictWriter(handle, fieldnames=config.FIELDS).writerow(row)
        with self.assertRaisesRegex(ValueError, "Duplicate successful"):
            run_inputs.load_run(self.input)

    def test_results_from_another_dataset_are_not_overwritten(self):
        with contextlib.redirect_stdout(io.StringIO()):
            processor.main(["--input", str(self.input), "--output", str(self.output)])
        other = self.root / "other-run"
        shutil.copytree(self.input, other)
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
            processor.main(["--input", str(other), "--output", str(self.output)])
        self.assertEqual(error.exception.code, 2)


class CSVChoiceTests(unittest.TestCase):
    def test_the_selected_comparison_is_checked_instead_of_a_cached_default(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "chosen.csv"
            frame = pd.DataFrame({
                "model_id": ["M"], "metric": ["score"], "reproduced": [0.5],
                "paper": [0.5], "rounding_tolerance": [0.0005], "matches_paper_precision": [True],
            })
            frame.to_csv(path, index=False)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(csv_checker.main(["--csv", str(path)]), 0)
                frame.loc[0, ["reproduced", "matches_paper_precision"]] = [0.7, False]
                frame.to_csv(path, index=False)
                self.assertEqual(csv_checker.main(["--csv", str(path)]), 1)

    def test_expected_csv_is_an_explicit_choice(self):
        with tempfile.TemporaryDirectory() as directory:
            actual, expected = Path(directory) / "actual.csv", Path(directory) / "expected.csv"
            actual.write_text("value\n1\n", encoding="utf-8")
            expected.write_text("value\n1\n", encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(csv_checker.main(["--csv", str(actual), "--expected", str(expected)]), 0)
                expected.write_text("value\n2\n", encoding="utf-8")
                self.assertEqual(csv_checker.main(["--csv", str(actual), "--expected", str(expected)]), 1)

    def test_noncomparison_csv_requires_an_expected_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "summary.csv"
            path.write_text("value\n1\n", encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                csv_checker.main(["--csv", str(path)])
            self.assertEqual(error.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
