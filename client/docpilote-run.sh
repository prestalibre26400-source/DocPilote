#!/usr/bin/env bash
set -euo pipefail
exec python3 /opt/docpilote/client/docpilote_client.py "$@"
