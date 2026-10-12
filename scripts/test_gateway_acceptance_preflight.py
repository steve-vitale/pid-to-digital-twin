"""Synthetic offline controls. These tests never establish native Ignition acceptance."""
import contextlib
import copy
import importlib.util
import io
import json
import os
import socket
import subprocess
import sys
import tempfile
import unittest
import urllib.request
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("acceptance_preflight", ROOT / "scripts/ignition/acceptance_preflight.py")
ap = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ap)


class AcceptancePreflightControls(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.manifest_path = "review/manifest.json"
        self.contract_path = "review/browser-contract.json"
        self.manifest = {
            "reviewed_model_commit": "a" * 40,
            "build_inputs": [self.write_record(name, b"fixture") for name in sorted(ap.BUILD_INPUTS)],
            "artifacts": [self.write_record(name, b"synthetic artifact") for name in sorted(ap.ARTIFACTS)],
        }
        self.contract = {
            "reviewed_model_commit": "a" * 40, "project": "PIDTwin", "provider": "Twin",
            "relative_project_base": "/data/perspective/client/PIDTwin",
            "artifacts": copy.deepcopy(self.manifest["artifacts"]),
            "routes": {f"/route/{i}": {"viewPath": f"View{i}"} for i in range(23)},
            "views": {f"View{i}": {} for i in range(23)},
            "expected_runtime_quality": {group: [f"[Twin]{group}/{i}/PV" for i in range(count)]
                                         for group, count in ap.QUALITY_COUNTS.items()},
            "prohibited_pv_asset_ids": ["S0-IN019"],
            "unmapped_clarification_asset_ids": ["S0-IN002", "S0-IN003"],
        }
        self.save_candidate()
        self.identity, _, _ = ap.candidate(self.root, self.manifest_path, self.contract_path)

    def write_record(self, name, data):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return {"path": name, "bytes": len(data), "sha256": ap.sha256(data)}

    def save_candidate(self):
        record = self.write_record(self.contract_path, json.dumps(self.contract).encode())
        self.manifest["checks_and_handoff"] = [record]
        self.write_record(self.manifest_path, json.dumps(self.manifest).encode())

    def capture(self, kind="synthetic"):
        data = {"schema_version": 1, "candidate_id": self.identity["candidate_id"],
                "evidence_kind": kind, "source_identity": "isolated synthetic fixture, never a gateway",
                "open100_source_running": True, "samples": []}
        for group, paths in self.contract["expected_runtime_quality"].items():
            good = group.startswith("good_")
            for path in paths:
                data["samples"].append({"path": path, "observations": [
                    {"observed_at": f"2026-10-11T05:00:0{i + 1}+00:00",
                     "source_timestamp": f"2026-10-11T05:00:0{i}+00:00",
                     "quality": "Good" if good else "Bad", "value": 12.5 if good else None}
                    for i in range(2 if good else 1)]})
        return data

    def invoke(self, *args):
        with contextlib.redirect_stdout(io.StringIO()) as stdout:
            status = ap.main(["--root", str(self.root), "--manifest", self.manifest_path,
                              "--contract", self.contract_path, *args])
        return status, json.loads(stdout.getvalue())

    def test_default_is_offline_only_and_native_gate_fails_closed(self):
        with patch.object(socket.socket, "connect", side_effect=AssertionError("network forbidden")), \
             patch.object(urllib.request, "urlopen", side_effect=AssertionError("network forbidden")), \
             patch.object(subprocess, "Popen", side_effect=AssertionError("process forbidden")), \
             patch.dict(os.environ, {"IGNITION_ENV_FILE": "/nonexistent/private.env", "IGNITION_API_TOKEN": "unused-fixture"}):
            status, report = self.invoke()
            native_status, native_report = self.invoke("--require-native")
        self.assertEqual(status, 0)
        self.assertEqual(native_status, 3)
        self.assertEqual(report["offline_candidate_preflight"]["status"], "PASS")
        self.assertEqual(report["offline_observation_check"]["status"], "NOT RUN")
        for result in (report, native_report):
            self.assertEqual(result["native_acceptance"], "NOT RUN")
            self.assertTrue(all(s["status"] == "NOT RUN" for s in result["runtime_stages"]))
        stages = {s["id"]: s for s in report["runtime_stages"]}
        self.assertTrue(stages["native_write_rejection"]["requires_separate_action_approval"])
        self.assertTrue(stages["native_fault_recovery"]["requires_separate_action_approval"])
        self.assertIn("native_history", stages)
        self.assertNotIn("gw", sys.modules)
        self.assertNotIn("verify_gateway", sys.modules)
        self.assertNotIn("build_gateway", sys.modules)

    def test_corrupt_input_artifact_or_contract_fails_before_observation_check(self):
        for name in ("data/te_process_model.json", next(iter(ap.ARTIFACTS)), self.contract_path):
            with self.subTest(path=name):
                path = self.root / name
                original = path.read_bytes()
                path.write_bytes(original + b" ")
                status, report = self.invoke("--observations", "does-not-exist.json")
                self.assertEqual(status, 2)
                self.assertEqual(report["offline_candidate_preflight"]["status"], "FAIL")
                self.assertEqual(report["offline_observation_check"]["status"], "NOT RUN")
                self.assertIn("mismatch", report["offline_candidate_preflight"]["error"])
                path.write_bytes(original)

    def test_manifest_artifact_mismatch_or_duplicate_is_rejected(self):
        self.contract["artifacts"][0]["sha256"] = "b" * 64
        self.save_candidate()
        self.assertEqual(self.invoke()[0], 2)
        self.contract["artifacts"] = copy.deepcopy(self.manifest["artifacts"])
        self.manifest["artifacts"].append(copy.deepcopy(self.manifest["artifacts"][0]))
        self.save_candidate()
        self.assertEqual(self.invoke()[0], 2)

    def test_missing_artifacts_inputs_and_contract_binding_are_rejected(self):
        for field in ("artifacts", "build_inputs", "checks_and_handoff"):
            with self.subTest(field=field):
                old = self.manifest[field]
                self.manifest[field] = []
                self.write_record(self.manifest_path, json.dumps(self.manifest).encode())
                self.assertEqual(self.invoke()[0], 2)
                self.manifest[field] = old

    def test_dropped_or_substituted_build_input_cannot_hide_drift(self):
        original = copy.deepcopy(self.manifest["build_inputs"])
        self.manifest["build_inputs"].pop()
        self.save_candidate()
        self.assertEqual(self.invoke()[0], 2)
        self.manifest["build_inputs"] = original
        self.manifest["build_inputs"][0] = self.write_record("unreviewed-input.json", b"fixture")
        self.save_candidate()
        self.assertEqual(self.invoke()[0], 2)

    def test_bad_candidate_shapes_fail_closed(self):
        cases = [("project", "Other"), ("reviewed_model_commit", "b" * 40),
                 ("routes", {}), ("views", []), ("expected_runtime_quality", {}),
                 ("prohibited_pv_asset_ids", []), ("unmapped_clarification_asset_ids", []),
                 ("artifacts", None)]
        for key, bad in cases:
            with self.subTest(key=key):
                old = self.contract[key]
                self.contract[key] = bad
                self.save_candidate()
                self.assertEqual(self.invoke()[0], 2)
                self.contract[key] = old

    def test_route_and_quality_duplicates_are_rejected(self):
        self.contract["routes"]["/route/0"]["viewPath"] = "Missing"
        self.save_candidate()
        self.assertEqual(self.invoke()[0], 2)
        self.contract["routes"]["/route/0"]["viewPath"] = "View0"
        groups = self.contract["expected_runtime_quality"]
        groups["bad_te_unavailable"][0] = groups["good_te_recorded"][0]
        self.save_candidate()
        self.assertEqual(self.invoke()[0], 2)

    def test_paths_reject_escape_urls_aliases_and_external_symlinks(self):
        for name in ("../outside", "/absolute", "a/../data/te_process_model.json", "./data/te_process_model.json",
                     "https://example.test/capture", "source\\model.json", "source//model.json"):
            with self.subTest(path=name), self.assertRaises(ap.InvalidEvidence):
                ap.local_file(self.root, name)
        with tempfile.TemporaryDirectory() as outside:
            external = Path(outside) / "secret"
            external.write_text("not for preflight")
            (self.root / "escape").symlink_to(external)
            with self.assertRaises(ap.InvalidEvidence):
                ap.local_file(self.root, "escape")

    def test_json_duplicates_and_nonfinite_numbers_are_rejected(self):
        for raw in ('{"x": 1, "x": 2}', '{"x": NaN}', '{"x": Infinity}'):
            self.write_record("bad.json", raw.encode())
            with self.assertRaises(ap.InvalidEvidence):
                ap.strict_json(self.root / "bad.json")

    def test_candidate_fingerprint_changes_with_contract(self):
        self.contract["routes"]["/route/0"]["title"] = "Revised"
        self.save_candidate()
        new, _, _ = ap.candidate(self.root, self.manifest_path, self.contract_path)
        self.assertNotEqual(new["candidate_id"], self.identity["candidate_id"])
        with self.assertRaises(ap.InvalidEvidence):
            ap.check_observations(self.capture(), new, self.contract)

    def test_changed_input_with_updated_manifest_invalidates_old_capture(self):
        original = self.capture()
        index = next(i for i, entry in enumerate(self.manifest["build_inputs"]) if entry["path"] == "data/te_process_model.json")
        self.manifest["build_inputs"][index] = self.write_record("data/te_process_model.json", b"revised source, same artifacts")
        self.save_candidate()
        revised, _, _ = ap.candidate(self.root, self.manifest_path, self.contract_path)
        self.assertNotEqual(revised["manifest_sha256"], self.identity["manifest_sha256"])
        self.assertNotEqual(revised["candidate_id"], self.identity["candidate_id"])
        with self.assertRaises(ap.InvalidEvidence):
            ap.check_observations(original, revised, self.contract)

    def test_complete_synthetic_and_native_label_never_promote_acceptance(self):
        for kind in ("synthetic", "native_capture"):
            data = self.capture(kind)
            self.write_record("capture.json", json.dumps(data).encode())
            status, report = self.invoke("--observations", "capture.json", "--require-native")
            self.assertEqual(status, 3)
            self.assertEqual(report["native_acceptance"], "NOT RUN")
            check = report["offline_observation_check"]
            self.assertEqual(check["status"], "PASS")
            self.assertEqual(check["path_count"], 411)
            self.assertEqual(check["evidence_kind"], kind)
            self.assertFalse(check["native_evidence_authenticated"])
            self.assertTrue(all(s["status"] == "NOT RUN" for s in report["runtime_stages"]))

    def test_observation_identity_provenance_and_source_prerequisites(self):
        for field, bad in (("candidate_id", "stale"), ("evidence_kind", "mock-pass"),
                           ("source_identity", ""), ("open100_source_running", False),
                           ("open100_source_running", 1), ("schema_version", True), ("samples", {})):
            data = self.capture()
            data[field] = bad
            with self.subTest(field=field), self.assertRaises(ap.InvalidEvidence):
                ap.check_observations(data, self.identity, self.contract)

    def test_missing_duplicate_unknown_paths_cannot_hide_behind_counts(self):
        for mode in ("missing", "duplicate", "unknown"):
            data = self.capture()
            if mode == "missing":
                data["samples"].pop()
            elif mode == "duplicate":
                data["samples"][-1] = copy.deepcopy(data["samples"][0])
            else:
                data["samples"][-1]["path"] = "[Twin]invented/PV"
            with self.subTest(mode=mode), self.assertRaises(ap.InvalidEvidence):
                ap.check_observations(data, self.identity, self.contract)

    def test_good_sample_rejects_bad_uncertain_nonfinite_bool_and_string(self):
        for field, bad in (("quality", "Bad"), ("quality", "Uncertain"), ("quality", ""),
                           ("value", float("nan")), ("value", float("inf")), ("value", True),
                           ("value", "12.5"), ("value", None)):
            data = self.capture()
            data["samples"][0]["observations"][0][field] = bad
            with self.subTest(field=field, bad=bad), self.assertRaises(ap.InvalidEvidence):
                ap.check_observations(data, self.identity, self.contract)

    def test_sample_timestamps_reject_stale_frozen_future_naive_and_reversed(self):
        changes = [(0, "source_timestamp", "2026-10-11T04:58:00Z"),
                   (1, "source_timestamp", "2026-10-11T05:00:00Z"),
                   (0, "source_timestamp", "2026-10-11T05:01:00Z"),
                   (0, "source_timestamp", "2026-10-11T05:00:00"),
                   (1, "observed_at", "2026-10-11T05:00:01Z"),
                   (0, "observed_at", "invalid")]
        for index, field, bad in changes:
            data = self.capture()
            data["samples"][0]["observations"][index][field] = bad
            with self.subTest(field=field, bad=bad), self.assertRaises(ap.InvalidEvidence):
                ap.check_observations(data, self.identity, self.contract)

    def test_single_good_sample_does_not_establish_liveness(self):
        data = self.capture()
        data["samples"][0]["observations"].pop()
        with self.assertRaises(ap.InvalidEvidence):
            ap.check_observations(data, self.identity, self.contract)

    def test_unavailable_and_placeholder_never_good(self):
        for group, bad in (("bad_te_unavailable", "Good"), ("bad_te_unavailable", "Uncertain"),
                           ("non_good_open100_placeholder", "Good")):
            data = self.capture()
            path = self.contract["expected_runtime_quality"][group][0]
            sample = next(s for s in data["samples"] if s["path"] == path)
            sample["observations"][0]["quality"] = bad
            with self.subTest(group=group, bad=bad), self.assertRaises(ap.InvalidEvidence):
                ap.check_observations(data, self.identity, self.contract)

    def test_unavailable_samples_need_no_fabricated_timestamp_or_value(self):
        for omitted in (False, True):
            data = self.capture()
            for sample in data["samples"]:
                if sample["path"] in self.contract["expected_runtime_quality"]["bad_te_unavailable"] or sample["path"] in self.contract["expected_runtime_quality"]["non_good_open100_placeholder"]:
                    for observation in sample["observations"]:
                        if omitted:
                            observation.pop("source_timestamp")
                            observation.pop("value")
                        else:
                            observation["source_timestamp"] = None
                            observation["value"] = None
            with self.subTest(omitted=omitted):
                self.assertEqual(ap.check_observations(data, self.identity, self.contract)["status"], "PASS")

    def test_uncertain_placeholder_is_permitted_without_source_sample(self):
        data = self.capture()
        path = self.contract["expected_runtime_quality"]["non_good_open100_placeholder"][0]
        observation = next(s for s in data["samples"] if s["path"] == path)["observations"][0]
        observation.update(quality="Uncertain", source_timestamp=None, value=None)
        self.assertEqual(ap.check_observations(data, self.identity, self.contract)["status"], "PASS")
        observation.pop("observed_at")
        with self.assertRaises(ap.InvalidEvidence):
            ap.check_observations(data, self.identity, self.contract)

    def test_good_samples_still_require_source_timestamp(self):
        for omitted in (False, True):
            data = self.capture()
            observation = data["samples"][0]["observations"][0]
            if omitted:
                observation.pop("source_timestamp")
            else:
                observation["source_timestamp"] = None
            with self.subTest(omitted=omitted), self.assertRaises(ap.InvalidEvidence):
                ap.check_observations(data, self.identity, self.contract)

    def test_metadata_only_callout_cannot_be_supplied_as_a_pv(self):
        data = self.capture()
        data["samples"].append({"path": "[Twin]OPEN100/MSS_sheet_0/MSS-XSS-140/MS_14010/PV",
                                "observations": [{"observed_at": "2026-10-11T05:00:01Z",
                                                  "source_timestamp": None, "quality": "Bad", "value": None}]})
        with self.assertRaises(ap.InvalidEvidence):
            ap.check_observations(data, self.identity, self.contract)

    def test_invalid_observations_preserve_passed_offline_identity_only(self):
        self.write_record("capture.json", b"{}")
        status, report = self.invoke("--observations", "capture.json")
        self.assertEqual(status, 2)
        self.assertEqual(report["offline_candidate_preflight"]["status"], "PASS")
        self.assertEqual(report["offline_observation_check"]["status"], "FAIL")
        self.assertEqual(report["native_acceptance"], "NOT RUN")

    def test_historical_check_hash_drift_is_separate_from_candidate_identity(self):
        old = self.write_record("review/old-test-log.txt", b"historical pass, not current evidence")
        self.manifest["checks_and_handoff"].append(old)
        self.write_record(self.manifest_path, json.dumps(self.manifest).encode())
        status, report = self.invoke()
        self.assertEqual(status, 0)
        self.assertEqual(report["historical_receipt_integrity"]["status"], "PASS")
        (self.root / old["path"]).write_text("changed since receipt")
        status, report = self.invoke()
        self.assertEqual(status, 0)
        self.assertEqual(report["offline_candidate_preflight"]["status"], "PASS")
        self.assertEqual(report["historical_receipt_integrity"]["status"], "DRIFT")
        self.assertEqual(report["historical_receipt_integrity"]["changed_or_unavailable"][0]["path"], old["path"])
        self.assertEqual(report["native_acceptance"], "NOT RUN")

    def test_no_execution_or_network_switches_exist(self):
        for option in ("--run", "--url", "--controls", "--fresh", "--import", "--start"):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
                ap.main([option])
            self.assertEqual(raised.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
