"""
EduCertify — Progress Service

Business logic for tracking lesson completion and calculating
student course/module progress.

Responsibilities:
- Mark lessons as completed
- Recalculate course progress
- Update enrollment completion status
- Retrieve completed lesson IDs
- Calculate module progress

Routes should call this service instead of directly modifying
progress records.
"""

from datetime import datetime, timezone

from database.database import db
from database.models import (
    LessonProgress,
    Lesson,
    Module,
    Enrollment,
)

from utils.helpers import calculate_percentage


# ============================================================
# MARK LESSON COMPLETE
# ============================================================

def mark_lesson_complete(
    student_id: int,
    lesson_id: int,
) -> float:
    """
    Mark a lesson as completed for a student.

    After marking the lesson complete, the student's course
    progress is recalculated.

    Returns:
        float: Updated course progress percentage.

    Raises:
        ValueError: If the lesson does not exist.
    """

    if not student_id:
        raise ValueError("Student ID is required.")

    if not lesson_id:
        raise ValueError("Lesson ID is required.")

    # --------------------------------------------------------
    # Find lesson
    # --------------------------------------------------------

    lesson = db.session.get(
        Lesson,
        lesson_id,
    )

    if lesson is None:
        raise ValueError("Lesson not found.")

    # --------------------------------------------------------
    # Find existing progress record
    # --------------------------------------------------------

    record = (
        LessonProgress.query
        .filter_by(
            StudentID=student_id,
            LessonID=lesson_id,
        )
        .first()
    )

    now = datetime.now(timezone.utc)

    try:

        if record is None:

            record = LessonProgress(
                StudentID=student_id,
                LessonID=lesson_id,
                Completed=True,
                CompletedAt=now,
            )

            db.session.add(record)

        else:

            record.Completed = True
            record.CompletedAt = now

        db.session.commit()

    except Exception as exc:

        db.session.rollback()

        raise ValueError(
            "Unable to update lesson progress."
        ) from exc

    # --------------------------------------------------------
    # Recalculate course progress
    # --------------------------------------------------------

    course_id = lesson.module.CourseID

    return recalculate_course_progress(
        student_id,
        course_id,
    )


# ============================================================
# RECALCULATE COURSE PROGRESS
# ============================================================

def recalculate_course_progress(
    student_id: int,
    course_id: int,
) -> float:
    """
    Recalculate and persist the student's progress percentage
    for a course.

    Progress is calculated from completed lessons.

    When progress reaches 100%, the enrollment is automatically
    marked as Completed.
    """

    if not student_id or not course_id:
        return 0.0

    # Local import prevents circular import during application
    # initialization.
    from database.models import Course

    course = db.session.get(
        Course,
        course_id,
    )

    if course is None:
        return 0.0

    # --------------------------------------------------------
    # Get course lessons
    # --------------------------------------------------------

    lesson_ids = [
        lesson.LessonID
        for module in course.modules
        for lesson in module.lessons
    ]

    total_lessons = len(lesson_ids)

    # --------------------------------------------------------
    # Calculate percentage
    # --------------------------------------------------------

    if total_lessons == 0:

        percentage = 0.0

    else:

        completed_count = (
            LessonProgress.query
            .filter(
                LessonProgress.StudentID == student_id,
                LessonProgress.LessonID.in_(lesson_ids),
                LessonProgress.Completed.is_(True),
            )
            .count()
        )

        percentage = calculate_percentage(
            completed_count,
            total_lessons,
        )

    # --------------------------------------------------------
    # Update enrollment
    # --------------------------------------------------------

    enrollment = (
        Enrollment.query
        .filter_by(
            StudentID=student_id,
            CourseID=course_id,
        )
        .first()
    )

    if enrollment:

        enrollment.ProgressPercentage = percentage

        if (
            percentage >= 100
            and enrollment.Status != "Completed"
        ):

            enrollment.Status = "Completed"

            enrollment.CompletionDate = (
                datetime.now(timezone.utc)
            )

        try:

            db.session.commit()

        except Exception as exc:

            db.session.rollback()

            raise ValueError(
                "Unable to update course progress."
            ) from exc

    return percentage


# ============================================================
# GET COMPLETED LESSON IDS
# ============================================================

def get_completed_lesson_ids(
    student_id: int,
    lesson_ids: list,
) -> set:
    """
    Return the IDs of lessons completed by a student.

    Returns:
        set[int]: Completed lesson IDs.
    """

    if not student_id or not lesson_ids:
        return set()

    records = (
        LessonProgress.query
        .filter(
            LessonProgress.StudentID == student_id,
            LessonProgress.LessonID.in_(lesson_ids),
            LessonProgress.Completed.is_(True),
        )
        .all()
    )

    return {
        record.LessonID
        for record in records
    }


# ============================================================
# GET MODULE PROGRESS
# ============================================================

def get_module_progress(
    student_id: int,
    module: Module,
) -> dict:
    """
    Calculate progress for a single course module.

    Returns:

        {
            "total": int,
            "completed": int,
            "percentage": float
        }
    """

    if not student_id or module is None:

        return {
            "total": 0,
            "completed": 0,
            "percentage": 0.0,
        }

    lesson_ids = [
        lesson.LessonID
        for lesson in module.lessons
    ]

    completed_ids = get_completed_lesson_ids(
        student_id,
        lesson_ids,
    )

    total = len(lesson_ids)

    completed = len(completed_ids)

    percentage = calculate_percentage(
        completed,
        total,
    )

    return {
        "total": total,
        "completed": completed,
        "percentage": percentage,
    }