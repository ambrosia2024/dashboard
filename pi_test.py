from pi_helper import PiSSHClient

# with PiSSHClient() as client:
    # client.list_files()

# with PiSSHClient() as client:
#     try:
#         client.upload_file("imager_latest_amd64.deb", overwrite=True)
#     except FileExistsError as e:
#         print(f"[Warning] {e}")

# with PiSSHClient() as client:
#     try:
#         client.download_file(
#             remote_filename="imager_latest_amd64.deb",
#             local_path="imager_latest_amd64.deb",
#             overwrite=False
#         )
#     except FileNotFoundError as e:
#         print(f"[Error] {e}")
#     except FileExistsError as e:
#         print(f"[Warning] {e}")
