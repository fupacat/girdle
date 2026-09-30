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

log=''
for job in $(gh api "repos/$GH_REPO/actions/runs/$RUN_ID/jobs" \
    --jq '.jobs[] | select(.conclusion == "failure") | .id' 2>/dev/null || true); do
  log+=$(gh api "repos/$GH_REPO/actions/jobs/$job/logs" 2>/dev/null || true)$'\n'
done
err=$(printf '%s\n' "$log" | grep -m1 -F '##[error]' | sed 's/^.*##\[error\]//' || true)
err=$(printf '%s' "$err" | tr -d '\000-\010\013-\037`' | sed 's/@/(at)/g' | cut -c1-300)

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
if [ -n "$err" ]; then
  body="$body"$'\n\n'"First error: \`$err\`"
fi
body="$body"$'\n\n'"Run: $RUN_URL"

gh issue comment "$TARGET_NUM" --repo "$GH_REPO" --body "$body"
gh issue edit "$TARGET_NUM" --repo "$GH_REPO" --add-label "agent:failed" \
  || echo "could not add the agent:failed label"
if [ "$kind" = "spend" ] && [ -n "${TRIGGER_LABEL:-}" ]; then
  gh issue edit "$TARGET_NUM" --repo "$GH_REPO" --remove-label "$TRIGGER_LABEL" \
    || echo "could not remove the $TRIGGER_LABEL label"
fi
