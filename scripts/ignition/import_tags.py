"""Import a tag JSON file into an Ignition 8.3 tag provider over the REST API. The minimal manual path: an API key is
all it needs (see scripts/ignition/gw.py for the IGNITION_* settings).

  python scripts/ignition/import_tags.py out/ignition/gateway/twin_provider.json --provider Twin

The Designer does the same thing by hand: Tag Browser > select the provider > Import Tags > choose the file.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gw import Gateway  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--provider", default="Twin", help="must be 'Twin' for the committed screens' bindings")
    ap.add_argument("--collision", default="Overwrite", choices=["Abort", "Overwrite", "Rename", "Ignore", "MergeOverwrite"])
    a = ap.parse_args()
    data = Path(a.file).read_bytes()
    s, b = Gateway().post(f"/data/api/v1/tags/import?provider={a.provider}&path=&type=json&collisionPolicy={a.collision}",
                          data, ctype="application/octet-stream")
    print(s, json.dumps(b))
    sys.exit(0 if s < 300 and not (b or {}).get("failureCount") else 1)


if __name__ == "__main__":
    main()
