"""Prepare a gateway backup for the shareable Docker demo (docker/twin-demo.gwbk).

The backup comes from a THROWAWAY Ignition gateway built with `build_gateway.py --demo-backup`, after its temporary
API key and permission level were deleted (docker/README.md, "How the demo backup is made"). This script:
  1. sets a neutral gateway name (the download carries the build machine's hostname), by editing the plain
     configuration file inside the backup (8.3 keeps configuration as files and supports editing them);
  2. refuses if anything personal or credential-like remains: the given strings (hostname, usernames, paths), any
     API key resource, or a verifier OPC UA user.

Usage: python scripts/ignition/prepare_demo_backup.py <downloaded.gwbk> docker/twin-demo.gwbk --forbid DESKTOP- --forbid <...>
"""
import argparse
import json
import sys
import zipfile

SYS_PROPS = "config/resources/core/ignition/system-properties/config.json"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dest")
    ap.add_argument("--name", default="twin-demo")
    ap.add_argument("--forbid", action="append", default=[], help="string that must not appear anywhere in the backup")
    a = ap.parse_args()
    src = zipfile.ZipFile(a.src)
    with zipfile.ZipFile(a.dest, "w", zipfile.ZIP_DEFLATED) as out:
        for info in src.infolist():
            data = src.read(info.filename)
            if info.filename == SYS_PROPS:
                cfg = json.loads(data)
                cfg["systemName"] = a.name
                data = json.dumps(cfg, indent=2).encode()
            out.writestr(info, data)
    problems = []
    z = zipfile.ZipFile(a.dest)
    for n in z.namelist():
        if "/api-token/" in n:
            problems.append(f"API key resource present: {n}")
        data = z.read(n)
        for s in a.forbid:
            if s.encode() in data or s in n:
                problems.append(f"'{s}' found in {n}")
    users = json.loads(z.read("config/resources/core/ignition/user-source/opcua-module/users.json"))
    extra = [u["username"] for u in users.get("users", []) if u["username"] != "opcuauser"]
    if extra:
        problems.append(f"extra OPC UA users: {extra}")
    if problems:
        print("REFUSED:\n  " + "\n  ".join(problems[:20]))
        sys.exit(1)
    print(f"ok: {a.dest} ({len(z.namelist())} entries), gateway name '{a.name}', nothing forbidden found")


if __name__ == "__main__":
    main()
