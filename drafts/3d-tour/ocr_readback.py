"""OCR read-back check for the draft 3D tour stills (draft tool, not part of the test suite).

Reads every label the renderer says it drew (label_truth.json: text + pixel box), runs an
off-the-shelf OCR engine on the still, and reports how much of each label comes back.

Two passes per still:
  crop  - OCR each label's own box (padded 8 px) at native resolution: "can this label be read?"
  frame - OCR the whole frame once, then look for each label's tag/unit ID anywhere in it:
          "does the ID survive a whole-screen read with all the clutter around it?"

Metric: character accuracy = 1 - Levenshtein(ocr, truth) / len(truth), after folding case,
collapsing whitespace and removing line breaks. Tag/unit IDs (e.g. PI-107, R-101) are scored
separately as exact matches, because an ID read wrong is worse than a word read wrong.

OCR is a proxy for legibility, not proof: an engine can fail on text a person reads easily
(and vice versa). Requires `pip install rapidocr onnxruntime` (ONNX models, no GPU, no torch).

    python drafts/3d-tour/ocr_readback.py            # writes drafts/3d-tour/ocr_readback.json
"""
import json
import re
import sys
import unicodedata
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
ID_RE = re.compile(r'\b[A-Z]{1,2}-\d{3}\b')


def norm(text):
    text = unicodedata.normalize('NFKC', text).replace('·', ' ').replace('•', ' ')
    return re.sub(r'\s+', ' ', text).strip().lower()


def lev(a, b):
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def char_accuracy(ocr, truth):
    t, o = norm(truth), norm(ocr)
    return max(0.0, 1 - lev(o, t) / max(1, len(t)))


def read(engine, img, use_cls):
    out = engine(img, use_cls=use_cls)
    if out is None or out.txts is None:
        return []
    items = list(zip(out.boxes.tolist(), out.txts, out.scores))
    items.sort(key=lambda x: (round(min(p[1] for p in x[0]) / 12), min(p[0] for p in x[0])))
    return items


def run(engine, truth, use_cls):
    report = {'engine': 'rapidocr (PP-OCR ONNX models)', 'text_orientation_classifier': use_cls, 'stills': []}
    for still in truth['stills']:
        image = Image.open(HERE / still['image']).convert('RGB')
        arr = np.array(image)
        frame_text = ' '.join(t for _, t, _ in read(engine, arr, use_cls))
        frame_ids = set(ID_RE.findall(frame_text.upper().replace('_', '-')))
        rows = []
        for label in still['labels']:
            x0, y0, x1, y1 = label['text_box']
            box = (max(0, int(x0) - 8), max(0, int(y0) - 8),
                   min(arr.shape[1], int(x1) + 8), min(arr.shape[0], int(y1) + 8))
            got = ' '.join(t for _, t, _ in read(engine, np.array(image.crop(box)), use_cls))
            ids = ID_RE.findall(label['text'])
            got_ids = set(ID_RE.findall(got.upper()))
            rows.append({'id': label['id'], 'kind': label['kind'], 'truth': label['text'], 'ocr_crop': got,
                         'char_accuracy': round(char_accuracy(got, label['text']), 3),
                         'exact': norm(got) == norm(label['text']),
                         'ids': ids, 'ids_read_in_crop': [i for i in ids if i in got_ids],
                         'ids_read_in_frame': [i for i in ids if i in frame_ids]})
        report['stills'].append({'name': still['name'], 'labels': rows})
    all_rows = [r for s in report['stills'] for r in s['labels']]
    id_total = sum(len(r['ids']) for r in all_rows)
    report['summary'] = {
        'labels': len(all_rows),
        'exact_after_normalising': sum(r['exact'] for r in all_rows),
        'mean_char_accuracy': round(sum(r['char_accuracy'] for r in all_rows) / len(all_rows), 3),
        'labels_below_0.90': [f"{s['name']}:{r['id']}" for s in report['stills'] for r in s['labels']
                              if r['char_accuracy'] < 0.9],
        'tag_and_unit_ids': id_total,
        'ids_read_in_crop': sum(len(r['ids_read_in_crop']) for r in all_rows),
        'ids_read_in_frame': sum(len(r['ids_read_in_frame']) for r in all_rows),
        'by_kind': {k: round(sum(r['char_accuracy'] for r in all_rows if r['kind'] == k)
                             / sum(1 for r in all_rows if r['kind'] == k), 3)
                    for k in sorted({r['kind'] for r in all_rows})},
    }
    return report


def main():
    from rapidocr import RapidOCR
    engine = RapidOCR()
    truth = json.loads((HERE / 'label_truth.json').read_text(encoding='utf-8'))
    # Every label is horizontal, so the 180-degree text-orientation classifier is not needed. It
    # is reported both ways because the default (on) flips some short labels upside down.
    runs = {'orientation_classifier_off': run(engine, truth, False),
            'orientation_classifier_on_default': run(engine, truth, True)}
    out = HERE / 'ocr_readback.json'
    out.write_text(json.dumps(runs, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    json.dump({k: v['summary'] for k, v in runs.items()}, sys.stdout, indent=1)
    print()


if __name__ == '__main__':
    main()
