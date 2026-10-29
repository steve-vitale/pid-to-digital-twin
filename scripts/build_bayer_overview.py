"""Overview screen of the Bayer residue treater, generated from the model and driven by the replayed Figure 11 trend.

python scripts/build_bayer_overview.py      # writes drafts/bayer-overview/index.html (one self-contained page)

Why this screen: the CSB found the board operators asked for equipment overview screens, and "the screens were not
available for the August 2008 startup" (report p. 60). This page is an overview of one unit built the way this
project builds screens: the geometry comes from the generated P&ID's layout (data/bayer_rt/pid_layout.json), the
items and tags from the model (data/bayer_rt/process_model.json), and the values and states from the replay
(data/bayer_rt/replay.csv, data/bayer_rt/replay_rules.json). Nothing on it is typed in by hand.

It follows high-performance HMI practice: grey process, colour only for an abnormal state, and every value shown
with the bound it carries. An interlock is shown as its condition (met / clear / cannot tell, from bounds the report
supports), with its as-operated state from the report: bypassed. The replay stops at 22:33, the failure, and says
what happened there in one plain sentence with its page.

It is a proof of concept: not the plant's screen, not its DCS, tags assigned by this project. Stdlib only.
"""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODEL = ROOT / "data" / "bayer_rt" / "process_model.json"
LAYOUT = ROOT / "data" / "bayer_rt" / "pid_layout.json"
RULES = ROOT / "data" / "bayer_rt" / "replay_rules.json"
REPLAY = ROOT / "data" / "bayer_rt" / "replay.csv"
OUT = ROOT / "drafts" / "bayer-overview" / "index.html"
REPORT = "https://www.csb.gov/assets/1/20/Bayer_Report_Final.pdf"

TAGS = ["TI-104", "PI-101", "LI-102", "FI-103"]


def replay_rows():
    lines = [ln for ln in REPLAY.read_text(encoding="utf-8").splitlines() if not ln.startswith("#")]
    rows = []
    for r in csv.DictReader(lines):
        row = {"t": r["time"]}
        for k, v in r.items():
            if k == "time":
                continue
            row[k] = (float(v) if v not in ("",) and k.split("_")[0] in TAGS else (v or None))
        rows.append(row)
    return rows


def geometry(model, layout):
    """Units, lines, valves, mounted instruments and interlock positions, from the P&ID layout."""
    sheet = layout["sheets"][0]
    units = {}
    for uid, u in sheet["units"].items():
        name = next(x["name"] for x in model["units"] if x["id"] == uid)
        units[uid] = dict(u, name=name)
    finals = {f["tag"]: f for f in model["final_elements"]}
    manual = {m["tag"]: m for m in model["manual_valves"]}
    relief = {r["tag"]: r for r in model["relief_devices"]}
    lines, valves, taps = [], [], {}
    for r in sheet["routes"]:
        utility = bool(r.get("stream")) and next((s for s in model["streams"] if s["id"] == r["stream"]), {}).get("utility")
        lines.append({"id": r["id"], "pts": r["pts"], "utility": bool(utility)})
        for tag, at in r.get("place", {}).items():
            kind = "control" if tag in finals else "manual" if tag in manual else "relief" if tag in relief else "tap"
            if kind == "tap":
                taps[tag] = at
            else:
                valves.append({"tag": tag, "at": at, "kind": kind,
                               "vertical": any(a[0] == b[0] == at[0] and min(a[1], b[1]) <= at[1] <= max(a[1], b[1])
                                               for a, b in zip(r["pts"], r["pts"][1:]))})
    mounts = {tag: at for u in sheet["units"].values() for tag, at in u.get("mount", {}).items()}
    flags = [{"at": f["at"], "dir": f["dir"], "label": f.get("label", "")} for f in sheet["flags"].values()]
    return {"units": units, "lines": lines, "valves": valves, "points": {**mounts, **taps}, "flags": flags,
            "interlocks": sheet.get("interlocks", {}), "controllers": sheet.get("controllers", {})}


def build():
    model = json.loads(MODEL.read_text(encoding="utf-8"))
    layout = json.loads(LAYOUT.read_text(encoding="utf-8"))
    rules = json.loads(RULES.read_text(encoding="utf-8"))
    inst = {i["tag"]: {"desc": i["description"], "uom": i["uom"]} for i in model["instruments"]}
    data = {
        "geometry": geometry(model, layout),
        "instruments": {t: inst[t] for t in TAGS},
        "interlocks": [{k: il[k] for k in ("id", "condition", "tag", "why_these_bounds", "as_operated")}
                       for il in rules["interlocks"]],
        "limits": rules["limits"],
        "events": [{"t": e["time"], "what": e["what"], "source": e["source"]} for e in model["events_2008_08_28"]],
        "feed": {"tag": "FV-107", "state": "open, in manual",
                 "why": "opened by hand at about 4 a.m. and feeding since (p. 38); its interlocks bypassed (pp. 38, 69)"},
        "rows": replay_rows(),
        "report": REPORT,
    }
    html = TEMPLATE.replace("__DATA__", json.dumps(data, separators=(",", ":")))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html, encoding="utf-8", newline="\n")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(data['rows'])} replay rows, {len(html)} bytes")


TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Residue Treater Overview</title>
<meta name="description" content="An overview screen of the Bayer CropScience residue treater generated from a model of the CSB report, replaying the published Figure 11 trend. Proof of concept.">
<style>
:root{--bg:#f4f5f7;--panel:#ffffff;--ink:#1d2229;--muted:#59626e;--line:#8b939e;--util:#b3b9c1;--equip:#3d454f;
--warn:#a35a00;--warn-bg:#fff1dc;--alarm:#b3261e;--alarm-bg:#fde7e5;--unsure:#5b5f9c;--ok:#2f6b3a;--accent:#1f5fa8;--grid:#e3e6ea}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#15181c;--panel:#1d2127;--ink:#e6e9ed;--muted:#a4adb8;
--line:#7d8590;--util:#565d66;--equip:#c3c9d0;--warn:#f0a648;--warn-bg:#3a2a12;--alarm:#ff8a80;--alarm-bg:#3d1c1a;--unsure:#a9adf0;--ok:#7cc48a;--accent:#7fb3f0;--grid:#2c3239}}
:root[data-theme="dark"]{--bg:#15181c;--panel:#1d2127;--ink:#e6e9ed;--muted:#a4adb8;--line:#7d8590;--util:#565d66;--equip:#c3c9d0;
--warn:#f0a648;--warn-bg:#3a2a12;--alarm:#ff8a80;--alarm-bg:#3d1c1a;--unsure:#a9adf0;--ok:#7cc48a;--accent:#7fb3f0;--grid:#2c3239}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
a{color:var(--accent)}
header,main,footer{max-width:1240px;margin:0 auto;padding:0 16px}
header{padding-top:18px}
h1{font-size:22px;margin:0 0 4px}
.note{color:var(--muted);font-size:13px;margin:0}
.bar{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin:14px 0 10px;background:var(--panel);border:1px solid var(--grid);border-radius:8px;padding:10px 12px}
.bar button{font:inherit;padding:6px 14px;border-radius:6px;border:1px solid var(--line);background:var(--panel);color:var(--ink);cursor:pointer}
.bar input[type=range]{flex:1 1 260px;min-width:0}
.clock{font:600 22px/1 ui-monospace,Consolas,monospace;min-width:6ch}
.grid{display:grid;grid-template-columns:minmax(0,1fr) 340px;gap:14px}
@media (max-width:900px){.grid{grid-template-columns:minmax(0,1fr)}.grid>section:last-child{order:-1}}
.card{background:var(--panel);border:1px solid var(--grid);border-radius:8px;padding:12px;min-width:0}
.card h2{font-size:14px;margin:0 0 8px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em}
svg{display:block;width:100%;height:auto}
.mimic text{font-family:system-ui,sans-serif}
.il{border:1px solid var(--grid);border-radius:6px;padding:8px;margin-bottom:8px}
.il .head{display:flex;justify-content:space-between;gap:8px;align-items:baseline}
.badge{font-size:12px;font-weight:700;padding:2px 7px;border-radius:10px;white-space:nowrap}
.met{background:var(--warn-bg);color:var(--warn)}
.clear{background:transparent;color:var(--ok);border:1px solid var(--ok)}
.unsure{background:transparent;color:var(--unsure);border:1px dashed var(--unsure)}
.none{color:var(--muted);border:1px dashed var(--muted)}
.info{background:transparent;color:var(--muted);border:1px solid var(--line)}
.svc{background:transparent;color:var(--muted);border:1px solid var(--line)}
.vals{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:2px 10px;align-items:baseline;margin-bottom:12px}
.vals .v{font:700 20px/1.2 ui-monospace,Consolas,monospace;text-align:right}
.vals .b{grid-column:1/-1;font-size:12px;color:var(--muted);border-bottom:1px solid var(--grid);padding-bottom:4px}
.vals .v.abn{color:var(--warn)}
.byp{background:var(--alarm-bg);color:var(--alarm)}
.small{font-size:13px;color:var(--muted)}
.lim{display:flex;justify-content:space-between;gap:8px;font-size:13px;padding:3px 0;border-bottom:1px solid var(--grid)}
.trends{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
@media (max-width:600px){.trends{grid-template-columns:minmax(0,1fr)}}
.events{list-style:none;padding:0;margin:0;font-size:13px}
.events li{padding:4px 0;border-bottom:1px solid var(--grid)}
.events li.past{color:var(--muted)}
.events li.now{font-weight:700}
.end{display:none;margin:12px 0;padding:12px;border:1px solid var(--line);border-radius:8px;background:var(--panel)}
.end.show{display:block}
footer{padding:18px 16px 30px;font-size:13px;color:var(--muted)}
</style>
</head>
<body>
<header>
<h1>Residue treater overview, August 28, 2008</h1>
<p class="note">Generated from a model of the <a href="" id="rep">CSB investigation report</a>: geometry from this project's generated P&amp;ID, values replayed from the report's Figure 11, each with the bound it carries. Tags are assigned by this project. Not the plant's screen. Proof of concept.</p>
</header>
<main>
<div class="bar" role="group" aria-label="Replay controls">
<button id="play" type="button" aria-label="Play the replay">Play</button>
<span class="clock" id="clock" aria-live="polite">--:--</span>
<input id="scrub" type="range" min="0" value="0" aria-label="Replay time">
</div>
<div class="end" id="end" role="status"></div>
<div class="grid">
<section class="card" aria-label="Unit overview">
<h2>Unit</h2>
<svg class="mimic" id="mimic" role="img" aria-label="Residue treater mimic"></svg>
</section>
<section class="card" aria-label="Interlocks and limits">
<h2>Values now</h2>
<div class="vals" id="vals"></div>
<h2>Feed valve interlocks</h2>
<div id="feed" class="small"></div>
<div id="ils"></div>
<h2 style="margin-top:12px">Operating limits</h2>
<div id="lims"></div>
</section>
</div>
<section class="card" style="margin-top:14px" aria-label="Trends">
<h2>The evening so far</h2>
<div class="trends" id="trends"></div>
</section>
<section class="card" style="margin-top:14px" aria-label="Report timeline">
<h2>The report's timeline</h2>
<ul class="events" id="events"></ul>
</section>
</main>
<footer>
Values: the median of each pixel column of Figure 11 (report p. 39); bounds: the column's range widened by the digitizing error. Interlock conditions: <em>met</em> (the feed valve would be held closed, were the interlock not bypassed), <em>clear</em>, or <em>cannot tell</em> where the bound straddles the range the report allows for an unpublished setpoint. Source data and method: data/bayer_rt/ and docs/BAYER_RT.md in this repository.
</footer>
<script>
const D=__DATA__;
document.getElementById("rep").href=D.report;
const rows=D.rows, G=D.geometry, NS="http://www.w3.org/2000/svg";
const el=(tag,attrs,parent,text)=>{const e=document.createElementNS(NS,tag);for(const k in attrs)e.setAttribute(k,attrs[k]);if(text!=null)e.textContent=text;if(parent)parent.appendChild(e);return e;};
const css=v=>getComputedStyle(document.documentElement).getPropertyValue(v).trim();
const fmt=(v,d=1)=>v==null?"—":v.toFixed(d);
const svg=document.getElementById("mimic");
svg.setAttribute("viewBox","90 130 2780 1640");
function drawMimic(){
  for(const l of G.lines){el("polyline",{points:l.pts.map(p=>p.join(",")).join(" "),fill:"none",stroke:l.utility?"var(--util)":"var(--line)","stroke-width":l.utility?6:9,"stroke-linejoin":"round"},svg);}
  for(const [uid,u] of Object.entries(G.units)){
    if(u.shape==="vertical_vessel"){const x=u.cx-u.w/2;el("rect",{x,y:u.top,width:u.w,height:u.bottom-u.top,rx:Math.min(u.head*1.6,u.w/2),fill:"var(--panel)",stroke:"var(--equip)","stroke-width":6},svg);
      el("text",{x:u.cx,y:(u.top+u.bottom)/2,"text-anchor":"middle","font-size":u.w>200?64:40,fill:"var(--ink)","font-weight":600},svg,uid);
      if(u.w>200)el("text",{x:u.cx,y:(u.top+u.bottom)/2+60,"text-anchor":"middle","font-size":40,fill:"var(--muted)"},svg,u.name);}
    else if(u.shape==="horizontal_exchanger"){el("rect",{x:u.x0,y:u.cy-u.h/2,width:u.x1-u.x0,height:u.h,rx:u.h/2,fill:"var(--panel)",stroke:"var(--equip)","stroke-width":6},svg);
      el("text",{x:(u.x0+u.x1)/2,y:u.cy+14,"text-anchor":"middle","font-size":40,fill:"var(--ink)","font-weight":600},svg,uid+(uid==="E-2"?" heater":" cooler"));}
    else if(u.shape==="pump"){el("circle",{cx:u.at[0],cy:u.at[1],r:u.r,fill:"var(--panel)",stroke:"var(--equip)","stroke-width":6},svg);
      el("text",{x:u.at[0],y:u.at[1]+u.r+50,"text-anchor":"middle","font-size":40,fill:"var(--ink)","font-weight":600},svg,uid);}
  }
  for(const f of G.flags){const [x,y]=f.at;const right=f.dir==="right";
    el("text",{x:right?x+12:x+228,y:y+12,"text-anchor":right?"start":"end","font-size":36,fill:"var(--muted)"},svg,f.label.toLowerCase());}
  for(const v of G.valves){const [x,y]=v.at,s=16;const g=el("g",{},svg);
    const pts=v.vertical?`${x-s},${y-s} ${x+s},${y-s} ${x-s},${y+s} ${x+s},${y+s}`:`${x-s},${y-s} ${x-s},${y+s} ${x+s},${y-s} ${x+s},${y+s}`;
    el("polygon",{points:pts,fill:"var(--panel)",stroke:"var(--equip)","stroke-width":4,id:"v-"+v.tag},g);
    if(v.kind!=="manual"||["HV-108","HV-110"].includes(v.tag))el("text",{x:v.vertical?x+26:x,y:v.vertical?y+12:y-28,"text-anchor":v.vertical?"start":"middle","font-size":36,fill:"var(--muted)"},g,v.tag);}
  for(const t of Object.keys(D.instruments)){const [x,y]=G.points[t];const g=el("g",{id:"box-"+t},svg);
    const w=300,h=112,off={"LI-102":[-w-30,-h/2],"FI-103":[-w/2,-h-40],"PI-101":[-w-60,-h-40],"TI-104":[40,-h/2]}[t],bx=x+off[0],by=y+off[1];
    el("rect",{x:bx,y:by,width:w,height:h,rx:8,fill:"var(--panel)",stroke:"var(--line)","stroke-width":3,class:"frame"},g);
    el("text",{x:bx+16,y:by+40,"font-size":34,fill:"var(--muted)"},g,t);
    el("text",{x:bx+16,y:by+94,"font-size":48,"font-weight":700,fill:"var(--ink)",class:"val"},g,"—");}
  for(const [id,[x,y]] of Object.entries(G.interlocks)){const g=el("g",{id:"dia-"+id},svg);
    el("polygon",{points:`${x},${y-56} ${x+56},${y} ${x},${y+56} ${x-56},${y}`,fill:"var(--panel)",stroke:"var(--equip)","stroke-width":4,class:"frame"},g);
    el("text",{x,y:y+12,"text-anchor":"middle","font-size":32,"font-weight":700,fill:"var(--ink)"},g,id);}
}
drawMimic();
const ilBox=document.getElementById("ils"),limBox=document.getElementById("lims");
document.getElementById("feed").innerHTML=`<p><strong>${D.feed.tag}</strong> feed valve: <strong>${D.feed.state}</strong>, ${D.feed.why}.</p>`;
for(const il of D.interlocks){const d=document.createElement("div");d.className="il";d.id="il-"+il.id;
  d.innerHTML=`<div class="head"><strong>${il.id}</strong><span class="badge state"></span></div><div>${il.condition}</div><div class="small">${/bypassed/.test(il.as_operated)&&!/not reported/.test(il.as_operated)?'<span class="badge byp">BYPASSED</span>':'<span class="badge svc">not reported bypassed</span>'} ${il.as_operated}</div><details class="small"><summary>Why these bounds</summary>${il.why_these_bounds}</details>`;ilBox.appendChild(d);}
for(const lim of D.limits){const d=document.createElement("div");d.className="lim";d.id="lim-"+lim.id;
  d.innerHTML=`<span>${lim.what} (${lim.tag} ${lim.at_or_above!=null?"≥ "+lim.at_or_above:"< "+lim.below})</span><span class="badge state"></span>`;limBox.appendChild(d);}
const valBox=document.getElementById("vals");
for(const t of Object.keys(D.instruments)){valBox.insertAdjacentHTML("beforeend",`<div><strong>${t}</strong> ${D.instruments[t].desc.replace(/ \(.*\)$/,"")}</div><div class="v" id="vn-${t}">—</div><div class="b" id="vb-${t}"></div>`);}
const evBox=document.getElementById("events");
for(const e of D.events){const li=document.createElement("li");li.dataset.t=e.t;li.innerHTML=`<strong>${e.t}</strong> ${e.what} <span class="small">(${e.source})</span>`;evBox.appendChild(li);}
const trendBox=document.getElementById("trends"),cursors=[];
const toMin=t=>{const [h,m,s]=t.split(":").map(Number);return h*60+m+s/60;};
const t0=toMin(rows[0].t),t1=toMin(rows[rows.length-1].t);
for(const tag of Object.keys(D.instruments)){const info=D.instruments[tag];const vals=rows.flatMap(r=>[r[tag+"_lo"],r[tag+"_hi"]]).filter(v=>v!=null);
  let lo=Math.min(0,...vals),hi=Math.max(...vals);for(const l of D.limits.filter(l=>l.tag===tag))hi=Math.max(hi,(l.at_or_above??l.below)*1.05);
  const W=520,H=170,X=t=>40+(toMin(t)-t0)/(t1-t0)*(W-50),Y=v=>H-22-(v-lo)/(hi-lo)*(H-36);
  const wrap=document.createElement("div");wrap.innerHTML=`<div class="small"><strong>${tag}</strong> ${info.desc} (${info.uom})</div>`;
  const s=el("svg",{viewBox:`0 0 ${W} ${H}`,role:"img","aria-label":`${tag} trend`},wrap);
  D.limits.filter(l=>l.tag===tag).forEach((l,k)=>{const v=l.at_or_above??l.below,col=l.informational?"var(--muted)":"var(--warn)";el("line",{x1:40,x2:W-10,y1:Y(v),y2:Y(v),stroke:col,"stroke-dasharray":"6 4","stroke-width":1.5},s);
    el("text",{x:k%2?W-12:46,y:Y(v)+(k%2?18:-6),"text-anchor":k%2?"end":"start","font-size":16,fill:col},s,l.short);});
  const ok=rows.filter(r=>r[tag+"_lo"]!=null);
  el("polygon",{points:ok.map(r=>`${X(r.t)},${Y(r[tag+"_hi"])}`).concat(ok.slice().reverse().map(r=>`${X(r.t)},${Y(r[tag+"_lo"])}`)).join(" "),fill:"var(--line)",opacity:.35},s);
  el("polyline",{points:ok.map(r=>`${X(r.t)},${Y(r[tag])}`).join(" "),fill:"none",stroke:"var(--ink)","stroke-width":1.5},s);
  el("text",{x:36,y:Y(lo)+4,"text-anchor":"end","font-size":16,fill:"var(--muted)"},s,String(Math.round(lo)));
  el("text",{x:36,y:Y(hi)+4,"text-anchor":"end","font-size":16,fill:"var(--muted)"},s,String(Math.round(hi)));
  el("text",{x:40,y:H-4,"font-size":16,fill:"var(--muted)"},s,rows[0].t.slice(0,5));
  el("text",{x:W-10,y:H-4,"text-anchor":"end","font-size":16,fill:"var(--muted)"},s,"22:33");
  const shade=el("rect",{x:0,y:0,width:0,height:H-18,fill:"var(--bg)",opacity:.7},s);
  const cur=el("line",{y1:6,y2:H-18,stroke:"var(--accent)","stroke-width":2},s);
  cursors.push({X,W,H,shade,cur});trendBox.appendChild(wrap);}
const label={met:"MET: would hold feed closed",clear:"CLEAR","cannot tell":"CANNOT TELL","no reading":"NO READING"};
const cls={met:"met",clear:"clear","cannot tell":"unsure","no reading":"none",crossed:"met","not crossed":"clear"};
const scrub=document.getElementById("scrub");scrub.max=rows.length-1;
let idx=0,timer=null;
function setTime(i){idx=Math.max(0,Math.min(rows.length-1,i));const r=rows[idx];scrub.value=idx;
  document.getElementById("clock").textContent=r.t.slice(0,5);
  for(const tag of Object.keys(D.instruments)){const g=document.getElementById("box-"+tag),v=r[tag],lo=r[tag+"_lo"],hi=r[tag+"_hi"];
    const d=tag==="PI-101"?1:1;g.querySelector(".val").textContent=v==null?"no reading":`${fmt(v,d)} ${D.instruments[tag].uom==="C"?"°C":D.instruments[tag].uom}`;
    g.setAttribute("data-value",v==null?"":String(v));g.setAttribute("data-lo",lo==null?"":String(lo));g.setAttribute("data-hi",hi==null?"":String(hi));
    g.querySelector("title")?.remove();el("title",{},g,v==null?`${tag}: no reading`:`${tag}: ${fmt(v)} (bounds ${fmt(lo)} to ${fmt(hi)})`);
    const crossed=D.limits.filter(l=>l.tag===tag&&!l.informational).some(l=>r[l.id]==="crossed"),unsure=D.limits.filter(l=>l.tag===tag).some(l=>r[l.id]==="cannot tell");
    const f=g.querySelector(".frame");f.setAttribute("stroke",crossed?"var(--warn)":"var(--line)");f.setAttribute("stroke-dasharray",unsure?"10 6":"none");f.setAttribute("stroke-width",crossed?6:3);}
  for(const il of D.interlocks){const s=r[il.id],b=document.querySelector(`#il-${il.id} .state`);b.textContent=label[s];b.className="badge state "+cls[s];b.dataset.state=s;
    const f=document.querySelector(`#dia-${il.id} .frame`);f.setAttribute("fill",s==="met"?"var(--warn-bg)":"var(--panel)");f.setAttribute("stroke",s==="met"?"var(--warn)":"var(--equip)");f.setAttribute("stroke-dasharray",s==="cannot tell"?"10 6":"none");}
  for(const lim of D.limits){const s=r[lim.id],b=document.querySelector(`#lim-${lim.id} .state`);b.textContent=lim.informational?(s==="crossed"?"ABOVE":s==="not crossed"?"BELOW":s.toUpperCase()):s.toUpperCase();b.className="badge state "+(lim.informational?"info":cls[s]);b.dataset.state=s;}
  for(const tag of Object.keys(D.instruments)){const v=r[tag],u=D.instruments[tag].uom==="C"?"°C":D.instruments[tag].uom;
    const abn=D.limits.some(l=>l.tag===tag&&!l.informational&&r[l.id]==="crossed");
    const n=document.getElementById("vn-"+tag);n.textContent=v==null?"no reading":`${fmt(v)} ${u}`;n.className="v"+(abn?" abn":"");
    document.getElementById("vb-"+tag).textContent=v==null?"":`bounds ${fmt(r[tag+"_lo"])} to ${fmt(r[tag+"_hi"])} ${u}`+(abn?" · limit crossed":"");}
  const now=toMin(r.t);for(const li of evBox.children){const t=toMin(li.dataset.t+":00");li.className=t<=now?(now-t<1.5?"now":"past"):"";}
  for(const c of cursors){const x=c.X(r.t);c.cur.setAttribute("x1",x);c.cur.setAttribute("x2",x);c.shade.setAttribute("x",x);c.shade.setAttribute("width",Math.max(0,c.W-x));}
  const end=document.getElementById("end");const last=idx===rows.length-1;end.classList.toggle("show",last);
  end.innerHTML=last?`<strong>22:33.</strong> The residue treater ruptured during the restart. Two employees died (<a href="${D.report}">CSB report</a>, p. 1). The replay stops here.`:"";}
scrub.addEventListener("input",()=>setTime(Number(scrub.value)));
const playBtn=document.getElementById("play");
playBtn.addEventListener("click",()=>{if(timer){clearInterval(timer);timer=null;playBtn.textContent="Play";return;}
  if(idx>=rows.length-1)setTime(0);playBtn.textContent="Pause";timer=setInterval(()=>{if(idx>=rows.length-1){clearInterval(timer);timer=null;playBtn.textContent="Play";return;}setTime(idx+1);},matchMedia("(prefers-reduced-motion: reduce)").matches?400:120);});
setTime(0);
window.__tour={rows:rows.length,setTime,state:()=>({t:rows[idx].t,
  values:Object.fromEntries(Object.keys(D.instruments).map(t=>[t,document.getElementById("box-"+t).getAttribute("data-value")])),
  interlocks:Object.fromEntries(D.interlocks.map(il=>[il.id,document.querySelector(`#il-${il.id} .state`).dataset.state])),
  limits:Object.fromEntries(D.limits.map(l=>[l.id,document.querySelector(`#lim-${l.id} .state`).dataset.state])),
  endShown:document.getElementById("end").classList.contains("show")})};
</script>
</body>
</html>
"""


if __name__ == "__main__":
    build()
