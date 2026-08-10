#!/usr/bin/env bash
# outils/installer_hooks.sh — Active les hooks Git versionnés du dépôt.
set -euo pipefail
RACINE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$RACINE"
git config core.hooksPath .githooks
git config commit.template .gitmessage
chmod +x .githooks/*
echo "Hooks Git activés (.githooks) et gabarit de commit configuré."
