#!/usr/bin/env python3
"""Matched fixed-output-length API benchmark with explicit cache conditions."""
import argparse
import concurrent.futures
import hashlib
import json
import os
import statistics
import time
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path


PROMPTS = {
    'prose': 'Explain how photosynthesis works, with clear sections for light absorption, water splitting, carbon fixation, and environmental limits. Use complete paragraphs.',
    'code': 'Write a complete Python module that reads a CSV file, validates required name and age columns, rejects invalid ages, and emits a JSON summary. Include useful error handling and examples.',
    'reasoning': 'Compare merge sort and quicksort for a database sorting one million rows under a strict memory limit. Analyze time, memory, stability, and input distributions. Explain the tradeoffs carefully.',
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default='http://127.0.0.1:8000')
    parser.add_argument('--model', default='dsv4-nvfp4')
    parser.add_argument('--label', required=True)
    parser.add_argument('--tokens', type=int, default=256)
    parser.add_argument('--repeats', type=int, default=2)
    parser.add_argument('--code-prompt-file', type=Path,
                        help='Complete UTF-8 user prompt replacing only the code workload')
    parser.add_argument('--cache-mode', choices=('warm-prefix', 'uncached'), default='warm-prefix',
                        help='Uncached assigns a fresh cache salt to every request, including warmups')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    if args.tokens < 32 or args.repeats < 1:
        parser.error('Use at least 32 tokens and one measured repeat')
    prompts = dict(PROMPTS)
    if args.code_prompt_file:
        try:
            prompts['code'] = args.code_prompt_file.read_bytes().decode('utf-8')
        except (OSError, UnicodeError) as error:
            parser.error(f'Cannot read code prompt: {error}')
        if not prompts['code'].strip():
            parser.error('Code prompt must not be empty')
    headers = {'Content-Type': 'application/json'}
    if os.environ.get('API_KEY'):
        headers['Authorization'] = 'Bearer ' + os.environ['API_KEY']

    def generate(name):
        payload = dict(model=args.model, messages=[{'role': 'user', 'content': prompts[name]}],
                       temperature=0, seed=42, min_tokens=args.tokens,
                       max_tokens=args.tokens, stream=True,
                       chat_template_kwargs={'thinking': name == 'reasoning'},
                       reasoning_effort='low', stream_options={'include_usage': True})
        cache_salt = uuid.uuid4().hex if args.cache_mode == 'uncached' else None
        if cache_salt is not None:
            payload['cache_salt'] = cache_salt
        request = urllib.request.Request(args.base_url + '/v1/chat/completions',
                                         data=json.dumps(payload).encode(), headers=headers)
        start = time.monotonic()
        first_output, usage, finish, done = None, None, None, False
        with urllib.request.urlopen(request, timeout=300) as response:
            for raw in response:
                line = raw.decode().strip()
                if line == 'data: [DONE]':
                    done = True
                    break
                if not line.startswith('data: '):
                    continue
                event = json.loads(line[6:])
                if 'error' in event:
                    raise RuntimeError(f"Benchmark stream error: {event['error']}")
                usage = event.get('usage') or usage
                for choice in event.get('choices', []):
                    delta = choice.get('delta', {})
                    if first_output is None and any(delta.get(key) for key in ('content', 'reasoning', 'reasoning_content')):
                        first_output = time.monotonic() - start
                    finish = choice.get('finish_reason') or finish
        elapsed = time.monotonic() - start
        if (not done or not usage or usage['completion_tokens'] != args.tokens
                or first_output is None or finish != 'length'):
            raise RuntimeError(
                f'Incomplete benchmark: done={done}, usage={usage}, '
                f'first={first_output}, finish={finish}')
        return dict(workload=name, elapsed_seconds=elapsed,
                    cache_salt=cache_salt,
                    first_output_seconds=first_output, usage=usage, finish_reason=finish,
                    output_tokens_per_second=usage['completion_tokens'] / elapsed)

    def speculation_metrics():
        request = urllib.request.Request(args.base_url + '/metrics', headers=headers)
        with urllib.request.urlopen(request, timeout=10) as response:
            lines = response.read().decode().splitlines()
        return [line for line in lines if 'spec_decode' in line and not line.startswith('#')]

    before = speculation_metrics()
    warmups = []
    for name in prompts:
        warmups.append(generate(name))
        print(json.dumps({'warmup_complete': name}), flush=True)
    rows = []
    for repeat in range(args.repeats):
        for name in prompts:
            result = generate(name)
            result['repeat'] = repeat
            rows.append(result)
            print(json.dumps(result), flush=True)
    started = time.monotonic()
    concurrent_workloads = ('prose', 'code')
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        concurrent_rows = list(pool.map(generate, concurrent_workloads))
    concurrent_elapsed = time.monotonic() - started
    result = dict(recorded_at=datetime.now(timezone.utc).isoformat(), label=args.label,
                  settings={'temperature': 0, 'seed': 42, 'output_tokens': args.tokens,
                            'repeats': args.repeats, 'cache_mode': args.cache_mode,
                            'cache': ('one warmup per exact prompt' if args.cache_mode == 'warm-prefix'
                                      else 'fresh cache salt per request, including warmups and concurrency'),
                            'code_prompt_sha256': hashlib.sha256(prompts['code'].encode('utf-8')).hexdigest()},
                  prompts=prompts, warmups=warmups, measured=rows, concurrent=concurrent_rows,
                  concurrent_workloads=list(concurrent_workloads),
                  concurrent_elapsed_seconds=concurrent_elapsed,
                  aggregate_output_tokens_per_second=sum(row['usage']['completion_tokens'] for row in concurrent_rows) / concurrent_elapsed,
                  median_output_tokens_per_second={name: statistics.median(
                      row['output_tokens_per_second'] for row in rows if row['workload'] == name) for name in prompts},
                  speculation_metrics_before=before, speculation_metrics_after=speculation_metrics(),
                  speculation_metrics_scope='Entire run: warmups, all workloads and the concurrent pair')
    with open(args.output, 'w') as output:
        json.dump(result, output, indent=2)
        output.write('\n')
    print(json.dumps({'summary': result['median_output_tokens_per_second'],
                      'concurrency_two_aggregate': result['aggregate_output_tokens_per_second']}), flush=True)


if __name__ == '__main__':
    main()
