# pidrive/transfers.py

import shlex

from pidrive.temp.utils import *

def download_direct(client, *, url: str, target_dir: str, remote_filename: str = "",
                    overwrite: bool = False, timeout: int = 0) -> dict:
    if not url.lower().startswith(("http://","https://")):
        raise ValueError("Only http(s) URLs are allowed.")
    client._exec(f"mkdir -p {shlex.quote(target_dir)}", timeout=10)
    final = (remote_filename or guess_filename_from_url(url)).strip()
    final_path = posixpath.join(target_dir, final)
    temp_path = final_path + ".part"
    try:
        client.sftp.stat(final_path)
        if not overwrite:
            raise FileExistsError(f"Remote file '{final_path}' already exists.")
    except FileNotFoundError:
        pass
    out, _, rc = client._exec("command -v curl", timeout=5)
    fetch = (
        f"curl -L --fail --retry 2 --speed-time 30 --speed-limit 1024 "
        f"-o {shlex.quote(temp_path)} {shlex.quote(url)}"
    ) if rc == 0 else (
        f"wget --tries=3 --timeout=60 -O {shlex.quote(temp_path)} {shlex.quote(url)}"
    )
    if timeout and timeout > 0:
        fetch = f"timeout {int(timeout)}s {fetch}"
    out, err, rc = client._exec(fetch, timeout=max(timeout,120) if timeout else 0)
    if rc != 0:
        try: client.sftp.remove(temp_path)
        except Exception: pass
        raise RuntimeError(f"Download failed (rc={rc}). stderr: {err or out}")
    _, err, rc = client._exec(f"mv -f {shlex.quote(temp_path)} {shlex.quote(final_path)}", timeout=10)
    if rc != 0:
        try: client.sftp.remove(temp_path)
        except Exception: pass
        raise RuntimeError(f"Failed to finalise file move: {err}")
    st = client.sftp.stat(final_path)
    return {"path": final_path, "bytes": st.st_size}

def upload_file(client, local_path: str, remote_filename: str | None = None, remote_folder: str | None = None,
                overwrite: bool = False,
                atomic: bool = True):
    """
    Upload a local file to the Pi via SFTP.

    - remote_folder:
        * absolute (starts with "/") -> used as-is
        * relative -> placed under client.remote_dir
    - atomic: upload to <remote>.part then rename to final
    """
    if not os.path.isfile(local_path):
        raise FileNotFoundError(f"Local file not found: {local_path}")

    base = client.remote_dir
    if remote_folder:
        full_remote_dir = remote_folder if remote_folder.startswith("/") else posixpath.join(base, remote_folder)
    else:
        full_remote_dir = base

    ensure_remote_dirs(client.sftp, full_remote_dir)

    remote_filename = remote_filename or os.path.basename(local_path)
    remote_final = posixpath.join(full_remote_dir, remote_filename)
    remote_part = remote_final + ".part" if atomic else remote_final

    try:
        client.sftp.stat(remote_final)
        if not overwrite:
            raise FileExistsError(f"Remote file '{remote_final}' already exists. Use overwrite=True to replace it.")
    except FileNotFoundError:
        pass

    if atomic:
        try:
            client.sftp.remove(remote_part)
        except FileNotFoundError:
            pass
        except Exception:
            pass

    size = os.path.getsize(local_path)
    client.sftp.put(local_path, remote_part, callback=lambda transferred, _: None)

    if atomic:
        mv_cmd = f"mv -f {shlex.quote(remote_part)} {shlex.quote(remote_final)}"
        _, err, rc = client._exec(mv_cmd, timeout=10)
        if rc != 0:
            # best-effort cleanup; don't hide the error
            try:
                client.sftp.remove(remote_part)
            except Exception:
                pass
            raise RuntimeError(f"Failed to finalise remote upload: {err or 'mv failed'}")

    return {"remote_path": remote_final, "bytes": size}

def download_file(client, remote_filename: str, local_path: str | None = None, remote_folder: str | None = None,
                  overwrite: bool = False, atomic: bool = True):
    """
    Download a file from the Pi via SFTP.

    - remote_folder:
        * absolute (starts with "/") -> used as-is
        * relative -> under client.remote_dir
    - atomic: download to <local>.part then os.replace() to final name
    """

    base = client.remote_dir

    if remote_folder:
        full_remote_dir = remote_folder if remote_folder.startswith("/") else posixpath.join(base, remote_folder)
    else:
        full_remote_dir = base

    remote_path = posixpath.join(full_remote_dir, remote_filename)

    st = client.sftp.stat(remote_path)
    total_size = getattr(st, "st_size", None)

    if not local_path:
        local_path = remote_filename
    local_path = os.path.abspath(local_path)

    if os.path.exists(local_path) and not overwrite:
        raise FileExistsError(f"Local file '{local_path}' already exists. Use overwrite=True to replace it.")

    os.makedirs(os.path.dirname(local_path) or ".", exist_ok=True)

    tmp_path = f"{local_path}.part" if atomic else local_path
    if atomic and os.path.exists(tmp_path):
        try:
            os.remove(tmp_path)
        except OSError:
            pass

    client.sftp.get(remote_path, tmp_path, callback=lambda transferred, _sz: None)

    if atomic:
        os.replace(tmp_path, local_path)

    return {
        "remote_path": remote_path,
        "local_path": local_path,
        "bytes": total_size
    }

