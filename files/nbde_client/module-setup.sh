#!/bin/sh

depends() {
  echo network-manager
  return 255
}

install() {
  inst_multiple nmcli grep cut

  # $moddir is a dracut variable.
  # shellcheck disable=SC2154
  inst_hook initqueue/online 60 "$moddir/nbde_client-hook.sh"
  inst_hook initqueue/settled 60 "$moddir/nbde_client-hook.sh"
}

# vim:set ts=2 sw=2 et:
