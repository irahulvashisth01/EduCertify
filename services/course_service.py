"""
Course/module/lesson/quiz authoring logic for instructors.
Ownership checks (instructor can only touch their own courses) are
enforced here, not just in routes, so the rule can't be bypassed.
"""

from database.database import db
from database.models import Course, Module, Lesson, Quiz, Question
from utils.helpers import slugify, unique_slug


class CourseError(Exception):
    pass


class OwnershipError(CourseError):
    pass


def _slug_exists(slug, exclude_course_id=None):
    query = Course.query.filter_by(Slug=slug)
    if exclude_course_id:
        query = query.filter(Course.CourseID != exclude_course_id)
    return query.first() is not None


def create_course(instructor_id: int, title: str, category_id: int, **kwargs) -> Course:
    if not title or not title.strip():
        raise CourseError("Course title is required.")

    base_slug = slugify(title)
    slug = unique_slug(base_slug, lambda s: _slug_exists(s))

    course = Course(
        InstructorID=instructor_id,
        CategoryID=category_id,
        Title=title.strip(),
        Slug=slug,
        ShortDescription=kwargs.get("short_description", ""),
        Description=kwargs.get("description", ""),
        Level=kwargs.get("level", "Beginner"),
        Duration=kwargs.get("duration", ""),
        Price=kwargs.get("price", 0.0),
        PassingScore=kwargs.get("passing_score", 70),
        Status="Draft",
    )
    db.session.add(course)
    db.session.commit()
    return course


def get_owned_course(course_id: int, instructor_id: int) -> Course:
    course = Course.query.get(course_id)
    if not course:
        raise CourseError("Course not found.")
    if course.InstructorID != instructor_id:
        raise OwnershipError("You do not have permission to modify this course.")
    return course


def update_course(course_id: int, instructor_id: int, **kwargs) -> Course:
    course = get_owned_course(course_id, instructor_id)

    if "title" in kwargs and kwargs["title"].strip() and kwargs["title"] != course.Title:
        course.Title = kwargs["title"].strip()
        base_slug = slugify(course.Title)
        course.Slug = unique_slug(base_slug, lambda s: _slug_exists(s, exclude_course_id=course.CourseID))

    for field in ("short_description", "description", "level", "duration", "price", "passing_score", "category_id"):
        if field in kwargs and kwargs[field] is not None:
            attr_map = {
                "short_description": "ShortDescription",
                "description": "Description",
                "level": "Level",
                "duration": "Duration",
                "price": "Price",
                "passing_score": "PassingScore",
                "category_id": "CategoryID",
            }
            setattr(course, attr_map[field], kwargs[field])

    db.session.commit()
    return course


def submit_for_review(course_id: int, instructor_id: int) -> Course:
    course = get_owned_course(course_id, instructor_id)
    if not course.modules:
        raise CourseError("Add at least one module before submitting for review.")
    course.Status = "Pending"
    db.session.commit()
    return course


def add_module(course_id: int, instructor_id: int, title: str, description: str = "") -> Module:
    course = get_owned_course(course_id, instructor_id)
    if not title or not title.strip():
        raise CourseError("Module title is required.")

    max_order = max([m.DisplayOrder for m in course.modules], default=0)
    module = Module(CourseID=course.CourseID, Title=title.strip(), Description=description, DisplayOrder=max_order + 1)
    db.session.add(module)
    db.session.commit()
    return module


def add_lesson(module_id: int, instructor_id: int, title: str, **kwargs) -> Lesson:
    module = Module.query.get(module_id)
    if not module:
        raise CourseError("Module not found.")
    if module.course.InstructorID != instructor_id:
        raise OwnershipError("You do not have permission to modify this module.")
    if not title or not title.strip():
        raise CourseError("Lesson title is required.")

    max_order = max([l.DisplayOrder for l in module.lessons], default=0)
    lesson = Lesson(
        ModuleID=module_id,
        Title=title.strip(),
        Description=kwargs.get("description", ""),
        Content=kwargs.get("content", ""),
        VideoURL=kwargs.get("video_url", ""),
        ResourceURL=kwargs.get("resource_url", ""),
        Duration=kwargs.get("duration", ""),
        IsPreview=kwargs.get("is_preview", False),
        DisplayOrder=max_order + 1,
    )
    db.session.add(lesson)
    db.session.commit()
    return lesson


def add_quiz(course_id: int, instructor_id: int, title: str, **kwargs) -> Quiz:
    course = get_owned_course(course_id, instructor_id)
    if not title or not title.strip():
        raise CourseError("Quiz title is required.")

    quiz = Quiz(
        CourseID=course_id,
        ModuleID=kwargs.get("module_id"),
        Title=title.strip(),
        Description=kwargs.get("description", ""),
        PassingScore=kwargs.get("passing_score", 70),
        TimeLimit=kwargs.get("time_limit"),
        AttemptsAllowed=kwargs.get("attempts_allowed", 3),
        IsFinalAssessment=kwargs.get("is_final_assessment", False),
    )
    db.session.add(quiz)
    db.session.commit()
    return quiz


def add_question(quiz_id: int, instructor_id: int, **kwargs) -> Question:
    quiz = Quiz.query.get(quiz_id)
    if not quiz:
        raise CourseError("Quiz not found.")
    if quiz.course.InstructorID != instructor_id:
        raise OwnershipError("You do not have permission to modify this quiz.")

    required = ["question_text", "option_a", "option_b", "option_c", "option_d", "correct_option"]
    for field in required:
        if not kwargs.get(field):
            raise CourseError("All question fields are required.")

    if kwargs["correct_option"].upper() not in ("A", "B", "C", "D"):
        raise CourseError("Correct option must be A, B, C, or D.")

    question = Question(
        QuizID=quiz_id,
        QuestionText=kwargs["question_text"],
        OptionA=kwargs["option_a"],
        OptionB=kwargs["option_b"],
        OptionC=kwargs["option_c"],
        OptionD=kwargs["option_d"],
        CorrectOption=kwargs["correct_option"].upper(),
        Marks=kwargs.get("marks", 1),
    )
    db.session.add(question)
    db.session.commit()
    return question


def get_instructor_courses(instructor_id: int):
    return Course.query.filter_by(InstructorID=instructor_id).order_by(Course.CreatedAt.desc()).all()
