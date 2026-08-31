"""
Seed script — populates the database with demo data so dashboards and
course pages have something to show immediately after setup.

Usage (PowerShell or bash, from the project root, with the venv active):
    python -m database.seed

Safe to re-run: it checks for existing records before inserting.
"""

from app import create_app
from database.database import db
from database.models import (
    User, Category, Course, Module, Lesson, Quiz, Question, Enrollment
)
from utils.security import hash_password
from utils.helpers import slugify


def get_or_create_user(full_name, email, password, role):
    user = User.query.filter_by(Email=email).first()
    if user:
        return user
    user = User(
        FullName=full_name,
        Email=email,
        PasswordHash=hash_password(password),
        Role=role,
        IsActive=True,
    )
    db.session.add(user)
    db.session.commit()
    return user


def get_or_create_category(name, description=""):
    category = Category.query.filter_by(Name=name).first()
    if category:
        return category
    category = Category(Name=name, Description=description, IsActive=True)
    db.session.add(category)
    db.session.commit()
    return category


def get_or_create_course(instructor, category, title, **kwargs):
    course = Course.query.filter_by(Title=title, InstructorID=instructor.UserID).first()
    if course:
        return course
    course = Course(
        InstructorID=instructor.UserID,
        CategoryID=category.CategoryID,
        Title=title,
        Slug=slugify(title),
        Status="Published",
        **kwargs,
    )
    db.session.add(course)
    db.session.commit()
    return course


def seed():
    app = create_app()
    with app.app_context():
        print("Seeding EduCertify demo data...")

        # ---------------- Users ----------------
        admin = get_or_create_user("Platform Admin", "admin@example.com", "Admin@12345", "Admin")
        instructor = get_or_create_user("Rahul Sharma", "instructor@example.com", "Instructor@123", "Instructor")
        student = get_or_create_user("Aisha Khan", "student@example.com", "Student@123", "Student")
        print(f"  Users: {admin.Email}, {instructor.Email}, {student.Email}")

        # ---------------- Categories ----------------
        category_names = [
            "Web Development", "Python", "Java", "Database Management",
            "Data Science", "Artificial Intelligence", "Cloud Computing", "Cyber Security",
        ]
        categories = {name: get_or_create_category(name) for name in category_names}
        print(f"  Categories: {len(categories)} created/verified")

        # ---------------- Courses ----------------
        html_css = get_or_create_course(
            instructor, categories["Web Development"], "Complete HTML & CSS",
            ShortDescription="Build responsive websites from scratch with HTML5 and CSS3.",
            Description="A hands-on course covering semantic HTML, modern CSS layout with Flexbox and Grid, "
                         "responsive design, and best practices for building real-world web pages.",
            Level="Beginner", Duration="8 hours", Price=0.0, PassingScore=70,
        )

        js_fundamentals = get_or_create_course(
            instructor, categories["Web Development"], "JavaScript Fundamentals",
            ShortDescription="Learn core JavaScript concepts used in every modern web app.",
            Description="Covers variables, functions, DOM manipulation, events, and asynchronous JavaScript "
                         "with fetch and promises.",
            Level="Beginner", Duration="10 hours", Price=0.0, PassingScore=70,
        )

        python_course = get_or_create_course(
            instructor, categories["Python"], "Python Programming",
            ShortDescription="Master Python from fundamentals to real-world scripting.",
            Description="A complete introduction to Python: syntax, data structures, functions, file handling, "
                         "and an introduction to object-oriented programming.",
            Level="Beginner", Duration="12 hours", Price=0.0, PassingScore=70,
        )

        sql_course = get_or_create_course(
            instructor, categories["Database Management"], "SQL & Database Management",
            ShortDescription="Learn to design, query, and manage relational databases.",
            Description="Covers relational database design, SQL queries, joins, indexing, and normalization "
                         "using Microsoft SQL Server.",
            Level="Intermediate", Duration="9 hours", Price=0.0, PassingScore=70,
        )

        print("  Courses: 4 created/verified")

        # ---------------- Modules & Lessons for Python course ----------------
        if not python_course.modules:
            m1 = Module(CourseID=python_course.CourseID, Title="Getting Started with Python", DisplayOrder=1)
            m2 = Module(CourseID=python_course.CourseID, Title="Control Flow & Functions", DisplayOrder=2)
            db.session.add_all([m1, m2])
            db.session.commit()

            lessons_m1 = [
                Lesson(ModuleID=m1.ModuleID, Title="Installing Python & Setting Up Your Editor",
                       Description="Get Python installed and your first script running.",
                       Content="<p>In this lesson we install Python 3 and set up VS Code for development.</p>",
                       Duration="10 min", DisplayOrder=1, IsPreview=True),
                Lesson(ModuleID=m1.ModuleID, Title="Variables and Data Types",
                       Description="Learn about strings, integers, floats, and booleans.",
                       Content="<p>Python is dynamically typed. We'll explore the core built-in data types.</p>",
                       Duration="15 min", DisplayOrder=2),
                Lesson(ModuleID=m1.ModuleID, Title="Working with Lists and Dictionaries",
                       Description="Understand Python's core data structures.",
                       Content="<p>Lists and dictionaries are the backbone of most Python programs.</p>",
                       Duration="20 min", DisplayOrder=3),
            ]
            lessons_m2 = [
                Lesson(ModuleID=m2.ModuleID, Title="If Statements and Loops",
                       Description="Control the flow of your programs.",
                       Content="<p>We cover if/elif/else, for loops, and while loops with examples.</p>",
                       Duration="18 min", DisplayOrder=1),
                Lesson(ModuleID=m2.ModuleID, Title="Writing Functions",
                       Description="Organize your code into reusable functions.",
                       Content="<p>Functions let us avoid repeating ourselves. We cover parameters and return values.</p>",
                       Duration="16 min", DisplayOrder=2),
            ]
            db.session.add_all(lessons_m1 + lessons_m2)
            db.session.commit()

            # Module quiz + final assessment
            quiz1 = Quiz(CourseID=python_course.CourseID, ModuleID=m1.ModuleID, Title="Python Basics Quiz",
                         PassingScore=70, AttemptsAllowed=3, IsFinalAssessment=False)
            db.session.add(quiz1)
            db.session.commit()

            questions = [
                Question(QuizID=quiz1.QuizID, QuestionText="Which keyword is used to define a function in Python?",
                          OptionA="func", OptionB="def", OptionC="function", OptionD="lambda",
                          CorrectOption="B", Marks=1),
                Question(QuizID=quiz1.QuizID, QuestionText="What data type is the result of 5 / 2 in Python 3?",
                          OptionA="int", OptionB="float", OptionC="str", OptionD="complex",
                          CorrectOption="B", Marks=1),
                Question(QuizID=quiz1.QuizID, QuestionText="Which of these creates an empty list?",
                          OptionA="list()", OptionB="{}", OptionC="()", OptionD="None",
                          CorrectOption="A", Marks=1),
            ]
            db.session.add_all(questions)

            final_quiz = Quiz(CourseID=python_course.CourseID, Title="Python Programming — Final Assessment",
                               PassingScore=70, AttemptsAllowed=3, IsFinalAssessment=True)
            db.session.add(final_quiz)
            db.session.commit()

            final_questions = [
                Question(QuizID=final_quiz.QuizID, QuestionText="What does PEP 8 refer to?",
                          OptionA="A Python testing library", OptionB="Python's style guide",
                          OptionC="A package manager", OptionD="An IDE",
                          CorrectOption="B", Marks=1),
                Question(QuizID=final_quiz.QuizID, QuestionText="Which method adds an item to the end of a list?",
                          OptionA="list.add()", OptionB="list.push()", OptionC="list.append()", OptionD="list.insert()",
                          CorrectOption="C", Marks=1),
            ]
            db.session.add_all(final_questions)
            db.session.commit()
            print("  Python course: modules, lessons, and quizzes created")

        # ---------------- Sample enrollment ----------------
        existing_enrollment = Enrollment.query.filter_by(StudentID=student.UserID, CourseID=python_course.CourseID).first()
        if not existing_enrollment:
            enrollment = Enrollment(StudentID=student.UserID, CourseID=python_course.CourseID,
                                     ProgressPercentage=0.0, Status="Active")
            db.session.add(enrollment)
            db.session.commit()
            print("  Demo student enrolled in Python Programming")

        print("\nSeed complete. Demo accounts (development only — change these passwords):")
        print("  Admin:      admin@example.com      / Admin@12345")
        print("  Instructor: instructor@example.com  / Instructor@123")
        print("  Student:    student@example.com     / Student@123")


if __name__ == "__main__":
    seed()
