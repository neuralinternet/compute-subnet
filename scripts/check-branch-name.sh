#!/bin/sh

# Define allowed prefixes including release
allowed_prefixes="feat|fix|hotfix|chore|refactor|test|spike|prototype|release|docs"

# Define the JIRA ticket pattern (CSN-XXXX, any number of digits)
jira_ticket_pattern="CSN-[0-9]+"

# Define the valid release version pattern (release/vX.Y.Z or release/vX.Y.Z-beta)
release_version_pattern="release/v[0-9]+\.[0-9]+\.[0-9]+(-[a-z0-9]+)?"

# Get the current branch name
branch_name="$1"

# Define the valid hotfix version pattern (hotfix/vX.Y.Z)
hotfix_version_pattern="hotfix/v[0-9]+\.[0-9]+\.[0-9]+"

# If branch_name is empty or you are in a detached HEAD state where HEAD is returned
if [ -z "$branch_name" ] || [ "$branch_name" = "HEAD" ]; then
    printf "❌ ERROR: Unable to determine branch name.\n"
    exit 1
fi

# Check if it's a valid release branch (release/vX.Y.Z)
if echo "$branch_name" | grep -Eq "^$release_version_pattern$"; then
    printf "✅ Branch name is valid (Release branch): '%s'\n" "$branch_name"
    exit 0
fi

# Validate hotfix branches
if echo "$branch_name" | grep -Eq "^hotfix/"; then
    if echo "$branch_name" | grep -Eq "^$hotfix_version_pattern-$jira_ticket_pattern-[a-z0-9]+(-[a-z0-9]+)*$"; then
        printf "✅ Branch name is valid (Hotfix branch): '%s'\n" "$branch_name"
        exit 0
    else
        printf "❌ ERROR: Hotfix branch name '%s' is invalid. Expected format is 'hotfix/vX.Y.Z-CSN-XXXX-description' where 'XXXX' can be any number of digits.\n" "$branch_name"
        printf "🔹 Suggested fix: 'hotfix/v1.2.3-CSN-1234-fix-login-issue'\n"
        printf "👉 Branch name should follow the format: 'hotfix/vX.Y.Z-CSN-XXXX-description'\n"
        exit 1
    fi
fi

# ❌ **If it starts with `release/` but is NOT valid, show a specific error**
if echo "$branch_name" | grep -Eq "^release/"; then
    printf "❌ ERROR: Branch name '%s' is invalid - Release branches must follow the format 'release/vX.Y.Z' or 'release/vX.Y.Z-beta'\n" "$branch_name" >&2
    printf "🔹 Suggested fix: 'release/v1.2.3'\n"
    printf "👉 Branch name should follow the format: 'release/vX.Y.Z' or 'release/vX.Y.Z-beta'\n"
    exit 1
fi

# Extract JIRA ticket (always uppercase CSN-XXXX)
jira_ticket=$(echo "$branch_name" | grep -o "$jira_ticket_pattern")

# Extract the description (everything after `CSN-XXXX-`)
branch_description=$(echo "$branch_name" | sed -E "s/^($allowed_prefixes)\/$jira_ticket_pattern-//g")

# Ensure description is lowercase (ignore the `CSN-XXXX` part)
branch_description_lower=$(echo "$branch_description" | tr '[:upper:]' '[:lower:]')

# Suggest a valid branch name (default to feat/CSN-1234-description if missing details)
if [ -n "$jira_ticket" ] && [ -n "$branch_description" ]; then
    suggested_branch_name="feat/${jira_ticket}-$(echo "$branch_description_lower" | tr '_' '-' | tr ' ' '-' | tr -d '[^a-z0-9-]')"
else
    suggested_branch_name="feat/CSN-1234-description"
fi

# Function to display errors properly (single-line for Git popups)
show_error() {
    # Print error message on the first line
    printf "❌ ERROR: %s\n" "$1" >&2

    # Print suggested fix on a new line
    printf "🔹 Suggested fix: '%s'\n" "$suggested_branch_name" >&2

    # Print additional information (e.g., branch name format)
    printf "👉 Branch name should follow the format: '<prefix>/CSN-XXXX-description'\n" >&2

    exit 1
}

# Check if the branch name starts with an allowed prefix
if ! echo "$branch_name" | grep -Eq "^($allowed_prefixes)/"; then
    show_error "Branch name '$branch_name' is invalid - Must start with one of: $allowed_prefixes/"
fi

# Check if the branch name contains a valid JIRA ticket (CSN-XXXX)
if ! echo "$branch_name" | grep -Eq "/$jira_ticket_pattern-"; then
    show_error "Branch name '$branch_name' is invalid - Must include a JIRA ticket like 'CSN-XXXX' (e.g., CSN-1234, CSN-98765)"
fi

# Check for uppercase letters in the description (ignore the JIRA ticket itself)
if [ "$branch_description" != "$branch_description_lower" ]; then
    show_error "Branch name '$branch_name' contains uppercase letters in the description - Use only lowercase letters, numbers, and hyphens"
fi

# Ensure kebab-case (no underscores, spaces, or special characters other than '-')
if echo "$branch_description" | grep -Eq "[^a-z0-9-]"; then
    show_error "Branch name '$branch_name' contains invalid characters in the description - Only lowercase letters, numbers, and hyphens are allowed"
fi

# Ensure proper formatting (e.g., feat/CSN-1234-description)
if ! echo "$branch_name" | grep -Eq "^($allowed_prefixes)/$jira_ticket_pattern-[a-z0-9]+(-[a-z0-9]+)*$"; then
    show_error "Branch name '$branch_name' is invalid - Format should be '<prefix>/CSN-XXXX-description' - Example: 'feat/CSN-1234-add-new-feature'"
fi

printf "✅ Branch name is valid: '%s'\n" "$branch_name"
exit 0
