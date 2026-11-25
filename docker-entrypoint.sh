#!/bin/sh
# Start OmniArmor as the unprivileged `omniarmor` user, whatever owns the disk.
#
# A host's persistent disk is often mounted owned by root, and on such a disk
# the app (which runs as `omniarmor`) could not create its database and the
# worker died on start ("unable to open database file"). This runs first, as
# root, only to give the data folders to `omniarmor`, then hands over: from
# `exec setpriv` on, nothing runs as root.
set -e

if [ "$(id -u)" = "0" ]; then
  for dir in "$(dirname "${DATABASE_PATH:-/data/omniarmor.db}")" "${BACKUP_DIR:-}"; do
    [ -n "$dir" ] || continue
    mkdir -p "$dir"
    chown -R omniarmor:omniarmor "$dir"
  done
  exec setpriv --reuid=omniarmor --regid=omniarmor --init-groups "$@"
fi

exec "$@"
