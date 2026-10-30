"""Check explicit source disagreements and selective staleness on synthetic copies.

Run the README prepare/apply commands first. Uses only the standard library.
Original source files, proposed answers and model inputs are never overwritten.
"""
import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path

packet = Path(__file__).resolve().parent
root = packet.parents[2]
script = root/'scripts/context_register.py'
manifest = json.loads((packet/'sources.json').read_text(encoding='utf-8'))
register_path = packet/'run/context.json'
if not register_path.is_file():
    raise SystemExit('Run the README prepare/apply commands first: run/context.json is missing.')
register = json.loads(register_path.read_text(encoding='utf-8'))
key = json.loads((packet/'source_key.json').read_text(encoding='utf-8'))
assert (packet/'run/context.md').read_text(encoding='utf-8') == (packet/'expected/context.md').read_text(encoding='utf-8'), 'committed report differs from the README run'
print('Committed readable report matches the README run')
assert len(register['decisions']) == 44
assert register['decisions'][:22] == json.loads((packet/'history/before-appearances.context.json').read_bytes())['decisions']
assert len(register['current']) == 21
assert register['current']['CTX-04@FIC301']['state'] == 'disputed'
assert all(not d.get('reviewer') and d['plant_truth'] == 'unknown' and d['decision'] == 'proposed'
           for d in register['decisions'])
assert all(v['owner'] is None and v['ownership'] == 'needs_owner' for v in register['current'].values())
by_answer = {d['answer_id']: d for d in register['decisions']}
graph = json.loads((packet/'run/enriched_graph.json').read_text(encoding='utf-8'))
assert len(graph['questions']) == 21 and graph['counts']['questions'] == 21
node_ids = {n['id'] for n in graph['nodes']}
for fact in key['facts']:
    answer = by_answer['PRONTO-'+fact['id']]
    source = answer['evidence']['source']
    assert fact['asset_id'] in node_ids
    assert source['id'] == fact['document_id']
    assert source['revision'] == fact['document_revision']
    assert source['sha256'] == fact['raw_sha256']
    assert source['locator_id'] == fact['locator_id']
    assert source['locator'] == fact['locator']
    assert answer['question_id'] == fact['question_id']
for fid in ('F07','F08','F09'):
    assert by_answer['PRONTO-'+fid]['value'] == 'not enabled'
assert by_answer['PRONTO-F04']['value'] == 'FT302'
assert by_answer['PRONTO-F18']['value'] == 'FIR305'
assert not ({'FIR305','FIR302'} & node_ids), 'unconfirmed identifiers became asset aliases'
assert {'V10','V11'} <= node_ids
print('22 exact source/locator bindings and stable asset joins; three disabled-limit controls; unresolved source labels retained')
(packet/'.work').mkdir(exist_ok=True)
for did, expected in [('PRONTO-REPORT',6),('PRONTO-ALARMS',7)]:
    variant = copy.deepcopy(manifest)
    for doc in variant['documents']:
        original = root/'data/external'/doc['path']
        doc['path'] = 'data/external/'+doc['path']
        if doc['id'] != did:
            continue
        revised = packet/'.work'/('synthetic-'+did+original.suffix)
        # A harmless trailing PDF comment or ZIP trailing bytes changes the actual
        # copied document hash. No original bytes or workbook cells are edited.
        revised.write_bytes(original.read_bytes()+b'\n% SYNTHETIC REVISION FOR STALENESS CHECK ONLY\n')
        doc['path'] = revised.relative_to(root).as_posix()
        doc['revision'] += '-synthetic-revision-2'
        doc['sha256'] = hashlib.sha256(revised.read_bytes()).hexdigest()
    path = packet/'.work'/('sources-'+did+'.json')
    path.write_text(json.dumps(variant,indent=2)+'\n',encoding='utf-8')
    out = packet/'.work'/('staleness-'+did)
    cmd = [sys.executable,'-S',str(script),'apply','--model',str(packet/'model.json'),
           '--questions',str(packet/'questions.json'),'--sources',str(path),'--source-root',str(root),
           '--register',str(packet/'run/context.json'),'--out',str(out)]
    result = subprocess.run(cmd,cwd=root,capture_output=True,text=True)
    assert result.returncode == 0, result.stderr
    fresh = json.loads((out/'context.json').read_text(encoding='utf-8'))
    got = {a['answer_id'] for q in fresh['current'].values() for a in q['answers'] if a['freshness']=='stale'}
    want = {'PRONTO-'+f['id'] for f in key['facts'] if f['document_id']==did}
    assert got == want, (did,got,want)
    assert len(got) == expected
    assert fresh['decisions'] == register['decisions'], 'history changed during freshness refresh'
    print(did+': exactly '+str(expected)+' dependent answers stale; '+str(22-expected)+' unrelated current; history unchanged')
print('All packet consistency checks passed. This is deterministic development evidence, not independent review.')
