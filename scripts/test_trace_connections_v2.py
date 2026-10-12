"""Offline authored geometry controls; no dataset labels or model/network calls."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

import cv2
import numpy as np
import trace_connections_v2 as v2


def train(start, stop, y):
    lines = [((x,y),(min(x+18,stop),y)) for x in range(start,stop,30)]
    if lines[-1][1][0] < stop:
        lines.append(((stop-18,y),(stop,y)))
    return lines


class ConnectivityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.image = Path(self.tmp.name) / 'drawing.png'

    def draw(self, boxes, lines, scale=1):
        image = np.full((round(1000*scale),round(1000*scale)),255,np.uint8)
        point = lambda p: tuple(round(x*scale) for x in p)
        for a,b in lines:
            cv2.line(image,point(a),point(b),0,max(1,round(2*scale)))
        for box in boxes.values():
            cv2.rectangle(image,point(box[:2]),point(box[2:]),0,max(1,round(2*scale)))
        cv2.imwrite(str(self.image),image)
        return [{'id':key,'class':'general','box':box} for key,box in boxes.items()]

    def assert_links(self, boxes, lines, expected, scale=1):
        symbols=self.draw(boxes,lines,scale)
        actual=v2.trace(self.image,symbols)
        self.assertEqual({tuple(sorted((x['from'],x['to']))) for x in actual},set(expected))
        return symbols,actual

    def test_topology_and_barriers_at_three_scales(self):
        a,b,c,d=[100,470,160,530],[840,470,900,530],[470,100,530,160],[470,840,530,900]
        for scale in (.5,1,2):
            with self.subTest(scale=scale):
                self.assert_links(dict(A=a,B=b,C=c),[((160,500),(840,500)),((500,160),(500,500))],
                                  [('A','B'),('A','C'),('B','C')],scale)
                self.assert_links(dict(A=a,B=b,C=c,D=d),[((160,500),(840,500)),((500,160),(500,840))],
                                  [('A','B'),('A','C'),('A','D'),('B','C'),('B','D'),('C','D')],scale)
                self.assert_links(dict(A=a,B=b,V=[470,470,530,530]),[((160,500),(840,500))],
                                  [('A','V'),('B','V')],scale)

    def test_dashed_connections_and_negative_gaps(self):
        boxes=dict(A=[100,470,160,530],B=[840,470,900,530])
        for scale in (.5,1,2):
            cases=[(train(160,840,500),[('A','B')]),
                   ([((160,500),(490,500)),((510,500),(840,500))],[]),
                   (train(160,400,500)+train(600,840,500),[]),
                   ([((160,500),(178,500)),((490,500),(508,500)),((822,500),(840,500))],[])]
            for index,(lines,want) in enumerate(cases):
                with self.subTest(scale=scale,case=index):
                    self.assert_links(boxes,lines,want,scale)
            self.assert_links({**boxes,'V':[470,470,530,530]},train(160,470,500)+train(530,840,500),
                              [('A','V'),('B','V')],scale)

    def test_bends_and_near_misses(self):
        for scale in (.5,1,2):
            boxes=dict(A=[100,470,160,530],B=[470,840,530,900])
            horizontal=train(160,490,500)
            vertical=[((500,y),(500,min(y+18,840))) for y in range(510,840,30)]
            vertical.append(((500,822),(500,840)))
            self.assert_links(boxes,horizontal+vertical,[('A','B')],scale)
            shifted=[((x+30,y),(u+30,v)) for (x,y),(u,v) in vertical]
            self.assert_links({**boxes,'B':[500,840,560,900]},horizontal+shifted,[],scale)

    def test_parallel_lines_never_merge(self):
        for scale in (.5,1,2):
            boxes=dict(A=[100,410,160,470],B=[840,410,900,470],C=[100,490,160,550],D=[840,490,900,550])
            self.assert_links(boxes,train(160,840,440)+train(160,840,520),[('A','B'),('C','D')],scale)

    def test_small_symbol_dash_threshold_is_explicit_limit(self):
        boxes=dict(A=[100,420,160,460],B=[840,420,900,460],C=[100,480,160,520],D=[840,480,900,520])
        # 21px rasterized dashes exceed .5*40px. Record the known miss, not a safety success.
        self.assert_links(boxes,train(160,840,440)+train(160,840,500),[],1)

    def test_refine_preserves_source_and_marks_unknowns(self):
        symbols=self.draw(dict(A=[100,470,160,530],B=[840,470,900,530]),train(160,840,500))
        record={'prediction':{'symbols':symbols,'connections':[]},'freeze':{'original':True}}
        original=copy.deepcopy(record)
        result=v2.refine(self.image,record)
        self.assertEqual(record,original)
        self.assertEqual(result['source_record'],record)
        self.assertEqual(result['prediction']['symbols'],symbols)
        self.assertNotIn('freeze',result)
        link=result['prediction']['connections'][0]
        self.assertIsNone(link['semantic_line_type']);self.assertIsNone(link['flow_direction'])
        self.assertTrue(link['gap_recovery_dependent']);self.assertTrue(link['network_ids'])
        self.assertEqual(result['connectivity']['raw_connections'],[])
        self.assertTrue(any(n['recovered_pixels'] for n in result['connectivity']['raster_recovery']['networks']))
        json.dumps(result,allow_nan=False)

    def test_raw_links_not_silently_unioned(self):
        symbols=self.draw(dict(A=[100,470,160,530],B=[840,470,900,530]),[])
        result=v2.refine(self.image,{'symbols':symbols,'connections':[{'from':'A','to':'B'}]})
        self.assertEqual(result['prediction']['connections'],[])
        self.assertEqual(len(result['connectivity']['raw_connections']),1)

    def test_bad_symbols_fail(self):
        symbols=self.draw(dict(A=[100,470,160,530],B=[840,470,900,530]),[])
        symbols[1]['id']='A'
        with self.assertRaises(ValueError):v2.refine(self.image,{'symbols':symbols})


if __name__ == '__main__':
    unittest.main(verbosity=2)
