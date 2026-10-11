#!/usr/bin/env bash

shopt -s nullglob

failed=0

for spec in .agent-vault/context/spec-*.md; do
  if ! girdle reqs check "$spec"; then
    failed=1
  fi
done

exit "$failed"
