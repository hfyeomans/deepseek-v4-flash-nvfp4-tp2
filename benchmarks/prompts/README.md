# Synthetic coding prompt

We needed the same long coding input across runs. `code-48k.txt` freezes 320
synthetic Python validators and asks for a refactor and boundary tests for
validator0187. It contains no user code. Use it to compare performance; it
isn't a coding-quality evaluation.

- UTF-8 bytes: 209,210.
- SHA256: `aeda010d0d3be31901137b5425b130d8ab39e7a45d0c6b64e6a42521234c7c7e`.
- Recorded chat prompt usage with the pinned model/tokenizer: 48,345 tokens.
- Recorded benchmark output budget: 512 tokens per request.

Results record usage, hash and salts. Keep this fixture unchanged; give new
prompts new filenames and hashes. This project-generated fixture uses the
recipe's Apache-2.0 license.
