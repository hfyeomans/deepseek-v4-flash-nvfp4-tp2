# Documentation checks

Compared with release checkpoint `0b67089`, the 41 existing documentation files
went from 28,716 to 22,527 words: about 22% shorter, including unchanged tables
and code blocks. Excluding protected blocks, prose is about 26% shorter. These
counts exclude this new task folder.

Checks confirmed:

- All 230 table lines, 33 fenced blocks, headings and inline literals are unchanged.
- Original link destinations are retained; local targets and anchors resolve.
- All 133 tracked non-documentation files are byte-identical, including code,
  raw results, fixtures, patches and licenses.
- No numeric value was added to or removed from the existing documentation set.
  Historical samples, startup warnings, K5 constraints and untested limits remain.
- Git whitespace checks pass. Benchmark termination wording matches the existing
  client's length/usage checks and explicit stream-error handling.

Review covered README, guides, research/state notes and patch/fixture docs.
The historical regression note under results was read and preserved as evidence.
No GPU tests or deployments ran for this prose edit. GitHub visibility was
checked as private before saving the review branch.
