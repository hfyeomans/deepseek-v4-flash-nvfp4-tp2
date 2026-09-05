#!/usr/bin/env python3
"""Check short-request responsiveness during a measured long-context retrieval."""
import argparse
import concurrent.futures
import json
import threading
import time
import uuid
from datetime import datetime, timezone

from verify import API, checks, exact, long_context, user

DEFAULT_BASE_URL = 'http://127.0.0.1:8000'
DEFAULT_MODEL = 'dsv4-nvfp4'
DEFAULT_PROMPT_TOKENS = 999000
DEFAULT_DELAY_SECONDS = 30
DEFAULT_LONG_TIMEOUT_SECONDS = 1800
DEFAULT_SHORT_TIMEOUT_SECONDS = 180
DEFAULT_MIN_OVERLAP_SECONDS = 1
DEFAULT_SHORT_CHECK = 'reply'
EXPECTED_SHORT_REPLY = 'CONCURRENT-947'


class CompletionObservedAPI(API):
    """Observe completion calls separately from prompt preparation/tokenization."""
    def __init__(self, url, model, timeout):
        super().__init__(url, model, timeout)
        self.started_or_finished = threading.Event()
        self.completion_started = None
        self.completion_finished = None

    def chat(self, messages, **kwargs):
        self.completion_started = time.monotonic()
        self.started_or_finished.set()
        try:
            return super().chat(messages, **kwargs)
        finally:
            self.completion_finished = time.monotonic()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default=DEFAULT_BASE_URL)
    parser.add_argument('--model', default=DEFAULT_MODEL)
    parser.add_argument('--prompt-tokens', type=int, default=DEFAULT_PROMPT_TOKENS)
    parser.add_argument('--delay', type=float, default=DEFAULT_DELAY_SECONDS)
    parser.add_argument('--long-timeout', type=float, default=DEFAULT_LONG_TIMEOUT_SECONDS)
    parser.add_argument('--short-timeout', type=float, default=DEFAULT_SHORT_TIMEOUT_SECONDS)
    parser.add_argument('--min-overlap', type=float, default=DEFAULT_MIN_OVERLAP_SECONDS)
    parser.add_argument('--short-check', choices=('reply', 'tools_auto'),
                        default=DEFAULT_SHORT_CHECK,
                        help='A tiny exact reply or the checked two-call automatic tool round trip')
    parser.add_argument('--label', required=True)
    parser.add_argument('--output', required=True, help='Raw local evidence, including synthetic prompts')
    args = parser.parse_args()
    if args.prompt_tokens < 1024 or min(args.delay, args.min_overlap) < 0:
        parser.error('Use at least 1024 prompt tokens and nonnegative delay/overlap.')
    if min(args.long_timeout, args.short_timeout) <= 0:
        parser.error('Timeouts must be positive.')

    long_api = CompletionObservedAPI(args.base_url, args.model, args.long_timeout)
    short_api = API(args.base_url, args.model, args.short_timeout)
    prefix = f'Independent probe {uuid.uuid4().hex}.\n'
    origin = time.monotonic()

    def measured(name, action):
        started = time.monotonic()
        try:
            result = {'check': name, 'status': 'pass', 'detail': action()}
        except Exception as error:
            result = {'check': name, 'status': 'fail',
                      'error': f'{type(error).__name__}: {error}'}
        result.update(started_seconds=started - origin,
                      finished_seconds=time.monotonic() - origin,
                      elapsed_seconds=time.monotonic() - started)
        print(json.dumps(result), flush=True)
        return result

    def short_request():
        message = short_api.chat(user('Reply with exactly: ' + EXPECTED_SHORT_REPLY),
                                 max_tokens=64)
        exact(message, EXPECTED_SHORT_REPLY)
        return {'observed': message['content']}

    def long_request():
        try:
            return measured('long_context',
                            lambda: long_context(long_api, args.prompt_tokens, prefix=prefix))
        finally:
            long_api.started_or_finished.set()

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        long_future = pool.submit(long_request)
        long_api.started_or_finished.wait(args.long_timeout)
        if long_api.completion_started is not None:
            time.sleep(args.delay)
        if long_api.completion_started is None or long_future.done():
            short_result = {'check': 'concurrent_short', 'status': 'inconclusive',
                            'error': 'Long completion was not active at probe time; check its result or reduce the delay.'}
            print(json.dumps(short_result), flush=True)
        else:
            action = checks(short_api)['tools_auto'] if args.short_check == 'tools_auto' else short_request
            short_result = measured('concurrent_short', action)
        long_result = long_future.result()

    overlap = (long_api.completion_finished - origin - short_result['finished_seconds']
               if long_api.completion_finished is not None and 'finished_seconds' in short_result else None)
    passed = (long_result['status'] == 'pass' and short_result['status'] == 'pass'
              and overlap is not None and overlap >= args.min_overlap
              and short_result['started_seconds'] >= long_api.completion_started - origin)
    result = {
        'recorded_at': datetime.now(timezone.utc).isoformat(), 'label': args.label,
        'status': 'pass' if passed else 'fail',
        'settings': {'requested_prompt_tokens': args.prompt_tokens, 'probe_delay_seconds': args.delay,
                     'short_check': args.short_check,
                     'unique_prompt_prefix': prefix,
                     'short_timeout_seconds': args.short_timeout,
                     'long_timeout_seconds': args.long_timeout,
                     'minimum_completion_separation_seconds': args.min_overlap},
        'short_finished_before_long_seconds': overlap,
        'long_completion_call': {
            'started_seconds': (long_api.completion_started - origin
                                if long_api.completion_started is not None else None),
            'finished_seconds': (long_api.completion_finished - origin
                                 if long_api.completion_finished is not None else None),
        },
        'results': [long_result, short_result],
        'observations': {'long': long_api.observations, 'short': short_api.observations},
        'limits': ('Synthetic completion-call overlap check with a unique prefix near the start '
                   'of the user prompt. Server admission and prefill phase require separate '
                   'metrics; this is not a controlled throughput benchmark.'),
    }
    with open(args.output, 'w') as output:
        json.dump(result, output, indent=2)
        output.write('\n')
    print(json.dumps({'status': result['status'], 'short_finished_before_long_seconds': overlap}),
          flush=True)
    raise SystemExit(0 if passed else 1)


if __name__ == '__main__':
    main()
