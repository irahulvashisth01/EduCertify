"""
EduCertify — Certificate Service

Business logic for:

- Certificate eligibility checking
- Lesson completion verification
- Quiz and final assessment verification
- Final score calculation
- Unique certificate number generation
- Certificate creation
- QR-code generation
- Professional PDF certificate generation
- Public certificate verification
- Certificate revocation

This service contains no Flask request/session handling.
"""

import os
from datetime import datetime, timezone

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import cm
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas as pdf_canvas
from reportlab.lib.utils import ImageReader

from supabase import create_client, Client
from database.database import db
from database.models import (
    Certificate,
    Enrollment,
    Quiz,
    QuizAttempt,
    Course,
    LessonProgress,
)

from utils.helpers import generate_certificate_number
from utils.qr_generator import generate_qr_code


# ============================================================
# CUSTOM EXCEPTION
# ============================================================

class CertificateError(Exception):
    """
    Raised when a certificate operation fails.
    """

    pass


# ============================================================
# SUPABASE STORAGE
# ============================================================

def _get_supabase_client(app_config) -> Client:
    """
    Create a Supabase client for server-side storage operations.

    Required configuration:
        SUPABASE_URL
        SUPABASE_SECRET_KEY

    The secret/service-role key must NEVER be exposed
    to frontend JavaScript or templates.
    """

    supabase_url = (
        app_config.get("SUPABASE_URL")
        or os.getenv("SUPABASE_URL")
    )

    supabase_key = (
        app_config.get("SUPABASE_SECRET_KEY")
        or os.getenv("SUPABASE_SECRET_KEY")
    )

    if not supabase_url:
        raise CertificateError(
            "SUPABASE_URL is not configured."
        )

    if not supabase_key:
        raise CertificateError(
            "SUPABASE_SECRET_KEY is not configured."
        )

    return create_client(
        supabase_url,
        supabase_key,
    )


def _get_certificate_bucket(app_config) -> str:
    """
    Return the Supabase Storage bucket used for certificates.
    """

    bucket = (
        app_config.get("SUPABASE_CERTIFICATE_BUCKET")
        or os.getenv(
            "SUPABASE_CERTIFICATE_BUCKET",
            "certificates",
        )
    )

    bucket = str(bucket).strip()

    if not bucket:
        raise CertificateError(
            "Supabase certificate bucket is not configured."
        )

    return bucket


def _upload_certificate_pdf(
    pdf_path: str,
    filename: str,
    app_config,
) -> str:
    """
    Upload a generated certificate PDF to Supabase Storage.

    Returns:
        The storage object path stored in the database.
    """

    if not pdf_path:
        raise CertificateError(
            "Certificate PDF path is missing."
        )

    if not os.path.isfile(pdf_path):
        raise CertificateError(
            "Generated certificate PDF was not found."
        )

    supabase = _get_supabase_client(
        app_config
    )

    bucket = _get_certificate_bucket(
        app_config
    )

    storage_path = filename

    try:
        with open(
            pdf_path,
            "rb",
        ) as pdf_file:

            pdf_bytes = pdf_file.read()

        supabase.storage.from_(
            bucket
        ).upload(
            storage_path,
            pdf_bytes,
            {
                "content-type": "application/pdf",
                "cache-control": "3600",
                "upsert": "true",
            },
        )

    except Exception as exc:

        raise CertificateError(
            "Unable to upload certificate PDF "
            "to Supabase Storage."
        ) from exc

    return storage_path


def _delete_local_file(path: str):
    """
    Safely delete a temporary local certificate file.
    """

    if not path:
        return

    try:

        if os.path.isfile(path):
            os.remove(path)

    except OSError:
        pass

# ============================================================
# CHECK CERTIFICATE ELIGIBILITY
# ============================================================

def check_eligibility(
    student_id: int,
    course_id: int,
) -> dict:
    """
    Check whether a student has completed all requirements
    for a course certificate.

    Requirements:

    1. Student must be enrolled.
    2. All course lessons must be completed.
    3. All module quizzes must be passed.
    4. Final assessment must be passed if one exists.
    """

    course = db.session.get(
        Course,
        course_id,
    )

    if course is None:
        raise CertificateError(
            "Course not found."
        )

    enrollment = (
        Enrollment.query
        .filter_by(
            StudentID=student_id,
            CourseID=course_id,
        )
        .first()
    )

    if enrollment is None:
        raise CertificateError(
            "You are not enrolled in this course."
        )

    # --------------------------------------------------------
    # Collect all lessons
    # --------------------------------------------------------

    lesson_ids = []

    for module in course.modules:

        for lesson in module.lessons:

            lesson_ids.append(
                lesson.LessonID
            )

    total_lessons = len(
        lesson_ids
    )

    # --------------------------------------------------------
    # Completed lessons
    # --------------------------------------------------------

    completed_lessons = 0

    if lesson_ids:

        completed_lessons = (
            LessonProgress.query
            .filter(
                LessonProgress.StudentID
                == student_id,

                LessonProgress.LessonID.in_(
                    lesson_ids
                ),

                LessonProgress.Completed.is_(True),
            )
            .count()
        )

    lessons_done = (
        total_lessons > 0
        and completed_lessons == total_lessons
    )

    # --------------------------------------------------------
    # Course quizzes
    # --------------------------------------------------------

    quizzes = (
        Quiz.query
        .filter_by(
            CourseID=course_id
        )
        .all()
    )

    module_quizzes = [
        quiz
        for quiz in quizzes
        if not quiz.IsFinalAssessment
    ]

    final_assessments = [
        quiz
        for quiz in quizzes
        if quiz.IsFinalAssessment
    ]

    # --------------------------------------------------------
    # Module quizzes
    # --------------------------------------------------------

    module_quizzes_passed = True

    for quiz in module_quizzes:

        passed_attempt = (
            QuizAttempt.query
            .filter_by(
                StudentID=student_id,
                QuizID=quiz.QuizID,
                Passed=True,
            )
            .first()
        )

        if passed_attempt is None:

            module_quizzes_passed = False

            break

    # --------------------------------------------------------
    # Final assessment
    # --------------------------------------------------------

    final_score = None
    final_passed = True

    if final_assessments:

        final_quiz = final_assessments[0]

        best_attempt = (
            QuizAttempt.query
            .filter_by(
                StudentID=student_id,
                QuizID=final_quiz.QuizID,
                Passed=True,
            )
            .order_by(
                QuizAttempt.Percentage.desc()
            )
            .first()
        )

        final_passed = (
            best_attempt is not None
        )

        if best_attempt:

            final_score = (
                best_attempt.Percentage
            )

    # --------------------------------------------------------
    # Final eligibility
    # --------------------------------------------------------

    eligible = (
        lessons_done
        and module_quizzes_passed
        and final_passed
    )

    return {
        "eligible": eligible,

        "lessons_done": lessons_done,

        "total_lessons": total_lessons,

        "completed_lessons": completed_lessons,

        "module_quizzes_passed":
            module_quizzes_passed,

        "final_assessment_required":
            bool(final_assessments),

        "final_passed":
            final_passed,

        "final_score":
            final_score,
    }


# ============================================================
# CALCULATE FINAL SCORE
# ============================================================

def _calculate_final_score(
    student_id: int,
    course_id: int,
) -> float:
    """
    Calculate the certificate final score.

    The score is the average of the student's best
    attempt for each quiz.

    If the course contains no quizzes, the score
    defaults to 100%.
    """

    quizzes = (
        Quiz.query
        .filter_by(
            CourseID=course_id
        )
        .all()
    )

    if not quizzes:
        return 100.0

    scores = []

    for quiz in quizzes:

        best_attempt = (
            QuizAttempt.query
            .filter_by(
                StudentID=student_id,
                QuizID=quiz.QuizID,
            )
            .filter(
                QuizAttempt.Percentage.isnot(None)
            )
            .order_by(
                QuizAttempt.Percentage.desc()
            )
            .first()
        )

        if (
            best_attempt
            and best_attempt.Percentage is not None
        ):

            scores.append(
                float(
                    best_attempt.Percentage
                )
            )

    if not scores:
        return 100.0

    return round(
        sum(scores) / len(scores),
        1,
    )


# ============================================================
# GENERATE UNIQUE CERTIFICATE NUMBER
# ============================================================

def _generate_unique_certificate_number():
    """
    Generate a certificate number that does not already
    exist in the database.
    """

    for _ in range(20):

        certificate_number = (
            generate_certificate_number()
        )

        certificate_number = (
            str(certificate_number)
            .strip()
            .upper()
        )

        existing = (
            Certificate.query
            .filter_by(
                CertificateNumber=
                certificate_number
            )
            .first()
        )

        if existing is None:

            return certificate_number

    raise CertificateError(
        "Unable to generate a unique certificate number."
    )


# ============================================================
# AUTO ISSUE CERTIFICATE IF ELIGIBLE
# ============================================================

def issue_certificate_if_eligible(
    student_id: int,
    course_id: int,
    app_config,
):
    """
    Check certificate eligibility and issue the certificate
    automatically when all course requirements are satisfied.

    Returns:
        Certificate | None
    """

    if not student_id:
        return None

    if not course_id:
        return None

    eligibility = check_eligibility(
        student_id,
        course_id,
    )

    if not eligibility.get(
        "eligible",
        False,
    ):
        return None

    return issue_certificate(
        student_id,
        course_id,
        app_config,
    )


# ============================================================
# ISSUE CERTIFICATE
# ============================================================

def issue_certificate(
    student_id: int,
    course_id: int,
    app_config,
) -> Certificate:
    """
    Issue a certificate after all course requirements
    have been satisfied.

    Creates:

    - Certificate database record
    - QR code
    - Professional PDF certificate
    """

    # --------------------------------------------------------
    # Existing certificate
    # --------------------------------------------------------

    existing = (
        Certificate.query
        .filter_by(
            StudentID=student_id,
            CourseID=course_id,
        )
        .first()
    )

    if existing:
        return existing

    # --------------------------------------------------------
    # Eligibility
    # --------------------------------------------------------

    eligibility = check_eligibility(
        student_id,
        course_id,
    )

    if not eligibility["eligible"]:

        raise CertificateError(
            "You have not yet met all requirements "
            "for this certificate."
        )

    # --------------------------------------------------------
    # Course
    # --------------------------------------------------------

    course = db.session.get(
        Course,
        course_id,
    )

    if course is None:

        raise CertificateError(
            "Course not found."
        )

    # --------------------------------------------------------
    # Enrollment
    # --------------------------------------------------------

    enrollment = (
        Enrollment.query
        .filter_by(
            StudentID=student_id,
            CourseID=course_id,
        )
        .first()
    )

    if enrollment is None:

        raise CertificateError(
            "Enrollment not found."
        )

    # --------------------------------------------------------
    # Final score
    # --------------------------------------------------------

    final_score = _calculate_final_score(
        student_id,
        course_id,
    )

    # --------------------------------------------------------
    # Certificate number
    # --------------------------------------------------------

    certificate_number = (
        _generate_unique_certificate_number()
    )

    # --------------------------------------------------------
    # Certificate database record
    # --------------------------------------------------------

    certificate = Certificate(
        StudentID=student_id,
        CourseID=course_id,
        CertificateNumber=certificate_number,
        FinalScore=final_score,
        IssueDate=datetime.now(
            timezone.utc
        ),
        Status="Valid",
    )

    try:

        db.session.add(
            certificate
        )

        db.session.commit()

        db.session.refresh(
            certificate
        )

    except Exception as exc:

        db.session.rollback()

        raise CertificateError(
            "Unable to create the certificate record."
        ) from exc

    # --------------------------------------------------------
    # Certificate folder
    # --------------------------------------------------------

    certificate_folder = (
        app_config.get(
            "CERTIFICATE_UPLOAD_FOLDER"
        )
    )

    if not certificate_folder:

        raise CertificateError(
            "Certificate storage folder is not configured."
        )

    os.makedirs(
        certificate_folder,
        exist_ok=True,
    )

    # --------------------------------------------------------
    # Base URL
    # --------------------------------------------------------

    base_url = (
        app_config.get(
            "BASE_URL",
            "",
        )
        or ""
    ).rstrip("/")

    if not base_url:

        raise CertificateError(
            "BASE_URL is not configured."
        )

    verify_url = (
        f"{base_url}"
        f"/certificates/verify/"
        f"{certificate_number}"
    )

    # --------------------------------------------------------
    # QR code
    # --------------------------------------------------------

    qr_filename = (
        f"{certificate_number}.png"
    )

    try:

        generate_qr_code(
            verify_url,
            certificate_folder,
            qr_filename,
        )

    except Exception as exc:

        db.session.delete(
            certificate
        )

        db.session.commit()

        raise CertificateError(
            "Unable to generate the certificate QR code."
        ) from exc

    certificate.QRCodePath = (
        qr_filename
    )

       # --------------------------------------------------------
    # PDF
    # --------------------------------------------------------

    pdf_filename = (
        f"{certificate_number}.pdf"
    )

    pdf_path = os.path.join(
        certificate_folder,
        pdf_filename,
    )

    try:

        # Generate PDF temporarily on the server.
        generate_certificate_pdf(
            certificate,
            certificate_folder,
            pdf_filename,
            qr_filename,
            app_config,
        )

        # Upload the generated PDF to Supabase Storage.
        storage_path = _upload_certificate_pdf(
            pdf_path,
            pdf_filename,
            app_config,
        )

    except CertificateError:

        # Remove temporary QR code.
        qr_path = os.path.join(
            certificate_folder,
            qr_filename,
        )

        _delete_local_file(
            qr_path
        )

        # Remove temporary PDF.
        _delete_local_file(
            pdf_path
        )

        db.session.delete(
            certificate
        )

        db.session.commit()

        raise

    except Exception as exc:

        # Remove temporary QR code.
        qr_path = os.path.join(
            certificate_folder,
            qr_filename,
        )

        _delete_local_file(
            qr_path
        )

        # Remove temporary PDF.
        _delete_local_file(
            pdf_path
        )

        db.session.delete(
            certificate
        )

        db.session.commit()

        raise CertificateError(
            "Unable to generate or upload "
            "the certificate PDF."
        ) from exc

    # Store the Supabase Storage object path.
    certificate.PDFPath = (
        storage_path
    )

    # The local PDF is no longer required.
    _delete_local_file(
        pdf_path
    )

    # QR code was only needed while creating
    # the certificate PDF.
    qr_path = os.path.join(
        certificate_folder,
        qr_filename,
    )

    _delete_local_file(
        qr_path
    )

    # --------------------------------------------------------
    # Mark enrollment completed
    # --------------------------------------------------------

    enrollment.Status = "Completed"

    if hasattr(
        enrollment,
        "CompletionDate",
    ):

        enrollment.CompletionDate = (
            datetime.now(timezone.utc)
        )

    try:

        db.session.commit()

    except Exception as exc:

        db.session.rollback()

        raise CertificateError(
            "Certificate was generated, but "
            "the enrollment status could not be updated."
        ) from exc

    return certificate


# ============================================================
# PDF HELPER FUNCTIONS
# ============================================================

def _draw_gold_line(
    pdf,
    x1,
    y,
    x2,
    width=1,
):
    """
    Draw decorative gold line.
    """

    pdf.setStrokeColor(
        HexColor("#c99a35")
    )

    pdf.setLineWidth(
        width
    )

    pdf.line(
        x1,
        y,
        x2,
        y,
    )


def _draw_corner_ribbon(
    pdf,
    x,
    y,
    size,
    flip_x=False,
    flip_y=False,
):
    """
    Decorative navy/gold corner element.
    """

    navy = HexColor("#071b3a")
    gold = HexColor("#d4aa4a")

    direction_x = -1 if flip_x else 1
    direction_y = -1 if flip_y else 1

    pdf.saveState()

    pdf.setFillColor(
        navy
    )

    path = pdf.beginPath()

    path.moveTo(
        x,
        y,
    )

    path.lineTo(
        x + direction_x * size,
        y,
    )

    path.lineTo(
        x,
        y + direction_y * size,
    )

    path.close()

    pdf.drawPath(
        path,
        fill=1,
        stroke=0,
    )

    pdf.setFillColor(
        gold
    )

    pdf.setLineWidth(
        5
    )

    pdf.line(
        x,
        y + direction_y * 8,
        x + direction_x * (size * .82),
        y + direction_y * (size * .82),
    )

    pdf.restoreState()


def _draw_seal(
    pdf,
    center_x,
    center_y,
):
    """
    Draw EduCertify certification seal.
    """

    navy = HexColor("#071b3a")
    navy_light = HexColor("#123d77")
    gold = HexColor("#d5aa45")
    gold_light = HexColor("#f3d47b")
    white = HexColor("#ffffff")

    pdf.saveState()

    # Outer gold circle
    pdf.setFillColor(
        gold
    )

    pdf.circle(
        center_x,
        center_y,
        1.55 * cm,
        fill=1,
        stroke=0,
    )

    # Navy circle
    pdf.setFillColor(
        navy
    )

    pdf.circle(
        center_x,
        center_y,
        1.30 * cm,
        fill=1,
        stroke=0,
    )

    # Inner circle
    pdf.setStrokeColor(
        gold_light
    )

    pdf.setLineWidth(
        1
    )

    pdf.circle(
        center_x,
        center_y,
        1.08 * cm,
        fill=0,
        stroke=1,
    )

    # Stars
    pdf.setFillColor(
        gold_light
    )

    pdf.setFont(
        "Helvetica-Bold",
        7,
    )

    pdf.drawCentredString(
        center_x,
        center_y + .72 * cm,
        "★  ★  ★",
    )

    # Graduation cap symbol
    pdf.setFillColor(
        white
    )

    pdf.setFont(
        "Helvetica-Bold",
        15,
    )

    pdf.drawCentredString(
        center_x,
        center_y + .12 * cm,
        "EDU",
    )

    # Certified
    pdf.setFillColor(
        gold_light
    )

    pdf.setFont(
        "Helvetica-Bold",
        6.5,
    )

    pdf.drawCentredString(
        center_x,
        center_y - .28 * cm,
        "CERTIFIED",
    )

    pdf.setFont(
        "Helvetica",
        4.8,
    )

    pdf.drawCentredString(
        center_x,
        center_y - .52 * cm,
        "BY EDUCERTIFY",
    )

    # Bottom stars
    pdf.setFont(
        "Helvetica-Bold",
        6,
    )

    pdf.drawCentredString(
        center_x,
        center_y - .78 * cm,
        "★  ★  ★",
    )

    # Ribbon
    ribbon_y = center_y - 1.55 * cm

    pdf.setFillColor(
        navy_light
    )

    left_path = pdf.beginPath()

    left_path.moveTo(
        center_x - .72 * cm,
        ribbon_y,
    )

    left_path.lineTo(
        center_x - .22 * cm,
        ribbon_y,
    )

    left_path.lineTo(
        center_x - .35 * cm,
        ribbon_y - 1.25 * cm,
    )

    left_path.lineTo(
        center_x - .58 * cm,
        ribbon_y - .92 * cm,
    )

    left_path.lineTo(
        center_x - .82 * cm,
        ribbon_y - 1.25 * cm,
    )

    left_path.close()

    pdf.drawPath(
        left_path,
        fill=1,
        stroke=0,
    )

    right_path = pdf.beginPath()

    right_path.moveTo(
        center_x + .22 * cm,
        ribbon_y,
    )

    right_path.lineTo(
        center_x + .72 * cm,
        ribbon_y,
    )

    right_path.lineTo(
        center_x + .82 * cm,
        ribbon_y - 1.25 * cm,
    )

    right_path.lineTo(
        center_x + .58 * cm,
        ribbon_y - .92 * cm,
    )

    right_path.lineTo(
        center_x + .35 * cm,
        ribbon_y - 1.25 * cm,
    )

    right_path.close()

    pdf.drawPath(
        right_path,
        fill=1,
        stroke=0,
    )

    pdf.restoreState()


def _draw_logo(
    pdf,
    logo_path,
    center_x,
    center_y,
):
    """
    Draw EduCertify logo if available.

    If no logo file exists, draw a clean fallback
    graduation-cap emblem.
    """

    navy = HexColor("#071b3a")
    blue = HexColor("#2563eb")
    gold = HexColor("#c99a35")

    if (
        logo_path
        and os.path.exists(logo_path)
    ):

        try:

            pdf.drawImage(
                ImageReader(
                    logo_path
                ),
                center_x - 1.15 * cm,
                center_y - .65 * cm,
                width=2.3 * cm,
                height=1.3 * cm,
                preserveAspectRatio=True,
                mask="auto",
            )

            return

        except Exception:
            pass

    # Fallback logo circle
    pdf.setFillColor(
        HexColor("#ffffff")
    )

    pdf.setStrokeColor(
        gold
    )

    pdf.setLineWidth(
        1.5
    )

    pdf.circle(
        center_x,
        center_y,
        .65 * cm,
        fill=1,
        stroke=1,
    )

    pdf.setFillColor(
        navy
    )

    pdf.setFont(
        "Helvetica-Bold",
        9,
    )

    pdf.drawCentredString(
        center_x,
        center_y - .08 * cm,
        "EC",
    )

    pdf.setFillColor(
        blue
    )

    pdf.setFont(
        "Helvetica-Bold",
        7,
    )

    pdf.drawCentredString(
        center_x,
        center_y - 1.05 * cm,
        "EDUCERTIFY",
    )


def _find_logo_path(
    app_config,
):
    """
    Try common EduCertify logo locations.

    This avoids breaking deployment if the exact
    static folder configuration differs.
    """

    configured = (
        app_config.get(
            "CERTIFICATE_LOGO_PATH"
        )
    )

    if configured:
        candidates = [
            configured
        ]
    else:
        candidates = []

    static_folder = (
        app_config.get(
            "STATIC_FOLDER"
        )
    )

    if static_folder:

        candidates.extend(
            [
                os.path.join(
                    static_folder,
                    "images",
                    "logo.png",
                ),
                os.path.join(
                    static_folder,
                    "img",
                    "logo.png",
                ),
                os.path.join(
                    static_folder,
                    "logo.png",
                ),
            ]
        )

    # Common project paths
    candidates.extend(
        [
            os.path.join(
                "static",
                "images",
                "logo.png",
            ),
            os.path.join(
                "static",
                "img",
                "logo.png",
            ),
            os.path.join(
                "static",
                "logo.png",
            ),
        ]
    )

    for path in candidates:

        if path and os.path.exists(path):

            return path

    return None


# ============================================================
# GENERATE PROFESSIONAL CERTIFICATE PDF
# ============================================================

def generate_certificate_pdf(
    certificate: Certificate,
    folder: str,
    filename: str,
    qr_filename: str,
    app_config=None,
):
    """
    Generate a premium professional landscape
    EduCertify certificate using ReportLab.

    Design includes:

    - EduCertify branding
    - Navy + gold theme
    - Double border
    - Decorative corner ribbons
    - Certificate title
    - Student name
    - Course name
    - Final score
    - Issue date
    - Certification seal
    - Founder signature
    - Certificate ID
    - QR verification
    - Watermark
    - Trust-feature footer
    """

    if app_config is None:
        app_config = {}

    os.makedirs(
        folder,
        exist_ok=True,
    )

    full_path = os.path.join(
        folder,
        filename,
    )

    qr_path = os.path.join(
        folder,
        qr_filename,
    )

    # --------------------------------------------------------
    # PAGE
    # --------------------------------------------------------

    page_size = landscape(A4)

    width, height = page_size

    pdf = pdf_canvas.Canvas(
        full_path,
        pagesize=page_size,
    )

    pdf.setTitle(
        "EduCertify Certificate"
    )

    pdf.setAuthor(
        "EduCertify"
    )

    # --------------------------------------------------------
    # COLORS
    # --------------------------------------------------------

    navy = HexColor(
        "#071b3a"
    )

    navy_2 = HexColor(
        "#0d2d59"
    )

    blue = HexColor(
        "#2563eb"
    )

    gold = HexColor(
        "#c99a35"
    )

    gold_light = HexColor(
        "#f3d47b"
    )

    gold_pale = HexColor(
        "#fff8e8"
    )

    gray = HexColor(
        "#64748b"
    )

    light_gray = HexColor(
        "#eef2f7"
    )

    white = HexColor(
        "#ffffff"
    )

    # --------------------------------------------------------
    # BACKGROUND
    # --------------------------------------------------------

    pdf.setFillColor(
        white
    )

    pdf.rect(
        0,
        0,
        width,
        height,
        fill=1,
        stroke=0,
    )

    # Subtle top background
    pdf.setFillColor(
        HexColor("#fbfcff")
    )

    pdf.rect(
        0,
        height * .15,
        width,
        height * .85,
        fill=1,
        stroke=0,
    )

    # --------------------------------------------------------
    # OUTER BORDER
    # --------------------------------------------------------

    pdf.setStrokeColor(
        navy
    )

    pdf.setLineWidth(
        1.2
    )

    pdf.roundRect(
        .65 * cm,
        .65 * cm,
        width - 1.3 * cm,
        height - 1.3 * cm,
        .28 * cm,
        fill=0,
        stroke=1,
    )

    # Gold border
    pdf.setStrokeColor(
        gold
    )

    pdf.setLineWidth(
        2
    )

    pdf.rect(
        1.0 * cm,
        1.0 * cm,
        width - 2.0 * cm,
        height - 2.0 * cm,
        fill=0,
        stroke=1,
    )

    # Inner fine border
    pdf.setStrokeColor(
        HexColor("#b58a2e")
    )

    pdf.setLineWidth(
        .5
    )

    pdf.rect(
        1.25 * cm,
        1.25 * cm,
        width - 2.5 * cm,
        height - 2.5 * cm,
        fill=0,
        stroke=1,
    )

    # --------------------------------------------------------
    # CORNER DECORATIONS
    # --------------------------------------------------------

    _draw_corner_ribbon(
        pdf,
        1.0 * cm,
        height - 1.0 * cm,
        3.1 * cm,
        False,
        False,
    )

    _draw_corner_ribbon(
        pdf,
        width - 1.0 * cm,
        height - 1.0 * cm,
        3.1 * cm,
        True,
        False,
    )

    _draw_corner_ribbon(
        pdf,
        1.0 * cm,
        1.0 * cm,
        2.8 * cm,
        False,
        True,
    )

    _draw_corner_ribbon(
        pdf,
        width - 1.0 * cm,
        1.0 * cm,
        2.8 * cm,
        True,
        True,
    )

    # --------------------------------------------------------
    # WATERMARK
    # --------------------------------------------------------

    pdf.saveState()

    pdf.setFillColor(
        HexColor("#071b3a")
    )

    pdf.setFillAlpha(
        0.035
    )

    pdf.setFont(
        "Helvetica-Bold",
        70,
    )

    pdf.translate(
        width / 2,
        height / 2,
    )

    pdf.rotate(
        -15
    )

    pdf.drawCentredString(
        0,
        0,
        "EDUCERTIFY",
    )

    pdf.restoreState()

    # --------------------------------------------------------
    # LOGO
    # --------------------------------------------------------

    logo_path = _find_logo_path(
        app_config
    )

    _draw_logo(
        pdf,
        logo_path,
        width / 2 - 3.8 * cm,
        height - 2.35 * cm,
    )

    # --------------------------------------------------------
    # BRAND NAME
    # --------------------------------------------------------

    brand_x = width / 2 - .7 * cm

    pdf.setFillColor(
        blue
    )

    pdf.setFont(
        "Helvetica-Bold",
        24,
    )

    pdf.drawString(
        brand_x,
        height - 2.35 * cm,
        "Edu",
    )

    pdf.setFillColor(
        navy
    )

    pdf.drawString(
        brand_x + 1.55 * cm,
        height - 2.35 * cm,
        "Certify",
    )

    pdf.setFillColor(
        gray
    )

    pdf.setFont(
        "Helvetica",
        8.5,
    )

    pdf.drawString(
        brand_x + .05 * cm,
        height - 2.88 * cm,
        "Learn • Certify • Succeed",
    )

    # --------------------------------------------------------
    # CERTIFICATE TITLE
    # --------------------------------------------------------

    pdf.setFillColor(
        navy
    )

    pdf.setFont(
        "Helvetica-Bold",
        35,
    )

    pdf.drawCentredString(
        width / 2,
        height - 4.35 * cm,
        "CERTIFICATE",
    )

    # Gold subtitle
    subtitle_y = (
        height - 4.95 * cm
    )

    _draw_gold_line(
        pdf,
        width / 2 - 5.0 * cm,
        subtitle_y + .06 * cm,
        width / 2 - 1.85 * cm,
        1.2,
    )

    _draw_gold_line(
        pdf,
        width / 2 + 1.85 * cm,
        subtitle_y + .06 * cm,
        width / 2 + 5.0 * cm,
        1.2,
    )

    pdf.setFillColor(
        HexColor("#9b7425")
    )

    pdf.setFont(
        "Helvetica",
        13,
    )

    pdf.drawCentredString(
        width / 2,
        subtitle_y,
        "OF COMPLETION",
    )

    # Small ornament
    pdf.setFont(
        "Helvetica-Bold",
        10,
    )

    pdf.drawCentredString(
        width / 2,
        subtitle_y - .42 * cm,
        "✦",
    )

    # --------------------------------------------------------
    # PRESENTED TO
    # --------------------------------------------------------

    pdf.setFillColor(
        gray
    )

    pdf.setFont(
        "Helvetica",
        10.5,
    )

    pdf.drawCentredString(
        width / 2,
        height - 6.05 * cm,
        "This certificate is proudly presented to",
    )

    # --------------------------------------------------------
    # STUDENT NAME
    # --------------------------------------------------------

    student_name = (
        certificate.student.FullName
        if certificate.student
        else "Student"
    )

    pdf.setFillColor(
        navy
    )

    # Keep long names inside certificate
    student_font_size = 27

    if len(student_name) > 28:
        student_font_size = 23

    if len(student_name) > 38:
        student_font_size = 19

    pdf.setFont(
        "Helvetica-Bold",
        student_font_size,
    )

    pdf.drawCentredString(
        width / 2,
        height - 7.15 * cm,
        student_name,
    )

    # Name gold underline
    _draw_gold_line(
        pdf,
        width / 2 - 4.8 * cm,
        height - 7.45 * cm,
        width / 2 + 4.8 * cm,
        1.0,
    )

    # --------------------------------------------------------
    # COMPLETION
    # --------------------------------------------------------

    pdf.setFillColor(
        gray
    )

    pdf.setFont(
        "Helvetica",
        10.5,
    )

    pdf.drawCentredString(
        width / 2,
        height - 8.05 * cm,
        "for successfully completing the course",
    )

    # --------------------------------------------------------
    # COURSE TITLE
    # --------------------------------------------------------

    course_title = (
        certificate.course.Title
        if certificate.course
        else "Course"
    )

    course_font_size = 21

    if len(course_title) > 34:
        course_font_size = 18

    if len(course_title) > 50:
        course_font_size = 15

    pdf.setFillColor(
        blue
    )

    pdf.setFont(
        "Helvetica-Bold",
        course_font_size,
    )

    pdf.drawCentredString(
        width / 2,
        height - 9.0 * cm,
        course_title,
    )

    # --------------------------------------------------------
    # SCORE
    # --------------------------------------------------------

    score = (
        certificate.FinalScore
        if certificate.FinalScore is not None
        else 0
    )

    score_y = (
        height - 9.85 * cm
    )

    pdf.setFillColor(
        navy
    )

    pdf.setFont(
        "Helvetica-Bold",
        11,
    )

    score_text = (
        f"Final Score: {float(score):.1f}%"
    )

    pdf.drawCentredString(
        width / 2,
        score_y,
        score_text,
    )

    # --------------------------------------------------------
    # ISSUE DATE
    # --------------------------------------------------------

    issue_date = (
        certificate.IssueDate
    )

    if issue_date:

        issue_str = issue_date.strftime(
            "%d %B %Y"
        )

    else:

        issue_str = "N/A"

    pdf.setFillColor(
        gray
    )

    pdf.setFont(
        "Helvetica",
        9.5,
    )

    pdf.drawCentredString(
        width / 2,
        height - 10.45 * cm,
        f"Issued on: {issue_str}",
    )

    # --------------------------------------------------------
    # SEAL
    # --------------------------------------------------------

    _draw_seal(
        pdf,
        4.2 * cm,
        4.65 * cm,
    )

    # --------------------------------------------------------
    # CERTIFICATE ID
    # --------------------------------------------------------

    pdf.setFillColor(
        navy
    )

    pdf.setFont(
        "Helvetica-Bold",
        8.5,
    )

    pdf.drawString(
        2.1 * cm,
        3.05 * cm,
        "CERTIFICATE ID",
    )

    pdf.setFillColor(
        blue
    )

    pdf.setFont(
        "Helvetica-Bold",
        10,
    )

    pdf.drawString(
        2.1 * cm,
        2.58 * cm,
        certificate.CertificateNumber,
    )

    # --------------------------------------------------------
    # SIGNATURE
    # --------------------------------------------------------

    signature_x = (
        width / 2
    )

    signature_y = (
        3.35 * cm
    )

    pdf.setFillColor(
        navy
    )

    pdf.setFont(
        "Helvetica-Oblique",
        20,
    )

    pdf.drawCentredString(
        signature_x,
        signature_y,
        "Rahul Sharma",
    )

    _draw_gold_line(
        pdf,
        signature_x - 3.0 * cm,
        signature_y - .25 * cm,
        signature_x + 3.0 * cm,
        .8,
    )

    pdf.setFillColor(
        blue
    )

    pdf.setFont(
        "Helvetica-Bold",
        8.5,
    )

    pdf.drawCentredString(
        signature_x,
        signature_y - .65 * cm,
        "Rahul Sharma",
    )

    pdf.setFillColor(
        gray
    )

    pdf.setFont(
        "Helvetica",
        7.5,
    )

    pdf.drawCentredString(
        signature_x,
        signature_y - 1.02 * cm,
        "Founder & CEO, EduCertify",
    )

    # --------------------------------------------------------
    # QR CODE
    # --------------------------------------------------------

    if os.path.exists(qr_path):

        qr_size = (
            2.35 * cm
        )

        qr_x = (
            width - 3.15 * cm - qr_size
        )

        qr_y = (
            2.28 * cm
        )

        # White QR background
        pdf.setFillColor(
            white
        )

        pdf.setStrokeColor(
            navy
        )

        pdf.setLineWidth(
            .8
        )

        pdf.roundRect(
            qr_x - .12 * cm,
            qr_y - .12 * cm,
            qr_size + .24 * cm,
            qr_size + .24 * cm,
            .08 * cm,
            fill=1,
            stroke=1,
        )

        pdf.drawImage(
            ImageReader(
                qr_path
            ),
            qr_x,
            qr_y,
            qr_size,
            qr_size,
            preserveAspectRatio=True,
            mask="auto",
        )

        pdf.setFillColor(
            gray
        )

        pdf.setFont(
            "Helvetica",
            6.8,
        )

        pdf.drawCentredString(
            qr_x + qr_size / 2,
            qr_y - .48 * cm,
            "SCAN TO VERIFY",
        )

    # --------------------------------------------------------
    # VERIFICATION TEXT
    # --------------------------------------------------------

    pdf.setFillColor(
        gray
    )

    pdf.setFont(
        "Helvetica-Oblique",
        7.2,
    )

    pdf.drawCentredString(
        width / 2,
        1.95 * cm,
        "Verify this certificate at the EduCertify Verification Portal",
    )

    # --------------------------------------------------------
    # FOOTER TRUST BAR
    # --------------------------------------------------------

    footer_x = 1.0 * cm
    footer_y = 1.0 * cm
    footer_w = width - 2.0 * cm
    footer_h = 1.35 * cm

    pdf.setFillColor(
        navy
    )

    pdf.rect(
        footer_x,
        footer_y,
        footer_w,
        footer_h,
        fill=1,
        stroke=0,
    )

    # Gold top edge
    pdf.setFillColor(
        gold
    )

    pdf.rect(
        footer_x,
        footer_y + footer_h - .07 * cm,
        footer_w,
        .07 * cm,
        fill=1,
        stroke=0,
    )

    footer_items = [
        (
            "▣",
            "Industry Relevant",
            "Curriculum",
        ),
        (
            "●",
            "Expert",
            "Instructors",
        ),
        (
            "★",
            "Verified",
            "Certificate",
        ),
        (
            "◎",
            "Lifetime",
            "Verification",
        ),
    ]

    item_width = (
        footer_w / 4
    )

    for index, item in enumerate(
        footer_items
    ):

        item_x = (
            footer_x
            + index * item_width
        )

        if index > 0:

            pdf.setStrokeColor(
                HexColor(
                    "#355477"
                )
            )

            pdf.setLineWidth(
                .5
            )

            pdf.line(
                item_x,
                footer_y + .12 * cm,
                item_x,
                footer_y + footer_h - .12 * cm,
            )

        icon, line1, line2 = item

        pdf.setFillColor(
            gold_light
        )

        pdf.setFont(
            "Helvetica-Bold",
            13,
        )

        pdf.drawString(
            item_x + .55 * cm,
            footer_y + .62 * cm,
            icon,
        )

        pdf.setFillColor(
            white
        )

        pdf.setFont(
            "Helvetica-Bold",
            6.5,
        )

        pdf.drawString(
            item_x + 1.05 * cm,
            footer_y + .76 * cm,
            line1,
        )

        pdf.setFont(
            "Helvetica",
            6,
        )

        pdf.drawString(
            item_x + 1.05 * cm,
            footer_y + .43 * cm,
            line2,
        )

    # --------------------------------------------------------
    # FINALIZE
    # --------------------------------------------------------

    pdf.showPage()

    pdf.save()


# ============================================================
# CERTIFICATE PDF PATH HELPER
# ============================================================

def get_certificate_pdf_path(certificate, app_config):
    """
    Safely resolve the physical PDF path for a certificate.

    Returns:
        str | None: Absolute PDF path if valid, otherwise None.

    This helper intentionally contains no Flask request/session handling.
    """

    if certificate is None:
        return None

    pdf_filename = getattr(certificate, "PDFPath", None)

    if not pdf_filename:
        return None

    certificate_folder = (
        app_config.get("CERTIFICATE_UPLOAD_FOLDER")
        if app_config
        else None
    )

    if not certificate_folder:
        return None

    certificate_folder = os.path.abspath(
        certificate_folder
    )

    # PDFPath should contain only a filename.  Strip any directory
    # components so database values cannot escape the certificate folder.
    filename = (
        str(pdf_filename)
        .replace("\\", "/")
        .split("/")[-1]
        .strip()
    )

    if not filename:
        return None

    if not filename.lower().endswith(".pdf"):
        return None

    pdf_path = os.path.abspath(
        os.path.join(
            certificate_folder,
            filename,
        )
    )

    try:
        if os.path.commonpath(
            [
                certificate_folder,
                pdf_path,
            ]
        ) != certificate_folder:
            return None
    except ValueError:
        return None

    if not os.path.isfile(pdf_path):
        return None

    return pdf_path


# ============================================================
# VERIFY CERTIFICATE
# ============================================================

def verify_certificate(
    certificate_number: str,
):
    """
    Public certificate lookup.

    No authentication is required.

    Returns:
        Certificate object or None.
    """

    if not certificate_number:
        return None

    certificate_number = (
        str(certificate_number)
        .strip()
        .upper()
    )

    if not certificate_number:
        return None

    return (
        Certificate.query
        .filter_by(
            CertificateNumber=
            certificate_number
        )
        .first()
    )


# ============================================================
# REVOKE CERTIFICATE
# ============================================================

def revoke_certificate(
    certificate_id: int,
    reason: str = "",
) -> Certificate:
    """
    Revoke a certificate.

    Args:
        certificate_id:
            Certificate database ID.

        reason:
            Optional revocation reason.

    Returns:
        Updated Certificate.
    """

    certificate = db.session.get(
        Certificate,
        certificate_id,
    )

    if certificate is None:

        raise CertificateError(
            "Certificate not found."
        )

    if certificate.Status == "Revoked":

        raise CertificateError(
            "This certificate has already been revoked."
        )

    certificate.Status = "Revoked"

    # Store reason only if supported
    if (
        reason
        and hasattr(
            certificate,
            "RevocationReason",
        )
    ):

        certificate.RevocationReason = (
            reason.strip()
        )

    try:

        db.session.commit()

    except Exception as exc:

        db.session.rollback()

        raise CertificateError(
            "Unable to revoke the certificate."
        ) from exc

    return certificate

