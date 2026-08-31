// EduCertify — Auth forms client-side validation (UX only; server always re-validates)

document.addEventListener("DOMContentLoaded", function () {
  const registerForm = document.getElementById("registerForm");
  if (registerForm) {
    const password = document.getElementById("password");
    const confirmPassword = document.getElementById("confirmPassword");
    const matchError = document.getElementById("matchError");

    function checkMatch() {
      if (confirmPassword.value && password.value !== confirmPassword.value) {
        matchError.style.display = "block";
        confirmPassword.setCustomValidity("Passwords do not match");
      } else {
        matchError.style.display = "none";
        confirmPassword.setCustomValidity("");
      }
    }

    password.addEventListener("input", checkMatch);
    confirmPassword.addEventListener("input", checkMatch);

    registerForm.addEventListener("submit", function (e) {
      checkMatch();
      if (!registerForm.checkValidity()) {
        e.preventDefault();
        registerForm.reportValidity();
      }
    });
  }

  const loginForm = document.getElementById("loginForm");
  if (loginForm) {
    loginForm.addEventListener("submit", function (e) {
      if (!loginForm.checkValidity()) {
        e.preventDefault();
        loginForm.reportValidity();
      }
    });
  }
});
