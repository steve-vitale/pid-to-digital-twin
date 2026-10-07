"""Run one extraction tool over P&ID drawings with the shared prompt, and save raw + parsed output with metadata.

Every run records {tool, model, access path, prompt sha256, image sha256, timestamp, seconds, cost} so a result can
always be traced to exactly what produced it (fairness rules: docs/JOURNAL.md entry 3).

Access paths:
  claude  Claude Code CLI (subscription). --system-prompt replaces Claude Code's default instructions with one
          neutral line; the image is opened with the Read tool. Runs in an empty folder.
  codex   Codex CLI (subscription), `codex exec -i <image>`, --ignore-user-config --ephemeral, read-only sandbox,
          empty folder. Codex keeps its own built-in instructions (unavoidable on this path; recorded).
  gemini  Gemini API, image inline. --model gemma-4-31b-it runs Google's open-weight Gemma through the same API,
          as a stand-in for what a self-hosted (air-gapped) model of that size would score. Key read at run time from GEMINI_API_KEY or the path in GEMINI_KEY_ENV_FILE.
          Hard spend cap: refuses to start a call that could push the ledger past $25.

Usage:
  python scripts/run_extraction.py --tool claude --drawings 8 [--label first-try] [--model opus]
  python scripts/run_extraction.py --tool gemini --list-models
Outputs: runs/<label>/<tool>/<drawing>.json   (gitignored raw is kept; the scorecard is what's published)
"""
import argparse
import base64
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROMPT = (ROOT / "extraction" / "prompt.md").read_text(encoding="utf-8")
DATA = ROOT / "data" / "external" / "pid2graph" / "PID2Graph" / "Complete" / "PID2Graph OPEN100"
RUNS = ROOT / "runs"
SPEND = RUNS / "gemini_spend.json"
GEMINI_CAP_USD = 25.0
# Conservative per-million-token prices used only for the spend cap (over-estimate on purpose).
GEMINI_PRICE = {"input": 2.50, "output": 15.00}
SYSTEM_LINE = "You extract structured data from engineering drawings. Follow the user's output format exactly."


def sha(b):
    return hashlib.sha256(b).hexdigest()


def parse_json(text):
    """Pull the first JSON object out of a model reply (tolerates code fences or stray prose)."""
    if text is None:
        return None, "no text"
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.M)
    start, end = t.find("{"), t.rfind("}")
    if start < 0 or end <= start:
        return None, "no JSON object found"
    try:
        return json.loads(t[start:end + 1]), None
    except json.JSONDecodeError as e:
        return None, f"invalid JSON: {e}"


def run_claude(image, model):
    work = Path(tempfile.mkdtemp(prefix="pid-claude-"))
    shutil.copy(image, work / "drawing.png")
    prompt = PROMPT + "\n\nThe drawing is the file drawing.png in the current folder. Open it with the Read tool."
    # The prompt goes in on stdin: on Windows, shell=True routes through cmd.exe, which cuts a multi-line
    # argument at its first line break (the first smoke run sent only the prompt's first sentence).
    cmd = ["claude", "-p", "--output-format", "json", "--system-prompt", SYSTEM_LINE,
           "--allowedTools", "Read", "--strict-mcp-config", "--disable-slash-commands"]
    if model:
        cmd += ["--model", model]
    try:
        p = subprocess.run(cmd, cwd=work, input=prompt, capture_output=True, text=True, encoding="utf-8",
                           timeout=1800, shell=(os.name == "nt"))
        if not p.stdout.strip():
            return {"text": None, "model": model, "error": (p.stderr or "no output")[-2000:]}
        out = json.loads(p.stdout)
        models = list((out.get("modelUsage") or {}).keys())
        return {"text": out.get("result"), "model": ",".join(models) or model or "default",
                "cost_usd_notional": out.get("total_cost_usd"), "error": out.get("result") if out.get("is_error") else None}
    finally:
        shutil.rmtree(work, ignore_errors=True)


def run_codex(image, model):
    work = Path(tempfile.mkdtemp(prefix="pid-codex-"))
    shutil.copy(image, work / "drawing.png")
    last = work / "last.txt"
    cmd = ["codex", "exec", "--ephemeral", "--ignore-user-config", "--skip-git-repo-check", "-s", "read-only",
           "-C", str(work), "-i", str(work / "drawing.png"), "-o", str(last)]
    if model:
        cmd += ["-m", model]
    cmd.append("-")  # read the prompt from stdin (see run_claude for why)
    try:
        p = subprocess.run(cmd, cwd=work, input=PROMPT, capture_output=True, text=True, encoding="utf-8",
                           timeout=1800, shell=(os.name == "nt"))
        m = re.search(r"^model:\s*(\S+)", p.stderr + p.stdout, flags=re.M)
        text = last.read_text(encoding="utf-8") if last.exists() else None
        return {"text": text, "model": m.group(1) if m else (model or "default"), "cost_usd_notional": None,
                "error": None if text else (p.stderr[-2000:] or "no output")}
    finally:
        shutil.rmtree(work, ignore_errors=True)


def gemini_key():
    if os.environ.get("GEMINI_API_KEY"):
        return os.environ["GEMINI_API_KEY"]
    env_file = os.environ.get("GEMINI_KEY_ENV_FILE")
    if env_file and Path(env_file).exists():
        for line in Path(env_file).read_text(encoding="utf-8").splitlines():
            m = re.match(r"\s*GEMINI_API_KEY\s*=\s*\"?([^\"\s]+)", line)
            if m:
                return m.group(1)
    sys.exit("No Gemini key: set GEMINI_API_KEY or GEMINI_KEY_ENV_FILE=<path to a .env file>")


def gemini_spent():
    return json.loads(SPEND.read_text())["usd"] if SPEND.exists() else 0.0


def run_gemini(image, model):
    model = model or "gemini-pro-latest"
    img = image.read_bytes()
    # Worst-case estimate before calling: image + prompt input plus a large output allowance.
    worst = (6000 / 1e6) * GEMINI_PRICE["input"] + (65536 / 1e6) * GEMINI_PRICE["output"]
    if gemini_spent() + worst > GEMINI_CAP_USD:
        return {"text": None, "model": model, "cost_usd": 0, "error": f"spend cap: ${gemini_spent():.2f} spent"}
    image_part = {"inline_data": {"mime_type": "image/png", "data": base64.b64encode(img).decode()}}
    if model.startswith("gemma"):
        # Open-weight Gemma on the same API: no separate system instruction or JSON mode, so the system line is
        # folded into the prompt and the reply goes through the same tolerant JSON parser as the CLI tools.
        body = {"contents": [{"parts": [{"text": SYSTEM_LINE + "\n\n" + PROMPT}, image_part]}],
                "generationConfig": {"maxOutputTokens": 32768}}
    else:
        body = {"contents": [{"parts": [{"text": PROMPT}, image_part]}],
                "systemInstruction": {"parts": [{"text": SYSTEM_LINE}]},
                "generationConfig": {"responseMimeType": "application/json", "maxOutputTokens": 65536}}
    req = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        data=json.dumps(body).encode(), headers={"Content-Type": "application/json", "x-goog-api-key": gemini_key()})
    with urllib.request.urlopen(req, timeout=1800) as r:
        out = json.load(r)
    u = out.get("usageMetadata", {})
    cost = (u.get("promptTokenCount", 0) / 1e6) * GEMINI_PRICE["input"] + \
           ((u.get("candidatesTokenCount", 0) + u.get("thoughtsTokenCount", 0)) / 1e6) * GEMINI_PRICE["output"]
    RUNS.mkdir(exist_ok=True)
    SPEND.write_text(json.dumps({"usd": round(gemini_spent() + cost, 4), "cap": GEMINI_CAP_USD}))
    parts = (out.get("candidates") or [{}])[0].get("content", {}).get("parts", [])
    text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
    return {"text": text, "model": out.get("modelVersion", model), "cost_usd": round(cost, 4), "usage": u,
            "error": None if text else json.dumps(out)[:2000]}


TOOLS = {"claude": run_claude, "codex": run_codex, "gemini": run_gemini}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tool", choices=TOOLS, required=True)
    ap.add_argument("--drawings", default="")
    ap.add_argument("--label", default="first-try")
    ap.add_argument("--model", default=None)
    ap.add_argument("--list-models", action="store_true")
    ap.add_argument("--prompt", default="extraction/prompt.md", help="prompt file, relative to the repo root")
    a = ap.parse_args()
    global PROMPT
    PROMPT = (ROOT / a.prompt).read_text(encoding="utf-8")
    if a.list_models and a.tool == "gemini":
        req = urllib.request.Request("https://generativelanguage.googleapis.com/v1beta/models?pageSize=200",
                                     headers={"x-goog-api-key": gemini_key()})
        for m in json.load(urllib.request.urlopen(req, timeout=60))["models"]:
            if "generateContent" in m.get("supportedGenerationMethods", []):
                print(m["name"])
        return
    for d in [x for x in a.drawings.split(",") if x]:
        image = DATA / f"{d}.png"
        out_path = RUNS / a.label / a.tool / f"{d}.json"
        if out_path.exists():
            print(f"skip {a.tool} drawing {d}: already run ({out_path.relative_to(ROOT)})")
            continue
        t0 = time.time()
        try:
            res = TOOLS[a.tool](image, a.model)
        except Exception as e:  # record failures too; a failed run is a result
            res = {"text": None, "model": a.model, "error": f"{type(e).__name__}: {e}"}
        parsed, perr = parse_json(res.get("text"))
        record = {"tool": a.tool, "drawing": d, "label": a.label, "prompt_file": a.prompt, "model": res.get("model"),
                  "prompt_sha256": sha(PROMPT.encode()), "image_sha256": sha(image.read_bytes()),
                  "ran_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                  "seconds": round(time.time() - t0, 1), "cost_usd": res.get("cost_usd"),
                  "cost_usd_notional": res.get("cost_usd_notional"), "error": res.get("error"),
                  "parse_error": perr, "raw_text": res.get("text"), "prediction": parsed}
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(record, indent=1), encoding="utf-8")
        n = len((parsed or {}).get("symbols", []))
        print(f"{a.tool} drawing {d}: {n} symbols, {record['seconds']}s, model={record['model']}, "
              f"error={record['error'] or perr}")
        if a.tool == "gemini":
            print(f"  gemini spend so far ${gemini_spent():.2f} of ${GEMINI_CAP_USD}")


if __name__ == "__main__":
    main()
