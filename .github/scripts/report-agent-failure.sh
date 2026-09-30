#!/usr/bin/env bash
# Reports a failed Gemini agent run on the issue or PR it was working on, so a
# failure is never silent (an agent that dies leaves nothing behind otherwise).
#
# Inputs (environment): GH_TOKEN, GH_REPO, TARGET_NUM (issue or PR number),
# RUN_ID, RUN_URL, and optionally TRIGGER_LABEL (a label that started the run;
# it is removed when the OpenRouter credit or spend limit is hit, so the run is
# not simply re-triggered into the same failure).
#
# The error text comes from the failed job log, which can echo model output or
# issue text, so it is treated as untrusted: it is truncated, stripped of
# control characters and backticks, and @-mentions are defused before posting.
set -euo pipefail

case "${TARGET_NUM:-}" in
  '' | *[!0-9]*)
    echo "no numeric issue or PR number; nothing to report"
    exit 0
    ;;
esac

# `gh run view --log-failed` does not work for the run that is still in
# progress (this job runs inside it), so read each failed job through the API.
# The failed step's name comes from the job metadata, which is available at
# once; the log text can lag the job's completion, so it is retried briefly
# (the first real run reported no error line because of exactly that).
jobs_json=$(gh api "repos/$GH_REPO/actions/runs/$RUN_ID/jobs" 2>/dev/null || true)
failed_ids=$(printf '%s' "$jobs_json" \
  | jq -r '.jobs[]? | select(.conclusion == "failure") | .id' 2>/dev/null || true)
failed_step=$(printf '%s' "$jobs_json" \
  | jq -r '[.jobs[]? | select(.conclusion == "failure") | .steps[]?
      | select(.conclusion == "failure") | .name] | first // empty' 2>/dev/null || true)
log=''
for _ in 1 2 3 4 5 6; do
  log=''
  for job in $failed_ids; do
    log+=$(gh api "repos/$GH_REPO/actions/jobs/$job/logs" 2>/dev/null || true)$'\n'
  done
  if printf '%s' "$log" | grep -qF '##[error]'; then
    break
  fi
  sleep "${LOG_RETRY_SLEEP:-5}"
done
clean() { tr -d '\000-\010\013-\037`' | sed 's/@/(at)/g' | cut -c1-300; }
err=$(printf '%s\n' "$log" | grep -m1 -F '##[error]' | sed 's/^.*##\[error\]//' | clean || true)
failed_step=$(printf '%s' "$failed_step" | clean || true)

# Classify from error-looking lines only, to avoid matching stray numbers.
errors=$(printf '%s\n' "$log" | grep -iE 'error|exception' | head -n 60 | tr '[:upper:]' '[:lower:]' || true)
kind=failure
if printf '%s\n' "$errors" | grep -Eq \
  'insufficient credits|payment required|key limit exceeded|credit limit|spend limit|"code": ?402|status ?code: ?402|error code: ?402'; then
  kind=spend
elif printf '%s\n' "$errors" | grep -Eq \
  'rate.?limit|too many requests|"code": ?429|status ?code: ?429|error code: ?429'; then
  kind=rate
fi

case "$kind" in
  spend)
    headline="The Gemini agent could not run: OpenRouter reports the credit or spend limit is used up."
    advice="It will not be retried automatically. Raise the key's limit or add credits, then re-add the agent:gemini label or comment mentioning the agent again."
    ;;
  rate)
    headline="The Gemini agent was rate-limited by OpenRouter or the model provider."
    advice="Wait a few minutes, then re-add the agent:gemini label or comment mentioning the agent again."
    ;;
  *)
    headline="The Gemini agent run failed."
    advice="Check the run log and fix the cause, then re-add the agent:gemini label or comment mentioning the agent again."
    ;;
esac

body="$headline $advice"
if [ -n "$failed_step" ]; then
  body="$body"$'\n\n'"Failed step: \`$failed_step\`"
fi
if [ -n "$err" ]; then
  body="$body"$'\n\n'"First error: \`$err\`"
fi
body="$body"$'\n\n'"Run: $RUN_URL"

# REST endpoints, not `gh issue comment/edit`: those use GraphQL, which needs
# pull-requests: write to touch a PR; the REST issues endpoints work for both
# issues and PRs with issues: write alone.
api="repos/$GH_REPO/issues/$TARGET_NUM"
gh api -X POST "$api/comments" -f body="$body" > /dev/null
gh api -X POST "$api/labels" -f "labels[]=agent:failed" > /dev/null \
  || echo "could not add the agent:failed label"
if [ "$kind" = "spend" ] && [ -n "${TRIGGER_LABEL:-}" ]; then
  gh api -X DELETE "$api/labels/$TRIGGER_LABEL" > /dev/null \
    || echo "could not remove the $TRIGGER_LABEL label"
fi
