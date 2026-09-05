"""Regression checks for false overlap and repeated-prefix evidence."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import mixed_probe


class MixedProbeTest(unittest.TestCase):
    def run_probe(self, delay, completion_duration):
        calls = []
        prefixes = []

        def fake_long(api, _tokens, prefix=''):
            prefixes.append(prefix)
            time.sleep(0.05)  # Prompt preparation must not count as inference.
            api.chat([{'role': 'user', 'content': 'long'}])
            return {'observed': 'long succeeded'}

        def fake_chat(_api, messages, **_kwargs):
            is_long = messages[0]['content'] == 'long'
            calls.append(('long' if is_long else 'short', time.monotonic()))
            if is_long:
                time.sleep(completion_duration)
            return {'content': mixed_probe.EXPECTED_SHORT_REPLY}

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'result.json'
            argv = ['mixed_probe.py', '--label', 'regression', '--output', str(output),
                    '--delay', str(delay), '--min-overlap', '0.01']
            with patch.object(sys, 'argv', argv), \
                 patch.object(mixed_probe, 'long_context', fake_long), \
                 patch.object(mixed_probe.API, 'chat', fake_chat), \
                 contextlib.redirect_stdout(io.StringIO()), \
                 self.assertRaises(SystemExit) as exit_result:
                mixed_probe.main()
            return json.loads(output.read_text()), calls, prefixes, exit_result.exception.code

    def test_short_starts_after_completion_call_despite_slow_preparation(self):
        result, calls, _prefixes, code = self.run_probe(0, 0.05)
        self.assertEqual([name for name, _stamp in calls], ['long', 'short'])
        self.assertEqual(result['status'], 'pass')
        self.assertEqual(code, 0)

    def test_completed_long_request_cannot_pass_overlap(self):
        result, calls, _prefixes, code = self.run_probe(0.03, 0.005)
        self.assertEqual([name for name, _stamp in calls], ['long'])
        self.assertEqual(result['results'][1]['status'], 'inconclusive')
        self.assertNotEqual(code, 0)

    def test_each_run_gets_a_fresh_recorded_prefix(self):
        first, _calls, first_prefixes, _code = self.run_probe(0, 0.03)
        second, _calls, second_prefixes, _code = self.run_probe(0, 0.03)
        self.assertTrue(first_prefixes[0])
        self.assertNotEqual(first_prefixes[0], second_prefixes[0])
        self.assertEqual(first['settings']['unique_prompt_prefix'], first_prefixes[0])
        self.assertEqual(second['settings']['unique_prompt_prefix'], second_prefixes[0])


class MixedToolProbeTest(unittest.TestCase):
    def run_tool_probe(self, returned_code):
        payloads = []

        def fake_long(api, _tokens, prefix=''):
            api.chat([{'role': 'user', 'content': 'long'}])
            return {'observed': prefix}

        def fake_request(_api, _path, payload=None):
            payloads.append(json.loads(json.dumps(payload)))
            if payload['messages'][0]['content'] == 'long':
                time.sleep(0.1)
                message = {'role': 'assistant', 'content': 'long result'}
            elif payload.get('tool_choice') == 'auto':
                message = {'role': 'assistant', 'content': None, 'tool_calls': [{
                    'id': 'synthetic-call', 'type': 'function',
                    'function': {'name': 'lookup_code', 'arguments': '{"record":"alpha"}'}}]}
            else:
                message = {'role': 'assistant', 'content': returned_code}
            return io.BytesIO(json.dumps({'choices': [{'message': message,
                'finish_reason': 'stop'}], 'usage': {'prompt_tokens': 12,
                'completion_tokens': 6}}).encode())

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'result.json'
            argv = ['mixed_probe.py', '--label', 'tool-regression', '--output', str(output),
                    '--delay', '0', '--min-overlap', '0.01', '--short-check', 'tools_auto']
            with patch.object(sys, 'argv', argv), \
                 patch.object(mixed_probe, 'long_context', fake_long), \
                 patch.object(mixed_probe.API, 'request', fake_request), \
                 contextlib.redirect_stdout(io.StringIO()), \
                 self.assertRaises(SystemExit) as exit_result:
                mixed_probe.main()
            return json.loads(output.read_text()), payloads, exit_result.exception.code

    def test_both_tool_calls_are_measured_and_recorded_during_long_request(self):
        result, payloads, code = self.run_tool_probe('VIOLET-937')
        self.assertEqual(code, 0)
        self.assertEqual(result['status'], 'pass')
        self.assertEqual(result['settings']['short_check'], 'tools_auto')
        self.assertEqual(len(payloads), 3)
        self.assertEqual(payloads[1]['tool_choice'], 'auto')
        self.assertEqual(payloads[2]['tool_choice'], 'none')
        self.assertEqual(payloads[2]['messages'][2]['tool_call_id'], 'synthetic-call')
        self.assertEqual(len(result['observations']['short']), 2)
        self.assertEqual(result['observations']['short'][0]['request'], payloads[1])
        self.assertEqual(result['observations']['short'][1]['request'], payloads[2])
        self.assertGreater(result['short_finished_before_long_seconds'], 0.01)

    def test_wrong_tool_result_cannot_pass_overlap(self):
        result, _payloads, code = self.run_tool_probe('WRONG')
        self.assertEqual(code, 1)
        self.assertEqual(result['status'], 'fail')
        self.assertEqual(result['results'][1]['status'], 'fail')
        self.assertIn('WRONG', result['results'][1]['error'])


if __name__ == '__main__':
    unittest.main()
