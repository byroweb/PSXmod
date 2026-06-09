#!/usr/bin/env bash
# AC1mod launcher — activates the venv and runs the app.
cd "$(dirname "$(readlink -f "$0")")"
exec ./.venv/bin/python main.py "$@"
