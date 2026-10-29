"""Single-instrument failures injected into the TE replay, for testing what the screens show when one device lies.

The replay (te_sim_server.py) plays back recorded data, so these failures change what one tag reports, never what the
"plant" does in response. Each failure is a line in the replay's control file, after the optional run line:

    fault6 250                      (optional: switch the recorded run, as before)
    freeze PT-107                   value held at what it read when the failure started; quality stays Good
    fixed LT-108 100                value pinned (a transmitter failed high or low); quality stays Good
    drift TT-109 0.05               adds 0.05 per sample, cumulative (calibration drift); quality stays Good
    noise FT-114 2.0                adds Gaussian noise with this standard deviation (seeded, repeatable)
    bad TT-121                      quality BadCommunicationError on this tag only; the value is not updated
    stale LT-112                    the tag is no longer written at all: old value, old timestamp, last quality

Removing a line clears that failure; an empty control file (or only a run line) clears them all. A failure on a tag
the replay doesn't serve is refused with a message, never silently ignored.

Stdlib only; the replay server applies the result.
"""
import random

KINDS = {"freeze": 0, "fixed": 1, "drift": 1, "noise": 1, "bad": 0, "stale": 0}


class FailureError(ValueError):
    pass


def parse(lines, known_tags):
    """Control-file lines (run line excluded) -> {tag: (kind, arg)}. Raises FailureError on any bad line."""
    out = {}
    for n, raw in enumerate(lines, 1):
        parts = raw.split("#", 1)[0].split()
        if not parts:
            continue
        kind = parts[0]
        if kind not in KINDS:
            raise FailureError(f"line {n}: unknown failure '{kind}' (one of {', '.join(KINDS)})")
        if len(parts) != 2 + KINDS[kind]:
            raise FailureError(f"line {n}: '{kind}' takes a tag{' and a number' if KINDS[kind] else ''}")
        tag = parts[1]
        if tag not in known_tags:
            raise FailureError(f"line {n}: the replay serves no tag '{tag}'")
        if tag in out:
            raise FailureError(f"line {n}: '{tag}' already has a failure")
        arg = None
        if KINDS[kind]:
            try:
                arg = float(parts[2])
            except ValueError:
                raise FailureError(f"line {n}: '{parts[2]}' is not a number") from None
        out[tag] = (kind, arg)
    return out


class Injector:
    """Turns each recorded value into what the failed instrument reports. Keeps per-tag state between samples."""

    def __init__(self, seed=20261029):
        self.active = {}
        self.state = {}
        self.rng = random.Random(seed)

    def set(self, failures):
        """Replace the active failures; a failure that continues keeps its state, a new one starts fresh."""
        for tag in list(self.state):
            if tag not in failures or failures[tag] != self.active.get(tag):
                del self.state[tag]
        self.active = dict(failures)

    def apply(self, tag, recorded):
        """-> ("write", value, good) or ("skip", None, None). good=False means write Bad quality."""
        if tag not in self.active:
            return "write", recorded, True
        kind, arg = self.active[tag]
        if kind == "stale":
            return "skip", None, None
        if kind == "bad":
            return "write", None, False
        if kind == "freeze":
            value = self.state.setdefault(tag, recorded)
        elif kind == "fixed":
            value = arg
        elif kind == "drift":
            steps = self.state.get(tag, 0) + 1
            self.state[tag] = steps
            value = recorded + arg * steps
        else:  # noise
            value = recorded + self.rng.gauss(0.0, arg)
        return "write", value, True
