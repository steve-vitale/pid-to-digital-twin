"""Render approximate offline SVG snapshots from the same Perspective components.

Requires Inkscape for PNG output. This is not a browser or gateway screenshot.
HTML preview remains the interactive deliverable; no additional data is generated.
"""
import html
import json
import subprocess
import textwrap
from preview_mimic import ROOT, OUT, fixtures, resolve
from ignition import build_mimic, build_hmi


def snapshot(v, values, states, good, title):
    canvas_height = v['props']['defaultSize']['height'] + 50
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="1600" height="%s" viewBox="0 0 1600 %s">' % (canvas_height, canvas_height),
             '<rect width="1600" height="%s" fill="#e5e5e5"/>' % canvas_height,
             '<rect width="1600" height="50" fill="#25313d"/><text x="24" y="31" font-family="Arial" font-size="16" fill="white">OFFLINE SVG RENDER / NOT A GATEWAY SCREENSHOT — ' + html.escape(title) + '</text>']
    for raw in v['root']['children']:
        c = resolve(raw, values, states, good)
        p, props = c['position'], c['props']
        x, y, w, h = p['x'], p['y'] + 50, p['width'], p['height']
        if c['type'] == 'ia.display.image':
            parts.append('<image x="%s" y="%s" width="%s" height="%s" xlink:href="%s"/>' % (x,y,w,h,props['source']))
            continue
        if c['type'] == 'ia.display.moving-analog-indicator':
            props['text'] = 'PV: ' + str(props.get('processValue', 'UNKNOWN'))
        s = props.get('style', {})
        bg = s.get('backgroundColor', 'none')
        if bg != 'transparent': parts.append('<rect x="%s" y="%s" width="%s" height="%s" rx="3" fill="%s"/>' % (x,y,w,h,bg))
        size = s.get('fontSize', 13)
        align = s.get('textAlign', 'left')
        tx = x + (w/2 if align == 'center' else w - 4 if align == 'right' else 4)
        anchor = 'middle' if align == 'center' else 'end' if align == 'right' else 'start'
        lines=[]
        for line in str(props.get('text','')).splitlines():
            lines += [line] if s.get('whiteSpace') == 'nowrap' else (textwrap.wrap(line, max(8, int((w-8)/(size*.50)))) or [''])
        parts.append('<text x="%s" y="%s" font-family="Arial" font-size="%s" font-weight="%s" text-anchor="%s" fill="%s">' % (tx,y+size+3,size,s.get('fontWeight','normal'),anchor,s.get('color','#1f2937')))
        for i,line in enumerate(lines[:max(1,int(h/(size*1.15)))]):
            parts.append('<tspan x="%s" dy="%s">%s</tspan>' % (tx,0 if i==0 else size*1.15,html.escape(line)))
        parts.append('</text>')
    return ''.join(parts)+'</svg>'


def main():
    model=json.loads((ROOT/'data/te_process_model.json').read_text())
    meta=json.loads((ROOT/'out/ignition/gateway/build_meta.json').read_text())
    views,_=build_hmi.te_views('Twin',meta['te_ranges'],meta['alarms'],set())
    for prefix,v in [('overview',views['TE/Overview'])] + [(build_mimic.KINDS[uid],views['TE/Unit_'+uid]) for uid in build_mimic.UNIT_ORDER]:
        for name,(title,values,states,good) in zip(['normal','fault6','bad-quality'],fixtures(model,meta)):
            path=OUT/(prefix+'-'+name+'.svg')
            path.write_text(snapshot(v,values,states,good,title))
            subprocess.run(['inkscape',str(path),'--export-type=png','--export-filename='+str(OUT/(prefix+'-'+name+'.png'))],check=True)
            if prefix == 'overview':
                for ext in ['svg','png']:
                    (OUT/(name+'.'+ext)).write_bytes((OUT/(prefix+'-'+name+'.'+ext)).read_bytes())


if __name__ == '__main__': main()
