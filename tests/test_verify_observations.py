"""Recorded requests must preserve the payload actually sent over HTTP."""
import io
import json
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


if __name__ == '__main__':
    unittest.main(verbosity=2)
