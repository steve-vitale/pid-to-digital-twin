"""Offline development comparison on exposed Synthetic sheets 0–3.

Labels enter only scoring after predictions have been written. No holdout claim,
model invocation, frozen-file edits, exports, downloads or network operations.
Historical run inputs are not distributed in this public snapshot. The command
requires those separately preserved inputs; it does not recreate sealed inference.
"""
import argparse
import hashlib
import json
from pathlib import Path
import time

import cv2
import numpy as np
import score_pid2graph as scorer
import trace_connections as legacy
import trace_connections_v2 as candidate

ROOT=Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def paths(sheet):
    if sheet in ('0','1'):
        data=ROOT/'data/external/pid2graph/PID2Graph/Complete/PID2Graph Synthetic'
        record=ROOT/f'runs/pid2graph-synthetic-adaptation/codex-native/{sheet}.json'
    else:
        data=ROOT/'data/external/pid2graph-synthetic-reserved23-frozen-v1'
        record=ROOT/f'runs/pid2graph-synthetic-reserved23-frozen-v1/attempts/{sheet}/attempt.json'
    return data/f'{sheet}.png', data/f'{sheet}.graphml',record


def pair_set(prediction):
    return {tuple(sorted((str(c['from']),str(c['to'])))) for c in prediction['connections']}


def counts(score):
    c=score['connections']
    return {**c,'false_positive':c['predicted']-c['tp'],'false_negative':c['in_key']-c['tp']}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',required=True)
    args=parser.parse_args()
    missing=[str(p.relative_to(ROOT)) for sheet in ("0","1","2","3")
             for p in paths(sheet) if not p.is_file()]
    if missing:
        parser.error("Historical evaluation inputs are not included in the public snapshot; "
                     "supply the separately preserved inputs before running. Missing: " + ", ".join(missing))
    out=Path(args.out)
    out.mkdir(exist_ok=False,parents=False)
    rows=[]
    for sheet in ('0','1','2','3'):
        png,key,source=paths(sheet)
        before={str(p.relative_to(ROOT)):sha(p) for p in (png,key,source)}
        record=json.loads(source.read_text());raw=record['prediction']
        start=time.monotonic()
        old={**raw,'connections':legacy.trace(png,raw['symbols'])}
        result=candidate.refine(png,record)
        result['connectivity']['source_record_sha256']=sha(source)
        result['connectivity']['review_overlay']=f'{sheet}.overlay.png'
        with (out/f'{sheet}.json').open('x') as stream:json.dump(result,stream,indent=2,allow_nan=False)
        elapsed=time.monotonic()-start
        # Exact recovered-pixel overlay, not inferred flow: red additions, blue detected boxes.
        image=cv2.imread(str(png));gray=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY)
        ink=legacy.binarize(gray);restored,_=candidate.recover_dashes(ink,raw['symbols'])
        image[(restored>ink)]=(0,0,255)
        h,w=gray.shape
        for symbol in raw['symbols']:
            a,b,c,d=legacy.symbol_box(symbol)
            start_point=(round(a*w/1000),round(b*h/1000));end_point=(round(c*w/1000),round(d*h/1000))
            cv2.rectangle(image,start_point,end_point,(255,0,0),2)
            cv2.putText(image,str(symbol['id']),start_point,cv2.FONT_HERSHEY_SIMPLEX,.8,(255,0,0),2)
        if not cv2.imwrite(str(out/f'{sheet}.overlay.png'),image):raise OSError('Overlay write failed')
        # Only now read the source annotations. They never enter candidate inference.
        scores={name:counts(scorer.score(key,pred,png)) for name,pred in
                (('raw',raw),('legacy_trace',old),('v2_trace',result['prediction']),
                 ('diagnostic_union', {**raw, 'connections': result['connectivity']['candidate_reconciliation']}))}
        nodes,adj=scorer.load_key(key,*scorer.png_size(png))
        matching=scorer.match(scorer.valid_symbols(raw),{k:v for k,v in nodes.items() if v['class'] in scorer.SCORED},False,scorer.THRESHOLDS['rough'])
        truth=scorer.asset_links(nodes,adj)
        def correct(pair):
            return frozenset(matching.get(x) for x in pair) in truth
        changed={}
        for method, candidate_prediction in (('v2_trace', result['prediction']),
                ('diagnostic_union', {**raw, 'connections': result['connectivity']['candidate_reconciliation']})):
            changed[method]={}
            for base,pred in (('raw',raw),('legacy_trace',old)):
                additions=pair_set(candidate_prediction)-pair_set(pred)
                removals=pair_set(pred)-pair_set(candidate_prediction)
                changed[method][base]={'correct_additions':[list(p) for p in sorted(additions) if correct(p)],
                               'incorrect_additions':[list(p) for p in sorted(additions) if not correct(p)],
                               'correct_link_removals':[list(p) for p in sorted(removals) if correct(p)],
                               'incorrect_link_removals':[list(p) for p in sorted(removals) if not correct(p)]}
        assert result['prediction']['symbols']==raw['symbols']
        assert before=={str(p.relative_to(ROOT)):sha(p) for p in (png,key,source)}
        row={'sheet':sheet,'scores':scores,'changed_links':changed,'inputs_sha256':before,
             'seconds_legacy_plus_v2':round(elapsed,3),'symbols_unchanged':True}
        rows.append(row);print(json.dumps({'sheet':sheet,'scores':scores}),flush=True)
    totals={}
    for name in ('raw','legacy_trace','v2_trace','diagnostic_union'):
        totals[name]={field:sum(r['scores'][name][field] for r in rows) for field in ('tp','predicted','in_key','false_positive','false_negative')}
    report={'method':candidate.METHOD,'status':'development_only_all_0_3_exposed',
        'warning':'Post-label development. No new holdout or full M3 reproduction. Collapsed undirected annotation links, not verified engineering connectivity.',
        'options':candidate.OPTIONS,'sheets':rows,'aggregate_0_3':totals,
        'source_inputs_unchanged':True,'model_calls':0}
    with (out/'evaluation.json').open('x') as stream:json.dump(report,stream,indent=2)


if __name__=='__main__':main()
