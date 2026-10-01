#!/usr/bin/env python3
"""Pure gating tests for the AirPods sidetone supervisor.

Cases: inactive, muted, disconnected, ownstream, wrongtarget, filters-only,
positive. No system calls — fixtures only.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sidetone import SRC, evaluate_gate  # noqa: E402


def base_outputs():
    return [
        {"node_name": "capture.voice_chain", "application_name": None, "pid": None,
         "monitor": False, "internal": True, "corked": False, "target": SRC},
        {"node_name": "sidetone-capture", "application_name": "pw-loopback", "pid": "1",
         "monitor": False, "internal": True, "corked": False, "target": SRC},
    ]


def snap(outputs=None, present=True, mute=False, sink=True):
    return {"source": {"name": SRC, "present": present, "mute": mute},
            "sink_present": sink,
            "source_outputs": outputs if outputs is not None else []}


def chromium(target=SRC, corked=False):
    return {"node_name": "Chromium input", "application_name": "Chromium input",
            "pid": "206879", "monitor": False, "internal": False,
            "corked": corked, "target": target}


CASES = []


def case(name, fn):
    CASES.append((name, fn))


case("inactive(no clients)", lambda: (snap(base_outputs()), False, "no_other_real_capture"))
case("muted(source mute)", lambda: (
    snap(base_outputs() + [chromium()], mute=True), False, "source_muted"))
case("disconnected(source gone)", lambda: (
    snap([], present=False), False, "source_disconnected"))
case("ownstream(only ours+filter)", lambda: (
    snap(base_outputs()), False, "no_other_real_capture"))
case("wrongtarget(client on other mic)", lambda: (
    snap(base_outputs() + [chromium(target="alsa_input.usb-other")]), False,
    "no_other_real_capture"))
case("filters-only(monitor+internal)", lambda: (
    snap([{"node_name": "quickshell", "application_name": "quickshell", "pid": "9",
           "monitor": True, "internal": False, "corked": False, "target": SRC},
          {"node_name": "bluez_capture_internal", "application_name": None, "pid": None,
           "monitor": False, "internal": True, "corked": False, "target": SRC}]), False,
    "no_other_real_capture"))
case("corked(client not active)", lambda: (
    snap(base_outputs() + [chromium(corked=True)]), False, "no_other_real_capture"))
case("positive(real client captures)", lambda: (
    snap(base_outputs() + [chromium(), chromium()]), True, None))


def run_case(name, fn):
    """Evaluate one gating case. Returns (ok, got). Shared by pytest and main()."""
    s, want_run, want_reason = fn()
    got = evaluate_gate(s)
    ok = got["run"] == want_run and (want_reason is None or want_reason in got["reasons"])
    if want_run and len(got["real_clients"]) != 2:
        ok = False
    return ok, got


def main():
    failed = 0
    for name, fn in CASES:
        ok, got = run_case(name, fn)
        print("%-34s run=%-5s reasons=%-28s clients=%d  %s"
              % (name, got["run"], ",".join(got["reasons"]) or "-", len(got["real_clients"]),
                 "PASS" if ok else "FAIL"))
        if not ok:
            failed += 1
    print("\n%d/%d passed" % (len(CASES) - failed, len(CASES)))
    return 1 if failed else 0


try:
    import pytest
except ModuleNotFoundError:  # direct `python tests/test_gate.py` needs no test runner
    pytest = None

if pytest is not None:
    # CI runs `pytest -v`; the case table above is not pytest-shaped on its own,
    # so expose it as one parametrized test. A collecting pytest always exits
    # non-zero on failure, which the standalone main() path could not guarantee.
    @pytest.mark.parametrize("name,fn", CASES, ids=[c[0].split("(")[0] for c in CASES])
    def test_gate(name, fn):
        ok, got = run_case(name, fn)
        assert ok, ("%s: run=%s reasons=%s clients=%d"
                    % (name, got["run"], ",".join(got["reasons"]) or "-",
                       len(got["real_clients"])))


if __name__ == "__main__":
    sys.exit(main())
