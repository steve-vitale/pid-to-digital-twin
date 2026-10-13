"""Derive the browser contract from a generated project ZIP: every route, its view title and every click target.

Stdlib only; reads a local file, contacts nothing. The browser harness (browser_contract.js) clicks each target at
its exported position and checks it lands on the right route and view, so the contract always matches the exact
candidate under test rather than a hand-kept list.

Usage: python scripts/ignition/acceptance/nav_contract.py [out/ignition/gateway/PIDTwin.zip] > contract.json
"""
import hashlib
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BASE = "com.inductiveautomation.perspective/"


def contract(zip_path):
    data = Path(zip_path).read_bytes()
    z = zipfile.ZipFile(zip_path)
    pages = json.loads(z.read(BASE + "page-config/config.json"))["pages"]
    views = {}
    for route, page in pages.items():
        view = json.loads(z.read(f"{BASE}views/{page['viewPath']}/view.json"))
        navs, title = [], None
        for c in view["root"]["children"]:
            click = c.get("events", {}).get("dom", {}).get("onClick")
            if click and click["type"] == "nav":
                p = c["position"]
                navs.append({"name": c["meta"]["name"], "target": click["config"]["page"],
                             "x": p["x"], "y": p["y"], "w": p["width"], "h": p["height"]})
            if c["meta"]["name"] == "Title":
                title = c["props"].get("text")
        views[route] = {"viewPath": page["viewPath"], "title": title,
                        "size": view["props"]["defaultSize"], "navs": navs}
    return {"project_zip_sha256": hashlib.sha256(data).hexdigest(), "routes": views}


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else ROOT / "out/ignition/gateway/PIDTwin.zip"
    json.dump(contract(path), sys.stdout, indent=1)
