"""
Instructor-facing routes: dashboard, course creation/management,
modules, lessons, quizzes, students, analytics.
"""

from flask import Blueprint, render_template, request, redirect, url_for, session, flash

from database.models import Course, Category, Enrollment, QuizAttempt, Review
from utils.decorators import login_required, role_required
from services.course_service import (
    create_course, update_course, submit_for_review, add_module, add_lesson,
    add_quiz, add_question, get_instructor_courses, get_owned_course, CourseError, OwnershipError
)

instructor_bp = Blueprint("instructor", __name__, url_prefix="/instructor")


@instructor_bp.route("/dashboard")
@login_required
@role_required("Instructor")
def dashboard():
    instructor_id = session["user_id"]
    courses = get_instructor_courses(instructor_id)

    total_students = 0
    for course in courses:
        total_students += Enrollment.query.filter_by(CourseID=course.CourseID).count()

    published_count = len([c for c in courses if c.Status == "Published"])
    pending_count = len([c for c in courses if c.Status == "Pending"])

    return render_template(
        "instructor/dashboard.html",
        courses=courses,
        total_students=total_students,
        published_count=published_count,
        pending_count=pending_count,
    )


@instructor_bp.route("/courses")
@login_required
@role_required("Instructor")
def courses():
    instructor_id = session["user_id"]
    course_list = get_instructor_courses(instructor_id)
    return render_template("instructor/courses.html", courses=course_list)


@instructor_bp.route("/courses/create", methods=["GET", "POST"])
@login_required
@role_required("Instructor")
def create_course_view():
    categories = Category.query.filter_by(IsActive=True).all()

    if request.method == "POST":
        try:
            course = create_course(
                instructor_id=session["user_id"],
                title=request.form.get("title", ""),
                category_id=request.form.get("category_id", type=int),
                short_description=request.form.get("short_description", ""),
                description=request.form.get("description", ""),
                level=request.form.get("level", "Beginner"),
                duration=request.form.get("duration", ""),
                price=request.form.get("price", 0, type=float),
                passing_score=request.form.get("passing_score", 70, type=int),
            )
            flash("Course created as draft. Now add modules and lessons.", "success")
            return redirect(url_for("instructor.edit_course", course_id=course.CourseID))
        except CourseError as e:
            flash(str(e), "error")

    return render_template("instructor/create_course.html", categories=categories)


@instructor_bp.route("/courses/<int:course_id>/edit", methods=["GET", "POST"])
@login_required
@role_required("Instructor")
def edit_course(course_id):
    try:
        course = get_owned_course(course_id, session["user_id"])
    except OwnershipError:
        flash("You do not have permission to edit this course.", "error")
        return redirect(url_for("instructor.courses"))
    except CourseError as e:
        flash(str(e), "error")
        return redirect(url_for("instructor.courses"))

    categories = Category.query.filter_by(IsActive=True).all()

    if request.method == "POST":
        try:
            update_course(
                course_id, session["user_id"],
                title=request.form.get("title"),
                short_description=request.form.get("short_description"),
                description=request.form.get("description"),
                level=request.form.get("level"),
                duration=request.form.get("duration"),
                price=request.form.get("price", type=float),
                passing_score=request.form.get("passing_score", type=int),
                category_id=request.form.get("category_id", type=int),
            )
            flash("Course updated successfully.", "success")
            return redirect(url_for("instructor.edit_course", course_id=course_id))
        except CourseError as e:
            flash(str(e), "error")

    return render_template("instructor/edit_course.html", course=course, categories=categories)


@instructor_bp.route("/courses/<int:course_id>/submit", methods=["POST"])
@login_required
@role_required("Instructor")
def submit_course(course_id):
    try:
        submit_for_review(course_id, session["user_id"])
        flash("Course submitted for admin review.", "success")
    except (CourseError, OwnershipError) as e:
        flash(str(e), "error")
    return redirect(url_for("instructor.edit_course", course_id=course_id))


@instructor_bp.route("/courses/<int:course_id>/modules", methods=["GET", "POST"])
@login_required
@role_required("Instructor")
def modules(course_id):
    try:
        course = get_owned_course(course_id, session["user_id"])
    except (CourseError, OwnershipError) as e:
        flash(str(e), "error")
        return redirect(url_for("instructor.courses"))

    if request.method == "POST":
        try:
            add_module(course_id, session["user_id"], request.form.get("title", ""), request.form.get("description", ""))
            flash("Module added.", "success")
        except (CourseError, OwnershipError) as e:
            flash(str(e), "error")
        return redirect(url_for("instructor.modules", course_id=course_id))

    return render_template("instructor/modules.html", course=course)


@instructor_bp.route("/modules/<int:module_id>/lessons", methods=["GET", "POST"])
@login_required
@role_required("Instructor")
def lessons(module_id):
    from database.models import Module
    module = Module.query.get_or_404(module_id)
    if module.course.InstructorID != session["user_id"]:
        flash("You do not have permission to modify this module.", "error")
        return redirect(url_for("instructor.courses"))

    if request.method == "POST":
        try:
            add_lesson(
                module_id, session["user_id"],
                request.form.get("title", ""),
                description=request.form.get("description", ""),
                content=request.form.get("content", ""),
                video_url=request.form.get("video_url", ""),
                resource_url=request.form.get("resource_url", ""),
                duration=request.form.get("duration", ""),
                is_preview=bool(request.form.get("is_preview")),
            )
            flash("Lesson added.", "success")
        except (CourseError, OwnershipError) as e:
            flash(str(e), "error")
        return redirect(url_for("instructor.lessons", module_id=module_id))

    return render_template("instructor/lessons.html", module=module)


@instructor_bp.route("/courses/<int:course_id>/quizzes", methods=["GET", "POST"])
@login_required
@role_required("Instructor")
def quizzes(course_id):
    try:
        course = get_owned_course(course_id, session["user_id"])
    except (CourseError, OwnershipError) as e:
        flash(str(e), "error")
        return redirect(url_for("instructor.courses"))

    if request.method == "POST":
        try:
            add_quiz(
                course_id, session["user_id"],
                request.form.get("title", ""),
                description=request.form.get("description", ""),
                passing_score=request.form.get("passing_score", 70, type=int),
                time_limit=request.form.get("time_limit", type=int),
                attempts_allowed=request.form.get("attempts_allowed", 3, type=int),
                is_final_assessment=bool(request.form.get("is_final_assessment")),
                module_id=request.form.get("module_id", type=int) or None,
            )
            flash("Quiz created. Now add questions.", "success")
        except (CourseError, OwnershipError) as e:
            flash(str(e), "error")
        return redirect(url_for("instructor.quizzes", course_id=course_id))

    return render_template("instructor/quizzes.html", course=course)


@instructor_bp.route("/quizzes/<int:quiz_id>/questions", methods=["POST"])
@login_required
@role_required("Instructor")
def add_question_view(quiz_id):
    from database.models import Quiz
    quiz = Quiz.query.get_or_404(quiz_id)
    try:
        add_question(
            quiz_id, session["user_id"],
            question_text=request.form.get("question_text", ""),
            option_a=request.form.get("option_a", ""),
            option_b=request.form.get("option_b", ""),
            option_c=request.form.get("option_c", ""),
            option_d=request.form.get("option_d", ""),
            correct_option=request.form.get("correct_option", ""),
            marks=request.form.get("marks", 1, type=int),
        )
        flash("Question added.", "success")
    except (CourseError, OwnershipError) as e:
        flash(str(e), "error")
    return redirect(url_for("instructor.quizzes", course_id=quiz.CourseID))


@instructor_bp.route("/students")
@login_required
@role_required("Instructor")
def students():
    instructor_id = session["user_id"]
    courses = get_instructor_courses(instructor_id)
    course_ids = [c.CourseID for c in courses]
    enrollments = Enrollment.query.filter(Enrollment.CourseID.in_(course_ids)).all() if course_ids else []
    return render_template("instructor/students.html", enrollments=enrollments)


@instructor_bp.route("/analytics")
@login_required
@role_required("Instructor")
def analytics():
    instructor_id = session["user_id"]
    courses = get_instructor_courses(instructor_id)

    course_stats = []
    for course in courses:
        enrollments = Enrollment.query.filter_by(CourseID=course.CourseID).all()
        completed = len([e for e in enrollments if e.Status == "Completed"])
        total = len(enrollments)
        completion_rate = round((completed / total) * 100, 1) if total else 0

        quiz_ids = [q.QuizID for q in course.quizzes]
        attempts = (
            QuizAttempt.query.filter(QuizAttempt.QuizID.in_(quiz_ids), QuizAttempt.CompletedAt.isnot(None)).all()
            if quiz_ids else []
        )
        avg_quiz_score = round(sum(a.Percentage for a in attempts) / len(attempts), 1) if attempts else 0

        reviews = Review.query.filter_by(CourseID=course.CourseID).all()
        avg_rating = round(sum(r.Rating for r in reviews) / len(reviews), 1) if reviews else 0

        course_stats.append({
            "course": course,
            "total_students": total,
            "completed": completed,
            "completion_rate": completion_rate,
            "avg_rating": avg_rating,
            "avg_quiz_score": avg_quiz_score,
        })

    return render_template("instructor/analytics.html", course_stats=course_stats)
