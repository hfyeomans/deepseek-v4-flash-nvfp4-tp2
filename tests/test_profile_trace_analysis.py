"""Bounded regressions for trace attribution and overlap accounting."""
import contextlib
import gzip
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from experiments.profile_trace_analysis import analyze_trace, main


def event(category, name, start, duration, pid=7, tid=7, **args):
    return dict(ph='X', cat=category, name=name, ts=start, dur=duration,
                pid=pid, tid=tid, args=args)


class TraceAnalysisTests(unittest.TestCase):
    def analyze(self, events):
        self.assertIsNotNone(analyze_trace, 'The trace analyzer must be implemented')
        return analyze_trace(dict(schemaVersion=1, traceEvents=events,
                                  distributedInfo={'rank': 0}))

    def test_launch_ownership_survives_cpu_scope_end_and_graph_reuse(self):
        events = [
            event('user_annotation', 'execute_context_0(0)_generation_1(6)', 0, 10),
            event('user_annotation', 'gpu_model_runner: forward', 1, 4),
            event('cuda_runtime', 'cudaGraphLaunch', 2, 1, correlation=9),
            event('user_annotation', 'gpu_model_runner: sample', 11, 4),
            event('cuda_runtime', 'cudaLaunchKernel', 12, 1, correlation=10),
            event('user_annotation', 'gpu_model_runner: draft', 16, 4),
            event('cuda_runtime', 'cudaGraphLaunch', 17, 1, correlation=11),
            event('kernel', 'target', 30, 10, pid=0, tid=2,
                  correlation=9, device=0, **{'graph id': 3}),
            event('kernel', 'sample', 40, 5, pid=0, tid=2, correlation=10, device=0),
            event('kernel', 'draft', 45, 5, pid=0, tid=2,
                  correlation=11, device=0, **{'graph id': 3}),
            event('gpu_user_annotation', 'gpu_model_runner: forward', 30, 200,
                  pid=0, tid=2),
        ]
        result = self.analyze(events)
        self.assertEqual(result['kernel_total']['count'], 3)
        self.assertEqual(result['components']['target_forward']['kernels']['sum_ms'], .01)
        self.assertEqual(result['components']['sampling']['kernels']['sum_ms'], .005)
        self.assertEqual(result['components']['draft_pipeline']['kernels']['sum_ms'], .005)
        self.assertEqual(result['steps'][0]['components']['sampling']['count'], 1)
        self.assertEqual(result['steps'][0]['components']['draft_pipeline']['count'], 1)
        self.assertEqual(result['kernel_attribution']['component_count_percent'], 100)

    def test_union_and_span_do_not_sum_overlapping_streams_or_cpu(self):
        result = self.analyze([
            event('user_annotation', 'gpu_model_runner: draft', 0, 100),
            event('cuda_driver', 'cuLaunchKernel', 1, 1, correlation=1),
            event('cuda_driver', 'cuLaunchKernel', 2, 1, correlation=2),
            event('kernel', 'a', 20, 10, pid=0, tid=2, device=0, correlation=1),
            event('kernel', 'b', 25, 10, pid=0, tid=3, device=0, correlation=2),
        ])
        self.assertEqual(result['kernel_total']['sum_ms'], .020)
        self.assertEqual(result['kernel_total']['by_device']['0']['union_ms'], .015)
        self.assertEqual(result['kernel_total']['by_device']['0']['span_ms'], .015)
        self.assertEqual(result['components']['draft_pipeline']['cpu_wall']['sum_ms'], .100)

    def test_unknown_graph_and_ambiguous_correlation_remain_unattributed(self):
        result = self.analyze([
            event('user_annotation', 'gpu_model_runner: forward', 0, 10),
            event('cuda_runtime', 'cudaGraphLaunch', 1, 1, correlation=1),
            event('cuda_runtime', 'cudaGraphLaunch', 2, 1, correlation=1),
            event('kernel', 'ambiguous', 20, 4, pid=0, tid=2, device=0,
                  correlation=1, **{'graph id': 7}),
            event('kernel', 'unknown', 24, 6, pid=0, tid=2, device=0,
                  correlation=99, **{'graph id': 7}),
        ])
        self.assertEqual(result['components']['unattributed']['kernels']['count'], 2)
        self.assertEqual(result['kernel_attribution']['component_count_percent'], 0)
        self.assertEqual(result['kernel_attribution']['reasons']['ambiguous_correlation'], 1)
        self.assertEqual(result['kernel_attribution']['reasons']['missing_correlation'], 1)

    def test_same_timestamp_on_another_thread_does_not_assign_scope(self):
        result = self.analyze([
            event('user_annotation', 'gpu_model_runner: forward', 0, 10),
            event('cuda_driver', 'cuLaunchKernel', 1, 1, tid=8, correlation=1),
            event('kernel', 'other_thread', 12, 4, pid=0, tid=2, device=0, correlation=1),
        ])
        self.assertEqual(result['components']['unattributed']['kernels']['count'], 1)
        self.assertEqual(result['kernel_attribution']['api_link_count_percent'], 100)

    def test_named_mqa_is_a_subset_and_memcpy_is_separate(self):
        result = self.analyze([
            event('user_annotation', 'gpu_model_runner: forward', 0, 10),
            event('cuda_runtime', 'cudaGraphLaunch', 1, 1, correlation=1),
            event('kernel', '_fp8_paged_mqa_logits_rowwise_kernel', 12, 4,
                  pid=0, tid=2, device=0, correlation=1, **{'graph id': 7}),
            event('gpu_memcpy', 'Memcpy', 16, 2, pid=0, tid=2, device=0, correlation=1),
        ])
        self.assertEqual(result['kernel_total']['count'], 1)
        self.assertEqual(result['components']['target_forward']['memory_activities']['count'], 1)
        self.assertEqual(result['named_indexer_mqa_logits_subset']['count'], 1)
        self.assertEqual(result['all_gpu_activities']['sum_ms'], .006)

    def test_mixed_context_step_is_separate_from_generation_only(self):
        result = self.analyze([
            event('user_annotation', 'execute_context_1(39)_generation_1(6)', 0, 10),
            event('user_annotation', 'gpu_model_runner: forward', 1, 4),
            event('cuda_runtime', 'cudaGraphLaunch', 2, 1, correlation=1),
            event('user_annotation', 'execute_context_0(0)_generation_2(12)', 20, 10),
            event('user_annotation', 'gpu_model_runner: forward', 21, 4),
            event('cuda_runtime', 'cudaGraphLaunch', 22, 1, correlation=2),
            event('kernel', 'mixed', 40, 9, pid=0, tid=2, device=0,
                  correlation=1, **{'graph id': 3}),
            event('kernel', 'generation', 49, 4, pid=0, tid=2, device=0,
                  correlation=2, **{'graph id': 3}),
        ])
        self.assertIn('phase_summaries', result)
        phases = result['phase_summaries']
        self.assertEqual(phases['mixed_context_generation']['step_indices'], [0])
        self.assertEqual(phases['generation_only']['step_indices'], [1])
        self.assertEqual(phases['generation_only']['components']['target_forward']['kernels']['sum_ms'], .004)


class TraceOutputTests(unittest.TestCase):
    def write_trace(self, path, rank=0):
        path.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(path, 'wt') as output:
            json.dump(dict(schemaVersion=1, distributedInfo={'rank': rank},
                           traceEvents=[event('kernel', 'synthetic', 0, 1)]), output)

    def run_analyzer(self, traces, output):
        argv = ['profile_trace_analysis.py', str(traces), '--output-dir', str(output)]
        with patch('sys.argv', argv), contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()):
            main()

    def test_duplicate_case_rank_cannot_replace_existing_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            traces, output = root / 'traces', root / 'output'
            self.write_trace(traces / 'case' / 'first.pt.trace.json.gz')
            self.write_trace(traces / 'case' / 'second.pt.trace.json.gz')
            output.mkdir()
            (output / 'case-rank0.json').write_text('retained result')
            (output / 'index.json').write_text('retained index')
            before = {path.name: path.read_bytes() for path in output.iterdir()}
            with self.assertRaises(SystemExit) as error:
                self.run_analyzer(traces, output)
            self.assertNotEqual(error.exception.code, 0)
            self.assertEqual({path.name: path.read_bytes() for path in output.iterdir()}, before)

    def test_equal_case_names_in_different_directories_fail_before_output_creation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            traces, output = root / 'traces', root / 'output'
            self.write_trace(traces / 'run1' / 'case' / 'one.pt.trace.json.gz')
            self.write_trace(traces / 'run2' / 'case' / 'two.pt.trace.json.gz')
            with self.assertRaises(SystemExit) as error:
                self.run_analyzer(traces, output)
            self.assertNotEqual(error.exception.code, 0)
            self.assertFalse(output.exists())

    def test_distinct_ranks_keep_separate_reports(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            traces, output = root / 'traces', root / 'output'
            self.write_trace(traces / 'case' / 'rank0.pt.trace.json.gz', rank=0)
            self.write_trace(traces / 'case' / 'rank1.pt.trace.json.gz', rank=1)
            self.run_analyzer(traces, output)
            index = json.loads((output / 'index.json').read_text())
            self.assertEqual({item['rank'] for item in index}, {0, 1})
            self.assertEqual(len(list(output.glob('case-rank*.json'))), 2)
            self.assertEqual(len(list(output.glob('case-rank*.md'))), 2)


if __name__ == '__main__':
    unittest.main()
