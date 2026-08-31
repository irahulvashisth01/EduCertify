// EduCertify — Instructor course/module/lesson/quiz form helpers
document.addEventListener("DOMContentLoaded", function () {
  // Confirm before submitting a course for admin review
  const submitCourseForm = document.getElementById("submitCourseForm");
  if (submitCourseForm) {
    submitCourseForm.addEventListener("submit", function (e) {
      if (!confirm("Submit this course for admin review? You won't be able to edit content while it's pending.")) {
        e.preventDefault();
      }
    });
  }
});
