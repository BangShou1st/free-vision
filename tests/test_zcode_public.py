import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen

from free_vision.types import Attempt, VisionResult


class _Upstream(BaseHTTPRequestHandler):
    requests = []
    queue = []
    def log_message(self, *_): pass
    def do_POST(self):
        body = self.rfile.read(int(self.headers.get('Content-Length', '0')))
        type(self).requests.append({'headers': dict(self.headers.items()), 'body': body})
        status, payload = type(self).queue.pop(0) if type(self).queue else (200, {'choices':[{'message':{'content':'ok'}}]})
        raw = json.dumps(payload).encode()
        self.send_response(status); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(raw))); self.end_headers(); self.wfile.write(raw)


class ZCodeGatewayPublicRegressions(unittest.TestCase):
    def setUp(self):
        _Upstream.requests=[]; _Upstream.queue=[]
        self.upstream=ThreadingHTTPServer(('127.0.0.1',0),_Upstream)
        threading.Thread(target=self.upstream.serve_forever,daemon=True).start()
    def tearDown(self):
        self.upstream.shutdown(); self.upstream.server_close()
        if hasattr(self,'gateway'):
            self.gateway.shutdown(); self.gateway.server_close()
    def _vision(self, text='visual evidence'):
        return VisionResult('opencode','mimo-v2.5-free',text,[],[Attempt('mimo-v2.5-free','success')])
    def _start(self, analyzer):
        from free_vision.gateway import create_gateway_server
        self.gateway=create_gateway_server('127.0.0.1',0,f'http://127.0.0.1:{self.upstream.server_port}/v1',analyzer=analyzer)
        threading.Thread(target=self.gateway.serve_forever,daemon=True).start()
        return f'http://127.0.0.1:{self.gateway.server_port}'
    def _payload(self, model='model'):
        return {'model':model,'messages':[{'role':'user','content':[{'type':'text','text':'debug this'},{'type':'image_url','image_url':{'url':'https://example.com/a.png'}}]}],'stream':False}
    def _post(self, base, payload):
        req=Request(base+'/v1/chat/completions',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer original'},method='POST')
        with urlopen(req,timeout=5) as r: return json.loads(r.read())

    def test_native_multimodal_model_keeps_original_image_request(self):
        calls=[]; base=self._start(lambda *a: calls.append(a) or self._vision())
        self._post(base,self._payload('vision-model'))
        self.assertEqual(calls,[])
        self.assertIn('image_url',repr(json.loads(_Upstream.requests[0]['body'])))

    def test_explicit_text_only_rejection_falls_back_and_retries_without_image(self):
        _Upstream.queue=[(400,{'error':{'message':"Model only supports text input; received unsupported content type 'image_url'."}}),(200,{'choices':[{'message':{'content':'retry ok'}}]})]
        calls=[]; base=self._start(lambda *a: calls.append(a) or self._vision('seen'))
        self._post(base,self._payload('text-model'))
        self.assertEqual(len(calls),1); self.assertEqual(len(_Upstream.requests),2)
        self.assertIn('image_url',repr(json.loads(_Upstream.requests[0]['body'])))
        retried=json.loads(_Upstream.requests[1]['body'])
        self.assertNotIn('image_url',repr(retried)); self.assertIn('seen',repr(retried))
        self.assertEqual(_Upstream.requests[1]['headers']['Authorization'],'Bearer original')

    def test_learned_text_model_skips_second_rejected_image_attempt(self):
        _Upstream.queue=[(400,{'error':{'message':"Model only supports text input; received unsupported content type 'image_url'."}}),(200,{'choices':[{'message':{'content':'retry'}}]}),(200,{'choices':[{'message':{'content':'second'}}]})]
        calls=[]; base=self._start(lambda *a: calls.append(a) or self._vision('seen'))
        self._post(base,self._payload('text-model')); self._post(base,self._payload('text-model'))
        self.assertEqual(len(_Upstream.requests),3); self.assertEqual(len(calls),1)
        self.assertNotIn('image_url',repr(json.loads(_Upstream.requests[2]['body'])))


class ZCodeAdapterPublicRegressions(unittest.TestCase):
    def _write(self, root: Path):
        zdir=root/'.zcode'/'v2'; zdir.mkdir(parents=True)
        config=zdir/'config.json'; cache=zdir/'bots-model-cache.v2.json'
        config.write_text(json.dumps({'provider':{'p1':{'enabled':True,'kind':'openai-compatible','options':{'baseURL':'https://up.example/v1','apiKey':'secret'}}}}),encoding='utf-8')
        cache.write_text(json.dumps({'providers':[{'id':'p1','endpoints':{'baseURL':'https://up.example/v1'}}],'lastUsedModel':{'providerId':'p1','modelId':'deepseek-v4-flash-free'},'revision':1}),encoding='utf-8')
        return config,cache

    def test_zcode_install_cli_prints_gateway_setup_next_step(self):
        from free_vision.install import main
        import io

        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as td:
            out, err = io.StringIO(), io.StringIO()
            rc = main(["--target", "zcode", "--dest", str(Path(td) / "skills")], source_root=root, stdout=out, stderr=err)
            self.assertEqual(rc, 0, err.getvalue())
            text = out.getvalue().lower()
            self.assertIn("scripts/zcode.py", text)
            self.assertIn("setup", text)
            self.assertIn("status", text)

    def test_zcode_install_target_and_payload(self):
        from free_vision.install import iter_payload_files, resolve_install_destination
        root=Path(__file__).resolve().parents[1]
        self.assertEqual(resolve_install_destination('zcode','user',home=Path('/home/me')),Path('/home/me/.zcode/skills/free-vision'))
        rel={p.relative_to(root).as_posix() for p in iter_payload_files(root)}
        self.assertIn('scripts/zcode.py',rel); self.assertIn('free_vision/gateway.py',rel)

    def test_detect_connect_status_and_restore_keep_secret_unchanged(self):
        from free_vision.zcode import ZCodeGatewayConfig, connect_zcode_provider, detect_zcode_upstream, restore_zcode_provider, zcode_provider_is_connected
        with tempfile.TemporaryDirectory() as td:
            config_path,cache_path=self._write(Path(td))
            self.assertEqual(detect_zcode_upstream(config_path),'https://up.example/v1')
            cfg=ZCodeGatewayConfig('https://up.example/v1')
            state=connect_zcode_provider(cfg,zcode_config_path=config_path)
            managed=ZCodeGatewayConfig(cfg.upstream_base_url,cfg.host,cfg.port,str(config_path),state.provider_id,state.original_base_url,state.cache_path,state.cache_provider_id,state.cache_original_base_url)
            self.assertTrue(zcode_provider_is_connected(managed))
            saved=json.loads(config_path.read_text()); cached=json.loads(cache_path.read_text())
            self.assertEqual(saved['provider']['p1']['options']['apiKey'],'secret')
            self.assertEqual(saved['provider']['p1']['options']['baseURL'],cfg.gateway_base_url)
            self.assertEqual(cached['providers'][0]['endpoints']['baseURL'],cfg.gateway_base_url)
            self.assertTrue(restore_zcode_provider(managed,zcode_config_path=config_path,provider_id=state.provider_id,original_base_url=state.original_base_url,cache_path=cache_path,cache_provider_id=state.cache_provider_id,cache_original_base_url=state.cache_original_base_url))
            self.assertEqual(json.loads(config_path.read_text())['provider']['p1']['options']['baseURL'],'https://up.example/v1')
            self.assertEqual(json.loads(cache_path.read_text())['providers'][0]['endpoints']['baseURL'],'https://up.example/v1')


if __name__ == '__main__': unittest.main()
