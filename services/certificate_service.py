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
- PDF certificate generation
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

    Returns:
        Dictionary containing eligibility information.
    """

    # --------------------------------------------------------
    # Find course
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
    # Check enrollment
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

        # The first final assessment is treated
        # as the course final assessment.
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

    # Try several times to avoid an accidental infinite loop.
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

    Returns None when the student is not yet eligible.

    Raises:
        CertificateError:
            If certificate generation itself fails after the
            student has become eligible.
    """

    if not student_id:
        return None

    if not course_id:
        return None

    # --------------------------------------------------------
    # Check eligibility first
    # --------------------------------------------------------

    eligibility = check_eligibility(
        student_id,
        course_id,
    )

    if not eligibility.get("eligible", False):
        return None

    # --------------------------------------------------------
    # Issue certificate
    # --------------------------------------------------------

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
    - PDF certificate
    """

    # --------------------------------------------------------
    # Check if certificate already exists
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
    # Check eligibility
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
    # Find course/enrollment
    # --------------------------------------------------------

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
            "Enrollment not found."
        )

    # --------------------------------------------------------
    # Calculate final score
    # --------------------------------------------------------

    final_score = _calculate_final_score(
        student_id,
        course_id,
    )

    # --------------------------------------------------------
    # Generate certificate number
    # --------------------------------------------------------

    certificate_number = (
        _generate_unique_certificate_number()
    )

    # --------------------------------------------------------
    # Create certificate record
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
    # Certificate storage directory
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
    # Generate QR code
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
    # Generate PDF
    # --------------------------------------------------------

    pdf_filename = (
        f"{certificate_number}.pdf"
    )

    try:

        generate_certificate_pdf(
            certificate,
            certificate_folder,
            pdf_filename,
            qr_filename,
        )

    except Exception as exc:

        # Remove generated QR file if possible.
        qr_path = os.path.join(
            certificate_folder,
            qr_filename,
        )

        if os.path.exists(qr_path):

            try:
                os.remove(qr_path)
            except OSError:
                pass

        db.session.delete(
            certificate
        )

        db.session.commit()

        raise CertificateError(
            "Unable to generate the certificate PDF."
        ) from exc

    certificate.PDFPath = (
        pdf_filename
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
# GENERATE CERTIFICATE PDF
# ============================================================

def generate_certificate_pdf(
    certificate: Certificate,
    folder: str,
    filename: str,
    qr_filename: str,
):
    """
    Generate a professional landscape certificate
    using ReportLab.
    """

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

    page_size = landscape(A4)

    width, height = page_size

    pdf = pdf_canvas.Canvas(
        full_path,
        pagesize=page_size,
    )

    # --------------------------------------------------------
    # Colors
    # --------------------------------------------------------

    navy = HexColor(
        "#0b1f3a"
    )

    blue = HexColor(
        "#2563eb"
    )

    gray = HexColor(
        "#64748b"
    )

    # --------------------------------------------------------
    # Outer border
    # --------------------------------------------------------

    pdf.setStrokeColor(
        blue
    )

    pdf.setLineWidth(
        3
    )

    pdf.rect(
        1.2 * cm,
        1.2 * cm,
        width - 2.4 * cm,
        height - 2.4 * cm,
    )

    # --------------------------------------------------------
    # Inner border
    # --------------------------------------------------------

    pdf.setStrokeColor(
        navy
    )

    pdf.setLineWidth(
        0.75
    )

    pdf.rect(
        1.5 * cm,
        1.5 * cm,
        width - 3 * cm,
        height - 3 * cm,
    )

    # --------------------------------------------------------
    # Header
    # --------------------------------------------------------

    pdf.setFillColor(
        navy
    )

    pdf.setFont(
        "Helvetica-Bold",
        26,
    )

    pdf.drawCentredString(
        width / 2,
        height - 3.2 * cm,
        "EDUCERTIFY",
    )

    pdf.setFont(
        "Helvetica",
        14,
    )

    pdf.setFillColor(
        gray
    )

    pdf.drawCentredString(
        width / 2,
        height - 4.1 * cm,
        "Certificate of Completion",
    )

    # --------------------------------------------------------
    # Intro text
    # --------------------------------------------------------

    pdf.setFillColor(
        gray
    )

    pdf.setFont(
        "Helvetica",
        12,
    )

    pdf.drawCentredString(
        width / 2,
        height - 5.6 * cm,
        "This certificate is proudly presented to",
    )

    # --------------------------------------------------------
    # Student name
    # --------------------------------------------------------

    student_name = (
        certificate.student.FullName
        if certificate.student
        else "Student"
    )

    pdf.setFillColor(
        navy
    )

    pdf.setFont(
        "Helvetica-Bold",
        28,
    )

    pdf.drawCentredString(
        width / 2,
        height - 6.8 * cm,
        student_name,
    )

    # --------------------------------------------------------
    # Course completion
    # --------------------------------------------------------

    pdf.setFillColor(
        gray
    )

    pdf.setFont(
        "Helvetica",
        12,
    )

    pdf.drawCentredString(
        width / 2,
        height - 7.9 * cm,
        "for successfully completing",
    )

    course_title = (
        certificate.course.Title
        if certificate.course
        else "Course"
    )

    pdf.setFillColor(
        blue
    )

    pdf.setFont(
        "Helvetica-Bold",
        20,
    )

    pdf.drawCentredString(
        width / 2,
        height - 8.9 * cm,
        course_title,
    )

    # --------------------------------------------------------
    # Score
    # --------------------------------------------------------

    pdf.setFillColor(
        navy
    )

    pdf.setFont(
        "Helvetica-Bold",
        13,
    )

    score = (
        certificate.FinalScore
        if certificate.FinalScore is not None
        else 0
    )

    pdf.drawCentredString(
        width / 2,
        height - 9.9 * cm,
        f"Final Score: {score}%",
    )

    # --------------------------------------------------------
    # Issue date
    # --------------------------------------------------------

    issue_date = certificate.IssueDate

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
        11,
    )

    pdf.drawCentredString(
        width / 2,
        height - 10.6 * cm,
        f"Issued: {issue_str}",
    )

    # --------------------------------------------------------
    # Certificate ID
    # --------------------------------------------------------

    pdf.setFillColor(
        navy
    )

    pdf.setFont(
        "Helvetica-Bold",
        11,
    )

    pdf.drawString(
        2.2 * cm,
        2.4 * cm,
        "Certificate ID:",
    )

    pdf.setFont(
        "Helvetica",
        11,
    )

    pdf.drawString(
        2.2 * cm,
        1.9 * cm,
        certificate.CertificateNumber,
    )

    # --------------------------------------------------------
    # QR code
    # --------------------------------------------------------

    if os.path.exists(qr_path):

        qr_size = 2.6 * cm

        pdf.drawImage(
            qr_path,
            width - 2.2 * cm - qr_size,
            1.6 * cm,
            qr_size,
            qr_size,
            preserveAspectRatio=True,
            mask="auto",
        )

        pdf.setFont(
            "Helvetica",
            8,
        )

        pdf.setFillColor(
            gray
        )

        pdf.drawRightString(
            width - 2.2 * cm,
            1.35 * cm,
            "Scan to verify",
        )

    # --------------------------------------------------------
    # Footer
    # --------------------------------------------------------

    pdf.setFont(
        "Helvetica-Oblique",
        9,
    )

    pdf.setFillColor(
        gray
    )

    pdf.drawCentredString(
        width / 2,
        1.7 * cm,
        "Verify this certificate at the EduCertify Verification Portal",
    )

    # --------------------------------------------------------
    # Save PDF
    # --------------------------------------------------------

    pdf.showPage()

    pdf.save()


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
        certificate_id: Certificate database ID.
        reason: Optional revocation reason.

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

    # Store reason only if your model has a corresponding
    # field. This keeps the service compatible with the
    # current model.
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