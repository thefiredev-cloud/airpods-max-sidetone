#!/usr/bin/env bash
# Stop and remove the airpods-sidetone user service.
#
#   ./uninstall.sh
#
# Disables and stops the service, deletes the unit file written by install.sh,
# reloads the user manager and kills any leftover sidetone pw-loopback.
# The clone and its state/ directory are left in place.
set -euo pipefail

unit_dir="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
unit="$unit_dir/airpods-sidetone.service"

systemctl --user disable --now airpods-sidetone.service 2>/dev/null || true
systemctl --user reset-failed airpods-sidetone.service 2>/dev/null || true
rm -f "$unit"
systemctl --user daemon-reload
pkill -f "[p]w-loopback -n airpods-sidetone" 2>/dev/null || true

echo "Removed airpods-sidetone.service"
