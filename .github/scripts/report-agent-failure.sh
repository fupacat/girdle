#!/usr/bin/env bash
# Reports a failed Gemini agent run on the issue or PR it was working on, so a
# failure is never silent (an agent that dies leaves nothing behind otherwise).
#
# Inputs (environment): GH_TOKEN, GH_REPO, TARGET_NUM (issue or PR number),
# RUN_ID, RUN_URL; FAILURE_KIND and FAILURE_ERROR when the agent job classified
# the failure (see agent-failure-lib.sh); and optionally TRIGGER_LABEL (a label
# that started the run; it is removed when the OpenRouter credit or spend limit
# is hit, so the run is not simply re-triggered into the same failure).
#
# The error text can echo model output or issue text, so it is untrusted: it is
# truncated, stripped of control characters and backticks, and @-mentions are
# defused before posting.
set -euo pipefail

. "$(dirname "$0")/agent-failure-lib.sh"

case "${TARGET_NUM:-}" in
  '' | *[!0-9]*)
    echo "no numeric issue or PR number; nothing to report"
    exit 0
    ;;
esac

# The failed step's name comes from the job metadata, which is readable while
# the run is still in progress.
jobs_json=$(gh api "repos/$GH_REPO/actions/runs/$RUN_ID/jobs" 2>/dev/null || true)
failed_step=$(printf '%s' "$jobs_json" \
  | jq -r '[.jobs[]? | select(.conclusion == "failure") | .steps[]?
      | select(.conclusion == "failure") | .name] | first // empty' 2>/dev/null || true)
failed_step=$(printf '%s' "$failed_step" | clean_line || true)

# The classification comes from the agent job. When it did not classify (the
# failure was in another step or job) the kind is a plain failure: the job log
# is not readable until the run completes.
KIND=failure
ERR=''
if [ -n "${FAILURE_KIND:-}" ]; then
  KIND=$FAILURE_KIND
  ERR=$(printf '%s' "${FAILURE_ERROR:-}" | clean_line || true)
fi

case "$KIND" in
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
    KIND=failure
    ;;
esac

body="$headline $advice"
if [ -n "$failed_step" ]; then
  body="$body"$'\n\n'"Failed step: \`$failed_step\`"
fi
if [ -n "$ERR" ]; then
  body="$body"$'\n\n'"First error: \`$ERR\`"
fi
body="$body"$'\n\n'"Run: $RUN_URL"

# Works for an issue (issues: write) and for a PR (pull-requests: write; the
# PR-mode workflow grants that to the reporting job, issues: write is not enough).
api="repos/$GH_REPO/issues/$TARGET_NUM"
gh api -X POST "$api/comments" -f body="$body" > /dev/null
gh api -X POST "$api/labels" -f "labels[]=agent:failed" > /dev/null \
  || echo "could not add the agent:failed label"
if [ "$KIND" = "spend" ] && [ -n "${TRIGGER_LABEL:-}" ]; then
  gh api -X DELETE "$api/labels/$TRIGGER_LABEL" > /dev/null \
    || echo "could not remove the $TRIGGER_LABEL label"
fi
