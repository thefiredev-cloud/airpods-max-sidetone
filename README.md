# airpods-sidetone

## What it is

A Python 3 stdlib supervisor that runs a volume-clamped PipeWire `pw-loopback` sidetone path for AirPods Max on Linux, only while another real capture client is using the headset mic.

## Why it exists

Linux AirPods Max have no native sidetone. An always-on loopback either stays silent, routes to the wrong nodes, or gets too loud; this process gates the loopback and clamps gain.

## How to run it

Runtime: Python 3, system PipeWire (`/usr/bin/pw-loopback`, `pw-link`, `pw-cli`, `pw-dump`, `pactl`). No PyPI deps.

Set your headset's Bluetooth address first. Find it with `bluetoothctl devices`.

```bash
export SIDETONE_BT_ADDR=AA:BB:CC:DD:EE:FF   # your AirPods Max
python3 sidetone.py status
```

Install the user service once. Edit the address in the unit, then:

```bash
mkdir -p ~/.config/systemd/user
sed "s|@REPO@|$PWD|" systemd/airpods-sidetone.service > ~/.config/systemd/user/airpods-sidetone.service
$EDITOR ~/.config/systemd/user/airpods-sidetone.service   # set SIDETONE_BT_ADDR
systemctl --user daemon-reload
```

Then, on a box where the AirPods Max BlueZ nodes exist:

```bash
python3 sidetone.py on
python3 sidetone.py status
python3 sidetone.py off
```

Commands: `on` | `off` | `status [--json]` | `level <0.02..0.125>` | `supervise`.

`on` enables the user unit `airpods-sidetone.service` and starts supervision. `supervise` is the loop that unit runs. Gain is clamped to amplitude `0.02`–`0.125` (`0.125` = −18.06 dB via `channelmix.max-volume`).

The `./sidetone` shim runs `sidetone.py` from the directory it lives in.

The BlueZ node names are built from `SIDETONE_BT_ADDR` (`bluez_input.<ADDR>` and `bluez_output.<ADDR with underscores>.1`). There is no fallback route to speakers or other mics. The state file `state/state.json` is created on first use and is not tracked.

## In scope / out of scope

In scope:

- Gate: source present and unmuted, sink present, at least one other real capture client.
- Manual `pw-link` with `node.autoconnect=false`.
- User systemd enable/disable of `airpods-sidetone.service`.
- Bounded level writes under `state/state.json`.

Out of scope:

- Network, telemetry, or non-stdlib Python.
- Generic Bluetooth headsets (the node names and the one-headset gate are written for an AirPods Max pair; other headsets are untested).
- Forcing HFP when nothing is capturing.

## Current production URL

Not deployed.

## Status

live
