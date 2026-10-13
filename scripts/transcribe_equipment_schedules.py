"""Transcribe the equipment schedules printed along the bottom of each OPEN100 drawing ("CVCS-HX-110  SERVICE: REGEN
HEAT EXCHANGER"). These are the drawings' own words for what each piece of equipment is for, and the extraction
never read them. Used for the tour's purpose cards (scripts/open100_structure.py).

  python scripts/transcribe_equipment_schedules.py     # crops, asks the claude CLI, writes data/open100_equipment_schedule.json

Model use: Claude (claude CLI) reads crops of the bottom strip of each sheet and copies tag + SERVICE text. The
result is a transcription, unverified: every entry keeps the sheet it came from, and a reviewer should check it
against the drawing like any other extracted text.
"""
import json
import re
import subprocess
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
DRAWINGS = ROOT / "data" / "external" / "pid2graph" / "PID2Graph" / "Complete" / "PID2Graph OPEN100"
CROPS = ROOT / "out" / "open100_structural" / "schedule_crops"
OUT = ROOT / "data" / "open100_equipment_schedule.json"
PROMPT = ("Read the two image files below with the Read tool. They are the left and right halves (overlapping) of the "
          "bottom strip of one P&ID sheet, where an equipment schedule is printed: an underlined equipment tag "
          "followed by 'SERVICE: ...'. Copy every schedule entry exactly as printed. Do not guess; skip an entry you "
          "cannot read completely. Reply with only a JSON list like "
          '[{"tag": "CVCS-HX-110", "service": "REGEN HEAT EXCHANGER"}]; reply [] if there is no schedule.\n')


def crops(sheet):
    im = Image.open(DRAWINGS / f"{sheet}.png").convert("L")
    W, H = im.size
    strip = im.crop((0, int(H * 0.84), int(W * 0.86), H))
    w = strip.size[0]
    out = []
    for k in range(2):
        p = CROPS / f"sheet{sheet}_{k}.png"
        strip.crop((max(0, k * w // 2 - 350), 0, min(w, (k + 1) * w // 2), strip.size[1])).save(p)
        out.append(p)
    return out


def main():
    CROPS.mkdir(parents=True, exist_ok=True)
    doc = {"method": "claude CLI transcription of each sheet's printed equipment schedule (bottom strip); unverified",
           "sheets": {}}
    for sheet in range(12):
        files = crops(sheet)
        res = subprocess.run(["claude", "-p", PROMPT + "\n".join(str(f) for f in files), "--allowedTools", "Read",
                              "--add-dir", str(CROPS)], capture_output=True, text=True, encoding="utf-8",
                             errors="replace", timeout=900, input="")
        m = re.search(r"\[.*\]", res.stdout, re.S)
        rows = json.loads(m.group(0)) if m else []
        seen, clean = set(), []
        for r in rows:
            tag = re.sub(r"\s+", "", str(r.get("tag", ""))).upper()
            if tag and tag not in seen and r.get("service"):
                seen.add(tag)
                clean.append({"tag": tag, "service": re.sub(r"\s+", " ", str(r["service"])).strip().upper()})
        doc["sheets"][str(sheet)] = clean
        print(sheet, clean)
    OUT.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
