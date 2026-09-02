"""
EduCertify — Supabase Storage Service

Stores generated certificate PDFs in Supabase Storage.

Required environment variables:

    SUPABASE_URL
    SUPABASE_SECRET_KEY

Optional:

    SUPABASE_CERTIFICATE_BUCKET

Default bucket:

    certificates

IMPORTANT:
    SUPABASE_SECRET_KEY must remain server-side only.
    Never expose it in frontend code or GitHub.
"""

import os
from typing import Optional

from dotenv import load_dotenv
from supabase import Client, create_client


# ============================================================
# LOAD ENVIRONMENT
# ============================================================

# Load .env when this module is imported directly.
load_dotenv()


# ============================================================
# CONFIGURATION
# ============================================================

def get_certificate_bucket() -> str:
    """
    Return the Supabase Storage bucket used for certificates.
    """

    bucket = os.getenv(
        "SUPABASE_CERTIFICATE_BUCKET",
        "certificates",
    ).strip()

    return bucket or "certificates"


# ============================================================
# CLIENT
# ============================================================

_supabase: Optional[Client] = None


def get_supabase() -> Client:
    """
    Return the configured Supabase client.

    Environment variables are read at runtime so that
    Render environment variables and .env configuration
    are handled correctly.
    """

    global _supabase

    if _supabase is not None:
        return _supabase

    supabase_url = os.getenv(
        "SUPABASE_URL",
        "",
    ).strip()

    supabase_secret_key = os.getenv(
        "SUPABASE_SECRET_KEY",
        "",
    ).strip()

    if not supabase_url:
        raise RuntimeError(
            "SUPABASE_URL environment variable is missing."
        )

    if not supabase_secret_key:
        raise RuntimeError(
            "SUPABASE_SECRET_KEY environment variable is missing."
        )

    _supabase = create_client(
        supabase_url,
        supabase_secret_key,
    )

    return _supabase


# ============================================================
# STORAGE PATH NORMALIZATION
# ============================================================

def normalize_storage_path(
    storage_path: str,
) -> str:
    """
    Normalize and validate a certificate storage path.

    Correct:

        EDC-2026-123456.pdf

    Also accepts an accidentally bucket-prefixed path:

        certificates/EDC-2026-123456.pdf

    and converts it to:

        EDC-2026-123456.pdf
    """

    if not storage_path:
        raise ValueError(
            "Certificate storage path is required."
        )

    path = str(storage_path).strip()

    # Convert Windows separators.
    path = path.replace("\\", "/")

    # Remove leading slash.
    path = path.lstrip("/")

    # Remove accidental ./ prefix.
    while path.startswith("./"):
        path = path[2:]

    bucket = get_certificate_bucket()

    # Remove bucket prefix if accidentally stored in DB.
    if path.startswith(bucket + "/"):
        path = path[
            len(bucket) + 1:
        ]

    # Prevent directory traversal.
    if ".." in path.split("/"):
        raise ValueError(
            "Invalid certificate storage path."
        )

    if not path:
        raise ValueError(
            "Certificate storage path is empty."
        )

    if not path.lower().endswith(".pdf"):
        raise ValueError(
            "Certificate storage path must point to a PDF."
        )

    return path


# ============================================================
# UPLOAD CERTIFICATE
# ============================================================

def upload_certificate(
    local_file_path: str,
    storage_path: str,
) -> str:
    """
    Upload a certificate PDF to the private
    Supabase Storage bucket.

    Returns the Supabase object path.
    """

    if not local_file_path:
        raise ValueError(
            "Local certificate file path is required."
        )

    if not os.path.isfile(
        local_file_path
    ):
        raise FileNotFoundError(
            f"Certificate PDF not found: "
            f"{local_file_path}"
        )

    normalized_path = normalize_storage_path(
        storage_path
    )

    supabase = get_supabase()

    bucket = get_certificate_bucket()

    with open(
        local_file_path,
        "rb",
    ) as file:

        file_bytes = file.read()

    if not file_bytes:
        raise ValueError(
            "Certificate PDF is empty."
        )

    try:

        supabase.storage.from_(
            bucket
        ).upload(
            path=normalized_path,
            file=file_bytes,
            file_options={
                "content-type": "application/pdf",
                "cache-control": "3600",
                "upsert": "true",
            },
        )

    except Exception as exc:

        raise RuntimeError(
            "Failed to upload certificate PDF "
            "to Supabase Storage."
        ) from exc

    return normalized_path


# ============================================================
# SIGNED DOWNLOAD URL
# ============================================================

def create_certificate_download_url(
    storage_path: str,
    expires_in: int = 3600,
) -> str:
    """
    Create a temporary signed URL for a private
    certificate PDF.

    Default expiration:

        3600 seconds = 1 hour
    """

    normalized_path = normalize_storage_path(
        storage_path
    )

    if expires_in <= 0:
        raise ValueError(
            "expires_in must be greater than zero."
        )

    supabase = get_supabase()

    bucket = get_certificate_bucket()

    try:

        response = (
            supabase
            .storage
            .from_(bucket)
            .create_signed_url(
                normalized_path,
                expires_in,
            )
        )

    except Exception as exc:

        raise RuntimeError(
            "Failed to create Supabase signed "
            "certificate download URL."
        ) from exc

    signed_url = _extract_signed_url(
        response
    )

    if not signed_url:

        raise RuntimeError(
            "Supabase did not return a signed "
            "certificate download URL."
        )

    return signed_url


# ============================================================
# EXTRACT SIGNED URL
# ============================================================

def _extract_signed_url(
    response,
) -> Optional[str]:
    """
    Extract signed URL from different supabase-py
    response formats.
    """

    if response is None:
        return None

    # --------------------------------------------------------
    # Dictionary response
    # --------------------------------------------------------

    if isinstance(
        response,
        dict,
    ):

        for key in (
            "signedURL",
            "signedUrl",
            "signed_url",
            "url",
        ):

            value = response.get(
                key
            )

            if value:
                return str(value)

        data = response.get(
            "data"
        )

        if isinstance(
            data,
            dict,
        ):

            for key in (
                "signedURL",
                "signedUrl",
                "signed_url",
                "url",
            ):

                value = data.get(
                    key
                )

                if value:
                    return str(value)

    # --------------------------------------------------------
    # Response object with .data
    # --------------------------------------------------------

    data = getattr(
        response,
        "data",
        None,
    )

    if isinstance(
        data,
        dict,
    ):

        for key in (
            "signedURL",
            "signedUrl",
            "signed_url",
            "url",
        ):

            value = data.get(
                key
            )

            if value:
                return str(value)

    # --------------------------------------------------------
    # Direct response attributes
    # --------------------------------------------------------

    for attribute in (
        "signedURL",
        "signedUrl",
        "signed_url",
        "url",
    ):

        value = getattr(
            response,
            attribute,
            None,
        )

        if value:
            return str(value)

    return None


# ============================================================
# CHECK CERTIFICATE EXISTS
# ============================================================

def certificate_exists(
    storage_path: str,
) -> bool:
    """
    Check whether a certificate PDF exists
    in Supabase Storage.
    """

    if not storage_path:
        return False

    try:

        normalized_path = normalize_storage_path(
            storage_path
        )

    except (
        ValueError,
        TypeError,
    ):

        return False

    supabase = get_supabase()

    bucket = get_certificate_bucket()

    directory = os.path.dirname(
        normalized_path
    ).replace(
        "\\",
        "/",
    )

    filename = os.path.basename(
        normalized_path
    )

    try:

        files = (
            supabase
            .storage
            .from_(bucket)
            .list(directory)
        )

        if not isinstance(
            files,
            list,
        ):

            data = getattr(
                files,
                "data",
                None,
            )

            if isinstance(
                data,
                list,
            ):
                files = data
            else:
                return False

        for item in files:

            if not isinstance(
                item,
                dict,
            ):
                continue

            if item.get(
                "name"
            ) == filename:

                return True

    except Exception:

        return False

    return False


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

    try:

        normalized_path = normalize_storage_path(
            storage_path
        )

    except (
        ValueError,
        TypeError,
    ):

        return False

    supabase = get_supabase()

    bucket = get_certificate_bucket()

    try:

        supabase.storage.from_(
            bucket
        ).remove(
            [normalized_path]
        )

        return True

    except Exception as exc:

        raise RuntimeError(
            "Failed to delete certificate "
            "from Supabase Storage."
        ) from exc


# ============================================================
# DELETE LOCAL TEMPORARY FILE
# ============================================================

def delete_local_certificate_file(
    local_file_path: str,
) -> bool:
    """
    Delete a locally generated temporary PDF.
    """

    if not local_file_path:
        return False

    try:

        if os.path.isfile(
            local_file_path
        ):

            os.remove(
                local_file_path
            )

            return True

    except OSError:

        return False

    return False


# ============================================================
# RESET CLIENT
# ============================================================

def reset_supabase_client() -> None:
    """
    Reset the cached Supabase client.
    """

    global _supabase

    _supabase = None