from pi_helper import PiSSHClient

# List all the files
with PiSSHClient() as client:
    client.list_files(remote_folder="")


# Upload a file
# with PiSSHClient() as client:
#     try:
#         client.upload_file("imager_latest_amd64.deb", remote_folder="test/test2/", overwrite=True)
#     except FileExistsError as e:
#         print(f"[Warning] {e}")


# Download a file
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


# Delete a file
# with PiSSHClient() as client:
#     client.delete_file_or_folder("imager_latest_amd64.deb")  # deletes file
#     client.delete_file_or_folder("test", remote_folder="")  # deletes folder and contents
