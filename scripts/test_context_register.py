"""Adversarial controls for a local engineering context register. All sources/people below are illustrative.

    python -S scripts/test_context_register.py
"""
import copy
import csv
import hashlib
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import context_register as cr


class ContextRegister(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.graph = {"schema": "twin-graph-1", "nodes": [
            {"id": "PLANT", "kind": "plant", "name": "Illustrative plant", "status": "unverified"},
            {"id": "P-1", "kind": "equipment", "name": "Illustrative pump", "status": "unverified",
             "attributes": [{"name": "service", "value": "water", "status": "unverified"}]},
            {"id": "P-2", "kind": "equipment", "name": "Another illustrative pump", "status": "unverified"}],
            "edges": [], "questions": []}
        self.questions = {"schema": "opportunity-questions-1", "questions": [
            {"id": "Q1@P-1", "question": "What operating pressure is recorded?", "assets": [{"id": "P-1"}],
             "status": "asked"},
            {"id": "Q2@P-2", "question": "What service is recorded?", "assets": [{"id": "P-2"}],
             "status": "asked"},
            {"id": "Q3@P-1", "question": "Has the normal range been checked?", "assets": [{"id": "P-1"}]}]}
        self.manifest = {"schema": "context-sources-1", "documents": [
            {"id": "MANUAL", "revision": "A", "path": "manual.txt", "locators": [
                {"id": "pressure", "locator": "line 2, pressure", "questions": ["Q1@P-1", "Q3@P-1"]}]},
            {"id": "SCHEDULE", "revision": "A", "path": "schedule.txt", "locators": [
                {"id": "service", "locator": "line 2, service", "questions": ["Q2@P-2"]}]}]}
        (self.root / "manual.txt").write_bytes(b"ILLUSTRATIVE test fixture\nPressure: 50 kPa\n")
        (self.root / "schedule.txt").write_bytes(b"ILLUSTRATIVE test fixture\nService: water\n")
        self.save_inputs()

    def write(self, name, value):
        (self.root / name).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

    def save_inputs(self):
        self.write("model.json", self.graph)
        self.write("questions.json", self.questions)
        self.write("sources.json", self.manifest)

    def invoke(self, command, out="bundle", register=None, answers=None, expected=0, extra=()):
        argv = [command, "--model", str(self.root / "model.json"), "--questions", str(self.root / "questions.json"),
                "--sources", str(self.root / "sources.json"), "--out", str(self.root / out)]
        if register:
            argv += ["--register", str(self.root / register)]
        if answers:
            argv += ["--answers", str(self.root / answers)]
        argv += list(extra)
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            result = cr.main(argv)
        self.assertEqual(result, expected, stderr.getvalue())
        return stdout.getvalue(), stderr.getvalue()

    def read(self, name="bundle/context.json"):
        return json.loads((self.root / name).read_text(encoding="utf-8"))

    def prepared(self):
        self.invoke("prepare")

    def row(self, qid="Q1@P-1", aid="answer-1", value="50 kPa", **kw):
        with (self.root / "bundle/evidence_choices.csv").open(encoding="utf-8", newline="") as f:
            choice = next(r for r in csv.DictReader(f) if r["question_id"] == qid)
        row = {c: "" for c in cr.COLUMNS}
        row.update(question_id=qid, answer_id=aid, claim_key="operating-pressure" if qid == "Q1@P-1" else "service",
                   value=value, answer="ILLUSTRATIVE answer quoting a fixture, not plant knowledge.",
                   answer_state="answered", decision="accepted", owner="example-owner", reviewer="example-reviewer",
                   assigned_by="example-coordinator", assigned_on="2026-10-29", reviewed_on="2026-10-29",
                   source_match="match", plant_truth="unknown", source_id=choice["source_id"],
                   locator_id=choice["locator_id"], evidence_fingerprint=choice["evidence_fingerprint"])
        row.update(kw)
        return row

    def answers(self, *rows):
        (self.root / "filled.csv").write_text(cr.csv_text(cr.COLUMNS, rows), encoding="utf-8", newline="")

    def apply(self):
        self.invoke("apply", register="bundle/context.json", answers="filled.csv")
        return self.read()

    def state(self, doc, qid="Q1@P-1"):
        return doc["current"][qid]

    def test_end_to_end_offline_fixture_retains_unknowns_and_base(self):
        before = (self.root / "model.json").read_bytes()
        self.prepared()
        blank = self.read()
        self.assertEqual(self.state(blank)["state"], "unanswered")
        self.assertEqual(self.state(blank)["ownership"], "needs_owner")
        row = self.row(owner="needs_owner", decision="proposed", reviewer="", reviewed_on="", answer_state="partial",
                       assigned_by="", assigned_on="")
        self.answers(row)
        doc = self.apply()
        self.assertEqual(self.state(doc)["state"], "partial")
        self.assertEqual(doc["decisions"][0]["plant_truth"], "unknown")
        self.assertEqual(self.state(doc, "Q3@P-1")["state"], "unanswered")
        self.assertEqual(before, (self.root / "model.json").read_bytes())
        exported = self.read("bundle/enriched_graph.json")
        self.assertEqual(exported["nodes"], self.graph["nodes"])
        self.assertEqual(exported["questions"][0]["context"]["state"], "partial")
        self.assertIn("needs owner", (self.root / "bundle/context.md").read_text(encoding="utf-8"))

    def test_identical_apply_is_byte_identical_and_preserves_history(self):
        self.prepared()
        self.answers(self.row())
        self.apply()
        before = {p.name: p.read_bytes() for p in (self.root / "bundle").iterdir()}
        self.apply()
        self.assertEqual(before, {p.name: p.read_bytes() for p in (self.root / "bundle").iterdir()})
        self.assertEqual(len(self.read()["decisions"]), 1)

    def test_separate_roles_can_have_same_person_and_ownership_is_explicit(self):
        self.prepared()
        self.answers(self.row(owner="example-engineer", reviewer="example-engineer"))
        doc = self.apply()
        self.assertEqual(self.state(doc)["owner"], "example-engineer")
        self.assertEqual(doc["decisions"][0]["reviewer"], "example-engineer")

    def test_conflicting_canonical_values_disputed_but_wording_is_not_compared(self):
        self.prepared()
        first = self.row()
        second = self.row(aid="independent-2", answer="Different explanatory wording; same canonical pressure.")
        self.answers(first, second)
        self.assertEqual(self.state(self.apply())["state"], "answered")
        second["value"] = "55 kPa"
        self.answers(second)
        doc = self.apply()
        self.assertEqual(self.state(doc)["state"], "disputed")
        self.assertEqual(self.state(doc)["disputed_claims"], ["operating-pressure"])
        self.assertEqual(len(doc["decisions"]), 3)
        second.update(decision="rejected", note="ILLUSTRATIVE rejection of the planted conflicting value.")
        self.answers(second)
        doc = self.apply()
        self.assertEqual(self.state(doc)["state"], "answered")
        self.assertEqual(len(doc["decisions"]), 4)

    def test_different_claim_slots_do_not_create_false_dispute(self):
        self.prepared()
        self.answers(self.row(), self.row(aid="range", claim_key="normal-range", value="40-60 kPa",
                                          answer_state="needs_data", decision="proposed"))
        state = self.state(self.apply())
        self.assertEqual(state["disputed_claims"], [])
        self.assertEqual(state["state"], "needs_data")

    def test_prose_and_verdicts_never_implicitly_close_questions(self):
        self.prepared()
        self.answers(self.row(answer="Yes, answered, closed, complete.", answer_state="partial"))
        self.assertEqual(self.state(self.apply())["state"], "partial")
        self.answers(self.row(answer_state="answered", decision="proposed", source_match="match"))
        self.assertEqual(self.state(self.apply())["state"], "partial")
        self.answers(self.row(answer_state="needs_data", decision="accepted"))
        self.assertEqual(self.state(self.apply())["state"], "needs_data")

    def test_screen_collection_prompts_rule_and_limits_remain_visible_after_answers(self):
        # Reuse the actual engine output's three-request shape, without claiming its assets in this toy model.
        screen = json.loads((Path(__file__).resolve().parent.parent /
                             "examples/opportunity-screen/bayer/questions.json").read_text(encoding="utf-8"))
        engine_question = next(q for q in screen["questions"] if q["question_id"] == "E18")
        self.assertEqual(len(engine_question["data_requests"]), 3)
        for field in ("data_requests", "decision_rule", "limits"):
            self.questions["questions"][0][field] = copy.deepcopy(engine_question[field])
        packet = json.loads((Path(__file__).resolve().parent.parent /
                             "examples/context-register/pronto/questions.json").read_text(encoding="utf-8"))
        structured = next(q["data_requests"][0] for q in packet["questions"] if q.get("data_requests"))
        self.assertTrue(structured["fields"])
        self.assertIsInstance(structured["where"][0], dict)
        self.questions["questions"][0]["data_requests"].append(copy.deepcopy(structured))
        expected = copy.deepcopy(self.questions["questions"][0])
        self.save_inputs()
        self.prepared()
        for answer_state in ("partial", "answered"):
            with self.subTest(answer_state=answer_state):
                self.answers(self.row(answer_state=answer_state, decision="accepted"))
                doc = self.apply()
                self.assertEqual(self.state(doc)["state"], answer_state)
                report = (self.root / "bundle/context.md").read_text(encoding="utf-8")
                self.assertIn("not per-request completion records", report)
                self.assertIn("does not automatically satisfy or clear", report)
                for request in expected["data_requests"]:
                    self.assertIn(cr.md(request["item"]), report)
                    self.assertIn(cr.md(request["how"]), report)
                    for field in request.get("fields", []):
                        self.assertIn("Field: " + cr.md(field), report)
                    for location in request["where"]:
                        if isinstance(location, dict):
                            self.assertIn("Where: " + cr.md(location["kind"]) + ": " +
                                          cr.md(location["description"]), report)
                            self.assertNotIn(str(location), report)
                        else:
                            self.assertIn(cr.md(location), report)
                for field in ("decision_rule", "limits"):
                    self.assertIn(cr.md(engine_question[field]), report)
                for name in ("enriched_questions.json", "enriched_graph.json"):
                    enriched = self.read("bundle/" + name)
                    for field in ("data_requests", "decision_rule", "limits"):
                        self.assertEqual(enriched["questions"][0][field], expected[field])

    def test_source_and_plant_truth_are_separate_and_checked_in_order(self):
        self.prepared()
        self.answers(self.row(source_match="mismatch", plant_truth="unknown", answer_state="partial"))
        doc = self.apply()
        self.assertEqual(doc["decisions"][0]["source_match"], "mismatch")
        self.assertEqual(doc["decisions"][0]["plant_truth"], "unknown")
        self.answers(self.row(reviewer="", reviewed_on="", decision="proposed", plant_truth="confirmed"))
        _, error = self.invoke("apply", out="bad", answers="filled.csv", expected=2)
        self.assertIn("plant truth requires", error)
        self.assertFalse((self.root / "bad").exists())
        self.answers(self.row(source_match="mismatch", plant_truth="confirmed", answer_state="partial"))
        _, error = self.invoke("apply", out="bad", answers="filled.csv", expected=2)
        self.assertIn("requires source_match=match", error)
        self.answers(self.row(source_match="unknown", plant_truth="unknown"))
        _, error = self.invoke("apply", out="bad", answers="filled.csv", expected=2)
        self.assertIn("answered response requires", error)
        self.answers(self.row(source_match="match", plant_truth="confirmed"))
        self.assertEqual(self.apply()["decisions"][-1]["plant_truth"], "confirmed")

    def two_accepted(self):
        self.prepared()
        self.answers(self.row(), self.row(qid="Q2@P-2", aid="service", value="water"))
        return self.apply()

    def refresh(self):
        self.invoke("apply", register="bundle/context.json")
        return self.read()

    def test_source_only_change_reopens_dependent_decision_and_rejects_old_approval(self):
        old = self.two_accepted()
        (self.root / "manual.txt").write_bytes(b"ILLUSTRATIVE revision\nPressure: 55 kPa\n")
        new = self.refresh()
        self.assertEqual(self.state(new)["state"], "unanswered")
        self.assertEqual(self.state(new)["answers"][0]["freshness"], "stale")
        self.assertEqual(self.state(new, "Q2@P-2")["state"], "answered")
        self.assertEqual(old["decisions"], new["decisions"])
        before = (self.root / "bundle/context.json").read_bytes()
        _, error = self.invoke("apply", register="bundle/context.json", answers="filled.csv", expected=2)
        self.assertIn("stale or missing evidence_fingerprint", error)
        self.assertEqual(before, (self.root / "bundle/context.json").read_bytes())

    def test_raw_bytes_not_normalized_or_stat_times(self):
        self.two_accepted()
        data = (self.root / "manual.txt").read_bytes()
        (self.root / "manual.txt").write_bytes(data.replace(b"\n", b"\r\n"))
        self.assertEqual(self.state(self.refresh())["answers"][0]["freshness"], "stale")

    def test_document_revision_and_exact_locator_independently_stale(self):
        self.two_accepted()
        self.manifest["documents"][0]["revision"] = "B"
        self.save_inputs()
        self.assertEqual(self.state(self.refresh())["state"], "unanswered")
        # Reprepare and make an explicit new decision on the new revision.
        self.invoke("prepare", out="fresh", register="bundle/context.json")
        with (self.root / "fresh/evidence_choices.csv").open(encoding="utf-8", newline="") as f:
            choice = next(r for r in csv.DictReader(f) if r["question_id"] == "Q1@P-1")
        row = self.row(evidence_fingerprint=choice["evidence_fingerprint"])
        self.answers(row)
        self.assertEqual(self.state(self.apply())["state"], "answered")
        self.manifest["documents"][0]["locators"][0]["locator"] = "line 3, corrected locator"
        self.save_inputs()
        doc = self.refresh()
        self.assertEqual(self.state(doc)["state"], "unanswered")
        self.assertEqual(len(doc["decisions"]), 3)
        self.assertEqual(doc["decisions"][0]["evidence"]["source"]["revision"], "A")

    def test_status_only_and_unrelated_changes_leave_decisions_current(self):
        self.two_accepted()
        self.graph["nodes"][1]["status"] = "confirmed"
        self.graph["nodes"][1]["attributes"][0]["status"] = "confirmed"
        self.questions["questions"][0]["status"] = "answered"
        self.questions["questions"][2]["question"] += " Changed unrelated question."
        self.graph["nodes"].append({"id": "UNRELATED", "kind": "equipment", "name": "Unrelated item"})
        self.save_inputs()
        doc = self.refresh()
        self.assertEqual(self.state(doc)["state"], "answered")
        self.assertEqual(self.state(doc, "Q2@P-2")["state"], "answered")

    def test_relevant_asset_question_and_relation_changes_only_stale_dependents(self):
        self.two_accepted()
        self.graph["nodes"][1]["attributes"][0]["value"] = "steam"
        self.save_inputs()
        doc = self.refresh()
        self.assertEqual(self.state(doc)["state"], "unanswered")
        self.assertEqual(self.state(doc, "Q2@P-2")["state"], "answered")
        self.questions["questions"][1]["question"] += " Include minimum purity."
        self.save_inputs()
        self.assertEqual(self.state(self.refresh(), "Q2@P-2")["state"], "unanswered")

    def test_unknown_and_ambiguous_references_refused_before_outputs(self):
        mutations = [
            lambda: self.questions["questions"][0]["assets"].append({"id": "UNKNOWN"}),
            lambda: self.graph["nodes"].append(copy.deepcopy(self.graph["nodes"][1])),
            lambda: self.questions["questions"].append(copy.deepcopy(self.questions["questions"][0])),
            lambda: self.manifest["documents"][0]["locators"][0]["questions"].append("UNKNOWN"),
            lambda: self.manifest["documents"].append(copy.deepcopy(self.manifest["documents"][0])),
            lambda: self.manifest["documents"][0]["locators"].append(
                copy.deepcopy(self.manifest["documents"][0]["locators"][0])),
            lambda: self.questions["questions"][0].update(evidence=[{"id": "UNKNOWN"}]),
            lambda: self.graph["edges"].append({"type": "connects", "id": "S1", "from": "P-1", "to": "UNKNOWN"}),
        ]
        baseline = copy.deepcopy((self.graph, self.questions, self.manifest))
        for change in mutations:
            with self.subTest(change=change):
                self.graph, self.questions, self.manifest = copy.deepcopy(baseline)
                change()
                self.save_inputs()
                self.invoke("prepare", out="bad", expected=2)
                self.assertFalse((self.root / "bad").exists())

    def test_identifier_whitespace_is_refused_instead_of_breaking_exact_export_joins(self):
        baseline = copy.deepcopy((self.graph, self.questions, self.manifest))
        changes = {
            "node id": lambda: self.graph["nodes"][1].update(id="P-1 "),
            "edge id": lambda: self.graph["edges"].append(
                {"id": " E1", "type": "contains", "from": "PLANT", "to": "P-1"}),
            "edge start": lambda: self.graph["edges"].append(
                {"id": "E1", "type": "contains", "from": "PLANT ", "to": "P-1"}),
            "edge end": lambda: self.graph["edges"].append(
                {"id": "E1", "type": "contains", "from": "PLANT", "to": " P-1"}),
            "edge type": lambda: self.graph["edges"].append(
                {"id": "E1", "type": "contains ", "from": "PLANT", "to": "P-1"}),
            "stream id": lambda: self.graph["edges"].append(
                {"id": "S1 ", "type": "connects", "from": "P-1", "to": "P-2"}),
            "question id": lambda: self.questions["questions"][0].update(id="Q1@P-1 "),
            "catalog question id": lambda: self.questions["questions"][0].update(question_id=" Q1"),
            "question asset ref": lambda: self.questions["questions"][0].update(assets=[{"id": "P-1 "}]),
            "question evidence ref": lambda: self.questions["questions"][0].update(evidence=[{"id": " P-1"}]),
            "source id": lambda: self.manifest["documents"][0].update(id="MANUAL "),
            "locator id": lambda: self.manifest["documents"][0]["locators"][0].update(id=" pressure"),
            "locator question ref": lambda: self.manifest["documents"][0]["locators"][0].update(
                questions=["Q1@P-1 "]),
        }
        for label, change in changes.items():
            with self.subTest(label=label):
                self.graph, self.questions, self.manifest = copy.deepcopy(baseline)
                change()
                self.save_inputs()
                original = (self.root / "model.json").read_bytes()
                _, error = self.invoke("prepare", out="bad", expected=2)
                self.assertIn("leading or trailing whitespace", error)
                self.assertFalse((self.root / "bad").exists())
                self.assertEqual(original, (self.root / "model.json").read_bytes())

    def test_csv_identity_whitespace_refused_but_internal_spaces_preserved(self):
        self.graph["nodes"][1]["id"] = "Pump A"
        for i in (0, 2):
            self.questions["questions"][i]["assets"] = [{"id": "Pump A"}]
        self.save_inputs()
        self.prepared()
        good = self.row()
        self.answers(good)
        doc = self.apply()
        self.assertEqual(doc["decisions"][0]["evidence"]["assets"][0]["id"], "Pump A")
        exported = self.read("bundle/enriched_graph.json")
        self.assertIn("Pump A", {n["id"] for n in exported["nodes"]})
        self.assertEqual(exported["questions"][0]["assets"][0]["id"], "Pump A")
        for field in ("question_id", "answer_id", "claim_key", "source_id", "locator_id"):
            with self.subTest(field=field):
                self.answers(dict(good, **{field: good[field] + " "}))
                _, error = self.invoke("apply", out="bad", answers="filled.csv", expected=2)
                self.assertIn("leading or trailing whitespace", error)
                self.assertFalse((self.root / "bad").exists())

    def test_bad_hash_missing_document_and_path_escape_refused(self):
        for mutation in ("hash", "missing", "escape"):
            with self.subTest(mutation=mutation):
                doc = self.manifest["documents"][0]
                if mutation == "hash":
                    doc["sha256"] = "0" * 64
                elif mutation == "missing":
                    doc.pop("sha256", None)
                    doc["path"] = "missing.txt"
                else:
                    doc["path"] = "../outside.txt"
                self.save_inputs()
                self.invoke("prepare", out="bad", expected=2)
                self.assertFalse((self.root / "bad").exists())

    def test_unbound_legacy_and_tampered_history_fail_before_writes(self):
        self.prepared()
        self.answers(self.row())
        original = self.apply()
        for value in ({"schema": "statements-1", "decisions": []},
                      dict(original, decisions=[{"question_id": "Q1@P-1", "answer": "old unbound approval"}])):
            self.write("legacy.json", value)
            self.invoke("apply", out="bad", register="legacy.json", expected=2)
            self.assertFalse((self.root / "bad").exists())
        tampered = copy.deepcopy(original)
        tampered["decisions"][0]["evidence"]["source"]["revision"] = "forged"
        self.write("legacy.json", tampered)
        _, error = self.invoke("apply", out="bad", register="legacy.json", expected=2)
        self.assertIn("snapshot/hash mismatch", error)

    def test_correctly_hashed_malformed_history_is_refused_without_writing(self):
        self.prepared()
        self.answers(self.row())
        baseline = self.apply()
        source_before = (self.root / "manual.txt").read_bytes()
        output = self.root / "refused-history"
        output.mkdir()
        (output / "sentinel.txt").write_bytes(b"ILLUSTRATIVE existing output must stay unchanged\n")
        output_before = {p.name: p.read_bytes() for p in output.iterdir()}
        mutations = {
            "empty ownership question identity": lambda d: d["ownership_history"][0].update(question_id=""),
            "whitespace ownership identity": lambda d: d["ownership_history"][0].update(question_id="   "),
            "empty assigned owner": lambda d: d["ownership_history"][0].update(owner=" "),
            "missing assignment actor": lambda d: d["ownership_history"][0].update(by=""),
            "invalid assignment date": lambda d: d["ownership_history"][0].update(on="2026-02-30"),
            "null asset content": lambda d: d["decisions"][0]["evidence"]["assets"][0].update(content=None),
            "non-list asset relations": lambda d: d["decisions"][0]["evidence"]["assets"][0].update(
                relations="not a relations list"),
            "non-object relation": lambda d: d["decisions"][0]["evidence"]["assets"][0].update(relations=[None]),
            "empty relation endpoint": lambda d: d["decisions"][0]["evidence"]["assets"][0].update(
                relations=[{"type": "contains", "from": "", "to": "P-1"}]),
            "unbound relation": lambda d: d["decisions"][0]["evidence"]["assets"][0].update(
                relations=[{"type": "contains", "from": "PLANT", "to": "P-2"}]),
            "mismatched asset identity": lambda d: d["decisions"][0]["evidence"]["assets"][0]["content"].update(
                id="P-2"),
            "unbound question reference": lambda d: d["decisions"][0]["evidence"]["question"].update(
                assets=[{"id": "UNKNOWN"}]),
            "missing question wording": lambda d: d["decisions"][0]["evidence"]["question"].update(question=None),
            "empty answer identity": lambda d: d["decisions"][0].update(answer_id=""),
            "invalid decision enum": lambda d: d["decisions"][0].update(decision="automatically approved"),
            "invalid reviewer structure": lambda d: d["decisions"][0].update(reviewer=[]),
            "whitespace reviewer": lambda d: d["decisions"][0].update(reviewer=" "),
            "missing review date": lambda d: d["decisions"][0].update(reviewed_on=""),
            "empty decision owner": lambda d: d["decisions"][0].update(owner=""),
            "unrecognized record field": lambda d: d["decisions"][0].update(source_id="unbound-extra-source"),
        }
        for label, mutate in mutations.items():
            with self.subTest(label=label):
                malformed = copy.deepcopy(baseline)
                mutate(malformed)
                # Each mutation receives internally correct hashes: structural validity must still fail.
                rec = malformed["decisions"][0]
                rec["evidence_fingerprint"] = cr.digest(rec["evidence"])
                rec["id"] = cr.record_id(rec, "d-")
                owner = malformed["ownership_history"][0]
                owner["id"] = cr.record_id(owner, "o-")
                self.write("malformed-history.json", malformed)
                input_before = (self.root / "malformed-history.json").read_bytes()
                self.invoke("apply", out="refused-history", register="malformed-history.json", expected=2)
                self.assertEqual(input_before, (self.root / "malformed-history.json").read_bytes())
                self.assertEqual(output_before, {p.name: p.read_bytes() for p in output.iterdir()})
                self.assertEqual(source_before, (self.root / "manual.txt").read_bytes())

    def test_csv_unknown_locator_duplicate_answer_and_owner_conflict_fail(self):
        self.prepared()
        good = self.row()
        cases = [[dict(good, locator_id="UNKNOWN")], [good, good],
                 [good, self.row(aid="second", owner="different-owner")],
                 [dict(good, question_id="UNKNOWN")], [dict(good, evidence_fingerprint="")],
                 [dict(good, decision="accepted", reviewer="")]]
        for rows in cases:
            with self.subTest(rows=rows):
                self.answers(*rows)
                self.invoke("apply", out="bad", answers="filled.csv", expected=2)
                self.assertFalse((self.root / "bad").exists())

    def test_no_configuration_paths_added_but_intentional_user_content_preserved(self):
        self.prepared()
        self.answers(self.row())
        self.apply()
        for path in (self.root / "bundle").iterdir():
            value = path.read_text(encoding="utf-8")
            self.assertNotIn(str(self.root), value)
            self.assertNotIn("manual.txt", value)
            self.assertNotIn("schedule.txt", value)
        intentional_owner = "reviewer" + chr(64) + "example.invalid"
        intentional_note = "Locally retained reference: " + str(self.root / "local-notes.txt")
        self.answers(self.row(owner=intentional_owner, note=intentional_note))
        doc = self.apply()
        self.assertEqual(doc["decisions"][-1]["owner"], intentional_owner)
        self.assertEqual(doc["decisions"][-1]["note"], intentional_note)

    def test_prepare_never_overwrites_filled_sheet(self):
        self.prepared()
        self.answers(self.row())
        value = (self.root / "bundle/answers.csv").read_bytes()
        self.invoke("prepare", expected=2)
        self.assertEqual(value, (self.root / "bundle/answers.csv").read_bytes())

    def test_source_document_output_collision_is_refused_before_any_writes(self):
        # A source named like an output must not be overwritten by the register writer.
        original = b"ILLUSTRATIVE source document, not a context report\n"
        (self.root / "context.md").write_bytes(original)
        self.manifest["documents"][0]["path"] = "context.md"
        self.save_inputs()
        _, error = self.invoke("prepare", out=".", expected=2)
        self.assertIn("source document", error)
        self.assertEqual(original, (self.root / "context.md").read_bytes())
        self.assertFalse((self.root / "context.json").exists())

    def test_alternate_register_filename_cannot_be_overwritten_by_a_report(self):
        self.prepared()
        original = (self.root / "bundle/context.json").read_bytes()
        (self.root / "bundle/context.md").write_bytes(original)
        _, error = self.invoke("apply", register="bundle/context.md", expected=2)
        self.assertIn("supplied register", error)
        self.assertEqual(original, (self.root / "bundle/context.md").read_bytes())
        self.assertEqual(original, (self.root / "bundle/context.json").read_bytes())

    def test_hardlinked_output_cannot_overwrite_source_or_another_output(self):
        self.prepared()
        target = self.root / "bundle/context.md"
        target.unlink()
        try:
            os.link(self.root / "manual.txt", target)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"filesystem does not support hardlink control: {exc}")
        original_source = (self.root / "manual.txt").read_bytes()
        original_register = (self.root / "bundle/context.json").read_bytes()
        _, error = self.invoke("apply", register="bundle/context.json", expected=2)
        self.assertIn("source document", error)
        self.assertEqual(original_source, (self.root / "manual.txt").read_bytes())
        self.assertEqual(original_register, (self.root / "bundle/context.json").read_bytes())
        target.unlink()
        os.link(self.root / "bundle/enriched_graph.json", target)
        original_graph = (self.root / "bundle/enriched_graph.json").read_bytes()
        _, error = self.invoke("apply", register="bundle/context.json", expected=2)
        self.assertIn("output files alias", error)
        self.assertEqual(original_graph, (self.root / "bundle/enriched_graph.json").read_bytes())
        self.assertEqual(original_register, (self.root / "bundle/context.json").read_bytes())

    def test_hardlink_to_register_under_another_output_name_is_protected(self):
        self.prepared()
        original = (self.root / "bundle/context.json").read_bytes()
        target = self.root / "bundle/context.md"
        target.unlink()
        try:
            os.link(self.root / "bundle/context.json", target)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"filesystem does not support hardlink control: {exc}")
        self.invoke("apply", register="bundle/context.json", expected=2)
        self.assertEqual(original, (self.root / "bundle/context.json").read_bytes())

    def test_duplicate_json_keys_and_wrong_typed_history_refused_clearly(self):
        (self.root / "sources.json").write_text('{"schema":"context-sources-1","schema":"other"}', encoding="utf-8")
        _, error = self.invoke("prepare", out="bad", expected=2)
        self.assertIn("duplicate JSON object key", error)
        self.assertFalse((self.root / "bad").exists())
        self.save_inputs()
        malformed = cr.empty_register()
        malformed["ownership_history"] = [{"id": "x", "question_id": [], "owner": "x", "by": "x",
                                            "on": "2026-10-29", "previous": None}]
        self.write("malformed.json", malformed)
        self.invoke("apply", out="bad", register="malformed.json", expected=2)
        self.assertFalse((self.root / "bad").exists())

    def test_owner_assignment_only_keeps_question_unanswered_and_history(self):
        self.prepared()
        row = {c: "" for c in cr.COLUMNS}
        row.update(question_id="Q1@P-1", owner="example-owner", assigned_by="example-coordinator",
                   assigned_on="2026-10-29")
        self.answers(row)
        doc = self.apply()
        self.assertEqual(self.state(doc)["state"], "unanswered")
        self.assertEqual(self.state(doc)["owner"], "example-owner")
        self.assertEqual(doc["decisions"], [])
        row["owner"] = "needs_owner"
        self.answers(row)
        doc = self.apply()
        self.assertEqual(self.state(doc)["ownership"], "needs_owner")
        self.assertEqual(len(doc["ownership_history"]), 2)
        self.assertEqual(doc["ownership_history"][0]["by"], "example-coordinator")
        self.assertEqual(doc["ownership_history"][0]["on"], "2026-10-29")

    def test_review_dates_and_ownership_changes_require_explicit_attribution(self):
        self.prepared()
        for changes in ({"reviewed_on": ""}, {"reviewed_on": "2026-02-30"},
                        {"reviewed_on": "2026-1-2"}, {"assigned_by": "", "assigned_on": ""},
                        {"assigned_by": "", "assigned_on": "2026-10-29"},
                        {"assigned_on": "not-a-date"}):
            with self.subTest(changes=changes):
                self.answers(self.row(**changes))
                self.invoke("apply", out="bad", answers="filled.csv", expected=2)
                self.assertFalse((self.root / "bad").exists())
        self.answers(self.row(owner="", assigned_by="", assigned_on="", reviewer="", reviewed_on="",
                              decision="proposed"))
        doc = self.apply()
        self.assertEqual(doc["ownership_history"], [])
        self.assertEqual(self.state(doc)["ownership"], "needs_owner")

    def test_exact_reversion_matches_snapshot_without_claiming_intervening_change_tracking(self):
        self.two_accepted()
        original_bytes = (self.root / "manual.txt").read_bytes()
        (self.root / "manual.txt").write_bytes(b"ILLUSTRATIVE changed source\n")
        self.assertEqual(self.state(self.refresh())["state"], "unanswered")
        (self.root / "manual.txt").write_bytes(original_bytes)
        doc = self.refresh()
        self.assertEqual(self.state(doc)["state"], "answered")
        self.assertEqual(len(doc["decisions"]), 2)

    def test_raw_process_model_and_stream_assets_work_offline(self):
        self.graph = {"meta": {"title": "Illustrative hand-built model"},
                      "units": [{"id": "P-1", "name": "Illustrative pump", "type": "pump"},
                                {"id": "P-2", "name": "Illustrative pump", "type": "pump"}],
                      "streams": [{"id": "S1", "from": "P-1", "to": "P-2", "name": "Water"}]}
        self.questions["questions"][0]["assets"].append({"id": "stream:S1"})
        self.save_inputs()
        self.prepared()
        exported = self.read("bundle/enriched_graph.json")
        self.assertEqual(exported["counts"]["questions"], len(self.questions["questions"]))
        self.assertEqual(len(exported["questions"]), len(self.questions["questions"]))
        self.answers(self.row())
        doc = self.apply()
        self.assertIn("stream:S1", [a["id"] for a in doc["decisions"][0]["evidence"]["assets"]])

    def test_relation_order_and_generated_edge_ids_are_not_dependencies(self):
        self.graph["edges"] = [{"id": "E1", "type": "contains", "from": "PLANT", "to": "P-1"},
                               {"id": "E2", "type": "contains", "from": "PLANT", "to": "P-2"}]
        self.save_inputs()
        self.two_accepted()
        self.graph["edges"].reverse()
        for i, edge in enumerate(self.graph["edges"]):
            edge["id"] = "OTHER" + str(i)
        self.save_inputs()
        self.assertEqual(self.state(self.refresh())["state"], "answered")
        self.graph["edges"].append({"id": "E3", "type": "protects", "from": "P-1", "to": "PLANT"})
        self.save_inputs()
        doc = self.refresh()
        self.assertEqual(self.state(doc)["state"], "unanswered")
        self.assertEqual(self.state(doc, "Q2@P-2")["state"], "answered")


if __name__ == "__main__":
    unittest.main()
