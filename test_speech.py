import os
import unittest
from unittest.mock import patch, Mock
import requests
from web_app import app, visits

class SpeechTests(unittest.TestCase):
    def setUp(self):
        visits.clear()
        self.client = app.test_client()
    @patch.dict(os.environ, {'ELEVENLABS_API_KEY':'test-secret'})
    @patch('web_app.requests.post')
    def test_audio_and_server_key(self, post):
        post.return_value=Mock(status_code=200,content=b'ID3test')
        r=self.client.post('/api/speech',json={'text':'Hello'})
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.mimetype,'audio/mpeg')
        self.assertEqual(post.call_args.kwargs['headers']['xi-api-key'],'test-secret')
        self.assertNotIn(b'test-secret',r.data)
        self.assertEqual(self.client.post('/api/speech',json={'text':'Hello'},headers={'Origin':'https://elsewhere.example'}).status_code,403)
        self.assertEqual(self.client.post('/api/speech',json={'text':'x'*4001}).status_code,400)
        post.side_effect=requests.RequestException('test-secret')
        r=self.client.post('/api/speech',json={'text':'Hello'})
        self.assertEqual(r.status_code,503)
        self.assertNotIn(b'test-secret',r.data)
        visits['speech'].extend([__import__('time').monotonic()]*10)
        self.assertEqual(self.client.post('/api/speech',json={'text':'Hello'}).status_code,429)
if __name__=='__main__': unittest.main()
