# airpods-max-sidetone

[![CI](https://github.com/thefiredev-cloud/airpods-max-sidetone/actions/workflows/ci.yml/badge.svg)](https://github.com/thefiredev-cloud/airpods-max-sidetone/actions/workflows/ci.yml)

A small Python supervisor that gives AirPods Max sidetone (hearing your own voice) on Linux. It runs a volume-capped PipeWire `pw-loopback` from the headset mic to the headset, and only while another app is actually capturing the mic.

## Why it exists

AirPods Max have no sidetone on Linux. A plain always-on loopback either stays silent, links to the wrong devices, or gets too loud. This tool gates the loopback on real mic use and clamps the gain.

## Requirements

- Linux with PipeWire and BlueZ
- Python 3 (standard library only; CI uses 3.11)
- PipeWire tools on `PATH`: `pw-loopback`, `pw-link`, `pw-cli`, `pw-dump`, `pactl`
- A systemd user session, for the supervised service

## Install

Find your headset's Bluetooth address with `bluetoothctl devices`, then:

```bash
git clone https://github.com/thefiredev-cloud/airpods-max-sidetone.git
cd airpods-max-sidetone
export SIDETONE_BT_ADDR=AA:BB:CC:DD:EE:FF   # your AirPods Max
python3 sidetone.py status
```

Install the user service once, then set the address in the unit:

```bash
mkdir -p ~/.config/systemd/user
sed "s|@REPO@|$PWD|" systemd/airpods-sidetone.service > ~/.config/systemd/user/airpods-sidetone.service
$EDITOR ~/.config/systemd/user/airpods-sidetone.service   # set SIDETONE_BT_ADDR
systemctl --user daemon-reload
```

## Usage

```bash
python3 sidetone.py on        # enable the user service and start supervision
python3 sidetone.py status    # add --json for machine-readable output
python3 sidetone.py level 0.05
python3 sidetone.py off
```

| Command | Effect |
|---|---|
| `on` | Enables and starts `airpods-sidetone.service`; the gate then controls the loopback |
| `off` | Stops and disables the service and cleans up the loopback |
| `status [--json]` | Shows the service state, gate decision, routing, and gain readback |
| `level <0.02..0.125>` | Sets the loopback amplitude; `0.125` is about -18 dB (`channelmix.max-volume`) |
| `supervise` | The loop the service runs |

The `./sidetone` shim runs `sidetone.py` from its own directory.

## How the gate works

The loopback runs only when all of these hold: the headset source exists and is unmuted, the headset sink exists, and at least one other real capture client is using the mic. Links are made by hand with `pw-link` and `node.autoconnect=false`, so audio never falls back to speakers or another mic.

Node names come from `SIDETONE_BT_ADDR`: `bluez_input.<ADDR>` and `bluez_output.<ADDR with underscores>.1`. The level is stored in `state/state.json`, created on first use and ignored by git.

## Tests

```bash
pip install pytest ruff
ruff check .
pytest -v
```

CI runs the same checks on pushes and pull requests to `main`. The tests cover the gate logic and do not need a headset.

## Scope

In scope: one AirPods Max pair, gated loopback, bounded level, user systemd control.

Out of scope: network access, telemetry, third-party Python packages, other Bluetooth headsets (untested), and forcing the HFP profile when nothing is capturing.

## Status

Working. Not packaged.

## License

MIT. See [LICENSE](LICENSE).
