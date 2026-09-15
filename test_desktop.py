import importlib
import os
import sys
import tempfile
import threading
import unittest
from unittest.mock import MagicMock, patch

class DesktopTests(unittest.TestCase):
    def test_packaged_paths_are_per_user_and_settings_have_no_developer_identity(self):
        import runtime_paths
        with patch.object(sys, 'frozen', True, create=True), patch.dict(os.environ, {}, clear=True):
            self.assertIn('Library/Application Support/Swift', str(runtime_paths.data_dir()))
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {'SWIFT_DATA_DIR': folder}):
            self.assertEqual(runtime_paths.load_settings()['user_first_name'], '')
            self.assertEqual(str(runtime_paths.settings_path()), folder + '/settings.json')

    def test_cancelled_speech_never_calls_provider_or_player(self):
        from transcription import speech
        cancel = threading.Event(); cancel.set()
        with patch.object(speech.requests, 'post') as post, patch.object(speech.subprocess, 'Popen') as popen:
            self.assertFalse(speech.speech('hello', cancel))
            post.assert_not_called(); popen.assert_not_called()

    def test_native_speech_provider_failure_uses_mac_voice_without_exposing_key(self):
        from transcription import speech
        with patch.dict(os.environ, {'ELEVENLABS_API_KEY': 'test-only-key'}), patch.object(speech, '_retry_after', 0), patch.object(speech.requests, 'post') as post, patch.object(speech, '_play', return_value=True) as play:
            post.return_value.status_code = 402
            self.assertTrue(speech.speech('hello'))
            self.assertEqual(play.call_args.args[0], ['/usr/bin/say', '--', 'hello'])
            self.assertEqual(post.call_args.kwargs['headers'], {'xi-api-key': 'test-only-key'})

    def test_general_mac_action_does_not_require_icloud(self):
        import tools
        with patch('react.applescript_loop', return_value={'success':True, 'message':'Done'}) as native:
            self.assertTrue(tools._execute_system_command('Open Calculator')['success'])
            native.assert_called_once()
            self.assertNotIn('location', native.call_args.kwargs['system_context'].lower())

    def test_cancelled_agent_never_calls_tools_or_model(self):
        import agent
        cancel = threading.Event(); cancel.set()
        with patch.object(agent, 'execute_tool') as execute, patch.object(agent, 'generate') as generate:
            self.assertEqual(agent.run('Open Calculator', {}, cancel), ('', True))
            execute.assert_not_called(); generate.assert_not_called()

if __name__ == '__main__':
    unittest.main()

class LocalMemoryTests(unittest.TestCase):
    def test_memory_is_searchable_deduplicated_and_isolated(self):
        import memory
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            with patch.dict(os.environ, {'SWIFT_DATA_DIR': first}):
                memory.save_facts(['User likes jazz', 'User likes jazz', 'User prefers tea'])
                self.assertIn('User likes jazz', memory.load_context('jazz'))
                self.assertNotIn('tea', memory.load_context('jazz'))
                with memory._connect() as connection:
                    self.assertEqual(connection.execute('SELECT count(*) FROM facts').fetchone()[0], 2)
            with patch.dict(os.environ, {'SWIFT_DATA_DIR': second}):
                self.assertEqual(memory.load_context('jazz'), '')
