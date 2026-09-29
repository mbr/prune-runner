#!/bin/sh
# Formats the action sources and development configuration.
set -eu
ruff check --select I --fix .
ruff format .
nixfmt flake.nix
