"""
EduCertify — Course Authoring Service

Business logic for instructors:

- Course creation
- Course updates
- Course ownership
- Course submission for review
- Module creation
- Lesson creation
- Quiz creation
- Question creation
- Instructor course listing

Ownership checks are enforced inside this service so that
instructor permissions cannot be bypassed by manipulating
routes or request parameters.
"""

from database.database import db
from database.models import (
    Course,
    Module,
    Lesson,
    Quiz,
    Question,
    Category,
)

from utils.helpers import (
    slugify,
    unique_slug,
)


# ============================================================
# CUSTOM EXCEPTIONS
# ============================================================

class CourseError(Exception):
    """
    Raised when a course authoring operation fails.
    """

    pass


class OwnershipError(CourseError):
    """
    Raised when an instructor attempts to modify
    another instructor's resource.
    """

    pass


# ============================================================
# INTERNAL HELPERS
# ============================================================

def _slug_exists(
    slug: str,
    exclude_course_id: int | None = None,
) -> bool:
    """
    Check whether a course slug already exists.
    """

    query = (
        Course.query
        .filter_by(
            Slug=slug
        )
    )

    if exclude_course_id is not None:

        query = query.filter(
            Course.CourseID
            != exclude_course_id
        )

    return (
        query.first()
        is not None
    )


def _get_course(
    course_id: int,
) -> Course:
    """
    Get a course or raise CourseError.
    """

    course = db.session.get(
        Course,
        course_id,
    )

    if course is None:

        raise CourseError(
            "Course not found."
        )

    return course


def _validate_course_values(
    level=None,
    price=None,
    passing_score=None,
):
    """
    Validate common course values.
    """

    allowed_levels = {
        "Beginner",
        "Intermediate",
        "Advanced",
    }

    if level is not None:

        level = str(level).strip()

        if level not in allowed_levels:

            raise CourseError(
                "Invalid course level."
            )

    if price is not None:

        try:
            price = float(price)
        except (
            TypeError,
            ValueError,
        ):

            raise CourseError(
                "Course price must be a valid number."
            )

        if price < 0:

            raise CourseError(
                "Course price cannot be negative."
            )

    if passing_score is not None:

        try:
            passing_score = float(
                passing_score
            )
        except (
            TypeError,
            ValueError,
        ):

            raise CourseError(
                "Passing score must be a valid number."
            )

        if not 0 <= passing_score <= 100:

            raise CourseError(
                "Passing score must be between 0 and 100."
            )


def _get_owned_module(
    module_id: int,
    instructor_id: int,
) -> Module:
    """
    Retrieve a module and verify that its course
    belongs to the specified instructor.
    """

    module = db.session.get(
        Module,
        module_id,
    )

    if module is None:

        raise CourseError(
            "Module not found."
        )

    if (
        not module.course
        or module.course.InstructorID
        != instructor_id
    ):

        raise OwnershipError(
            "You do not have permission "
            "to modify this module."
        )

    return module


def _get_owned_quiz(
    quiz_id: int,
    instructor_id: int,
) -> Quiz:
    """
    Retrieve a quiz and verify ownership
    through its course.
    """

    quiz = db.session.get(
        Quiz,
        quiz_id,
    )

    if quiz is None:

        raise CourseError(
            "Quiz not found."
        )

    if (
        not quiz.course
        or quiz.course.InstructorID
        != instructor_id
    ):

        raise OwnershipError(
            "You do not have permission "
            "to modify this quiz."
        )

    return quiz


# ============================================================
# CREATE COURSE
# ============================================================

def create_course(
    instructor_id: int,
    title: str,
    category_id: int,
    **kwargs,
) -> Course:
    """
    Create a new instructor course.

    New courses start in Draft status.
    """

    title = (
        title or ""
    ).strip()

    if not title:

        raise CourseError(
            "Course title is required."
        )

    if len(title) > 200:

        raise CourseError(
            "Course title must not exceed 200 characters."
        )

    if not instructor_id:

        raise CourseError(
            "Instructor ID is required."
        )

    if not category_id:

        raise CourseError(
            "Course category is required."
        )

    # --------------------------------------------------------
    # Verify category
    # --------------------------------------------------------

    category = db.session.get(
        Category,
        category_id,
    )

    if category is None:

        raise CourseError(
            "Selected category does not exist."
        )

    if not category.IsActive:

        raise CourseError(
            "Selected category is not active."
        )

    # --------------------------------------------------------
    # Validate course values
    # --------------------------------------------------------

    level = (
        kwargs.get(
            "level",
            "Beginner",
        )
        or "Beginner"
    ).strip()

    price = kwargs.get(
        "price",
        0.0,
    )

    passing_score = kwargs.get(
        "passing_score",
        70,
    )

    _validate_course_values(
        level=level,
        price=price,
        passing_score=passing_score,
    )

    # --------------------------------------------------------
    # Generate unique slug
    # --------------------------------------------------------

    base_slug = slugify(
        title
    )

    if not base_slug:

        raise CourseError(
            "Unable to generate a valid course URL."
        )

    slug = unique_slug(
        base_slug,
        lambda value:
            _slug_exists(value),
    )

    # --------------------------------------------------------
    # Create course
    # --------------------------------------------------------

    course = Course(
        InstructorID=instructor_id,
        CategoryID=category_id,
        Title=title,
        Slug=slug,
        ShortDescription=(
            kwargs.get(
                "short_description",
                "",
            )
            or ""
        ).strip(),
        Description=(
            kwargs.get(
                "description",
                "",
            )
            or ""
        ).strip(),
        Level=level,
        Duration=(
            kwargs.get(
                "duration",
                "",
            )
            or ""
        ).strip(),
        Price=float(price),
        PassingScore=float(
            passing_score
        ),
        Status="Draft",
    )

    try:

        db.session.add(
            course
        )

        db.session.commit()

        db.session.refresh(
            course
        )

        return course

    except Exception as exc:

        db.session.rollback()

        raise CourseError(
            "Unable to create the course."
        ) from exc


# ============================================================
# GET OWNED COURSE
# ============================================================

def get_owned_course(
    course_id: int,
    instructor_id: int,
) -> Course:
    """
    Retrieve a course and verify instructor ownership.
    """

    course = _get_course(
        course_id
    )

    if (
        course.InstructorID
        != instructor_id
    ):

        raise OwnershipError(
            "You do not have permission "
            "to modify this course."
        )

    return course


# ============================================================
# UPDATE COURSE
# ============================================================

def update_course(
    course_id: int,
    instructor_id: int,
    **kwargs,
) -> Course:
    """
    Update an instructor-owned course.
    """

    course = get_owned_course(
        course_id,
        instructor_id,
    )

    # --------------------------------------------------------
    # Title
    # --------------------------------------------------------

    if "title" in kwargs:

        new_title = (
            kwargs.get("title")
            or ""
        ).strip()

        if not new_title:

            raise CourseError(
                "Course title cannot be empty."
            )

        if len(new_title) > 200:

            raise CourseError(
                "Course title must not exceed 200 characters."
            )

        if new_title != course.Title:

            course.Title = new_title

            base_slug = slugify(
                new_title
            )

            if not base_slug:

                raise CourseError(
                    "Unable to generate a valid course URL."
                )

            course.Slug = unique_slug(
                base_slug,
                lambda value:
                    _slug_exists(
                        value,
                        exclude_course_id=course.CourseID,
                    ),
            )

    # --------------------------------------------------------
    # Validate values
    # --------------------------------------------------------

    level = kwargs.get(
        "level"
    )

    price = kwargs.get(
        "price"
    )

    passing_score = kwargs.get(
        "passing_score"
    )

    _validate_course_values(
        level=level,
        price=price,
        passing_score=passing_score,
    )

    # --------------------------------------------------------
    # Field mapping
    # --------------------------------------------------------

    field_map = {
        "short_description":
            "ShortDescription",

        "description":
            "Description",

        "level":
            "Level",

        "duration":
            "Duration",

        "price":
            "Price",

        "passing_score":
            "PassingScore",

        "category_id":
            "CategoryID",
    }

    for field, attribute in field_map.items():

        if (
            field not in kwargs
            or kwargs[field] is None
        ):
            continue

        value = kwargs[field]

        # ----------------------------------------------------
        # Category validation
        # ----------------------------------------------------

        if field == "category_id":

            category = db.session.get(
                Category,
                value,
            )

            if category is None:

                raise CourseError(
                    "Selected category does not exist."
                )

            if not category.IsActive:

                raise CourseError(
                    "Selected category is not active."
                )

        # ----------------------------------------------------
        # Normalize strings
        # ----------------------------------------------------

        if field in {
            "short_description",
            "description",
            "duration",
        }:

            value = (
                str(value)
                .strip()
            )

        # ----------------------------------------------------
        # Numeric values
        # ----------------------------------------------------

        elif field == "price":

            value = float(value)

        elif field == "passing_score":

            value = float(value)

        setattr(
            course,
            attribute,
            value,
        )

    try:

        db.session.commit()

        db.session.refresh(
            course
        )

        return course

    except Exception as exc:

        db.session.rollback()

        raise CourseError(
            "Unable to update the course."
        ) from exc


# ============================================================
# SUBMIT COURSE FOR REVIEW
# ============================================================

def submit_for_review(
    course_id: int,
    instructor_id: int,
) -> Course:
    """
    Submit an owned course for administrator review.
    """

    course = get_owned_course(
        course_id,
        instructor_id,
    )

    # --------------------------------------------------------
    # Course must have modules
    # --------------------------------------------------------

    if not course.modules:

        raise CourseError(
            "Add at least one module "
            "before submitting for review."
        )

    # --------------------------------------------------------
    # Every module should contain a lesson
    # --------------------------------------------------------

    empty_modules = [
        module
        for module in course.modules
        if not module.lessons
    ]

    if empty_modules:

        raise CourseError(
            "Every module must contain "
            "at least one lesson."
        )

    # --------------------------------------------------------
    # Prevent unnecessary resubmission
    # --------------------------------------------------------

    if course.Status == "Pending":

        raise CourseError(
            "This course is already pending review."
        )

    if course.Status == "Published":

        raise CourseError(
            "This course has already been published."
        )

    course.Status = "Pending"

    # Clear an old rejection reason when
    # the instructor resubmits.
    if hasattr(
        course,
        "RejectionReason",
    ):

        course.RejectionReason = None

    try:

        db.session.commit()

        return course

    except Exception as exc:

        db.session.rollback()

        raise CourseError(
            "Unable to submit the course for review."
        ) from exc


# ============================================================
# ADD MODULE
# ============================================================

def add_module(
    course_id: int,
    instructor_id: int,
    title: str,
    description: str = "",
) -> Module:
    """
    Add a module to an instructor-owned course.
    """

    course = get_owned_course(
        course_id,
        instructor_id,
    )

    title = (
        title or ""
    ).strip()

    description = (
        description or ""
    ).strip()

    if not title:

        raise CourseError(
            "Module title is required."
        )

    if len(title) > 200:

        raise CourseError(
            "Module title must not exceed 200 characters."
        )

    max_order = max(
        (
            module.DisplayOrder
            for module in course.modules
            if module.DisplayOrder is not None
        ),
        default=0,
    )

    module = Module(
        CourseID=course.CourseID,
        Title=title,
        Description=description,
        DisplayOrder=max_order + 1,
    )

    try:

        db.session.add(
            module
        )

        db.session.commit()

        db.session.refresh(
            module
        )

        return module

    except Exception as exc:

        db.session.rollback()

        raise CourseError(
            "Unable to create the module."
        ) from exc


# ============================================================
# ADD LESSON
# ============================================================

def add_lesson(
    module_id: int,
    instructor_id: int,
    title: str,
    **kwargs,
) -> Lesson:
    """
    Add a lesson to an instructor-owned module.
    """

    module = _get_owned_module(
        module_id,
        instructor_id,
    )

    title = (
        title or ""
    ).strip()

    if not title:

        raise CourseError(
            "Lesson title is required."
        )

    if len(title) > 200:

        raise CourseError(
            "Lesson title must not exceed 200 characters."
        )

    max_order = max(
        (
            lesson.DisplayOrder
            for lesson in module.lessons
            if lesson.DisplayOrder is not None
        ),
        default=0,
    )

    lesson = Lesson(
        ModuleID=module.ModuleID,
        Title=title,
        Description=(
            kwargs.get(
                "description",
                "",
            )
            or ""
        ).strip(),
        Content=(
            kwargs.get(
                "content",
                "",
            )
            or ""
        ),
        VideoURL=(
            kwargs.get(
                "video_url",
                "",
            )
            or ""
        ).strip(),
        ResourceURL=(
            kwargs.get(
                "resource_url",
                "",
            )
            or ""
        ).strip(),
        Duration=(
            kwargs.get(
                "duration",
                "",
            )
            or ""
        ).strip(),
        IsPreview=bool(
            kwargs.get(
                "is_preview",
                False,
            )
        ),
        DisplayOrder=max_order + 1,
    )

    try:

        db.session.add(
            lesson
        )

        db.session.commit()

        db.session.refresh(
            lesson
        )

        return lesson

    except Exception as exc:

        db.session.rollback()

        raise CourseError(
            "Unable to create the lesson."
        ) from exc


# ============================================================
# ADD QUIZ
# ============================================================

def add_quiz(
    course_id: int,
    instructor_id: int,
    title: str,
    **kwargs,
) -> Quiz:
    """
    Add a quiz to an instructor-owned course.
    """

    course = get_owned_course(
        course_id,
        instructor_id,
    )

    title = (
        title or ""
    ).strip()

    if not title:

        raise CourseError(
            "Quiz title is required."
        )

    if len(title) > 200:

        raise CourseError(
            "Quiz title must not exceed 200 characters."
        )

    # --------------------------------------------------------
    # Optional module
    # --------------------------------------------------------

    module_id = kwargs.get(
        "module_id"
    )

    if module_id is not None:

        module = db.session.get(
            Module,
            module_id,
        )

        if module is None:

            raise CourseError(
                "Selected module was not found."
            )

        if module.CourseID != course.CourseID:

            raise CourseError(
                "The selected module does not belong "
                "to this course."
            )

    # --------------------------------------------------------
    # Quiz configuration
    # --------------------------------------------------------

    passing_score = kwargs.get(
        "passing_score",
        70,
    )

    try:

        passing_score = float(
            passing_score
        )

    except (
        TypeError,
        ValueError,
    ):

        raise CourseError(
            "Quiz passing score must be a valid number."
        )

    if not 0 <= passing_score <= 100:

        raise CourseError(
            "Quiz passing score must be between 0 and 100."
        )

    attempts_allowed = kwargs.get(
        "attempts_allowed",
        3,
    )

    try:

        attempts_allowed = int(
            attempts_allowed
        )

    except (
        TypeError,
        ValueError,
    ):

        raise CourseError(
            "Attempts allowed must be a valid number."
        )

    if attempts_allowed < 1:

        raise CourseError(
            "At least one quiz attempt must be allowed."
        )

    time_limit = kwargs.get(
        "time_limit"
    )

    if time_limit is not None:

        try:

            time_limit = int(
                time_limit
            )

        except (
            TypeError,
            ValueError,
        ):

            raise CourseError(
                "Time limit must be a valid number."
            )

        if time_limit < 1:

            raise CourseError(
                "Time limit must be greater than zero."
            )

    quiz = Quiz(
        CourseID=course.CourseID,
        ModuleID=module_id,
        Title=title,
        Description=(
            kwargs.get(
                "description",
                "",
            )
            or ""
        ).strip(),
        PassingScore=passing_score,
        TimeLimit=time_limit,
        AttemptsAllowed=attempts_allowed,
        IsFinalAssessment=bool(
            kwargs.get(
                "is_final_assessment",
                False,
            )
        ),
    )

    try:

        db.session.add(
            quiz
        )

        db.session.commit()

        db.session.refresh(
            quiz
        )

        return quiz

    except Exception as exc:

        db.session.rollback()

        raise CourseError(
            "Unable to create the quiz."
        ) from exc


# ============================================================
# ADD QUESTION
# ============================================================

def add_question(
    quiz_id: int,
    instructor_id: int,
    **kwargs,
) -> Question:
    """
    Add a multiple-choice question to an
    instructor-owned quiz.
    """

    quiz = _get_owned_quiz(
        quiz_id,
        instructor_id,
    )

    required_fields = [
        "question_text",
        "option_a",
        "option_b",
        "option_c",
        "option_d",
        "correct_option",
    ]

    # --------------------------------------------------------
    # Validate required fields
    # --------------------------------------------------------

    for field in required_fields:

        value = kwargs.get(
            field
        )

        if (
            value is None
            or not str(value).strip()
        ):

            raise CourseError(
                "All question fields are required."
            )

    # --------------------------------------------------------
    # Correct option
    # --------------------------------------------------------

    correct_option = (
        str(
            kwargs["correct_option"]
        )
        .strip()
        .upper()
    )

    if correct_option not in {
        "A",
        "B",
        "C",
        "D",
    }:

        raise CourseError(
            "Correct option must be A, B, C, or D."
        )

    # --------------------------------------------------------
    # Marks
    # --------------------------------------------------------

    marks = kwargs.get(
        "marks",
        1,
    )

    try:

        marks = float(
            marks
        )

    except (
        TypeError,
        ValueError,
    ):

        raise CourseError(
            "Question marks must be a valid number."
        )

    if marks <= 0:

        raise CourseError(
            "Question marks must be greater than zero."
        )

    # --------------------------------------------------------
    # Create question
    # --------------------------------------------------------

    question = Question(
        QuizID=quiz.QuizID,
        QuestionText=str(
            kwargs["question_text"]
        ).strip(),
        OptionA=str(
            kwargs["option_a"]
        ).strip(),
        OptionB=str(
            kwargs["option_b"]
        ).strip(),
        OptionC=str(
            kwargs["option_c"]
        ).strip(),
        OptionD=str(
            kwargs["option_d"]
        ).strip(),
        CorrectOption=correct_option,
        Marks=marks,
    )

    try:

        db.session.add(
            question
        )

        db.session.commit()

        db.session.refresh(
            question
        )

        return question

    except Exception as exc:

        db.session.rollback()

        raise CourseError(
            "Unable to create the question."
        ) from exc


# ============================================================
# GET INSTRUCTOR COURSES
# ============================================================

def get_instructor_courses(
    instructor_id: int,
):
    """
    Return all courses belonging to an instructor.
    """

    return (
        Course.query
        .filter_by(
            InstructorID=instructor_id
        )
        .order_by(
            Course.CreatedAt.desc()
        )
        .all()
    )