"""Platform capability checks shared by tests. Stdlib only.

A test may skip a sub-case ONLY when the operating system refuses the fixture it needs, never when the code under
test misbehaves. Each skip prints "SKIP [platform] " that scripts/run_tests.py surfaces separately from unittest's
skipped-case totals, so the same skipped case is not counted twice and a
platform gap can never pass silently.
"""
import os
import sys

WINDOWS_PRIVILEGE_NOT_HELD = 1314  # ERROR_PRIVILEGE_NOT_HELD: creating a symlink needs SeCreateSymbolicLinkPrivilege


def symlink_or_skip(test, link, target, target_is_directory=False):
    """Create link -> target, or skip `test` (a unittest.TestCase) if this Windows account may not create symlinks.

    Any other failure, and any failure off Windows, is raised: the control must run wherever symlinks exist.
    """
    try:
        os.symlink(target, link, target_is_directory)
    except OSError as error:
        if os.name == "nt" and getattr(error, "winerror", None) == WINDOWS_PRIVILEGE_NOT_HELD:
            reason = (f"{test.id()}: this Windows account cannot create symlinks (WinError 1314, "
                      "SeCreateSymbolicLinkPrivilege). Enable Developer Mode or run elevated to exercise it; "
                      "Linux/macOS CI always runs it.")
            print("\nSKIP [platform] " + reason, file=sys.stderr, flush=True)  # own line: unittest's dots share stderr
            test.skipTest(reason)
        raise
