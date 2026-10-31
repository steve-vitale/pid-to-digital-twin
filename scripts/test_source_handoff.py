"""Portable, offline PT01-PT12 controls for the explicit local handoff utility.

Run with Python -B. Required small fixtures are repository-relative; missing data
fails. TemporaryDirectory respects the caller's platform temporary-directory policy.
There is no private fixture cache, model service, environment-specific test switch,
or generated golden-file update mode.
"""
import argparse
import copy
import errno
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import source_handoff as h

REPO = Path(__file__).resolve().parents[1]
FIXTURE = REPO / "examples" / "source-handoff" / "fixture"
NAMES = ("native.model.json", "source.evidence.json", "handoff.manifest.json")
ENCODING_ERROR = "native write is not canonically UTF-8 encodable"
SYMLINK_POSIX_UNAVAILABLE = frozenset((errno.EPERM, errno.EACCES, errno.ENOSYS, errno.EOPNOTSUPP, errno.ENOTSUP))


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def pretty(value):
    return (json.dumps(value, ensure_ascii=False, indent=1, allow_nan=False) + "\n").encode("utf-8")


def typed_order(value):
    if type(value) is dict:
        return ("object", tuple((k, typed_order(v)) for k, v in value.items()))
    if type(value) is list:
        return ("array", tuple(typed_order(v) for v in value))
    return (type(value).__name__, value)


def order_digest(value):
    rows = []
    def walk(v, path):
        if type(v) is dict:
            rows.append([path, "object", list(v)])
            for key, child in v.items():
                walk(child, path + [key])
        elif type(v) is list:
            rows.append([path, "array", len(v)])
            for index, child in enumerate(v):
                walk(child, path + [index])
    walk(value, [])
    return sha(canonical(rows))


def seal(manifest):
    manifest["package_id"] = "source-handoff:" + sha(canonical(
        {k: v for k, v in manifest.items() if k != "package_id"}))
    return canonical(manifest) + b"\n"


def rebind_packet(model):
    packet = model["source_evidence"]
    packet["native_model_sha256"] = sha(canonical({k: v for k, v in model.items() if k != "source_evidence"}))
    packet["integrity_sha256"] = sha(canonical({k: v for k, v in packet.items() if k != "integrity_sha256"}))


class SourceHandoffPortable(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.expected = json.loads((FIXTURE / "EXPECTED.json").read_bytes())
        cls.provenance = json.loads((FIXTURE / "PROVENANCE.json").read_bytes())
        cls.embedded = (FIXTURE / "embedded.model.json").read_bytes()
        cls.model = json.loads(cls.embedded)
        cls.native = {k: v for k, v in cls.model.items() if k != "source_evidence"}
        cls.packet = cls.model["source_evidence"]
        for name, pin in (("embedded.model.json", cls.expected["embedded"]),
                          ("I01V01-VER.EX01.xml", cls.expected["original_xml"])):
            raw = (FIXTURE / name).read_bytes()
            if len(raw) != pin["bytes"] or sha(raw) != pin["raw_sha256"]:
                raise AssertionError("required fixture bytes differ: " + name)
        for file, key in (("source_handoff.py", "exporter_sha256"), ("source_evidence.py", "validator_sha256")):
            if sha((REPO / "scripts" / file).read_bytes()) != cls.expected["historical_code"][key]:
                raise AssertionError("frozen method bytes differ: " + file)

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="source handoff ")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.input = self.root / "explicit input.json"
        self.input.write_bytes(self.embedded)
        self.sentinel = self.root / "unrelated sentinel"
        self.sentinel.write_bytes(b"unrelated\x00sentinel\r\n")

    def export_args(self, out=None, scope="scope", role="role", reference=None):
        return argparse.Namespace(root=str(self.root), embedded_model=str(self.input), out=str(out or self.root / "package"),
                                  owned_scope=scope, responsible_role=role, company_reference=reference)

    def inspect_args(self, out, format="json"):
        return argparse.Namespace(root=str(self.root), native=str(out / NAMES[0]), evidence=str(out / NAMES[1]),
                                  manifest=str(out / NAMES[2]), format=format)

    def manifest(self, *, scope="scope", role="role", reference=None, raw=None, model=None, nr=None, er=None):
        model = self.model if model is None else model
        raw = self.embedded if raw is None else raw
        native = {k: v for k, v in model.items() if k != "source_evidence"}
        packet = model["source_evidence"]
        nr = pretty(native) if nr is None else nr
        er = pretty(packet) if er is None else er
        m = {"schema": "native-source-handoff-1", "required_capabilities": ["native-source-handoff-1"], "package_id": "",
             "document": {k: packet["document"][k] for k in ("document_id", "raw_source_sha256", "raw_size_bytes")},
             "native": {"file": NAMES[0], "size_bytes": len(nr), "raw_sha256": sha(nr), "canonical_sha256": sha(canonical(native))},
             "evidence": {"file": NAMES[1], "size_bytes": len(er), "raw_sha256": sha(er), "packet_schema": packet["schema"],
                          "packet_integrity_sha256": packet["integrity_sha256"]},
             "provenance": {"embedded_input_size_bytes": len(raw), "embedded_input_raw_sha256": sha(raw),
                            **self.expected["historical_code"], "capture_method_attestation": "not_provided"},
             "handoff": {"owned_scope": scope, "responsible_role": role,
                         "company_release_reference": {"present": False} if reference is None else {"present": True, "value": reference},
                         "company_release_state": "not_evaluated"}}
        return m, nr, er, seal(m)

    def brief(self, m, mr, operation, format, packet=None):
        packet = self.packet if packet is None else packet
        b = {"schema": "native-source-handoff-brief-1", "operation": operation, "package_id": m["package_id"],
             "document": m["document"], "native": m["native"], "evidence": m["evidence"],
             "manifest": {"file": NAMES[2], "size_bytes": len(mr), "raw_sha256": sha(mr)}, "completeness": packet["completeness"],
             "handoff": m["handoff"], "declared_provenance": m["provenance"],
             "receiving_validation": {"inspector_sha256": self.expected["historical_code"]["exporter_sha256"],
                                      "validator_sha256": self.expected["historical_code"]["validator_sha256"],
                                      "artifact_basis": "validated_export_bytes" if operation == "export" else "actual_selected_files"},
             "comparison": "not_compared", "application_status": "unverified", "external_originals": "not_reverified"}
        return canonical(b) + b"\n" if format == "json" else b"Native/source handoff summary\n" + json.dumps(
            b, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False).encode("utf-8") + b"\n"

    def package(self, path, *, parts=None):
        path.mkdir(parents=True, exist_ok=False)
        m, nr, er, mr = self.manifest() if parts is None else parts
        for name, raw in zip(NAMES, (nr, er, mr)):
            (path / name).write_bytes(raw)
        return m, nr, er, mr

    def cli(self, argv, *, success=True, semantic=True):
        p = subprocess.run([sys.executable, "-B", str(REPO / "scripts" / "source_handoff.py"), *map(str, argv)],
                           capture_output=True, check=False)
        self.assertEqual(p.returncode, 0 if success else 1, p.stderr)
        if success:
            self.assertEqual(p.stderr, b"")
        else:
            self.assertEqual(p.stdout, b"")
            self.assertTrue(p.stderr.startswith(b"handoff refused: ") if semantic else p.stderr.startswith(b"handoff I/O failure;"), p.stderr)
        self.assertEqual(self.sentinel.read_bytes(), b"unrelated\x00sentinel\r\n")
        return p.stdout

    def inspect_cli(self, path, *, success=True, format="json", semantic=True):
        before = {name: (path / name).read_bytes() for name in NAMES if (path / name).exists()}
        raw = self.cli(["inspect", "--root", self.root, "--native", path / NAMES[0], "--evidence", path / NAMES[1],
                        "--manifest", path / NAMES[2], "--format", format], success=success, semantic=semantic)
        self.assertEqual(before, {name: (path / name).read_bytes() for name in NAMES if (path / name).exists()})
        return raw

    def refuse(self, action, literal=None):
        with self.assertRaises(h.Error) as caught:
            action()
        if literal is not None:
            self.assertEqual(str(caught.exception), literal)
        self.assertEqual(self.sentinel.read_bytes(), b"unrelated\x00sentinel\r\n")
        return caught.exception

    def _check_escaping_symlink(self):
        link = self.root / "escape-link"
        try:
            link.symlink_to(self.root.parent, target_is_directory=True)
        except OSError as exc:
            winerror = getattr(exc, "winerror", None)
            unavailable = winerror == 1314 or (winerror is None and exc.errno in SYMLINK_POSIX_UNAVAILABLE)
            if not unavailable:
                raise
            # unittest's progress prefix may already occupy stderr's current line.
            # Begin a physical line so the actual runner can recognize this notice.
            print("\nSKIP [platform] PT08 escaping-symlink creation unavailable: " + type(exc).__name__ +
                  " errno=" + str(exc.errno) + " winerror=" + str(winerror) + " " + str(exc), file=sys.stderr)
        else:
            self.refuse(lambda: h._export(self.export_args(link / "escape")), "selected path escapes approved root")

    def _coverage_notices(self, text):
        spec = importlib.util.spec_from_file_location("handoff_actual_runner", REPO / "scripts" / "run_tests.py")
        runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runner)
        return runner.coverage_notices("", text)

    def test_PT01_saved_complete_cli_roundtrip(self):
        m, nr, er, mr = self.manifest()
        for raw, pin in ((nr, self.expected["saved_native"]), (er, self.expected["saved_packet"]), (mr, self.expected["saved_manifest"])):
            self.assertEqual((len(raw), sha(raw)), (pin["bytes"], pin["raw_sha256"]))
        self.assertEqual(m["package_id"], self.expected["saved_manifest"]["package_id"])
        out = self.root / "package"
        actual = self.cli(["export", "--root", self.root, "--embedded-model", self.input, "--out", out,
                           "--owned-scope", "scope", "--responsible-role", "role"])
        expected = self.brief(m, mr, "export", "text")
        self.assertEqual(sha(expected), self.expected["base_saved_briefs"]["export-text.expected"]["raw_sha256"])
        self.assertEqual(actual, expected)
        for name, expected in zip(NAMES, (nr, er, mr)):
            self.assertEqual((out / name).read_bytes(), expected)
        expected = self.brief(m, mr, "inspect", "json")
        self.assertEqual(sha(expected), self.expected["base_saved_briefs"]["inspect-json.expected"]["raw_sha256"])
        self.assertEqual(self.inspect_cli(out), expected)
        native, packet = json.loads(nr), json.loads(er)
        self.assertEqual(typed_order(native), typed_order(self.native))
        self.assertEqual(typed_order(packet), typed_order(self.packet))
        self.assertEqual(order_digest(native), self.expected["saved_native"]["recursive_order_sha256"])
        self.assertEqual(order_digest(packet), self.expected["saved_packet"]["recursive_order_sha256"])
        native["source_evidence"] = packet
        self.assertEqual(pretty(native), self.embedded)

    def test_PT02_explicit_reader_capture_and_native_default(self):
        xml = self.root / self.expected["reader_PT02_literals"]["XML_basename"]
        shutil.copyfile(FIXTURE / xml.name, xml)
        self.assertEqual(xml.read_bytes().count(b"\r\n"), 133)
        for capture in (False, True):
            out = self.root / ("captured" if capture else "native")
            argv = [sys.executable, "-B", str(REPO / "scripts" / "dexpi_reader.py"), "--xml", str(xml), "--out", str(out),
                    "--sheet-id", "reference"]
            if capture:
                argv.append("--capture-source")
            p = subprocess.run(argv, capture_output=True)
            self.assertEqual(p.returncode, 0, p.stderr)
            raw = (out / "reference.model.json").read_bytes()
            self.assertEqual(sha(raw), self.expected["reader_PT02_literals"]["enabled_embedded_expected_raw_sha256" if capture else "Native_expected_raw_sha256"])
            self.assertEqual(raw, self.embedded if capture else pretty(self.native))
            self.assertEqual("source_evidence" in json.loads(raw), capture)
            args = self.export_args(self.root / ("pair-" + str(capture))); args.embedded_model = str(out / "reference.model.json")
            if capture:
                actual = h._export(args); m, nr, er, mr = self.manifest()
                self.assertEqual(actual, self.brief(m, mr, "export", "text"))
            else:
                self.refuse(lambda: h._export(args), "embedded source packet required")
                self.assertFalse(Path(args.out).exists())
        utility = (REPO / "scripts" / "source_handoff.py").read_text(encoding="utf-8")
        self.assertNotIn("dexpi_reader", utility)

    def test_PT03_missing_mixed_changed_binding_refusals(self):
        for index in range(3):
            with self.subTest(missing=index):
                out = self.root / ("missing-" + str(index)); self.package(out); (out / NAMES[index]).unlink()
                self.inspect_cli(out, success=False, semantic=False)
        variants = ("mixed", "stale", "native-reseal", "packet-change", "manifest-only")
        for label in variants:
            with self.subTest(mutation=label):
                out = self.root / label; m, nr, er, mr = self.package(out)
                n, e = json.loads(nr), json.loads(er)
                if label == "mixed":
                    alternate = copy.deepcopy(self.model); alternate["native_extra"] = 1; rebind_packet(alternate)
                    er = pretty(alternate["source_evidence"])
                elif label == "stale":
                    nr += b" "
                elif label == "native-reseal":
                    n["changed"] = 1; nr = pretty(n); m["native"]["size_bytes"] = len(nr); m["native"]["raw_sha256"] = sha(nr); mr = seal(m)
                elif label == "packet-change":
                    e["records"].reverse(); er = pretty(e); m["evidence"]["raw_sha256"] = sha(er); mr = seal(m)
                else:
                    m["native"]["canonical_sha256"] = "0" * 64; mr = seal(m)
                for name, raw in zip(NAMES, (nr, er, mr)): (out / name).write_bytes(raw)
                self.inspect_cli(out, success=False)
        for existing in (False, True):
            out = self.root / ("prewrite-" + str(existing))
            if existing: out.mkdir(); (out / "sentinel").write_bytes(b"keep")
            before = self.input.read_bytes(); self.input.write_bytes(pretty(self.native))
            self.refuse(lambda: h._export(self.export_args(out)), "embedded source packet required")
            self.assertEqual(self.input.read_bytes(), pretty(self.native))
            self.assertEqual(list(out.iterdir()), [out / "sentinel"]) if existing else self.assertFalse(out.exists())
            self.input.write_bytes(before)

    def test_PT04_strict_encoding_closed_profiles(self):
        invalid = {"utf8": b'{"x":"\xff"}', "duplicate": b'{"x":1,"x":2}', "nonfinite": b'{"x":NaN}',
                   "high": b'{"x":"\\ud800"}', "low": b'{"x":"\\udfff"}'}
        for label, raw in invalid.items():
            with self.subTest(strict=label):
                self.input.write_bytes(raw); out = self.root / label
                stderr = io.StringIO(); stdout = io.BytesIO(); wrapper = io.TextIOWrapper(stdout, encoding="utf-8", write_through=True)
                argv = ["export", "--root", str(self.root), "--embedded-model", str(self.input), "--out", str(out), "--owned-scope", "scope", "--responsible-role", "role"]
                with patch.object(sys, "stdout", wrapper), patch.object(sys, "stderr", stderr): code = h.main(argv)
                self.assertEqual(code, 1); self.assertEqual(stdout.getvalue(), b""); wrapper.detach()
                self.assertFalse(out.exists()); self.assertTrue(stderr.getvalue().startswith("handoff refused: "))
                if label in ("high", "low"): self.assertEqual(stderr.getvalue(), "handoff refused: " + ENCODING_ERROR + "\n")
                self.assertNotIn("UnicodeEncodeError", stderr.getvalue())
        self.input.write_bytes(self.embedded)
        for label in ("schema", "capability", "field", "bool"):
            out = self.root / ("closed-" + label); m, nr, er, _ = self.manifest()
            if label == "schema": m["schema"] = "future"
            if label == "capability": m["required_capabilities"].append("future")
            if label == "field": m["native"]["extra"] = 0
            if label == "bool": m["provenance"]["embedded_input_size_bytes"] = True
            self.package(out, parts=(m, nr, er, seal(m))); self.inspect_cli(out, success=False)
        for field in ("owned_scope", "responsible_role", "company_reference"):
            args = self.export_args(self.root / field); setattr(args, field, "\ud800")
            err = self.refuse(lambda: h._export(args), ENCODING_ERROR)
            self.assertIsNone(err.__cause__); self.assertFalse(Path(args.out).exists())
        bad = copy.deepcopy(self.model); bad["source_evidence"]["required_capabilities"].append("future")
        self.input.write_bytes(canonical(bad)); self.refuse(lambda: h._export(self.export_args()))

    def test_PT05_raw_canonical_separate_legal_formats(self):
        m, nr, er, mr = self.manifest()
        nr = nr.replace(b"\n", b"\r\n") + b" \t"
        er = er.replace(b"\n", b"\r\n")
        out = self.root / "old binding"; self.package(out, parts=(m, nr, er, mr)); self.inspect_cli(out, success=False)
        for key, raw in (("native", nr), ("evidence", er)):
            m[key]["size_bytes"], m[key]["raw_sha256"] = len(raw), sha(raw)
        mr = seal(m).replace(b"\n", b"\r\n") + b" \n"
        (out / NAMES[2]).write_bytes(mr)
        actual = json.loads(self.inspect_cli(out))
        self.assertEqual(actual["manifest"]["raw_sha256"], sha(mr))
        self.assertEqual(actual["native"]["canonical_sha256"], self.expected["saved_native"]["canonical_sha256"])
        self.assertNotEqual(actual["native"]["raw_sha256"], self.expected["saved_native"]["raw_sha256"])
        ids = (m["provenance"]["embedded_input_raw_sha256"], m["native"]["canonical_sha256"],
               m["evidence"]["packet_integrity_sha256"], m["package_id"])
        self.assertEqual(len(set(ids)), 4)

    def test_PT06_saved_derivatives_typed_recursive_order(self):
        self.assertNotEqual(typed_order(False), typed_order(0))
        self.assertNotEqual(typed_order(0), typed_order(None))
        for label, pins in self.expected["order_derivative_saved_pins"].items():
            with self.subTest(derivative=label):
                model = copy.deepcopy(self.model); packet = model.pop("source_evidence")
                if label == "nested": model["opaque"] = {"source_evidence": {"source": "ordinary", "status": "data"}}
                if label == "typed": model["typed"] = {"false": False, "zero": 0, "none": None, "empty": "", "raw": ["01", "1.00", "false"]}
                if label == "qname": model["opaque"] = {"{urn:scope}empty": "", "ordered": [{"b": False, "a": None}, []]}
                items = list(model.items()); position = 0 if label == "first" else len(items) // 2 if label == "middle" else len(items)
                items.insert(position, ("source_evidence", packet)); model = dict(items); rebind_packet(model)
                raw = pretty(model) if label == "last" else json.dumps(model, ensure_ascii=True, separators=(",", ":")).encode("ascii")
                nr = pretty({k: v for k, v in model.items() if k != "source_evidence"}); er = pretty(packet)
                for key, data in (("embedded.json", raw), (NAMES[0], nr), (NAMES[1], er)):
                    self.assertEqual((len(data), sha(data)), (pins[key]["bytes"], pins[key]["raw_sha256"]))
                self.input.write_bytes(raw); out = self.root / label; h._export(self.export_args(out))
                self.assertEqual((out / NAMES[0]).read_bytes(), nr); self.assertEqual((out / NAMES[1]).read_bytes(), er)
                n, p = json.loads(nr), json.loads(er)
                self.assertEqual(typed_order(n), typed_order({k: v for k, v in model.items() if k != "source_evidence"}))
                self.assertEqual(typed_order(p), typed_order(packet)); n["source_evidence"] = p
                self.assertEqual(list(n)[-1], "source_evidence")
                self.assertEqual(pretty(n) == raw, label == "last")

    def test_PT07_declared_history_and_receiving_validation(self):
        m, nr, er, _ = self.manifest(scope=" \n\t", role="responsible\x1brole", reference="https://unavailable.invalid/review")
        m["provenance"]["exporter_sha256"] = "1" * 64; m["provenance"]["validator_sha256"] = "2" * 64
        out = self.root / "history"; self.package(out, parts=(m, nr, er, seal(m)))
        # No selected artifact contains a live fetch target. Originals/history are absent.
        b = json.loads(self.inspect_cli(out))
        self.assertEqual(b["declared_provenance"], m["provenance"])
        self.assertNotEqual(b["declared_provenance"]["exporter_sha256"], b["receiving_validation"]["inspector_sha256"])
        self.assertEqual(b["handoff"], m["handoff"])
        for key in ("comparison", "application_status", "external_originals"):
            self.assertEqual(b[key], self.expected["labels_required"][key])
        self.assertEqual(b["handoff"]["company_release_state"], "not_evaluated")
        self.assertEqual(b["declared_provenance"]["capture_method_attestation"], "not_provided")

    def test_PT08_filesystem_git_checkout_relocation(self):
        sub = self.root / "input elsewhere"; sub.mkdir(); self.input.rename(sub / self.input.name); self.input = sub / self.input.name
        out = self.root / "Caf\u00e9 \U0001f6e0 package"; out.mkdir(); (out / "sentinel").write_bytes(b"keep")
        h._export(self.export_args(out)); self.assertEqual((out / "sentinel").read_bytes(), b"keep")
        before = {name: (out / name).read_bytes() for name in NAMES}
        self.refuse(lambda: h._export(self.export_args(out)), "handoff target already exists")
        self.assertEqual(before, {name: (out / name).read_bytes() for name in NAMES})
        self.refuse(lambda: h._export(self.export_args(self.root.parent / "escape")), "selected path escapes approved root")
        args = self.inspect_args(out); args.evidence = str(self.root / NAMES[1]); shutil.copyfile(out / NAMES[1], args.evidence)
        self.refuse(lambda: h._inspect(args), "selected roles require one package parent")
        hard = self.root / "hard"; self.package(hard); (hard / NAMES[1]).unlink(); os.link(hard / NAMES[0], hard / NAMES[1])
        self.refuse(lambda: h._inspect(self.inspect_args(hard)), "selected file alias")
        self._check_escaping_symlink()
        git = shutil.which("git")
        self.assertIsNotNone(git, "Git is required for the durable checkout control")
        source = self.root / "git source"; source.mkdir()
        files = [".gitattributes", "scripts/source_handoff.py", "scripts/source_evidence.py", "scripts/test_source_handoff.py",
                 *[str(p.relative_to(REPO)) for p in FIXTURE.iterdir()]]
        for name in files:
            target = source / name; target.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(REPO / name, target)
        def command(argv, cwd):
            p = subprocess.run([git, *argv], cwd=cwd, capture_output=True); self.assertEqual(p.returncode, 0, p.stderr)
        command(["init", "-q"], source); command(["config", "user.name", "Fixture test"], source)
        command(["config", "user.email", "fixture@example.invalid"], source)
        command(["add", "."], source); command(["commit", "-qm", "Frozen public training seed"], source)
        for clean in ("true", "false"):
            for checkout in ("true", "false"):
                with self.subTest(clean=clean, checkout=checkout):
                    command(["config", "core.autocrlf", clean], source)
                    command(["add", "--renormalize", "."], source)
                    diff = subprocess.run([git, "diff", "--cached", "--exit-code"], cwd=source, capture_output=True)
                    self.assertEqual(diff.returncode, 0, diff.stdout)
                    clone = self.root / ("checkout-" + clean + "-" + checkout)
                    command(["-c", "core.autocrlf=" + checkout, "clone", "-q", str(source), str(clone)], self.root)
                    for name in files:
                        self.assertEqual((clone / name).read_bytes(), (REPO / name).read_bytes(), name)
                    moved = self.root / ("relocated-" + clean + "-" + checkout); shutil.copytree(clone, moved, ignore=shutil.ignore_patterns(".git"))
                    model = moved / "examples/source-handoff/fixture/embedded.model.json"
                    p = subprocess.run([sys.executable, "-B", str(moved / "scripts/source_handoff.py"), "export", "--root", str(moved),
                                        "--embedded-model", str(model), "--out", str(moved / "package"), "--owned-scope", "scope", "--responsible-role", "role"], capture_output=True)
                    self.assertEqual(p.returncode, 0, p.stderr)
                    m, nr, er, mr = self.manifest(); self.assertEqual(p.stdout, self.brief(m, mr, "export", "text"))
                    p = subprocess.run([sys.executable, "-B", str(moved / "scripts/source_handoff.py"), "inspect", "--root", str(moved),
                                        "--native", str(moved / "package" / NAMES[0]), "--evidence", str(moved / "package" / NAMES[1]),
                                        "--manifest", str(moved / "package" / NAMES[2]), "--format", "json"], capture_output=True)
                    self.assertEqual(p.returncode, 0, p.stderr); self.assertEqual(p.stdout, self.brief(m, mr, "inspect", "json"))

    def test_PT09_bounded_binary_acquisition_and_rechecks(self):
        original = Path.open; logs = []; counts = {}
        class Reader:
            def __init__(inner, path, stream): inner.path, inner.stream, inner.total = path, stream, 0
            def __enter__(inner): inner.stream.__enter__(); counts[inner.path] = counts.get(inner.path, 0) + 1; return inner
            def __exit__(inner, *args): return inner.stream.__exit__(*args)
            def read(inner, size=None):
                self.assertIs(type(size), int); self.assertGreater(size, 0)
                self.assertLessEqual(size, min(65536, h.MAX_INPUT + 1 - inner.total))
                raw = inner.stream.read(min(size, (1, 7, 4093, 65000)[len(logs) % 4])); inner.total += len(raw)
                logs.append((inner.path.name, size, len(raw), inner.total)); return raw
        def opening(path, mode="r", *args, **kwargs):
            stream = original(path, mode, *args, **kwargs)
            return Reader(path, stream) if mode == "rb" else stream
        out = self.root / "instrumented"
        with patch.object(Path, "open", opening):
            h._export(self.export_args(out)); h._inspect(self.inspect_args(out))
        self.assertGreaterEqual(counts[self.input], 6)
        for name, minimum in zip(NAMES, (5, 4, 3)): self.assertGreaterEqual(counts[out / name], minimum)
        for name in ("source_handoff.py", "source_evidence.py"):
            self.assertGreaterEqual(counts[(REPO / "scripts" / name).resolve()], 3)
        class Lazy:
            def __init__(inner, length, short=False): inner.left, inner.total, inner.requests, inner.short = length, 0, [], short
            def read(inner, request=None):
                self.assertIs(type(request), int); self.assertGreater(request, 0)
                self.assertLessEqual(request, min(65536, h.MAX_INPUT + 1 - inner.total))
                count = min(inner.left, request, 4093 if inner.short else request)
                inner.requests.append((request, count)); inner.left -= count; inner.total += count
                return b"x" * count
        for cap in (0, 1, 65535, 65536, 65537, 33554432):
            with patch.object(h, "MAX_INPUT", cap):
                for length in (cap, cap + 1):
                    reader = Lazy(length, short=True)
                    if length <= cap:
                        self.assertEqual(len(h._acquire(reader)), length); self.assertEqual(reader.requests[-1][1], 0)
                    else:
                        self.refuse(lambda: h._acquire(reader), "selected input exceeds 32MiB")
                        self.assertEqual(reader.total, cap + 1); self.assertGreater(reader.requests[-1][1], 0)
        class Broken:
            calls = 0
            def read(inner, size):
                inner.calls += 1
                if inner.calls == 1: return b"x"
                raise OSError("injected acquisition failure")
        with self.assertRaises(OSError): h._acquire(Broken())

    def test_PT10_size_domains_real_file_and_generated_boundaries(self):
        for maximum in (33554432, 268435456):
            for value in (0, maximum): h._size(value, maximum)
            for value in (-1, maximum + 1, True, 0.0, "0", None): self.refuse(lambda value=value: h._size(value, maximum), "invalid handoff byte size")
        for role in ("embedded", "native", "evidence", "manifest"):
            for target in (33554431, 33554432, 33554433):
                with self.subTest(selected=role, target=target), tempfile.TemporaryDirectory(dir=self.root) as temp:
                    folder = Path(temp)
                    if role == "embedded":
                        self.input.write_bytes(self.embedded + b" " * (target - len(self.embedded)))
                        action = lambda: h._export(self.export_args(folder / "out"))
                    else:
                        m, nr, er, mr = self.manifest()
                        if role == "native": nr += b" " * (target - len(nr))
                        if role == "evidence": er += b" " * (target - len(er))
                        for key, raw in (("native", nr), ("evidence", er)):
                            m[key]["size_bytes"], m[key]["raw_sha256"] = len(raw), sha(raw)
                        mr = seal(m)
                        if role == "manifest": mr += b" " * (target - len(mr))
                        self.package(folder / "pair", parts=(m, nr, er, mr)); action = lambda: h._inspect(self.inspect_args(folder / "pair"))
                    if target <= 33554432: self.assertTrue(action())
                    else: self.refuse(action, "selected input exceeds 32MiB")
        self.input.write_bytes(self.embedded)
        for role in ("native", "evidence", "manifest"):
            for target in (33554431, 33554432, 33554433):
                with self.subTest(generated=role, target=target), tempfile.TemporaryDirectory(dir=self.root) as temp:
                    model = copy.deepcopy(self.model); scope = "scope"
                    if role == "native":
                        model["padding_array"] = [None] * 100000; model["padding_text"] = ""; rebind_packet(model)
                        model["padding_text"] = "x" * (target - len(pretty({k: v for k, v in model.items() if k != "source_evidence"}))); rebind_packet(model)
                    elif role == "evidence":
                        selected = None
                        for record in model["source_evidence"]["records"]:
                            mappings = {entry["source_occurrence_id"]: entry["destinations"] for entry in record["mappings"]}
                            for attr in record["raw_payload"]["attributes"]:
                                if attr["name"]["local_name"] not in ("ID", "Name", "FromID", "ToID", "ItemID", "TagName") and not mappings[attr["occurrence_id"]] and not record["raw_payload"]["source_assertions"]:
                                    selected = record, attr; break
                            if selected: break
                        self.assertIsNotNone(selected); record, attr = selected; attr["value"] = ""
                        def version():
                            record["record_version_id"] = sha(canonical({k: v for k, v in record.items() if k not in ("id", "record_version_id")}))
                            record["id"] = "source_record:" + record["record_version_id"]; rebind_packet(model)
                        version(); attr["value"] = "x" * (target - len(pretty(model["source_evidence"]))); version()
                    else:
                        _, _, _, mr = self.manifest(scope="", model=model, raw=canonical(model))
                        scope = "x" * (target - len(mr))
                    raw = json.dumps(model, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
                    self.assertLessEqual(len(raw), 33554432); self.input.write_bytes(raw)
                    parts = self.manifest(scope=scope, model=json.loads(raw), raw=raw)
                    expected = parts[("native", "evidence", "manifest").index(role) + 1]
                    self.assertEqual(len(expected), target)
                    out = Path(temp) / "out"; observed = []
                    old_pretty, old_can = h._pretty, h._canonical
                    def render(value):
                        result = old_pretty(value)
                        if (role == "native" and "padding_text" in value) or (role == "evidence" and value.get("schema") == "xml-source-evidence-1"): observed.append(result)
                        return result
                    def encode(value):
                        result = old_can(value)
                        if role == "manifest" and type(value) is dict and value.get("schema") == h.SCHEMA and "package_id" in value: observed.append(result + b"\n")
                        return result
                    with patch.object(h, "_pretty", render), patch.object(h, "_canonical", encode):
                        if target > 33554432:
                            self.refuse(lambda: h._export(self.export_args(out, scope=scope)), "generated handoff artifact exceeds 32MiB")
                        elif role == "manifest":
                            self.refuse(lambda: h._export(self.export_args(out, scope=scope)), "handoff summary exceeds 2MiB")
                        else:
                            h._export(self.export_args(out, scope=scope)); self.assertEqual((out / NAMES[("native", "evidence").index(role)]).read_bytes(), expected)
                    self.assertIn(expected, observed)
                    if role == "manifest" or target > 33554432: self.assertFalse(out.exists())

    def test_PT11_nine_frozen_encoded_brief_vectors(self):
        vectors = self.expected["nine_brief_vectors"]; self.assertEqual(len(vectors), 9)
        for row in vectors:
            with self.subTest(vector=row["id"]):
                scope = row["scope_prefix"] + "x" * row["x_count"]
                self.assertEqual((len(scope.encode("utf-8")), sha(scope.encode("utf-8"))), (row["scope_utf8_bytes"], row["scope_raw_sha256"]))
                m, nr, er, mr = self.manifest(scope=scope, role=row["metadata"]["responsible_role"], reference=row["metadata"]["company_reference"])
                self.assertEqual(sha(mr), row["manifest_raw_sha256"]); self.assertEqual(m["package_id"], row["package_id"])
                operation, format = row["surface"].split("-"); expected = self.brief(m, mr, operation, format)
                self.assertEqual((len(expected), sha(expected)), (row["size"], row["sha256"]))
                self.assertTrue(expected.endswith(b"\n") and not expected.endswith(b"\n\n") and b"\r\n" not in expected)
                out = self.root / row["id"]
                if operation == "inspect":
                    self.package(out, parts=(m, nr, er, mr))
                    actual = self.inspect_cli(out, success=row["success"], format=format)
                    if row["success"]: self.assertEqual(actual, expected)
                else:
                    # Deliberately bypass the OS argv-size limit; exercise the actual parser/main.
                    argv = ["export", "--root", str(self.root), "--embedded-model", str(self.input), "--out", str(out),
                            "--owned-scope", scope, "--responsible-role", row["metadata"]["responsible_role"],
                            "--company-reference", row["metadata"]["company_reference"]]
                    stdout = io.BytesIO(); wrapper = io.TextIOWrapper(stdout, encoding="utf-8", write_through=True); stderr = io.StringIO()
                    with patch.object(sys, "stdout", wrapper), patch.object(sys, "stderr", stderr): code = h.main(argv)
                    actual = stdout.getvalue(); wrapper.detach()
                    self.assertEqual(code, 0 if row["success"] else 1)
                    self.assertEqual(actual, expected if row["success"] else b"")
                    self.assertEqual(out.exists(), row["success"])
                    if not row["success"]: self.assertEqual(stderr.getvalue(), "handoff refused: handoff summary exceeds 2MiB\n")

    def test_PT12_five_rechecks_and_three_partial_write_roles(self):
        expected_parts = self.manifest()[1:]
        for stage, count in enumerate((2, 3, 4, 5, 6)):
            for sentinel in (False, True):
                with self.subTest(recheck=stage, sentinel=sentinel):
                    self.input.write_bytes(self.embedded); out = self.root / ("phase-%d-%s" % (stage, sentinel))
                    if sentinel: out.mkdir(); (out / "sentinel").write_bytes(b"keep")
                    reads = 0; original = h._read
                    def changed(path):
                        nonlocal reads
                        if path == self.input:
                            reads += 1
                            if reads == count: self.input.write_bytes(self.embedded + b" ")
                        return original(path)
                    with patch.object(h, "_read", changed):
                        self.refuse(lambda: h._export(self.export_args(out)), "selected input bytes changed" if stage < 2 else "incomplete handoff operation; explicit inspect required")
                    prefix = (0, 0, 1, 2, 3)[stage]
                    self.assertEqual(out.exists(), sentinel or stage > 0)
                    for i, name in enumerate(NAMES):
                        self.assertEqual((out / name).exists(), i < prefix)
                        if i < prefix: self.assertEqual((out / name).read_bytes(), expected_parts[i])
                    if sentinel: self.assertEqual((out / "sentinel").read_bytes(), b"keep")
                    self.assertEqual(self.input.read_bytes(), self.embedded + b" ")
        self.input.write_bytes(self.embedded)
        for index in range(3):
            for partial in (False, True):
                for sentinel in (False, True):
                    with self.subTest(write=index, partial=partial, sentinel=sentinel):
                        out = self.root / ("write-%d-%s-%s" % (index, partial, sentinel))
                        if sentinel: out.mkdir(); (out / "sentinel").write_bytes(b"keep")
                        original = h._write_exclusive
                        def failure(path, raw):
                            if path.name == NAMES[index]:
                                if partial:
                                    with path.open("xb") as stream: stream.write(raw[:7])
                                raise OSError("injected write failure")
                            original(path, raw)
                        with patch.object(h, "_write_exclusive", failure):
                            self.refuse(lambda: h._export(self.export_args(out)), "incomplete handoff operation; explicit inspect required")
                        for i, name in enumerate(NAMES):
                            self.assertEqual((out / name).exists(), i < index or (i == index and partial))
                            if i < index: self.assertEqual((out / name).read_bytes(), expected_parts[i])
                            if i == index and partial: self.assertEqual((out / name).read_bytes(), expected_parts[i][:7])
                        if sentinel: self.assertEqual((out / "sentinel").read_bytes(), b"keep")

    def test_reporting_allowed_symlink_errors_are_platform_notices(self):
        windows = OSError(errno.EINVAL, "forced Windows symlink privilege")
        windows.winerror = 1314
        cases = [("Windows1314", windows)]
        for number in sorted(SYMLINK_POSIX_UNAVAILABLE):
            for shape in ("absent", "none"):
                error = OSError(number, "forced POSIX symlink unavailable")
                if shape == "none": error.winerror = None
                elif hasattr(error, "winerror"): del error.winerror
                cases.append(("POSIX-%d-%s" % (number, shape), error))
        for label, error in cases:
            with self.subTest(allowed=label):
                stderr = io.StringIO()
                with patch.object(Path, "symlink_to", side_effect=error) as link, patch.object(sys, "stderr", stderr):
                    self._check_escaping_symlink()
                link.assert_called_once()
                text = stderr.getvalue()
                lines = [line for line in text.splitlines() if line]
                self.assertEqual(len(lines), 1)
                self.assertTrue(lines[0].startswith("SKIP [platform] PT08 escaping-symlink creation unavailable: "))
                self.assertIn("errno=" + str(error.errno), lines[0])
                self.assertIn("winerror=" + str(getattr(error, "winerror", None)), lines[0])
                cases_skipped, platform, other = self._coverage_notices(text)
                self.assertEqual(cases_skipped, 0); self.assertEqual(len(platform), 1); self.assertEqual(other, [])

    def test_reporting_unexpected_symlink_errors_are_test_errors(self):
        cases = []
        for number in (errno.ENOENT, errno.EIO, errno.ENOSPC, errno.EINVAL):
            error = OSError(number, "forced unexpected symlink IO")
            error.winerror = None
            cases.append(("errno-" + str(number), error))
        for code, number in ((5, errno.EACCES), (87, errno.EINVAL)):
            error = OSError(number, "forced unexpected Windows symlink IO")
            error.winerror = code
            cases.append(("winerror-" + str(code), error))
        for label, error in cases:
            with self.subTest(unexpected=label):
                result = unittest.TestResult(); stderr = io.StringIO()
                case = unittest.FunctionTestCase(self._check_escaping_symlink)
                with patch.object(Path, "symlink_to", side_effect=error) as link, patch.object(sys, "stderr", stderr):
                    case.run(result)
                link.assert_called_once()
                self.assertEqual(result.testsRun, 1); self.assertEqual(len(result.errors), 1)
                self.assertEqual(result.failures, []); self.assertEqual(result.skipped, [])
                self.assertIn("forced unexpected", result.errors[0][1])
                self.assertEqual(stderr.getvalue(), "")
                self.assertEqual(self._coverage_notices(stderr.getvalue()), (0, [], []))

    def test_reporting_success_runs_actual_escape_check_without_notice(self):
        original = Path.symlink_to
        def create(link, target, target_is_directory=False):
            if os.name == "nt":
                p = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], capture_output=True)
                self.assertEqual(p.returncode, 0, p.stderr)
            else:
                original(link, target, target_is_directory=target_is_directory)
        stderr = io.StringIO()
        with patch.object(Path, "symlink_to", create), patch.object(h, "_export", wraps=h._export) as actual, patch.object(sys, "stderr", stderr):
            self._check_escaping_symlink()
        self.assertEqual(actual.call_count, 1)
        self.assertEqual(stderr.getvalue(), "")
        self.assertEqual(self._coverage_notices(stderr.getvalue()), (0, [], []))


if __name__ == "__main__":
    unittest.main(verbosity=2)
