# pidrive/pi_helper.py

import os
import paramiko
import posixpath
import requests
import shlex
import threading

from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv()


class PiSSHClient:
    def __init__(self):
        self.username = os.getenv("PI_USER")
        self.password = os.getenv("PI_PASSWORD")
        self.remote_dir = os.getenv("PI_REMOTE_DIR")
        self.ngrok_api_key = os.getenv("NGROK_API_KEY")

        if not all([self.username, self.password, self.remote_dir, self.ngrok_api_key]):
            raise ValueError("Missing required environment variables.")

        self.hostname, self.port = self.resolve_ngrok_tcp()
        self.ssh = None
        self.sftp = None

    def resolve_ngrok_tcp(self):
        headers = {
            "Authorization": f"Bearer {self.ngrok_api_key}",
            "Ngrok-Version": "2"
        }
        try:
            resp = requests.get("https://api.ngrok.com/tunnels", headers=headers, timeout=5)
            resp.raise_for_status()
            tunnels = resp.json().get("tunnels", [])
            tcp_tunnel = next((t for t in tunnels if t["proto"] == "tcp"), None)
            if not tcp_tunnel:
                raise RuntimeError("No TCP tunnel found.")
            _, address = tcp_tunnel["public_url"].split("tcp://")
            hostname, port = address.split(":")
            print(f"Resolved ngrok address: {hostname}:{port}")
            return hostname, int(port)
        except Exception as e:
            raise RuntimeError(f"Failed to query ngrok: {e}")

    def __enter__(self):
        self.ssh = paramiko.SSHClient()
        # self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.ssh.set_missing_host_key_policy(paramiko.WarningPolicy())
        self.ssh.connect(
            hostname=self.hostname,
            port=self.port,
            username=self.username,
            password=self.password,
            timeout=30,
            banner_timeout=30,
            auth_timeout=30,
            allow_agent=False
        )

        # Keep the TCP session alive through ngrok/NAT so idle sessions don’t drop
        self.ssh.get_transport().set_keepalive(30)

        self.sftp = self.ssh.open_sftp()

        # Canonicalise the configured base directory on the remote (resolves .. and symlinks)
        self.remote_dir = self.sftp.normalize(self.remote_dir)

        # Protect the uploads root
        self.uploads_dir = self.sftp.normalize(posixpath.join(self.remote_dir, "uploads"))

        # Paths we will NEVER delete as a whole (contents can still be deleted)
        self._protected_paths = {self.remote_dir, self.uploads_dir}

        # Optional: prepare a trash directory for future soft-delete use
        self.trash_dir = self.sftp.normalize(posixpath.join(self.uploads_dir, ".trash"))
        try:
            self.sftp.stat(self.trash_dir)
        except FileNotFoundError:
            try:
                self.sftp.mkdir(self.trash_dir)
            except Exception:
                # Not fatal if we cannot create it
                pass
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.sftp: self.sftp.close()
        if self.ssh: self.ssh.close()
        del self.ssh, self.sftp

    def _progress_callback(self, total_size):
        """Return a callback function that updates tqdm progress bar."""
        pbar = tqdm(total=total_size, unit='B', unit_scale=True, desc="Transferring", dynamic_ncols=True)
        lock = threading.Lock()

        def callback(transferred, _):
            with lock:
                pbar.n = transferred
                pbar.refresh()
                if transferred >= total_size and not pbar.disable:
                    pbar.close()

        return callback

    def list_files(self, remote_folder=None):
        target_dir = posixpath.join(self.remote_dir, remote_folder) if remote_folder else self.remote_dir

        command = f"ls -lh {shlex.quote(target_dir)}"
        # command = f"ls -lh {target_dir}"
        stdin, stdout, stderr = self.ssh.exec_command(command)
        out = stdout.read().decode().strip()
        err = stderr.read().decode().strip()

        if err:
            if "No such file or directory" in err:
                return {"status": "not_found", "message": f"Remote folder '{target_dir}' does not exist."}
            else:
                return {"status": "error", "message": err}
        elif out:
            return {"status": "ok", "folder": target_dir, "contents": out.splitlines()}
        else:
            return {"status": "ok", "folder": target_dir, "contents": []}

    def _ensure_remote_dirs(self, path):
        """Recursively create directories on the remote Pi if they don't exist."""
        dirs = []
        while path not in ('', '/'):
            dirs.insert(0, posixpath.basename(path))
            path = posixpath.dirname(path)

        current_path = '/'
        for d in dirs:
            current_path = posixpath.join(current_path, d)
            try:
                self.sftp.stat(current_path)
            except FileNotFoundError:
                try:
                    self.sftp.mkdir(current_path)
                except IOError as e:
                    # Some SFTP servers throw generic IOError if exists/permissions,
                    # re-stat to confirm existence or raise.
                    try:
                        self.sftp.stat(current_path)
                    except Exception:
                        raise

    def upload_file(self, local_path, remote_filename=None, remote_folder=None, overwrite=False):
        if not remote_filename:
            remote_filename = os.path.basename(local_path)

        # Build full remote path: remote_dir + optional remote_folder + filename
        if remote_folder:
            if remote_folder.startswith("/"):
                # Absolute: use as-is (e.g. /mnt/t7_2/videos)
                full_remote_dir = remote_folder
            else:
                # Relative: treat as subpath under the configured remote_dir
                full_remote_dir = posixpath.join(self.remote_dir, remote_folder)
        else:
            full_remote_dir = self.remote_dir

        remote_full_path = posixpath.join(full_remote_dir, remote_filename)

        # Ensure remote folders exist
        self._ensure_remote_dirs(full_remote_dir)

        try:
            self.sftp.stat(remote_full_path)  # check if file exists
            if not overwrite:
                raise FileExistsError(
                    f"Remote file '{remote_filename}' already exists. Set `overwrite=True` to replace it.")
        except FileNotFoundError:
            pass  # file doesn't exist, proceed

        file_size = os.path.getsize(local_path)
        self.sftp.put(local_path, remote_full_path, callback=self._progress_callback(file_size))

        print(f"Uploaded: {local_path} → {remote_full_path}")

    def download_file(self, remote_filename, local_path=None, remote_folder=None, overwrite=False):
        # Build remote path from optional subfolder
        if remote_folder:
            full_remote_dir = posixpath.join(self.remote_dir, remote_folder)
        else:
            full_remote_dir = self.remote_dir

        remote_path = posixpath.join(full_remote_dir, remote_filename)

        if not local_path:
            local_path = remote_filename

        # Check if remote file exists
        try:
            self.sftp.stat(remote_path)
        except FileNotFoundError:
            raise FileNotFoundError(f"Remote file '{remote_path}' does not exist.")

        # Check if local file exists
        if os.path.exists(local_path) and not overwrite:
            raise FileExistsError(
                f"Local file '{local_path}' already exists. Use `overwrite=True` to replace it.")

        attr = self.sftp.stat(remote_path)
        file_size = attr.st_size

        local_dir = os.path.dirname(os.path.abspath(local_path))
        if local_dir and not os.path.exists(local_dir):
            os.makedirs(local_dir, exist_ok=True)

        self.sftp.get(remote_path, local_path, callback=self._progress_callback(file_size))

        print(f"Downloaded: {remote_path} → {local_path}")

    def _safe_target(self, target_path: str) -> str:
        """
        Resolve the target path on the server, ensure it's inside remote_dir,
        and not one of the protected paths (e.g. uploads/ or the base root).
        """
        canonical = self.sftp.normalize(target_path)  # resolves .. and symlinks

        # Ensure target lives under remote_dir
        if not (canonical == self.remote_dir or canonical.startswith(self.remote_dir + "/")):
            raise PermissionError("Operation not permitted: target is outside the configured storage root.")

        # Block deleting protected roots exactly (but allow contents)
        if canonical in self._protected_paths:
            raise PermissionError(f"Operation not permitted: deletion of protected path '{canonical}' is restricted.")

        return canonical


    def delete_file_or_folder(self, target, remote_folder=None):
        """
        Secure delete: normalises paths, blocks deleting protected roots (base, uploads),
        prevents escapes via '..' or symlinks, and re-checks on every recursive step.
        """

        import stat

        # Build and normalise the base dir first
        base_dir = posixpath.join(self.remote_dir, remote_folder) if remote_folder else self.remote_dir
        base_dir = self.sftp.normalize(base_dir)

        # Build raw target and run through guard (may raise PermissionError)
        raw_target_path = posixpath.join(base_dir, target)
        target_path = self._safe_target(raw_target_path)

        # target_path = posixpath.join(base_dir, target)

        def _recursive_delete(path):
            try:
                # Re-guard every step to avoid mid-tree symlink tricks
                path = self._safe_target(path)
                st_mode = self.sftp.stat(path).st_mode

                # mode = self.sftp.stat(path).st_mode
                if stat.S_ISDIR(st_mode):
                    for item in self.sftp.listdir(path):
                        _recursive_delete(posixpath.join(path, item))
                    self.sftp.rmdir(path)
                    print(f"Deleted folder: {path}")
                else:
                    self.sftp.remove(path)
                    print(f"Deleted file: {path}")
            except FileNotFoundError:
                print(f"[Info] '{path}' does not exist.")
            except PermissionError as pe:
                print(f"[Secure-Block] {pe}")
                raise
            except Exception as e:
                print(f"[Error] Failed to delete '{path}': {e}")

        _recursive_delete(target_path)

    def detect_mergerfs_branches(self) -> list[str]:
        """
        Parse /etc/fstab on the Pi and return the list of mergerfs branch paths.
        """
        import shlex

        pool_target = self.remote_dir if self.remote_dir else "/mnt/storage"

        # 1) Try findmnt on the pool target
        cmd = f"findmnt -no SOURCE -T {shlex.quote(pool_target)} 2>/dev/null || true"
        out, _, _ = self._exec(cmd, timeout=5)
        src = out.strip()
        if src.startswith("mergerfs#"):
            branches_part = src.split("#", 1)[1]
            return [p for p in branches_part.split(":") if p]

        # 2) Try any mounted mergerfs source
        out, _, _ = self._exec("findmnt -t fuse.mergerfs -no SOURCE | head -n1 || true", timeout=5)
        src = out.strip()
        if src.startswith("mergerfs#"):
            branches_part = src.split("#", 1)[1]
            return [p for p in branches_part.split(":") if p]

        # 3) Fallback: parse fstab (ignore commented lines, allow leading spaces)
        out, _, _ = self._exec(r"awk '!/^\s*#/ && $1 ~ /^mergerfs#/ {print $1; exit}' /etc/fstab || true", timeout=5)
        src = out.strip()
        if src.startswith("mergerfs#"):
            branches_part = src.split("#", 1)[1]
            return [p for p in branches_part.split(":") if p]

        return []


    def ensure_pool_dirs(self, subpath: str, branches: list[str]):
        """
        Ensure the same subpath exists on all pool branches so epmfs can balance.
        Example: subpath='uploads', branches=['/mnt/t7_1','/mnt/t7_2']
        """
        import shlex
        # Build a single remote shell command for efficiency
        parts = []
        for b in branches:
            parts.append(f"mkdir -p {shlex.quote(posixpath.join(b, subpath))}")
        cmd = " && ".join(parts)
        self._exec(cmd, timeout=10)


    def _exec(self, cmd: str, timeout: int = 15):
        """
        Run a shell command on the Pi via SSH and return (stdout, stderr, exit_status).
        Keeping it here avoids repeating the exec/read boilerplate everywhere.
        """
        stdin, stdout, stderr = self.ssh.exec_command(cmd, timeout=timeout)
        out = stdout.read().decode(errors="replace")
        err = stderr.read().decode(errors="replace")
        code = stdout.channel.recv_exit_status()
        return out, err, code

    def get_system_info(self) -> dict:
        """
        Gather system info from the Pi:
          - RAM (total/used/available) from /proc/meminfo
          - Mount usage from df (bytes)
          - Block devices (labels/UUIDs/mounts) from lsblk (JSON)
          - Include mergerfs pool if present (fuse mount)
        Return a structured dict ready to JSONify.
        """
        import json
        import re

        # 1) RAM: parse /proc/meminfo (kB -> bytes)
        meminfo_out, _, _ = self._exec("cat /proc/meminfo")
        mem_kb = {}
        for line in meminfo_out.splitlines():
            if ":" not in line:
                continue
            k, v = line.split(":", 1)
            m = re.search(r"(\d+)\s*kB", v)
            if m:
                mem_kb[k.strip()] = int(m.group(1))
        ram_total = mem_kb.get("MemTotal", 0) * 1024
        ram_available = mem_kb.get("MemAvailable", 0) * 1024
        ram_used = max(ram_total - ram_available, 0)

        # 2) Mount usage: df in bytes for clean calculations
        df_cmd = r"df -B1 --output=source,fstype,size,used,avail,target | tail -n +2"
        df_out, _, _ = self._exec(df_cmd)
        mount_rows = []
        for line in df_out.splitlines():
            parts = line.split()
            if len(parts) < 6:
                # Some mountpoints may contain spaces; re-join the tail
                source, fstype, size, used, avail = parts[:5]
                target = " ".join(parts[5:])
            else:
                source, fstype, size, used, avail, target = parts[:6]
            try:
                size_i = int(size); used_i = int(used); avail_i = int(avail)
            except ValueError:
                size_i = used_i = avail_i = 0
            mount_rows.append({
                "source": source,
                "fstype": fstype,
                "size_bytes": size_i,
                "used_bytes": used_i,
                "avail_bytes": avail_i,
                "mountpoint": target
            })

        # 3) Block devices with labels/UUIDs as JSON
        lsblk_cmd = "lsblk -J -b -o NAME,TYPE,FSTYPE,LABEL,UUID,SIZE,MOUNTPOINT"
        lsblk_out, lsblk_err, lsblk_code = self._exec(lsblk_cmd)
        try:
            blk = json.loads(lsblk_out)  # {'blockdevices': [...]}
        except Exception:
            blk = {"error": "lsblk_parse_failed", "raw": lsblk_out, "stderr": lsblk_err, "code": lsblk_code}

        # Quick lookups to enrich devices with usage
        by_target = {m["mountpoint"]: m for m in mount_rows if m.get("mountpoint")}
        drives = []

        def walk(nodes):
            for n in nodes:
                entry = {
                    "name": n.get("name"),
                    "type": n.get("type"),
                    "fstype": n.get("fstype"),
                    "label": n.get("label"),
                    "uuid": n.get("uuid"),
                    "size_bytes": int(n.get("size", 0) or 0),
                    "mountpoint": n.get("mountpoint"),
                }
                mp = entry["mountpoint"]
                if mp and mp in by_target:
                    usage = by_target[mp]
                    entry.update({
                        "total_bytes": usage["size_bytes"],
                        "used_bytes": usage["used_bytes"],
                        "avail_bytes": usage["avail_bytes"],
                    })
                drives.append(entry)
                if "children" in n and isinstance(n["children"], list):
                    walk(n["children"])

        if isinstance(blk, dict) and "blockdevices" in blk:
            walk(blk["blockdevices"])

        # Add FUSE/mergerfs mounts that lsblk doesn't list as block devices
        for m in mount_rows:
            if m["fstype"].startswith("fuse") and not any(d.get("mountpoint") == m["mountpoint"] for d in drives):
                drives.append({
                    "name": m["source"], "type": "fuse", "fstype": m["fstype"],
                    "label": None, "uuid": None, "size_bytes": m["size_bytes"],
                    "mountpoint": m["mountpoint"],
                    "total_bytes": m["size_bytes"], "used_bytes": m["used_bytes"], "avail_bytes": m["avail_bytes"],
                })

        # Identify microSD partitions (typical mmcblk0p1/p2)
        microsd = [d for d in drives if (d.get("name") or "").startswith("mmcblk0p")]

        # Helper to format bytes → GiB
        def to_gb(b):
            return round(b / (1024 ** 3), 2) if b else 0.0

        def percent(used, total):
            return round((used / total) * 100, 1) if total else 0.0

        # Build concise drive list (ignore tmpfs/dev)
        drive_summary = []
        for d in drives:
            if d.get("fstype") in (None, "devtmpfs", "tmpfs"):
                continue
            if not d.get("mountpoint"):
                continue
            # Skip internal microSD partitions
            if d.get("name", "").startswith("mmcblk"):
                continue
            total = d.get("total_bytes") or d.get("size_bytes") or 0
            used = d.get("used_bytes", 0)
            avail = d.get("avail_bytes", 0)
            drive_summary.append({
                "label": d.get("label") or d.get("name"),
                "mountpoint": d.get("mountpoint"),
                "fstype": d.get("fstype"),
                "total_gb": to_gb(total),
                "used_gb": to_gb(used),
                "free_gb": to_gb(avail),
                "used_percent": percent(used, total)
            })
        drive_summary = sorted(drive_summary, key=lambda x: x["mountpoint"])

        # MicroSD summary (boot + root)
        microsd_summary = {}
        for d in drives:
            if d.get("label") == "rootfs":
                microsd_summary["root_total_gb"] = to_gb(d.get("total_bytes"))
                microsd_summary["root_used_gb"] = to_gb(d.get("used_bytes"))
            elif d.get("label") == "bootfs":
                microsd_summary["boot_total_gb"] = to_gb(d.get("total_bytes"))
                microsd_summary["boot_used_gb"] = to_gb(d.get("used_bytes"))

        return {
            "ram": {
                "total_gb": to_gb(ram_total),
                "used_gb": to_gb(ram_used),
                "free_gb": to_gb(ram_available),
                "used_percent": percent(ram_used, ram_total),
            },
            "drives": drive_summary,
            "microsd": microsd_summary
        }
