"""Risk explain HTTP contract tests: JSON upload and static local resources."""
import http.client
from functools import partial
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
from threading import Thread
from unittest import TestCase

from option_lab.server import Handler, DOCS

REPO = Path(__file__).resolve().parents[1]

class RiskHttpTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = ThreadingHTTPServer(("127.0.0.1",0),partial(Handler,directory=str(DOCS)))
        cls.thread = Thread(target=cls.srv.serve_forever,daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        cls.thread.join(timeout=2)

    def request(self, method, path, payload=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1",self.srv.server_port,timeout=10)
        try:
            conn.request(method,path,body=payload,headers=headers or {})
            reply=conn.getresponse()
            return reply.status, reply.read().decode("utf-8")
        finally:
            conn.close()

    def test_valid_risk_post(self):
        payload = json.dumps({
          "start_csv":(REPO/"examples"/"positions_2026-10-05.csv").read_text(),
          "end_csv":(REPO/"examples"/"positions_2026-10-06.csv").read_text(),
          "threshold":500
        })
        code, body=self.request("POST","/api/explain",payload,{"Content-Type":"application/json"})
        self.assertEqual(code,200,body)
        obj=json.loads(body)
        self.assertEqual(obj["position_count"],5)
        self.assertAlmostEqual(obj["totals"]["reconciliation_error"],0,places=7)
        self.assertAlmostEqual(obj["totals"]["observed_pnl"],
            sum(obj["totals"][k] for k in
                ("delta","gamma","vega","theta","rho","dividend",
                 "approximation_residual","market_basis_change")),places=7)

    def test_reject_bad_http_upload(self):
        for body in ("{}",'{"start_csv":"hi"}'):
            code, out=self.request("POST","/api/explain",body,{"Content-Type":"application/json"})
            self.assertEqual(code,400,out)
        code,_=self.request("POST","/api/wrong","{}",{"Content-Type":"application/json"})
        self.assertEqual(code,404)
        code,_=self.request("POST","/api/explain","{}",{"Content-Type":"text/plain"})
        self.assertEqual(code,415)

    def test_static_assets(self):
        for name in ("/","/risk.js","/risk.css","/risk-first.css","/risk-scenarios.json","/risk-demo.json",
                     "/positions_2026-10-05.csv","/positions_2026-10-06.csv"):
            code, content=self.request("GET",name)
            self.assertEqual(code,200,name)
            self.assertGreater(len(content),30)
        demo=json.loads(self.request("GET","/risk-demo.json")[1])
        self.assertEqual(demo["position_count"],5)
        scenarios=json.loads(self.request("GET","/risk-scenarios.json")[1])["scenarios"]
        self.assertEqual(len(scenarios),4)
        for item in scenarios:
            self.assertAlmostEqual(item["report"]["totals"]["reconciliation_error"],0,places=7)
