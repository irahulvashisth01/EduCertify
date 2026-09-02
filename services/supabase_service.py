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
    SUPABASE_SECRET_KEY is server-side only.
    Never expose it in frontend code.
    Never commit it to GitHub.
"""

import os
from typing import Optional

from dotenv import load_dotenv
from supabase import Client, create_client


# ============================================================
# LOAD ENVIRONMENT
# ============================================================

# Load .env for local development.
# On Render, environment variables are loaded by Render itself.
load_dotenv()


# ============================================================
# SUPABASE CONFIGURATION
# ============================================================

def get_certificate_bucket() -> str:
    """
    Return the Supabase Storage bucket used for certificates.
    """

    bucket = os.getenv(
        "SUPABASE_CERTIFICATE_BUCKET",
        "certificates",
    )

    bucket = bucket.strip()

    return bucket or "certificates"


# ============================================================
# SUPABASE CLIENT
# ============================================================

_supabase: Optional[Client] = None


def get_supabase() -> Client:
    """
    Return the configured Supabase client.

    The client is created lazily so importing the application
    does not immediately require Supabase configuration.

    Environment variables are read at runtime.
    """

    global _supabase

    # Reuse existing client.
    if _supabase is not None:
        return _supabase

    # --------------------------------------------------------
    # Read environment variables
    # --------------------------------------------------------

    supabase_url = os.getenv(
        "SUPABASE_URL",
        "",
    ).strip()

    supabase_secret_key = os.getenv(
        "SUPABASE_SECRET_KEY",
        "",
    ).strip()

    # --------------------------------------------------------
    # Validate configuration
    # --------------------------------------------------------

    if not supabase_url:
        raise RuntimeError(
            "SUPABASE_URL environment variable is missing."
        )

    if not supabase_secret_key:
        raise RuntimeError(
            "SUPABASE_SECRET_KEY environment variable is missing."
        )

    # --------------------------------------------------------
    # Create client
    # --------------------------------------------------------

    try:

        _supabase = create_client(
            supabase_url,
            supabase_secret_key,
        )

    except Exception as exc:

        raise RuntimeError(
            "Unable to initialize Supabase client."
        ) from exc

    return _supabase


# ============================================================
# STORAGE PATH NORMALIZATION
# ============================================================

def normalize_storage_path(
    storage_path: str,
) -> str:
    """
    Normalize and validate a Supabase certificate object path.

    Correct:

        EDC-2026-123456.pdf

    Also accepts:

        certificates/EDC-2026-123456.pdf

    and converts it to:

        EDC-2026-123456.pdf

    The bucket name itself must NOT be part of the final
    object path.
    """

    if storage_path is None:
        raise ValueError(
            "Certificate storage path is required."
        )

    path = str(storage_path).strip()

    if not path:
        raise ValueError(
            "Certificate storage path is required."
        )

    # --------------------------------------------------------
    # Normalize separators
    # --------------------------------------------------------

    path = path.replace("\\", "/")

    # Remove leading slash.
    path = path.lstrip("/")

    # Remove accidental "./"
    while path.startswith("./"):
        path = path[2:]

    # --------------------------------------------------------
    # Remove accidental bucket prefix
    # --------------------------------------------------------

    bucket = get_certificate_bucket()

    if path == bucket:
        raise ValueError(
            "Certificate storage path points to the bucket, "
            "not to a certificate file."
        )

    if path.startswith(
        bucket + "/"
    ):
        path = path[
            len(bucket) + 1:
        ]

    # --------------------------------------------------------
    # Security validation
    # --------------------------------------------------------

    parts = path.split("/")

    if any(
        part == ".."
        for part in parts
    ):
        raise ValueError(
            "Invalid certificate storage path."
        )

    if any(
        part == ""
        for part in parts
    ):
        raise ValueError(
            "Invalid certificate storage path."
        )

    # --------------------------------------------------------
    # Certificate must be PDF
    # --------------------------------------------------------

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
    Upload a generated certificate PDF to Supabase Storage.

    Example:

        local_file_path:
            uploads/certificates/EC-2026-000001.pdf

        storage_path:
            EC-2026-000001.pdf

    Returns:

        EC-2026-000001.pdf
    """

    # --------------------------------------------------------
    # Validate local file
    # --------------------------------------------------------

    if not local_file_path:
        raise ValueError(
            "Local certificate file path is required."
        )

    if not os.path.isfile(
        local_file_path
    ):
        raise FileNotFoundError(
            "Certificate PDF not found: "
            f"{local_file_path}"
        )

    # --------------------------------------------------------
    # Validate storage path
    # --------------------------------------------------------

    normalized_path = normalize_storage_path(
        storage_path
    )

    # --------------------------------------------------------
    # Supabase
    # --------------------------------------------------------

    supabase = get_supabase()

    bucket = get_certificate_bucket()

    # --------------------------------------------------------
    # Read PDF
    # --------------------------------------------------------

    try:

        with open(
            local_file_path,
            "rb",
        ) as file:

            file_bytes = file.read()

    except OSError as exc:

        raise RuntimeError(
            "Unable to read certificate PDF."
        ) from exc

    if not file_bytes:
        raise ValueError(
            "Certificate PDF is empty."
        )

    # --------------------------------------------------------
    # Upload
    # --------------------------------------------------------

    try:

        supabase.storage.from_(
            bucket
        ).upload(
            path=normalized_path,
            file=file_bytes,
            file_options={
                "content-type": "application/pdf",
                "cache-control": "3600",
                "upsert": True,
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
    Create a temporary signed URL for a private certificate PDF.

    Default:

        3600 seconds = 1 hour

    The generated URL can be sent to the student's browser.
    The Supabase secret key is never exposed.
    """

    # --------------------------------------------------------
    # Validate expiration
    # --------------------------------------------------------

    if expires_in <= 0:
        raise ValueError(
            "expires_in must be greater than zero."
        )

    # --------------------------------------------------------
    # Normalize path
    # --------------------------------------------------------

    normalized_path = normalize_storage_path(
        storage_path
    )

    # --------------------------------------------------------
    # Supabase
    # --------------------------------------------------------

    supabase = get_supabase()

    bucket = get_certificate_bucket()

    # --------------------------------------------------------
    # Create signed URL
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # Extract URL
    # --------------------------------------------------------

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
    Extract the signed URL from different response formats
    supported by supabase-py versions.
    """

    if response is None:
        return None

    # ========================================================
    # Direct dictionary response
    # ========================================================

    if isinstance(
        response,
        dict,
    ):

        # Direct keys
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

        # Nested data
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

    # ========================================================
    # Response object with .data
    # ========================================================

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

    # ========================================================
    # Direct response attributes
    # ========================================================

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

    # --------------------------------------------------------
    # Normalize path
    # --------------------------------------------------------

    try:

        normalized_path = normalize_storage_path(
            storage_path
        )

    except (
        ValueError,
        TypeError,
    ):

        return False

    # --------------------------------------------------------
    # Supabase
    # --------------------------------------------------------

    try:

        supabase = get_supabase()

        bucket = get_certificate_bucket()

        # ----------------------------------------------------
        # Determine directory and filename
        # ----------------------------------------------------

        if "/" in normalized_path:

            directory = (
                normalized_path.rsplit(
                    "/",
                    1,
                )[0]
            )

            filename = (
                normalized_path.rsplit(
                    "/",
                    1,
                )[1]
            )

        else:

            directory = ""

            filename = normalized_path

        # ----------------------------------------------------
        # List objects
        # ----------------------------------------------------

        response = (
            supabase
            .storage
            .from_(bucket)
            .list(directory)
        )

        # ----------------------------------------------------
        # Handle response formats
        # ----------------------------------------------------

        if isinstance(
            response,
            list,
        ):

            files = response

        else:

            files = getattr(
                response,
                "data",
                None,
            )

            if not isinstance(
                files,
                list,
            ):

                return False

        # ----------------------------------------------------
        # Search filename
        # ----------------------------------------------------

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

    # --------------------------------------------------------
    # Normalize
    # --------------------------------------------------------

    try:

        normalized_path = normalize_storage_path(
            storage_path
        )

    except (
        ValueError,
        TypeError,
    ):

        return False

    # --------------------------------------------------------
    # Supabase
    # --------------------------------------------------------

    try:

        supabase = get_supabase()

        bucket = get_certificate_bucket()

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
# DELETE LOCAL TEMPORARY CERTIFICATE
# ============================================================

def delete_local_certificate_file(
    local_file_path: str,
) -> bool:
    """
    Delete a locally generated temporary certificate PDF.

    Useful on Render because generated files should not be
    relied upon for permanent storage.
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
# RESET SUPABASE CLIENT
# ============================================================

def reset_supabase_client() -> None:
    """
    Reset the cached Supabase client.

    Useful for testing or when environment configuration
    changes during the application lifetime.
    """

    global _supabase

    _supabase = None