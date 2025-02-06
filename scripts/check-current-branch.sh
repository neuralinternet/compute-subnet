#!/bin/sh

# Get the current branch name
branch_name="${GITHUB_HEAD_REF:-$(git branch --show-current)}"

scripts/check-branch-name.sh "$branch_name"
