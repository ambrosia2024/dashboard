# pidrive/routes.py

import os
import posixpath
import shutil
import stat
import tempfile

from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import JSONResponse
from pathlib import Path

from .pi_helper import PiSSHClient

router = APIRouter()

@router.post("/upload")
async def upload_file(
    remote_folder: str = Form(..., description="Target subfolder on the Pi"),
    remote_filename: str = Form("", description="Filename to save as on the Pi (optional)"),
    overwrite: bool = Form(False, description="Overwrite file if it already exists"),
    file: UploadFile = File(..., description="The file to upload"),
):
    temp_path: str = ""
    try:
        with tempfile.NamedTemporaryFile(mode="wb", delete=False) as tmp:
            shutil.copyfileobj(file.file, tmp)
            temp_path = tmp.name

        if not temp_path:
            return {"status": "error", "message": "Temporary file path is not set."}

        # Upload using SSH
        with PiSSHClient() as client:
            client.upload_file(
                local_path=temp_path,
                remote_filename=remote_filename or file.filename,
                remote_folder=remote_folder,
                overwrite=overwrite
            )

        return JSONResponse(status_code=201, content={"status": "uploaded", "filename": file.filename})
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})

    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


@router.post("/download")
async def download_file(
    remote_folder: str = Form(..., description="Folder on the Pi to fetch from"),
    remote_filename: str = Form(..., description="Name of the file to download from the Pi"),
    local_path: str = Form("", description="Optional: where to store file temporarily"),
    overwrite: bool = Form(False, description="Overwrite local file if it already exists"),
):
    if not local_path:
        # Use ./downloads/<remote_filename> as fallback
        downloads_dir = Path("./downloads")
        downloads_dir.mkdir(parents=True, exist_ok=True)
        final_path = downloads_dir / remote_filename
    else:
        final_path = Path(local_path).expanduser()
        if final_path.is_dir():
            final_path = final_path / remote_filename
        else:
            final_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with PiSSHClient() as client:
            client.download_file(
                remote_filename=remote_filename,
                local_path=str(final_path),
                remote_folder=remote_folder,
                overwrite=overwrite
            )

        return JSONResponse(status_code=200, content={
            "status": "downloaded",
            "path": str(final_path),
            "filename": remote_filename
        })

    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})


@router.get("/files")
async def list_files(remote_folder: str = ""):
    with PiSSHClient() as client:
        result = client.list_files(remote_folder=remote_folder)
    return result


@router.delete("/delete")
async def delete_file(
    target: str = Form(..., description="File or folder name to delete on the Pi"),
    remote_folder: str = Form("", description="Subfolder on the Pi (optional)")
):
    try:
        with PiSSHClient() as client:
            base_dir = client.remote_dir if not remote_folder else posixpath.join(client.remote_dir, remote_folder)
            target_path = posixpath.join(base_dir, target)

            try:
                mode = client.sftp.stat(target_path).st_mode
                if stat.S_ISDIR(mode):
                    deleted_type = "folder"
                else:
                    deleted_type = "file"
            except FileNotFoundError:
                return JSONResponse(status_code=404, content={
                    "status": "not_found",
                    "exists": False,
                    "target": target,
                    "path": target_path
                })

            client.delete_file_or_folder(target=target, remote_folder=remote_folder)

        return JSONResponse(status_code=200, content={
            "status": "deleted",
            "deleted_type": deleted_type,
            "target": target,
            "path": target_path,
            "exists": True
        })

    except Exception as e:
        return JSONResponse(status_code=500, content={
            "status": "error",
            "message": str(e)
        })
