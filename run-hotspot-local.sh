#!/usr/bin/env bash
set -euo pipefail

# Windows Mobile hotspot address; keep port forwarding pointed at this address.
export KEIVOTOS_HOTSPOT_HOST=192.168.137.1
exec bash "$(dirname -- "${BASH_SOURCE[0]}")/run-lan-local.sh" "$@"
