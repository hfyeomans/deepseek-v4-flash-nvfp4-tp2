"""Recorded requests must preserve the payload actually sent over HTTP."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import verify


class RequestObservationTest(unittest.TestCase):
    def test_later_tool_turns_do_not_rewrite_prior_request(self):
        wire_requests = []

        def respond(request, timeout):
            wire_requests.append(json.loads(request.data))
            return io.BytesIO(json.dumps({'choices': [{
                'finish_reason': 'stop', 'message': {'role': 'assistant', 'content': 'ok'},
            }]}).encode())

        api = verify.API('http://example.invalid', 'synthetic', 10)
        messages = verify.user('Look up record alpha.')
        tools = [{'type': 'function', 'function': {
            'name': 'lookup_code', 'description': 'Original description',
        }}]
        with patch.object(verify.urllib.request, 'urlopen', respond):
            api.chat(messages, tools=tools)
            messages += [{'role': 'tool', 'tool_call_id': 'example', 'content': 'ABC-123'}]
            tools[0]['function']['description'] = 'Changed in a later call'
            api.chat(messages, tools=tools)

        self.assertNotEqual(wire_requests[0], wire_requests[1])
        self.assertEqual(api.observations[0]['request'], wire_requests[0])
        self.assertEqual(api.observations[1]['request'], wire_requests[1])


class StreamingObservationTest(unittest.TestCase):
    def run_check(self, name, body):
        api = verify.API('http://example.invalid', 'synthetic', 10)
        outgoing = []
        response = io.BytesIO(body)

        def respond(request, timeout):
            outgoing.append(json.loads(request.data))
            return response

        with patch.object(verify.urllib.request, 'urlopen', respond):
            verify.checks(api)[name]()
        self.assertEqual(len(api.observations), 1)
        observation = api.observations[0]
        self.assertEqual(observation['request'], outgoing[0])
        self.assertTrue(response.closed)
        self.assertTrue(observation['closed'])
        return observation

    def test_all_complete_stream_checks_record_the_received_events(self):
        tool_delta = {'tool_calls': [{'index': 0, 'id': 'call-synthetic',
            'type': 'function', 'function': {'name': 'lookup_code',
            'arguments': '{"record":"gamma"}'}}]}
        cases = {
            'streaming': ({'content': 'STREAM-416'}, 'stop'),
            'stream_reasoning': ({'content': '323', 'reasoning': '17 times 19 is 323.'}, 'stop'),
            'stream_tools': (tool_delta, 'tool_calls'),
        }
        for name, (delta, finish) in cases.items():
            with self.subTest(check=name):
                event = {'choices': [{'index': 0, 'delta': delta, 'finish_reason': finish}],
                         'usage': {'completion_tokens': 3}}
                body = ('data: ' + json.dumps(event) + '\n\ndata: [DONE]\n\n').encode()
                observation = self.run_check(name, body)
                self.assertEqual(observation['response']['events'], [event])
                self.assertTrue(observation['response']['done'])
                self.assertEqual(observation['status'], 'complete')

    def test_malformed_stream_preserves_partial_response_and_error(self):
        api = verify.API('http://example.invalid', 'synthetic', 10)
        partial = {'choices': [{'delta': {'reasoning': 'Partial reasoning'}}]}
        body = ('data: ' + json.dumps(partial) + '\n\ndata: {broken\n\n').encode()
        response = io.BytesIO(body)
        with patch.object(verify.urllib.request, 'urlopen', return_value=response):
            with self.assertRaises(json.JSONDecodeError):
                verify.checks(api)['stream_reasoning']()
        self.assertEqual(len(api.observations), 1)
        observation = api.observations[0]
        self.assertEqual(observation['response']['events'], [partial])
        self.assertIn('data: {broken\n', observation['response']['lines'])
        self.assertFalse(observation['response']['done'])
        self.assertEqual(observation['status'], 'error')
        self.assertIn('JSONDecodeError', observation['error'])
        self.assertTrue(response.closed)
        self.assertTrue(observation['closed'])

    def test_missing_done_is_an_error_with_the_partial_events_retained(self):
        api = verify.API('http://example.invalid', 'synthetic', 10)
        event = {'choices': [{'delta': {'content': 'STREAM-416'}, 'finish_reason': 'stop'}],
                 'usage': {'completion_tokens': 3}}
        response = io.BytesIO(('data: ' + json.dumps(event) + '\n\n').encode())
        with patch.object(verify.urllib.request, 'urlopen', return_value=response):
            with self.assertRaises(AssertionError):
                verify.checks(api)['streaming']()
        self.assertEqual(len(api.observations), 1)
        self.assertEqual(api.observations[0]['response']['events'], [event])
        self.assertEqual(api.observations[0]['status'], 'error')

    def test_failed_http_request_records_its_body_and_closes_the_response(self):
        api = verify.API('http://example.invalid', 'synthetic', 10)
        body = io.BytesIO(b'{"error":"synthetic backend failure"}')
        error = verify.urllib.error.HTTPError(api.url, 500, 'Backend failed', {}, body)
        with patch.object(verify.urllib.request, 'urlopen', side_effect=error):
            with self.assertRaises(verify.urllib.error.HTTPError):
                verify.checks(api)['streaming']()
        self.assertEqual(len(api.observations), 1)
        observation = api.observations[0]
        self.assertEqual(observation['status'], 'error')
        self.assertIn('HTTPError', observation['error'])
        self.assertEqual(observation['response']['body'], '{"error":"synthetic backend failure"}')
        self.assertTrue(body.closed)
        self.assertTrue(observation['closed'])

    def test_cli_writes_stream_http_failure_evidence_after_response_close(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'result.json'
            body = '{"error":"synthetic backend failure"}'
            error = verify.urllib.error.HTTPError('http://example.invalid', 500, 'Failed', {},
                                                  io.BytesIO(body.encode()))
            argv = ['verify.py', '--only', 'streaming', '--output', str(output)]
            with patch('sys.argv', argv), \
                    patch.object(verify.urllib.request, 'urlopen', side_effect=error), \
                    contextlib.redirect_stdout(io.StringIO()), \
                    self.assertRaises(SystemExit) as exited:
                verify.main()
            self.assertEqual(exited.exception.code, 1)
            result = json.loads(output.read_text())
            self.assertEqual(result['results'][0]['status'], 'fail')
            self.assertEqual(result['observations'][0]['response']['body'], body)

    def test_server_error_event_cannot_pass_after_valid_content(self):
        api = verify.API('http://example.invalid', 'synthetic', 10)
        events = [
            {'choices': [{'delta': {'content': 'STREAM-416'}, 'finish_reason': 'stop'}],
             'usage': {'completion_tokens': 3}},
            {'error': {'message': 'synthetic stream failure', 'type': 'server_error'}},
        ]
        body = ''.join('data: ' + json.dumps(event) + '\n\n' for event in events)
        response = io.BytesIO((body + 'data: [DONE]\n\n').encode())
        with patch.object(verify.urllib.request, 'urlopen', return_value=response):
            with self.assertRaisesRegex(RuntimeError, 'synthetic stream failure'):
                verify.checks(api)['streaming']()
        self.assertEqual(api.observations[0]['response']['events'], events)
        self.assertEqual(api.observations[0]['status'], 'error')
        self.assertTrue(response.closed)

    def test_cancellation_closes_without_consuming_the_remaining_stream(self):
        api = verify.API('http://example.invalid', 'synthetic', 10)
        first = {'choices': [{'delta': {'content': '1,'}, 'finish_reason': None}]}
        first_line = ('data: ' + json.dumps(first) + '\n').encode()
        stream = io.BytesIO(first_line + b'\ndata: {must not be read}\n\n')
        outgoing = []

        def respond(request, timeout):
            outgoing.append(json.loads(request.data))
            if outgoing[-1].get('stream'):
                return stream
            return io.BytesIO(json.dumps({'choices': [{'finish_reason': 'stop',
                'message': {'role': 'assistant', 'content': 'RECOVERED-832'}}]}).encode())

        with patch.object(verify.urllib.request, 'urlopen', respond):
            verify.checks(api)['cancellation']()
        self.assertEqual(len(api.observations), 2)
        cancelled = api.observations[0]
        self.assertEqual(cancelled['request'], outgoing[0])
        self.assertEqual(cancelled['response']['events'], [first])
        self.assertEqual(cancelled['response']['lines'], [first_line.decode()])
        self.assertEqual(cancelled['status'], 'cancelled')
        self.assertFalse(cancelled['response']['done'])
        self.assertTrue(cancelled['closed'])
        self.assertTrue(stream.closed)
        self.assertEqual(api.observations[1]['request'], outgoing[1])


if __name__ == '__main__':
    unittest.main(verbosity=2)
