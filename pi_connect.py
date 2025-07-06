
import os
import paramiko
import requests

from dotenv import load_dotenv
load_dotenv()

username = os.getenv("PI_USER")
password = os.getenv("PI_PASSWORD")
remote_dir = os.getenv("PI_REMOTE_DIR")
ngrok_api_key = os.getenv("NGROK_API_KEY")

if not all([username, password, remote_dir, ngrok_api_key]):
    raise ValueError("Missing one or more required environment variables.")

headers = {
    "Authorization": f"Bearer {ngrok_api_key}",
    "Ngrok-Version": "2"
}

try:
    response = requests.get("https://api.ngrok.com/tunnels", headers=headers, timeout=5)
    response.raise_for_status()
    tunnels = response.json().get("tunnels", [])

    tcp_tunnel = next((t for t in tunnels if t["proto"] == "tcp"), None)
    if not tcp_tunnel:
        raise Exception("No active TCP tunnel found")

    public_url = tcp_tunnel["public_url"]
    _, address = public_url.split("tcp://")
    hostname, port = address.split(":")
    print(f"Resolved ngrok address: {hostname}:{port}")

except Exception as e:
    raise RuntimeError(f"Failed to retrieve ngrok tunnel info: {e}")

# SSH and list directory
try:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(hostname, port=int(port), username=username, password=password, timeout=10)

    command = f"ls -lh {remote_dir}"
    stdin, stdout, stderr = ssh.exec_command(command)

    output = stdout.read().decode()
    error = stderr.read().decode()

    if output:
        print("\nFiles in directory:")
        print(output)
    if error:
        print("Error output:")
        print(error)

    ssh.close()
    del ssh, stdin, stdout, stderr

except Exception as e:
    raise RuntimeError(f"SSH connection failed: {e}")

