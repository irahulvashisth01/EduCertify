// EduCertify — Dashboard sidebar mobile toggle
document.addEventListener("DOMContentLoaded", function () {
  const toggle = document.getElementById("dashSidebarToggle");
  const sidebar = document.getElementById("dashSidebar");
  if (toggle && sidebar) {
    toggle.addEventListener("click", function () {
      sidebar.classList.toggle("ec-open");
    });
  }

  // Animated stat counters
  document.querySelectorAll(".ec-stat-value[data-count]").forEach(function (el) {
    const target = parseFloat(el.dataset.count) || 0;
    let current = 0;
    const step = Math.max(target / 30, 0.5);
    const suffix = el.dataset.suffix || "";
    const interval = setInterval(function () {
      current += step;
      if (current >= target) {
        current = target;
        clearInterval(interval);
      }
      el.textContent = Math.round(current) + suffix;
    }, 20);
  });
});
