"""Replay-channel expansion, without changing the reviewed seed model.

Analyzer component names/order come from the seed's source-verified XMEAS ranges:
23–28 A–F, 29–36 A–H, 37–41 D–H (teprob.f header, out/te_source_check.md).
The legacy scalar analyzer tags retain their first component. New sibling suffixes
are project-assigned display/OPC identifiers, not original plant instrument tags.
"""
from copy import deepcopy

ANALYZERS = {'AI-123': (23, 'ABCDEF'), 'AI-129': (29, 'ABCDEFGH'), 'AI-137': (37, 'DEFGH')}


def expanded_items(model):
    result = []
    for original in model['instruments'] + model['final_elements']:
        item = deepcopy(original)
        spec = ANALYZERS.get(item['tag'])
        if not spec:
            result.append(item)
            continue
        start, components = spec
        if str(item.get('xmeas')) != '%s-%s' % (start, start + len(components) - 1):
            raise ValueError('Unexpected analyzer source range: ' + item['tag'])
        parent = item['tag']
        for offset, component in enumerate(components):
            channel = deepcopy(item)
            channel.update(tag=parent if offset == 0 else parent + '-' + component,
                           xmeas=start + offset, analyzer_parent=parent, component=component,
                           source_range=item['xmeas'],
                           description=item['description'].split(' (components')[0] + ' | component ' + component,
                           channel_provenance='Project-assigned component identifier; teprob.f XMEAS %d' % (start + offset))
            result.append(channel)
    return result


def channel_columns(model):
    columns = {}
    for item in expanded_items(model):
        if 'xmeas' in item:
            columns[item['tag']] = item['xmeas'] - 1
        elif item['xmv'] <= 11:
            columns[item['tag']] = 41 + item['xmv'] - 1
    return columns
