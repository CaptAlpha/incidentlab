import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from http.server import ThreadingHTTPServer
from incidentlab.engine import analyze, report
from incidentlab.server import handler, ROOT
from incidentlab.store import Store

class EngineTests(unittest.TestCase):
    def setUp(self): self.records=json.loads((ROOT/'fixtures/checkout.json').read_text())
    def test_citations_and_correlation(self):
        result=analyze(self.records);f=result['findings'][0]
        self.assertEqual(result['severity'],'critical')
        self.assertEqual(f['confidence'],'medium')
        self.assertEqual(len(f['evidence_ids']),4)
        self.assertTrue(set(f['evidence_ids'])<={e['id'] for e in result['evidence']})
        self.assertIn('not proof of causation',f['explanation'])
    def test_idempotence(self): self.assertEqual(analyze(self.records),analyze(self.records+list(reversed(self.records))))
    def test_other_service_excluded(self):
        self.records[1]['resource']['labels']['service_name']='unrelated'
        self.assertEqual(analyze(self.records)['findings'][0]['confidence'],'low')
    def test_future_and_stale_changes_excluded(self):
        for t in ('2026-10-28T11:00:00Z','2026-10-28T09:00:00Z'):
            self.records[1]['timestamp']=t
            self.assertEqual(analyze(self.records)['findings'][0]['confidence'],'low')
    def test_healthy_window(self): self.assertEqual(analyze([self.records[0]])['findings'],[])
    def test_bad_input(self):
        for records in ([],{},[None],[{'timestamp':'invalid'}],self.records*2000):
            with self.assertRaises((ValueError,TypeError)): analyze(records)
    def test_invalid_metrics(self):
        for value in ('ninety',-1,101,True,float('nan')):
            self.records[0]['jsonPayload']['error_rate']=value
            with self.assertRaises(ValueError): analyze(self.records)
    def test_timezone_required(self):
        self.records[0]['timestamp']='2026-10-28T10:00:00'
        with self.assertRaises(ValueError): analyze(self.records)
    def test_other_scenarios(self):
        for name,title in [('database','Resource saturation'),('iam','Authorization failures')]:
            result=analyze(json.loads((ROOT/('fixtures/'+name+'.json')).read_text()))
            self.assertIn(title,[f['title'] for f in result['findings']])
    def test_report(self):
        result=analyze(self.records);output=report(result)
        for e in result['evidence']:self.assertIn(e['id'],output)
        self.assertIn('## Limits',output)

class APITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.path=Path(cls.temp.name)/'test.db'
        cls.store=Store(cls.path)
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),handler(cls.store))
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
        cls.base='http://127.0.0.1:'+str(cls.server.server_port)
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join();cls.temp.cleanup()
    def request(self,path,body=None,headers=None):
        return urlopen(Request(self.base+path,data=json.dumps(body).encode() if body is not None else None,headers=headers or {}),timeout=5)
    def test_end_to_end_and_persistence(self):
        with self.request('/api/scenarios',{'name':'checkout'}) as response:
            self.assertEqual(response.status,201);result=json.load(response)
        with self.request('/api/investigations/'+result['id']) as response:self.assertEqual(json.load(response),result)
        with self.request('/api/investigations/'+result['id']+'/report') as response:self.assertIn(result['id'],response.read().decode())
        self.assertEqual(Store(self.path).get(result['id']),result)
        self.request('/api/scenarios',{'name':'checkout'}).close()
        self.assertEqual(len(self.store.list()),1)
    def test_assets_and_health(self):
        with self.request('/api/health') as response:self.assertEqual(json.load(response)['cloud_connections'],0)
        for path in ('/','/app.js','/style.css'):
            with self.request(path) as response:
                self.assertEqual(response.status,200);self.assertIn("default-src 'self'",response.headers['Content-Security-Policy'])
    def test_invalid_scenario(self):
        with self.assertRaises(HTTPError) as caught:self.request('/api/scenarios',{'name':'../../etc/passwd'})
        self.assertEqual(caught.exception.code,400)
    def test_cross_origin_rejected(self):
        with self.assertRaises(HTTPError) as caught:self.request('/api/scenarios',{'name':'iam'},{'Origin':'https://example.com'})
        self.assertEqual(caught.exception.code,403)
    def test_missing_paths(self):
        for path in ('/api/investigations/missing','/../incidentlab/server.py'):
            with self.assertRaises(HTTPError) as caught:self.request(path)
            self.assertEqual(caught.exception.code,404)
if __name__=='__main__':unittest.main()
