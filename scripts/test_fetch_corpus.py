"""Offline tests for scripts/fetch_corpus.py: the pin table is well formed, changed upstream bytes are refused, zip
members are read correctly over (faked) Range requests, and the PRONTO conversion works on a tiny synthetic sample.

No network: fetch_corpus.http_get is replaced by a function that fails the test if anything calls it.
"""
import copy
import csv
import io
import json
import sys
import tempfile
import unittest
import zipfile
import zlib
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import csv_normal_bands as cnb  # noqa: E402
import fetch_corpus as fc  # noqa: E402


def _no_network(*a, **k):
    raise AssertionError("a test tried to use the network")


fc.http_get = _no_network


def ranged(blob, json_by_url=None):
    """A fake fetch: (url, None) returns json_by_url[url]; (url, (a, b)) returns blob[a:b+1]."""
    def fetch(url, byte_range):
        if byte_range is None:
            return json.dumps(json_by_url[url]).encode() if isinstance(json_by_url[url], dict) else json_by_url[url]
        a, b = byte_range
        return blob[a:b + 1]
    return fetch


def make_zip(members):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in members.items():
            z.writestr(name, data)
    blob = buf.getvalue()
    eocd = blob.rfind(b"PK\x05\x06")
    cd_size, cd_off = int.from_bytes(blob[eocd + 12:eocd + 16], "little"), int.from_bytes(blob[eocd + 16:eocd + 20],
                                                                                         "little")
    return blob, cd_off, cd_size


class PinsTest(unittest.TestCase):
    def test_pins_well_formed(self):
        self.assertEqual(fc.validate_pins(), [])
        for m in fc.SOURCES["pronto"]["members"].values():
            self.assertIsNotNone(m["sha256"], "every PRONTO member has a recorded sha256")

    def test_bad_pins_are_reported(self):
        bad = copy.deepcopy(fc.SOURCES)
        m = bad["pronto"]["members"]
        m["../escape.txt"] = dict(next(iter(m.values())))
        next(iter(m.values()))["sha256"] = "XYZ"
        bad["dtu-te"]["files"]["Readme.html"]["md5"] = "short"
        problems = " ".join(fc.validate_pins(bad))
        self.assertIn("not a safe relative path", problems)
        self.assertIn("64 lowercase hex", problems)
        self.assertIn("size/md5 malformed", problems)

    def test_check_bytes_refuses_changes(self):
        data = b"hello historian"
        crc = f"{zlib.crc32(data) & 0xffffffff:08x}"
        sha = fc.check_bytes("x", data, len(data), None, crc)
        self.assertEqual(fc.check_bytes("x", data, len(data), sha, crc), sha)
        with self.assertRaisesRegex(fc.PinError, "pinned"):
            fc.check_bytes("x", data + b"!", len(data), sha, crc)  # size
        with self.assertRaisesRegex(fc.PinError, "sha256"):
            fc.check_bytes("x", b"jello historian", len(data), sha)  # same size, different bytes
        with self.assertRaisesRegex(fc.PinError, "CRC-32"):
            fc.check_bytes("x", b"jello historian", len(data), None, crc)

    def test_safe_dest(self):
        base = Path(tempfile.gettempdir()) / "fc_base"
        self.assertTrue(str(fc.safe_dest(base, "a/b.csv")).endswith("b.csv"))
        for bad in ("../x", "/etc/passwd", "a/../../x"):
            with self.assertRaises(fc.PinError):
                fc.safe_dest(base, bad)


class ZipRangeTest(unittest.TestCase):
    def setUp(self):
        self.data = {"top/a.csv": b"t,x\n" + b"0,1.5\n" * 500, "top/b.txt": b"alarm journal"}
        self.blob, self.cd_off, self.cd_size = make_zip(self.data)

    def test_central_directory_and_member(self):
        cd = fc.parse_central_directory(self.blob[self.cd_off:self.cd_off + self.cd_size])
        self.assertEqual(sorted(cd), ["top/a.csv", "top/b.txt"])
        e = cd["top/a.csv"]
        self.assertEqual(e["size"], len(self.data["top/a.csv"]))
        got = fc.fetch_zip_member(ranged(self.blob), "u", "top/a.csv", e)
        self.assertEqual(got, self.data["top/a.csv"])
        fc.check_bytes("a", got, e["size"], None, e["crc32"])

    def test_changed_member_is_refused(self):
        cd = fc.parse_central_directory(self.blob[self.cd_off:self.cd_off + self.cd_size])
        e = cd["top/b.txt"]
        pinned_sha = fc.check_bytes("b", self.data["top/b.txt"], e["size"])
        other, cd_off, cd_size = make_zip({"top/a.csv": self.data["top/a.csv"], "top/b.txt": b"alarm journaX"})
        e2 = fc.parse_central_directory(other[cd_off:cd_off + cd_size])["top/b.txt"]
        got = fc.fetch_zip_member(ranged(other), "u", "top/b.txt", e2)
        with self.assertRaises(fc.PinError):
            fc.check_bytes("b", got, e["size"], pinned_sha, e["crc32"])

    def test_record_change_refused_before_download(self):
        s = fc.SOURCES["pronto"]
        rec = {"metadata": {"license": {"id": "cc-by-4.0"}},
               "files": [{"key": s["zip"]["key"], "size": s["zip"]["size"] + 1, "checksum": s["zip"]["checksum"]}]}
        calls = []

        def fetch(url, byte_range):
            calls.append(byte_range)
            return json.dumps(rec).encode()
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(fc.PinError, "pinned"):
                fc.fetch_pronto(500, Path(d), fetch=fetch)
            self.assertEqual(list(Path(d).iterdir()), [])
        self.assertEqual(calls, [None])  # only the record listing was read
        rec["metadata"]["license"]["id"] = "cc-by-nc-4.0"
        with tempfile.TemporaryDirectory() as d, self.assertRaisesRegex(fc.PinError, "license"):
            fc.fetch_pronto(500, Path(d), fetch=fetch)

    def test_max_mb_respected(self):
        s = fc.SOURCES["pronto"]
        rec = {"metadata": {"license": {"id": "cc-by-4.0"}},
               "files": [{"key": s["zip"]["key"], "size": s["zip"]["size"], "checksum": s["zip"]["checksum"]}]}
        with tempfile.TemporaryDirectory() as d, self.assertRaisesRegex(SystemExit, "max-mb"):
            fc.fetch_pronto(1, Path(d), fetch=lambda u, r: json.dumps(rec).encode())


class DtuTest(unittest.TestCase):
    def record(self):
        files = [{"name": n, "size": p["size"], "computed_md5": p["md5"]} for n, p in fc.SOURCES["dtu-te"]["files"].items()]
        return {"license": {"name": "CC0"}, "files": files}

    def test_skips_with_reasons_and_refuses_a_changed_readme(self):
        readme_url = fc.SOURCES["dtu-te"]["files"]["Readme.html"]["url"]
        fake = ranged(b"", {fc.SOURCES["dtu-te"]["api_url"]: self.record(), readme_url: b"x" * 8493})
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(fc.PinError, "sha256"):
                fc.fetch_dtu(500, Path(d), fetch=fake, have_h5py=False)
            self.assertFalse((Path(d) / "Readme.html").exists())

    def test_record_change_refused(self):
        rec = self.record()
        rec["files"][0]["size"] += 1
        with tempfile.TemporaryDirectory() as d, self.assertRaisesRegex(fc.PinError, "pinned"):
            fc.fetch_dtu(500, Path(d), fetch=ranged(b"", {fc.SOURCES["dtu-te"]["api_url"]: rec}), have_h5py=False)

    def test_readme_failure_still_records_skip(self):
        import urllib.error

        def fetch(url, byte_range):
            if url == fc.SOURCES["dtu-te"]["api_url"]:
                return json.dumps(self.record()).encode()
            raise urllib.error.URLError("certificate verify failed")
        with tempfile.TemporaryDirectory() as d:
            r = fc.fetch_dtu(500, Path(d), fetch=fetch, have_h5py=False)
        whats = [s["what"] for s in r["skipped"]]
        self.assertEqual(whats, ["all data files", "conversion", "Readme.html"])
        self.assertIn("TEP_Mode4.h5", r["skipped"][0]["reason"])


def synthetic_day(n=40, lead=5, fault_at=20):
    """A raw DeltaV-style export (metadata, tag, description rows; minute timestamps) and a merged file that starts
    `lead` rows into it, with 2 alarm columns, 3 process columns and a Fault label switching at merged row fault_at."""
    raw = [["Start Time", "09/11/2017 10:59", "End Time", "x", "Interval", "1s"],
           ["", "FT305/OUT.CV", "TT/OUT.CV", "PT/OUT.CV"], ["TIMESTAMP", "Air In1", "Air T", "Air P"]]
    for i in range(n + lead + 3):
        sec = 59 * 60 + i  # starts at 10:59:00
        stamp = f"09/11/2017 {10 + sec // 3600}:{(sec // 60) % 60:02d}"
        raw.append([stamp, f"{120 + i % 3}", f"{19.0 + i / 1000:.4f}", f"{1.2 + (i % 5) / 100:.3f}"])
    merged = [["ALM1", "ALM2", "AirIn", "Air.T", "Air.P", "Fault"]]
    for k in range(n):
        r = raw[3 + lead + k]
        merged.append(["0", "1" if k >= fault_at + 3 else "0", r[1], r[2], r[3],
                       "Normal" if k < fault_at else "Air leakage"])
    return merged, raw


PAIRS = {"normal": {"rows": (0, 10), "label": "Normal", "what": "n"},
         "fault": {"rows": (10, 40), "fault_label": "Air leakage", "fault_row": 20, "what": "f"}}


class ConversionTest(unittest.TestCase):
    def test_times_alignment_and_fault_start(self):
        merged, raw = synthetic_day()
        out, meta = fc.build_pronto_csvs(merged, raw, PAIRS, ("AirIn", "Air.T", "Air.P"))
        self.assertEqual(meta["alignment"]["merged_row_0_is_raw_row"], 5)
        self.assertEqual(meta["alignment"]["merged_row_0_time"], "2017-09-11 10:59:05")
        self.assertEqual(meta["alarm_columns"], ["ALM1", "ALM2"])
        text, info = out["fault"]
        self.assertEqual(info["fault_start_row"], 10)
        self.assertEqual(info["fault_start_time"], "2017-09-11 10:59:25")
        self.assertEqual(info["real_alarms"]["ALM2"], {"state_at_fault": "0", "first_new_activation_row": 13})
        self.assertIsNone(info["real_alarms"]["ALM1"]["first_new_activation_row"])
        with tempfile.TemporaryDirectory() as d:  # the output is what csv_normal_bands.py reads
            p = Path(d) / "f.csv"
            p.write_text(text, encoding="utf-8")
            tname, tags, times, rows = cnb.read_historian_csv(p)
        self.assertEqual((tname, tags), ("time", ["AirIn", "Air.T", "Air.P"]))
        self.assertEqual(times[0], datetime(2017, 9, 11, 10, 59, 15))
        self.assertEqual(rows[0], [float(x) for x in merged[11][2:5]])  # values unchanged

    def test_wrong_labels_refused(self):
        merged, raw = synthetic_day(fault_at=22)
        with self.assertRaisesRegex(ValueError, "expected Normal"):
            fc.build_pronto_csvs(merged, raw, PAIRS, ("AirIn", "Air.T", "Air.P"))

    def test_alignment_must_be_unique(self):
        merged, raw = synthetic_day()
        merged[1][3] = "99.9"  # merged row 0 matches nothing in the raw file
        with self.assertRaisesRegex(ValueError, "alignment"):
            fc.build_pronto_csvs(merged, raw, PAIRS, ("AirIn", "Air.T", "Air.P"))

    def test_raw_timestamps_checked(self):
        _, raw = synthetic_day()
        raw[3][0] = "09/11/2017 11:30"  # data row 0 stamped half an hour late
        with self.assertRaisesRegex(ValueError, "stamped"):
            fc.raw_export_times(raw)

    def test_excel_serial_stamps(self):
        t = datetime(2017, 9, 11, 16, 20, 1)
        self.assertTrue(fc.export_time_matches("42989.68057", t))
        self.assertFalse(fc.export_time_matches("42989.69057", t))
        self.assertTrue(fc.export_time_matches("09/11/2017 16:20", t))

    def test_historian_csv_text(self):
        text = fc.historian_csv_text([datetime(2017, 1, 1, 0, 0, 1)], ["A", "B"], [["1.5", ""]])
        self.assertEqual(list(csv.reader(io.StringIO(text))), [["time", "A", "B"], ["2017-01-01 00:00:01", "1.5", ""]])


class PinnedFilesTest(unittest.TestCase):
    """The per-file sources added 2026-10-29 (data/corpus_pins.json)."""

    def setUp(self):
        import hashlib
        self.src = {"name": "t", "license": "CC0", "license_url": "https://x", "attribution": "a",
                    "landing_url": "https://x", "api_url": "https://x", "kind": "pinned-files",
                    "url": "https://example.org/{path}", "skipped": "none"}
        self.data = b"hello,world\n"
        self.pin = {"bytes": len(self.data), "sha256": hashlib.sha256(self.data).hexdigest()}
        self.pins = {"t": {"dir/a.csv": self.pin}}
        fc.FILE_SOURCES["t"] = self.src

    def tearDown(self):
        fc.FILE_SOURCES.pop("t", None)

    def test_committed_pin_table_well_formed(self):
        fc.FILE_SOURCES.pop("t", None)
        pins = fc.load_pins()
        self.assertEqual(fc.validate_file_pins(pins), [])
        self.assertTrue(set(fc.FILE_SOURCES) <= set(pins))
        self.assertIn("never vendored", fc.FILE_SOURCES["skab"]["license"])

    def test_present_file_needs_no_network(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "dir").mkdir()
            (Path(d) / "dir" / "a.csv").write_bytes(self.data)
            r = fc.fetch_pinned("t", 1, Path(d), fetch=_no_network, pins=self.pins)
        self.assertEqual(r["files"][0]["status"], "already present, checks OK")

    def test_missing_file_fetched_and_changed_bytes_refused(self):
        with tempfile.TemporaryDirectory() as d:
            r = fc.fetch_pinned("t", 1, Path(d), fetch=lambda url, rng: self.data, pins=self.pins)
            self.assertEqual(r["files"][0]["status"], "fetched")
            self.assertEqual((Path(d) / "dir" / "a.csv").read_bytes(), self.data)
            (Path(d) / "dir" / "a.csv").unlink()
            with self.assertRaises(fc.PinError):
                fc.fetch_pinned("t", 1, Path(d), fetch=lambda url, rng: b"changed!!!!!\n", pins=self.pins)
            self.assertFalse((Path(d) / "dir" / "a.csv").exists())

    def test_unsafe_pin_path_reported(self):
        bad = {"t": {"../x": self.pin}}
        self.assertTrue(any("safe relative path" in p for p in fc.validate_file_pins(bad, {"t": self.src})))

    def test_zip_member_by_name(self):
        blob, off, size = make_zip({"ROOT/m.csv": self.data})
        fc.FILE_SOURCES["t"] = dict(self.src, kind="pinned-zip-members", zip_of="zz", dest_prefix="ROOT/")
        fc.SOURCES["zz"] = {"zip": {"url": "https://z", "central_directory_offset": off,
                                    "central_directory_size": size, "entries": 1}}
        try:
            pins = {"t": {"m.csv": dict(self.pin, crc32=f"{zlib.crc32(self.data) & 0xffffffff:08x}")}}
            with tempfile.TemporaryDirectory() as d:
                fc.fetch_pinned("t", 1, Path(d), fetch=ranged(blob), pins=pins)
                self.assertEqual((Path(d) / "ROOT" / "m.csv").read_bytes(), self.data)
        finally:
            fc.SOURCES.pop("zz")


if __name__ == "__main__":
    unittest.main(verbosity=1)
