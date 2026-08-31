"""
EduCertify — Enrollment Service

Business logic for student course enrollment.

Responsibilities:
- Validate course availability
- Prevent duplicate enrollments
- Create student enrollments
- Retrieve individual enrollments
- Retrieve a student's enrollment history
- Safely handle database failures

Routes should call this service instead of directly
modifying Enrollment records.
"""

from database.database import db
from database.models import Enrollment, Course

from services.progress_service import (
    recalculate_course_progress,
)


# ============================================================
# CUSTOM EXCEPTION
# ============================================================

class EnrollmentError(Exception):
    """
    Raised when an enrollment operation fails.
    """

    pass


# ============================================================
# ENROLL STUDENT
# ============================================================

def enroll_student(
    student_id: int,
    course_id: int,
) -> Enrollment:
    """
    Enroll a student in a published course.

    Raises:
        EnrollmentError:
            If the course does not exist,
            is not published, or the student
            is already enrolled.
    """

    if not student_id:

        raise EnrollmentError(
            "Student ID is required."
        )

    if not course_id:

        raise EnrollmentError(
            "Course ID is required."
        )

    # --------------------------------------------------------
    # Find course
    # --------------------------------------------------------

    course = db.session.get(
        Course,
        course_id,
    )

    if course is None:

        raise EnrollmentError(
            "Course not found."
        )

    # --------------------------------------------------------
    # Course availability
    # --------------------------------------------------------

    if course.Status != "Published":

        raise EnrollmentError(
            "This course is not available for enrollment."
        )

    # --------------------------------------------------------
    # Prevent duplicate enrollment
    # --------------------------------------------------------

    existing = (
        Enrollment.query
        .filter_by(
            StudentID=student_id,
            CourseID=course_id,
        )
        .first()
    )

    if existing:

        # If the student already has an active/completed
        # enrollment, don't create another record.
        raise EnrollmentError(
            "You are already enrolled in this course."
        )

    # --------------------------------------------------------
    # Create enrollment
    # --------------------------------------------------------

    enrollment = Enrollment(
        StudentID=student_id,
        CourseID=course_id,
        ProgressPercentage=0.0,
        Status="Active",
    )

    try:

        db.session.add(
            enrollment
        )

        db.session.commit()

        db.session.refresh(
            enrollment
        )

        return enrollment

    except Exception as exc:

        db.session.rollback()

        raise EnrollmentError(
            "Unable to enroll in this course. "
            "Please try again."
        ) from exc


# ============================================================
# GET SINGLE ENROLLMENT
# ============================================================

def get_enrollment(
    student_id: int,
    course_id: int,
):
    """
    Return a student's enrollment for a specific course.

    Returns:
        Enrollment | None
    """

    if not student_id or not course_id:

        return None

    return (
        Enrollment.query
        .filter_by(
            StudentID=student_id,
            CourseID=course_id,
        )
        .first()
    )


# ============================================================
# GET STUDENT ENROLLMENTS
# ============================================================

def get_student_enrollments(
    student_id: int,
    status: str = None,
):
    """
    Return all enrollments belonging to a student.

    Optional status filtering is supported.

    Example:

        get_student_enrollments(
            student_id=10,
            status="Active",
        )
    """

    if not student_id:

        return []

    query = (
        Enrollment.query
        .filter_by(
            StudentID=student_id
        )
    )

    # --------------------------------------------------------
    # Optional status filter
    # --------------------------------------------------------

    if status:

        status = (
            str(status)
            .strip()
        )

        allowed_statuses = {
            "Active",
            "Completed",
            "Cancelled",
            "Dropped",
        }

        if status not in allowed_statuses:

            raise EnrollmentError(
                "Invalid enrollment status."
            )

        query = query.filter_by(
            Status=status
        )

    # --------------------------------------------------------
    # Latest enrollment first
    # --------------------------------------------------------

    return (
        query
        .order_by(
            Enrollment.EnrollmentDate.desc()
        )
        .all()
    )