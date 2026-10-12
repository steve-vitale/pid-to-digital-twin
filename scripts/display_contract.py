"""Small additive presentation contract for existing plant models.

Layout is reviewed display configuration, never process topology or evidence of a
physical tap. Missing point mappings and unknown directions remain permissible.
"""
import math

ASSOCIATION_STATUSES = frozenset(('approximate', 'confirmed', 'unresolved'))


def stream_is_directed(stream):
    """Only an explicit forward direction authorizes a forward arrow."""
    return stream.get('direction') in ('forward', 'from_to')


def validate_display_layout(model, layout):
    errors = []
    if layout.get('schema_version') != 1:
        errors.append('unsupported display schema_version')
    if layout.get('model_id') != model.get('meta', {}).get('model_id'):
        errors.append('display model_id does not match model')
    units = {u['id']: u for u in model.get('units', [])}
    streams = {s['id']: s for s in model.get('streams', [])}
    items = {i['tag']: i for i in model.get('instruments', []) + model.get('final_elements', []) if i.get('tag')}

    def geometry(value, length, path, positive_size=False):
        valid = isinstance(value, (list, tuple)) and len(value) == length
        valid = valid and all(isinstance(n, (int, float)) and not isinstance(n, bool) and math.isfinite(n) for n in value)
        if not valid:
            errors.append(path + ': expected %s finite coordinates' % length)
        elif positive_size and (value[2] <= 0 or value[3] <= 0):
            errors.append(path + ': width and height must be positive')

    for uid, spec in layout.get('units', {}).items():
        prefix = 'unit ' + uid
        if uid not in units:
            errors.append(prefix + ': unknown model unit')
        geometry(spec.get('equipment'), 4, prefix + '.equipment', True)
        geometry([spec.get('table_top')], 1, prefix + '.table_top')
        if not isinstance(spec.get('kind'), str) or not spec['kind']:
            errors.append(prefix + ': missing symbol kind')
        for sid, route in spec.get('streams', {}).items():
            st = streams.get(sid)
            if st is None:
                errors.append(prefix + ': unknown stream ' + sid)
            elif uid not in (st.get('from'), st.get('to')):
                errors.append(prefix + ': stream ' + sid + ' is not incident to unit')
            if not isinstance(route, (list, tuple)) or len(route) != 3 or not isinstance(route[0], str):
                errors.append(prefix + ': invalid route ' + sid)
            else:
                geometry(route[1:], 2, prefix + '.streams.' + sid)
        for tag, card in spec.get('cards', {}).items():
            path = prefix + '.cards.' + tag
            item = items.get(tag)
            if item is None:
                errors.append(path + ': unknown measurement tag')
            geometry(card.get('box'), 2, path + '.box')
            if card.get('anchor') is not None:
                geometry(card['anchor'], 2, path + '.anchor')
            a = card.get('association') or {}
            kind, target, status = a.get('kind'), a.get('id'), a.get('status')
            if status not in ASSOCIATION_STATUSES:
                errors.append(path + ': invalid association status')
            if not isinstance(a.get('evidence'), str) or not a['evidence'].strip():
                errors.append(path + ': missing association evidence or unresolved reason')
            if status == 'unresolved':
                if card.get('anchor') is not None:
                    errors.append(path + ': unresolved association cannot have a physical anchor')
            elif kind not in ('unit', 'stream'):
                errors.append(path + ': unsupported association kind')
            elif target not in (units if kind == 'unit' else streams):
                errors.append(path + ': unknown association target')
            elif kind == 'stream':
                if target not in spec.get('streams', {}):
                    errors.append(path + ': associated stream has no display route')
                if item and item.get('stream') and item['stream'] != target:
                    errors.append(path + ': association conflicts with model stream')
            if status != 'unresolved' and card.get('anchor') is None:
                errors.append(path + ': resolved/approximate association requires anchor')
        level = spec.get('level')
        if level:
            item = items.get(level)
            if not item or item.get('variable') != 'level' or item.get('uom') != '%':
                errors.append(prefix + ': level fill requires a modeled level measurement in %')
        for block in spec.get('unavailable', []):
            if block.get('tag') not in items:
                errors.append(prefix + ': unknown unavailable tag')
            geometry(block.get('box'), 4, prefix + '.unavailable.box', True)
            geometry(block.get('anchor'), 2, prefix + '.unavailable.anchor')
        if spec.get('utilities'):
            utility = spec['utilities']
            if len(utility) != 3:
                errors.append(prefix + ': invalid utilities block')
            else:
                geometry(utility[:2], 2, prefix + '.utilities')
                for tag in utility[2]:
                    if tag not in items:
                        errors.append(prefix + ': unknown utility tag ' + tag)
        if spec.get('analyzer'):
            analyzer = spec['analyzer']
            if analyzer.get('parent') not in items:
                errors.append(prefix + ': unknown analyzer parent')
            for key in ('x', 'y', 'anchor_x', 'anchor_y', 'sample_minutes', 'delay_minutes'):
                geometry([analyzer.get(key)], 1, prefix + '.analyzer.' + key)
            for key in ('sample_minutes', 'delay_minutes'):
                value = analyzer.get(key)
                if isinstance(value, (int, float)) and value < 0:
                    errors.append(prefix + ': analyzer timing cannot be negative')
    return errors


def require_display_layout(model, layout):
    errors = validate_display_layout(model, layout)
    if errors:
        raise ValueError('Invalid display layout: ' + '; '.join(errors))
    return layout
