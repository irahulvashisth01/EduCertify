"""
REST-style JSON API endpoints consumed by frontend fetch() calls.
Every response follows: {"success": bool, "message": str, ...extra}
"""

from flask import Blueprint, request, session, jsonify

from database.models import Lesson, Course
from utils.decorators import login_required, role_required
from utils.helpers import json_response
from services.progress_service import mark_lesson_complete
from services.quiz_service import start_attempt, submit_attempt, get_quiz_for_taking, QuizError
from services.certificate_service import verify_certificate

api_bp = Blueprint("api", __name__, url_prefix="/api")


@api_bp.route("/courses")
def api_courses():
    courses = Course.query.filter_by(Status="Published").limit(50).all()
    data = [
        {
            "CourseID": c.CourseID,
            "Title": c.Title,
            "Slug": c.Slug,
            "Level": c.Level,
            "Price": c.Price,
        }
        for c in courses
    ]
    return jsonify(json_response(True, "OK", courses=data))


@api_bp.route("/courses/<int:course_id>")
def api_course_detail(course_id):
    course = Course.query.get(course_id)
    if not course:
        return jsonify(json_response(False, "Course not found")), 404
    return jsonify(json_response(True, "OK", course={
        "CourseID": course.CourseID,
        "Title": course.Title,
        "Slug": course.Slug,
        "TotalLessons": course.total_lessons,
    }))


@api_bp.route("/progress/<int:lesson_id>", methods=["POST"])
@login_required
@role_required("Student")
def api_mark_progress(lesson_id):
    lesson = Lesson.query.get(lesson_id)
    if not lesson:
        return jsonify(json_response(False, "Lesson not found")), 404

    try:
        new_progress = mark_lesson_complete(session["user_id"], lesson_id)
    except ValueError as e:
        return jsonify(json_response(False, str(e))), 400

    return jsonify(json_response(True, "Progress updated", progress=new_progress))


@api_bp.route("/quizzes/<int:quiz_id>/start", methods=["POST"])
@login_required
@role_required("Student")
def api_start_quiz(quiz_id):
    try:
        attempt = start_attempt(session["user_id"], quiz_id)
        quiz, questions = get_quiz_for_taking(quiz_id)
    except QuizError as e:
        return jsonify(json_response(False, str(e))), 400

    return jsonify(json_response(
        True, "Quiz started",
        attempt_id=attempt.AttemptID,
        time_limit=quiz.TimeLimit,
        questions=questions,
    ))


@api_bp.route("/quizzes/<int:quiz_id>/submit", methods=["POST"])
@login_required
@role_required("Student")
def api_submit_quiz(quiz_id):
    payload = request.get_json(silent=True) or {}
    attempt_id = payload.get("attempt_id")
    answers = payload.get("answers", {})

    if not attempt_id:
        return jsonify(json_response(False, "Missing attempt_id")), 400

    try:
        attempt = submit_attempt(session["user_id"], attempt_id, answers)
    except QuizError as e:
        return jsonify(json_response(False, str(e))), 400

    return jsonify(json_response(
        True, "Quiz submitted",
        score=attempt.Score,
        percentage=attempt.Percentage,
        passed=attempt.Passed,
    ))


@api_bp.route("/certificates/verify/<certificate_id>")
def api_verify_certificate(certificate_id):
    cert = verify_certificate(certificate_id)
    if not cert:
        return jsonify(json_response(False, "Certificate not found", valid=False)), 404

    return jsonify(json_response(
        True, "Certificate found", valid=(cert.Status == "Valid"),
        certificate={
            "CertificateNumber": cert.CertificateNumber,
            "StudentName": cert.student.FullName,
            "CourseTitle": cert.course.Title,
            "FinalScore": cert.FinalScore,
            "IssueDate": cert.IssueDate.strftime("%d %B %Y"),
            "Status": cert.Status,
        }
    ))
