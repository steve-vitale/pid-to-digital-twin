"""Import a tag JSON file into an Ignition 8.3 tag provider over the REST API. The minimal manual path: an API key is
all it needs (see scripts/ignition/gw.py for the IGNITION_* settings).

  python scripts/ignition/import_tags.py out/ignition/gateway/twin_provider.json --provider Twin

The Designer does the same thing by hand: Tag Browser > select the provider > Import Tags > choose the file.
"""
import argparse
import json
import sys
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gw import Gateway  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--provider", default="Twin", help="must be 'Twin' for the committed screens' bindings")
    ap.add_argument("--collision", default="Overwrite", choices=["Abort", "Overwrite", "Rename", "Ignore", "MergeOverwrite"])
    a = ap.parse_args()
    # Check the file before contacting any gateway: a bad path or a non-JSON file is refused, nothing is sent.
    try:
        data = Path(a.file).read_bytes()
        json.loads(data.decode("utf-8-sig"))
    except FileNotFoundError:
        sys.exit(_refuse(f"no such file: {a.file}"))
    except OSError as exc:
        sys.exit(_refuse(f"cannot read {a.file}: {exc}"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        sys.exit(_refuse(f"{a.file} is not valid JSON ({exc}); export tags with scripts/generate.py or "
                         "build_gateway.py --write-only"))
    gw = Gateway()
    try:
        s, b = gw.post(f"/data/api/v1/tags/import?provider={a.provider}&path=&type=json&collisionPolicy={a.collision}",
                       data, ctype="application/octet-stream")
    except (urllib.error.URLError, OSError) as exc:
        print(f"failed: cannot reach the gateway at {gw.url} ({getattr(exc, 'reason', exc)}); nothing was imported",
              file=sys.stderr)
        sys.exit(1)
    print(s, json.dumps(b))
    sys.exit(0 if s < 300 and not (b or {}).get("failureCount") else 1)


def _refuse(message):
    print(f"refused: {message}; nothing was sent to the gateway", file=sys.stderr)
    return 2


if __name__ == "__main__":
    main()
