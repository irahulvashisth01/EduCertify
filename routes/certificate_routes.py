"""
Public certificate verification routes. No login required by design -
anyone (employers, recruiters) should be able to verify a certificate.
"""

from flask import Blueprint, render_template, request, redirect, url_for

from services.certificate_service import verify_certificate
from utils.validators import is_valid_certificate_number

certificate_bp = Blueprint("certificate", __name__, url_prefix="/certificates")


@certificate_bp.route("/verify", methods=["GET"])
def verify_form():
    cert_number = request.args.get("cert_id", "").strip()
    certificate = None
    searched = False

    if cert_number:
        searched = True
        certificate = verify_certificate(cert_number)

    return render_template(
        "certificate/verify.html",
        certificate=certificate,
        searched=searched,
        cert_number=cert_number,
    )


@certificate_bp.route("/verify/<certificate_number>")
def verify(certificate_number):
    certificate = verify_certificate(certificate_number)
    return render_template(
        "certificate/verify.html",
        certificate=certificate,
        searched=True,
        cert_number=certificate_number,
    )
