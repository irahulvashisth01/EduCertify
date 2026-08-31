"""
EduCertify — Public Certificate Verification Routes

Certificate verification is intentionally public.

Anyone can verify a certificate using its certificate number.
No login is required.

Routes:
    GET /certificates/verify
    GET /certificates/verify/<certificate_number>
"""

from flask import (
    Blueprint,
    render_template,
    request,
)

from services.certificate_service import (
    verify_certificate,
)

from utils.validators import (
    is_valid_certificate_number,
)


# ============================================================
# BLUEPRINT
# ============================================================

certificate_bp = Blueprint(
    "certificate",
    __name__,
    url_prefix="/certificates",
)


# ============================================================
# CERTIFICATE VERIFICATION FORM
# ============================================================

@certificate_bp.route(
    "/verify",
    methods=["GET"],
)
def verify_form():
    """
    Display the public certificate verification form.

    Example:
        /certificates/verify

    Query parameter:
        cert_id=<certificate number>
    """

    cert_number = (
        request.args.get(
            "cert_id",
            "",
        )
        .strip()
    )

    certificate = None
    searched = False
    error = None

    # --------------------------------------------------------
    # Certificate search
    # --------------------------------------------------------

    if cert_number:

        searched = True

        # Validate certificate number before
        # querying the database.
        if not is_valid_certificate_number(
            cert_number
        ):

            error = (
                "Please enter a valid certificate number."
            )

        else:

            try:

                certificate = verify_certificate(
                    cert_number
                )

            except Exception:

                certificate = None

                error = (
                    "Unable to verify the certificate "
                    "at this time."
                )

    return render_template(
        "certificate/verify.html",
        certificate=certificate,
        searched=searched,
        cert_number=cert_number,
        error=error,
    )


# ============================================================
# DIRECT CERTIFICATE VERIFICATION
# ============================================================

@certificate_bp.route(
    "/verify/<certificate_number>",
    methods=["GET"],
)
def verify(certificate_number):
    """
    Verify a certificate directly using its certificate number.

    Example:
        /certificates/verify/EC-2026-000001
    """

    certificate_number = (
        certificate_number.strip()
    )

    certificate = None
    error = None

    # --------------------------------------------------------
    # Validate certificate number
    # --------------------------------------------------------

    if not is_valid_certificate_number(
        certificate_number
    ):

        error = (
            "Invalid certificate number."
        )

    else:

        try:

            certificate = verify_certificate(
                certificate_number
            )

        except Exception:

            error = (
                "Unable to verify the certificate "
                "at this time."
            )

    return render_template(
        "certificate/verify.html",
        certificate=certificate,
        searched=True,
        cert_number=certificate_number,
        error=error,
    )