"""Rehearse four fictional owned packets with existing local graph/context tools."""
import argparse,asyncio,copy,csv,hashlib,importlib.metadata,json,os,shutil,subprocess,sys,time
from pathlib import Path
EXAMPLE=Path(__file__).resolve().parent
ROOT=EXAMPLE.parents[1]
INPUTS=EXAMPLE/'inputs'
ENV = dict(os.environ, PYTHONIOENCODING='utf-8')
SCOPES=('site-a-process','site-a-ei','site-a-maintenance','site-b-process')
PUMP='P-1'
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,o):
 p.parent.mkdir(parents=True,exist_ok=True)
 p.write_bytes((json.dumps(o,indent=2,ensure_ascii=False,allow_nan=False)+'\n').encode('utf-8'))
def files(p):return {q.relative_to(p).as_posix():sha(q) for q in p.rglob('*') if q.is_file()} if p.exists() else None

def selected(out,slug,state):return out/'packets'/slug/state

def validate_states(register,expected):return {q:v['state'] for q,v in register['current'].items()}==expected

class Exercise:
 def __init__(self,out):
  self.out=out;self.commands=[];self.checks=[];self.original=files(INPUTS)
  self.expected=read(INPUTS/'EXPECTED.json');self.mapping=read(INPUTS/'OWNED-SCOPES.json')
 def check(self,label,value):
  self.checks.append({'label':label,'pass':bool(value)});write(self.out/'checks.json',self.checks);assert value,label
 def cli(self,label,script,args,expected=0,error=None):
  command=[sys.executable,'-S',str(ROOT/'scripts'/script),*map(str,args)]
  before=time.perf_counter();p=subprocess.run(command,cwd=ROOT,env=ENV,capture_output=True);wall=time.perf_counter()-before
  (self.out/(label+'.stdout')).write_bytes(p.stdout);(self.out/(label+'.stderr')).write_bytes(p.stderr)
  self.commands.append({'label':label,'command':command,'exit':p.returncode,'wall_seconds':wall})
  write(self.out/'commands.json',self.commands)
  self.check(label+'/exit',p.returncode==expected)
  if error:self.check(label+'/specific refusal',error.encode() in p.stderr)
  self.check(label+'/all frozen input bytes unchanged',files(INPUTS)==self.original)
  return p
 def args(self,slug,revision,out,register=None,answers=None,bad=False):
  scope=INPUTS/slug
  name=('sources-'+revision+('-old-pin' if bad else '')+'.json') if slug in SCOPES[:2] else 'sources.json'
  args=['--model',scope/'graph.json','--questions',scope/'questions.json','--sources',scope/name,'--out',out]
  if register:args+=['--register',register]
  if answers:args+=['--answers',answers]
  return args
 def answers(self,slug,prepared,key,name):
  with (prepared/'answers.csv').open(encoding='utf-8',newline='') as f:columns=csv.DictReader(f).fieldnames
  with (prepared/'evidence_choices.csv').open(encoding='utf-8',newline='') as f:choices=list(csv.DictReader(f))
  intents=copy.deepcopy(read(INPUTS/'ANSWER-INTENTS.json')[key]);rows=[]
  if name.endswith('reverse'):intents.reverse()
  owner=next(p['owning_role'] for p in self.mapping['packets'] if p['packet']==slug)
  for intent in intents:
   matches=[r for r in choices if r['question_id']==intent['question_id'] and r['source_id']==intent['source_id']]
   self.check(name+'/'+intent['answer_id']+'/one real prepared binding',len(matches)==1)
   choice=matches[0];row={k:'' for k in columns};row.update(intent)
   row.update(owner=owner,assigned_by='training-assignment-coordinator',assigned_on='2026-10-31',reviewed_on='2026-10-31',locator_id=choice['locator_id'],evidence_fingerprint=choice['evidence_fingerprint'],note='Fictional local source/proposal record; no company authority or observed plant truth.')
   rows.append(row)
  target=self.out/'sheets'/(name+'.csv');target.parent.mkdir(exist_ok=True)
  with target.open('w',encoding='utf-8',newline='') as f:
   w=csv.DictWriter(f,fieldnames=columns,lineterminator='\n');w.writeheader();w.writerows(rows)
  return target
 def refusal(self,slug,kind,populated):
  label=slug+'-'+kind+('-populated' if populated else '-absent');dest=self.out/'refusals'/label
  if populated:dest.mkdir(parents=True);(dest/'keep.txt').write_bytes(b'Preserved existing output.\n')
  before=files(dest)
  old=kind=='old-sheet'
  self.cli(label,'context_register.py',['apply' if old else 'prepare',*self.args(slug,'B',dest,register=selected(self.out,slug,'refreshed')/'context.json' if old else None,answers=self.out/'sheets'/(slug+'-A.csv') if old else None,bad=not old)],expected=2,error='stale or missing evidence_fingerprint' if old else 'raw-byte sha256 disagrees')
  self.check(label+'/no output mutation',files(dest)==before)
 def run(self):
  self.out.mkdir(parents=True)
  shutil.copytree(INPUTS,self.out/'source-records')
  initial={}
  for slug in SCOPES:
   self.cli(slug+'-graph-check','graph_export.py',['--check',INPUTS/slug/'graph.json'])
   prepared=selected(self.out,slug,'prepared-A')
   self.cli(slug+'-prepare-A','context_register.py',['prepare',*self.args(slug,'A',prepared)])
   sheet=self.answers(slug,prepared,slug+'/A',slug+'-A')
   dest=selected(self.out,slug,'A')
   self.cli(slug+'-apply-A','context_register.py',['apply',*self.args(slug,'A',dest,register=prepared/'context.json',answers=sheet)])
   initial[slug]=read(dest/'context.json')
  for slug in SCOPES[:2]:
   for populated in (False,True):self.refusal(slug,'bad-pin',populated)
  for slug in SCOPES:
   self.cli(slug+'-refresh','context_register.py',['apply',*self.args(slug,'B',selected(self.out,slug,'refreshed'),register=selected(self.out,slug,'A')/'context.json')])
  for populated in (False,True):self.refusal('site-a-ei','old-sheet',populated)
  slug='site-a-ei';prepared=selected(self.out,slug,'prepared-B');refreshed=selected(self.out,slug,'refreshed')
  self.cli('ei-prepare-B','context_register.py',['prepare',*self.args(slug,'B',prepared,register=refreshed/'context.json')])
  sheet=self.answers(slug,prepared,slug+'/B','site-a-ei-B')
  base=selected(self.out,slug,'B')
  self.cli('ei-apply-B','context_register.py',['apply',*self.args(slug,'B',base,register=refreshed/'context.json',answers=sheet)])
  pprepared=selected(self.out,slug,'prepared-proposals')
  self.cli('ei-prepare-proposals','context_register.py',['prepare',*self.args(slug,'B',pprepared,register=base/'context.json')])
  base_hash=sha(base/'context.json')
  for order in ('forward','reverse'):
   sheet=self.answers(slug,pprepared,'proposals','proposals-'+order)
   self.cli('ei-apply-proposals-'+order,'context_register.py',['apply',*self.args(slug,'B',selected(self.out,slug,'proposals-'+order),register=base/'context.json',answers=sheet)])
   self.check(order+'/same immutable B base',sha(base/'context.json')==base_hash)
  for state,expected in self.expected['states'].items():
   slug,stage=state.split('/');folder=selected(self.out,slug,stage);c=read(folder/'context.json')
   self.check(state+'/exact frozen state table',validate_states(c,expected))
   self.check(state+'/unknown plant truth',all(d['plant_truth']=='unknown' for d in c['decisions']))
   a=initial[slug]
   self.check(state+'/exact old ordered decisions',c['decisions'][:len(a['decisions'])]==a['decisions'])
   self.check(state+'/exact old ordered ownership',c['ownership_history'][:len(a['ownership_history'])]==a['ownership_history'])
   self.cli(state.replace('/','-')+'-selected-check','graph_export.py',['--check',folder/'enriched_graph.json'])
  for state,expected in self.expected['freshness'].items():
   slug,stage=state.split('/');c=read(selected(self.out,slug,stage)/'context.json')
   actual={a['answer_id']:a['freshness'] for q in c['current'].values() for a in q['answers']}
   self.check(state+'/exact freshness table',actual==expected)
  for slug in SCOPES[2:]:
   a=selected(self.out,slug,'A');b=selected(self.out,slug,'refreshed')
   self.check(slug+'/actual refreshed complete register exact',read(a/'context.json')==read(b/'context.json'))
   self.check(slug+'/actual refreshed four selected raw outputs exact',all(sha(a/n)==sha(b/n) for n in ('context.json','context.md','enriched_graph.json','enriched_questions.json')))
  loop=initial['site-a-ei']['current']['LOOP@P-1']
  for stage in ('refreshed','B','proposals-forward','proposals-reverse'):
   c=read(selected(self.out,'site-a-ei',stage)/'context.json')
   self.check('ei/'+stage+'/complete independent loop current wrapper exact',c['current']['LOOP@P-1']==loop)
   self.check('ei/'+stage+'/complete independent loop decision and fingerprint exact',c['decisions'][1]==initial['site-a-ei']['decisions'][1])
  forward=read(selected(self.out,'site-a-ei','proposals-forward')/'context.json');reverse=read(selected(self.out,'site-a-ei','proposals-reverse')/'context.json');b=read(base/'context.json')
  records=lambda c:sorted([d for d in c['decisions'] if d['question_id']=='PROPOSAL@P-1'],key=lambda d:d['answer_id'])
  props=records(forward)
  self.check('proposal reversal complete semantic records including all metadata exact',props==records(reverse) and len(props)==2)
  self.check('proposal histories distinct ordered records preserved',forward['decisions'][-2:]==list(reversed(reverse['decisions'][-2:])))
  self.check('proposal exact same original base prefix',all(c['decisions'][:len(b['decisions'])]==b['decisions'] for c in (forward,reverse)))
  self.check('proposal same owner history and current state',forward['ownership_history']==reverse['ownership_history'] and forward['current']==reverse['current'])
  self.check('proposal same source base fingerprint',props[0]['evidence']==props[1]['evidence'] and props[0]['evidence_fingerprint']==props[1]['evidence_fingerprint'])
  self.check('proposal distinct attributed active proposed partial values',{d['value'] for d in props}=={'200 kPa','220 kPa'} and len({d['reviewer'] for d in props})==2 and all(d['owner']=='training-controls-owner' and d['decision']=='proposed' and d['answer_state']=='partial' and d['plant_truth']=='unknown' for d in props))
  self.check('proposal exact disputed claim',forward['current']['PROPOSAL@P-1']['disputed_claims']==['proposed-pressure-kPa'])
  self.check('all exact fixture bytes retained',files(INPUTS)==self.original and files(self.out/'source-records')==self.original)
  self.report(initial)
  write(self.out/'CLI-RESULT.json',{'pass':True,'actual_CLIs':len(self.commands),'assertions':len(self.checks),'input_raw_sha256':self.original,'scope':'Actual local synthetic composition; SDK and independent/company acceptance separate.'})
 def report(self,initial):
  final={'site-a-process':'refreshed','site-a-ei':'proposals-forward','site-a-maintenance':'refreshed','site-b-process':'refreshed'}
  observations=[];refreshed_answers=[]
  for slug in SCOPES:
   for qid,current in read(selected(self.out,slug,'refreshed')/'context.json')['current'].items():
    for answer in current['answers']:
     d=next(d for d in initial[slug]['decisions'] if d['id']==answer['decision_id'])
     refreshed_answers.append({'packet':slug,'question':qid,'answer_id':answer['answer_id'],'source':d['evidence']['source']['id'],'freshness':answer['freshness'],'changed':answer['changed']})
  dependent=[r for r in refreshed_answers if r['source']=='PROCESS-BASIS'];independent=[r for r in refreshed_answers if r['source']!='PROCESS-BASIS']
  self.check('observed source-only dependency fanout exactly2stale',len(dependent)==2 and all(r['freshness']=='stale' for r in dependent))
  self.check('observed independent actual refresh exactly3current',len(independent)==3 and all(r['freshness']=='current' for r in independent))
  worked=self.out/'worked';worked.mkdir();sources=worked/'source-records'
  for p in INPUTS.rglob('*'):
   if not p.is_file() or p.name in ('ANSWER-INTENTS.json','EXPECTED.json','sources-B-old-pin.json'):continue
   dest=sources/p.relative_to(INPUTS);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
  for slug,stage in final.items():
   record=next(p for p in self.mapping['packets'] if p['packet']==slug);folder=selected(self.out,slug,stage)
   source_manifest=INPUTS/slug/('sources-B.json' if slug in SCOPES[:2] else 'sources.json')
   docs=read(source_manifest)['documents']
   sourcebytes=[{'id':d['id'],'revision':d['revision'],'raw_sha256':d['sha256'],'bytes':(INPUTS/slug/d['path']).stat().st_size,'retained_original':'source-records/'+slug+'/'+d['path']} for d in docs]
   obs={**record,'selected_state':stage,'graph_raw_sha256':sha(folder/'enriched_graph.json'),'context_raw_sha256':sha(folder/'context.json'),'questions_raw_sha256':sha(folder/'enriched_questions.json'),'graph_bytes':(folder/'enriched_graph.json').stat().st_size,'context_bytes':(folder/'context.json').stat().st_size,'declared_source_bytes_sum':sum(d['bytes'] for d in sourcebytes),'sources':sourcebytes}
   observations.append(obs)
   dest=worked/'packets'/slug/'selected';dest.mkdir(parents=True)
   for name in ('enriched_graph.json','context.json','enriched_questions.json','context.md'):shutil.copyfile(folder/name,dest/name)
  for source_stage,dest_stage in [('refreshed','source-refreshed'),('B','proposal-base-B'),('proposals-reverse','reverse-order')]:
   dest=worked/'packets/site-a-ei'/dest_stage;dest.mkdir(parents=True)
   for name in ('enriched_graph.json','context.json','enriched_questions.json','context.md'):shutil.copyfile(selected(self.out,'site-a-ei',source_stage)/name,dest/name)
  write(worked/'COMPOSITION.json',{'kind':'teaching-composition-index-result','product_schema':False,'mapping_input':self.mapping,'packets':observations,'scope':'Explicit supplied mapping and selected local records; no federation/identity/auth consumer.'})
  write(worked/'OBSERVATIONS.json',{'metric_definitions':'Frozen before execution in private author controls; per-command wall time also retained privately.','post_source_refresh_answers':refreshed_answers,'dependent_stale_count':len(dependent),'independent_current_count':len(independent),'selected_packet_sizes':observations,'per_command_wall_seconds':[{'label':c['label'],'exit':c['exit'],'wall_seconds':c['wall_seconds']} for c in self.commands],'environment':'One actual Windows environment and tiny fictional workload; not throughput/large-team capacity or human review time.','company_acceptance':'not performed','recipient_acceptance':'not performed'})
  lines=['# Four owned scopes; one explicit source revision','','All records and people are invented. This is local source/decision accounting, not a company release, identity resolver or scale benchmark.','','| Scope | Supplied company identity | Selected outcome | Receiving owner |','|---|---|---|---|']
  for row in observations:
   slug=row['packet'];outcome={'site-a-process':'Old basis answer stale; new source review needed','site-a-ei':'Fresh Bpartial basis; loop current; two unresolved proposals disputed','site-a-maintenance':'Actual unchanged refresh; independent answer current','site-b-process':'Actual unchanged refresh; separate Site B answer current'}[slug]
   lines.append('| ['+row['scope']+'](packets/'+slug+'/selected/context.md) | `'+row['supplied_company_asset']+'` | '+outcome+' | '+row['owning_role']+' |')
  lines+=['','Process and E&I explicitly receive identical revision A/B publication bytes. Only those two source-bound answers stale on the first refresh. The separately sourced E&I loop, Maintenance and Site B records remain current after actual refresh. The full selected P-1 asset, relationships and authored questions remain unchanged; incoming B configuration interpretation is unresolved. Whole-document hashes, not field watchers, drive this source-only example.','','The same native tag P-1 appears in all scopes. The [authored identity map and exact packet/source pins](COMPOSITION.json) supplies three Site A references and one distinct Site B identity. The toolkit does not resolve, merge or enforce those company namespaces.','','The source [unresolved options](source-records/site-a-ei/proposal-options.txt) contains 200 kPa and220 kPa in the same declared pressure scope and units. Distinct answer IDs, reviewers, same owner and same prepared source/base preserve both. [Forward selected history](packets/site-a-ei/selected/context.json), [reversed history](packets/site-a-ei/reverse-order/context.json) and [immutable proposal base](packets/site-a-ei/proposal-base-B/context.json) remain complete. Neither proposed value wins. This is literal-string local dispute accounting, not unit inference or concurrent editing.','','Read the [receiving brief](HANDOFF.md), [source-refreshed E&I state](packets/site-a-ei/source-refreshed/context.md), and [bounded observations](OBSERVATIONS.json). Plant truth remains unknown; real company/recipient acceptance was not performed.','']
  (worked/'CHANGE-REVIEW.md').write_bytes('\n'.join(lines).encode())
  brief=['# Fictional receiving handoff','','Status: draft; actual recipient/company acceptance not performed. Local source matches grant no organizational release.','','Next owner actions: Process owner reviews incoming Bbasis; controls owner reconciles the two proposed pressure bases and unresolved configuration through the existing company acceptance route. Maintenance and Site Bowners retain their independent scopes and review actual applicability. No logic, equipment, controlled original or operating limit is changed.','','| Scope | Selected graph SHA-256 | Selected context SHA-256 |','|---|---|---|']
  for row in observations:
   slug=row['packet'];brief.append('| '+row['scope']+' | ['+row['graph_raw_sha256']+'](packets/'+slug+'/selected/enriched_graph.json) | ['+row['context_raw_sha256']+'](packets/'+slug+'/selected/context.json) |')
  brief+=['','Originals, exact source versions/locators, complete histories, owners and explicit supplied mapping travel with this folder. See [composition/source pins](COMPOSITION.json) and [review](CHANGE-REVIEW.md).','','Not implemented or performed: authenticated owner release, company stale-base/namespace checks, concurrent-write control, subscriptions, cross-packet search, revocation, retry/recovery, actual recipient usefulness, physical/safety acceptance or large-company performance. Copilot/manual and approved disconnected packet review remain valid; this exercise opens no port.','']
  (worked/'HANDOFF.md').write_bytes('\n'.join(brief).encode())

async def snapshot_checks(out):
 from mcp import Client
 from mcp.client.stdio import StdioServerParameters
 assert importlib.metadata.version('mcp')=='2.3.0'
 sdk=out/'sdk';sdk.mkdir();responses=[];checks=[];times=[];before=files(out/'worked')
 def check(label,value):checks.append({'label':label,'pass':bool(value)});write(sdk/'checks.json',checks);assert value,label
 targets=[('site-a-ei','proposals-forward'),('site-b-process','refreshed')]
 for slug,stage in targets:
  folder=selected(out,slug,stage);g=read(folder/'enriched_graph.json');c=read(folder/'context.json')
  params=StdioServerParameters(command=sys.executable,args=['-u',str(ROOT/'scripts/serve_snapshot.py'),'--graph',str(folder/'enriched_graph.json'),'--context',str(folder/'context.json')],env=ENV)
  start=time.perf_counter()
  async with Client(params,read_timeout_seconds=20) as client:
   async def call(tool,args=None):
    value=await client.call_tool(tool,args or {});raw=value.model_dump(mode='json',by_alias=True,exclude_none=True)
    responses.append({'packet':slug,'tool':tool,'arguments':args or {},'response':raw});write(sdk/'responses.json',responses)
    check(slug+'/'+tool+'/complete serialization',not value.is_error and json.loads(value.content[0].text)==value.structured_content)
    body=value.structured_content
    check(slug+'/'+tool+'/selected raw and canonical context hashes',body['snapshot_sha256']==sha(folder/'enriched_graph.json') and body['context_sha256']==sha(folder/'context.json') and body['context_content_sha256']==g['context_register']['content_sha256'])
    check(slug+'/'+tool+'/supplied nonlive scope',body['data_mode']=='supplied_snapshot' and body['live'] is False and body['source_acquisition_time'] is None)
    return body['result']
   summary=await call('snapshot_summary')
   expected={'schema':g['schema'],'title':g.get('title'),'source_model':g.get('source_model'),'nodes':len(g['nodes']),'edges':len(g['edges']),'questions':len(g['questions']),'virtual_streams':sum(e.get('type')=='connects' for e in g['edges']),'context_available':True,'context_questions':len(c['current']),'decisions':len(c['decisions']),'available_sections':['nodes','edges','questions','context','decision_history','ownership_history'],'unserved_review_events':len(g.get('events',[])),'not_exported':g.get('not_exported',[])}
   check(slug+'/complete summary',summary==expected)
   for node in g['nodes']:
    aid=node['id'];check(slug+'/'+aid+'/complete node',await call('get_asset',{'asset_id':aid})==node)
    edges=[e for e in g['edges'] if aid in (e['from'],e['to'])]
    check(slug+'/'+aid+'/complete relations',await call('get_relations',{'asset_id':aid,'limit':100})=={'total':len(edges),'offset':0,'limit':100,'next_offset':None,'truncated':False,'relations':edges})
   for q in g['questions']:
    qid=q['id'];check(slug+'/'+qid+'/complete selected question',await call('get_question',{'question_id':qid})==q)
    expected={'question_id':qid,'current':c['current'][qid],'ownership_history':[r for r in c['ownership_history'] if r['question_id']==qid],'sources':[dict(s,locators=[l for l in s['locators'] if qid in l['questions']]) for s in c['sources'] if any(qid in l['questions'] for l in s['locators'])]}
    check(slug+'/'+qid+'/complete current source owner bodies',await call('get_context',{'question_id':qid})==expected)
   decisions=[];offset=0
   while True:
    page=await call('list_decisions',{'limit':1,'offset':offset})
    check(slug+'/exact history page '+str(offset),page['decisions']==c['decisions'][offset:offset+1] and page['total']==len(c['decisions']))
    decisions+=page['decisions']
    if page['next_offset'] is None:break
    offset=page['next_offset']
   check(slug+'/entire exact ordered history',decisions==c['decisions'])
  times.append({'packet':slug,'stdio_session_wall_seconds':time.perf_counter()-start})
 negatives=[]
 for graph_scope,context_scope in ((targets[0],targets[1]),(targets[1],targets[0])):
  gp=selected(out,*graph_scope)/'enriched_graph.json';cp=selected(out,*context_scope)/'context.json';command=[sys.executable,str(ROOT/'scripts/serve_snapshot.py'),'--graph',str(gp),'--context',str(cp)]
  start=time.perf_counter();p=subprocess.run(command,input=b'',capture_output=True,env=ENV,timeout=20);wall=time.perf_counter()-start
  label=graph_scope[0]+'-graph-'+context_scope[0]+'-context'
  (sdk/(label+'.stderr')).write_bytes(p.stderr);(sdk/(label+'.stdout')).write_bytes(p.stdout)
  negatives.append({'command':command,'exit':p.returncode,'wall_seconds':wall})
  check(label+'/bound pair startup refusal',p.returncode==2 and b'Invalid selected context' in p.stderr)
 check('worked handoff bytes unchanged by readback',files(out/'worked')==before)
 write(sdk/'RESULT.json',{'pass':True,'mcp':importlib.metadata.version('mcp'),'actual_stdio_sessions':2,'actual_responses':len(responses),'assertions':len(checks),'session_times':times,'mixed_pair_CLIs':negatives,'scope':'Selected-pair integrity only, no company namespace/auth/global search/live update or recipient acceptance.'})

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);p.add_argument('--sdk-only',action='store_true');a=p.parse_args();out=a.out.resolve()
 if a.sdk_only:
  assert read(out/'CLI-RESULT.json')['pass'] and not (out/'sdk').exists();asyncio.run(snapshot_checks(out))
 else:
  assert not out.exists(),'Use a fresh output folder; preserve every earlier run.';Exercise(out).run()
 print('PASS fictional bounded team-context example; read exact records and limits.')
if __name__=='__main__':main()
