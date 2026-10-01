#!/usr/bin/env python3
"""AirPods Max sidetone — minimal supervised pw-loopback with a hard -18 dB start.

Gain: 0.125 amplitude = -18.06 dB. Bounded controls: [0.02 .. 0.125].

Gate (loopback runs ONLY while ALL hold, checked every cycle):
  - source  bluez_input.<ADDR>  present and not muted
  - sink    bluez_output.<ADDR with _>.1  present
  - >= 1 OTHER real active capture client on the source.
    Excluded (never counted): our own sidetone streams, passive
    monitors (stream.monitor), internal/virtual nodes (node.virtual,
    media.class .../Internal), filter-chain capture streams
    (capture.* / rnnoise_source), corked streams.

Routing is fully manual and has NO fallback path: both loopback streams
are created with node.autoconnect=false + node.dont-reconnect=true, then
wired with pw-link to exactly:
  bluez_input.<ADDR>:capture_MONO -> sidetone-capture:input_MONO
  sidetone-playback:output_MONO -> bluez_output.<ADDR with _>.1:playback_MONO
Never touches speakers/other mics. Supervisor re-verifies the exact link
set every cycle and restarts from scratch on any drift.

Params used (documented in pipewire-props(7), matching local 1.6.8 man):
  channelmix.max-volume = 0.125   ("Any volume that is set will be clamped")
  node.param.Props = { volume }   (initial Props param, pw-cli-equivalent)
Supervisor also re-reads the playback Props volume every cycle and
re-applies the bounded level if it ever reads above the cap.

Commands:  sidetone on | off | status [--json] | level <x> | supervise
"""
import argparse
import json
import math
import os
import re
import signal
import subprocess
import time

PLACEHOLDER_ADDR = "AA:BB:CC:DD:EE:FF"
BT_ADDR = os.environ.get("SIDETONE_BT_ADDR", PLACEHOLDER_ADDR).strip().upper()
if not re.fullmatch(r"[0-9A-F]{2}(:[0-9A-F]{2}){5}", BT_ADDR):
    raise SystemExit("SIDETONE_BT_ADDR must look like AA:BB:CC:DD:EE:FF, got %r" % BT_ADDR)
SRC = "bluez_input." + BT_ADDR
SNK = "bluez_output.%s.1" % BT_ADDR.replace(":", "_")
CAP_NODE = "sidetone-capture"
PLAY_NODE = "sidetone-playback"
CAP = 0.125                 # channelmix.max-volume hard cap == -18.06 dB
LEVEL_MIN = 0.02
INTERVAL = 2.0
UNIT = "airpods-sidetone.service"

PW_LOOPBACK = "/usr/bin/pw-loopback"
PW_LINK = "/usr/bin/pw-link"
PW_CLI = "/usr/bin/pw-cli"
PW_DUMP = "/usr/bin/pw-dump"
PACTL = "/usr/bin/pactl"

STATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state")
STATE_FILE = os.path.join(STATE_DIR, "state.json")

NONREAL_NAMES = {"capture.voice_chain", "rnnoise_source"}


def log(msg):
    print("[%s] %s" % (time.strftime("%H:%M:%S"), msg), flush=True)


def run(cmd, timeout=10):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def jcmd(cmd):
    r = run(cmd)
    if r.returncode != 0:
        raise RuntimeError("%s failed rc=%d: %s" % (cmd[0], r.returncode, r.stderr.strip()))
    return json.loads(r.stdout)


def pw_dump():
    return json.loads(run([PW_DUMP]).stdout)


def node_id(name, dump=None):
    d = dump if dump is not None else pw_dump()
    for o in d:
        if o.get("type") == "PipeWire:Interface:Node":
            if o.get("info", {}).get("props", {}).get("node.name") == name:
                return o.get("id")
    return None


def read_volume(name):
    nid = node_id(name)
    if nid is None:
        return None
    r = run([PW_CLI, "e", str(nid), "Props"])
    m = re.search(r"Props:volume[^\n]*\n\s*Float\s+([0-9.eE+-]+)", r.stdout)
    return float(m.group(1)) if m else None


def set_volume(name, v):
    nid = node_id(name)
    if nid is None:
        return False
    r = run([PW_CLI, "s", str(nid), "Props", '{ "volume": %.6f }' % v])
    return r.returncode == 0


# ---------------------------------------------------------------- snapshot

def snapshot():
    """Read-only state snapshot (pure data, everything else derives from it)."""
    sources = jcmd([PACTL, "-f", "json", "list", "sources"])
    sinks = jcmd([PACTL, "-f", "json", "list", "sinks"])
    outs = jcmd([PACTL, "-f", "json", "list", "source-outputs"])
    by_idx = {s.get("index"): s for s in sources}
    src = next((s for s in sources if s.get("name") == SRC), None)
    outputs = []
    for o in outs:
        p = o.get("properties") or {}
        tgt = by_idx.get(o.get("source")) or {}
        outputs.append({
            "node_name": p.get("node.name") or p.get("application.name") or "?",
            "application_name": p.get("application.name"),
            "pid": p.get("application.process.id"),
            "monitor": str(p.get("stream.monitor", "")).lower() in ("true", "1", "yes"),
            "internal": ("Internal" in (p.get("media.class") or "")) or
                        (str(p.get("node.virtual", "")).lower() in ("true", "1", "yes")),
            "corked": bool(o.get("corked")),
            "target": tgt.get("name"),
        })
    return {
        "source": {"name": SRC, "present": src is not None,
                   "mute": bool(src and src.get("mute"))},
        "sink_present": any(s.get("name") == SNK for s in sinks),
        "source_outputs": outputs,
    }


def evaluate_gate(snap):
    """Pure gate: decide run/stop from a snapshot dict (no system access)."""
    reasons = []
    if not snap["source"]["present"]:
        reasons.append("source_disconnected")
    elif snap["source"]["mute"]:
        reasons.append("source_muted")
    if not snap["sink_present"]:
        reasons.append("sink_missing")
    real = []
    for o in snap["source_outputs"]:
        if o.get("target") != SRC:
            continue
        if o.get("corked") or o.get("monitor") or o.get("internal"):
            continue
        n = o.get("node_name") or ""
        if n.startswith("sidetone") or n in NONREAL_NAMES or n.startswith("capture."):
            continue
        real.append(o)
    if not real:
        reasons.append("no_other_real_capture")
    return {
        "run": not reasons,
        "reasons": reasons,
        "real_clients": [{"node": o["node_name"], "pid": o.get("pid")} for o in real],
    }


# ---------------------------------------------------------------- routing

def verify_routing():
    d = pw_dump()
    ids = {}
    for o in d:
        if o.get("type") == "PipeWire:Interface:Node":
            nm = o.get("info", {}).get("props", {}).get("node.name")
            if nm in (SRC, SNK, CAP_NODE, PLAY_NODE):
                ids[nm] = o.get("id")
    missing = [n for n in (SRC, SNK, CAP_NODE, PLAY_NODE) if n not in ids]
    if missing:
        return {"ok": False, "missing_nodes": missing, "links": [], "extra": []}
    want = {(ids[SRC], ids[CAP_NODE]), (ids[PLAY_NODE], ids[SNK])}
    found, extra = set(), []
    for link in d:
        if link.get("type") != "PipeWire:Interface:Link":
            continue
        i = link.get("info", {})
        pair = (i.get("output-node-id"), i.get("input-node-id"))
        if ids[CAP_NODE] in pair or ids[PLAY_NODE] in pair:
            if pair in want:
                found.add(pair)
            else:
                extra.append({"out": pair[0], "in": pair[1]})
    ok = found == want and not extra
    return {"ok": ok, "links_present": len(found), "extra": extra, "missing_nodes": missing}


# ---------------------------------------------------------------- loopback life

def _cleanup_stale_nodes():
    for n in (CAP_NODE, PLAY_NODE):
        nid = node_id(n)
        if nid:
            run([PW_CLI, "destroy", str(nid)])
    time.sleep(0.2)


def start_loopback(level):
    _cleanup_stale_nodes()
    cap_props = {
        "node.name": CAP_NODE,
        "node.description": "AirPods sidetone capture (mic)",
        "node.autoconnect": False,
        "node.dont-reconnect": True,
    }
    play_props = {
        "node.name": PLAY_NODE,
        "node.description": "AirPods sidetone (quiet, -18 dB cap)",
        "node.autoconnect": False,
        "node.dont-reconnect": True,
        "channelmix.max-volume": CAP,
        "node.param.Props": {"volume": level},
    }
    cmd = [PW_LOOPBACK, "-n", "airpods-sidetone", "-c", "1", "-m", "[ MONO ]",
           "-i", json.dumps(cap_props), "-o", json.dumps(play_props)]
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    t0 = time.time()
    while time.time() - t0 < 5:
        if proc.poll() is not None:
            raise RuntimeError("pw-loopback exited rc=%s" % proc.returncode)
        if node_id(CAP_NODE) is not None and node_id(PLAY_NODE) is not None:
            break
        time.sleep(0.25)
    else:
        stop_loopback(proc)
        raise RuntimeError("loopback nodes did not appear")
    # Enforce bounded gain BEFORE any link exists (nothing audible yet).
    set_volume(PLAY_NODE, level)
    v = read_volume(PLAY_NODE)
    if v is None or v > CAP + 1e-6:
        stop_loopback(proc)
        raise RuntimeError("gain readback %s exceeds cap %s" % (v, CAP))
    # Wire the exact two links only; any failure tears everything down.
    r1 = run([PW_LINK, "%s:capture_MONO" % SRC, "%s:input_MONO" % CAP_NODE])
    r2 = run([PW_LINK, "%s:output_MONO" % PLAY_NODE, "%s:playback_MONO" % SNK])
    if r1.returncode or r2.returncode:
        stop_loopback(proc)
        raise RuntimeError("pw-link failed: %s %s" % (r1.stderr.strip(), r2.stderr.strip()))
    rv = verify_routing()
    if not rv["ok"]:
        stop_loopback(proc)
        raise RuntimeError("routing verify failed: %s" % rv)
    return proc


def stop_loopback(proc):
    if proc is None:
        return
    try:
        proc.terminate()
        proc.wait(timeout=3)
    except Exception:
        try:
            proc.kill()
            proc.wait(timeout=2)
        except Exception:
            pass
    t0 = time.time()
    while time.time() - t0 < 3:
        if node_id(CAP_NODE) is None and node_id(PLAY_NODE) is None:
            return
        time.sleep(0.25)
    for n in (CAP_NODE, PLAY_NODE):
        nid = node_id(n)
        if nid:
            run([PW_CLI, "destroy", str(nid)])


# ---------------------------------------------------------------- state

def read_level():
    try:
        with open(STATE_FILE) as f:
            v = float(json.load(f).get("level", CAP))
    except Exception:
        v = CAP
    return max(LEVEL_MIN, min(CAP, v))


def write_level(v):
    ensure_state_dir()
    v = max(LEVEL_MIN, min(CAP, float(v)))
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump({"level": v, "cap": CAP,
                   "note": "bounded [0.02..0.125]; 0.125 == -18.06 dB"}, f)
    os.replace(tmp, STATE_FILE)
    return v


def ensure_state_dir():
    os.makedirs(STATE_DIR, exist_ok=True)


# ---------------------------------------------------------------- supervisor

def supervise(interval=INTERVAL):
    proc = None
    applied = None
    stopping = {"v": False}

    def _h(signum, frame):
        stopping["v"] = True

    signal.signal(signal.SIGTERM, _h)
    signal.signal(signal.SIGINT, _h)
    log("supervisor started (interval %.1fs, cap %.3f = %.1f dB)"
        % (interval, CAP, 20 * math.log10(CAP)))
    while not stopping["v"]:
        level = read_level()
        try:
            snap = snapshot()
            gate = evaluate_gate(snap)
        except Exception as e:
            log("snapshot failed: %s -> fail-closed" % e)
            if proc is not None and proc.poll() is None:
                stop_loopback(proc)
            proc, applied = None, None
            time.sleep(interval)
            continue
        if gate["run"]:
            if proc is None or proc.poll() is not None:
                proc, applied = None, None
                try:
                    proc = start_loopback(level)
                    applied = level
                    log("loopback STARTED level=%.3f clients=%s" % (level, gate["real_clients"]))
                except Exception as e:
                    log("start failed: %s" % e)
            else:
                if applied != level:
                    set_volume(PLAY_NODE, level)
                    applied = level
                    log("level applied %.3f" % level)
                v = read_volume(PLAY_NODE)
                if v is None or v > CAP + 1e-6:
                    set_volume(PLAY_NODE, level)
                    v = read_volume(PLAY_NODE)
                    log("gain reconciled -> %s" % v)
                    if v is None or v > CAP + 1e-6:
                        stop_loopback(proc)
                        proc, applied = None, None
                        log("gain unenforceable -> stopped")
                        time.sleep(interval)
                        continue
                rv = verify_routing()
                if not rv["ok"]:
                    log("routing drift -> stopping from scratch: %s" % rv)
                    stop_loopback(proc)
                    proc, applied = None, None
        else:
            if proc is not None:
                stop_loopback(proc)
                proc, applied = None, None
                log("loopback STOPPED reasons=%s" % gate["reasons"])
        time.sleep(interval)
    if proc is not None:
        stop_loopback(proc)
    log("supervisor stopped, loopback cleaned up")


# ---------------------------------------------------------------- CLI

def gather_status():
    st = {}
    st["service_active"] = run(["systemctl", "--user", "is-active", UNIT]).stdout.strip()
    st["service_enabled"] = run(["systemctl", "--user", "is-enabled", UNIT]).stdout.strip()
    try:
        snap = snapshot()
        st["gate"] = evaluate_gate(snap)
        st["source"] = snap["source"]
    except Exception as e:
        st["gate"] = {"run": None, "reasons": ["snapshot_error: %s" % e], "real_clients": []}
    st["routing"] = verify_routing()
    cap_id = node_id(CAP_NODE)
    play_id = node_id(PLAY_NODE)
    st["loopback_running"] = cap_id is not None and play_id is not None
    st["level"] = read_level()
    st["cap"] = CAP
    st["playback_volume"] = read_volume(PLAY_NODE) if play_id else None
    return st


def fmt_state(st):
    if st["loopback_running"]:
        return "RUNNING"
    if st.get("gate", {}).get("run"):
        return "ARMED (gate open, starting)"
    return "ARMED (gate closed)"


def cmd_status(args):
    st = gather_status()
    if getattr(args, "json", False):
        print(json.dumps(st, indent=2))
        return
    print("service: %s (enabled=%s)  unit=%s" % (st["service_active"], st["service_enabled"], UNIT))
    print("state:   %s" % fmt_state(st))
    g = st.get("gate", {})
    print("gate:    run=%s reasons=%s" % (g.get("run"), g.get("reasons")))
    if g.get("real_clients"):
        print("clients: %s" % g["real_clients"])
    r = st["routing"]
    print("route:   ok=%s links_present=%s extra=%s missing=%s"
          % (r.get("ok"), r.get("links_present"), r.get("extra"), r.get("missing_nodes")))
    if st["playback_volume"] is not None:
        print("gain:    playback=%.3f (%.1f dB)  cap=%.3f (%.1f dB)  level=%.3f"
              % (st["playback_volume"], 20 * math.log10(st["playback_volume"]),
                 CAP, 20 * math.log10(CAP), st["level"]))
    else:
        print("gain:    loopback not running  cap=%.3f (%.1f dB)  level=%.3f"
              % (CAP, 20 * math.log10(CAP), st["level"]))


def require_configured():
    if BT_ADDR == PLACEHOLDER_ADDR:
        raise SystemExit("Set SIDETONE_BT_ADDR to your headset's Bluetooth address (see `bluetoothctl devices`).")


def cmd_on(args):
    require_configured()
    write_level(read_level())  # ensure state file exists
    subprocess.run(["systemctl", "--user", "enable", "--now", UNIT], capture_output=True, text=True)
    time.sleep(2.5)
    cmd_status(argparse.Namespace(json=False))


def cmd_off(args):
    subprocess.run(["systemctl", "--user", "disable", "--now", UNIT], capture_output=True, text=True)
    time.sleep(1.5)
    subprocess.run(["systemctl", "--user", "reset-failed", UNIT], capture_output=True, text=True)
    pg = run(["pgrep", "-f", "[p]w-loopback -n airpods-sidetone"])
    cap_id = node_id(CAP_NODE)
    play_id = node_id(PLAY_NODE)
    print("service: %s (enabled=%s)" % (run(["systemctl", "--user", "is-active", UNIT]).stdout.strip(),
                                        run(["systemctl", "--user", "is-enabled", UNIT]).stdout.strip()))
    print("loopback process: %s" % ("STILL RUNNING pid %s" % pg.stdout.strip() if pg.stdout.strip() else "none"))
    print("sidetone nodes: %s" % ("STILL PRESENT" if (cap_id or play_id) else "none"))
    print("off done: no capture past Discord/voice clients, nothing forces HFP")


def cmd_level(args):
    v = write_level(args.value)
    if v != float(args.value):
        print("clamped to bounded range: %.3f" % v)
    if node_id(PLAY_NODE):
        set_volume(PLAY_NODE, v)
    rb = read_volume(PLAY_NODE)
    db = ("%.1f dB" % (20 * math.log10(rb))) if rb else "n/a"
    print("level: %.3f (%s) readback=%s cap=%.3f (%s)"
          % (v, db if rb else "not running", ("%.3f" % rb) if rb is not None else "n/a",
             CAP, "%.1f dB" % (20 * math.log10(CAP))))


def cmd_supervise(args):
    require_configured()
    supervise()


def main(argv=None):
    ap = argparse.ArgumentParser(prog="sidetone", description="AirPods Max sidetone (supervised, -18 dB cap)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("on", help="enable + start supervision (gate controls the loopback)")
    sub.add_parser("off", help="stop + disable supervision, clean up loopback")
    sp = sub.add_parser("status", help="show gate, routing, gain readback")
    sp.add_argument("--json", action="store_true")
    sp = sub.add_parser("level", help="bounded level control [0.02..0.125], 0.125 == -18 dB")
    sp.add_argument("value", type=float)
    sub.add_parser("supervise", help="run supervisor loop (used by the systemd unit)")
    a = ap.parse_args(argv)
    {"on": cmd_on, "off": cmd_off, "status": cmd_status,
     "level": cmd_level, "supervise": cmd_supervise}[a.cmd](a)


if __name__ == "__main__":
    main()
