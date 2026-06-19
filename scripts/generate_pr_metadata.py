#!/usr/bin/env python3
"""Generate PR metadata with an OpenAI-compatible chat endpoint.

The script reads LLM_* values from the environment and, if present, from the
repository .env file. It writes shell-safe assignments for push_via_pr.sh.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = REPO_ROOT / ".env"


def load_dotenv() -> None:
    if not ENV_PATH.exists():
        return

    for raw_line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if key and key not in os.environ:
            os.environ[key] = value


def git(args: list[str]) -> str:
    return subprocess.check_output(
        ["git", "-C", str(REPO_ROOT), *args],
        text=True,
    ).strip()


def sanitize_slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    slug = re.sub(r"-+", "-", slug)[:60].strip("-")
    return slug or "changes"


def compact_text(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[:limit].rstrip() + "\n...[truncated]"


def extract_json(content: str) -> dict[str, str]:
    content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
    content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content, flags=re.DOTALL).strip()

    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, flags=re.DOTALL)
        if not match:
            raise
        data = json.loads(match.group(0))

    if not isinstance(data, dict):
        raise ValueError("LLM response JSON must be an object.")

    return {
        "title": str(data.get("title", "")).strip(),
        "body": str(data.get("body", "")).strip(),
        "branch_slug": sanitize_slug(str(data.get("branch_slug", "")).strip()),
    }


def request_metadata(base_branch: str) -> dict[str, str]:
    api_key = os.environ.get("LLM_API_KEY")
    llm_url = os.environ.get("LLM_URL")
    endpoint = os.environ.get("LLM_CHAT_ENDPOINT", "/v1/chat/completions")
    model = os.environ.get("LLM_MODEL")

    if not api_key or not llm_url or not model:
        raise RuntimeError("LLM_API_KEY, LLM_URL, and LLM_MODEL are required.")

    max_user_chars = int(os.environ.get("LLM_MAX_USER_CHARS", "8000"))
    max_tokens = int(os.environ.get("LLM_MAX_TOKENS", "512"))
    temperature = float(os.environ.get("LLM_TEMPERATURE", "0.2"))
    timeout = float(os.environ.get("LLM_TIMEOUT_SECONDS", "60"))

    commits = git(["log", "--reverse", "--format=%h %s", f"origin/{base_branch}..HEAD"])
    diff_stat = git(["diff", "--stat", f"origin/{base_branch}..HEAD"])
    diff = git(["diff", "--find-renames", "--unified=20", f"origin/{base_branch}..HEAD"])

    user_context = compact_text(
        "\n".join(
            [
                f"Base branch: {base_branch}",
                "",
                "Commits:",
                commits,
                "",
                "Diff stat:",
                diff_stat,
                "",
                "Diff:",
                diff,
            ]
        ),
        max_user_chars,
    )

    prompt = (
        "Generate GitHub pull request metadata for these committed changes. "
        "Return only JSON with keys: title, body, branch_slug. "
        "title must be concise, imperative, and at most 72 characters. "
        "branch_slug must be lowercase kebab-case, without a leading branch prefix, "
        "and at most 50 characters. "
        "body must be Markdown with a short summary and relevant validation notes. "
        "Do not invent tests or behavior not supported by the commits."
    )

    url = llm_url.rstrip("/") + "/" + endpoint.lstrip("/")
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_context},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=timeout) as response:
        response_data = json.loads(response.read().decode("utf-8"))

    content = response_data["choices"][0]["message"]["content"]
    metadata = extract_json(content)

    if not metadata["title"] or not metadata["body"]:
        raise ValueError("LLM response did not include title and body.")

    return metadata


def write_shell_assignments(path: Path, metadata: dict[str, str]) -> None:
    lines = [
        f"LLM_PR_TITLE={shlex.quote(metadata['title'])}",
        f"LLM_PR_BODY={shlex.quote(metadata['body'])}",
        f"LLM_BRANCH_SLUG={shlex.quote(metadata['branch_slug'])}",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate PR metadata with the configured LLM.")
    parser.add_argument("--base", default="main", help="Base branch name. Defaults to main.")
    parser.add_argument("--output", required=True, type=Path, help="Output file for shell assignments.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    load_dotenv()

    try:
        metadata = request_metadata(args.base)
    except (KeyError, ValueError, RuntimeError, urllib.error.URLError, subprocess.CalledProcessError) as exc:
        print(f"LLM metadata generation unavailable: {exc}", file=sys.stderr)
        return 1

    write_shell_assignments(args.output, metadata)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
