import socket
import tempfile
import unittest
from pathlib import Path
from fastapi.testclient import TestClient
from app.engine import Engine
from app.main import create_app


class ApiTests(unittest.TestCase):
    def test_demo_end_to_end(self):
        try:
            probe = socket.socket()
            probe.close()
        except PermissionError:
            self.skipTest('Cet environnement interdit les sockets requis par asyncio/TestClient')
        with tempfile.TemporaryDirectory() as tmp:
            engine=Engine(str(Path(tmp)/'api.sqlite3'))
            app=create_app(engine,interval=10)
            with TestClient(app) as client:
                self.assertEqual(client.get('/api/health').json()['execution'],'paper-only')
                self.assertIn('Démonstration',client.get('/').text)
                self.assertEqual(client.get('/static/app.js').status_code,200)
                self.assertEqual(client.post('/api/control',json={'action':'start'}).status_code,200)
                for _ in range(180): engine.step()
                s=client.get('/api/state').json()
                self.assertTrue(s['trades'])
                self.assertEqual(s['modules']['llm'],'désactivé')
                self.assertEqual(client.post('/api/control',json={'action':'pause'}).json()['mode'],'paused')
                self.assertEqual(client.post('/api/control',json={'action':'stop'}).status_code,200)
                engine.step()
                self.assertFalse(client.get('/api/state').json()['positions'])
                self.assertEqual(client.post('/api/control',json={'action':'real_order'}).status_code,400)
                self.assertEqual(client.post('/api/control',headers={'origin':'https://evil.example'},json={'action':'start'}).status_code,403)
