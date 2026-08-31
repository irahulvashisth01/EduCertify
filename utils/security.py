"""
Security helper functions: safe file handling, password hashing wrappers.
"""

import os
import uuid
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename


def hash_password(plain_password: str) -> str:
    return generate_password_hash(plain_password)


def verify_password(password_hash: str, plain_password: str) -> bool:
    return check_password_hash(password_hash, plain_password)


def allowed_file(filename: str, allowed_extensions: set) -> bool:
    if not filename or "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in allowed_extensions


def make_safe_filename(original_filename: str) -> str:
    """Generate a collision-resistant, path-safe filename while keeping the
    original extension."""
    safe_name = secure_filename(original_filename)
    ext = ""
    if "." in safe_name:
        ext = safe_name.rsplit(".", 1)[1].lower()
    unique_id = uuid.uuid4().hex[:12]
    return f"{unique_id}.{ext}" if ext else unique_id


def save_uploaded_file(file_storage, destination_folder: str, allowed_extensions: set):
    """
    Validate and save an uploaded file. Returns the saved filename, or raises
    ValueError if the file is missing/invalid.
    """
    if file_storage is None or file_storage.filename == "":
        raise ValueError("No file was selected.")

    if not allowed_file(file_storage.filename, allowed_extensions):
        raise ValueError("File type not allowed.")

    os.makedirs(destination_folder, exist_ok=True)
    filename = make_safe_filename(file_storage.filename)
    full_path = os.path.join(destination_folder, filename)
    file_storage.save(full_path)
    return filename
