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
#   USE_LLM_METADATA=auto  # auto, 1/true/yes, or 0/false/no

BASE_BRANCH="${BASE_BRANCH:-main}"
USE_LLM_METADATA="${USE_LLM_METADATA:-auto}"
CURRENT_BRANCH="$(git branch --show-current)"

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

HEAD_SUBJECT="$(git log -1 --pretty=%s)"
HEAD_SHORT_SHA="$(git rev-parse --short HEAD)"
COMMIT_COUNT="$(git rev-list --count "origin/${BASE_BRANCH}..HEAD")"
COMMIT_LIST="$(git log --reverse --format='- %h %s' "origin/${BASE_BRANCH}..HEAD")"

SLUG="$(printf '%s' "${HEAD_SUBJECT}" \
  | tr '[:upper:]' '[:lower:]' \
  | sed 's/[^a-z0-9][^a-z0-9]*/-/g; s/^-//; s/-$//; s/^\(................................................\).*/\1/; s/-$//')"

if [ -z "${SLUG}" ]; then
  SLUG="changes"
fi

if [ "${USE_LLM_METADATA}" != "0" ] && [ "${USE_LLM_METADATA}" != "false" ] && [ "${USE_LLM_METADATA}" != "no" ]; then
  METADATA_FILE="/tmp/push-via-pr-metadata-$$.env"

  if scripts/generate_pr_metadata.py --base "${BASE_BRANCH}" --output "${METADATA_FILE}"; then
    . "${METADATA_FILE}"
    SLUG="${LLM_BRANCH_SLUG:-${SLUG}}"
    PR_TITLE="${PR_TITLE:-${LLM_PR_TITLE}}"
    PR_BODY="${PR_BODY:-${LLM_PR_BODY}}"
    echo "Generated PR metadata with LLM."
  elif [ "${USE_LLM_METADATA}" = "1" ] || [ "${USE_LLM_METADATA}" = "true" ] || [ "${USE_LLM_METADATA}" = "yes" ]; then
    rm -f "${METADATA_FILE}"
    echo "LLM metadata generation was required but failed." >&2
    exit 1
  else
    echo "Using commit-derived PR metadata fallback."
  fi

  rm -f "${METADATA_FILE}"
fi

TEMP_BRANCH="${1:-auto/${SLUG}-${HEAD_SHORT_SHA}}"

if [ -z "${PR_TITLE:-}" ]; then
  if [ "${COMMIT_COUNT}" = "1" ]; then
    PR_TITLE="${HEAD_SUBJECT}"
  else
    PR_TITLE="Merge ${COMMIT_COUNT} commits into ${BASE_BRANCH}"
  fi
fi

if [ -z "${PR_BODY:-}" ]; then
  PR_BODY="$(printf 'Automated PR for changes that cannot be pushed directly to protected `%s`.\n\nCommits:\n%s\n' "${BASE_BRANCH}" "${COMMIT_LIST}")"
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
