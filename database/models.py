"""
SQLAlchemy ORM models for EduCertify.

Design notes:
- Works against both Microsoft SQL Server (production/dev via pyodbc) and
  SQLite (local demo mode), so column types stick to portable SQLAlchemy
  types (String, Integer, Float, Boolean, DateTime, Text) rather than
  SQL-Server-only types.
- All FK relationships use ON DELETE behavior appropriate to the entity
  (mostly RESTRICT/CASCADE where it makes sense) but defaults are left
  conservative to avoid accidental data loss; application code enforces
  ownership and business rules on top of these constraints.
"""

from datetime import datetime, timezone
from database.database import db


def utcnow():
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------
class User(db.Model):
    __tablename__ = "Users"

    UserID = db.Column(db.Integer, primary_key=True)
    FullName = db.Column(db.String(150), nullable=False)
    Email = db.Column(db.String(150), unique=True, nullable=False, index=True)
    PasswordHash = db.Column(db.String(255), nullable=False)
    Role = db.Column(db.String(20), nullable=False, default="Student")  # Student, Instructor, Admin
    ProfileImage = db.Column(db.String(255), nullable=True)
    IsActive = db.Column(db.Boolean, default=True, nullable=False)
    CreatedAt = db.Column(db.DateTime, default=utcnow, nullable=False)
    UpdatedAt = db.Column(db.DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    courses = db.relationship("Course", back_populates="instructor", foreign_keys="Course.InstructorID")
    enrollments = db.relationship("Enrollment", back_populates="student", cascade="all, delete-orphan")
    lesson_progress = db.relationship("LessonProgress", back_populates="student", cascade="all, delete-orphan")
    quiz_attempts = db.relationship("QuizAttempt", back_populates="student", cascade="all, delete-orphan")
    certificates = db.relationship("Certificate", back_populates="student", cascade="all, delete-orphan")
    reviews = db.relationship("Review", back_populates="student", cascade="all, delete-orphan")
    notifications = db.relationship("Notification", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User {self.Email} ({self.Role})>"


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------
class Category(db.Model):
    __tablename__ = "Categories"

    CategoryID = db.Column(db.Integer, primary_key=True)
    Name = db.Column(db.String(120), unique=True, nullable=False)
    Description = db.Column(db.Text, nullable=True)
    ImageURL = db.Column(db.String(255), nullable=True)
    IsActive = db.Column(db.Boolean, default=True, nullable=False)
    CreatedAt = db.Column(db.DateTime, default=utcnow, nullable=False)

    courses = db.relationship("Course", back_populates="category")

    def __repr__(self):
        return f"<Category {self.Name}>"


# ---------------------------------------------------------------------------
# Courses
# ---------------------------------------------------------------------------
class Course(db.Model):
    __tablename__ = "Courses"

    CourseID = db.Column(db.Integer, primary_key=True)
    InstructorID = db.Column(db.Integer, db.ForeignKey("Users.UserID"), nullable=False)
    CategoryID = db.Column(db.Integer, db.ForeignKey("Categories.CategoryID"), nullable=False)
    Title = db.Column(db.String(200), nullable=False)
    Slug = db.Column(db.String(220), unique=True, nullable=False, index=True)
    ShortDescription = db.Column(db.String(300), nullable=True)
    Description = db.Column(db.Text, nullable=True)
    ThumbnailURL = db.Column(db.String(255), nullable=True)
    Level = db.Column(db.String(20), default="Beginner", nullable=False)  # Beginner/Intermediate/Advanced
    Duration = db.Column(db.String(50), nullable=True)  # e.g. "6 hours"
    Price = db.Column(db.Float, default=0.0, nullable=False)
    PassingScore = db.Column(db.Integer, default=70, nullable=False)
    Status = db.Column(db.String(20), default="Draft", nullable=False)  # Draft/Pending/Published/Rejected/Archived
    RejectionReason = db.Column(db.Text, nullable=True)
    CreatedAt = db.Column(db.DateTime, default=utcnow, nullable=False)
    UpdatedAt = db.Column(db.DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    instructor = db.relationship("User", back_populates="courses", foreign_keys=[InstructorID])
    category = db.relationship("Category", back_populates="courses")
    modules = db.relationship(
        "Module", back_populates="course", cascade="all, delete-orphan",
        order_by="Module.DisplayOrder"
    )
    quizzes = db.relationship("Quiz", back_populates="course", cascade="all, delete-orphan")
    enrollments = db.relationship("Enrollment", back_populates="course", cascade="all, delete-orphan")
    certificates = db.relationship("Certificate", back_populates="course", cascade="all, delete-orphan")
    reviews = db.relationship("Review", back_populates="course", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Course {self.Title} ({self.Status})>"

    @property
    def total_lessons(self):
        count = 0
        for module in self.modules:
            count += len(module.lessons)
        return count

    @property
    def average_rating(self):
        if not self.reviews:
            return 0
        return round(sum(r.Rating for r in self.reviews) / len(self.reviews), 1)


# ---------------------------------------------------------------------------
# Modules
# ---------------------------------------------------------------------------
class Module(db.Model):
    __tablename__ = "Modules"

    ModuleID = db.Column(db.Integer, primary_key=True)
    CourseID = db.Column(db.Integer, db.ForeignKey("Courses.CourseID"), nullable=False)
    Title = db.Column(db.String(200), nullable=False)
    Description = db.Column(db.Text, nullable=True)
    DisplayOrder = db.Column(db.Integer, default=0, nullable=False)
    CreatedAt = db.Column(db.DateTime, default=utcnow, nullable=False)

    course = db.relationship("Course", back_populates="modules")
    lessons = db.relationship(
        "Lesson", back_populates="module", cascade="all, delete-orphan",
        order_by="Lesson.DisplayOrder"
    )
    quizzes = db.relationship("Quiz", back_populates="module")

    def __repr__(self):
        return f"<Module {self.Title}>"


# ---------------------------------------------------------------------------
# Lessons
# ---------------------------------------------------------------------------
class Lesson(db.Model):
    __tablename__ = "Lessons"

    LessonID = db.Column(db.Integer, primary_key=True)
    ModuleID = db.Column(db.Integer, db.ForeignKey("Modules.ModuleID"), nullable=False)
    Title = db.Column(db.String(200), nullable=False)
    Description = db.Column(db.Text, nullable=True)
    Content = db.Column(db.Text, nullable=True)
    VideoURL = db.Column(db.String(255), nullable=True)
    ResourceURL = db.Column(db.String(255), nullable=True)
    Duration = db.Column(db.String(50), nullable=True)  # e.g. "12 min"
    DisplayOrder = db.Column(db.Integer, default=0, nullable=False)
    IsPreview = db.Column(db.Boolean, default=False, nullable=False)
    CreatedAt = db.Column(db.DateTime, default=utcnow, nullable=False)

    module = db.relationship("Module", back_populates="lessons")
    progress_records = db.relationship("LessonProgress", back_populates="lesson", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Lesson {self.Title}>"


# ---------------------------------------------------------------------------
# Enrollments
# ---------------------------------------------------------------------------
class Enrollment(db.Model):
    __tablename__ = "Enrollments"
    __table_args__ = (
        db.UniqueConstraint("StudentID", "CourseID", name="uq_student_course_enrollment"),
    )

    EnrollmentID = db.Column(db.Integer, primary_key=True)
    StudentID = db.Column(db.Integer, db.ForeignKey("Users.UserID"), nullable=False)
    CourseID = db.Column(db.Integer, db.ForeignKey("Courses.CourseID"), nullable=False)
    EnrollmentDate = db.Column(db.DateTime, default=utcnow, nullable=False)
    CompletionDate = db.Column(db.DateTime, nullable=True)
    ProgressPercentage = db.Column(db.Float, default=0.0, nullable=False)
    Status = db.Column(db.String(20), default="Active", nullable=False)  # Active/Completed/Dropped

    student = db.relationship("User", back_populates="enrollments")
    course = db.relationship("Course", back_populates="enrollments")

    def __repr__(self):
        return f"<Enrollment student={self.StudentID} course={self.CourseID}>"


# ---------------------------------------------------------------------------
# LessonProgress
# ---------------------------------------------------------------------------
class LessonProgress(db.Model):
    __tablename__ = "LessonProgress"
    __table_args__ = (
        db.UniqueConstraint("StudentID", "LessonID", name="uq_student_lesson_progress"),
    )

    ProgressID = db.Column(db.Integer, primary_key=True)
    StudentID = db.Column(db.Integer, db.ForeignKey("Users.UserID"), nullable=False)
    LessonID = db.Column(db.Integer, db.ForeignKey("Lessons.LessonID"), nullable=False)
    Completed = db.Column(db.Boolean, default=False, nullable=False)
    CompletedAt = db.Column(db.DateTime, nullable=True)

    student = db.relationship("User", back_populates="lesson_progress")
    lesson = db.relationship("Lesson", back_populates="progress_records")


# ---------------------------------------------------------------------------
# Quizzes
# ---------------------------------------------------------------------------
class Quiz(db.Model):
    __tablename__ = "Quizzes"

    QuizID = db.Column(db.Integer, primary_key=True)
    CourseID = db.Column(db.Integer, db.ForeignKey("Courses.CourseID"), nullable=False)
    ModuleID = db.Column(db.Integer, db.ForeignKey("Modules.ModuleID"), nullable=True)
    Title = db.Column(db.String(200), nullable=False)
    Description = db.Column(db.Text, nullable=True)
    PassingScore = db.Column(db.Integer, default=70, nullable=False)
    TimeLimit = db.Column(db.Integer, nullable=True)  # minutes
    AttemptsAllowed = db.Column(db.Integer, default=3, nullable=False)
    IsFinalAssessment = db.Column(db.Boolean, default=False, nullable=False)
    CreatedAt = db.Column(db.DateTime, default=utcnow, nullable=False)

    course = db.relationship("Course", back_populates="quizzes")
    module = db.relationship("Module", back_populates="quizzes")
    questions = db.relationship("Question", back_populates="quiz", cascade="all, delete-orphan")
    attempts = db.relationship("QuizAttempt", back_populates="quiz", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Quiz {self.Title}>"


# ---------------------------------------------------------------------------
# Questions
# ---------------------------------------------------------------------------
class Question(db.Model):
    __tablename__ = "Questions"

    QuestionID = db.Column(db.Integer, primary_key=True)
    QuizID = db.Column(db.Integer, db.ForeignKey("Quizzes.QuizID"), nullable=False)
    QuestionText = db.Column(db.Text, nullable=False)
    OptionA = db.Column(db.String(500), nullable=False)
    OptionB = db.Column(db.String(500), nullable=False)
    OptionC = db.Column(db.String(500), nullable=False)
    OptionD = db.Column(db.String(500), nullable=False)
    CorrectOption = db.Column(db.String(1), nullable=False)  # 'A' / 'B' / 'C' / 'D'
    Marks = db.Column(db.Integer, default=1, nullable=False)

    quiz = db.relationship("Quiz", back_populates="questions")

    def to_public_dict(self):
        """Serialize WITHOUT the correct answer - safe to send to the browser."""
        return {
            "QuestionID": self.QuestionID,
            "QuestionText": self.QuestionText,
            "OptionA": self.OptionA,
            "OptionB": self.OptionB,
            "OptionC": self.OptionC,
            "OptionD": self.OptionD,
            "Marks": self.Marks,
        }


# ---------------------------------------------------------------------------
# QuizAttempts
# ---------------------------------------------------------------------------
class QuizAttempt(db.Model):
    __tablename__ = "QuizAttempts"

    AttemptID = db.Column(db.Integer, primary_key=True)
    QuizID = db.Column(db.Integer, db.ForeignKey("Quizzes.QuizID"), nullable=False)
    StudentID = db.Column(db.Integer, db.ForeignKey("Users.UserID"), nullable=False)
    Score = db.Column(db.Integer, default=0, nullable=False)
    Percentage = db.Column(db.Float, default=0.0, nullable=False)
    Passed = db.Column(db.Boolean, default=False, nullable=False)
    StartedAt = db.Column(db.DateTime, default=utcnow, nullable=False)
    CompletedAt = db.Column(db.DateTime, nullable=True)
    AttemptNumber = db.Column(db.Integer, default=1, nullable=False)

    quiz = db.relationship("Quiz", back_populates="attempts")
    student = db.relationship("User", back_populates="quiz_attempts")
    answers = db.relationship("QuizAnswer", back_populates="attempt", cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# QuizAnswers
# ---------------------------------------------------------------------------
class QuizAnswer(db.Model):
    __tablename__ = "QuizAnswers"

    AnswerID = db.Column(db.Integer, primary_key=True)
    AttemptID = db.Column(db.Integer, db.ForeignKey("QuizAttempts.AttemptID"), nullable=False)
    QuestionID = db.Column(db.Integer, db.ForeignKey("Questions.QuestionID"), nullable=False)
    SelectedOption = db.Column(db.String(1), nullable=True)
    IsCorrect = db.Column(db.Boolean, default=False, nullable=False)
    MarksObtained = db.Column(db.Integer, default=0, nullable=False)

    attempt = db.relationship("QuizAttempt", back_populates="answers")
    question = db.relationship("Question")


# ---------------------------------------------------------------------------
# Certificates
# ---------------------------------------------------------------------------
class Certificate(db.Model):
    __tablename__ = "Certificates"

    CertificateID = db.Column(db.Integer, primary_key=True)
    StudentID = db.Column(db.Integer, db.ForeignKey("Users.UserID"), nullable=False)
    CourseID = db.Column(db.Integer, db.ForeignKey("Courses.CourseID"), nullable=False)
    CertificateNumber = db.Column(db.String(50), unique=True, nullable=False, index=True)
    FinalScore = db.Column(db.Float, nullable=False)
    IssueDate = db.Column(db.DateTime, default=utcnow, nullable=False)
    PDFPath = db.Column(db.String(255), nullable=True)
    QRCodePath = db.Column(db.String(255), nullable=True)
    Status = db.Column(db.String(20), default="Valid", nullable=False)  # Valid/Revoked

    student = db.relationship("User", back_populates="certificates")
    course = db.relationship("Course", back_populates="certificates")

    def __repr__(self):
        return f"<Certificate {self.CertificateNumber}>"


# ---------------------------------------------------------------------------
# Reviews
# ---------------------------------------------------------------------------
class Review(db.Model):
    __tablename__ = "Reviews"
    __table_args__ = (
        db.UniqueConstraint("StudentID", "CourseID", name="uq_student_course_review"),
    )

    ReviewID = db.Column(db.Integer, primary_key=True)
    StudentID = db.Column(db.Integer, db.ForeignKey("Users.UserID"), nullable=False)
    CourseID = db.Column(db.Integer, db.ForeignKey("Courses.CourseID"), nullable=False)
    Rating = db.Column(db.Integer, nullable=False)  # 1-5
    Comment = db.Column(db.Text, nullable=True)
    CreatedAt = db.Column(db.DateTime, default=utcnow, nullable=False)

    student = db.relationship("User", back_populates="reviews")
    course = db.relationship("Course", back_populates="reviews")


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------
class Notification(db.Model):
    __tablename__ = "Notifications"

    NotificationID = db.Column(db.Integer, primary_key=True)
    UserID = db.Column(db.Integer, db.ForeignKey("Users.UserID"), nullable=False)
    Title = db.Column(db.String(200), nullable=False)
    Message = db.Column(db.Text, nullable=False)
    Type = db.Column(db.String(30), default="info", nullable=False)
    IsRead = db.Column(db.Boolean, default=False, nullable=False)
    CreatedAt = db.Column(db.DateTime, default=utcnow, nullable=False)

    user = db.relationship("User", back_populates="notifications")
