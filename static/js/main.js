// EduCertify — Global JS (navbar, flash messages, footer year)

document.addEventListener("DOMContentLoaded", function () {
  // Footer dynamic year
  const yearEl = document.getElementById("currentYear");
  if (yearEl) yearEl.textContent = new Date().getFullYear();

  // Mobile nav toggle
  const navToggle = document.getElementById("navToggle");
  const navLinks = document.getElementById("navLinks");
  if (navToggle && navLinks) {
    navToggle.addEventListener("click", function () {
      navLinks.classList.toggle("ec-open");
    });
  }

  // Flash message close + auto-hide
  document.querySelectorAll(".ec-alert").forEach(function (alert) {
    const closeBtn = alert.querySelector(".ec-alert-close");
    if (closeBtn) {
      closeBtn.addEventListener("click", function () {
        dismissAlert(alert);
      });
    }
    setTimeout(function () {
      dismissAlert(alert);
    }, 5000);
  });

  function dismissAlert(alert) {
    alert.style.transition = "opacity 0.3s ease, transform 0.3s ease";
    alert.style.opacity = "0";
    alert.style.transform = "translateY(-8px)";
    setTimeout(function () {
      alert.remove();
    }, 300);
  }
});

/**
 * Small fetch() wrapper used across dashboard/quiz/certificate JS files.
 * Always returns a parsed JSON object and never throws for HTTP errors -
 * callers should check `.success`.
 */
async function ecFetch(url, options = {}) {
  try {
    const response = await fetch(url, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
    return await response.json();
  } catch (err) {
    console.error("Network error:", err);
    return { success: false, message: "Network error. Please try again." };
  }
}
