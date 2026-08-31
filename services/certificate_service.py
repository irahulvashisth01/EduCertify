"""
Certificate business logic:
- Eligibility checking (lessons complete + quizzes passed + final assessment passed)
- Unique certificate number generation
- PDF generation (ReportLab)
- QR code generation pointing to the public verification page
- Public verification lookup
"""

import os
from datetime import datetime, timezone

from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib.units import cm
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas as pdf_canvas

from database.database import db
from database.models import Certificate, Enrollment, Quiz, QuizAttempt, Course, LessonProgress
from utils.helpers import generate_certificate_number
from utils.qr_generator import generate_qr_code


class CertificateError(Exception):
    pass


def check_eligibility(student_id: int, course_id: int) -> dict:
    """
    Returns a dict describing whether the student is eligible for a
    certificate, and which requirements are outstanding.
    """
    course = Course.query.get(course_id)
    if not course:
        raise CertificateError("Course not found.")

    enrollment = Enrollment.query.filter_by(StudentID=student_id, CourseID=course_id).first()
    if not enrollment:
        raise CertificateError("You are not enrolled in this course.")

    total_lessons = course.total_lessons
    lesson_ids = [lesson.LessonID for module in course.modules for lesson in module.lessons]
    completed_lessons = LessonProgress.query.filter(
        LessonProgress.StudentID == student_id,
        LessonProgress.LessonID.in_(lesson_ids) if lesson_ids else False,
        LessonProgress.Completed.is_(True),
    ).count() if lesson_ids else 0

    lessons_done = total_lessons > 0 and completed_lessons == total_lessons

    quizzes = Quiz.query.filter_by(CourseID=course_id).all()
    module_quizzes = [q for q in quizzes if not q.IsFinalAssessment]
    final_assessments = [q for q in quizzes if q.IsFinalAssessment]

    module_quizzes_passed = all(
        QuizAttempt.query.filter_by(StudentID=student_id, QuizID=q.QuizID, Passed=True).first() is not None
        for q in module_quizzes
    ) if module_quizzes else True

    final_score = None
    final_passed = True
    if final_assessments:
        final_quiz = final_assessments[0]
        best_attempt = (
            QuizAttempt.query.filter_by(StudentID=student_id, QuizID=final_quiz.QuizID, Passed=True)
            .order_by(QuizAttempt.Percentage.desc())
            .first()
        )
        final_passed = best_attempt is not None
        if best_attempt:
            final_score = best_attempt.Percentage

    eligible = lessons_done and module_quizzes_passed and final_passed

    return {
        "eligible": eligible,
        "lessons_done": lessons_done,
        "total_lessons": total_lessons,
        "completed_lessons": completed_lessons,
        "module_quizzes_passed": module_quizzes_passed,
        "final_assessment_required": bool(final_assessments),
        "final_passed": final_passed,
        "final_score": final_score,
    }


def _calculate_final_score(student_id: int, course_id: int) -> float:
    """Compute a final score for the certificate: average of all passed quiz
    percentages for the course, falling back to 100 if there were no quizzes."""
    quizzes = Quiz.query.filter_by(CourseID=course_id).all()
    if not quizzes:
        return 100.0

    scores = []
    for quiz in quizzes:
        best = (
            QuizAttempt.query.filter_by(StudentID=student_id, QuizID=quiz.QuizID)
            .order_by(QuizAttempt.Percentage.desc())
            .first()
        )
        if best:
            scores.append(best.Percentage)

    return round(sum(scores) / len(scores), 1) if scores else 100.0


def issue_certificate(student_id: int, course_id: int, app_config) -> Certificate:
    existing = Certificate.query.filter_by(StudentID=student_id, CourseID=course_id).first()
    if existing:
        return existing

    eligibility = check_eligibility(student_id, course_id)
    if not eligibility["eligible"]:
        raise CertificateError("You have not yet met all requirements for this certificate.")

    final_score = _calculate_final_score(student_id, course_id)

    # Ensure certificate number uniqueness
    cert_number = generate_certificate_number()
    while Certificate.query.filter_by(CertificateNumber=cert_number).first() is not None:
        cert_number = generate_certificate_number()

    certificate = Certificate(
        StudentID=student_id,
        CourseID=course_id,
        CertificateNumber=cert_number,
        FinalScore=final_score,
        IssueDate=datetime.now(timezone.utc),
        Status="Valid",
    )
    db.session.add(certificate)
    db.session.commit()

    # Generate QR code pointing at the public verification page
    verify_url = f"{app_config['BASE_URL']}/certificates/verify/{cert_number}"
    qr_filename = f"{cert_number}.png"
    generate_qr_code(verify_url, app_config["CERTIFICATE_UPLOAD_FOLDER"], qr_filename)
    certificate.QRCodePath = qr_filename

    # Generate the PDF certificate
    pdf_filename = f"{cert_number}.pdf"
    generate_certificate_pdf(certificate, app_config["CERTIFICATE_UPLOAD_FOLDER"], pdf_filename, qr_filename)
    certificate.PDFPath = pdf_filename

    db.session.commit()

    # Mark enrollment completed
    enrollment = Enrollment.query.filter_by(StudentID=student_id, CourseID=course_id).first()
    if enrollment and enrollment.Status != "Completed":
        enrollment.Status = "Completed"
        enrollment.CompletionDate = datetime.now(timezone.utc)
        db.session.commit()

    return certificate


def generate_certificate_pdf(certificate: Certificate, folder: str, filename: str, qr_filename: str):
    """Render a professional landscape PDF certificate using ReportLab."""
    os.makedirs(folder, exist_ok=True)
    full_path = os.path.join(folder, filename)
    qr_path = os.path.join(folder, qr_filename)

    page_size = landscape(A4)
    width, height = page_size
    c = pdf_canvas.Canvas(full_path, pagesize=page_size)

    navy = HexColor("#0b1f3a")
    blue = HexColor("#2563eb")
    gray = HexColor("#64748b")

    # Border
    c.setStrokeColor(blue)
    c.setLineWidth(3)
    c.rect(1.2 * cm, 1.2 * cm, width - 2.4 * cm, height - 2.4 * cm)
    c.setStrokeColor(navy)
    c.setLineWidth(0.75)
    c.rect(1.5 * cm, 1.5 * cm, width - 3 * cm, height - 3 * cm)

    # Header
    c.setFillColor(navy)
    c.setFont("Helvetica-Bold", 26)
    c.drawCentredString(width / 2, height - 3.2 * cm, "EDUCERTIFY")

    c.setFont("Helvetica", 14)
    c.setFillColor(gray)
    c.drawCentredString(width / 2, height - 4.1 * cm, "Certificate of Completion")

    # Body
    c.setFillColor(gray)
    c.setFont("Helvetica", 12)
    c.drawCentredString(width / 2, height - 5.6 * cm, "This certificate is proudly presented to")

    c.setFillColor(navy)
    c.setFont("Helvetica-Bold", 28)
    c.drawCentredString(width / 2, height - 6.8 * cm, certificate.student.FullName)

    c.setFillColor(gray)
    c.setFont("Helvetica", 12)
    c.drawCentredString(width / 2, height - 7.9 * cm, "for successfully completing")

    c.setFillColor(blue)
    c.setFont("Helvetica-Bold", 20)
    c.drawCentredString(width / 2, height - 8.9 * cm, certificate.course.Title)

    c.setFillColor(navy)
    c.setFont("Helvetica-Bold", 13)
    c.drawCentredString(width / 2, height - 9.9 * cm, f"Final Score: {certificate.FinalScore}%")

    issue_str = certificate.IssueDate.strftime("%d %B %Y")
    c.setFillColor(gray)
    c.setFont("Helvetica", 11)
    c.drawCentredString(width / 2, height - 10.6 * cm, f"Issued: {issue_str}")

    # Certificate ID (bottom left)
    c.setFillColor(navy)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(2.2 * cm, 2.4 * cm, "Certificate ID:")
    c.setFont("Helvetica", 11)
    c.drawString(2.2 * cm, 1.9 * cm, certificate.CertificateNumber)

    # QR code (bottom right)
    if os.path.exists(qr_path):
        qr_size = 2.6 * cm
        c.drawImage(qr_path, width - 2.2 * cm - qr_size, 1.6 * cm, qr_size, qr_size)
        c.setFont("Helvetica", 8)
        c.setFillColor(gray)
        c.drawRightString(width - 2.2 * cm, 1.35 * cm, "Scan to verify")

    c.setFont("Helvetica-Oblique", 9)
    c.setFillColor(gray)
    c.drawCentredString(width / 2, 1.7 * cm, "Verify this certificate at the EduCertify Verification Portal")

    c.showPage()
    c.save()


def verify_certificate(certificate_number: str):
    """Public lookup - no login required. Returns Certificate or None."""
    if not certificate_number:
        return None
    return Certificate.query.filter_by(CertificateNumber=certificate_number.strip().upper()).first()


def revoke_certificate(certificate_id: int, reason: str = ""):
    certificate = Certificate.query.get(certificate_id)
    if not certificate:
        raise CertificateError("Certificate not found.")
    certificate.Status = "Revoked"
    db.session.commit()
    return certificate
