# pidrive/fs.py

import posixpath, shlex, stat
from .exceptions import StorageRootViolation

def canonicalise(sftp, p: str) -> str:
    return sftp.normalize(p)

def guard_inside_root(sftp, root: str, candidate: str):
    canon = canonicalise(sftp, candidate)
    root = canonicalise(sftp, root)
    if not (canon == root or canon.startswith(root + "/")):
        raise StorageRootViolation("Path outside storage root.")
    return canon

def safe_delete(ssh_client, base_dir: str, target: str, protected: set[str]):
    sftp = ssh_client.sftp
    base_dir = canonicalise(sftp, base_dir)
    raw = posixpath.join(base_dir, target)
    def _safe(path):
        c = guard_inside_root(sftp, base_dir, path)
        if c in protected:
            raise StorageRootViolation(f"Deletion of protected path '{c}' is restricted.")
        return c
    def _rm(path):
        path = _safe(path)
        st = sftp.stat(path).st_mode
        if stat.S_ISDIR(st):
            for item in sftp.listdir(path):
                _rm(posixpath.join(path, item))
            sftp.rmdir(path)
        else:
            sftp.remove(path)
    _rm(raw)

def detect_mergerfs_branches(ssh_client) -> list[str]:
    out, _, _ = ssh_client._exec("findmnt -t fuse.mergerfs -no SOURCE | head -n1 || true", timeout=5)
    src = out.strip()
    if src.startswith("mergerfs#"):
        return [p for p in src.split("#",1)[1].split(":") if p]
    out, _, _ = ssh_client._exec(r"awk '!/^\s*#/ && $1 ~ /^mergerfs#/ {print $1; exit}' /etc/fstab || true", timeout=5)
    src = out.strip()
    if src.startswith("mergerfs#"):
        return [p for p in src.split("#",1)[1].split(":") if p]
    return []

def ensure_pool_dirs(ssh_client, subpath: str, branches: list[str]):
    cmds = [f"mkdir -p {shlex.quote(posixpath.join(b, subpath))}" for b in branches]
    if cmds:
        ssh_client._exec(" && ".join(cmds), timeout=10)
