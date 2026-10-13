"""Read-only TE process mimic. No plant writes, new process model, or new alarm limits.

SVG geometry is illustrative. Only level (%) changes vessel fill; XMV output changes
its own output gauge, never inferred flow or physical valve-position feedback.
Script transforms are Python 2.7/Jython-compatible for Perspective.
"""
import base64
import json
from pathlib import Path
from build_hmi import TRANSFORM_SIGNATURE, label, tag_binding, script_transform, view, header, INK, MUTED, UNIT_ORDER

ROOT = Path(__file__).resolve().parents[2]
TAGS = {
    'U-100': ['FI-101', 'FI-102', 'FI-103'],
    'R-101': ['PI-107', 'TI-109', 'LI-108', 'FI-106'],
    'E-101': ['TI-122', 'TV-211'],
    'V-101': ['PI-113', 'TI-111', 'LI-112', 'FI-114'],
    'K-101': ['FI-105', 'FI-110', 'JI-120', 'HV-205'],
    'C-101': ['PI-116', 'TI-118', 'LI-115', 'FI-117'],
}

STREAMS = ['S1', 'S2', 'S3', 'S4', 'S5', 'S6', 'S7', 'S7b', 'S8', 'S8b', 'S9', 'S10', 'S11']
VIEW_HEIGHT = 930
KINDS = {'U-100': 'feed', 'R-101': 'reactor', 'E-101': 'condenser', 'V-101': 'separator', 'K-101': 'compressor', 'C-101': 'stripper'}
LEVELS = {'R-101': 'LI-108', 'V-101': 'LI-112', 'C-101': 'LI-115'}


def uri(svg):
    return 'data:image/svg+xml;base64,' + base64.b64encode(svg.encode('utf-8')).decode('ascii')


def shell(kind, fill='__FILL__', y='__Y__', height='__HEIGHT__', note='__NOTE__'):
    """Stable SVG template shared verbatim by Perspective and the offline preview."""
    if kind == 'feed':
        return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 240 250"><g fill="none" stroke="#4b5563" stroke-width="5"><path d="M20 65 H100 M20 125 H100 M20 185 H100 M100 55 V195 M100 125 H225"/></g><text x="120" y="230" text-anchor="middle" font-family="Arial" font-size="14">Feed header</text></svg>'
    if kind == 'compressor':
        return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 240 250"><circle cx="120" cy="125" r="76" fill="#eef0f1" stroke="#4b5563" stroke-width="3"/><path d="M65 78 L182 125 L65 172 Z" fill="#c4cbd0" stroke="#4b5563" stroke-width="3"/><text x="120" y="230" text-anchor="middle" font-family="Arial" font-size="14">Static compressor</text></svg>'
    if kind == 'condenser':
        return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 240 250"><g fill="#eef0f1" stroke="#4b5563" stroke-width="3"><rect x="20" y="75" width="200" height="100" rx="50"/><path fill="none" d="M40 125 L65 95 L95 155 L125 95 L155 155 L185 95 L205 125"/></g><text x="120" y="211" text-anchor="middle" font-family="Arial" font-size="13" fill="#59636e">Heat exchanger symbol</text></svg>'
    if kind == 'output':
        return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 240 40">'
                '<path d="M10 5 L45 20 L10 35 Z M80 5 L45 20 L80 35 Z" fill="#dde1e4" stroke="#4b5563" stroke-width="2"/>'
                '<rect x="100" y="10" width="130" height="20" fill="#f4f5f6" stroke="#66717c"/>'
                '<rect x="100" y="10" width="__WIDTH__" height="20" fill="__FILL__"/>'
                '<title>Recorded output: __NOTE__</title></svg>')
    if kind not in ('reactor','separator','stripper'):
        return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 240 250"><rect x="30" y="45" width="180" height="155" rx="5" fill="#eef0f1" stroke="#4b5563" stroke-width="3"/><text x="120" y="225" text-anchor="middle" font-family="Arial" font-size="12">Unspecified equipment symbol</text></svg>'
    internals = '<path d="M120 10 V100 M88 100 H152" stroke="#66717c" stroke-width="4"/>' if kind == 'reactor' else ''
    if kind == 'stripper':
        internals = '<path d="M60 65 H180 M60 100 H180 M60 135 H180 M60 170 H180" stroke="#66717c" stroke-width="2"/>'
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 240 250">'
            '<defs><clipPath id="vessel"><rect x="38" y="22" width="164" height="200" rx="46"/></clipPath>'
            '<pattern id="unknown" width="12" height="12" patternUnits="userSpaceOnUse"><path d="M0 12 L12 0" stroke="#8a9198" stroke-width="2"/></pattern></defs>'
            '<rect x="38" y="22" width="164" height="200" rx="46" fill="#f4f5f6"/>'
            '<rect x="38" y="' + y + '" width="164" height="' + height + '" fill="' + fill + '" clip-path="url(#vessel)"/>'
            '<rect x="38" y="22" width="164" height="200" rx="46" fill="none" stroke="#4b5563" stroke-width="3"/>'
            + internals + '<path d="M68 218 V242 M172 218 V242" stroke="#4b5563" stroke-width="4"/>'
            '<text x="120" y="166" text-anchor="middle" font-family="Arial" font-size="14" fill="#17212b">' + note + '</text></svg>')


def graphic_script(kind):
    # Quality and non-finite checks are inside the transform so stale values cannot look normal.
    return '''import base64
import math
svg = %r
valid = quality.isGood() and value is not None
try:
    number = float(value)
    valid = valid and not math.isnan(number) and not math.isinf(number)
except (TypeError, ValueError):
    valid = False
if valid:
    percent = max(0.0, min(100.0, number))
    note = "%%.1f%%%%" %% number
    if number < 0 or number > 100:
        note += " (off scale)"
    fill = "#b7c0c8"
    height = 2 * percent
    y = 222 - height
    width = 1.3 * percent
else:
    note = "UNKNOWN"
    fill = "url(#unknown)"
    height, y, width = 200, 22, 0
svg = svg.replace("__NOTE__", note).replace("__FILL__", fill)
svg = svg.replace("__HEIGHT__", str(height)).replace("__Y__", str(y)).replace("__WIDTH__", str(width))
return "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode("ascii")
''' % shell(kind)


VALUE_SCRIPT = '''import math
if not quality.isGood() or value is None:
    return "UNKNOWN / bad quality"
try:
    number = float(value)
except (TypeError, ValueError):
    return "UNKNOWN / invalid value"
if math.isnan(number) or math.isinf(number):
    return "UNKNOWN / invalid value"
return "%.1f" % number
'''
STATE_SCRIPT = '''if not quality.isGood() or value is None:
    return "State unknown"
return {0: "Within normal band", 1: "Outside normal band", 2: "ALARM ACTIVE"}.get(value, "State unknown")
'''


def script(code):
    return script_transform(code)  # stored-body form; see build_hmi.TRANSFORM_SIGNATURE


def image(name, x, y, w, h, kind, base=None):
    c = {'type': 'ia.display.image', 'meta': {'name': name},
         'position': {'x': x, 'y': y, 'width': w, 'height': h},
         'props': {'source': uri(shell(kind).replace('__FILL__', 'url(#unknown)').replace('__Y__', '22')
                                .replace('__HEIGHT__', '200').replace('__WIDTH__', '0').replace('__NOTE__', 'UNKNOWN')),
                   'fit': {'mode': 'contain'}}}
    if base:
        c['propConfig'] = {'props.source': tag_binding(base + '/PV', [script(graphic_script(kind))])}
    return c


def mimic(provider, model, hidden=frozenset()):
    items = {i['tag']: i for i in model['instruments'] + model['final_elements']}
    streams = {s['id']: s for s in model['streams']}
    kids = header(provider, 'Whole-process overview', '/')
    kids += [label('Mode', 24, 72, 1500, 24, 'RECORDED TE REPLAY  /  READ ONLY  /  NO RESPONSIVE PROCESS PHYSICS', {'fontWeight': 'bold', 'fontSize': 15}),
             label('Caveat', 24, 102, 1510, 36, 'Asset shapes are illustrative. Units and stream topology are UNVERIFIED pending operations review. Arrows reproduce the seed model only; no measured-flow animation.', {'fontSize': 13}),
             label('FullSchematic', 1280, 70, 290, 26, 'Open full model schematic >', {'textAlign': 'right'}, page='/schematic')]
    positions = {'U-100': (70, 350), 'R-101': (360, 350), 'E-101': (650, 350),
                 'V-101': (940, 350), 'K-101': (940, 170), 'C-101': (1300, 350)}
    for uid in UNIT_ORDER:
        x, top = positions[uid]
        unit = next(u for u in model['units'] if u['id'] == uid)
        kids.append(label('Title_' + uid, x - 45, top - 28, 280, 28, uid + ' | ' + unit['name'], {'fontSize': 15, 'fontWeight': 'bold'}, page='/unit/' + uid))
        level = LEVELS.get(uid)
        base = '[%s]TE_Plant/%s/%s' % (provider, uid, level) if level and level not in hidden else None
        eq = image('Equipment_' + uid, x, top, 180, 125 if uid == 'K-101' else 150, KINDS[uid], base)
        eq['events'] = {'dom': {'onClick': {'type': 'nav', 'scope': 'C', 'config': {'page': '/unit/' + uid}}}}
        eq['props']['style'] = {'cursor': 'pointer'}
        kids.append(eq)
        note = ('Fill = ' + level + ' measured %') if level else ('TI-122 ownership unresolved' if uid == 'E-101' else '')
        kids.append(label('GraphicNote_' + uid, 1120 if uid == 'K-101' else x - 45, 170 if uid == 'K-101' else top + 151, 280, 20, note, {'fontSize': 12, 'textAlign': 'center', 'color': MUTED}))
    # Draw only directions explicitly supplied in the unverified seed model.
    paths = {'S1': 'M15 389 H100', 'S2': 'M15 425 H100', 'S3': 'M15 461 H100',
             'S4': 'M1555 285 H1515 V390 H1430', 'S5': 'M1340 380 H1225 V700 H15 V510 H148 V467',
             'S6': 'M217 425 H398', 'S7': 'M502 425 H680', 'S7b': 'M800 425 H978',
             'S8': 'M1030 366 V278', 'S8b': 'M990 234 H260 V425 H223', 'S9': 'M1070 234 H1190',
             'S10': 'M1082 425 H1338', 'S11': 'M1442 425 H1570'}
    svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 720"><defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0 0 L8 4 L0 8" fill="#717b85"/></marker></defs>'
    for stream in model['streams']:
        svg += '<path d="%s" fill="none" stroke="#717b85" stroke-width="2" marker-end="url(#arrow)"/>' % paths[stream['id']]
    svg += '</svg>'
    kids.insert(0, {'type': 'ia.display.image', 'meta': {'name': 'ModeledStreams'}, 'position': {'x': 0, 'y': 0, 'width': 1600, 'height': 720}, 'props': {'source': uri(svg), 'fit': {'mode': 'fill'}, 'style': {'pointerEvents': 'none'}}})
    loc = {'S1': (16, 365), 'S2': (16, 401), 'S3': (16, 437), 'S4': (1420, 258), 'S5': (640, 675),
           'S6': (261, 400), 'S7': (547, 400), 'S7b': (845, 400), 'S8': (1070, 300),
           'S8b': (550, 209), 'S9': (1140, 208), 'S10': (1130, 400), 'S11': (1480, 400)}
    for sid, (x, y) in loc.items():
        st = streams[sid]
        kids.append(label('Stream_' + sid, x, y, 110, 22, sid + (' / BL' if 'BL' in (st['from'], st['to']) else ''), {'fontSize': 12}, tooltip='%s: %s → %s (%s); unverified seed direction' % (sid, st['from'], st['to'], st['name'])))
    kids.append(label('OverviewGuide', 24, 725, 1552, 32, 'Select equipment for all mapped readings, 30-minute history, normal bands and review status. BL = model boundary. Static arrows are seed-model directions, not measured flow.', {'fontSize': 13}))
    # Level-one essentials sit beside their equipment, not in a second inventory.
    for uid in UNIT_ORDER:
        x, _ = positions[uid]
        left, top = (1210, 150) if uid == 'K-101' else (x - 45, 535)
        for row, tag in enumerate(t for t in placed_tags(model, uid) if t not in hidden):
            it = items[tag]
            base = '[%s]TE_Plant/%s/%s' % (provider, it['unit'], tag)
            y = top + row*30
            kids.append(label('Tag_' + tag, left, y, 74, 26, tag, {'fontSize': 14, 'fontWeight': 'bold', 'whiteSpace': 'nowrap'}, tooltip=it['description']))
            c = label('Value_' + tag, left+76, y, 203, 26, 'UNKNOWN', {'fontSize': 14, 'fontWeight': 'bold', 'whiteSpace': 'nowrap'}, tooltip=it['description'] + '; existing State coloring; recorded output only for XMV')
            code = VALUE_SCRIPT.replace('return "%.1f" % number', 'return ("%.1f" % number) + ' + repr(' ' + it['uom']))
            # Compact unknown text remains legible; detail preserves the full quality explanation.
            code = code.replace('UNKNOWN / bad quality', 'UNKNOWN').replace('UNKNOWN / invalid value', 'UNKNOWN')
            if it['uom'] == '%':
                code = code.rstrip() + ' + (" (off scale)" if number < 0 or number > 100 else "")\n'
            c['propConfig'] = {'props.text': tag_binding(base + '/PV', [script(code)]),
                              'props.style.color': tag_binding(base + '/State', [script('if not quality.isGood() or value is None:\n    return "#6b7280"\nreturn {1: "#8a5d00", 2: "#b91c1c"}.get(value, "#1f2937")')])}
            kids.append(c)
    kids += [label('TI122Review', 24, 765, 1552, 36, 'TI-122 ownership unresolved: source says separator cooling-water outlet; model retains E-101 pending operations review.', {'fontSize': 12, 'color': '#624d25', 'backgroundColor': '#f1e9d9', 'padding': 8}),
             label('ValveMeaning', 24, 811, 1552, 28, 'XMV readings are recorded output (%), not measured valve position. No controls or inferred flow animation. Full instrumentation and utility notes are on each unit page.', {'fontSize': 12, 'color': MUTED}),
             label('Legend', 24, 850, 1552, 30, 'Grey = normal; amber = outside existing normal band (not alarm); red = existing alarm. UNKNOWN / hatching = unavailable data. Level shape is not vessel volume.', {'fontSize': 12}),
             label('Scope', 24, 890, 1552, 24, 'Local prototype. Selection and layout need operator review. Hover a tag for its measurement name; select equipment to investigate boundaries, all readings and history.', {'fontSize': 12, 'color': MUTED})]
    return view(VIEW_HEIGHT, kids)


def detail_table_top(model, uid):
    if uid in SPATIAL: return SPATIAL[uid]["table_top"]
    count = sum(uid in (s['from'], s['to']) for s in model['streams'])
    return max(555, 154 + ((count + 1)//2)*76 + 185)


# Plant-specific labels and reviewed presentation coordinates live outside this renderer.
DISPLAY = json.loads((ROOT / 'data/te_display_layout.json').read_text())
SPATIAL = DISPLAY['units']
SHORT_NAMES = DISPLAY['labels']


def unit_context(provider, model, uid, hidden=frozenset(), layout=None):
    from display_contract import require_display_layout, stream_is_directed
    layout = DISPLAY if layout is None else layout
    require_display_layout(model, layout)
    if uid not in layout["units"]:
        raise ValueError('No reviewed display configuration for unit ' + uid)
    spec = layout['units'][uid]
    replay = layout.get('channel_adapter') == 'te_replay'
    if layout.get('channel_adapter') == 'te_replay':
        from te_channels import expanded_items
        channel_items = expanded_items(model)
    else:
        channel_items = model.get('instruments', []) + model.get('final_elements', [])
    items = {i['tag']:i for i in channel_items}
    names = layout.get('labels', {})
    def source_path(it):
        template = layout.get('binding_template')
        return template.format(provider=provider, unit=it['unit'], tag=it['tag']) if template else it.get('data_point', {}).get('tag_path')
    kids = [label('BackOverview',24,70,220,24,'< Whole-process overview',{'fontWeight':'bold'},page='/'),
            label('DetailMode',270,70,1290,24,('UNIT DETAIL / RECORDED REPLAY / READ ONLY / TOPOLOGY UNVERIFIED' if replay else 'UNIT DETAIL / READ ONLY / REVIEWED DISPLAY CONFIGURATION; CHECK ASSOCIATION STATUS'),{'fontWeight':'bold'}),
            label('DetailGuide',24,106,1540,24,'Readings beside their process region. Dashed leaders = approximate location; exact taps and along-stream instrument order are unverified.',{'fontSize':13})]
    diagram_height = spec['table_top']-20
    svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 %s"><defs><marker id="spatialArrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0 0 L8 4 L0 8" fill="#717b85"/></marker></defs>' % diagram_height
    for sid,(path,x,y) in spec['streams'].items():
        st = next(s for s in model['streams'] if s['id']==sid)
        other = st['to'] if st['from']==uid else st['from']
        direction = dict(st)
        if layout.get('direction_adapter') == 'te_seed_from_to_unverified' and 'direction' not in st:
            direction['direction'] = 'forward'
        directed = stream_is_directed(direction)
        svg += '<path d="%s" fill="none" stroke="#717b85" stroke-width="2.5"%s/>' % (path, ' marker-end="url(#spatialArrow)"' if directed else '')
        kids.append(label('UnitStream_'+sid,x,y,360,29,sid+' | '+st.get('name',sid)+' | '+st['from']+(' → ' if directed else ' — ')+st['to']+('' if directed else ' · direction unknown'),{'fontSize':12},page='/unit/'+other if other!='BL' else None))
        if not any(i.get('stream')==sid for i in items.values()):
            nx,ny=spec.get('unmapped_note_positions',{}).get(sid,(x,y+47))
            kids.append(label('BoundaryUnknown_'+sid,nx,ny,300,20,'No mapped reading',{'fontSize':11,'color':MUTED}))
    level=spec.get("level")
    base=source_path(items[level]) if level and level not in hidden else None
    kids.append(image('UnitEquipment_'+uid,*spec['equipment'],spec['kind'],base))
    ex,ey,ew,eh=spec['equipment']
    kids.append(label('EquipmentName',ex-10,ey+eh+3,ew+20,24,uid,{'fontSize':13,'textAlign':'center','fontWeight':'bold'}))
    def leader(x,y,tx,ty):
        return '<path d="M%s %s L%s %s" stroke="#87929c" stroke-width="1.3" stroke-dasharray="4 3"/><circle cx="%s" cy="%s" r="4" fill="#fafafa" stroke="#566572"/>' % (x,y,tx,ty,tx,ty)
    def card(tag,x,y,width=210,name=None):
        if tag in hidden: return
        it=items[tag]
        title=name or names.get(tag,it.get('description',tag))
        kids.append(label('SpatialName_'+tag,x,y,width,20,title,{'fontSize':13,'fontWeight':'bold','backgroundColor':'#e5e5e5'}))
        c=label('Boundary_'+it['stream']+'_'+tag if it.get('stream') else 'SpatialValue_'+tag,x,y+20,width,23,'UNKNOWN',{'fontSize':16,'fontWeight':'bold','backgroundColor':'#e5e5e5'})
        code=VALUE_SCRIPT.replace('return "%.1f" % number','return ("%.1f" % number) + '+repr(' '+it['uom'])).replace('UNKNOWN / bad quality','UNKNOWN').replace('UNKNOWN / invalid value','UNKNOWN')
        path=source_path(it)
        if path: c['propConfig']={'props.text':tag_binding(path+'/PV',[script(code)]),'props.style.color':tag_binding(path+'/State',[script('if not quality.isGood() or value is None:\n    return "#6b7280"\nreturn {1:"#8a5d00",2:"#b91c1c"}.get(value,"#1f2937")')])}
        kids.append(c)
        kids.append(label('SpatialTag_'+tag,x,y+43,width,17,tag+(' · recorded output' if 'xmv' in it else ''),{'fontSize':10,'color':MUTED,'backgroundColor':'#e5e5e5'}))
    for tag,placement in spec['cards'].items():
        x,y=placement['box']
        if tag in hidden: continue
        card(tag,x,y)
        if placement.get('anchor') is not None:
            tx,ty=placement['anchor']
            sx,sy = (x,y+30) if tx < x else ((x+210,y+30) if tx > x+210 else (x+105,y if ty < y else y+60))
            svg+=leader(sx,sy,tx,ty)
        else:
            kids.append(label('Unplaced_'+tag,x,y+60,210,18,'Location unresolved',{'fontSize':10,'color':'#624d25'}))
    if 'analyzer' in spec:
        a=spec['analyzer']
        parent,x,y,tx,ty=[a[k] for k in ['parent','x','y','anchor_x','anchor_y']]
        group=[i for i in items.values() if i.get('analyzer_parent')==parent and i['tag'] not in hidden]
        if group:
            period=a['sample_minutes']
            kids.append(label('AnalyzerGroup',x,y,530,26,group[0]['stream']+' sample composition · '+str(period)+' min sample / '+str(a['delay_minutes'])+' min delay',{'fontSize':12,'fontWeight':'bold'}))
            if a.get('leader_path'):
                svg+='<path d="%s" fill="none" stroke="#87929c" stroke-width="1.3" stroke-dasharray="4 3"/><circle cx="%s" cy="%s" r="4" fill="#fafafa" stroke="#566572"/>' % (a['leader_path'],tx,ty)
            else: svg+=leader(x+70,y,tx,ty)
            for n,it in enumerate(group): card(it['tag'],x+(n%3)*165,y+30+(n//3)*65,155,'Component '+it['component'])
    if 'utilities' in spec:
        x,y,tags=spec['utilities']
        kids.append(label('UtilityTitle',x,y,520,22,spec.get('utilities_title','UTILITY CONTEXT · endpoints not modeled'),{'fontSize':12,'fontWeight':'bold'}))
        for n,tag in enumerate(tags): card(tag,x+(n%2)*245,y+28+(n//2)*65,240)
    for unavailable in spec.get('unavailable',[]):
        if unavailable['tag'] in hidden: continue
        x,y,w,h=unavailable['box']
        kids.append(label('Unavailable_'+unavailable['tag'],x,y,w,h,unavailable['label']+' · '+unavailable['tag']+'\n'+unavailable['reason'],{'fontSize':12,'whiteSpace':'pre-line'}))
        svg+=leader(x+55,y+h,*unavailable['anchor'])
    svg+='</svg>'
    kids.insert(0,{'type':'ia.display.image','meta':{'name':'UnitSpatialConnections'},'position':{'x':0,'y':0,'width':1600,'height':diagram_height},'props':{'source':uri(svg),'fit':{'mode':'fill'},'style':{'pointerEvents':'none'}}})
    foot=spec['table_top']-65
    for n,note in enumerate(spec.get('notes',[])):
        kids.append(label('PlacementReview_'+str(n),24,foot-32,1550,28,note,{'fontSize':12,'color':'#624d25'}))
    kids.append(label('UnitGraphicNote',24,foot,1550,23,('Approximate process arrangement. Solid arrows = seed-model direction. Level fill = measured %, not volume. Outputs are not measured valve position.' if replay else 'Display coordinates are illustrative. Arrows require explicit direction. Missing mappings remain UNKNOWN; unresolved locations have no physical anchor.'),{'fontSize':12,'color':MUTED}))
    kids.append(label('UnitCaveat',24,foot+25,1550,23,('Full channel inventory, quality, normal bands, alarms and history below. Grey = normal; amber = outside normal band; red = existing alarm; UNKNOWN = unavailable.' if replay else 'Configured unit presentation only. This does not establish native platform bindings, site-approved limits or operations acceptance.'),{'fontSize':12}))
    return kids


def placed_tags(model, uid):
    """The overview's curated selection (TAGS), drawn beside whichever unit the model says owns each tag.

    TAGS chooses WHICH readings the overview shows; the model decides WHERE they belong. A corrected owner in
    data/te_process_model.json therefore moves the reading on the next build without editing this file
    (scripts/pipeline.py and scripts/test_pipeline.py prove it)."""
    owner = {i['tag']: i['unit'] for i in model['instruments'] + model['final_elements']}
    return [t for tags in TAGS.values() for t in tags if owner.get(t) == uid]
