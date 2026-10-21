#!/usr/bin/env bash
# Install the airpods-sidetone user service for this clone.
#
#   SIDETONE_BT_ADDR=AA:BB:CC:DD:EE:FF ./install.sh
#
# Writes ~/.config/systemd/user/airpods-sidetone.service with this clone's
# path and your headset address filled in, then reloads the user manager.
# It does not start the service: run `python3 sidetone.py on` for that.
# Safe to run again; it overwrites only that unit file.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
addr="${SIDETONE_BT_ADDR:-}"
addr="${addr^^}"

if ! [[ "$addr" =~ ^[0-9A-F]{2}(:[0-9A-F]{2}){5}$ ]] || [[ "$addr" == "AA:BB:CC:DD:EE:FF" ]]; then
  echo "install.sh: set SIDETONE_BT_ADDR to your headset's Bluetooth address (see: bluetoothctl devices)" >&2
  exit 2
fi

unit_dir="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
unit="$unit_dir/airpods-sidetone.service"
mkdir -p "$unit_dir"
sed -e "s|@REPO@|$here|" \
    -e "s|^Environment=SIDETONE_BT_ADDR=.*|Environment=SIDETONE_BT_ADDR=$addr|" \
    "$here/systemd/airpods-sidetone.service" > "$unit"
systemctl --user daemon-reload

echo "Installed $unit"
echo "Next: SIDETONE_BT_ADDR=$addr python3 $here/sidetone.py on"
