# Successful scripts can still have missing checks

The runner now distinguishes successful script exits from complete coverage. A source cache can be absent while
the tests that can run all pass. That outcome needs a visible omission, not a complete-suite claim.

Run this small example from a clean clone, offline, with Python 3.10+ and no packages:

```sh
python -S examples/test-coverage/demonstrate.py --check
```

It executes four **illustrative child programs** through the real runner. Only test selection and prerequisite
discovery are replaced for these fixtures; child processes actually run. No source cache is fetched or edited.
The expected counts are declared from the authored test cases before comparison:

| Child | Exit | Unittest cases skipped | Platform notices | Additional skipped-check notices | Complete-suite message |
|---|---:|---:|---:|---:|---|
| All checks execute | 0 | 0 | 0 | 0 | Yes |
| Class, method and subtest skips, summary on stdout | 0 | 4 | 0 | 0 | No |
| Simulated platform restriction and extra check group | 0 | 1 | 1 | 1 | No |
| A failure and a skipped method, summary on stderr | 1 | 1 | 0 | 0 | No |

[expected.json](expected.json) records the reproducible results. The simulated platform case is explicitly a
fixture, not a claim about this machine's permissions. A platform notice explains a unittest skip and is not
added to that case count. Additional notices describe individual checks or groups; they are not a second unit-test
denominator. The failure control proves a nonzero exit stays a failure even when another case is skipped.

The production runner reads unittest's `OK`/`FAILED` skipped counts from both streams and explicit `SKIP` notices.
It does not infer omissions from ordinary prose containing the word “skipped”. Run an affected unittest script
with `-v` to see its case identities and reasons. The runner reports what child programs say: it cannot detect
an arbitrary test program that silently returns without checking anything or fabricates a report. The DEXPI oracle's
known early-return case was changed to a genuine unittest skip.

For the actual repository, use [the reviewer guide](../../docs/REVIEWING.md). Required missing prerequisites stop
before tests; optional source checks can skip and now prevent a complete-suite message. A successful prerequisite
check, a successful script exit and a complete selected suite are different evidence. Source-only remains a narrower
selection. None establishes drawing accuracy, engineering approval or runtime acceptance.
