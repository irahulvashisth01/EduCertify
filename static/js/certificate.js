// EduCertify — Certificate verification form UX (uppercase + trim as-you-type)
document.addEventListener("DOMContentLoaded", function () {
  const input = document.getElementById("certIdInput");
  if (input) {
    input.addEventListener("input", function () {
      this.value = this.value.toUpperCase();
    });
  }
});
