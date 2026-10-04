import json
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
from market_state_filter.api import make_server

class ApiTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.token='t'*40
        self.server=make_server(self.temp.name,self.token,0)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.base=f'http://127.0.0.1:{self.server.server_port}'
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join();self.temp.cleanup()
    def request(self,path,body=None,token=None):
        headers={'Authorization':'Bearer '+(token or self.token),'Content-Type':'application/json'}
        request=urllib.request.Request(self.base+path,data=json.dumps(body).encode() if body is not None else None,headers=headers)
        with urllib.request.urlopen(request,timeout=3) as response:return json.load(response)
    def test_authentication_required(self):
        with self.assertRaises(urllib.error.HTTPError) as context:self.request('/api/tools',token='wrong')
        self.assertEqual(context.exception.code,401)
    def test_registration_never_executes_or_promotes(self):
        response=self.request('/api/tasks',{'horizon':24,'seed':7})
        self.assertEqual(response['status'],'REGISTERED');self.assertFalse(response['executed'])
        task=self.request('/api/tasks')['tasks'][0]
        self.assertEqual(task['spec']['promotion'],'NONE')
    def test_shell_and_unknown_fields_rejected(self):
        with self.assertRaises(urllib.error.HTTPError) as context:self.request('/api/tasks',{'command':'whoami'})
        self.assertEqual(context.exception.code,400)
        self.assertEqual(self.request('/api/tasks')['tasks'],[])
    def test_weak_token_rejected(self):
        with self.assertRaises(ValueError):make_server(self.temp.name,'short',0)

if __name__=='__main__':unittest.main()
