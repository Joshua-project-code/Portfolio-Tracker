const backToTopButton = document.querySelector("#back-to-top");

function updateBackToTopVisibility() {
  if (!backToTopButton) {
    return;
  }
  const shouldShow = window.scrollY > 280;
  backToTopButton.hidden = !shouldShow;
}

backToTopButton?.addEventListener("click", () => {
  window.scrollTo({ top: 0, behavior: "smooth" });
});

window.addEventListener("scroll", updateBackToTopVisibility, { passive: true });
document.addEventListener("DOMContentLoaded", updateBackToTopVisibility);
