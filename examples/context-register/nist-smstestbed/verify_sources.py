"""Check pinned original XML and raw observations independently of answer prose.

Standard library only; no source or model writes. Expectations below are explicit
primary-source checks. This script never reads proposed_answers.csv/source_key.json.
"""
import argparse
import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

NS = '{urn:mtconnect.org:MTConnectDevices:1.3}'
PINS = {
    '2016/Devices.xml': (61363, 'c696155196da9a783efc1f5be6618db561a4f5a6dc8998a1120c3077e60c9998'),
    '2017/Devices.xml': (39450, 'bb54e4eca7b65e50b026d02b785c3f905b66bd38493456569272540296f68166'),
    'raw/Hurco04-20170217-20170218.txt': (17314, '093a80ace21094a6c164e5ab8879ffd893c90fdf5902e18677f57d8bfa679b6a'),
    'README.md': (3704, '295bf123b805c8b3232702ed390a10ee77a5ebc159388b421781b55f76e31eaa'),
}


def device(data):
    root = ET.fromstring(data)
    matches = [d for d in root.iter(NS+'Device') if d.get('id') == 'Hurco04']
    assert len(matches) == 1, 'Hurco04 is missing or ambiguous'
    return matches[0]


def item(dev, item_id):
    matches = [d for d in dev.iter(NS+'DataItem') if d.get('id') == item_id]
    assert len(matches) == 1, item_id+' is missing or ambiguous in Hurco04'
    return matches[0]


def attrs(element, expected):
    for name, expected_value in expected.items():
        assert element.get(name) == expected_value, name+' differs from the inspected original'


def verify(source_root):
    data, failures, unavailable, checked = {}, [], [], []
    for name, (size, sha) in PINS.items():
        path = source_root/name
        if not path.is_file():
            unavailable.append(name)
            continue
        content = path.read_bytes()
        if len(content) != size or hashlib.sha256(content).hexdigest() != sha:
            failures.append(name+': original byte count or SHA-256 differs')
            continue
        data[name] = content
    if failures or unavailable:
        return dict(originals_verified=len(data), primary_check_groups_verified=[], failures=failures,
                    unavailable=unavailable, note='Run python -S examples/context-register/nist-smstestbed/fetch_sources.py to fetch the pinned originals.')

    old = device(data['2016/Devices.xml'])
    new = device(data['2017/Devices.xml'])
    raw = data['raw/Hurco04-20170217-20170218.txt'].decode('utf-8').splitlines()
    old_lines = data['2016/Devices.xml'].decode('utf-8').splitlines()
    def check(name, fn):
        try:
            fn()
        except (AssertionError, IndexError, KeyError, ValueError) as exc:
            failures.append(name+': '+str(exc))
        else:
            checked.append(name)
    def identity(dev):
        attrs(dev, {'id':'Hurco04','name':'Hurco04','uuid':'mtc_adapter008'})
        attrs(dev.find(NS+'Description'), {'manufacturer':'Hurco','model':'VMX24'})
    def record(line, expected):
        assert raw[line-1].split('|') == expected, 'physical line '+str(line)+' differs'
    check('N01 old machine identity', lambda: identity(old))
    check('N02 later machine identity', lambda: identity(new))
    check('N03 old reused-ID meaning', lambda: attrs(item(old,'Hurco04-path_7'),
          {'name':'current_tool','type':'TOOL_NUMBER','category':'EVENT'}))
    check('N04 later reused-ID meaning', lambda: attrs(item(new,'Hurco04-path_7'),
          {'name':'Program_Runtime_Seconds','type':'ACCUMULATED_TIME','category':'SAMPLE','units':'SECOND'}))
    def spindle_definition():
        element = item(new,'Hurco04-C_1')
        attrs(element, {'name':'Spindle_Speed','type':'ROTARY_VELOCITY','subType':'ACTUAL','units':'REVOLUTION/MINUTE'})
        assert element.find(NS+'Source').text == 'spindle_speed'
    check('N05 later spindle definition', spindle_definition)
    check('N06 selected original spindle record', lambda: record(81,
          ['2017-02-17T09:26:08.0468750Z','Spindle_Speed','1000.000000']))
    def unavailable_vs_zero():
        record(3, ['2017-02-14T16:12:54.968217Z','Spindle_Speed','UNAVAILABLE'])
        record(34, ['2017-02-17T09:18:51.4531250Z','Spindle_Speed','0'])
    check('N07 unavailable and zero retained separately', unavailable_vs_zero)
    def program_records():
        record(37, ['2017-02-17T09:18:51.4531250Z','Program_Name_Running',' '])
        record(45, ['2017-02-17T09:18:51.4531250Z','Program_Status','READY'])
        record(359, ['2017-02-17T09:40:46.755688Z','Program_Status','UNAVAILABLE'])
        assert {r.split('|')[2] for r in raw if r.split('|')[1]=='Program_Status'} == {'READY','UNAVAILABLE'}
    check('N08 program evidence and gaps', program_records)
    def raw_structure():
        assert len(raw) == 363
        assert all(len(line.split('|')) == 3 for line in raw)
        content = '\n'.join(raw)
        assert all(value not in content for value in ['mtc_adapter008','configuration_revision','Devices.xml'])
        assert raw[0].startswith('2017-01-23T'), 'out-of-filename-date initial observation missing'
    check('N09 raw structure and absent deployment identity', raw_structure)
    def feed_uncertainty():
        attrs(item(old,'Hurco04-path_10'), {'name':'feed_rate','type':'PATH_FEEDRATE','subType':'ACTUAL','units':'MILLIMETER/SECOND'})
        assert '<!-- Actual? -->' in old_lines[726]
    check('N10 source feed semantic uncertainty', feed_uncertainty)
    notice = data['README.md'].decode('utf-8')
    assert 'With the exception of material marked as copyrighted' in notice
    assert 'may be distributed or copied' in notice
    return dict(originals_verified=4, primary_check_groups_verified=checked, failures=failures,
                unavailable=unavailable, note='Development checks of original records; no human ownership, deployment truth, production state or sign-off established.')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-root',type=Path,default=Path('data/external/nist-smstestbed'))
    args = p.parse_args()
    result = verify(args.source_root)
    print(json.dumps(result,indent=2))
    return 1 if result['failures'] else 2 if result['unavailable'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
