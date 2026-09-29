#!/bin/sh
# Checks formatting, workflows, and non-destructive unit tests.
set -eu
ruff format --check .
ruff check .
nixfmt --check flake.nix
actionlint .github/workflows/test.yml
python3 -B -m unittest -v
