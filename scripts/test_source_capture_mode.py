"""Explicit capture admission, Native bypass and complete enabled evidence; stdlib offline controls."""
import builtins
import contextlib
import hashlib
import inspect
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import dexpi_reader as R


RAW = b'<PlantModel><MetaData><GenericAttributes><GenericAttribute Name="DrawingNameAssignmentClass" Value="Fixture"/></GenericAttributes></MetaData><Equipment ID="E1" ComponentClass="Tank"><GenericAttributes Set="Custom"><GenericAttribute Name="Pressure" Value="0" Units="Bar"/></GenericAttributes></Equipment></PlantModel>'
BOOL_ERROR = 'capture_source must be a boolean; nothing was written'
ID_ERROR = 'source_document_id requires capture_source=True; nothing was written'


class CaptureModeControls(unittest.TestCase):
    def test_signatures_keep_legacy_positions_and_keyword_only_opt_in(self):
        self.assertEqual(str(inspect.signature(R.Reader)), '(xml_path, sheet_id=None, attribution=None, source_document_id=None, *, capture_source=False)')
        self.assertEqual(str(inspect.signature(R.run)), '(xml, out, sheet_id=None, png=None, attribution=None, compare=None, quiet=False, source_document_id=None, *, capture_source=False)')
        with self.assertRaises(TypeError): R.Reader('absent', None, None, None, True)
        with self.assertRaises(TypeError): R.run('absent', 'out', None, None, None, None, False, None, True)

    def test_non_boolean_capture_refuses_before_path_backend_or_callbacks(self):
        calls = []
        class Foreign:
            def __bool__(self): calls.append('bool'); return True
            def __str__(self): calls.append('str'); return 'foreign'
            def __repr__(self): calls.append('repr'); return 'foreign'
            def __fspath__(self): calls.append('path'); return 'absent'
        class Meta(type):
            def __eq__(self, other): calls.append('type-equality'); return True
        class Profile(metaclass=Meta): pass
        for entry in ('Reader', 'run'):
            for number, value in enumerate((None, 0, 1, 1.0, 'true', Foreign(), Profile())):
                with self.subTest(entry=entry, case=number), patch.object(R, 'Path', side_effect=AssertionError('path access')), self.assertRaises(R.DexpiError) as error:
                    R.Reader(Foreign(), capture_source=value) if entry=='Reader' else R.run(Foreign(), Foreign(), capture_source=value)
                self.assertEqual(error.exception.args, (BOOL_ERROR,))
        self.assertEqual(calls, [])

    def test_disabled_document_id_uses_identity_only_and_precedes_path_work(self):
        calls = []
        class Foreign:
            def __eq__(self, other): calls.append('eq'); return other is None
            def __bool__(self): calls.append('bool'); return False
            def __str__(self): calls.append('str'); return 'id'
            def __repr__(self): calls.append('repr'); return 'id'
            def __fspath__(self): calls.append('path'); return 'absent'
        for entry in ('Reader', 'run'):
            for number, value in enumerate(('', 'department/A', 0, False, Foreign())):
                with self.subTest(entry=entry, case=number), patch.object(R, 'Path', side_effect=AssertionError('path access')), self.assertRaises(R.DexpiError) as error:
                    R.Reader(Foreign(), source_document_id=value) if entry=='Reader' else R.run(Foreign(), Foreign(), source_document_id=value)
                self.assertEqual(error.exception.args, (ID_ERROR,))
        self.assertEqual(calls, [])

    def test_default_and_explicit_false_are_native_with_ordinary_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);xml=base/'source.xml';xml.write_bytes(RAW)
            a, ar=R.run(xml, base/'a', 'fixture', quiet=True)
            b, br=R.run(xml, base/'b', 'fixture', quiet=True, capture_source=False)
            self.assertEqual(a, b); self.assertEqual(ar, br)
            self.assertNotIn('source_evidence', a); self.assertNotIn('source_evidence', ar)
            self.assertEqual(a['meta']['drawing']['DrawingNameAssignmentClass'], 'Fixture')
            self.assertEqual(a['units'][0]['Pressure']['value'], '0')
            self.assertEqual({p.name:p.read_bytes() for p in (base/'a').iterdir()}, {p.name:p.read_bytes() for p in (base/'b').iterdir()})
            self.assertIsNone(R.Reader(xml).source_capture)

    def test_fresh_native_success_and_failures_never_import_capture_backend(self):
        bootstrap = '''import builtins,sys
original=builtins.__import__
def importing(name,*a,**k):
    if name=='source_evidence':raise AssertionError('Native imported capture backend')
    return original(name,*a,**k)
builtins.__import__=importing
sys.path.insert(0,sys.argv[1])
import dexpi_reader as R
try:R.run(sys.argv[2],sys.argv[3],quiet=True,png=sys.argv[4] or None)
except R.DexpiError:
    assert sys.argv[5]=='refuse'
else:assert sys.argv[5]=='success'
assert 'source_evidence' not in sys.modules
'''
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);badpng=base/'bad.png';badpng.write_bytes(b'bad')
            for number, (raw, png, expected) in enumerate(((RAW, '', 'success'), (b'<broken', '', 'refuse'),
                    (b'<PlantModel><Equipment ID="X"/><Equipment ID="X"/></PlantModel>', '', 'refuse'), (RAW, str(badpng), 'refuse'))):
                xml=base/f'{number}.xml';xml.write_bytes(raw)
                p=subprocess.run([sys.executable,'-B','-S','-c',bootstrap,str(Path(R.__file__).parent),str(xml),str(base/f'out{number}'),png,expected],capture_output=True)
                self.assertEqual(p.returncode,0,p.stderr.decode(errors='replace'))

    def test_native_bypass_when_backend_already_loaded_does_not_use_it(self):
        import source_evidence as S
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);xml=base/'source.xml';xml.write_bytes(RAW)
            with contextlib.ExitStack() as stack:
                for name in ('capture_xml','canonical','digest','_native_encoding_bytes'):
                    stack.enter_context(patch.object(S,name,side_effect=AssertionError('source work')))
                for name in ('source_ref','assign','transfer','finalize'):
                    stack.enter_context(patch.object(S.Capture,name,side_effect=AssertionError('source work')))
                m,_=R.run(xml,base/'out',quiet=True)
            self.assertNotIn('source_evidence',m)
            self.assertEqual(m['units'][0]['Pressure']['uom'],'Bar')

    def test_enabled_capture_is_complete_and_native_projection_is_equal(self):
        import source_evidence as S
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);xml=base/'source.xml';xml.write_bytes(RAW)
            native,nrep=R.run(xml,base/'native','fixture',quiet=True)
            enabled,rep=R.run(xml,base/'capture','fixture',quiet=True,capture_source=True)
            packet=enabled['source_evidence'];S.validate_packet(packet,native_model=enabled,require_native_targets=True)
            self.assertEqual({k:v for k,v in enabled.items() if k!='source_evidence'},native)
            self.assertEqual({k:v for k,v in rep.items() if k!='source_evidence'},nrep)
            self.assertEqual(packet['document']['raw_source_sha256'],hashlib.sha256(RAW).hexdigest())
            self.assertTrue(packet['records']); self.assertGreater(packet['completeness']['native_mapping']['destinations'],0)
            self.assertEqual(rep['source_evidence']['completeness'],packet['completeness'])
            self.assertIn('Opaque XML source evidence',R.report_text(rep))
            self.assertNotIn('Opaque XML source evidence',R.report_text(nrep))

    def test_controlled_ids_are_exact_and_never_engineering_joins(self):
        with tempfile.TemporaryDirectory() as tmp:
            xml=Path(tmp)/'source.xml';xml.write_bytes(RAW);models=[]
            for identity in (None,'plant/A','plant/B'):
                r=R.Reader(xml,source_document_id=identity,capture_source=True);models.append(r.read())
            packets=[m['source_evidence'] for m in models]
            self.assertEqual(packets[0]['document']['document_id'],'urn:sha256:'+hashlib.sha256(RAW).hexdigest())
            self.assertEqual([p['document']['document_id'] for p in packets[1:]],['plant/A','plant/B'])
            self.assertEqual(len({p['records'][0]['occurrence_id'] for p in packets}),3)
            self.assertEqual([{k:v for k,v in m.items() if k!='source_evidence'} for m in models],[{k:v for k,v in models[0].items() if k!='source_evidence'}]*3)
            class Foreign(str): pass
            for number, bad in enumerate(('', ' ', ' padded', 0, Foreign('id'))):
                with self.subTest(case=number),self.assertRaises(R.DexpiError):R.Reader(xml,source_document_id=bad,capture_source=True)

    def test_enabled_initialization_finalization_and_assignment_never_fall_back(self):
        import source_evidence as S
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);xml=base/'source.xml';xml.write_bytes(RAW)
            with patch.object(S,'capture_xml',side_effect=S.SourceEvidenceError('controlled initializer')) as capture, self.assertRaises(R.DexpiError):
                R.run(xml,base/'init',capture_source=True,quiet=True)
            self.assertEqual(capture.call_count,1);self.assertFalse((base/'init').exists())
            for name in ('finalize','assign'):
                with patch.object(S.Capture,name,side_effect=S.SourceEvidenceError('controlled '+name)),self.assertRaises(S.SourceEvidenceError):
                    R.run(xml,base/name,capture_source=True,quiet=True)
                self.assertFalse((base/name).exists())

    def test_disabled_scope_helper_refuses_before_any_source_callback_or_write(self):
        calls=[]
        class Foreign:
            def __hash__(self):calls.append('hash');return 0
            def __eq__(self,other):calls.append('eq');return True
            def __str__(self):calls.append('str');return 'foreign'
        with tempfile.TemporaryDirectory() as tmp:
            xml=Path(tmp)/'source.xml';xml.write_bytes(RAW);r=R.Reader(xml);target={'before':False,'value':None}
            with self.assertRaises(R.DexpiError) as error:r._assign_scope_excluded_native(Foreign(),target,'value','bad',Foreign(),Foreign())
            self.assertEqual(error.exception.args,('source capture is not enabled',));self.assertEqual(target,{'before':False,'value':None})
        self.assertEqual(calls,[])

    def test_cli_explicit_capture_id_and_disabled_combination(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);xml=base/'source.xml';xml.write_bytes(RAW);script=str(Path(R.__file__))
            for number, args in enumerate((['--source-document-id','A'],['--source-document-id',''],['--document-id','A'])):
                out=base/f'bad{number}';p=subprocess.run([sys.executable,'-B','-S',script,'--xml',str(base/'absent.xml'),'--out',str(out),*args],capture_output=True)
                self.assertEqual(p.returncode,2);self.assertEqual(p.stdout,b'');self.assertFalse(out.exists())
                self.assertIn(b'--source-document-id requires --capture-source' if number<2 else b'unrecognized arguments',p.stderr)
            for number, args in enumerate(([],['--capture-source'],['--capture-source','--source-document-id','site/department'])):
                out=base/f'good{number}';p=subprocess.run([sys.executable,'-B','-S',script,'--xml',str(xml),'--out',str(out),'--sheet-id','fixture',*args],capture_output=True)
                self.assertEqual(p.returncode,0,p.stderr.decode(errors='replace'));self.assertEqual(p.stderr,b'')
                model=json.loads((out/'fixture.model.json').read_bytes());self.assertEqual('source_evidence' in model,number>0)
                if number==2:self.assertEqual(model['source_evidence']['document']['document_id'],'site/department')


if __name__=='__main__':
    unittest.main()
