#!/usr/bin/env python3
"""Analyze copied schema-v1 Kineto traces without loading Torch or contacting GPUs."""
from __future__ import annotations

import argparse
from bisect import bisect_right
from collections import Counter, defaultdict
import gzip
import hashlib
import json
from pathlib import Path
import re


COMPONENTS = ('target_forward', 'postprocess_logits', 'sampling',
              'draft_pipeline', 'misc', 'unattributed')
SCOPE_COMPONENT = {'forward': 'target_forward', 'postprocess': 'postprocess_logits',
                   'sample': 'sampling', 'draft': 'draft_pipeline'}
MQA_NAMES = {'_fp8_paged_mqa_logits_rowwise_kernel',
             '_fp8_paged_mqa_logits_kernel', '_fp8_mqa_logits_kernel'}


def end(event: dict) -> float:
    return event['ts'] + event['dur']


def intervals(events: list[dict]) -> dict:
    """Duration sum differs deliberately from union and first-to-last span."""
    ordered = sorted((event['ts'], end(event)) for event in events)
    merged = []
    for start, stop in ordered:
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(stop, merged[-1][1])
        else:
            merged.append([start, stop])
    return dict(count=len(events),
                sum_ms=round(sum(event['dur'] for event in events) / 1000, 6),
                union_ms=round(sum(stop - start for start, stop in merged) / 1000, 6),
                span_ms=round((merged[-1][1] - merged[0][0]) / 1000, 6) if merged else 0,
                first_relative_us=ordered[0][0] if ordered else None,
                last_relative_us=max(stop for _, stop in ordered) if ordered else None)


def gpu_summary(events: list[dict]) -> dict:
    devices = defaultdict(list)
    for event in events:
        devices[str(event.get('args', {}).get('device', event['pid']))].append(event)
    return dict(count=len(events),
                sum_ms=round(sum(event['dur'] for event in events) / 1000, 6),
                by_device={device: intervals(rows) for device, rows in devices.items()})


def analyze_trace(trace: dict) -> dict:
    if trace.get('schemaVersion') != 1 or not isinstance(trace.get('traceEvents'), list):
        raise ValueError('Expected inspected Kineto schemaVersion 1 with traceEvents')
    raw_events = trace['traceEvents']
    complete = [event for event in raw_events if event.get('ph') == 'X']
    if not complete or any(event.get('dur', -1) < 0 for event in complete):
        raise ValueError('Missing or invalid complete-event durations')
    origin = min(event['ts'] for event in complete)
    events = [{**event, 'ts': event['ts'] - origin} for event in complete]
    scopes = [event for event in events if event.get('cat') == 'user_annotation'
              and event['name'].startswith('gpu_model_runner: ')]
    executes = sorted((event for event in events
                       if event.get('cat') == 'user_annotation'
                       and event['name'].startswith('execute_')), key=lambda event: event['ts'])
    by_thread = defaultdict(list)
    execute_threads = defaultdict(list)
    for scope in scopes:
        by_thread[(scope['pid'], scope['tid'])].append(scope)
    for number, event in enumerate(executes):
        event['step'] = number
        execute_threads[(event['pid'], event['tid'])].append(event)
        label = re.fullmatch(r'execute_context_(\d+)\((\d+)\)_generation_(\d+)\((\d+)\)', event['name'])
        context, generation = (int(label[1]), int(label[3])) if label else (-1, -1)
        event['phase'] = ('generation_only' if context == 0 and generation > 0 else
                          'mixed_context_generation' if context > 0 and generation > 0 else
                          'context_only' if context > 0 and generation == 0 else 'unknown')

    def owner(api: dict) -> tuple[str, int | None]:
        thread = (api['pid'], api['tid'])
        containing = [scope for scope in by_thread[thread]
                      if scope['ts'] <= api['ts'] and end(api) <= end(scope) + .002]
        component = 'unattributed'
        if containing:
            scope = min(containing, key=lambda item: item['dur'])
            component = SCOPE_COMPONENT.get(scope['name'].split(': ', 1)[1], 'misc')
        steps = execute_threads[thread]
        index = bisect_right([step['ts'] for step in steps], api['ts']) - 1
        # The last step extends through its final runner scope, not the trace end.
        step = None
        if index >= 0:
            terminal = (steps[index + 1]['ts'] if index + 1 < len(steps) else
                        max([end(steps[index])] + [end(scope) for scope in by_thread[thread]
                                                  if scope['ts'] >= steps[index]['ts']]))
            if api['ts'] < terminal:
                step = steps[index]['step']
        return component, step

    apis = defaultdict(list)
    for event in events:
        if event.get('cat') in ('cuda_runtime', 'cuda_driver'):
            correlation = event.get('args', {}).get('correlation')
            if correlation is not None:
                apis[correlation].append(event)
    api_owners = {key: owner(rows[0]) for key, rows in apis.items() if len(rows) == 1}
    components = {name: dict(kernels=[], memory=[], cpu=[]) for name in COMPONENTS}
    for scope in scopes:
        component = SCOPE_COMPONENT.get(scope['name'].split(': ', 1)[1], 'misc')
        components[component]['cpu'].append(scope)
    kernels = [event for event in events if event.get('cat') == 'kernel']
    memory = [event for event in events if event.get('cat') in ('gpu_memcpy', 'gpu_memset')]
    step_kernels = [defaultdict(list) for _ in executes]
    reasons = Counter()
    links = []
    names = defaultdict(list)
    graph_launches = defaultdict(list)
    for event in kernels + memory:
        args = event.get('args', {})
        correlation = args.get('correlation')
        candidates = apis.get(correlation, [])
        component, step = 'unattributed', None
        linked = False
        if not candidates:
            reason = 'missing_correlation'
        elif len(candidates) != 1:
            reason = 'ambiguous_correlation'
        else:
            api = candidates[0]
            if args.get('graph id', 0) and api['name'] != 'cudaGraphLaunch':
                reason = 'graph_without_graph_launch'
            elif event.get('cat') == 'kernel' and 'Launch' not in api['name']:
                reason = 'kernel_without_launch'
            else:
                linked = True
                component, step = api_owners[correlation]
                reason = ('outside_runner_scope' if component == 'unattributed' else
                          'unique_graph_launch' if args.get('graph id', 0) else
                          'unique_direct_api')
                if args.get('graph id', 0):
                    graph_launches[correlation].append(event)
        event['component'] = component
        event['step'] = step
        if event.get('cat') == 'kernel':
            components[component]['kernels'].append(event)
            reasons[reason] += 1
            links.append((event, linked))
            names[(component, event['name'])].append(event)
            if step is not None:
                step_kernels[step][component].append(event)
        else:
            components[component]['memory'].append(event)

    total_us = sum(event['dur'] for event in kernels)
    linked = [event for event, matched in links if matched]
    attributed = [event for event in kernels if event['component'] != 'unattributed']
    def percent(part: float, total: float) -> float | None:
        return round(100 * part / total, 6) if total else None

    phase_summaries = {}
    for phase in sorted({event['phase'] for event in executes}):
        indices = [event['step'] for event in executes if event['phase'] == phase]
        phase_rows = [event for event in kernels if event['step'] in indices]
        phase_components = {}
        for name, rows in components.items():
            phase_components[name] = dict(
                kernels=gpu_summary([event for event in rows['kernels'] if event['step'] in indices]),
                cpu_wall=intervals([scope for scope in rows['cpu'] if owner(scope)[1] in indices]))
        phase_summaries[phase] = dict(
            step_indices=indices, kernel_total=gpu_summary(phase_rows), components=phase_components,
            named_indexer_mqa_logits_subset=gpu_summary([event for event in phase_rows if event['name'] in MQA_NAMES]))
    result_components = {}
    for name, rows in components.items():
        result_components[name] = dict(
            kernels=gpu_summary(rows['kernels']), memory_activities=gpu_summary(rows['memory']),
            cpu_wall=intervals(rows['cpu']),
            kernel_work_percent=percent(sum(event['dur'] for event in rows['kernels']), total_us))
    return dict(
        rank=trace.get('distributedInfo', {}).get('rank'),
        schema=dict(version=1, event_timestamp_unit='microseconds',
                    display_time_unit=trace.get('displayTimeUnit'), origin_event_ts_us=origin,
                    base_time_nanoseconds=trace.get('baseTimeNanoseconds'),
                    original_event_count=len(raw_events),
                    complete_categories=dict(Counter(event.get('cat', '') for event in events)),
                    cpu_process_threads=[list(thread) for thread in by_thread]),
        execute_scope_count=len(executes), execute_labels=dict(Counter(event['name'] for event in executes)),
        runner_cpu_scope_counts=dict(Counter(scope['name'] for scope in scopes)),
        kernel_total=gpu_summary(kernels), all_gpu_activities=gpu_summary(kernels + memory),
        components=result_components,
        phase_summaries=phase_summaries,
        kernel_attribution=dict(
            reasons=dict(reasons), api_link_count_percent=percent(len(linked), len(kernels)),
            api_link_duration_percent=percent(sum(event['dur'] for event in linked), total_us),
            component_count_percent=percent(len(attributed), len(kernels)),
            component_duration_percent=percent(sum(event['dur'] for event in attributed), total_us),
            ambiguous_api_correlations=sum(len(rows) > 1 for rows in apis.values()),
            unpaired_step_kernels=len(kernels) - sum(len(rows) for step in step_kernels for rows in step.values())),
        graph_launches=[dict(correlation=key, component=api_owners[key][0],
                             graph_ids=sorted({event['args']['graph id'] for event in rows}),
                             kernels=gpu_summary([event for event in rows if event['cat'] == 'kernel']))
                        for key, rows in graph_launches.items()],
        named_indexer_mqa_logits_subset=gpu_summary([event for event in kernels if event['name'] in MQA_NAMES]),
        named_indexer_mqa_logits_by_component={name: gpu_summary([event for event in rows['kernels']
                                                               if event['name'] in MQA_NAMES])
                                             for name, rows in components.items()},
        kernel_names=[dict(component=component, name=name, **gpu_summary(rows))
                      for (component, name), rows in sorted(names.items(),
                          key=lambda item: -sum(event['dur'] for event in item[1]))],
        steps=[dict(index=index, label=event['name'],
                    execute_cpu_wall_ms=round(event['dur'] / 1000, 6),
                    components={name: gpu_summary(rows) for name, rows in step_kernels[index].items()})
               for index, event in enumerate(executes)],
        exclusions=['gpu_user_annotation rollups', 'CPU/GPU duration addition',
                    'cross-rank duration addition', 'graph-ID-only ownership inference',
                    'critical-path or throughput claim', 'complete indexer cost claim'])


def markdown(result: dict) -> str:
    lines = [f"# {result['case']} rank {result['rank']} trace accounting", '',
             f"Observed execution steps: {result['execute_scope_count']}. "
             f"Kernel attribution by duration: {result['kernel_attribution']['component_duration_percent']}%.", '',
             '| Component | Kernels | Kernel sum ms | GPU union ms/device | CPU scope wall sum ms |',
             '|---|---:|---:|---|---:|']
    for name, component in result['components'].items():
        kernel = component['kernels']
        union = ', '.join(f"{device}: {value['union_ms']:.3f}" for device, value in kernel['by_device'].items()) or '—'
        lines.append(f"| {name} | {kernel['count']} | {kernel['sum_ms']:.3f} | {union} | {component['cpu_wall']['sum_ms']:.3f} |")
    lines += ['', f"All kernels: {result['kernel_total']['sum_ms']:.3f} ms of summed work."]
    for device, value in result['kernel_total']['by_device'].items():
        lines.append(f"Device {device}: kernel union {value['union_ms']:.3f} ms; "
                     f"first-to-last kernel span {value['span_ms']:.3f} ms.")
    for phase, summary in result['phase_summaries'].items():
        lines += ['', f"{phase}: {len(summary['step_indices'])} steps, "
                  f"{summary['kernel_total']['sum_ms']:.3f} ms kernel sum."]
        if len(result['phase_summaries']) > 1:
            lines += ['', '| Component | Phase kernel sum ms |', '|---|---:|']
            lines += [f"| {name} | {component['kernels']['sum_ms']:.3f} |"
                      for name, component in summary['components'].items()]
    lines += ['', f"Identified indexer MQA-logits subset: {result['named_indexer_mqa_logits_subset']['sum_ms']:.3f} ms. "
              'This is already included in the component totals and omits other indexer work.', '',
              'Kernel sums are work accounting. Unions remove stream overlap; component unions may still overlap each other. '
              'Spans include gaps and are not critical paths. CPU scope wall durations may include waits and profiler overhead. '
              'The columns must not be added together. GPU annotation rollups are excluded.', '',
              'Warm-prefix diagnostic profile only; no request-latency, clean profiler-overhead, adaptive-speedup, '
              'or complete-indexer-cost claim. Each rank is analyzed independently.', '']
    return '\n'.join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('traces', type=Path)
    parser.add_argument('--output-dir', type=Path, required=True)
    cfg = parser.parse_args()
    files = sorted(cfg.traces.rglob('*.pt.trace.json.gz'))
    if not files:
        parser.error('No copied trace files found')
    pending = []
    destinations = set()
    for path in files:
        with gzip.open(path, 'rt') as handle:
            result = analyze_trace(json.load(handle))
        result.update(case=path.parent.name, source=path.name,
                      source_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        prefix = f"{result['case']}-rank{result['rank']}"
        if prefix in destinations:
            parser.error(f'Duplicate trace report destination: {prefix}')
        destinations.add(prefix)
        pending.append((prefix, result))
    cfg.output_dir.mkdir(parents=True, exist_ok=True)
    index = []
    for prefix, result in pending:
        (cfg.output_dir / f'{prefix}.json').write_text(json.dumps(result, indent=2) + '\n')
        (cfg.output_dir / f'{prefix}.md').write_text(markdown(result))
        index.append(dict(case=result['case'], rank=result['rank'],
                          execute_scope_count=result['execute_scope_count'],
                          kernel_sum_ms=result['kernel_total']['sum_ms'],
                          kernel_attribution=result['kernel_attribution']))
    (cfg.output_dir / 'index.json').write_text(json.dumps(index, indent=2) + '\n')
    print(json.dumps(index, indent=2))


if __name__ == '__main__':
    main()
