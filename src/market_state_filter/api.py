"""Authenticated deterministic tools for an AI client. Registration != execution."""
from contextlib import closing
import hashlib
import hmac
import json
import os
from pathlib import Path
import sqlite3
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

TOOLS=[{"name":"get_research_report","method":"GET","path":"/api/report"},
       {"name":"get_tasks","method":"GET","path":"/api/tasks"},
       {"name":"register_research_task","method":"POST","path":"/api/tasks",
        "input":{"horizon":"integer 1..96","seed":"integer 0..2147483647"},
        "effect":"register only; no execution or model promotion"}]

def make_server(output, token, port=8765):
    if len(token)<32:
        raise ValueError("Set MARKET_STATE_FILTER_API_TOKEN to a random token of at least 32 characters")
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=True)
    db=output/'tasks.sqlite3'
    with closing(sqlite3.connect(db)) as c:
        c.execute('CREATE TABLE IF NOT EXISTS tasks (id TEXT PRIMARY KEY, created REAL, spec TEXT, status TEXT)')
        c.commit()
    token_hash=hashlib.sha256(token.encode()).digest()
    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup();self.connection.settimeout(5)
        def log_message(self,*args):
            pass  # never log headers, tokens or arbitrary request text
        def send_json(self,status,payload):
            raw=json.dumps(payload,ensure_ascii=False).encode()
            self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8')
            self.send_header('Content-Length',str(len(raw)));self.send_header('Cache-Control','no-store')
            self.end_headers();self.wfile.write(raw)
        def authorized(self):
            value=self.headers.get('Authorization','')
            candidate=value[7:] if value.startswith('Bearer ') else ''
            if not hmac.compare_digest(hashlib.sha256(candidate.encode()).digest(),token_hash):
                self.send_json(401,{"error":"unauthorized"});return False
            return True
        def do_GET(self):
            if not self.authorized():return
            if self.path=='/api/tools':self.send_json(200,{"tools":TOOLS})
            elif self.path=='/api/report':
                p=output/'report.json'
                if not p.is_file():self.send_json(404,{"error":"report_not_available"})
                else:self.send_json(200,json.loads(p.read_text(encoding='utf-8')))
            elif self.path=='/api/tasks':
                with closing(sqlite3.connect(db)) as c:
                    rows=c.execute('SELECT id, created, spec, status FROM tasks ORDER BY created DESC LIMIT 100').fetchall()
                self.send_json(200,{"tasks":[{"id":r[0],"created":r[1],"spec":json.loads(r[2]),"status":r[3]} for r in rows]})
            else:self.send_json(404,{"error":"unknown_tool"})
        def do_POST(self):
            if not self.authorized():return
            if self.path!='/api/tasks':self.send_json(404,{"error":"unknown_tool"});return
            try:
                if self.headers.get('Content-Type','').split(';')[0]!='application/json':raise ValueError()
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=4096 or self.headers.get('Transfer-Encoding'):raise ValueError()
                body=json.loads(self.rfile.read(size))
                if not isinstance(body,dict) or set(body)-{'horizon','seed'}:raise ValueError()
                horizon=body.get('horizon',24);seed=body.get('seed',7)
                if type(horizon)!=int or not 1<=horizon<=96 or type(seed)!=int or not 0<=seed<=2147483647:raise ValueError()
            except (ValueError,UnicodeError):self.send_json(400,{"error":"invalid_task_spec"});return
            spec={"kind":"line_quality_research","horizon":horizon,"seed":seed,"promotion":"NONE"}
            identity=str(uuid.uuid4())
            with closing(sqlite3.connect(db)) as c:
                c.execute('INSERT INTO tasks VALUES (?,?,?,?)',(identity,time.time(),json.dumps(spec),'REGISTERED'))
                c.commit()
            self.send_json(201,{"task_id":identity,"status":"REGISTERED","executed":False})
    return ThreadingHTTPServer(('127.0.0.1',port),Handler)

def serve(output,port):
    server=make_server(output,os.environ.get('MARKET_STATE_FILTER_API_TOKEN',''),port)
    print(f"Research tools at http://127.0.0.1:{server.server_port}; authenticated; task registration only")
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
