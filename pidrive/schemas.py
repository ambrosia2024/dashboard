# pidrive/schemas.py

from pydantic import BaseModel
from typing import Optional


class UploadRequest(BaseModel):
    remote_folder: Optional[str] = None
    remote_filename: Optional[str] = None
    overwrite: bool = False


class DownloadRequest(BaseModel):
    remote_folder: Optional[str] = None
    remote_filename: str
    local_path: Optional[str] = None
    overwrite: bool = False


class DeleteRequest(BaseModel):
    target: str
    remote_folder: Optional[str] = None


class ListFilesRequest(BaseModel):
    remote_folder: Optional[str] = None
