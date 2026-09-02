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

from supabase import create_client, Client


# ============================================================
# CONFIGURATION
# ============================================================

SUPABASE_BUCKET = os.getenv(
    "SUPABASE_CERTIFICATE_BUCKET",
    "certificates",
).strip() or "certificates"


# ============================================================
# CLIENT
# ============================================================

_supabase: Optional[Client] = None


def get_supabase() -> Client:
    """
    Return the configured Supabase client.

    The client is created lazily.
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
# STORAGE PATH
# ============================================================

def normalize_storage_path(
    storage_path: str,
) -> str:
    """
    Normalize a certificate storage path.

    Correct example:

        EDC-2026-123456.pdf

    The bucket name should NOT normally be included because
    Supabase already knows which bucket is being accessed.
    """

    if not storage_path:
        raise ValueError(
            "Certificate storage path is required."
        )

    path = str(storage_path).strip()

    # Windows -> Linux style path
    path = path.replace("\\", "/")

    # Remove leading slash
    path = path.lstrip("/")

    # Remove accidental ./ prefix
    while path.startswith("./"):
        path = path[2:]

    # If database contains:
    # certificates/file.pdf
    #
    # convert it to:
    # file.pdf
    bucket = SUPABASE_BUCKET

    if path.startswith(bucket + "/"):
        path = path[len(bucket) + 1:]

    # Security: prevent directory traversal
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
            "Certificate storage path must be a PDF."
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
    Upload a generated certificate PDF to Supabase Storage.

    Example:

        local_file_path:
            /tmp/EDC-2026-123456.pdf

        storage_path:
            EDC-2026-123456.pdf

    Returns:
        Supabase storage object path.
    """

    if not local_file_path:
        raise ValueError(
            "Local certificate file path is required."
        )

    if not os.path.isfile(local_file_path):
        raise FileNotFoundError(
            f"Certificate PDF not found: {local_file_path}"
        )

    normalized_path = normalize_storage_path(
        storage_path
    )

    supabase = get_supabase()

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
            SUPABASE_BUCKET
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
# CREATE SIGNED DOWNLOAD URL
# ============================================================

def create_certificate_download_url(
    storage_path: str,
    expires_in: int = 3600,
) -> str:
    """
    Generate a temporary signed URL for a private
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

    try:

        response = (
            supabase
            .storage
            .from_(SUPABASE_BUCKET)
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
            "Could not create Supabase signed "
            "download URL."
        )

    return signed_url


# ============================================================
# EXTRACT SIGNED URL
# ============================================================

def _extract_signed_url(
    response,
) -> Optional[str]:
    """
    Support multiple supabase-py response formats.
    """

    if response is None:
        return None

    # --------------------------------------------------------
    # Direct dictionary
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

            value = response.get(key)

            if value:
                return str(value)

        # Nested data
        data = response.get("data")

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

                value = data.get(key)

                if value:
                    return str(value)

    # --------------------------------------------------------
    # Object with .data
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

            value = data.get(key)

            if value:
                return str(value)

    # --------------------------------------------------------
    # Direct attributes
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

    # Example:
    #
    # certificates/
    #     EDC-2026-123456.pdf
    #
    # directory = ""
    # filename  = EDC-2026-123456.pdf

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
            .from_(SUPABASE_BUCKET)
            .list(directory)
        )

        # Handle response-object versions
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

    try:

        supabase.storage.from_(
            SUPABASE_BUCKET
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
# DELETE LOCAL TEMP FILE
# ============================================================

def delete_local_certificate_file(
    local_file_path: str,
) -> bool:
    """
    Delete a temporary certificate PDF from
    the local filesystem after uploading it.
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

    Mainly useful for testing.
    """

    global _supabase

    _supabase = None