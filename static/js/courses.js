// EduCertify — Course catalog filter auto-submit
document.addEventListener("DOMContentLoaded", function () {
  const filterForm = document.getElementById("courseFilterForm");
  if (!filterForm) return;

  filterForm.querySelectorAll("select").forEach(function (select) {
    select.addEventListener("change", function () {
      filterForm.submit();
    });
  });
});
