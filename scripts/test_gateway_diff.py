"""Controls for the Ignition verifier's fidelity diff (V1), runnable without a gateway.

V1 is only worth trusting if it fails when it should. These cases plant each kind of difference the gateway could
introduce, and one it must ignore (a member stub with no overrides, which Ignition lists on every instance).
"""
import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "ignition"))
from verify_gateway import diff  # noqa: E402

SENT = {"name": "", "tagType": "Provider", "tags": [
    {"name": "_types_", "tagType": "Folder", "tags": [
        {"name": "T", "tagType": "UdtType", "tags": [
            {"name": "PV", "tagType": "AtomicTag", "readOnly": True, "engHigh": 100.0},
            {"name": "AlarmActive", "tagType": "AtomicTag", "valueSource": "expr"}]}]},
    {"name": "Plant", "tagType": "Folder", "tags": [
        {"name": "PI-1", "tagType": "UdtInstance", "typeId": "T",
         "tags": [{"name": "PV", "tagType": "AtomicTag", "engUnit": "kPa"}]}]}]}


def run(name, mutate, expect_differences):
    held = copy.deepcopy(SENT)
    mutate(held)
    out = []
    diff(SENT, held, "", out)
    ok = bool(out) == expect_differences
    print(f"{'PASS' if ok else 'FAIL'}  {name}: {out[:2] if out else 'no differences'}")
    return ok


def inst(h):
    return h["tags"][1]["tags"][0]


CASES = [
    ("identical", lambda h: None, False),
    ("member stub listed on an instance is ignored",
     lambda h: inst(h)["tags"].append({"name": "AlarmActive", "tagType": "AtomicTag"}), False),
    ("float written back as an int is equal", lambda h: h["tags"][0]["tags"][0]["tags"][0].update(engHigh=100), False),
    ("member deleted from the type", lambda h: h["tags"][0]["tags"][0]["tags"].pop(1), True),
    ("override value changed", lambda h: inst(h)["tags"][0].update(engUnit="psi"), True),
    ("property added that was never sent", lambda h: inst(h)["tags"][0].update(readOnly=False), True),
    ("override with real content held but never sent",
     lambda h: inst(h)["tags"].append({"name": "AlarmActive", "tagType": "AtomicTag", "value": 1}), True),
    ("instance missing", lambda h: h["tags"][1]["tags"].clear(), True),
]

# A screen with a trend: its history binding has a "tags" list of PATHS, not named tags. The diff once crashed on it
# (it matched every "tags" list by name), so a view with a trend could never be verified.
VIEW = {"root": {"type": "ia.container.coord", "children": [
    {"type": "ia.display.sparkline", "meta": {"name": "Trend"}, "propConfig": {"props.points": {"binding": {
        "type": "tag-history", "config": {"tags": [{"path": "[Twin]Plant/PI-1/PV", "alias": "v"}]}}}}}]}}


def trend_tags(h):
    return h["root"]["children"][0]["propConfig"]["props.points"]["binding"]["config"]["tags"]


def run_view(name, mutate, expect_differences):
    held = copy.deepcopy(VIEW)
    mutate(held)
    out = []
    diff(VIEW, held, "", out)
    ok = bool(out) == expect_differences
    print(f"{'PASS' if ok else 'FAIL'}  {name}: {out[:2] if out else 'no differences'}")
    return ok


VIEW_CASES = [
    ("trend binding identical", lambda h: None, False),
    ("trend bound to a different tag", lambda h: trend_tags(h)[0].update(path="[Twin]Plant/PI-2/PV"), True),
    ("trend lost its tag", lambda h: trend_tags(h).clear(), True),
]

if __name__ == "__main__":
    results = [run(*c) for c in CASES] + [run_view(*c) for c in VIEW_CASES]
    print("all passed" if all(results) else "FAILURES")
    sys.exit(0 if all(results) else 1)
