#!/usr/bin/env bash
# Shared by classify-agent-failure.sh (runs inside the agent job, where the
# model step's output is available locally) and report-agent-failure.sh.
#
# Why the classification happens in the agent job: a run's job logs cannot be
# read through the API until the whole run has completed, and the reporting job
# runs inside that run, so it cannot classify from the log itself (the first
# real reports had no error line, and a spend limit could never have been
# detected). The agent job has the text on disk, so it classifies there and
# passes the result on as job outputs.
#
# The text is treated as untrusted: it can echo model output or issue text.

# Truncate, strip control characters and backticks, defuse @-mentions.
clean_line() {
  tr -d '\000-\010\013-\037`' | sed 's/@/(at)/g' | cut -c1-300
}

# classify_failure_log FILE -> sets KIND (spend | rate | failure) and ERR (the
# first error-looking line). Looks at error-looking lines only, so stray numbers
# in ordinary output cannot match.
classify_failure_log() {
  local file=$1 errors
  KIND=failure
  ERR=''
  [ -f "$file" ] || return 0
  errors=$(grep -iE 'error|exception' "$file" | head -n 60 | tr '[:upper:]' '[:lower:]' || true)
  if printf '%s\n' "$errors" | grep -Eq \
    'insufficient credits|payment required|key limit exceeded|credit limit|spend limit|"code": ?402|status ?code: ?402|error code: ?402'; then
    KIND=spend
  elif printf '%s\n' "$errors" | grep -Eq \
    'rate.?limit|too many requests|"code": ?429|status ?code: ?429|error code: ?429'; then
    KIND=rate
  fi
  ERR=$(grep -m1 -iE 'error|exception' "$file" | clean_line || true)
}
