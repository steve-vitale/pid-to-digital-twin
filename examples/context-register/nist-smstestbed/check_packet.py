"""Check development packet bindings and document-specific staleness on copies.

Run the README prepare/apply commands first. Standard library only. Original
documents and model/question inputs are never edited by this check.
"""
import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path

PACKET = Path(__file__).resolve().parent
ROOT = PACKET.parents[2]
SCRIPT = ROOT/'scripts/context_register.py'
SOURCE_ROOT = ROOT/'data/external/nist-smstestbed'


def run(out, sources, source_root, register=None, questions=None, expect=0):
    cmd = [sys.executable,'-S',str(SCRIPT),'apply','--model',str(PACKET/'model.json'),
           '--questions',str(questions or PACKET/'questions.json'),'--sources',str(sources),
           '--source-root',str(source_root),'--out',str(out)]
    if register:
        cmd += ['--register',str(register)]
    result = subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True)
    assert result.returncode == expect, result.stdout+result.stderr
    return result


def check():
    register_path = PACKET/'run/context.json'
    if not register_path.is_file():
        raise SystemExit('Run the README prepare/apply commands first: run/context.json is missing.')
    original = json.loads(register_path.read_text(encoding='utf-8'))
    expected_report = PACKET/'expected_context.md'
    if expected_report.is_file():
        assert (PACKET/'run/context.md').read_bytes() == expected_report.read_bytes(), 'readable report differs from the pinned development record'
    manifest = json.loads((PACKET/'sources.json').read_text(encoding='utf-8'))
    key = json.loads((PACKET/'source_key.json').read_text(encoding='utf-8'))
    graph = json.loads((PACKET/'run/enriched_graph.json').read_text(encoding='utf-8'))
    assert len(original['decisions']) == 20 and len(original['current']) == 8
    assert original['decisions'][:10] == json.loads((PACKET/'history/before-appearances.context.json').read_bytes())['decisions']
    assert len(graph['questions']) == graph['counts']['questions'] == 8
    assert not original['ownership_history']
    assert all(q['owner'] is None and q['ownership']=='needs_owner' for q in original['current'].values())
    assert all(q['state']!='disputed' for q in original['current'].values()), 'different revisions became a simultaneous contradiction'
    assert original['current']['SMS-DEPLOYED-REVISION@mtc_adapter008']['state']=='needs_data'
    assert all(d['decision']=='proposed' and d['source_match']=='match' and d['plant_truth']=='unknown'
               and not d['owner'] and not d['reviewer'] and not d['reviewed_on'] for d in original['decisions'])
    node_ids = {n['id'] for n in graph['nodes']}
    assert 'mtc_adapter008' in node_ids and 'Hurco04-path_7' not in node_ids
    answers = {d['answer_id']:d for d in original['decisions']}
    for fact in key['facts']:
        answer = answers['SMS-'+fact['id']]
        source = answer['evidence']['source']
        assert source == dict(id=fact['document_id'],revision=fact['document_revision'],sha256=fact['raw_sha256'],
                              locator_id=fact['locator_id'],locator=fact['locator'])
        assert answer['evidence']['assets'][0]['id'] == 'mtc_adapter008'
        assert answer['question_id'] == fact['question_id']
    assert answers['SMS-N03']['claim_key'] != answers['SMS-N04']['claim_key']
    assert answers['SMS-N09']['value'] == 'unknown'
    assert 'UNAVAILABLE' in answers['SMS-N07']['value'] and '; 0 at ' in answers['SMS-N07']['value']
    print('10 exact original-source bindings; machine UUID joins; revision-scoped meanings; no inferred owner/review/deployment truth')

    scratch = PACKET/'.work'
    scratch.mkdir(exist_ok=True)
    counts = {}
    for did, expected in [('SMS-DEV-2016',3),('SMS-DEV-2017',3),('SMS-RAW-20170217',4),('SMS-NOTICE',0)]:
        variant = copy.deepcopy(manifest)
        for doc in variant['documents']:
            original_path = SOURCE_ROOT/doc['path']
            doc['path'] = original_path.relative_to(ROOT).as_posix()
            if doc['id'] != did:
                continue
            changed = scratch/('synthetic-'+did+original_path.suffix)
            suffix = (b'\n<!-- SYNTHETIC CONTEXT REVISION CHECK ONLY -->\n' if original_path.suffix=='.xml'
                      else b'\n2030-01-01T00:00:00Z|SYNTHETIC_REVISION|TEST_ONLY\n' if did=='SMS-RAW-20170217'
                      else b'\n<!-- SYNTHETIC NOTICE REVISION CHECK ONLY -->\n')
            changed.write_bytes(original_path.read_bytes()+suffix)
            doc.update(path=changed.relative_to(ROOT).as_posix(),revision=doc['revision']+'-synthetic-2',
                       sha256=hashlib.sha256(changed.read_bytes()).hexdigest())
        sources = scratch/('sources-'+did+'.json')
        sources.write_text(json.dumps(variant,indent=2)+'\n',encoding='utf-8')
        out = scratch/('staleness-'+did)
        run(out,sources,ROOT,register_path)
        fresh = json.loads((out/'context.json').read_text(encoding='utf-8'))
        stale = {a['answer_id'] for q in fresh['current'].values() for a in q['answers'] if a['freshness']=='stale'}
        want = {'SMS-'+f['id'] for f in key['facts'] if f['document_id']==did}
        assert stale == want and len(stale)==expected, (did,stale,want)
        assert fresh['decisions']==original['decisions'], 'refresh changed retained decision history'
        counts[did] = expected
        print(did+': exactly '+str(expected)+' dependent stale; '+str(10-expected)+' current; history unchanged')
        if did=='SMS-DEV-2016':
            bad = copy.deepcopy(variant)
            old_pin = next(d['sha256'] for d in manifest['documents'] if d['id']==did)
            next(d for d in bad['documents'] if d['id']==did)['sha256'] = old_pin
            bad_path = scratch/'sources-hash-mismatch.json'
            bad_path.write_text(json.dumps(bad),encoding='utf-8')
            result = run(scratch/'rejected-hash',bad_path,ROOT,expect=2)
            assert 'sha256 disagrees' in result.stderr
    questions = json.loads((PACKET/'questions.json').read_text(encoding='utf-8'))
    questions['questions'][0]['assets'].append(dict(id='Hurco04-path_7'))
    wrong = scratch/'questions-unregistered-id.json'
    wrong.write_text(json.dumps(questions),encoding='utf-8')
    result = run(scratch/'rejected-id',PACKET/'sources.json',SOURCE_ROOT,questions=wrong,expect=2)
    assert 'unknown asset id' in result.stderr
    print('Wrong raw hash and unregistered reused signal-as-asset both rejected.')
    result = dict(schema='nist-sms-context-development-check-1',source_bindings=10,questions=8,
                  stale_by_synthetic_document=counts,unrelated_notice_stale=0,
                  hash_mismatch_rejected=True,unregistered_signal_rejected=True,
                  no_human_signoff=True,evidence_role='seen development cases, not held out')
    (PACKET/'run/packet_checks.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    return result


if __name__ == '__main__':
    check()
