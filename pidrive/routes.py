# pidrive/routes.py

import shutil
import tempfile

from fastapi import APIRouter, UploadFile, File

from .pi_helper import PiSSHClient
from .schemas import UploadRequest, DownloadRequest, DeleteRequest, ListFilesRequest

router = APIRouter()

@router.post("/upload")
async def upload_file(req: UploadRequest, file: UploadFile = File(...)):
    temp_path = tempfile.mktemp()
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    with PiSSHClient() as client:
        client.upload_file(
            local_path=temp_path,
            remote_filename=req.remote_filename or file.filename,
            remote_folder=req.remote_folder,
            overwrite=req.overwrite
        )
    return {"status": "uploaded", "filename": file.filename}


@router.post("/download")
async def download_file(req: DownloadRequest):
    with PiSSHClient() as client:
        client.download_file(
            remote_filename=req.remote_filename,
            local_path=req.local_path,
            remote_folder=req.remote_folder,
            overwrite=req.overwrite
        )
    return {"status": "downloaded", "filename": req.remote_filename}


@router.get("/files")
async def list_files(remote_folder: str = ""):
    with PiSSHClient() as client:
        result = client.list_files(remote_folder=remote_folder)
    return result


@router.delete("/delete")
async def delete_file(req: DeleteRequest):
    with PiSSHClient() as client:
        client.delete_file_or_folder(
            target=req.target,
            remote_folder=req.remote_folder
        )
    return {"status": "deleted", "target": req.target}
