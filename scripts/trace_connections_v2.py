"""Development v2 connectivity: repeated dash recovery + the unchanged CV tracer.

Inference consumes only the source raster and detected symbols. No labels, model
calls, network, engineering class reassignment or flow direction inference.
"""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import tempfile

import cv2
import numpy as np
import trace_connections as legacy

METHOD = 'source-image-connectivity-dev-v2'
OPTIONS = {'max_gap_frac': 0.25, 'max_dash_frac': 0.50,
           'min_dashes': 4, 'min_span_frac': 0.60}


def recover_dashes(ink, symbols, enabled=True):
    """Fill only short collinear gaps in trains of >=4 short ink runs.

    Detected boxes are opaque barriers, including for gap filling. Both axes use
    the original masked image, so one synthesized stroke cannot justify another.
    Gaps larger than the symbol-relative bound and isolated broken lines remain
    unresolved. Repeated text strokes can still resemble dashes: review required.
    """
    height, width = ink.shape
    masked = ink.copy()
    boxes = []
    for symbol in symbols:
        box = legacy.symbol_box(symbol)
        if box is None:
            continue
        x0, y0 = max(0, int(np.floor(box[0] * width / 1000))), max(0, int(np.floor(box[1] * height / 1000)))
        x1, y1 = min(width - 1, int(np.ceil(box[2] * width / 1000))), min(height - 1, int(np.ceil(box[3] * height / 1000)))
        if x1 > x0 and y1 > y0:
            boxes.append((x0, y0, x1, y1))
            # Masking is applied after a stroke-scale boundary guard below.
    if not boxes:
        return masked, {'added_pixels': 0, 'dash_trains': 0}
    side = float(np.median([min(x1-x0, y1-y0) for x0,y0,x1,y1 in boxes]))
    max_gap = max(2, round(side * OPTIONS['max_gap_frac']))
    max_dash = max(2, round(side * OPTIONS['max_dash_frac']))
    added = np.zeros_like(masked)
    barriers = np.zeros_like(masked)
    guard = max(1, round(side * 0.025))
    for x0,y0,x1,y1 in boxes:
        barriers[max(0,y0-guard):min(height,y1+guard+1), max(0,x0-guard):min(width,x1+guard+1)] = 1
    masked[barriers > 0] = 0
    trains = 0
    for axis in ((0, 1) if enabled else ()):
        view = masked if axis == 0 else masked.T
        out = added if axis == 0 else added.T
        blocked = barriers if axis == 0 else barriers.T
        for row, pixels in enumerate(view):
            delta = np.diff(np.r_[0, pixels, 0].astype(np.int8))
            starts, ends = np.flatnonzero(delta == 1), np.flatnonzero(delta == -1)
            if len(starts) < OPTIONS['min_dashes']:
                continue
            cuts = np.flatnonzero(starts[1:] - ends[:-1] > max_gap) + 1
            for group in np.split(np.arange(len(starts)), cuts):
                a, b = int(group[0]), int(group[-1])
                lengths = ends[group] - starts[group]
                if (np.count_nonzero(lengths <= max_dash) < OPTIONS['min_dashes']
                        or ends[b] - starts[a] < side * OPTIONS['min_span_frac']):
                    continue
                # Never bridge even a tiny detected inline component.
                if blocked[row, starts[a]:ends[b]].any():
                    continue
                trains += 1
                left, right = int(starts[a]), int(ends[b])
                for position in range(left - 1, max(-1, left - max_gap - 1), -1):
                    if blocked[row, position]:
                        break
                    left = position
                for position in range(right, min(len(pixels), right + max_gap)):
                    if blocked[row, position]:
                        break
                    right = position + 1
                out[row, left:right] = 1
    added &= 1 - masked
    return masked | added, {'added_pixels': int(added.sum()), 'dash_trains': trains,
                            'median_symbol_side_px': side, 'max_gap_px': max_gap, 'symbol_guard_px': guard}


def trace_with_evidence(image_path, symbols):
    gray = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
    if gray is None:
        raise ValueError('Cannot read source image')
    ink = legacy.binarize(gray)
    restored, evidence = recover_dashes(ink, symbols)
    unchanged, _ = recover_dashes(ink, symbols, enabled=False)
    with tempfile.TemporaryDirectory(prefix='pid-connectivity-') as temporary:
        image = Path(temporary) / 'restored.png'
        if not cv2.imwrite(str(image), (1 - restored) * 255):
            raise OSError('Cannot write temporary tracing raster')
        # Preserve supplied barriers; the OPEN100 through-line snap heuristic can
        # erase valid inline symbols on differently scaled line art.
        guard = evidence.get('symbol_guard_px', 0)
        height, width = gray.shape
        guarded = []
        for symbol in symbols:
            box = legacy.symbol_box(symbol)
            if box is not None:
                guarded.append({**symbol, 'box': [box[0]-guard*1000/width, box[1]-guard*1000/height,
                                                   box[2]+guard*1000/width, box[3]+guard*1000/height]})
        debug = {}
        links = legacy.trace(image, guarded, through_ext=0, debug=debug)
        cv2.imwrite(str(image), (1 - unchanged) * 255)
        baseline = {tuple(sorted((c['from'], c['to']))) for c in legacy.trace(image, guarded, through_ext=0)}
        evidence['networks'] = []
        rootimg = debug.get('_rootimg')
        if rootimg is not None:
            for network, members in debug['_attach'].items():
                if len(members) < 2:
                    continue
                yy, xx = np.nonzero((rootimg == network) & (restored > unchanged))
                evidence['networks'].append({'id': int(network), 'symbols': members,
                    'bounds_px': [int(v) for v in debug['_ext'][network]],
                    'recovered_pixels': len(xx),
                    'recovery_bounds_px': [int(xx.min()), int(yy.min()), int(xx.max()), int(yy.max())] if len(xx) else None})
        for link in links:
            pair = tuple(sorted((link['from'], link['to'])))
            link['gap_recovery_dependent'] = pair not in baseline
            link['network_ids'] = [n['id'] for n in evidence['networks'] if set(pair).issubset(n['symbols'])]
    return links, evidence


def trace(image_path, symbols, **options):
    if options:
        raise ValueError('Development v2 has a fixed documented graph convention')
    return trace_with_evidence(image_path, symbols)[0]


def refine(image_path, record):
    """Return a separate record, retaining raw links and all original symbols."""
    prediction = record.get('prediction', record)
    symbols = prediction.get('symbols')
    if not isinstance(symbols, list):
        raise ValueError('Prediction needs symbols')
    if not all(isinstance(s, dict) for s in symbols):
        raise ValueError('Symbols must be objects')
    ids = [str(s.get('id')) for s in symbols]
    if len(set(ids)) != len(ids) or any(s.get('id') is None or legacy.symbol_box(s) is None for s in symbols):
        raise ValueError('Detected symbols need unique IDs and valid boxes')
    for symbol in symbols:
        box = legacy.symbol_box(symbol)
        if not all(math.isfinite(x) and 0 <= x <= 1000 for x in box) or box[0] >= box[2] or box[1] >= box[3]:
            raise ValueError('Boxes must be finite, positive and within the 0–1000 image scale')
    traced, evidence = trace_with_evidence(image_path, symbols)
    raw = prediction.get('connections', [])
    pairs = {}
    for kind, links in (('source_image_trace', traced),):
        for link in links:
            a, b = str(link.get('from')), str(link.get('to'))
            if a not in ids or b not in ids or a == b:
                continue
            pair = tuple(sorted((a,b)))
            pairs.setdefault(pair, []).append(kind)
    result = {'prediction': copy.deepcopy(prediction), 'tool': METHOD, 'model': None,
              'source_record': copy.deepcopy(record)}
    result['prediction']['connections'] = [
        {'from': a, 'to': b, 'evidence': sorted(set(kinds)),
         'semantic_line_type': None, 'flow_direction': None, 'review_status': 'unverified',
         'gap_recovery_dependent': next(c['gap_recovery_dependent'] for c in traced if (c['from'],c['to']) == (a,b)),
         'network_ids': next(c['network_ids'] for c in traced if (c['from'],c['to']) == (a,b))}
        for (a,b), kinds in sorted(pairs.items())]
    raw_pairs = {tuple(sorted((str(c.get('from')), str(c.get('to'))))) for c in raw}
    traced_pairs = set(pairs)
    reconciliation = [{'from': a, 'to': b, 'raw_model_support': (a,b) in raw_pairs,
                       'image_trace_support': (a,b) in traced_pairs, 'review_status': 'unverified',
                       'semantic_line_type': None, 'flow_direction': None}
                      for a,b in sorted(raw_pairs | traced_pairs)]
    result['connectivity'] = {'method': METHOD, 'evaluation_status': 'development_only',
        'options': copy.deepcopy(OPTIONS),
        'implementation_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path(__file__), Path(legacy.__file__))}, 'legacy_options': {'through_ext': 0}, 'raster_recovery': evidence,
        'image_sha256': hashlib.sha256(Path(image_path).read_bytes()).hexdigest(),
        'raw_connections': copy.deepcopy(raw), 'traced_connections': traced,
        'candidate_reconciliation': reconciliation,
        'warning': 'Undirected candidate adjacency only. Crossings are joined under the graph convention; '
                   'dash style, physical junctions, process/signal meaning and direction are unverified. '
                   'Raw model links are preserved separately; every output link requires review.'}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', required=True)
    parser.add_argument('--record', required=True)
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    target = Path(args.out)
    if target.exists():
        parser.error('Output already exists; original records must not be overwritten')
    result = refine(args.image, json.loads(Path(args.record).read_text()))
    result['connectivity']['source_record_sha256'] = hashlib.sha256(Path(args.record).read_bytes()).hexdigest()
    with target.open('x') as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print(f'{METHOD}: {len(result["prediction"]["connections"])} unverified candidate links -> {target}')


if __name__ == '__main__':
    main()
