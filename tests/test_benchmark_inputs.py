"""Verify benchmark prompt identity and cache isolation at the HTTP boundary."""
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import benchmark


class BenchmarkInputsTest(unittest.TestCase):
    def run_benchmark(self, directory, extra_args):
        outgoing = []
        output = directory / 'result.json'

        def respond(request, timeout):
            if request.full_url.endswith('/metrics'):
                return io.BytesIO(b'')
            payload = json.loads(request.data)
            outgoing.append(payload)
            events = [
                {'choices': [{'delta': {'content': 'Synthetic output'}, 'finish_reason': None}]},
                {'choices': [{'delta': {}, 'finish_reason': 'length'}],
                 'usage': {'prompt_tokens': 17, 'completion_tokens': 32}},
            ]
            body = ''.join('data: ' + json.dumps(event) + '\n\n' for event in events)
            return io.BytesIO((body + 'data: [DONE]\n\n').encode())

        args = ['benchmark.py', '--label', 'test', '--tokens', '32', '--repeats', '1',
                '--output', str(output), *extra_args]
        with patch('sys.argv', args), patch.object(benchmark.urllib.request, 'urlopen', respond), \
                patch('sys.stdout', new_callable=io.StringIO):
            benchmark.main()
        return outgoing, json.loads(output.read_text())

    def test_uncached_requests_keep_prompt_bytes_and_use_individual_salts(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            content = 'Repository fixture: café\n\ndef validate(value):\n    return value > 0\n'
            source = directory / 'code.txt'
            source.write_text(content, encoding='utf-8')
            outgoing, result = self.run_benchmark(
                directory, ['--code-prompt-file', str(source), '--cache-mode', 'uncached'])
            self.assertEqual(len(outgoing), 8)
            salts = [payload.get('cache_salt') for payload in outgoing]
            self.assertTrue(all(isinstance(salt, str) and salt for salt in salts))
            self.assertEqual(len(set(salts)), 8)
            self.assertEqual(sum(payload['messages'][0]['content'] == content
                                 for payload in outgoing), 3)
            self.assertEqual(result['prompts']['code'], content)
            self.assertEqual(result['settings']['code_prompt_sha256'],
                             hashlib.sha256(source.read_bytes()).hexdigest())
            self.assertEqual(result['settings']['cache_mode'], 'uncached')
            recorded = result['warmups'] + result['measured'] + result['concurrent']
            self.assertEqual({row['cache_salt'] for row in recorded}, set(salts))
            self.assertEqual(result['concurrent_workloads'], ['prose', 'code'])

    def test_defaults_keep_original_prompts_and_warm_prefix_behavior(self):
        with tempfile.TemporaryDirectory() as temporary:
            outgoing, result = self.run_benchmark(Path(temporary), [])
            self.assertEqual(len(outgoing), 8)
            self.assertTrue(all('cache_salt' not in payload for payload in outgoing))
            self.assertEqual(result['prompts'], benchmark.PROMPTS)
            self.assertEqual(result['settings']['cache_mode'], 'warm-prefix')


if __name__ == '__main__':
    unittest.main(verbosity=2)
