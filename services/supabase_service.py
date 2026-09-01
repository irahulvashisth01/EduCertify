"""
EduCertify — Supabase Storage Service

Stores generated certificate PDFs in Supabase Storage.

Required environment variables:

    SUPABASE_URL
    SUPABASE_SECRET_KEY

Bucket:

    certificates
"""

from builtins import Exception
import os
from typing import Optional

from supabase import create_client, Client


# ============================================================
# CONFIGURATION
# ============================================================

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY")

SUPABASE_BUCKET = "certificates"


# ============================================================
# CLIENT
# ============================================================

_supabase: Optional[Client] = None


def get_supabase() -> Client:
    """
    Return the configured Supabase client.

    The client is created lazily so the Flask application
    can still start cleanly when configuration is missing.
    """

    global _supabase

    if _supabase is not None:
        return _supabase

    if not SUPABASE_URL:
        raise RuntimeError(
            "SUPABASE_URL environment variable is missing."
        )

    if not SUPABASE_SECRET_KEY:
        raise RuntimeError(
            "SUPABASE_SECRET_KEY environment variable is missing."
        )

    _supabase = create_client(
        SUPABASE_URL,
        SUPABASE_SECRET_KEY,
    )

    return _supabase


# ============================================================
# UPLOAD CERTIFICATE
# ============================================================

def upload_certificate(
    local_file_path: str,
    storage_path: str,
) -> str:
    """
    Upload a certificate PDF to Supabase Storage.

    Example storage path:

        certificates/EDC-2026-123456.pdf

    Returns:
        Storage path.
    """

    if not os.path.isfile(local_file_path):
        raise FileNotFoundError(
            f"Certificate PDF not found: {local_file_path}"
        )

    supabase = get_supabase()

    with open(local_file_path, "rb") as file:
        file_bytes = file.read()

    response = (
        supabase
        .storage
        .from_(SUPABASE_BUCKET)
        .upload(
            path=storage_path,
            file=file_bytes,
            file_options={
                "content-type": "application/pdf",
                "cache-control": "3600",
                "upsert": "true",
            },
        )
    )

    return storage_path


# ============================================================
# CREATE DOWNLOAD URL
# ============================================================

def create_certificate_download_url(
    storage_path: str,
    expires_in: int = 3600,
) -> str:
    """
    Generate a temporary signed download URL.

    Default:
        1 hour
    """

    if not storage_path:
        raise ValueError(
            "Certificate storage path is required."
        )

    supabase = get_supabase()

    response = (
        supabase
        .storage
        .from_(SUPABASE_BUCKET)
        .create_signed_url(
            storage_path,
            expires_in,
        )
    )

    # Supabase Python responses can expose the URL
    # through the response data dictionary.
    data = getattr(response, "data", None)

    if isinstance(data, dict):
        signed_url = (
            data.get("signedURL")
            or data.get("signedUrl")
        )

        if signed_url:
            return signed_url

    if isinstance(response, dict):
        signed_url = (
            response.get("signedURL")
            or response.get("signedUrl")
        )

        if signed_url:
            return signed_url

    raise RuntimeError(
        "Could not create Supabase signed download URL."
    )


# ============================================================
# DELETE CERTIFICATE
# ============================================================

def delete_certificate(
    storage_path: str,
) -> bool:
    """
    Delete a certificate PDF from Supabase Storage.
    """

    if not storage_path:
        return False

    supabase = get_supabase()

    supabase.storage.from_(
        SUPABASE_BUCKET
    ).remove(
        [storage_path]
    )

    return True


# ============================================================
# CHECK FILE EXISTS
# ============================================================

def certificate_exists(
    storage_path: str,
) -> bool:
    """
    Check whether a certificate exists in storage.
    """

    if not storage_path:
        return False

    supabase = get_supabase()

    directory = os.path.dirname(storage_path)
    filename = os.path.basename(storage_path)

    try:
        files = (
            supabase
            .storage
            .from_(SUPABASE_BUCKET)
            .list(directory)
        )

        for item in files or []:
            if item.get("name") == filename:
                return True

    except Exception:
        return False

    return False