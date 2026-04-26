(() => {
  const sidebar = document.getElementById("sidebar");
  const toggle = document.getElementById("sidebarToggle");
  if (!sidebar || !toggle) return;

  toggle.addEventListener("click", () => {
    sidebar.classList.toggle("open");
  });

  document.addEventListener("click", (e) => {
    if (window.innerWidth > 991) return;
    const target = e.target;
    if (!(target instanceof HTMLElement)) return;
    if (target.closest("#sidebar") || target.closest("#sidebarToggle")) return;
    sidebar.classList.remove("open");
  });
})();

