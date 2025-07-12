# pi_helper.py

import os
import paramiko
import requests
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
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.ssh.connect(
            hostname=self.hostname,
            port=self.port,
            username=self.username,
            password=self.password,
            timeout=10
        )
        self.sftp = self.ssh.open_sftp()
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
                if transferred >= total_size:
                    pbar.close()

        return callback

    def list_files(self, remote_folder=None):
        target_dir = os.path.join(self.remote_dir, remote_folder) if remote_folder else self.remote_dir
        command = f"ls -lh {target_dir}"
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
            dirs.insert(0, os.path.basename(path))
            path = os.path.dirname(path)

        current_path = '/'
        for d in dirs:
            current_path = os.path.join(current_path, d)
            try:
                self.sftp.stat(current_path)
            except FileNotFoundError:
                self.sftp.mkdir(current_path)

    def upload_file(self, local_path, remote_filename=None, remote_folder=None, overwrite=False):
        if not remote_filename:
            remote_filename = os.path.basename(local_path)

        # Build full remote path: remote_dir + optional remote_folder + filename
        if remote_folder:
            full_remote_dir = os.path.join(self.remote_dir, remote_folder)
        else:
            full_remote_dir = self.remote_dir

        remote_full_path = os.path.join(full_remote_dir, remote_filename)

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
            full_remote_dir = os.path.join(self.remote_dir, remote_folder)
        else:
            full_remote_dir = self.remote_dir

        remote_path = os.path.join(full_remote_dir, remote_filename)

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
        self.sftp.get(remote_path, local_path, callback=self._progress_callback(file_size))

        print(f"Downloaded: {remote_path} → {local_path}")

    def delete_file_or_folder(self, target, remote_folder=None):
        import stat

        if remote_folder:
            base_dir = os.path.join(self.remote_dir, remote_folder)
        else:
            base_dir = self.remote_dir

        target_path = os.path.join(base_dir, target)

        def _recursive_delete(path):
            try:
                mode = self.sftp.stat(path).st_mode
                if stat.S_ISDIR(mode):
                    for item in self.sftp.listdir(path):
                        _recursive_delete(os.path.join(path, item))
                    self.sftp.rmdir(path)
                    print(f"Deleted folder: {path}")
                else:
                    self.sftp.remove(path)
                    print(f"Deleted file: {path}")
            except FileNotFoundError:
                print(f"[Info] '{path}' does not exist.")
            except Exception as e:
                print(f"[Error] Failed to delete '{path}': {e}")

        _recursive_delete(target_path)
