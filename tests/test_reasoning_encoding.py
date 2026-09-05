"""Compare installed tokenizer prompts to the pinned model's official encoder."""
import importlib.util
import os
import unittest
from pathlib import Path

from vllm.tokenizers.deepseek_v4 import DeepseekV4Tokenizer


class ReasoningEncodingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        model_dir = Path(os.environ['DSPARK_TEST_MODEL_DIR'])
        source = model_dir / 'encoding' / 'encoding_dsv4.py'
        spec = importlib.util.spec_from_file_location('official_dsv4_encoding', source)
        cls.official = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.official)
        cls.tokenizer = DeepseekV4Tokenizer.from_pretrained(str(model_dir))
        cls.messages = [{'role': 'user', 'content': 'Calculate 17 * 19.'}]

    def assert_prompt(self, effort, thinking=True, official_effort=None):
        expected = self.official.encode_messages(
            self.messages, thinking_mode='thinking' if thinking else 'chat',
            reasoning_effort=official_effort or effort,
        )
        actual = self.tokenizer.apply_chat_template(
            self.messages, tokenize=False, thinking=thinking,
            reasoning_effort=effort,
        )
        self.assertEqual(actual, expected)

    def test_three_thinking_efforts_match_pinned_encoder(self):
        for effort in ('low', 'high', 'max'):
            with self.subTest(effort=effort):
                self.assert_prompt(effort)

    def test_default_thinking_matches_low(self):
        self.assert_prompt(None, official_effort='low')

    def test_chat_does_not_include_effort_prefix(self):
        for effort in ('low', 'high', 'max'):
            with self.subTest(effort=effort):
                self.assert_prompt(effort, thinking=False)

    def test_xhigh_alias_matches_max(self):
        self.assert_prompt('xhigh', official_effort='max')


if __name__ == '__main__':
    unittest.main(verbosity=2)
