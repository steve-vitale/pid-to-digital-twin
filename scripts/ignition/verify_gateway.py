"""Verify the twin inside a running Ignition gateway. The acceptance test from docs/IGNITION_BUILD.md.

Every check reads the running gateway (REST export for configuration, its OPC UA server for live data), never our
own generated files alone. Our files are the claim; the gateway is the evidence.

  V1 import fidelity      what the gateway holds == what we sent, both ways (tags and screens)
  V2 reconciliation       every twin item has exactly one tag, and every tag maps back to a twin item
  V3 binding resolution   every screen binding names a tag that exists; every drawn instrument has a binding
  V4 quality honesty      fed tags read Good; tags with no source read not-Good; no false-good
  V5 liveness             fed tags' timestamps advance (a Good value that never changes is stale)
  V6 plausibility         live values inside the engineering range the gateway holds (reported, never clipped)
  V7 read-only            config marks every process tag read-only, and a real write attempt is refused
  V8 alarm pipeline       normal replay: no alarm; fault replay: the reactor pressure alarm goes active
  V9 change record        a backup matching the build record exists, the config is in git, a dated receipt is written

Usage:
  python scripts/ignition/verify_gateway.py            all checks (starts and stops the TE replay itself)
  python scripts/ignition/verify_gateway.py --controls plant each known fault, confirm it is caught, restore
The TE replay must not already be running on port 4841: the verifier drives it (normal, then the fault case).
"""
import argparse
import asyncio
import datetime
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import time
import zipfile
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gw  # noqa: E402
gw._load_env()
import build_gateway as bg  # noqa: E402
import build_views as bv  # noqa: E402
import ua_client  # noqa: E402
from asyncua import ua  # noqa: E402

ROOT = bg.ROOT
OUT = bg.OUT
P = bg.PROVIDER
SIM = ROOT / "scripts" / "ignition" / "te_sim_server.py"
LIMIT = 15  # failures listed per check in the receipt


def result(check, name, principle, passed, counts, failures=(), note=""):
    failures = list(failures)
    return {"id": check, "name": name, "principle": principle, "passed": bool(passed), "counts": counts,
            "failures": failures[:LIMIT], "failure_count": len(failures), "note": note}


# ---------------------------------------------------------------- what the gateway holds

class Held:
    def __init__(self, g):
        s, self.provider = g.get(f"/data/api/v1/tags/export?provider={P}&type=json&recursive=true&includeUdts=true")
        bg.check(s, self.provider, "tag export")
        s, data = g.get(f"/data/api/v1/projects/export/{bv.PROJECT}", raw=True)
        bg.check(s, data[:200], "project export")
        z = zipfile.ZipFile(io.BytesIO(data))
        self.views = {n.split("/views/")[1][:-len("/view.json")]: json.loads(z.read(n))
                      for n in z.namelist() if "/views/" in n and n.endswith("/view.json")}
        s, self.conn = g.get(f"/data/api/v1/resources/find/ignition/opc-connection/{bg.OPC_CONN}")
        bg.check(s, self.conn, "read OPC connection")
        self.types = {t["name"]: t for t in self.folder("_types_")["tags"]}

    def folder(self, name):
        return next(t for t in self.provider["tags"] if t["name"] == name)

    def instances(self, root):
        """(path, instance) for every UDT instance under a top-level folder."""
        out = []

        def walk(node, path):
            for t in node.get("tags", []):
                p = f"{path}/{t['name']}"
                if t.get("tagType") == "UdtInstance":
                    out.append((p, t))
                elif t.get("tagType") == "Folder":
                    walk(t, p)
        walk(self.folder(root), root)
        return out

    def member(self, inst, name):
        """Effective member config: the type's member with the instance's overrides applied."""
        base = next((m for m in self.types[inst["typeId"]]["tags"] if m["name"] == name), None)
        if base is None:
            return None
        over = next((m for m in inst.get("tags", []) if m["name"] == name), {})
        return {**base, **over}

    def tag_paths(self):
        paths = set()
        for root in ("TE_Plant", "OPEN100"):
            for p, inst in self.instances(root):
                for m in self.types[inst["typeId"]]["tags"]:
                    paths.add(f"[{P}]{p}/{m['name']}")
        return paths


# ---------------------------------------------------------------- V1

def diff(sent, held, path, out):
    if isinstance(sent, dict) and isinstance(held, dict):
        for k in sorted(set(sent) | set(held)):
            if k == "tags":
                s_by = {t["name"]: t for t in sent.get("tags", [])}
                h_by = {t["name"]: t for t in held.get("tags", [])}
                for n in sorted(set(s_by) | set(h_by)):
                    if n not in h_by:
                        out.append(f"{path}/{n}: sent, not held")
                    elif n not in s_by:
                        # Instances list every member; a member with no overrides is a stub, not a difference.
                        if set(h_by[n]) - {"name", "tagType"}:
                            out.append(f"{path}/{n}: held, never sent")
                    else:
                        diff(s_by[n], h_by[n], f"{path}/{n}", out)
            elif k not in held:
                out.append(f"{path}.{k}: sent, not held")
            elif k not in sent:
                out.append(f"{path}.{k}: held, never sent ({json.dumps(held[k])[:60]})")
            else:
                diff(sent[k], held[k], f"{path}.{k}", out)
    elif isinstance(sent, list) and isinstance(held, list):
        if len(sent) != len(held):
            out.append(f"{path}: {len(sent)} sent, {len(held)} held")
        for i, (a, b) in enumerate(zip(sent, held)):
            diff(a, b, f"{path}[{i}]", out)
    elif isinstance(sent, (int, float)) and isinstance(held, (int, float)) and not isinstance(sent, bool):
        if abs(sent - held) > 1e-9 * max(1.0, abs(sent)):
            out.append(f"{path}: sent {sent}, held {held}")
    elif sent != held:
        out.append(f"{path}: sent {json.dumps(sent)[:60]}, held {json.dumps(held)[:60]}")


def v1(held, sent_doc, sent_views):
    out = []
    diff(sent_doc, held.provider, "", out)
    for name in sorted(set(sent_views) | set(held.views)):
        if name not in held.views:
            out.append(f"view {name}: sent, not held")
        elif name not in sent_views:
            out.append(f"view {name}: held, never sent")
        else:
            diff(sent_views[name], held.views[name], f"view {name}", out)
    n_nodes = sum(1 for _ in re.finditer(r'"tagType"', json.dumps(sent_doc)))
    return result("V1", "Import fidelity", "Configuration is what the gateway holds, not what was sent", not out,
                  {"tag_nodes_sent": n_nodes, "views_sent": len(sent_views), "differences": len(out)}, out)


# ---------------------------------------------------------------- V2

def v2(held, te_model, twin_model):
    fails = []
    te_tags = [i["tag"] for i in te_model["instruments"] + te_model["final_elements"]]
    held_te = Counter(inst["parameters"]["Tag"]["value"] for _, inst in held.instances("TE_Plant"))
    twin_ids = [x["id"] for k in ("units", "instruments", "line_items") for x in twin_model[k]]
    held_tw = Counter(inst["parameters"]["AssetId"]["value"] for _, inst in held.instances("OPEN100"))
    for label, want, have in (("TE", te_tags, held_te), ("OPEN100", twin_ids, held_tw)):
        for item in want:
            if have[item] == 0:
                fails.append(f"{label} {item}: twin item with no tag")
            elif have[item] > 1:
                fails.append(f"{label} {item}: {have[item]} tags for one item")
        for item in set(have) - set(want):
            fails.append(f"{label} {item}: tag with no twin item")
    return result("V2", "Reconciliation", "One asset, one tag", not fails,
                  {"te_items": len(te_tags), "te_tags": sum(held_te.values()), "open100_items": len(twin_ids),
                   "open100_tags": sum(held_tw.values())}, fails)


# ---------------------------------------------------------------- V3

def bindings(view):
    out = []

    def walk(c):
        for prop, cfg in (c.get("propConfig") or {}).items():
            b = cfg.get("binding", {})
            if b.get("type") == "tag":
                out.append((c["meta"]["name"], prop, b["config"]["tagPath"]))
            elif b.get("type") == "expr":
                for p in re.findall(r"\{(\[[^}]+)\}", b["config"]["expression"]):
                    out.append((c["meta"]["name"], prop, p))
        for k in c.get("children", []):
            walk(k)
    walk(view["root"])
    return out


def v3(held, twin_dir):
    tags = held.tag_paths()
    fails, n = [], 0
    for name, view in sorted(held.views.items()):
        bound = bindings(view)
        n += len(bound)
        for comp, prop, path in bound:
            if path not in tags:
                fails.append(f"{name} {comp} {prop}: no such tag {path}")
        on_screen = {comp for comp, prop, _ in bound if prop == "props.text"}
        if name == "TE/Overview":
            drawn = set(re.findall(r'data-tag="([^"]+)"', (ROOT / "out/svg/overview.svg").read_text(encoding="utf-8")))
        else:
            svg = (twin_dir / "svg" / f"sheet_{name.split('_')[-1]}.svg").read_text(encoding="utf-8")
            drawn = set(re.findall(r'data-asset="([^"]+)"[^>]*data-class="instrumentation"', svg))
        for item in sorted(drawn - on_screen):
            fails.append(f"{name}: instrument {item} drawn but not bound")
    return result("V3", "Binding resolution", "A broken binding shows as a quality error on screen", not fails,
                  {"views": len(held.views), "bindings": n}, fails)


# ---------------------------------------------------------------- live reads (OPC UA)

async def read_many(c, ns, paths):
    nodes = [c.get_node(f"ns={ns};s={p}") for p in paths]
    out = {}
    for i in range(0, len(nodes), 200):
        params = ua.ReadParameters()
        for n in nodes[i:i + 200]:
            rv = ua.ReadValueId()
            rv.NodeId = n.nodeid
            rv.AttributeId = ua.AttributeIds.Value
            params.NodesToRead.append(rv)
        res = await c.uaclient.read(params)
        for p, dv in zip(paths[i:i + 200], res):
            out[p] = dv
    return out


def live_sets(held, meta):
    te, te_nodata, tw = [], [], []
    for p, inst in held.instances("TE_Plant"):
        tag = inst["parameters"]["Tag"]["value"]
        (te if meta["te_ranges"][tag]["has_data"] else te_nodata).append((f"[{P}]{p}/PV", p, inst))
    for p, inst in held.instances("OPEN100"):
        if any(m["name"] == "PV" for m in held.types[inst["typeId"]]["tags"]):  # instruments carry a PV
            tw.append((f"[{P}]{p}/PV", p, inst))
    return te, te_nodata, tw


def v4(reads, te, te_nodata, tw):
    fails, dist = [], Counter()
    for path, *_ in te:
        q = reads[path].StatusCode
        dist["TE fed: " + q.name] += 1
        if not q.is_good():
            fails.append(f"{path}: fed by the replay but reads {q.name}")
    for label, group in (("TE no source", te_nodata), ("OPEN100 placeholder", tw)):
        for path, *_ in group:
            q = reads[path].StatusCode
            dist[f"{label}: {q.name}"] += 1
            if q.is_good():
                fails.append(f"{path}: FALSE GOOD, no data source but reads Good ({reads[path].Value.Value})")
    return result("V4", "Quality honesty", "Tag quality carries the truth; no placeholder ever reads Good", not fails,
                  {"fed": len(te), "no_source": len(te_nodata), "placeholders": len(tw),
                   "quality": dict(sorted(dist.items()))}, fails)


def v5(first, second, te):
    fails, changed = [], 0
    for path, *_ in te:
        a, b = first[path], second[path]
        if not (a.StatusCode.is_good() and b.StatusCode.is_good()):
            continue  # V4 reports quality
        if not (a.SourceTimestamp and b.SourceTimestamp and b.SourceTimestamp > a.SourceTimestamp):
            fails.append(f"{path}: timestamp did not advance ({a.SourceTimestamp} -> {b.SourceTimestamp})")
        changed += a.Value.Value != b.Value.Value
    return result("V5", "Liveness", "A Good value that never changes is stale", not fails,
                  {"fed": len(te), "values_changed": changed}, fails)


def v6(held, reads, te):
    fails, checked = [], 0
    for path, _, inst in te:
        dv = reads[path]
        if not dv.StatusCode.is_good():
            continue
        m = held.member(inst, "PV")
        lo, hi, v = m.get("engLow"), m.get("engHigh"), dv.Value.Value
        if lo is None or hi is None:
            fails.append(f"{path}: no engineering range held")
            continue
        checked += 1
        if not lo <= v <= hi:
            fails.append(f"{path}: {v} outside {lo}-{hi} {m.get('engUnit', '')}")
    return result("V6", "Plausibility", "Engineering limits belong on the tag; out-of-range is reported, never clipped",
                  not fails, {"checked": checked}, fails)


async def v7(held, c, ns, te, tw):
    fails, attempts = [], []
    for name, t in held.types.items():
        for m in t["tags"]:
            if m.get("valueSource") == "opc" and not m.get("readOnly"):
                fails.append(f"type {name}/{m['name']}: OPC member not read-only")
    for root in ("TE_Plant", "OPEN100"):
        for p, inst in held.instances(root):
            for over in inst.get("tags", []):
                if over.get("readOnly") is False:
                    fails.append(f"{p}/{over['name']}: instance overrides read-only to writable")
    if not held.conn["config"]["profile"].get("readOnly"):
        fails.append(f"OPC connection {bg.OPC_CONN} is not read-only")
    # Positive control first: the same client must be able to write somewhere (a review workflow field, written
    # with its current value). If it can't write at all, a refused write below would prove nothing.
    review = tw[0][0].rsplit("/", 1)[0] + "/ReviewStatus"
    node = c.get_node(f"ns={ns};s={review}")
    try:
        current = (await node.read_data_value(raise_on_bad_status=False)).Value.Value
        await node.write_value(ua.DataValue(ua.Variant(current, ua.VariantType.String)))
        attempts.append(f"{review}: write accepted (positive control: this client CAN write)")
    except ua.UaStatusCodeError as e:
        fails.append(f"positive control failed: the verifier could not write {review} ({type(e).__name__}), so "
                     f"refused writes below would prove nothing")
    for path in [te[0][0], tw[0][0]]:
        node = c.get_node(f"ns={ns};s={path}")
        try:
            await node.write_value(ua.DataValue(ua.Variant(12345.0, ua.VariantType.Double)))
            attempts.append(f"{path}: write ACCEPTED")
            fails.append(f"{path}: an outside client's write was accepted")
        except ua.UaStatusCodeError as e:
            attempts.append(f"{path}: refused ({type(e).__name__})")
    memory = sum(1 for _, inst in held.instances("OPEN100")
                 if any(m.get("valueSource") == "memory" for m in held.types[inst["typeId"]]["tags"]))
    return result("V7", "Read-only enforcement", "Monitoring, not control", not fails,
                  {"write_attempts": attempts, "workflow_fields_writable_by_design": memory}, fails,
                  "Write attempts use a ReadWrite OPC UA user on purpose: a refusal must come from the tags, "
                  "not from a client that lacked rights. ReviewStatus memory fields are review workflow, not process.")


# ---------------------------------------------------------------- V8 (drives the replay)

class Sim:
    def __init__(self):
        self.proc = None

    def start(self, run, start=0, rate=1.0):
        self.stop()
        self.proc = subprocess.Popen([sys.executable, str(SIM), "--run", run, "--start", str(start), "--rate", str(rate)],
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            self.proc.wait(10)
        self.proc = None


async def wait_fed(c, ns, path, seconds=120):
    deadline = time.time() + seconds
    last = None
    while time.time() < deadline:
        dv = (await read_many(c, ns, [path]))[path]
        if dv.StatusCode.is_good() and last is not None and dv.SourceTimestamp != last:
            return True
        last = dv.SourceTimestamp if dv.StatusCode.is_good() else None
        await asyncio.sleep(1)
    return False


async def v8(c, ns, sim):
    pv, aa = f"[{P}]TE_Plant/R-101/PI-107/PV", f"[{P}]TE_Plant/R-101/PI-107/AlarmActive"
    other = f"[{P}]TE_Plant/R-101/TI-109/AlarmActive"
    fails, log = [], []
    r = await read_many(c, ns, [pv, aa, other])
    log.append(f"normal: PV {r[pv].Value.Value} {r[pv].StatusCode.name}, AlarmActive {r[aa].Value.Value} "
               f"{r[aa].StatusCode.name}, TI-109 AlarmActive {r[other].Value.Value}")
    for p in (aa, other):
        if not r[p].StatusCode.is_good():
            fails.append(f"normal: {p} reads {r[p].StatusCode.name}; a broken alarm signal can't count as 'no alarm'")
        elif r[p].Value.Value:
            fails.append(f"normal: {p} active during normal operation")

    sim.start("fault6", start=250, rate=0.5)
    if not await wait_fed(c, ns, pv):
        fails.append("fault: gateway never received the fault replay")
        return result("V8", "Alarm pipeline", "Alarms are configured on the tag and proven, not assumed", False,
                      {"log": log}, fails)
    crossed = active = None
    t0 = time.time()
    peak = 0.0
    while time.time() - t0 < 90 and active is None:
        r = await read_many(c, ns, [pv, aa, other])
        v = r[pv].Value.Value if r[pv].StatusCode.is_good() else None
        if v is not None:
            peak = max(peak, v)
            if crossed is None and v > bg.ALARMS["PI-107"][0]["setpointA"]:
                crossed = time.time()
                log.append(f"fault: PV crossed {bg.ALARMS['PI-107'][0]['setpointA']} at {v}")
        if r[aa].StatusCode.is_good() and r[aa].Value.Value:
            active = time.time()
            log.append(f"fault: AlarmActive True, PV {v}")
        await asyncio.sleep(0.5)
    r = await read_many(c, ns, [other])
    if crossed is None:
        fails.append(f"fault: PV never crossed the setpoint (peak {peak})")
    if active is None:
        fails.append("fault: PI-107 alarm never went active")
    elif crossed is not None and active - crossed > 10:
        fails.append(f"fault: alarm went active {active - crossed:.1f}s after the crossing (limit 10s)")
    if r[other].Value.Value:
        fails.append("fault: TI-109 alarm active, but reactor temperature never reaches 175 degC in this run")
    delay = round(active - crossed, 1) if active and crossed else None
    return result("V8", "Alarm pipeline", "Alarms are configured on the tag and proven, not assumed", not fails,
                  {"log": log, "pv_peak_kPa": peak, "alarm_delay_s": delay}, fails,
                  "PressureShutdown (above 3000 kPa) is not expected to activate: the recorded run holds at "
                  "exactly 3000.0 kPa when the simulator shuts down. Reported, not tuned.")


# ---------------------------------------------------------------- V9

def v9(stamp):
    fails = []
    rec = json.loads((OUT / "last_build.json").read_text(encoding="utf-8"))
    b = rec["backup"]
    path = Path(os.environ.get("IGNITION_BACKUP_DIR", "")) / b["file"]
    if not path.exists():
        fails.append(f"backup {b['file']} not found")
    elif hashlib.sha256(path.read_bytes()).hexdigest() != b["sha256"]:
        fails.append(f"backup {b['file']} does not match its recorded checksum")
    tracked = ["out/ignition/gateway/twin_provider.json", f"out/ignition/gateway/{bv.PROJECT}.zip",
               "out/ignition/gateway/build_meta.json"]
    for f in tracked:
        if subprocess.run(["git", "ls-files", "--error-unmatch", f], cwd=ROOT, capture_output=True).returncode:
            fails.append(f"{f} is not in git")
        elif subprocess.run(["git", "diff", "--quiet", "HEAD", "--", f], cwd=ROOT).returncode:
            fails.append(f"{f} has uncommitted changes: the gateway config would not match any commit")
    head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    return result("V9", "Change record", "Gateway backups and versioned configuration", not fails,
                  {"backup": b["file"], "backup_sha256": b["sha256"][:16], "commit": head,
                   "receipt": f"out/ignition/gateway/receipts/{stamp}.json"}, fails)


# ---------------------------------------------------------------- orchestration

def sent():
    doc = json.loads((OUT / "twin_provider.json").read_text(encoding="utf-8"))
    z = zipfile.ZipFile(OUT / f"{bv.PROJECT}.zip")
    views = {n.split("/views/")[1][:-len("/view.json")]: json.loads(z.read(n))
             for n in z.namelist() if "/views/" in n and n.endswith("/view.json")}
    return doc, views


def models():
    meta = json.loads((OUT / "build_meta.json").read_text(encoding="utf-8"))
    te = json.loads(bg.MODEL.read_text(encoding="utf-8"))
    twin_dir = ROOT / meta["twin_source"]
    return meta, te, json.loads((twin_dir / "plant_model.json").read_text(encoding="utf-8")), twin_dir


async def run_all(g, only=None, sim=None, te_override=None):
    held = Held(g)
    doc, views = sent()
    meta, te_model, twin_model, twin_dir = models()
    te_model = te_override or te_model
    want = lambda k: only is None or k in only  # noqa: E731
    out = []
    if want("V1"):
        out.append(v1(held, doc, views))
    if want("V2"):
        out.append(v2(held, te_model, twin_model))
    if want("V3"):
        out.append(v3(held, twin_dir))
    if any(want(k) for k in ("V4", "V5", "V6", "V7", "V8")):
        te, te_nodata, tw = live_sets(held, meta)
        c = await ua_client.connect()
        async with c:
            ns = await ua_client.tag_ns(c)
            if sim:
                sim.start("normal")
                if not await wait_fed(c, ns, te[0][0]):
                    raise SystemExit("the gateway is not receiving the TE replay; is port 4841 free?")
            paths = [p for p, *_ in te + te_nodata + tw]
            first = await read_many(c, ns, paths)
            await asyncio.sleep(6)
            second = await read_many(c, ns, paths)
            if want("V4"):
                out.append(v4(second, te, te_nodata, tw))
            if want("V5"):
                out.append(v5(first, second, te))
            if want("V6"):
                out.append(v6(held, second, te))
            if want("V7"):
                out.append(await v7(held, c, ns, te, tw))
            if want("V8") and sim:
                out.append(await v8(c, ns, sim))
    return out


def write_receipt(stamp, results, controls=None):
    rec_dir = OUT / "receipts"
    rec_dir.mkdir(parents=True, exist_ok=True)
    body = {"utc": stamp, "gateway": "Ignition 8.3.10 (trial), local", "provider": P, "project": bv.PROJECT,
            "passed": all(r["passed"] for r in results), "checks": results}
    if controls is not None:
        body["negative_controls"] = controls
    (rec_dir / f"{stamp}.json").write_text(json.dumps(body, indent=1, default=str), encoding="utf-8")
    lines = [f"# Gateway verification {stamp}", "", f"Overall: **{'PASS' if body['passed'] else 'FAIL'}**", "",
             "| Check | Result | Counts |", "|---|---|---|"]
    for r in results:
        counts = ", ".join(f"{k}: {v}" for k, v in r["counts"].items() if not isinstance(v, (list, dict)))
        lines.append(f"| {r['id']} {r['name']} | {'PASS' if r['passed'] else 'FAIL'} | {counts} |")
    if controls:
        lines += ["", "## Negative controls (each fault planted on purpose; the verifier must catch it)", "",
                  "| Fault planted | Expected catch | Caught? | Restored? |", "|---|---|---|---|"]
        for ct in controls:
            lines.append(f"| {ct['fault']} | {ct['check']} | {'yes' if ct['caught'] else 'NO'} | "
                         f"{'yes' if ct['restored'] else 'NO'} |")
    (rec_dir / f"{stamp}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def print_results(results):
    for r in results:
        print(f"{r['id']} {r['name']:<22} {'PASS' if r['passed'] else 'FAIL'}  "
              f"{json.dumps(r['counts'], default=str)[:220]}")
        for f in r["failures"][:5]:
            print("     -", f)


# ---------------------------------------------------------------- negative controls

def import_doc(g, doc):
    s, b = g.post(f"/data/api/v1/tags/import?provider={P}&path=&type=json&collisionPolicy=Overwrite",
                  json.dumps(doc).encode(), ctype="application/octet-stream")
    bg.check(s, b, "control import")


def import_views(g, views_override):
    doc, _ = sent()
    src = zipfile.ZipFile(OUT / f"{bv.PROJECT}.zip")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for n in src.namelist():
            data = src.read(n)
            key = n.split("/views/")[1][:-len("/view.json")] if "/views/" in n and n.endswith("view.json") else None
            if key in views_override:
                data = json.dumps(views_override[key]).encode()
            z.writestr(n, data)
    s, b = g.post(f"/data/api/v1/projects/import/{bv.PROJECT}?overwrite=true", buf.getvalue(), ctype="application/zip")
    bg.check(s, b, "control project import")


def restore(g):
    """Fresh rebuild of the provider from the committed file, plus the committed screens."""
    doc, _ = sent()
    s, cur = g.get(f"/data/api/v1/resources/find/ignition/tag-provider/{P}")
    s, b = g.post("/data/api/v1/resources/delete/ignition/tag-provider?confirm=true",
                  [{"name": P, "signature": cur["signature"]}])
    bg.check(s, b, "restore: delete provider")
    time.sleep(3)
    s, b = g.post("/data/api/v1/resources/ignition/tag-provider", [{
        "name": P, "enabled": True, "description": cur.get("description"), "config": cur["config"]}])
    bg.check(s, b, "restore: create provider")
    bg.wait_healthy(g, "ignition/tag-provider", P)
    import_doc(g, doc)
    import_views(g, {})
    time.sleep(5)


async def controls(g):
    doc, views = sent()
    out = []

    def find_inst(d, root, pred):
        def walk(n):
            for t in n.get("tags", []):
                if t.get("tagType") == "UdtInstance" and pred(t):
                    return t
                r = walk(t) if t.get("tagType") == "Folder" else None
                if r:
                    return r
        return walk(next(t for t in d["tags"] if t["name"] == root))

    async def run(fault, check, plant, te_override=None):
        plant()
        time.sleep(5)
        r = (await run_all(g, only={check}, te_override=te_override))[0]
        caught = not r["passed"]
        print(f"control: {fault} -> {check} {'CAUGHT' if caught else 'MISSED'}: {r['failures'][:1]}")
        if te_override is None:
            restore(g)
        back = (await run_all(g, only={check, "V1"}))
        restored = all(x["passed"] for x in back)
        out.append({"fault": fault, "check": check, "caught": caught, "restored": restored,
                    "evidence": r["failures"][:3]})

    # 1. a UDT member deleted after import
    d1 = json.loads(json.dumps(doc))
    t = next(t for t in d1["tags"][0]["tags"] if t["name"] == "TE_AlarmedMeasurement")
    t["tags"] = [m for m in t["tags"] if m["name"] != "AlarmActive"]
    await run("UDT member AlarmActive deleted from TE_AlarmedMeasurement", "V1", lambda: import_doc(g, d1))

    # 2. a twin instrument with no tag (the model gains an item the gateway never got)
    te_model = json.loads(bg.MODEL.read_text(encoding="utf-8"))
    te_model["instruments"].append({"tag": "PI-999", "unit": "R-101", "uom": "kPa g", "description": "planted",
                                    "xmeas": 7})
    await run("twin instrument PI-999 with no tag", "V2", lambda: None, te_override=te_model)

    # 3. a screen binding pointing at a misspelled tag path
    v3v = json.loads(json.dumps(views["TE/Overview"]))
    lab = v3v["root"]["children"][1]
    lab["propConfig"]["props.text"]["binding"]["config"]["tagPath"] = \
        lab["propConfig"]["props.text"]["binding"]["config"]["tagPath"].replace("/PV", "/PVV")
    await run(f"binding on {lab['meta']['name']} misspelled (/PVV)", "V3",
              lambda: import_views(g, {"TE/Overview": v3v}))

    # 4. a placeholder tag forced to read Good from a memory value
    d4 = json.loads(json.dumps(doc))
    inst = find_inst(d4, "OPEN100", lambda t: t["typeId"].startswith("Instrument_"))
    inst["tags"] = [{"name": "PV", "tagType": "AtomicTag", "valueSource": "memory", "value": 0.0}]
    await run(f"placeholder {inst['name']} forced Good via a memory value", "V4", lambda: import_doc(g, d4))

    # 5. a twin tag left writable
    d5 = json.loads(json.dumps(doc))
    inst = find_inst(d5, "TE_Plant", lambda t: t["name"] == "FI-101")
    inst["tags"][0]["readOnly"] = False
    await run("TE_Plant FI-101 PV left writable", "V7", lambda: import_doc(g, d5))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--controls", action="store_true", help="plant each known fault, confirm it is caught, restore")
    ap.add_argument("--no-sim", action="store_true", help="skip V5/V8 replay control (a replay is already running)")
    args = ap.parse_args()
    g = gw.Gateway()
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    sim = None if args.no_sim else Sim()
    try:
        ctl = None
        if args.controls:
            if sim:
                sim.start("normal")
            ctl = asyncio.run(controls(g))
        results = asyncio.run(run_all(g, sim=sim))
    finally:
        if sim:
            sim.stop()
    results.append(v9(stamp))
    print_results(results)
    write_receipt(stamp, results, ctl)
    print(f"receipt: out/ignition/gateway/receipts/{stamp}.md")
    sys.exit(0 if all(r["passed"] for r in results) and all(c["caught"] and c["restored"] for c in ctl or []) else 1)


if __name__ == "__main__":
    main()
