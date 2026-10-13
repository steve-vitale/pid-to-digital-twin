"""Blind spot check of the inferred OPEN100 flow directions (the answer keys carry no direction, so this is the only
check of direction correctness there is).

  python scripts/direction_spot_check.py make          # draw a stratified random sample of directed links as crops
  python scripts/direction_spot_check.py ask-gpt       # GPT (Codex CLI) reads each crop, blind to the inference
  python scripts/direction_spot_check.py ask-claude    # Claude (claude CLI, fresh session) does the same
  python scripts/direction_spot_check.py score         # agreement per evidence source -> data/open100_direction_confidence.json

Each crop outlines the two linked symbols, A (blue) and B (orange), on the original drawing. Which one is A is a coin
flip with a fixed seed, so "A to B" is not always the inferred direction. The readers see only the crop and the
question; the inferred direction stays in a separate file until scoring. A reader may answer UNCLEAR; those are
reported, not counted as right or wrong.

What this measures: whether a careful reader of the same drawing agrees with the code. It is not an answer key. The
two readers are AI models, not plant engineers; where they disagree with each other, that's reported too.
"""
import argparse
import json
import random
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
OUT = ROOT / "out" / "open100_structural" / "spot_check"
DRAWINGS = ROOT / "data" / "external" / "pid2graph" / "PID2Graph" / "Complete" / "PID2Graph OPEN100"
TWIN = ROOT / "out" / "twin" / "r2-tiles-trace" / "codex" / "plant_model.json"
DIRECTIONS = ROOT / "out" / "open100_structural" / "flow_direction.json"
CONF = ROOT / "data" / "open100_direction_confidence.json"
SEED = 20261013
PER_SOURCE = {"arrowhead": 15, "offpage_flag": 10, "pump_ports": 7, "arrowhead_via_junction": 15,
              "offpage_flag_via_junction": 10, "valve_chain": 8}
QUESTION = ("This is a crop of a piping and instrumentation diagram (P&ID). Two symbols are outlined: A in blue and "
            "B in orange. Looking only at what is drawn (arrowheads on the lines, off-page connector flags, equipment "
            "symbols), which way does process flow go along the line(s) between A and B? Answer A_TO_B, B_TO_A, or "
            "UNCLEAR if the drawing does not show it.")
WEAK = ("arrowhead_via_junction", "offpage_flag_via_junction")


def deciding_source(rec):
    tier = {"first_hand": lambda s: s not in WEAK + ("valve_chain",), "via_junction": lambda s: s in WEAK,
            "valve_chain": lambda s: s == "valve_chain"}[rec["basis"]]
    srcs = sorted({e["source"] for e in rec["evidence"] if tier(e["source"])})
    order = list(PER_SOURCE)
    return min(srcs, key=order.index)


def boxes_by_asset(model):
    out = defaultdict(list)
    for key in ("units", "instruments", "line_items", "offpage_connectors"):
        for x in model[key]:
            for p in x["provenance"]:
                out[x["id"]].append((p["sheet"], p["box_0_1000"]))
    return out


def make():
    from PIL import Image, ImageDraw
    model = json.loads(TWIN.read_text(encoding="utf-8"))
    recs = json.loads(DIRECTIONS.read_text(encoding="utf-8"))["streams"]
    boxes = boxes_by_asset(model)
    rng = random.Random(SEED)
    pool = defaultdict(list)
    for r in recs:
        if r["direction"] in ("forward", "reverse") and r["kind"] == "extracted_link":
            pool[deciding_source(r)].append(r)
    sample = []
    for src, n in PER_SOURCE.items():
        items = sorted(pool.get(src, []), key=lambda r: r["id"])
        sample += [(src, r) for r in rng.sample(items, min(n, len(items)))]
    (OUT / "crops").mkdir(parents=True, exist_ok=True)
    manifest, hidden = [], {}
    for k, (src, r) in enumerate(sample):
        sheet = r["sheet"]
        im = Image.open(DRAWINGS / f"{sheet}.png").convert("RGB")
        W, H = im.size
        a_is_from = rng.random() < 0.5
        A, B = (r["from"], r["to"]) if a_is_from else (r["to"], r["from"])
        ba = next(b for s, b in boxes[A] if s == sheet)
        bb = next(b for s, b in boxes[B] if s == sheet)
        px = lambda b: (b[0] * W / 1000, b[1] * H / 1000, b[2] * W / 1000, b[3] * H / 1000)  # noqa: E731
        pa, pb = px(ba), px(bb)
        x0, y0 = min(pa[0], pb[0]), min(pa[1], pb[1])
        x1, y1 = max(pa[2], pb[2]), max(pa[3], pb[3])
        pad = max(80, 0.15 * max(x1 - x0, y1 - y0))
        x0, y0, x1, y1 = max(0, x0 - pad), max(0, y0 - pad), min(W, x1 + pad), min(H, y1 + pad)
        crop = im.crop((int(x0), int(y0), int(x1), int(y1)))
        dr = ImageDraw.Draw(crop)
        for (b, col, name) in ((pa, (30, 90, 230), "A"), (pb, (240, 130, 0), "B")):
            q = (b[0] - x0 - 3, b[1] - y0 - 3, b[2] - x0 + 3, b[3] - y0 + 3)
            dr.rectangle(q, outline=col, width=4)
            dr.rectangle((q[0], q[1] - 26, q[0] + 24, q[1]), fill=col)
            dr.text((q[0] + 7, q[1] - 22), name, fill=(255, 255, 255))
        scale = min(1.0, 1400 / max(crop.size))
        if scale < 1:
            crop = crop.resize((int(crop.size[0] * scale), int(crop.size[1] * scale)))
        name = f"q{k:02d}.png"
        crop.save(OUT / "crops" / name)
        inferred = "A_TO_B" if r["flow_from"] == A else "B_TO_A"
        manifest.append({"q": k, "image": f"crops/{name}", "sheet": sheet})
        hidden[str(k)] = {"stream": r["id"], "source": src, "A": A, "B": B, "inferred": inferred,
                          "confidence": r["confidence"]}
    (OUT / "manifest.json").write_text(json.dumps({"question": QUESTION, "items": manifest}, indent=1))
    (OUT / "inferred_hidden.json").write_text(json.dumps(hidden, indent=1))
    print(f"{len(manifest)} crops in {OUT / 'crops'}; per source: {dict(Counter(s for s, _ in sample))}")


def parse(text, ids):
    got = {}
    for m in re.finditer(r'"?q?(\d+)"?\s*[:=]\s*"?(A_TO_B|B_TO_A|UNCLEAR)', text):
        if int(m.group(1)) in ids:
            got[int(m.group(1))] = m.group(2)
    return got


def ask(reader, batch=6):
    """batch: crops per call. GPT goes in larger batches because each Codex start pays a fixed overhead here."""
    man = json.loads((OUT / "manifest.json").read_text())
    path = OUT / f"answers_{reader}.json"
    answers = json.loads(path.read_text()) if path.exists() else {}
    todo = [it for it in man["items"] if str(it["q"]) not in answers]
    for i in range(0, len(todo), batch):
        chunk = todo[i:i + batch]
        ids = [it["q"] for it in chunk]
        files = [str((OUT / it["image"]).resolve()) for it in chunk]
        prompt = (man["question"] + "\n\nThere are %d crops, one question each. The files are:\n" % len(chunk)
                  + "\n".join(f"question {it['q']}: {f}" for it, f in zip(chunk, files))
                  + "\n\nReply with only a JSON object mapping each question number to A_TO_B, B_TO_A or UNCLEAR, "
                    'e.g. {"%d": "UNCLEAR"}.' % ids[0])
        if reader == "gpt":
            cmd = ["codex", "exec", "--skip-git-repo-check", "--sandbox", "read-only", "-c",
                   "model_reasoning_effort=medium"]
            for f in files:
                cmd += ["-i", f]
            cmd += ["-"]  # prompt on stdin: a multi-line argument does not survive the Windows .cmd shim
            stdin = prompt
        else:
            cmd = ["claude", "-p", prompt, "--allowedTools", "Read", "--add-dir", str(OUT / "crops")]
            stdin = ""
        res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=3600,
                             input=stdin, shell=sys.platform == "win32" and reader == "gpt", cwd=str(OUT))
        got = parse(res.stdout, set(ids))
        for q in ids:
            answers[str(q)] = got.get(q, "NO_ANSWER")
        path.write_text(json.dumps(answers, indent=1))
        print(reader, ids, [answers[str(q)] for q in ids])


def wilson(k, n, z=1.96):
    if n == 0:
        return None
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    m = z * ((p * (1 - p) + z * z / (4 * n)) / n) ** 0.5
    return round((c - m) / d, 3), round((c + m) / d, 3)


def score():
    hidden = json.loads((OUT / "inferred_hidden.json").read_text())
    readers = {r: json.loads((OUT / f"answers_{r}.json").read_text())
               for r in ("gpt", "claude") if (OUT / f"answers_{r}.json").exists()}
    per = defaultdict(lambda: defaultdict(Counter))
    between = Counter()
    for q, h in hidden.items():
        calls = {r: a.get(q, "NO_ANSWER") for r, a in readers.items()}
        for r, c in calls.items():
            per[h["source"]][r]["agree" if c == h["inferred"] else "unclear" if c in ("UNCLEAR", "NO_ANSWER")
                                else "disagree"] += 1
        if len(calls) == 2:
            a, b = calls.values()
            between["both decided, same" if a == b and a in ("A_TO_B", "B_TO_A") else
                    "both decided, different" if a in ("A_TO_B", "B_TO_A") and b in ("A_TO_B", "B_TO_A") else
                    "at least one unclear"] += 1
    sources = {}
    for src, by_reader in per.items():
        k = sum(c["agree"] for c in by_reader.values())
        n = sum(c["agree"] + c["disagree"] for c in by_reader.values())
        unclear = sum(c["unclear"] for c in by_reader.values())
        sources[src] = {"readers": {r: dict(c) for r, c in by_reader.items()}, "agree": k, "decided": n,
                        "unclear": unclear, "agreement": round(k / n, 3) if n else None, "wilson95": wilson(k, n)}
        if n:
            # the confidence carried on each link is the LOWER end of the 95% interval: with 5-15 readings, a
            # perfect score is not certainty
            sources[src]["confidence"] = wilson(k, n)[0]
    names = {"gpt": "GPT (Codex CLI)", "claude": "Claude (claude CLI, fresh session)"}
    doc = {"readers": [names[r] for r in readers],
           "method": "blind spot check: the readers listed read crops of the original drawing "
                     "with A/B outlined. agreement = share of decided readings (readers pooled) that agree with the "
                     "inferred direction; confidence = the lower end of its 95% Wilson interval. UNCLEAR readings are "
                     "not counted either way. Not an answer key.",
           "sample": "scripts/direction_spot_check.py, seed %d, per source %s" % (SEED, PER_SOURCE),
           "sources": sources, "reader_agreement": dict(between)}
    CONF.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(doc, indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["make", "ask-gpt", "ask-claude", "score"])
    a = ap.parse_args()
    {"make": make, "ask-gpt": lambda: ask("gpt", batch=22), "ask-claude": lambda: ask("claude"), "score": score}[a.step]()


if __name__ == "__main__":
    main()
