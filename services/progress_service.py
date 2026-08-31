"""
Lesson/course progress tracking business logic.
"""

from datetime import datetime, timezone
from database.database import db
from database.models import LessonProgress, Lesson, Module, Enrollment
from utils.helpers import calculate_percentage


def mark_lesson_complete(student_id: int, lesson_id: int):
    lesson = Lesson.query.get(lesson_id)
    if not lesson:
        raise ValueError("Lesson not found.")

    record = LessonProgress.query.filter_by(StudentID=student_id, LessonID=lesson_id).first()
    if not record:
        record = LessonProgress(StudentID=student_id, LessonID=lesson_id, Completed=True,
                                 CompletedAt=datetime.now(timezone.utc))
        db.session.add(record)
    else:
        record.Completed = True
        record.CompletedAt = datetime.now(timezone.utc)

    db.session.commit()

    course_id = lesson.module.CourseID
    new_progress = recalculate_course_progress(student_id, course_id)
    return new_progress


def recalculate_course_progress(student_id: int, course_id: int) -> float:
    """Recompute and persist a student's progress percentage for a course."""
    from database.models import Course  # local import to avoid cycle at module load

    course = Course.query.get(course_id)
    if not course:
        return 0.0

    total_lessons = course.total_lessons
    if total_lessons == 0:
        percentage = 0.0
    else:
        lesson_ids = [lesson.LessonID for module in course.modules for lesson in module.lessons]
        completed_count = LessonProgress.query.filter(
            LessonProgress.StudentID == student_id,
            LessonProgress.LessonID.in_(lesson_ids),
            LessonProgress.Completed.is_(True),
        ).count()
        percentage = calculate_percentage(completed_count, total_lessons)

    enrollment = Enrollment.query.filter_by(StudentID=student_id, CourseID=course_id).first()
    if enrollment:
        enrollment.ProgressPercentage = percentage
        if percentage >= 100 and enrollment.Status != "Completed":
            enrollment.Status = "Completed"
            enrollment.CompletionDate = datetime.now(timezone.utc)
        db.session.commit()

    return percentage


def get_completed_lesson_ids(student_id: int, lesson_ids: list) -> set:
    if not lesson_ids:
        return set()
    records = LessonProgress.query.filter(
        LessonProgress.StudentID == student_id,
        LessonProgress.LessonID.in_(lesson_ids),
        LessonProgress.Completed.is_(True),
    ).all()
    return {r.LessonID for r in records}


def get_module_progress(student_id: int, module: Module) -> dict:
    lesson_ids = [lesson.LessonID for lesson in module.lessons]
    completed_ids = get_completed_lesson_ids(student_id, lesson_ids)
    total = len(lesson_ids)
    completed = len(completed_ids)
    return {
        "total": total,
        "completed": completed,
        "percentage": calculate_percentage(completed, total),
    }
