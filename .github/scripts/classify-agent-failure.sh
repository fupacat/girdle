#!/usr/bin/env bash
# Runs in the agent job when the model step failed. Classifies the failure from
# the model step's own output (teed to a file) and publishes the result as step
# outputs, which the job exposes to the report-failure job. See
# agent-failure-lib.sh for why this happens here and not in the reporter.
set -uo pipefail

. "$(dirname "$0")/agent-failure-lib.sh"

classify_failure_log "${1:-${RUNNER_TEMP:-/tmp}/aider.log}"
{
  echo "kind=$KIND"
  echo "error=$ERR"
} >> "${GITHUB_OUTPUT:-/dev/stdout}"
