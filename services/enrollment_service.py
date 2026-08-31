"""
Enrollment business logic.
"""

from database.database import db
from database.models import Enrollment, Course
from services.progress_service import recalculate_course_progress


class EnrollmentError(Exception):
    pass


def enroll_student(student_id: int, course_id: int) -> Enrollment:
    course = Course.query.get(course_id)
    if not course or course.Status != "Published":
        raise EnrollmentError("This course is not available for enrollment.")

    existing = Enrollment.query.filter_by(StudentID=student_id, CourseID=course_id).first()
    if existing:
        raise EnrollmentError("You are already enrolled in this course.")

    enrollment = Enrollment(StudentID=student_id, CourseID=course_id, ProgressPercentage=0.0, Status="Active")
    db.session.add(enrollment)
    db.session.commit()
    return enrollment


def get_enrollment(student_id: int, course_id: int):
    return Enrollment.query.filter_by(StudentID=student_id, CourseID=course_id).first()


def get_student_enrollments(student_id: int, status: str = None):
    query = Enrollment.query.filter_by(StudentID=student_id)
    if status:
        query = query.filter_by(Status=status)
    return query.order_by(Enrollment.EnrollmentDate.desc()).all()
