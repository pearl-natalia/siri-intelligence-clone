"""Private cross-chat memory, tested without production accounts or secrets."""
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from google.genai import types
import test_accounts
from web_memory import UserMemory
import web_assistant as adapter


def response(text=None, tool=None, args=None):
    part = types.Part(function_call=types.FunctionCall(name=tool, args=args or {})) if tool else types.Part.from_text(text=text)
    return SimpleNamespace(candidates=[SimpleNamespace(content=types.Content(role='model', parts=[part]))])


class MemoryTests(unittest.TestCase):
    setUp = test_accounts.AccountTests.setUp
    tearDown = test_accounts.AccountTests.tearDown
    request = test_accounts.AccountTests.request
    login_fixture = test_accounts.AccountTests.login_fixture

    def test_fact_survives_new_chat_and_new_session_but_not_another_user(self):
        csrf, _ = self.login_fixture()
        with patch.dict(os.environ, {'GEMINI_API_KEY': 'test'}), patch.object(adapter.genai, 'Client') as factory:
            model = factory.return_value.__enter__.return_value.models.generate_content
            model.side_effect = [response(tool='remember_fact', args={'topic':'music preference', 'fact':'Prefers jazz', 'source_quote':'I prefer jazz', 'user_id':'bob'}), response(text="I'll remember that you prefer jazz.")]
            saved = self.request('POST', '/api/chat', csrf=csrf, json={'message':'I prefer jazz', 'user_id':'bob'}).json
            first_chat = saved['conversation']['id']
            self.assertEqual(self.store.list_memories('alice')[0]['fact'], 'Prefers jazz')
            csrf, _ = self.login_fixture()
            model.side_effect = [response(text='You prefer jazz.')]
            new_chat = self.request('POST', '/api/chat', csrf=csrf, json={'message':'What music do I like?'}).json
            self.assertNotEqual(new_chat['conversation']['id'], first_chat)
            self.assertIn('Prefers jazz', model.call_args.kwargs['config'].system_instruction)
            csrf, _ = self.login_fixture('bob')
            model.side_effect = [response(text="I don't know yet.")]
            self.request('POST', '/api/chat', csrf=csrf, json={'message':'What music do I like?'})
            self.assertNotIn('Prefers jazz', model.call_args.kwargs['config'].system_instruction)
            self.assertEqual(self.request('GET', '/api/memory').json['facts'], [])

    def test_guest_cannot_read_write_or_spoof_saved_memory(self):
        self.assertEqual(self.request('GET', '/api/memory').status_code, 401)
        self.assertEqual(self.request('PATCH', '/api/memory', json={'enabled':True}).status_code, 401)
        self.assertEqual(self.request('DELETE', '/api/memory/arbitrary').status_code, 401)
        result = adapter.execute('remember_fact', {'topic':'music','fact':'jazz','source_quote':'jazz','user_id':'alice'}, 'UTC')
        self.assertFalse(result['success'])

    def test_pause_stops_reading_and_writing_and_survives_login(self):
        csrf, _ = self.login_fixture()
        memory = UserMemory(self.store, 'alice', 'I prefer jazz')
        args = {'topic':'music', 'fact':'Prefers jazz', 'source_quote':'I prefer jazz'}
        self.assertTrue(memory.remember(args)['success'])
        self.assertEqual(self.request('PATCH', '/api/memory', csrf=csrf, json={'enabled':False}).status_code, 200)
        self.assertEqual(memory.context(), {'enabled':False,'facts':[]})
        self.assertFalse(memory.remember(args)['success'])
        self.login_fixture()
        panel = self.request('GET', '/api/memory').json
        self.assertFalse(panel['enabled'])
        self.assertEqual(len(panel['facts']), 1)
        self.store.set_memory_enabled('alice', True)
        self.assertEqual(memory.context()['facts'][0]['fact'], 'Prefers jazz')

    def test_review_and_delete_are_scoped_and_csrf_protected(self):
        csrf, _ = self.login_fixture()
        fact = self.store.remember('alice', 'music', 'Prefers jazz')
        path = '/api/memory/' + fact['id']
        self.assertEqual(self.request('DELETE', path).status_code, 403)
        self.assertEqual(self.request('PATCH', '/api/memory', json={'enabled':False}).status_code, 403)
        self.assertEqual(self.request('PATCH', '/api/memory', csrf=csrf, json={'enabled':'yes'}).status_code, 400)
        bob_csrf, _ = self.login_fixture('bob')
        self.assertEqual(self.request('DELETE', path, csrf=bob_csrf).status_code, 404)
        self.assertEqual(len(self.store.list_memories('alice')), 1)
        self.login_fixture('alice')
        self.assertEqual(self.request('DELETE', path, csrf=csrf).status_code, 200)
        self.assertEqual(self.request('GET', '/api/memory').json['facts'], [])

    def test_quotes_must_come_from_current_user_message_and_corrections_replace(self):
        self.login_fixture()
        memory = UserMemory(self.store, 'alice', 'I prefer jazz')
        args = {'topic':' Music preference ', 'fact':'Prefers jazz', 'source_quote':'The assistant suggested jazz'}
        self.assertFalse(memory.remember(args)['success'])
        args['source_quote'] = 'I prefer jazz'
        first = memory.remember(args)
        self.assertTrue(first['success'])
        update = UserMemory(self.store, 'alice', 'Actually I prefer classical now')
        changed = update.remember({'topic':'music preference','fact':'Prefers classical','source_quote':'I prefer classical'})
        self.assertEqual(first['id'], changed['id'])
        self.assertEqual(len(self.store.list_memories('alice')), 1)
        self.assertEqual(self.store.list_memories('alice')[0]['fact'], 'Prefers classical')

    def test_forget_tool_cannot_target_another_owner_or_reuse_old_instructions(self):
        self.login_fixture()
        self.login_fixture('bob')
        fact = self.store.remember('alice','music','Prefers jazz')
        request = 'Forget my music preference'
        bob = UserMemory(self.store,'bob',request)
        self.assertFalse(bob.forget({'id':fact['id'],'source_quote':request})['success'])
        alice = UserMemory(self.store,'alice',request)
        self.assertFalse(alice.forget({'id':fact['id'],'source_quote':'some old request'})['success'])
        self.assertTrue(alice.forget({'id':fact['id'],'source_quote':request})['success'])
        self.assertEqual(alice.context()['facts'], [])

    def test_memory_quota_allows_corrections_and_is_account_scoped(self):
        self.login_fixture()
        self.login_fixture('bob')
        for i in range(50):
            self.assertTrue(self.store.remember('alice',f'topic {i}',f'Fact {i}')['success'])
        self.assertFalse(self.store.remember('alice','extra','Another fact')['success'])
        self.assertTrue(self.store.remember('alice','topic 0','Corrected fact')['success'])
        self.assertTrue(self.store.remember('bob','extra','Independent fact')['success'])


if __name__ == '__main__':
    unittest.main()
