#!/usr/bin/env bash
# Runs in the agent job. Classifies a model failure from the model step's own
# output (teed to a file) and publishes the result as step outputs, which the
# job exposes to the report-failure job. See agent-failure-lib.sh for why this
# happens here and not in the reporter.
#
# Usage: classify-agent-failure.sh [--silent] [LOGFILE]
#
#   (default)  the model step exited non-zero: always classify.
#   --silent   the model step exited 0 but produced no changes: aider prints a
#              provider error (bad model id, exhausted credits, rate limit) and
#              still exits 0, so classify only if the output shows one, and
#              then exit 1 so the job fails and the reporter explains it
#              instead of the run being reported as "no changes".
set -uo pipefail

. "$(dirname "$0")/agent-failure-lib.sh"

silent=0
if [ "${1:-}" = "--silent" ]; then
  silent=1
  shift
fi
log="${1:-${RUNNER_TEMP:-/tmp}/aider.log}"

if [ "$silent" -eq 1 ] && ! has_model_error "$log"; then
  exit 0
fi

classify_failure_log "$log"
{
  echo "kind=$KIND"
  echo "error=$ERR"
} >> "${GITHUB_OUTPUT:-/dev/stdout}"

if [ "$silent" -eq 1 ]; then
  echo "the model step exited 0 but its output shows a provider error: $ERR"
  exit 1
fi
