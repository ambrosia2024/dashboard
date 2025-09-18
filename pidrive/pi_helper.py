# pidrive/pi_helper.py

import os
import paramiko
import posixpath
import requests
import shlex
import threading
import time

from dotenv import load_dotenv
from tqdm import tqdm
from urllib.parse import urlparse, unquote
from uuid import uuid4

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

    def _guess_filename_from_url(self, url: str) -> str:
        """
        Best-effort name from URL path. Falls back to 'download.bin' when empty.
        Server-provided names via Content-Disposition are not available here
        because we fetch remotely with curl/wget.
        """
        try:
            path = urlparse(url).path
            name = os.path.basename(unquote(path).rstrip("/"))
            return name or "download.bin"
        except Exception:
            return "download.bin"

    def _detect_archive_kind(self, path: str) -> str | None:
        """
        Best-effort archive kind detection by extension (lowercased).
        Returns one of: 'zip','7z','rar','tar','tar.gz','tar.bz2','tar.xz','gz','bz2','xz', or None.
        """
        name = posixpath.basename(path).lower()

        # Common tar+compress combos first
        combos = {
            ('.tar.gz', '.tgz'): 'tar.gz',
            ('.tar.bz2', '.tbz2'): 'tar.bz2',
            ('.tar.xz', '.txz'): 'tar.xz',
        }
        for exts, kind in combos.items():
            if any(name.endswith(ext) for ext in exts):
                return kind

        # Singles (order matters for .gz vs .tar.gz — already handled above)
        if name.endswith('.zip'):
            return 'zip'
        if name.endswith('.7z'):
            return '7z'
        if name.endswith('.rar'):
            return 'rar'
        if name.endswith('.tar'):
            return 'tar'
        if name.endswith('.gz'):
            return 'gz'  # single-file gzip, not tarball
        if name.endswith('.bz2'):
            return 'bz2'
        if name.endswith('.xz'):
            return 'xz'
        return None

    def _archive_stem(self, path: str) -> str:
        """
        Produce a human-friendly folder name from an archive path.
        E.g. foo-1.2.3.tar.gz -> 'foo-1.2.3'
        """
        base = posixpath.basename(path)
        lowered = base.lower()

        # Strip multi-part tars first
        for ext in ('.tar.gz', '.tgz', '.tar.bz2', '.tbz2', '.tar.xz', '.txz'):
            if lowered.endswith(ext):
                return base[: -len(ext)]
        # Then single ext
        for ext in ('.zip', '.7z', '.rar', '.tar', '.gz', '.bz2', '.xz'):
            if lowered.endswith(ext):
                return base[: -len(ext)]
        # Fallback: remove a single trailing extension if present
        root, _ = posixpath.splitext(base)
        return root or 'extracted'

    def download_direct(
            self,
            *,
            url: str,
            target_dir: str,
            remote_filename: str = "",
            overwrite: bool = False,
            timeout: int = 0,
            auto_extract: bool = False,  # set True to auto-extract after download
            extract_dest_dir: str | None = None,  # default = target_dir
            delete_archive_after_extract: bool = True,  # remove archive if extraction succeeds
            return_extraction_errors: bool = True, # if True, keep download success but report extraction error in result
        ) -> dict:
        """
        Ask the Pi to fetch a URL directly into target_dir using curl (falls back to wget).
        Creates target_dir if needed. Writes to a .part then mv for atomicity.

        :param url: http(s) URL
        :param target_dir: absolute path where the file should land
        :param remote_filename: optional final filename; will be guessed from URL if not provided
        :param overwrite: whether to overwrite existing file
        :param timeout: optional overall shell timeout in seconds (0 = let curl decide)
        """

        # 1) Validate inputs
        if not url.lower().startswith(("http://", "https://")):
            raise ValueError("Only http(s) URLs are allowed.")

        # Ensure target_dir exists (mkdir -p) and is owned by pi:storageusers if that matches policy
        self._ensure_remote_dirs(target_dir)  # recursive create via SFTP
        out, err, rc = self._exec(f"mkdir -p {shlex.quote(target_dir)}", timeout=10)
        if rc != 0:  # non-zero means shell command failed
            raise RuntimeError(
                f"Failed to ensure target directory: {target_dir} (rc={rc}). {(err or out).strip()}"
            )
        # Verify the path is a directory and visible on the mount
        try:
            self.sftp.listdir(target_dir)  # listing guarantees it's a directory, not a file
        except FileNotFoundError as e:
            raise RuntimeError(
                f"Target directory is not available on the pool mount: {target_dir}. Details: {e}"
            )

        # Pick filename
        final_name = remote_filename or self._guess_filename_from_url(url)

        # Force a plain basename and guard empties/dots
        final_name = posixpath.basename(final_name).strip()
        if final_name in ("", ".", ".."):
            final_name = "download.bin"

        # if the caller supplies a Windows path, drop any backslash segments
        # (POSIX treats '\' as a valid char; this ensures we don't keep "C:\foo\bar.mkv")
        if "\\" in final_name:
            final_name = final_name.split("\\")[-1]  # keep the last segment

        # clamp very long names for filesystems with 255-byte limits
        if len(final_name) > 255:
            final_name = final_name[:255]

        final_path = posixpath.join(target_dir, final_name)
        temp_path = f"{final_path}.part.{uuid4().hex[:8]}"

        # Existence check
        try:
            self.sftp.stat(final_path)
            if not overwrite:
                raise FileExistsError(
                    f"Remote file '{final_path}' already exists. Use overwrite=True to replace it.")
        except FileNotFoundError:
            pass  # ok

        # Build a safe curl command.
        curl_cmd = (
            f"umask 0002; "  # <-- group-writable outputs
            f"curl -sS -L --fail --retry 2 "
            f"--speed-time 30 --speed-limit 1024 "
            f"--create-dirs "
            f"-o {shlex.quote(temp_path)} {shlex.quote(url)}"
        )

        # If curl is absent, try wget
        _, _, rc = self._exec("command -v curl >/dev/null 2>&1", timeout=5)
        if rc != 0:
            curl_cmd = (
                f"umask 0002; "
                f"wget -O {shlex.quote(temp_path)} --tries=3 --timeout=60 {shlex.quote(url)}"
            )

        # Optional: enforce a hard timeout from our side
        if timeout and timeout > 0:
            curl_cmd = f"timeout {int(timeout)}s {curl_cmd}"

        # Download
        exec_timeout = max(timeout, 120) if (timeout and timeout > 0) else None
        out, err, rc = self._exec(curl_cmd, timeout=exec_timeout)

        if rc != 0:
            # Clean up partial file if present
            try:
                self.sftp.remove(temp_path)
            except Exception:
                pass
            raise RuntimeError(f"Download failed (rc={rc}). stderr: {err or out}")

        try:
            st_part = self.sftp.stat(temp_path)
        except FileNotFoundError:
            raise RuntimeError(
                f"Download reported success but temp file not found: {temp_path}. "
                f"stderr: {(err or out).strip()}"
            )

        if getattr(st_part, "st_size", 0) == 0:
            raise RuntimeError(
                f"Downloaded 0 bytes to {temp_path}. URL may require cookies/headers or is not directly downloadable."
            )

        # --- Move into place using shell mv (more reliable on mergerfs/FUSE) ---
        mv_cmd = (
            f"umask 0002; "
            f"mv -f -- {shlex.quote(temp_path)} {shlex.quote(final_path)}"
        )
        out, err, rc = self._exec(mv_cmd, timeout=10)
        if rc != 0:
            # Best-effort cleanup if mv failed
            try:
                self.sftp.remove(temp_path)
            except Exception:
                pass
            raise RuntimeError(
                f"Failed to finalise file move (rc={rc}). {(err or out).strip() or 'mv failed'}"
            )

        # Return a small summary including size
        last_err = None
        for _ in range(5):  # ~0.5s total
            try:
                st = self.sftp.stat(final_path)
                result: dict = {"path": final_path, "bytes": st.st_size}

                # --- NEW: optional auto-extract if looks like an archive ---
                archive_kind = self._detect_archive_kind(final_path)
                result["archive_kind"] = archive_kind  # None if not an archive

                if auto_extract and archive_kind:
                    try:
                        extracted = self.extract_remote_archive(
                            archive_path=final_path,
                            dest_dir=extract_dest_dir or target_dir,
                            overwrite=overwrite,  # mirror caller's overwrite behaviour
                            delete_archive=delete_archive_after_extract,
                            timeout=max(timeout, 0),
                        )
                        result["extracted"] = extracted  # {'extracted_to','tool','files','bytes'}
                    except Exception as ex:
                        # Either bubble up (default) or attach error to result
                        if return_extraction_errors:
                            result["extraction_error"] = str(ex)
                        else:
                            raise  # keep previous behaviour: fail the call

                return result

            except FileNotFoundError as e:
                last_err = e
                time.sleep(0.1)

        raise RuntimeError(f"Final file not found after move: {final_path}. Details: {last_err}")

    def extract_remote_archive(
            self,
            *,
            archive_path: str,
            dest_dir: str | None = None,
            overwrite: bool = False,
            delete_archive: bool = False,
            timeout: int = 0
    ) -> dict:
        """
        Extract an archive on the Pi, inside dest_dir/<archive_stem>/.
        Creates a unique temp extraction directory and then atomically renames it.

        Supports: 7z, zip, rar, tar, tar.gz/tgz, tar.bz2/tbz2, tar.xz/txz, gz, bz2, xz.

        :param archive_path: absolute path to the downloaded archive on the Pi
        :param dest_dir: where to create the output folder; defaults to parent of archive
        :param overwrite: if True and final folder exists, it will be replaced
        :param delete_archive: if True, removes the archive after successful extraction
        :param timeout: hard shell timeout in seconds for the extract command (0 = no wrapper)
        :return: dict with {'extracted_to': <final_dir>, 'tool': <tool>, 'files': <int>, 'bytes': <int>}
        """

        # --- Validate inputs & existence ---
        try:
            st = self.sftp.stat(archive_path)
        except FileNotFoundError:
            raise FileNotFoundError(f"Archive not found on remote: {archive_path}")

        if dest_dir is None:
            dest_dir = posixpath.dirname(archive_path) or "/tmp"

        # Ensure dest_dir exists
        self._ensure_remote_dirs(dest_dir)
        out, err, rc = self._exec(f"mkdir -p {shlex.quote(dest_dir)}", timeout=10)
        if rc != 0:
            raise RuntimeError(f"Failed to ensure dest dir {dest_dir}: {(err or out).strip()} (rc={rc})")

        kind = self._detect_archive_kind(archive_path)
        if kind is None:
            raise ValueError(f"Cannot determine archive type from name: {archive_path}")

        # Create stable final dir & unique temp dir
        stem = self._archive_stem(archive_path)
        final_dir = posixpath.join(dest_dir, stem)
        temp_dir = posixpath.join(dest_dir, f".extract-{stem}.{uuid4().hex[:8]}")

        # Handle overwrite logic up-front
        if not overwrite:
            try:
                self.sftp.stat(final_dir)
                raise FileExistsError(
                    f"Destination folder already exists: {final_dir}. "
                    f"Use overwrite=True to replace it."
                )
            except FileNotFoundError:
                pass  # good, doesn't exist yet
        else:
            # If overwriting, ensure we can remove any previous folder
            cmd_rm = f"rm -rf -- {shlex.quote(final_dir)}"
            self._exec(cmd_rm, timeout=10)

        # Make a fresh temp dir
        out, err, rc = self._exec(f"mkdir -p {shlex.quote(temp_dir)}", timeout=10)
        if rc != 0:
            raise RuntimeError(f"Failed to create temp dir {temp_dir}: {(err or out).strip()} (rc={rc})")

        # Figure out which tools are available
        def has(cmd: str) -> bool:
            _, _, r = self._exec(f"command -v {shlex.quote(cmd)} >/dev/null 2>&1", timeout=5)
            return r == 0

        have_7z = has("7z")
        have_unzip = has("unzip")
        have_unrar = has("unrar") or has("unar")  # 'unar' (The Unarchiver) if installed
        have_tar = has("tar")
        have_gunzip = has("gunzip")
        have_bunzip2 = has("bunzip2")
        have_unxz = has("unxz") or has("xz")

        # Prefer a universal extractor if present (7z can do most formats)
        tool = None
        if have_7z:
            # 7z: -y (assume Yes), -bso0/-bsp0 (quieter), -oDIR for output
            extract_cmd = (
                f"umask 0002; "
                f"7z x -y -bso0 -bsp0 -o{shlex.quote(temp_dir)} -- {shlex.quote(archive_path)}"
            )
            tool = "7z"
        else:
            # Fallback per type
            if kind in ("tar", "tar.gz", "tar.bz2", "tar.xz"):
                if not have_tar:
                    raise RuntimeError("GNU tar not available on remote to extract tar archives.")
                # GNU tar auto-detects compression with just -xf (if built with libs)
                extract_cmd = (
                    f"umask 0002; "
                    f"tar -xpf {shlex.quote(archive_path)} -C {shlex.quote(temp_dir)}"
                )
                tool = "tar"
            elif kind == "zip":
                if not have_unzip:
                    raise RuntimeError("unzip not available on remote for .zip archives.")
                extract_cmd = (
                    f"umask 0002; "
                    f"unzip -q -o -- {shlex.quote(archive_path)} -d {shlex.quote(temp_dir)}"
                )
                tool = "unzip"
            elif kind == "rar":
                if has("unrar"):
                    extract_cmd = (
                        f"umask 0002; "
                        f"unrar x -o+ -- {shlex.quote(archive_path)} {shlex.quote(temp_dir)}/"
                    )
                    tool = "unrar"
                elif has("unar"):
                    extract_cmd = (
                        f"umask 0002; "
                        f"unar -quiet -force-overwrite -output-directory {shlex.quote(temp_dir)} -- {shlex.quote(archive_path)}"
                    )
                    tool = "unar"
                else:
                    raise RuntimeError("Neither unrar nor unar available for .rar archives.")
            elif kind == "gz":
                if not have_gunzip:
                    raise RuntimeError("gunzip not available for .gz file.")
                # Single-file .gz (NOT a tarball). We’ll inflate to <stem>
                out_file = posixpath.join(temp_dir, self._archive_stem(archive_path))
                extract_cmd = (
                    f"umask 0002; "
                    f"gunzip -c -- {shlex.quote(archive_path)} > {shlex.quote(out_file)}"
                )
                tool = "gunzip"
            elif kind == "bz2":
                if not have_bunzip2:
                    raise RuntimeError("bunzip2 not available for .bz2 file.")
                out_file = posixpath.join(temp_dir, self._archive_stem(archive_path))
                extract_cmd = (
                    f"umask 0002; "
                    f"bunzip2 -c -- {shlex.quote(archive_path)} > {shlex.quote(out_file)}"
                )
                tool = "bunzip2"
            elif kind == "xz":
                if not have_unxz:
                    raise RuntimeError("unxz (or xz) not available for .xz file.")
                out_file = posixpath.join(temp_dir, self._archive_stem(archive_path))
                # some systems have 'xz -d -c' instead of 'unxz -c'
                if has("unxz"):
                    extract_cmd = (
                        f"umask 0002; "
                        f"unxz -c -- {shlex.quote(archive_path)} > {shlex.quote(out_file)}"
                    )
                else:
                    extract_cmd = (
                        f"umask 0002; "
                        f"xz -d -c -- {shlex.quote(archive_path)} > {shlex.quote(out_file)}"
                    )
                tool = "unxz"
            else:
                raise RuntimeError(f"Unsupported archive kind: {kind}")

        # Optional hard timeout wrapper
        if timeout and timeout > 0:
            extract_cmd = f"timeout {int(timeout)}s {extract_cmd}"

        # --- Execute extraction ---
        exec_timeout = max(timeout, 300) if (timeout and timeout > 0) else None
        out, err, rc = self._exec(extract_cmd, timeout=exec_timeout)
        if rc != 0:
            # Best-effort cleanup
            self._exec(f"rm -rf -- {shlex.quote(temp_dir)}", timeout=10)
            raise RuntimeError(f"Extraction failed (tool={tool}, rc={rc}). {(err or out).strip()}")

        # --- Atomically move temp_dir -> final_dir (or remove existing if overwriting) ---
        mv_cmd = (
            f"umask 0002; "
            f"rm -rf -- {shlex.quote(final_dir)} && "
            f"mv -- {shlex.quote(temp_dir)} {shlex.quote(final_dir)}"
        )
        out, err, rc = self._exec(mv_cmd, timeout=15)
        if rc != 0:
            # Try to clean temp_dir if move failed
            self._exec(f"rm -rf -- {shlex.quote(temp_dir)}", timeout=10)
            raise RuntimeError(f"Failed to finalise extraction move: {(err or out).strip()} (rc={rc})")

        # Optionally delete original archive after success
        if delete_archive:
            self._exec(f"rm -f -- {shlex.quote(archive_path)}", timeout=10)

        # Summarise results
        # Count files recursively and compute total bytes in extracted dir
        count_cmd = f"find {shlex.quote(final_dir)} -type f | wc -l"
        out_c, _, rc_c = self._exec(count_cmd, timeout=10)
        files_count = int(out_c.strip()) if rc_c == 0 and out_c.strip().isdigit() else 0

        size_cmd = f"du -sb -- {shlex.quote(final_dir)} | awk '{{print $1}}'"
        out_s, _, rc_s = self._exec(size_cmd, timeout=10)
        total_bytes = int(out_s.strip()) if rc_s == 0 and out_s.strip().isdigit() else 0

        return {
            "extracted_to": final_dir,
            "tool": tool,
            "files": files_count,
            "bytes": total_bytes,
        }

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


    def delete_file_or_folder(self, target: str | bytes, remote_folder: str | bytes | None = None) -> None:
        """
        Secure delete: normalises paths, blocks deleting protected roots (base, uploads),
        prevents escapes via '..' or symlinks, and re-checks on every recursive step.
        """

        import stat
        from typing import cast

        if isinstance(target, (bytes, bytearray)):
            target = target.decode("utf-8")
        if remote_folder is not None and isinstance(remote_folder, (bytes, bytearray)):
            remote_folder = remote_folder.decode("utf-8")

        # Build and normalise the base dir first
        base_dir = posixpath.join(self.remote_dir, remote_folder) if remote_folder else self.remote_dir
        base_dir = self.sftp.normalize(base_dir)

        # Build raw target and run through guard (may raise PermissionError)
        raw_target_path = posixpath.join(base_dir, target)
        raw_target_path = cast(str, raw_target_path)
        target_path = self._safe_target(raw_target_path)

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

    # Run a shell command on the remote Pi and capture stdout/err/return code
    def _exec(self, cmd: str, timeout: int | float | None = 15):
        """
        Run a shell command on the Pi via SSH and return (stdout, stderr, exit_status).
        Keeping it here avoids repeating the exec/read boilerplate everywhere.
        """

        # Paramiko: timeout=None => no timeout; timeout=0 => immediate timeout (bad)
        if isinstance(timeout, (int, float)) and timeout <= 0:
            timeout = None

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
