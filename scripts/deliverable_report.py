"""Turn a review bundle (scripts/import_site_drawing.py output) into the one-page report a client would read first.

    python scripts/deliverable_report.py my-bundle                     # writes my-bundle/REPORT.html
    python scripts/deliverable_report.py my-bundle --out report.html

The report is a single self-contained HTML file: what was extracted from the drawing and by what, the drawing with
every extracted item boxed, the items to check first and why, the asset hierarchy, what each file in the package is
for, the next steps, and what the package does not establish. It reads only the bundle; it adds no judgement of its
own, and every number in it comes from the bundle's files. With Pillow installed the drawing is embedded as a
reduced JPEG; without it, as the original PNG.
"""
import argparse
import base64
import csv
import html
import io
import json
import struct
import sys
from collections import Counter
from pathlib import Path

CLASS_COLOURS = {"tank": "#b45309", "pump": "#7c3aed", "valve": "#0f766e", "instrumentation": "#2563eb",
                 "inlet/outlet": "#be185d", "general": "#4b5563"}
ROUTINE = ("routine check", "check the line exists")
FILES = [
    ("review_queue.csv", "Every extracted item and link, one row each, for a reviewer to confirm, correct or reject in "
                         "the OPS_ columns. Start here."),
    ("plant_model.json", "The draft asset model: systems, equipment, instruments, valves, links, with where each came "
                         "from on the sheet."),
    ("ignition/tags.json", "An Ignition tag import (UDT types, one instance per asset); every value is a placeholder "
                           "until mapped to a real signal."),
    ("pi/", "PI AF staging sheets and the steps a PI site would still run; not import-tested."),
    ("svg/sheet_0.svg", "The extracted items and links drawn as a logical diagram, not pipe routes."),
    ("source/", "The exact drawing and extraction the bundle was built from, with hashes in intake_manifest.json."),
    ("READ_ME.txt", "What the bundle has not established."),
]


def png_size(data):
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("source drawing is not a PNG")
    return struct.unpack(">II", data[16:24])


def drawing_uri(png_bytes, max_width=1600):
    try:
        from PIL import Image
        im = Image.open(io.BytesIO(png_bytes)).convert("RGB")
        if im.width > max_width:
            im = im.resize((max_width, round(im.height * max_width / im.width)))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=82)
        return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
    except ImportError:
        return "data:image/png;base64," + base64.b64encode(png_bytes).decode()


def items(model):
    for group in ("units", "instruments", "final_elements", "line_items", "offpage_connectors"):
        for it in model.get(group, []):
            for prov in it.get("provenance", [])[:1]:
                yield it, prov


def overlay(model, w, h, uri):
    boxes = []
    for it, prov in items(model):
        x1, y1, x2, y2 = prov["box_0_1000"]
        colour = CLASS_COLOURS.get(it.get("class"), "#4b5563")
        label = html.escape(f'{it["id"]}: {it.get("tag") or "no tag"} ({it.get("class")})')
        boxes.append(f'<rect x="{x1 * w / 1000:.1f}" y="{y1 * h / 1000:.1f}" width="{(x2 - x1) * w / 1000:.1f}" '
                     f'height="{(y2 - y1) * h / 1000:.1f}" fill="none" stroke="{colour}" stroke-width="{w / 600:.1f}">'
                     f'<title>{label}</title></rect>')
    return (f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="The drawing with every extracted item boxed">'
            f'<image href="{uri}" width="{w}" height="{h}"/>{"".join(boxes)}</svg>')


def hierarchy_html(node, depth=0):
    kids = node.get("children", [])
    tag = node.get("tag") or ("no tag" if node.get("kind") not in ("site", "system") else "")
    name = node.get("name") or ""
    label = " ".join(x for x in (html.escape(node["id"]), html.escape(tag), html.escape(name)) if x)
    if depth >= 2 and not kids:
        return f"<li>{label} <span class=k>{html.escape(node.get('class') or node.get('kind', ''))}</span></li>"
    inner = "".join(hierarchy_html(k, depth + 1) for k in kids + node.get("unassigned", []) +
                    node.get("offpage_connectors", []))
    open_ = " open" if depth < 2 else ""
    return (f"<li><details{open_}><summary>{label} <span class=k>{html.escape(node.get('kind', ''))}"
            f"{', ' + str(len(kids)) + ' below' if kids else ''}</span></summary><ul>{inner}</ul></details></li>")


def build(bundle):
    bundle = Path(bundle)
    model = json.loads((bundle / "plant_model.json").read_text(encoding="utf-8"))
    intake = json.loads((bundle / "intake_manifest.json").read_text(encoding="utf-8"))
    with open(bundle / "review_queue.csv", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    png = next((bundle / "source").glob("*.png")).read_bytes()
    w, h = png_size(png)
    s = model["summary"]
    meta = model["meta"]
    limits = [ln for ln in (bundle / "READ_ME.txt").read_text(encoding="utf-8").splitlines()[1:] if ln.strip()]
    first = [r for r in rows if not r["why_check_this"].startswith(ROUTINE)]
    reasons = Counter(r["why_check_this"].split(";")[0] for r in first)
    kinds = Counter(r["item_type"] for r in rows)
    drawing = intake.get("drawing") or {}
    producer = intake.get("supplied_producer") or intake.get("producer") or {}
    e = html.escape

    def tile(n, label):
        return f'<div class=tile><b>{n:,}</b><span>{e(label)}</span></div>'

    first_rows = "".join(
        f"<tr><td>{e(r['item_id'])}</td><td>{e(r['what_it_is'])}</td><td>{e(r['item_type'])}</td>"
        f"<td>{e(r['why_check_this'])}</td></tr>" for r in first)
    files = "".join(f"<tr><td><code>{e(n)}</code></td><td>{e(d)}</td></tr>" for n, d in FILES if (bundle / n).exists())
    legend = "".join(f'<span><i style="border-color:{c}"></i>{e(k)}</span>' for k, c in CLASS_COLOURS.items())
    reason_list = "".join(f"<li>{n} × {e(k)}</li>" for k, n in reasons.most_common())
    return f"""<!doctype html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>Draft asset model report</title>
<style>
:root{{--bg:#fafaf9;--fg:#1c1917;--mute:#57534e;--line:#e7e5e4;--card:#fff;--warn:#92400e;--warnbg:#fef3c7}}
@media (prefers-color-scheme:dark){{:root{{--bg:#1c1917;--fg:#f5f5f4;--mute:#a8a29e;--line:#44403c;--card:#292524;
--warn:#fcd34d;--warnbg:#451a03}}}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}}
main{{max-width:1100px;margin:0 auto;padding:24px 16px 64px}}h1{{font-size:26px;margin:0 0 4px}}
h2{{font-size:18px;margin:36px 0 8px;border-bottom:1px solid var(--line);padding-bottom:4px}}
.sub{{color:var(--mute)}}.draft{{background:var(--warnbg);color:var(--warn);padding:10px 14px;border-radius:6px;
margin:16px 0}}.tiles{{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:10px}}
.tile{{background:var(--card);border:1px solid var(--line);border-radius:6px;padding:10px 12px}}
.tile b{{display:block;font-size:22px}}.tile span{{color:var(--mute);font-size:13px}}
figure{{margin:0;background:var(--card);border:1px solid var(--line);border-radius:6px;padding:8px}}
figure svg{{width:100%;height:auto;display:block}}.legend{{display:flex;flex-wrap:wrap;gap:14px;font-size:13px;
color:var(--mute);margin-top:6px}}.legend i{{display:inline-block;width:12px;height:12px;border:2px solid;
margin-right:5px;vertical-align:-1px}}table{{width:100%;border-collapse:collapse;font-size:14px}}
th,td{{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top}}
th{{color:var(--mute);font-weight:600}}.scroll{{overflow-x:auto}}ul.tree,ul.tree ul{{list-style:none;padding-left:18px}}
ul.tree{{padding-left:0;font-size:14px}}.k{{color:var(--mute);font-size:12px}}code{{font-size:13px}}
ol li,ul li{{margin:3px 0}}
</style></head><body><main>
<h1>Draft asset model: {e(drawing.get('drawing_id', meta.get('source_document', '')))}</h1>
<div class=sub>Revision {e(str(drawing.get('revision', '?')))}, page {e(str(drawing.get('page', '?')))} ·
{e(meta.get('title', ''))} · extraction: {e(producer.get('method', 'not stated'))}
{('(' + e(producer.get('model')) + ')') if producer.get('model') else ''}</div>
<div class=draft><b>Draft, unverified.</b> Every item below was read off the drawing by software and has not been
checked by a person. Nothing here is approved for operational use.</div>

<h2>What was extracted</h2>
<div class=tiles>{tile(s['equipment'], 'equipment')}{tile(s['instruments'], 'instruments')}
{tile(kinds.get('valve', 0), 'valves')}{tile(kinds.get('in-line item', 0), 'other in-line items')}
{tile(s['offpage_connectors'], 'off-page connectors')}{tile(s['streams_extracted'], 'links between items')}
{tile(len(rows), 'rows to review')}{tile(len(first), 'to check first')}</div>

<h2>The drawing, with what was extracted</h2>
<figure>{overlay(model, w, h, drawing_uri(png))}
<figcaption class=legend>{legend}</figcaption></figure>
<p class=sub>Each box is one extracted item, coloured by class; hover for its id and tag. Links aren't drawn here
(see <code>svg/sheet_0.svg</code>).</p>

<h2>Check these first ({len(first)} of {len(rows)} rows)</h2>
<p>The software flagged these for a specific reason; the rest are routine checks (does this line exist, is this
item right). Reasons:</p><ul>{reason_list}</ul>
<div class=scroll><table><thead><tr><th>Item</th><th>What it is</th><th>Type</th><th>Why check it</th></tr></thead>
<tbody>{first_rows}</tbody></table></div>

<h2>Asset hierarchy</h2>
<p class=sub>Instruments are attached to the nearest line item or equipment; {s['instrument_parent_method'].get('linked', 0)}
by a drawn link and {s['instrument_parent_method'].get('geometry_nearest', 0)} by distance alone, which needs a closer look.</p>
<ul class=tree>{hierarchy_html(model['hierarchy'])}</ul>

<h2>What's in the package</h2>
<div class=scroll><table><tbody>{files}</tbody></table></div>

<h2>Next steps</h2>
<ol><li>A reviewer who knows the unit works through <code>review_queue.csv</code>, starting with the rows above, and
fills the <code>OPS_</code> columns.</li>
<li>The decisions are applied with <code>apply_review.py</code> and the exports regenerated.</li>
<li>Instruments are mapped to real signals from the plant's I/O list (<code>map_points.py</code>).</li>
<li><code>ignition/tags.json</code> is imported into a lab gateway and checked before anything goes further.</li></ol>

<h2>What this package does not establish</h2>
<ul>{''.join(f'<li>{e(x)}</li>' for x in limits)}</ul>
<p class=sub>Generated by <code>scripts/deliverable_report.py</code> from the bundle's own files.</p>
</main></body></html>
"""


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("bundle")
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    out = Path(a.out) if a.out else Path(a.bundle) / "REPORT.html"
    try:
        text = build(a.bundle)
    except (OSError, KeyError, ValueError, StopIteration) as exc:
        print(f"{a.bundle}: not a complete review bundle ({exc!r})", file=sys.stderr)
        return 1
    out.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {out} ({len(text) // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
