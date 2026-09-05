#!/usr/bin/env python3
"""Live API checks using synthetic data. Exits nonzero on any failed check."""
import argparse
import concurrent.futures
import copy
import json
import os
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from datetime import datetime, timezone


def require(condition, detail):
    if not condition:
        raise AssertionError(detail)


class API:
    def __init__(self, url, model, timeout):
        self.url = url.rstrip('/')
        self.model = model
        self.timeout = timeout
        self.observations = []

    def request(self, path, payload=None):
        headers = {'Content-Type': 'application/json'}
        if os.environ.get('API_KEY'):
            headers['Authorization'] = 'Bearer ' + os.environ['API_KEY']
        return urllib.request.urlopen(urllib.request.Request(
            self.url + path, headers=headers,
            data=None if payload is None else json.dumps(payload).encode(),
        ), timeout=self.timeout)

    def chat(self, messages, **kwargs):
        payload = dict(model=self.model, messages=messages, temperature=0,
                       max_tokens=256, chat_template_kwargs={'thinking': False})
        payload.update(kwargs)
        payload = copy.deepcopy(payload)
        started = time.monotonic()
        with self.request('/v1/chat/completions', payload) as response:
            result = json.load(response)
        self.observations.append({'elapsed_seconds': time.monotonic() - started,
                                  'request': payload, 'response': result})
        require(result['choices'][0]['finish_reason'] != 'length', 'Output truncated')
        return result['choices'][0]['message']

    @contextmanager
    def stream(self, payload):
        """Record received evidence and close the response, including early exit."""
        payload = copy.deepcopy(payload)
        received = {'events': [], 'lines': [], 'done': False}
        observation = {'request': payload, 'response': received, 'closed': False}
        started = time.monotonic()
        response = None
        try:
            with self.request('/v1/chat/completions', payload) as response:
                def events():
                    for raw in response:
                        received['lines'].append(raw.decode(errors='replace'))
                        line = raw.decode().strip()
                        if line == 'data: [DONE]':
                            received['done'] = True
                            return
                        if line.startswith('data: '):
                            event = json.loads(line[6:])
                            received['events'].append(copy.deepcopy(event))
                            if 'error' in event:
                                raise RuntimeError(f"Stream error: {event['error']}")
                            yield event
                    require(False, 'Stream ended without [DONE]')

                yield events()
            observation['status'] = 'complete' if received['done'] else 'cancelled'
        except Exception as error:
            observation.update(status='error', error=f'{type(error).__name__}: {error}')
            if isinstance(error, urllib.error.HTTPError):
                try:
                    received['body'] = error.read().decode(errors='replace')
                finally:
                    error.close()
                    observation['closed'] = True
            raise
        finally:
            if response is not None:
                observation['closed'] = response.closed
            observation['elapsed_seconds'] = time.monotonic() - started
            self.observations.append(observation)


def user(text):
    return [{'role': 'user', 'content': text}]


def exact(message, expected):
    require((message.get('content') or '').strip() == expected, repr(message))


TOOL = {'type': 'function', 'function': {
    'name': 'lookup_code', 'description': 'Read the code for a named synthetic record.',
    'parameters': {'type': 'object', 'properties': {'record': {'type': 'string'}},
                   'required': ['record'], 'additionalProperties': False},
}}


def tool_call(message, record):
    calls = message.get('tool_calls') or []
    require(len(calls) == 1, repr(message))
    call = calls[0]
    require(bool(call.get('id')), 'Missing tool call ID')
    require(call['function']['name'] == 'lookup_code', repr(call))
    require(json.loads(call['function']['arguments']) == {'record': record}, repr(call))
    return call


def long_context(api, desired_tokens, prefix=''):
    """Retrieve distinct facts near the beginning, middle and end of a long prompt."""
    filler_count = max(1, desired_tokens - 200)
    expected = {'first': 'IVORY-162', 'middle': 'COPPER-493', 'last': 'SILVER-857'}
    for _attempt in range(4):
        section = 'padding ' * (filler_count // 10)
        prompt = (prefix + section + 'The first code is IVORY-162.\n' + section * 4
                  + 'The middle code is COPPER-493.\n' + section * 4
                  + 'The last code is SILVER-857.\n' + section
                  + '\nReturn only JSON with keys first, middle, last and their codes.')
        messages = user(prompt)
        with api.request('/tokenize', {'model': api.model, 'messages': messages,
                                      'chat_template_kwargs': {'thinking': False}}) as response:
            count = json.load(response)['count']
        if desired_tokens * 0.97 <= count <= desired_tokens:
            break
        filler_count = max(1, int(filler_count * (desired_tokens - 100) / count))
    require(desired_tokens * 0.9 <= count <= desired_tokens,
            f'Could not construct the requested prompt length: {count}')
    message = api.chat(messages, response_format={'type': 'json_object'})
    require(json.loads(message['content']) == expected, repr(message))
    return {'requested_prompt_tokens': desired_tokens, 'measured_prompt_tokens': count,
            'expected': expected, 'observed': json.loads(message['content'])}


def checks(api):
    def identity():
        with api.request('/health') as response:
            require(response.status == 200, 'Health failed')
        with api.request('/v1/models') as response:
            data = json.load(response)
        require(api.model in [m['id'] for m in data['data']], repr(data))
        return data

    def chat():
        message = api.chat(user('Reply with exactly: ORBIT-629'))
        exact(message, 'ORBIT-629')
        require(not (message.get('reasoning') or message.get('reasoning_content')),
                'Thinking disabled but reasoning returned')

    def multi_turn():
        exact(api.chat([
            {'role': 'user', 'content': 'Remember this synthetic code: MAPLE-814.'},
            {'role': 'assistant', 'content': 'I will remember it.'},
            {'role': 'user', 'content': 'Reply with only the code I gave you.'},
        ]), 'MAPLE-814')

    def reasoning(effort='low'):
        message = api.chat(user('Calculate 17 * 19. Final answer must be only the integer.'),
                           chat_template_kwargs={'thinking': True},
                           reasoning_effort=effort, max_tokens=1024)
        require(bool(message.get('reasoning') or message.get('reasoning_content')),
                'Missing separated reasoning')
        exact(message, '323')

    def tools(choice):
        messages = user('Use lookup_code to read record alpha. Do not guess its code.')
        message = api.chat(messages, tools=[TOOL], tool_choice=choice)
        call = tool_call(message, 'alpha')
        messages += [message, {'role': 'tool', 'tool_call_id': call['id'],
                               'content': '{"code":"VIOLET-937"}'},
                     {'role': 'user', 'content': 'Reply with exactly the code returned by the tool.'}]
        exact(api.chat(messages, tools=[TOOL], tool_choice='none'), 'VIOLET-937')

    def json_output(strict):
        schema = {'type': 'object', 'properties': {
            'code': {'type': 'string', 'enum': ['BIRCH-528']},
            'count': {'type': 'integer', 'enum': [7]}},
            'required': ['code', 'count'], 'additionalProperties': False}
        fmt = {'type': 'json_object'}
        if strict:
            fmt = {'type': 'json_schema', 'json_schema': {
                'name': 'synthetic_record', 'strict': True, 'schema': schema}}
        message = api.chat(user('Return exactly this JSON object, preserving both key names and values: {"code":"BIRCH-528","count":7}. No other fields.'),
                           response_format=fmt)
        require(json.loads(message['content']) == {'code': 'BIRCH-528', 'count': 7}, repr(message))

    def reasoning_tools():
        messages = user('Use lookup_code for record delta, then reply with only its returned code.')
        options = dict(tools=[TOOL], chat_template_kwargs={'thinking': True},
                       reasoning_effort='low', max_tokens=1024)
        message = api.chat(messages, tool_choice='auto', **options)
        call = tool_call(message, 'delta')
        require(bool(message.get('reasoning') or message.get('reasoning_content')),
                'Missing reasoning before tool call')
        # Preserve the entire assistant message, including reasoning, across the
        # tool response. No new user turn should reset the ongoing reasoning.
        messages += [message, {'role': 'tool', 'tool_call_id': call['id'],
                               'content': '{"code":"LILAC-286"}'}]
        exact(api.chat(messages, tool_choice='none', **options), 'LILAC-286')

    def streaming():
        payload = dict(model=api.model, messages=user('Reply with exactly: STREAM-416'),
                       temperature=0, max_tokens=64, stream=True,
                       stream_options={'include_usage': True},
                       chat_template_kwargs={'thinking': False})
        chunks, finish, usage = [], None, None
        with api.stream(payload) as events:
            for event in events:
                if event.get('usage'):
                    usage = event['usage']
                for choice in event.get('choices', []):
                    delta = choice.get('delta', {})
                    require(not (delta.get('reasoning') or delta.get('reasoning_content')),
                            'Unexpected reasoning in chat stream')
                    chunks.append(delta.get('content') or '')
                    finish = choice.get('finish_reason') or finish
        require(''.join(chunks).strip() == 'STREAM-416', repr(chunks))
        require(finish == 'stop', f'finish={finish}')
        require(usage and usage['completion_tokens'] > 0, 'Missing real token usage')
        return {'content': ''.join(chunks), 'usage': usage}

    def concurrency():
        codes = ['CEDAR-319', 'ELM-742']
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(api.chat, user('Reply with exactly: ' + code)) for code in codes]
            for code, future in zip(codes, futures):
                exact(future.result(), code)

    def stream_reasoning():
        payload = dict(model=api.model,
                       messages=user('Calculate 17 * 19. Final answer must be only the integer.'),
                       temperature=0, max_tokens=1024, stream=True,
                       chat_template_kwargs={'thinking': True}, reasoning_effort='low')
        content, reasoning_parts, finish = [], [], None
        with api.stream(payload) as events:
            for event in events:
                for choice in event.get('choices', []):
                    finish = choice.get('finish_reason') or finish
                    delta = choice.get('delta', {})
                    content.append(delta.get('content') or '')
                    reasoning_parts.append(delta.get('reasoning') or delta.get('reasoning_content') or '')
        require(finish == 'stop', f'finish={finish}')
        require(''.join(content).strip() == '323', repr(content))
        require(bool(''.join(reasoning_parts).strip()), 'Missing streamed reasoning')
        return {'content': ''.join(content), 'reasoning_characters': len(''.join(reasoning_parts))}

    def multiple_tools():
        messages = user('Call lookup_code twice: once for alpha, once for beta. Both are required.')
        message = api.chat(messages, tools=[TOOL], tool_choice='required', max_tokens=512)
        calls = message.get('tool_calls') or []
        require(len(calls) == 2, repr(message))
        require(len({call['id'] for call in calls}) == 2, 'Repeated call IDs')
        observed = set()
        messages.append(message)
        values = {'alpha': 'AMBER-614', 'beta': 'TEAL-927'}
        for call in calls:
            require(call['function']['name'] == 'lookup_code', repr(call))
            arguments = json.loads(call['function']['arguments'])
            require(set(arguments) == {'record'}, repr(arguments))
            record = arguments['record']
            require(record in values, repr(arguments))
            observed.add(record)
            messages.append({'role': 'tool', 'tool_call_id': call['id'],
                             'content': json.dumps({'code': values[record]})})
        require(observed == set(values), 'Missing record')
        messages.append({'role': 'user', 'content': 'Reply only with alpha code, then beta code, separated by one space.'})
        exact(api.chat(messages, tools=[TOOL], tool_choice='none'), 'AMBER-614 TEAL-927')

    def stream_tools():
        payload = dict(model=api.model,
                       messages=user('Use lookup_code for record gamma.'), tools=[TOOL],
                       tool_choice='auto', stream=True, temperature=0, max_tokens=256,
                       chat_template_kwargs={'thinking': False})
        calls, finish = {}, None
        with api.stream(payload) as events:
            for event in events:
                for choice in event.get('choices', []):
                    finish = choice.get('finish_reason') or finish
                    for delta in choice.get('delta', {}).get('tool_calls') or []:
                        call = calls.setdefault(delta['index'], {
                            'id': '', 'type': 'function', 'function': {'name': '', 'arguments': ''}})
                        call['id'] += delta.get('id') or ''
                        for key in ('name', 'arguments'):
                            call['function'][key] += delta.get('function', {}).get(key) or ''
        require(finish == 'tool_calls', f'finish={finish}')
        tool_call({'tool_calls': list(calls.values())}, 'gamma')
        return list(calls.values())

    def cancellation():
        payload = dict(model=api.model, messages=user('Count integers from 1 to 5000, separated by commas.'),
                       temperature=0, max_tokens=1024, stream=True,
                       chat_template_kwargs={'thinking': False})
        received = False
        with api.stream(payload) as events:
            for event in events:
                if any(choice.get('delta', {}).get('content') for choice in event.get('choices', [])):
                    received = True
                    break
        require(received, 'No generated content before cancellation')
        exact(api.chat(user('Reply with exactly: RECOVERED-832')), 'RECOVERED-832')

    def prefix_reuse():
        prefix = 'Read the final instruction carefully. ' * 100
        for code in ['PREFIX-158', 'PREFIX-963', 'PREFIX-158']:
            exact(api.chat(user(prefix + 'Reply with exactly: ' + code)), code)

    return {'identity': identity, 'chat': chat, 'multi_turn': multi_turn,
            'reasoning': reasoning, 'reasoning_high': lambda: reasoning('high'),
            'reasoning_max': lambda: reasoning('max'), 'stream_reasoning': stream_reasoning,
            'reasoning_tools': reasoning_tools,
            'tools_auto': lambda: tools('auto'),
            'tools_required': lambda: tools('required'),
            'tools_named': lambda: tools({'type': 'function', 'function': {'name': 'lookup_code'}}),
            'json_object': lambda: json_output(False), 'json_schema': lambda: json_output(True),
            'streaming': streaming, 'stream_tools': stream_tools, 'multiple_tools': multiple_tools,
            'concurrency': concurrency, 'prefix_reuse': prefix_reuse, 'cancellation': cancellation}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default='http://127.0.0.1:8000')
    parser.add_argument('--model', default='dsv4-nvfp4')
    parser.add_argument('--timeout', type=float, default=180)
    parser.add_argument('--only', help='Comma-separated check names')
    parser.add_argument('--output', help='Save observations locally; may contain model output')
    parser.add_argument('--long-context-tokens', type=int, default=0,
                        help='Add a measured long-context retrieval check; reserve output room')
    args = parser.parse_args()
    api = API(args.base_url, args.model, args.timeout)
    suite = checks(api)
    if args.long_context_tokens:
        if args.long_context_tokens < 1024:
            parser.error('--long-context-tokens must be at least 1024')
        suite['long_context'] = lambda: long_context(api, args.long_context_tokens)
    selected = args.only.split(',') if args.only else list(suite)
    unknown = set(selected) - suite.keys()
    if unknown:
        parser.error('Unknown checks: ' + ', '.join(sorted(unknown)))
    results = []
    for name in selected:
        started = time.monotonic()
        try:
            detail = suite[name]()
            result = {'check': name, 'status': 'pass', 'detail': detail}
        except Exception as error:
            result = {'check': name, 'status': 'fail', 'error': str(error)}
            if isinstance(error, urllib.error.HTTPError) and not error.closed:
                result['response'] = error.read().decode(errors='replace')
        result['elapsed_seconds'] = time.monotonic() - started
        results.append(result)
        print(json.dumps(result), flush=True)
    if args.output:
        with open(args.output, 'w') as output:
            json.dump({'recorded_at': datetime.now(timezone.utc).isoformat(),
                       'results': results, 'observations': api.observations}, output, indent=2)
            output.write('\n')
    raise SystemExit(int(any(result['status'] != 'pass' for result in results)))


if __name__ == '__main__':
    main()
