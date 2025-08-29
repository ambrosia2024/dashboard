# pidrive/routes.py

import os
import posixpath
import shlex
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
    remote_folder: str = Form("", description="Target subfolder inside the pool (optional)"),
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
            if remote_folder.startswith("/"):
                # ABSOLUTE PATH (pin to a specific drive). Ensure it exists or return 400.
                target_dir = remote_folder.rstrip("/")
                # Try a quick SFTP stat to see if directory exists
                try:
                    st = client.sftp.stat(target_dir)
                except FileNotFoundError:
                    # Try to create it via shell (may fail if pi lacks perms)
                    out, err, code = client._exec(
                        f"mkdir -p {shlex.quote(target_dir)} && chown pi:storageusers {shlex.quote(target_dir)}",
                        timeout=10)
                    if code != 0:
                        return JSONResponse(
                            status_code=400,
                            content={
                                "status": "error",
                                "message": f"Absolute target directory does not exist and could not be created: {target_dir}. "
                                           f"Create it with: sudo mkdir -p {target_dir} && sudo chown -R pi:storageusers {target_dir}"
                            }
                        )
            else:
                # POOL WRITE (balanced)
                raw = (remote_folder or "").strip().strip("/")
                # Always create relative subpaths under the pool container 'uploads'
                subpath = "uploads" if not raw else posixpath.join("uploads", raw)

                if subpath.startswith("/") or ".." in subpath:
                    return JSONResponse(status_code=400, content={"status": "error", "message": "Invalid subpath"})

                branches = client.detect_mergerfs_branches()
                if not branches:
                    return JSONResponse(
                        status_code=500,
                        content={"status": "error", "message": "No mergerfs branches detected on the storage server."}
                    )

                # Ensure the subpath exists on ALL branches so epmfs can choose
                client.ensure_pool_dirs(subpath=subpath, branches=branches)

                # Pool root
                pool_root = client.remote_dir or "/mnt/storage"
                target_dir = posixpath.join(pool_root, subpath)

            client.upload_file(
                local_path=temp_path,
                remote_filename=remote_filename or file.filename,
                remote_folder=target_dir,
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
            # Build base dir and canonicalise
            base_dir = client.remote_dir if not remote_folder else posixpath.join(client.remote_dir, remote_folder)
            base_dir = client.sftp.normalize(base_dir)

            # Compose raw target path and run pre-flight guard (gives canonical path)
            raw_target_path = posixpath.join(base_dir, target)

            try:
                canonical = client._safe_target(raw_target_path)
            except PermissionError as pe:
                return JSONResponse(status_code=403, content={
                    "status": "forbidden",
                    "message": str(pe),
                    "target": target,
                    "path": raw_target_path
                })

            # Extra clarity for uploads root (redundant with guard but gives nicer message)
            if canonical == getattr(client, "uploads_dir", ""):
                return JSONResponse(status_code=403, content={
                    "status": "forbidden",
                    "message": "Deleting the uploads directory is not allowed.",
                    "target": target,
                    "path": canonical
                })

            # Probe what we're deleting to label it
            try:
                mode = client.sftp.stat(canonical).st_mode
                deleted_type = "folder" if stat.S_ISDIR(mode) else "file"
            except FileNotFoundError:
                return JSONResponse(status_code=404, content={
                    "status": "not_found",
                    "exists": False,
                    "target": target,
                    "path": canonical
                })

            client.delete_file_or_folder(target=target, remote_folder=remote_folder)

        return JSONResponse(status_code=200, content={
            "status": "deleted",
            "deleted_type": deleted_type,
            "target": target,
            "path": canonical,
            "exists": True
        })

    except PermissionError as pe:
        return JSONResponse(status_code=403, content={
            "status": "forbidden",
            "message": str(pe),
            "target": target
        })
    except Exception as e:
        return JSONResponse(status_code=500, content={
            "status": "error",
            "message": str(e)
        })


@router.get("/system/info")
async def system_info():
    """
    Return RAM, mounts, per-drive sizes (incl. mergerfs), and microSD partitions.
    """
    try:
        with PiSSHClient() as client:
            data = client.get_system_info()
        return JSONResponse(status_code=200, content={"status": "ok", "data": data})
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})
