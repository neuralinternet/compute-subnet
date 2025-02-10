#!/bin/bash

# Define regex patterns for each part of the commit message
VALID_TYPE_REGEX="^(feat|fix|docs|style|refactor|perf|test|chore|ci|build|revert)"
VALID_SCOPE_REGEX="^(feat|fix|docs|style|refactor|perf|test|chore|ci|build|revert)(\([a-zA-Z0-9/_-]+\))?:"
VALID_SUBJECT_REGEX=": .{3,72}$"

# Detect whether it's running locally (pre-commit) or in GitHub Actions
if [[ -f "$1" ]]; then
    # Local pre-commit hook: Validate a single commit message from a file
    COMMIT_MSG=$(cat "$1")
    COMMIT_MESSAGES=("$COMMIT_MSG")
else
    # GitHub Actions: Validate multiple commit messages from base_sha to head_sha
    COMMIT_MESSAGES=($(git log --pretty=format:%s "$1..$2"))
fi

invalid_commit_found=0

echo "🔍 Checking commit messages..."
echo ""

# Loop through commit messages and validate each
for commit_msg in "${COMMIT_MESSAGES[@]}"; do
    echo "🔹 Checking: \"$commit_msg\""

    error_messages=()  # Initialize an array to store errors

    # Check if commit message starts with a valid type
    if ! [[ $commit_msg =~ $VALID_TYPE_REGEX ]]; then
        error_messages+=("❌ Missing or invalid commit type. Expected one of: feat, fix, docs, style, refactor, perf, test, chore, ci, build, revert.")
    fi

    # Check if scope format is valid (optional but well-formed)
    if ! [[ $commit_msg =~ $VALID_SCOPE_REGEX ]]; then
        error_messages+=("❌ Scope format is incorrect or missing. If included, it should be in parentheses e.g., 'feat(auth):'.")
    fi

    # Check if it contains a valid subject after the colon
    if ! [[ $commit_msg =~ $VALID_SUBJECT_REGEX ]]; then
        error_messages+=("❌ Commit subject is missing, too short (<3 characters), or too long (>72 characters). Example: 'feat(auth): add JWT authentication'.")
    fi

    # If any errors were found, print them
    if [[ ${#error_messages[@]} -gt 0 ]]; then
        echo "❌ ERROR: Commit message does not follow Conventional Commit format: \"$commit_msg\""
        for error in "${error_messages[@]}"; do
            echo "   - $error"
        done
        invalid_commit_found=1
    else
        echo "✅ Valid: \"$commit_msg\""
    fi
done

if [[ $invalid_commit_found -eq 1 ]]; then
    echo -e "\n❌ ERROR: Some commit messages are invalid. Please follow the Conventional Commit format."
    echo -e "\n💡 Expected format: <type>(<scope>): <subject>\n"
    echo -e "🔹 Valid types: feat, fix, docs, style, refactor, perf, test, chore, ci, build, revert"
    echo -e "🔹 Example: feat(auth): add JWT authentication\n"
    exit 1
else
    echo -e "\n✅ All commit messages are valid."
    exit 0
fi
