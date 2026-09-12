#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

./.venv/bin/python3 src/planner.py "$@"