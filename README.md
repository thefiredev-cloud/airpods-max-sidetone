# airpods-max-sidetone

[![CI](https://github.com/thefiredev-cloud/airpods-max-sidetone/actions/workflows/ci.yml/badge.svg)](https://github.com/thefiredev-cloud/airpods-max-sidetone/actions/workflows/ci.yml)

A small Python supervisor that gives AirPods Max sidetone (hearing your own voice while you talk) on Linux with PipeWire. It is for people who use AirPods Max as a Bluetooth headset on a desktop and want a quiet mic-to-ear loopback that only runs during calls or recordings.

Status: a single-file utility with no dependencies beyond the standard library. The gate logic has unit tests. Live PipeWire routing, gain enforcement and the systemd unit have no automated tests.

It does not switch Bluetooth profiles, change default devices, route to any speaker other than the headset, or touch the network.

## What it does

The script `sidetone.py` runs a PipeWire `pw-loopback` from the headset microphone to the headset speakers. It keeps that loopback alive only while another application is actually capturing from the headset mic, and it caps the loopback gain at 0.125 amplitude (about -18 dB).

### The sidetone loop

1. The supervisor sleeps 2 seconds between cycles. Each cycle it takes a read-only snapshot of PipeWire through `pactl`: the headset source, the headset sink, and every active capture stream.
2. A pure gate function decides whether the loopback should run. It runs only when all of these hold:
   - the headset source exists and is not muted,
   - the headset sink exists,
   - at least one other real capture client is recording from the headset source.
3. When the gate opens, the supervisor starts `pw-loopback` with two mono streams, `sidetone-capture` and `sidetone-playback`. Both are created with `node.autoconnect=false` and `node.dont-reconnect=true`, so PipeWire never wires them anywhere on its own.
4. The supervisor sets the playback volume, reads it back, and refuses to continue if the readback is above the cap. Only then does it link exactly two ports with `pw-link`:
   - `bluez_input.<ADDR>:capture_MONO` to `sidetone-capture:input_MONO`
   - `sidetone-playback:output_MONO` to `bluez_output.<ADDR with underscores>.1:playback_MONO`
5. When the gate closes, the supervisor stops `pw-loopback` and removes both sidetone nodes.

The gate does not count these as capture clients: the loopback's own streams, passive monitor streams, internal or virtual nodes, filter-chain capture streams (`capture.*`, `rnnoise_source`), corked streams, and streams that record from a different microphone.

### How it is supervised

- **Gate first, fail closed.** If the snapshot fails, the loopback is stopped and the loop tries again on the next cycle.
- **Every cycle re-checks the running loopback.** It reads the playback volume and reapplies the saved level if the reading is above the cap. If the cap cannot be enforced, it stops the loopback. It also verifies that the link set is exactly the two links above. Any extra link or missing link stops the loopback so it restarts from scratch.
- **Start-up failures clean up.** If `pw-loopback` exits early, the nodes do not appear within 5 seconds, the gain readback is too high, `pw-link` fails, or the link check fails, the supervisor stops `pw-loopback` and removes the sidetone nodes.
- **Signals are handled.** SIGTERM and SIGINT end the loop and clean up the loopback before exit.
- **systemd keeps the supervisor running.** The user unit in `systemd/airpods-sidetone.service` uses `Restart=on-failure` with a 2 second delay. `ExecStopPost` also kills any leftover `pw-loopback -n airpods-sidetone` process.

## Requirements

- Linux with PipeWire and a Bluetooth stack that exposes the headset as `bluez_input.<ADDR>` and `bluez_output.<ADDR with underscores>.1` nodes.
- Python 3 with the standard library only. CI uses 3.11.
- These tools at the exact paths hard-coded in `sidetone.py`: `/usr/bin/pw-loopback`, `/usr/bin/pw-link`, `/usr/bin/pw-cli`, `/usr/bin/pw-dump`, `/usr/bin/pactl`.
- `/usr/bin/python3`, which both the `./sidetone` shim and the systemd unit call.
- A systemd user session with `systemctl --user`. The `off` command also calls `pgrep`, and the unit's `ExecStopPost` uses `pkill`.
- The headset must be connected, and the profile it is using must expose a microphone source. The gate stays closed when the source is missing.

## Quick start

Find your headset's Bluetooth address with `bluetoothctl devices`, then:

```bash
git clone https://github.com/thefiredev-cloud/airpods-max-sidetone.git
cd airpods-max-sidetone
export SIDETONE_BT_ADDR=AA:BB:CC:DD:EE:FF   # replace with your headset's address
python3 sidetone.py status
```

`status` only reads state. It prints the service state, the gate decision, the routing check, and the gain readback.

Install the user service once. `install.sh` fills in the clone path and your headset address (the unit template keeps the placeholders `@REPO@` and `AA:BB:CC:DD:EE:FF`) and reloads the user manager:

```bash
./install.sh
```

To do the same by hand:

```bash
mkdir -p ~/.config/systemd/user
sed "s|@REPO@|$PWD|" systemd/airpods-sidetone.service > ~/.config/systemd/user/airpods-sidetone.service
$EDITOR ~/.config/systemd/user/airpods-sidetone.service   # set SIDETONE_BT_ADDR
systemctl --user daemon-reload
```

Then turn supervision on:

```bash
python3 sidetone.py on
```

`on` writes the state file if needed, enables and starts the user service, waits a moment, and prints status. It does not check whether the unit file is installed, so confirm `service:` in the output shows `active`. Keep `SIDETONE_BT_ADDR` exported in the shell you use for the other commands, because the CLI reads it too.

## Usage

```bash
python3 sidetone.py on        # enable the user service and start supervision
python3 sidetone.py status    # add --json for machine-readable output
python3 sidetone.py level 0.05
python3 sidetone.py off
```

| Command | Effect |
|---|---|
| `on` | Enables and starts `airpods-sidetone.service`. The gate then controls the loopback. |
| `off` | Disables and stops the service, then reports whether any loopback process or sidetone node is left. |
| `status [--json]` | Shows service state, gate decision, routing check, and gain readback. |
| `level <value>` | Saves the loopback amplitude and applies it if the loopback is running. Values are clamped to 0.02 through 0.125. |
| `supervise` | Runs the supervisor loop in the foreground. The service runs this command. |

The `./sidetone` shim runs `sidetone.py` from the directory it lives in.

`on`, `off`, `level` and `supervise` change live audio routing. `on` and `supervise` refuse to run until `SIDETONE_BT_ADDR` is set to a real address.

## Configuration

| Setting | Where | Notes |
|---|---|---|
| `SIDETONE_BT_ADDR` | environment, and the `Environment=` line in the unit | Required. Bluetooth address in the form `AA:BB:CC:DD:EE:FF`. The script exits if the format is wrong. |
| Level | `state/state.json` next to `sidetone.py` | Created on first use and ignored by git. Default and maximum are 0.125. Minimum is 0.02. |

The cap (0.125, about -18.06 dB), the minimum level (0.02), the 2 second check interval, and the tool paths are constants near the top of `sidetone.py`.

## Project layout

```text
sidetone.py                          supervisor, gate, routing check, CLI
sidetone                             shell shim that runs sidetone.py
install.sh                           write the user unit for this clone and reload systemd
uninstall.sh                         stop the service and remove that unit
systemd/airpods-sidetone.service     user unit template
tests/test_gate.py                   gate tests (no PipeWire needed)
ruff.toml                            lint rules
.github/workflows/ci.yml             lint and test on push and pull request to main
```

## Development

```bash
pip install pytest ruff
ruff check .
pytest -v
```

`python3 tests/test_gate.py` also works without pytest installed. CI runs `ruff check .` and `pytest -v` on Python 3.11.

The 8 tests cover the pure gate decision only. They need no headset and no PipeWire. Check live routing on your own machine with `status`.

Only AirPods Max are intended. Other Bluetooth headsets are untested. The tool uses no third-party Python packages.

## License

MIT. See [LICENSE](LICENSE). Copyright 2026 thefiredev-cloud.

Questions and bug reports: [GitHub issues](https://github.com/thefiredev-cloud/airpods-max-sidetone/issues).
