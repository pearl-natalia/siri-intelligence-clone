"""Run with: python -m unittest test_web -v (no live credentials needed)."""
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from google.genai import types
import web_app
import web_assistant as adapter

class WebTests(unittest.TestCase):
    def setUp(self):
        self.client = web_app.app.test_client()
        web_app.visits.clear()
        self.env = patch.dict(os.environ, {"GEMINI_API_KEY": "", "WEATHER_API": ""})
        self.env.start()
    def tearDown(self):
        self.env.stop()
    def test_setup_and_secret_files(self):
        self.assertFalse(self.client.get('/api/status').json['ai_configured'])
        for path in ('/.env','/settings.json','/model.py','/.git/config','/static/../model.py'):
            self.assertEqual(self.client.get(path).status_code,404)
        with self.client.get('/') as response:
            self.assertIn('Content-Security-Policy', response.headers)
    def test_local_time_and_missing_key(self):
        result = self.client.post('/api/chat',json={'message':'What time is it?','timezone':'America/Toronto'})
        self.assertEqual(result.json['mode'],'local')
        self.assertRegex(result.json['reply'],r'E[DS]T')
        result = self.client.post('/api/chat',json={'message':'Hello'})
        self.assertEqual(result.json['mode'],'setup')
    def test_validation_and_origin(self):
        for data in ([],{}, {'message':'x'*4001}, {'message':'hi','history':[{'role':'system','text':'bad'}]}):
            self.assertEqual(self.client.post('/api/chat',json=data).status_code,400)
        self.assertEqual(self.client.post('/api/chat',json={'message':'hello'},headers={'Origin':'https://attacker.test'}).status_code,403)
    def test_tools_never_execute_desktop_commands(self):
        with patch('subprocess.run', side_effect=AssertionError('Desktop execution')):
            self.assertFalse(adapter.execute('execute_system_command',{'task':'anything'},'UTC')['success'])
            self.assertFalse(adapter.execute('get_weather',{'city':'current'},'UTC')['success'])
            self.assertIn('open.spotify.com',adapter.execute('control_music',{'action':'play','query':'jazz'},'UTC')['link']['url'])
            self.assertFalse(adapter.execute('browser',{'action':'open_url','url':'javascript:alert(1)'},'UTC')['success'])
    def test_no_secret_in_errors(self):
        with patch('web_app.reply',side_effect=RuntimeError('secret=private')):
            result=self.client.post('/api/chat',json={'message':'hello'})
            self.assertEqual(result.status_code,503)
            self.assertNotIn('private',result.text)
        with patch.dict(os.environ,{'WEATHER_API':'private'}), patch.object(adapter,'_get_weather',return_value={'success':False,'message':'url?key=private'}):
            self.assertNotIn('private',str(adapter.execute('get_weather',{'city':'Toronto'},'UTC')))
    def test_gemini_history_and_tool_roundtrip(self):
        responses=[SimpleNamespace(candidates=[SimpleNamespace(content=types.Content(role='model',parts=[types.Part(function_call=types.FunctionCall(name='get_time',args={}))]))]),SimpleNamespace(candidates=[SimpleNamespace(content=types.Content(role='model',parts=[types.Part.from_text(text='Here is the time.')]))])]
        with patch.dict(os.environ,{'GEMINI_API_KEY':'test'}), patch.object(adapter.genai,'Client') as factory:
            client=factory.return_value.__enter__.return_value
            client.models.generate_content.side_effect=responses
            answer=adapter.reply('Tell me the current date', [{'role':'user','text':'Hi'},{'role':'model','text':'Hello'}], 'UTC')
            self.assertEqual(answer['reply'],'Here is the time.')
            self.assertEqual(client.models.generate_content.call_count,2)
            contents=client.models.generate_content.call_args.kwargs['contents']
            self.assertEqual(contents[0].parts[0].text,'Hi')
            self.assertIsNotNone(contents[-1].parts[0].function_response)
        self.assertFalse(hasattr(web_app,'conversation_history'))
    def test_rate_limit(self):
        for _ in range(30):
            self.client.post('/api/chat',json={'message':'time'})
        self.assertEqual(self.client.post('/api/chat',json={'message':'time'}).status_code,429)

    def test_native_request_returns_download_without_executing_or_claiming_success(self):
        response = SimpleNamespace(candidates=[SimpleNamespace(content=types.Content(role='model', parts=[types.Part(function_call=types.FunctionCall(name='use_mac_app', args={}))]))])
        with patch.dict(os.environ, {'GEMINI_API_KEY': 'test'}), patch.object(adapter.genai, 'Client') as factory, patch('subprocess.run', side_effect=AssertionError('Desktop execution')):
            model = factory.return_value.__enter__.return_value.models.generate_content
            model.return_value = response
            answer = self.client.post('/api/chat', json={'message': 'Open Calculator on my Mac'}).json
            self.assertEqual(answer['mode'], 'mac_required')
            self.assertEqual(answer['reply'], adapter.MAC_REQUIRED_MESSAGE)
            self.assertEqual(answer['links'][0]['kind'], 'mac_download')
            self.assertEqual(answer['links'][0]['url'], self.client.get('/download/mac').headers['Location'])
            self.assertEqual(model.call_count, 1)

    def test_normal_answer_does_not_offer_mac_download(self):
        response = SimpleNamespace(candidates=[SimpleNamespace(content=types.Content(role='model', parts=[types.Part.from_text(text='Here is a draft of your message.')]))])
        with patch.dict(os.environ, {'GEMINI_API_KEY': 'test'}), patch.object(adapter.genai, 'Client') as factory:
            factory.return_value.__enter__.return_value.models.generate_content.return_value = response
            answer = adapter.reply('Draft a message', [], 'UTC')
            self.assertEqual(answer['mode'], 'live')
            self.assertEqual(answer['links'], [])

if __name__ == '__main__': unittest.main()
