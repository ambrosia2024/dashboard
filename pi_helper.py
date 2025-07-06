import os
import paramiko
import requests
from dotenv import load_dotenv

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

    def list_files(self):
        command = f"ls -lh {self.remote_dir}"
        stdin, stdout, stderr = self.ssh.exec_command(command)
        out, err = stdout.read().decode(), stderr.read().decode()
        if out: print(out)
        if err: print(f"Error:\n{err}")

    def upload_file(self, local_path, remote_filename=None):
        if not remote_filename:
            remote_filename = os.path.basename(local_path)
        remote_path = os.path.join(self.remote_dir, remote_filename)
        self.sftp.put(local_path, remote_path)
        print(f"Uploaded: {local_path} → {remote_path}")

    def download_file(self, remote_filename, local_path=None):
        remote_path = os.path.join(self.remote_dir, remote_filename)
        if not local_path:
            local_path = remote_filename
        self.sftp.get(remote_path, local_path)
        print(f"Downloaded: {remote_path} → {local_path}")
