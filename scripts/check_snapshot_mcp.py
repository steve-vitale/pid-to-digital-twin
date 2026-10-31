"""Check the optional MCP snapshot server with actual local SDK and transport clients.

Install requirements-mcp.txt separately in an approved environment. Uses public fixtures, disposable files,
stdio and one temporary loopback HTTP listener; never contacts a company service or model API.
The committed sample is checked against the actual P-1 response; no output is published by this checker.
"""
import argparse
import asyncio
import copy
import hashlib
import json
import os
import socket
import subprocess
import sys
import tempfile
from pathlib import Path

import graph_export
import serve_snapshot
import test_context_register

ROOT = Path(__file__).resolve().parents[1]


async def exercise(client, graph, digest, label):
    summary = (await client.call_tool('snapshot_summary')).structured_content
    assert summary['snapshot_sha256'] == digest and summary['live'] is False
    assert summary['source_acquisition_time'] is None
    tools = (await client.list_tools()).tools
    assert len(tools) == 9 and all(t.annotations.read_only_hint and not t.annotations.open_world_hint for t in tools)
    asset = await client.call_tool('get_asset', {'asset_id':'P-1'})
    assert not asset.is_error
    assert asset.structured_content['result'] == next(n for n in graph['nodes'] if n['id']=='P-1')
    assert json.loads(asset.content[0].text) == asset.structured_content
    expected = [e for e in graph['edges'] if 'P-1' in (e['from'],e['to'])]
    edges = (await client.call_tool('get_relations', {'asset_id':'P-1','limit':100})).structured_content
    assert edges['result']['relations'] == expected and not edges['result']['truncated']
    questions = (await client.call_tool('list_questions', {'asset_id':'P-1'})).structured_content['result']
    assert questions['total'] > 0
    qid = questions['questions'][0]['id']
    question = (await client.call_tool('get_question', {'question_id':qid})).structured_content['result']
    assert question == next(q for q in graph['questions'] if q['id']==qid)
    stream = next(e for e in graph['edges'] if e['id'] == 'S1' and e['type'] == 'connects')
    assert (await client.call_tool('get_asset', {'asset_id': 'stream:S1'})).structured_content['result'] == stream
    stream_questions = (await client.call_tool('list_questions', {'asset_id': 'stream:S1'})).structured_content['result']
    assert any(q['id'] == 'E11@stream:S1' for q in stream_questions['questions'])
    expected_stream_relations = [e for e in graph['edges'] if e is stream or 'stream:S1' in (e['from'], e['to'])]
    assert (await client.call_tool('get_relations', {'asset_id': 'stream:S1'})).structured_content['result']['relations'] == expected_stream_relations
    for name,args in [('get_asset',{'asset_id':'../../outside.json'}),('find_assets',{'query':'   '}),
                      ('get_relations',{'asset_id':'P-1','limit':101}),
                      ('get_context', {'question_id': qid}), ('list_decisions', {}), ('list_context_questions', {})]:
        assert (await client.call_tool(name,args)).is_error
    assert (await client.call_tool('snapshot_summary')).structured_content == summary
    resource = await client.read_resource('engineering://snapshot/summary')
    assert json.loads(resource.contents[0].text) == summary
    print(f'PASS {label}: protocol {client.protocol_version}; evidence, errors and session retained',flush=True)
    return asset.structured_content


async def exercise_context(client, graph, register, graph_digest, context_digest, label):
    summary = (await client.call_tool('snapshot_summary')).structured_content
    assert summary['snapshot_sha256'] == graph_digest and summary['context_sha256'] == context_digest
    assert summary['result']['context_available'] and summary['result']['decisions'] == 2
    questions = (await client.call_tool('list_context_questions', {'limit': 50})).structured_content['result']
    assert [q['id'] for q in questions['questions']] == list(register['current'])
    removed = (await client.call_tool('get_context', {'question_id': 'Q2@P-2'})).structured_content['result']
    assert removed['current'] == register['current']['Q2@P-2'] and not removed['current']['present']
    assert removed['ownership_history'] == [r for r in register['ownership_history'] if r['question_id'] == 'Q2@P-2']
    current = (await client.call_tool('get_context', {'question_id': 'Q1@P-1'})).structured_content['result']
    assert current['current'] == register['current']['Q1@P-1']
    assert current['current']['answers'][0]['freshness'] == 'stale'
    seen, offset = [], 0
    while True:
        result = await client.call_tool('list_decisions', {'limit': 1, 'offset': offset})
        assert not result.is_error
        payload = result.structured_content
        assert payload['snapshot_sha256'] == graph_digest and payload['context_sha256'] == context_digest
        assert json.loads(result.content[0].text) == payload
        seen.extend(payload['result']['decisions'])
        offset = payload['result']['next_offset']
        if offset is None:
            break
    assert seen == register['decisions']  # Full prose/values/verdicts/old evidence, not only IDs/counts.
    assert seen[0]['decision'] == 'accepted' and seen[0]['plant_truth'] == 'unknown'
    assert (await client.call_tool('list_decisions', {'question_id': 'Q2@P-2'})).structured_content['result']['decisions'] == [seen[1]]
    for name, args in [('get_context', {'question_id': '../../outside.json'}),
                       ('list_decisions', {'offset': 2}), ('list_decisions', {'limit': True}),
                       ('list_context_questions', {'offset': 99})]:
        assert (await client.call_tool(name, args)).is_error
    assert (await client.call_tool('snapshot_summary')).structured_content == summary
    print(f'PASS {label}: complete bound answer/source/verdict/ownership history, removed question and rejection freshness', flush=True)


async def check_context(Client, StdioServerParameters, folder):
    fixture = test_context_register.ContextRegister()
    fixture.setUp()
    try:
        fixture.graph['nodes'][1]['attributes'][0]['source'] = {'kind': 'illustrative fixture'}
        fixture.save_inputs()
        fixture.two_accepted()
        fixture.graph['nodes'][1]['status'] = 'rejected'
        fixture.questions['questions'] = [q for q in fixture.questions['questions'] if q['id'] != 'Q2@P-2']
        fixture.manifest['documents'][1]['locators'][0]['questions'] = []
        fixture.save_inputs()
        fixture.refresh()
        graph_path, context_path = fixture.root/'bundle/enriched_graph.json', fixture.root/'bundle/context.json'
        graph, register = fixture.read('bundle/enriched_graph.json'), fixture.read()
        graph_raw, context_raw = graph_path.read_bytes(), context_path.read_bytes()
        graph_digest, context_digest = hashlib.sha256(graph_raw).hexdigest(), hashlib.sha256(context_raw).hexdigest()
        for mode in ('auto', 'legacy'):
            async with Client(serve_snapshot.create_server(graph_path, context_path), mode=mode) as client:
                await exercise_context(client, graph, register, graph_digest, context_digest, 'context-in-memory-'+mode)
                context_path.write_text('{}', encoding='utf-8')
                graph_path.write_text('{}', encoding='utf-8')
                assert (await client.call_tool('list_decisions')).structured_content['result']['decisions'] == register['decisions']
            graph_path.write_bytes(graph_raw)
            context_path.write_bytes(context_raw)
        command = [sys.executable, '-u', str(ROOT/'scripts/serve_snapshot.py'), '--graph', str(graph_path), '--context', str(context_path)]
        env = dict(os.environ, NO_PROXY='127.0.0.1,localhost')
        for mode in ('auto', 'legacy'):
            params = StdioServerParameters(command=sys.executable, args=command[1:], env=env)
            async with Client(params, mode=mode, read_timeout_seconds=15) as client:
                await exercise_context(client, graph, register, graph_digest, context_digest, 'context-stdio-'+mode)
        with socket.socket() as reservation:
            reservation.bind(('127.0.0.1', 0))
            port = reservation.getsockname()[1]
        with (folder/'context-http.log').open('w', encoding='utf-8') as log:
            proc = subprocess.Popen(command+['--transport', 'streamable-http', '--port', str(port)], cwd=ROOT,
                                    env=env, stdout=log, stderr=subprocess.STDOUT)
            try:
                url, ready = f'http://127.0.0.1:{port}/mcp', False
                for _ in range(50):
                    assert proc.poll() is None, 'Context HTTP server stopped before readiness'
                    try:
                        async with Client(url, read_timeout_seconds=1) as client:
                            await client.call_tool('snapshot_summary')
                        ready = True
                        break
                    except Exception:
                        await asyncio.sleep(0.1)
                assert ready, 'Context loopback server did not become ready'
                for mode in ('auto', 'legacy'):
                    async with Client(url, mode=mode, read_timeout_seconds=15) as client:
                        await exercise_context(client, graph, register, graph_digest, context_digest, 'context-loopback-http-'+mode)
            finally:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=5)
    finally:
        fixture.doCleanups()


async def check_pages(Client, path, base):
    graph = copy.deepcopy(base)
    node = next(n for n in graph['nodes'] if n['id']=='P-1')
    edge = next(e for e in graph['edges'] if e['from']=='P-1')
    graph['nodes'] = [dict(copy.deepcopy(node),id=f'PAGE-{i}',tag=f'PAGE-{i}') for i in range(123)]
    graph['edges'] = [dict(copy.deepcopy(edge),id=f'E-{i}',**{'from':'PAGE-0','to':f'PAGE-{i}'}) for i in range(1,123)]
    graph['questions'] = [{'id':f'Q-{i}','question':f'Question {i}','about':'PAGE-0',
                            'data_requests':[{'purpose':f'Request {i}'}]} for i in range(117)]
    graph['events'] = []
    path.write_text(json.dumps(graph),encoding='utf-8')
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    for mode in ('auto','legacy'):
        async with Client(serve_snapshot.create_server(path),mode=mode) as client:
            for tool,args,key,expected,cap in [
                    ('find_assets',{'query':'PAGE-'},'matches',graph['nodes'],50),
                    ('get_relations',{'asset_id':'PAGE-0'},'relations',graph['edges'],100),
                    ('list_questions',{'asset_id':'PAGE-0'},'questions',graph['questions'],50)]:
                seen=[];offset=0
                while True:
                    response=await client.call_tool(tool,dict(args,limit=cap,offset=offset))
                    assert not response.is_error
                    payload=response.structured_content;page=payload['result']
                    assert payload['snapshot_sha256']==digest and page['total']==len(expected)
                    assert page['offset']==offset and page['limit']==cap and len(page[key])<=cap
                    seen.extend(row['id'] for row in page[key]);offset=page['next_offset']
                    if offset is None:break
                assert seen==[row['id'] for row in expected] and len(set(seen))==len(expected)
                for bad in (-1,True,1.5,len(expected),len(expected)+1):
                    assert (await client.call_tool(tool,dict(args,offset=bad))).is_error
                assert not (await client.call_tool(tool,dict(args,limit=1))).is_error
            last=(await client.call_tool('get_question',{'question_id':'Q-116'})).structured_content['result']
            assert last==graph['questions'][-1]
            last_edges=(await client.call_tool('get_relations',{'asset_id':'PAGE-0','offset':100,'limit':100})).structured_content['result']
            assert last_edges['relations']==graph['edges'][100:]
        print(f'PASS in-memory-{mode}: all 123 assets,122 relations,117 questions reachable once',flush=True)


async def check_sizes(Client, path, base):
    for mode in ('auto','legacy'):
        for name,value,refuse in [('ascii','x'*10000,False),('large-ascii','x'*1100000,True),
                                  ('escaped','\\'*400000,True),('utf8','工'*250000,False)]:
            graph=copy.deepcopy(base)
            node=next(n for n in graph['nodes'] if n['id']=='P-1')
            node['attributes'].append({'name':'size-control','value':value,'status':'unverified','source':{'kind':'test'}})
            path.write_text(json.dumps(graph,ensure_ascii=False),encoding='utf-8')
            async with Client(serve_snapshot.create_server(path),mode=mode) as client:
                result=await client.call_tool('get_asset',{'asset_id':'P-1'})
                assert result.is_error==refuse,(mode,name)
                assert len(result.model_dump_json(by_alias=True).encode('utf-8'))<serve_snapshot.MAX_RESPONSE_BYTES
                if refuse:
                    assert 'Serialized MCP result exceeds' in result.content[0].text and value not in result.content[0].text
                else:
                    assert result.structured_content['result']==node
                    assert json.loads(result.content[0].text)==result.structured_content
                assert not (await client.call_tool('snapshot_summary')).is_error
        for value,refuse in [('x'*10000,False),('\\'*600000,True)]:
            graph=copy.deepcopy(base);graph['source_model']=value
            path.write_text(json.dumps(graph),encoding='utf-8')
            async with Client(serve_snapshot.create_server(path),mode=mode) as client:
                try:
                    result=await client.read_resource('engineering://snapshot/summary')
                except Exception as exc:
                    assert refuse and 'Serialized MCP resource result exceeds' in str(exc)
                else:
                    assert not refuse
                    assert len(result.model_dump_json(by_alias=True).encode('utf-8'))<serve_snapshot.MAX_RESPONSE_BYTES
                assert not (await client.call_tool('find_assets',{'query':'P-1','limit':1})).is_error
        print(f'PASS in-memory-{mode}: six actual serialized result-size controls',flush=True)


async def run(Client, StdioServerParameters, folder):
    graph=graph_export.build(ROOT/'data/bayer_rt/process_model.json',questions=ROOT/'examples/opportunity-screen/bayer/questions.json')
    packet=folder/'graph.json'
    packet.write_text(json.dumps(graph,ensure_ascii=False,indent=1)+'\n',encoding='utf-8',newline='\n')
    digest=hashlib.sha256(packet.read_bytes()).hexdigest()
    sample=None
    for mode in ('auto','legacy'):
        server=serve_snapshot.create_server(packet)
        async with Client(server,mode=mode) as client:
            sample=await exercise(client,graph,digest,'in-memory-'+mode)
            # A changed file cannot silently refresh the server or its fingerprint.
            packet.write_text('{}',encoding='utf-8')
            assert (await client.call_tool('get_asset',{'asset_id':'P-1'})).structured_content==sample
        packet.write_text(json.dumps(graph,ensure_ascii=False,indent=1)+'\n',encoding='utf-8',newline='\n')
    command=[sys.executable,'-u',str(ROOT/'scripts/serve_snapshot.py'),'--graph',str(packet)]
    env=dict(os.environ,NO_PROXY='127.0.0.1,localhost')
    for mode in ('auto','legacy'):
        params=StdioServerParameters(command=sys.executable,args=command[1:],env=env)
        async with Client(params,mode=mode,read_timeout_seconds=15) as client:
            await exercise(client,graph,digest,'stdio-'+mode)
    with socket.socket() as reservation:
        reservation.bind(('127.0.0.1',0));port=reservation.getsockname()[1]
    with (folder/'http.log').open('w',encoding='utf-8') as log:
        proc=subprocess.Popen(command+['--transport','streamable-http','--port',str(port)],cwd=ROOT,
                              env=env,stdout=log,stderr=subprocess.STDOUT)
        try:
            url=f'http://127.0.0.1:{port}/mcp';ready=False
            for attempt in range(50):
                assert proc.poll() is None,'HTTP server stopped before readiness'
                try:
                    async with Client(url,read_timeout_seconds=1) as client:
                        await client.call_tool('snapshot_summary')
                    ready=True;break
                except Exception:
                    await asyncio.sleep(0.1)
            assert ready,'Live loopback server did not become ready'
            for mode in ('auto','legacy'):
                async with Client(url,mode=mode,read_timeout_seconds=15) as client:
                    await exercise(client,graph,digest,'loopback-http-'+mode)
        finally:
            proc.terminate()
            try:proc.wait(timeout=5)
            except subprocess.TimeoutExpired:proc.kill();proc.wait(timeout=5)
    assert hashlib.sha256(packet.read_bytes()).hexdigest()==digest
    await check_pages(Client,folder/'pages.json',graph)
    await check_sizes(Client,folder/'sizes.json',graph)
    await check_context(Client, StdioServerParameters, folder)
    return sample


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.parse_args(argv)
    try:
        from mcp import Client
        from mcp.client.stdio import StdioServerParameters
    except ImportError:
        parser.error('Install requirements-mcp.txt separately in the approved developer environment')
    with tempfile.TemporaryDirectory(prefix='snapshot-mcp-check-') as folder:
        sample=asyncio.run(run(Client,StdioServerParameters,Path(folder)))
    committed=ROOT/'examples/internal-mcp/sample_asset.json'
    prior=json.loads(committed.read_text(encoding='utf-8'))
    assert {k:v for k,v in prior.items() if k!='loaded_at'}=={k:v for k,v in sample.items() if k!='loaded_at'}
    print('PASS local snapshot MCP checks; no company/Copilot/OT acceptance claimed.',flush=True)
    return 0


if __name__=='__main__':
    raise SystemExit(main())
