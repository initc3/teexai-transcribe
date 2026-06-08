#!/bin/bash
# Self-contained RedactBench runner. Scores the skill on the bundled samples.
#   ZAI_API_KEY=sk-... bash run.sh                 # all samples, vanilla vs workflow
#   ARMS=vanilla,prompt,workflow bash run.sh 11    # one sample, all three arms
set -eu
HERE="$(cd "$(dirname "$0")" && pwd)"
export SKILL_PATH="${SKILL_PATH:-$HERE/../skill/SKILL.md}"
export REDACT_DIR="${REDACT_DIR:-$HERE/../runtime}"
export SAMPLES_DIR="${SAMPLES_DIR:-$HERE/samples}"
# the workflow arm needs the smithers runtime installed once:
[ -d "$REDACT_DIR/node_modules" ] || (cd "$REDACT_DIR" && bun install)
cd "$HERE" && python3 bench.py "$@"
