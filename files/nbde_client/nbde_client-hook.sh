#!/bin/sh

# disable_inird_connections() will disable autoconnect for the active
# connections within the initramfs, so that these will not clash with
# the system network connections once the flush is performed and
# the network configuration is applied to the system.
disable_inird_connections() {
  nmcli -t -f NAME connection show --active 2>/dev/null | while read -r _c; do
  if ! _enabled="$(nmcli -t connection show "${_c}" \
             | grep connection.autoconnect: \
             | cut -d: -f2)" || [ -z "${_enabled}" ]; then
    continue
  fi
  [ "${_enabled}" = "no" ] && continue

  echo "[nbde_client] Disabling autoconnect for connection ${_c}" >&2
  nmcli connection modify "${_c}" connection.autoconnect no
  done
}

disable_inird_connections

# vim:set ts=2 sw=2 et:
