"""Exercise the Dockerfile's patch options against real temporary files."""
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest


DOCKERFILE = Path(__file__).resolve().parents[1] / 'Dockerfile.dspark'
PATCH = '--- a/runtime.txt\n+++ b/runtime.txt\n@@ -1 +1 @@\n-before\n+after\n'


class PatchDirectionTest(unittest.TestCase):
    def test_runtime_patch_commands_reject_repeat_without_reversing(self):
        commands = [
            shlex.split(line.removeprefix('RUN ').removesuffix('\\'))
            for line in DOCKERFILE.read_text().splitlines()
            if line.startswith('RUN patch ')
        ]
        self.assertEqual(len(commands), 3)
        for command in commands:
            with self.subTest(patch=command[-1]), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                target = root / 'runtime.txt'
                target.write_text('before\n')
                arguments = command[:command.index('<')]
                arguments[arguments.index('-d') + 1] = str(root)
                first = subprocess.run(arguments, input=PATCH, text=True, capture_output=True)
                self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
                self.assertEqual(target.read_text(), 'after\n')

                repeated = subprocess.run(arguments, input=PATCH, text=True, capture_output=True)
                self.assertEqual(
                    (repeated.returncode == 0, target.read_text()),
                    (False, 'after\n'),
                    repeated.stdout + repeated.stderr,
                )


if __name__ == '__main__':
    unittest.main(verbosity=2)
