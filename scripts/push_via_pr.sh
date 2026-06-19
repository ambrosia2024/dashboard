#!/bin/sh
set -eu

# Push the current committed HEAD through a temporary GitHub PR branch.
#
# Usage:
#   scripts/push_via_pr.sh
#   scripts/push_via_pr.sh my-temp-branch
#
# Optional environment:
#   BASE_BRANCH=main
#   PR_TITLE="My PR title"
#   PR_BODY="My PR body"

BASE_BRANCH="${BASE_BRANCH:-main}"
TEMP_BRANCH="${1:-auto/merge-to-${BASE_BRANCH}-$(date +%Y%m%d-%H%M%S)}"
CURRENT_BRANCH="$(git branch --show-current)"
PR_TITLE="${PR_TITLE:-$(git log -1 --pretty=%s)}"
PR_BODY="${PR_BODY:-Automated PR for changes that cannot be pushed directly to protected ${BASE_BRANCH}.}"

if ! command -v gh >/dev/null 2>&1; then
  echo "GitHub CLI (gh) is required." >&2
  exit 1
fi

if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "Commit or stash local changes before running this script." >&2
  exit 1
fi

git fetch origin "${BASE_BRANCH}"

if ! git merge-base --is-ancestor "origin/${BASE_BRANCH}" HEAD; then
  echo "Current HEAD is not based on origin/${BASE_BRANCH}. Rebase or merge first." >&2
  exit 1
fi

if [ "$(git rev-parse HEAD)" = "$(git rev-parse "origin/${BASE_BRANCH}")" ]; then
  echo "No committed changes to publish." >&2
  exit 1
fi

if git show-ref --verify --quiet "refs/heads/${TEMP_BRANCH}"; then
  echo "Local branch already exists: ${TEMP_BRANCH}" >&2
  exit 1
fi

git branch "${TEMP_BRANCH}" HEAD
git push -u origin "${TEMP_BRANCH}"

PR_URL="$(gh pr create \
  --base "${BASE_BRANCH}" \
  --head "${TEMP_BRANCH}" \
  --title "${PR_TITLE}" \
  --body "${PR_BODY}")"

echo "Created PR: ${PR_URL}"

gh pr merge "${PR_URL}" --merge --delete-branch

if [ "${CURRENT_BRANCH}" != "${BASE_BRANCH}" ]; then
  git switch "${BASE_BRANCH}"
fi

git fetch origin "${BASE_BRANCH}"
git merge --ff-only "origin/${BASE_BRANCH}"
if git show-ref --verify --quiet "refs/heads/${TEMP_BRANCH}"; then
  git branch -d "${TEMP_BRANCH}"
else
  echo "Local temporary branch ${TEMP_BRANCH} was already deleted."
fi

echo "Merged ${TEMP_BRANCH} into ${BASE_BRANCH} and deleted the temporary branch."
