# pidrive/utils.py

import os
import posixpath
import re

from urllib.parse import urlparse, unquote


_SAFE_NAME_RE = re.compile(r"[^\w.\-]+")

def guess_filename_from_url(url: str, default: str = "download.bin") -> str:
    """
    Best-effort filename from a URL path.
    - Accepts only str, else returns `default`.
    - Decodes %-escapes and strips trailing slashes.
    - Falls back to `default` when empty.
    - Sanitises to a conservative character set.
    - Truncates to a reasonable length to avoid filesystem issues.
    """
    if not isinstance(url, str) or not url:
        return default

    try:
        path = urlparse(url).path or ""
        # Decode %20 etc., strip trailing slash, take basename
        name = os.path.basename(unquote(path).rstrip("/")) or default
    except Exception:
        # Extremely defensive fallback
        return default

    # Replace unsafe chars with underscores
    name = _SAFE_NAME_RE.sub("_", name)

    # Avoid hidden dotfiles and empty strings after sanitisation
    if name in ("", ".", ".."):
        name = default

    # Trim very long names (common on object stores with queryyish paths)
    # ext length handling: keep extension if present
    if len(name) > 200:
        root, ext = os.path.splitext(name)
        name = (root[:200 - len(ext)]) + ext

    return name

def ensure_remote_dirs(sftp, path: str):
    parts = []
    p = path
    while p not in ("", "/"):
        parts.insert(0, posixpath.basename(p))
        p = posixpath.dirname(p)
    cur = "/"
    for d in parts:
        cur = posixpath.join(cur, d)
        try:
            sftp.stat(cur)
        except FileNotFoundError:
            sftp.mkdir(cur)