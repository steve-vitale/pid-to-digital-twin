"""Build the twin into a running Ignition 8.3 gateway over its REST API. Read docs/IGNITION_BUILD.md first.

What it does, in order (each step is idempotent):
  1. Gateway backup, saved to IGNITION_BACKUP_DIR before anything changes (V9: change record).
  2. A dedicated OPC UA user for the verifier, created through the gateway's SCIM API. It is deliberately
     write-capable: the read-only check (V7) must prove the TAGS refuse writes, not that the client lacked rights.
  3. Ignition's OPC UA server: expose tag providers, so outside clients (the verifier) read what the gateway holds.
  4. OPC connection "TE-Sim" to the Tennessee Eastman replay server, marked read-only.
  5. Tag provider "Twin", separate from the default provider.
  6. One tag import: UDT types, the live TE plant (TE_Plant) and the extracted OPEN100 twin (OPEN100), placeholders
     and all. The import file is written to out/ignition/gateway/twin_provider.json first, so the verifier can diff
     what we sent against what the gateway holds (V1).
  7. Perspective project PIDTwin with one screen per drawing (scripts/ignition/build_views.py).

Usage:
  python scripts/ignition/build_gateway.py [--write-only] [--twin out/twin/r2-tiles-trace/codex]
Credentials: see scripts/ignition/gw.py. Also needs IGNITION_BACKUP_DIR and IGNITION_SECRETS_DIR (private folders).
"""
import argparse
import datetime
import hashlib
import json
import os
import secrets
import string
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gw import Gateway  # noqa: E402
import build_views  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
MODEL = ROOT / "data" / "te_process_model.json"
DATA = ROOT / "data" / "external" / "te-braatz"
OUT = ROOT / "out" / "ignition" / "gateway"
PROVIDER = "Twin"
OPC_CONN = "TE-Sim"
SIM_URL = "opc.tcp://localhost:4841/te-sim"
SIM_NS = "urn:pid-digital-twin:te-sim"  # namespace URI, not index: survives a server restart that renumbers
VERIFY_USER = "twin-verifier"
PROBE_PATH = "[default]_verifier/WriteProbe"  # the verifier's positive write control, kept outside the Twin provider

# Alarm setpoints come from published sources, never from the replay data.
ALARMS = {
    "PI-107": [
        {"name": "PressureHigh", "setpointA": 2895.0, "priority": "High",
         "source": "Downs & Vogel (1993), operating constraints: reactor pressure normal limit 2895 kPa"},
        {"name": "PressureShutdown", "setpointA": 3000.0, "priority": "Critical",
         "source": "teprob.f line 703: the simulator shuts down when XMEAS(7) > 3000 kPa"},
    ],
    "TI-109": [
        {"name": "TemperatureShutdown", "setpointA": 175.0, "priority": "Critical",
         "source": "teprob.f line 706: the simulator shuts down when XMEAS(9) > 175 degC"},
    ],
}


def eng_range(item, normal_mean):
    """Engineering range per tag, with where it came from. Ignition defaults every tag to 0-100, which would make
    a 2700 kPa pressure look out of range, so every tag gets an explicit range."""
    if item["uom"] in ("%", "mol%"):
        return 0.0, 100.0, "physical: a percentage"
    # No published instrument spans exist for TE. Assume 0 to 2x the normal-run mean, the way a span is often
    # sized, and say so. Ops confirms or corrects these in review.
    return 0.0, round(2 * abs(normal_mean), 3) or 1.0, "ASSUMED: 0 to 2x normal-run mean (d00), not a published span"


def te_columns(model):
    cols = {}
    for it in model["instruments"]:
        cols[it["tag"]] = int(str(it["xmeas"]).split("-")[0]) - 1
    for it in model["final_elements"]:
        if it["xmv"] <= 11:
            cols[it["tag"]] = 41 + it["xmv"] - 1
    return cols


def te_tags(model):
    rows = [list(map(float, l.split())) for l in (DATA / "d00_te.dat").read_text().splitlines() if l.strip()]
    cols = te_columns(model)

    def pv(kind):
        return {"name": "PV", "tagType": "AtomicTag", "valueSource": "opc", "dataType": "Float8", "readOnly": True,
                "engLimitMode": "No_Clamp",
                "documentation": f"{kind}. Read-only: the twin monitors, it never writes to the process.",
                "opcServer": {"bindType": "parameter", "binding": "{OPCServer}"},
                "opcItemPath": {"bindType": "parameter", "binding": "nsu=" + SIM_NS + ";s=TE/{Tag}"}}

    alarm_active = {"name": "AlarmActive", "tagType": "AtomicTag", "valueSource": "expr", "dataType": "Boolean",
                    "documentation": "True while any alarm on PV is active, as judged by the gateway's alarm engine.",
                    # Expression tags are event-driven by default: they re-run only when a tag they reference
                    # changes. This expression references none, so it would run once at startup (Bad if the alarm
                    # was not registered yet) and never turn True in a fault. Poll it instead.
                    "executionMode": "FixedRate", "executionRate": 1000,
                    # {PathToParentFolder} of a UDT member is the instance's own path (no provider), so PV is a
                    # direct child. Parameters are NOT substituted inside string literals: concatenate outside
                    # the quotes. A wrong path reads Bad quality, never False, so a broken alarm check can't pass.
                    "expression": 'isAlarmActive("[' + PROVIDER + ']" + {PathToParentFolder} + "/PV")'}
    params = {"Tag": {"dataType": "String", "value": ""}, "OPCServer": {"dataType": "String", "value": OPC_CONN}}
    # AlarmActive lives only on the alarmed type: isAlarmActive() on a tag with no alarms configured reads Bad.
    # Wrapping it in try() would also hide a broken path, so the type split is the honest fix.
    types = [
        {"name": "TE_Measurement", "tagType": "UdtType", "parameters": params,
         "tags": [pv("Measured process value")]},
        {"name": "TE_AlarmedMeasurement", "tagType": "UdtType", "parameters": params,
         "tags": [pv("Measured process value, with alarms"), alarm_active]},
        {"name": "TE_FinalElement", "tagType": "UdtType", "parameters": params,
         "tags": [pv("Controller output to the final element, %")]},
    ]
    units = {u["id"]: {"name": u["id"], "tagType": "Folder", "documentation": u["name"], "tags": []}
             for u in model["units"]}
    ranges = {}
    for it in model["instruments"] + model["final_elements"]:
        is_fe = "xmv" in it
        col = cols.get(it["tag"])
        mean = sum(r[col] for r in rows) / len(rows) if col is not None else 0.0
        lo, hi, why = eng_range(it, mean)
        member = {"name": "PV", "tagType": "AtomicTag", "engUnit": it["uom"], "engLow": lo, "engHigh": hi}
        if it["tag"] in ALARMS:
            member["alarms"] = [{"name": a["name"], "mode": "AboveValue", "setpointA": a["setpointA"],
                                 "priority": a["priority"], "notes": a["source"]} for a in ALARMS[it["tag"]]]
        source = f'{"XMV" if is_fe else "XMEAS"} {it.get("xmv", it.get("xmeas"))}'
        note = ""
        if col is None:
            note = " | NO DATA SOURCE: not in the replay data set, so it must read Bad, never a value"
        elif "-" in str(it.get("xmeas", "")):
            note = " | analyzer: the replay exposes the first component only"
        units[it["unit"]]["tags"].append({
            "name": it["tag"], "tagType": "UdtInstance",
            "typeId": "TE_FinalElement" if is_fe else
                      "TE_AlarmedMeasurement" if it["tag"] in ALARMS else "TE_Measurement",
            "documentation": f'{it["description"]} | {source} | range {lo}-{hi} {it["uom"]} ({why}){note}',
            "parameters": {"Tag": {"dataType": "String", "value": it["tag"]}},
            "tags": [member]})
        ranges[it["tag"]] = {"low": lo, "high": hi, "source": why, "has_data": col is not None}
    plant = {"name": "TE_Plant", "tagType": "Folder",
             "documentation": "Tennessee Eastman plant (Downs & Vogel 1993), live from the open replay data",
             "tags": list(units.values())}
    return types, plant, ranges


def twin_tags(twin_dir):
    t = json.loads((twin_dir / "ignition" / "tags.json").read_text(encoding="utf-8"))
    types = next(x for x in t["tags"] if x["name"] == "_types_")["tags"]
    site = next(x for x in t["tags"] if x["name"] != "_types_")
    site = dict(site, name="OPEN100",
                documentation=site.get("documentation", "") + " | extracted from drawings, placeholders only")
    return types, site


def build_file(twin_dir):
    model = json.loads(MODEL.read_text(encoding="utf-8"))
    te_types, plant, ranges = te_tags(model)
    tw_types, site = twin_tags(twin_dir)
    doc = {"name": "", "tagType": "Provider", "tags": [
        {"name": "_types_", "tagType": "Folder", "tags": te_types + tw_types}, plant, site]}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "twin_provider.json").write_text(json.dumps(doc, indent=1), encoding="utf-8")
    meta = {"provider": PROVIDER, "opc_connection": OPC_CONN, "sim_url": SIM_URL, "sim_namespace": SIM_NS,
            "twin_source": twin_dir.relative_to(ROOT).as_posix(), "alarms": ALARMS, "te_ranges": ranges}
    (OUT / "build_meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    return doc


def check(status, body, what):
    if status >= 300:
        raise SystemExit(f"{what} failed: HTTP {status}: {json.dumps(body)[:800]}")
    return body


def backup(g, folder):
    status, data = g.get("/data/api/v1/backup", raw=True)
    check(status, data[:200].decode("utf-8", "replace"), "backup")
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = folder / f"gateway-{stamp}.gwbk"
    path.write_bytes(data)
    digest = hashlib.sha256(data).hexdigest()
    print(f"backup: {path.name} {len(data)} bytes sha256 {digest[:16]}")
    return {"file": path.name, "bytes": len(data), "sha256": digest, "utc": stamp}


def ensure_verify_user(g, secrets_dir):
    cred = secrets_dir / "opcua-verifier.json"
    s, body = g.get("/data/api/v1/scim/opcua-module/v2/Users")
    users = {u["userName"]: u for u in check(s, body, "list OPC UA users")["Resources"]}
    if VERIFY_USER in users and cred.exists():
        return
    alphabet = string.ascii_letters + string.digits
    password = "".join(secrets.choice(alphabet) for _ in range(24))
    s, groups = g.get("/data/api/v1/scim/opcua-module/v2/Groups")
    rw = next(x["id"] for x in check(s, groups, "list OPC UA roles")["Resources"] if x["displayName"] == "ReadWrite")
    user = {"schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"], "userName": VERIFY_USER,
            "password": password, "groups": [{"value": rw}]}
    if VERIFY_USER in users:
        s, b = g.put(f"/data/api/v1/scim/opcua-module/v2/Users/{users[VERIFY_USER]['id']}", user)
    else:
        s, b = g.post("/data/api/v1/scim/opcua-module/v2/Users", user)
    check(s, b, "create OPC UA verifier user")
    secrets_dir.mkdir(parents=True, exist_ok=True)
    cred.write_text(json.dumps({"username": VERIFY_USER, "password": password}), encoding="utf-8")
    print(f"OPC UA user {VERIFY_USER}: created (ReadWrite role, on purpose; credentials kept privately)")


def put_singleton(g, rtype, mutate):
    s, cur = g.get(f"/data/api/v1/resources/singleton/{rtype}")
    cur = check(s, cur, f"read {rtype}")
    cfg = json.loads(json.dumps(cur["config"]))
    mutate(cfg)
    if cfg == cur["config"]:
        return False
    s, b = g.put(f"/data/api/v1/resources/{rtype}", [{"signature": cur["signature"], "config": cfg}])
    check(s, b, f"update {rtype}")
    return True


def same(want, have):
    """True if every key we set already has that value (the gateway adds defaults we don't send)."""
    if isinstance(want, dict):
        return isinstance(have, dict) and all(same(v, have.get(k)) for k, v in want.items())
    return want == have


def upsert(g, rtype, name, description, config):
    """Create or update. An unchanged resource is left alone: re-saving restarts it (a restarted tag provider
    briefly does not exist, and an import sent in that window fails)."""
    s, cur = g.get(f"/data/api/v1/resources/find/{rtype}/{name}")
    item = {"name": name, "enabled": True, "description": description, "config": config}
    if s == 200:
        if same(config, cur.get("config")) and cur.get("description") == description and cur.get("enabled"):
            print(f"{rtype} {name}: unchanged")
            return
        s, b = g.put(f"/data/api/v1/resources/{rtype}", [dict(item, signature=cur["signature"])])
        verb = "updated"
    else:
        s, b = g.post(f"/data/api/v1/resources/{rtype}", [item])
        verb = "created"
    check(s, b, f"{verb} {rtype} {name}")
    print(f"{rtype} {name}: {verb}")


def health(g, rtype, name):
    s, b = g.get(f"/data/api/v1/resources/find/{rtype}/{name}")
    if s != 200:
        return False, f"HTTP {s}"
    result = next(iter((b.get("healthchecks") or {}).values()), {}).get("result", {})
    return bool(result.get("healthy")), result.get("message", "")


def wait_healthy(g, rtype, name, seconds=60):
    deadline = time.time() + seconds
    while True:
        ok, msg = health(g, rtype, name)
        if ok:
            return msg
        if time.time() > deadline:
            raise SystemExit(f"{rtype} {name} not healthy after {seconds}s: {msg}")
        time.sleep(2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--twin", default="out/twin/r2-tiles-trace/codex")
    ap.add_argument("--write-only", action="store_true", help="write the import file; don't touch a gateway")
    ap.add_argument("--fresh", action="store_true",
                    help="delete and recreate the Twin provider before importing (after the backup), so nothing "
                         "from an earlier build can survive into this one")
    args = ap.parse_args()
    doc = build_file(ROOT / args.twin)
    views_zip, views = build_views.project_zip(doc, ROOT / args.twin, PROVIDER, set(ALARMS))
    (OUT / f"{build_views.PROJECT}.zip").write_bytes(views_zip)
    print(f"wrote {(OUT / 'twin_provider.json').relative_to(ROOT).as_posix()} and {build_views.PROJECT}.zip "
          f"({len(views)} views)")
    if args.write_only:
        return

    g = Gateway()
    backup_dir = Path(os.environ.get("IGNITION_BACKUP_DIR", ""))
    secrets_dir = Path(os.environ.get("IGNITION_SECRETS_DIR", ""))
    if not backup_dir.name or not secrets_dir.name:
        raise SystemExit("set IGNITION_BACKUP_DIR and IGNITION_SECRETS_DIR (private folders outside the repo)")
    record = {"backup": backup(g, backup_dir)}

    ensure_verify_user(g, secrets_dir)

    def expose(cfg):
        cfg["advanced"]["exposedTagsEnabled"] = True
    if put_singleton(g, "com.inductiveautomation.opcua/server-config", expose):
        print("OPC UA server: tag providers exposed")

    # Start from the gateway's own loopback connection settings and change only the endpoint and login. The API
    # accepts a config missing any settings block (HTTP 200), then the connection fails at runtime, one missing
    # block at a time. This also reuses the client keystore password the gateway already holds, encrypted: it
    # never appears in plaintext here or in the repo.
    s, loop = g.get("/data/api/v1/resources/find/ignition/opc-connection/Ignition%20OPC%20UA%20Server")
    settings = json.loads(json.dumps(check(s, loop, "read loopback connection")["config"]["settings"]))
    settings["endpoint"] = {"endpointUrl": SIM_URL, "discoveryUrl": SIM_URL, "hostOverride": "",
                            "securityPolicy": "None", "securityMode": "None"}
    settings["authentication"] = {"authenticationType": "ANONYMOUS"}
    upsert(g, "ignition/opc-connection", OPC_CONN,
           "Tennessee Eastman replay (open data). Read-only: the twin never writes to the process.",
           {"profile": {"type": "com.inductiveautomation.OpcUaServerType", "readOnly": True}, "settings": settings})
    if args.fresh:
        s, cur = g.get(f"/data/api/v1/resources/find/ignition/tag-provider/{PROVIDER}")
        if s == 200:
            s, b = g.post("/data/api/v1/resources/delete/ignition/tag-provider?confirm=true",
                          [{"name": PROVIDER, "signature": cur["signature"]}])
            check(s, b, "delete tag provider")
            print(f"ignition/tag-provider {PROVIDER}: deleted for a fresh build (backup {record['backup']['file']})")
            time.sleep(3)
    upsert(g, "ignition/tag-provider", PROVIDER,
           "Digital twin built from P&IDs. Kept apart from production providers.",
           {"profile": {"type": "STANDARD", "allowBackfill": False, "enableTagReferenceStore": True},
            "settings": {"valuePersistence": "Database"}})

    probe = {"name": "", "tagType": "Provider", "tags": [{"name": "_verifier", "tagType": "Folder", "tags": [
        {"name": "WriteProbe", "tagType": "AtomicTag", "valueSource": "memory", "dataType": "String", "value": "",
         "documentation": "Written by verify_gateway.py to prove its client can write (V7 positive control)."}]}]}
    s, b = g.post("/data/api/v1/tags/import?provider=default&path=&type=json&collisionPolicy=Overwrite",
                  json.dumps(probe).encode(), ctype="application/octet-stream")
    check(s, b, "write-probe import")

    wait_healthy(g, "ignition/tag-provider", PROVIDER)
    s, b = g.post(f"/data/api/v1/tags/import?provider={PROVIDER}&path=&type=json&collisionPolicy=Overwrite",
                  json.dumps(doc).encode(), ctype="application/octet-stream")
    print("tag import:", s, json.dumps(b)[:600])
    check(s, b, "tag import")
    record["import"] = {"status": s, "response": b}
    try:
        print("TE-Sim connection:", wait_healthy(g, "ignition/opc-connection", OPC_CONN, 30))
    except SystemExit as e:  # reported, not fatal: the verifier's quality checks will show the consequence
        print("WARNING:", e)

    s, b = g.post(f"/data/api/v1/projects/import/{build_views.PROJECT}?overwrite=true", views_zip,
                  ctype="application/zip")
    check(s, b, "project import")
    print(f"Perspective project {build_views.PROJECT}: imported {len(views)} views")
    record["views"] = sorted(views)
    (OUT / "last_build.json").write_text(json.dumps(record, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
