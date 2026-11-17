// navigation.expand opens every section; start these bulky generated ones collapsed.
// Sections containing the current page are rendered checked, so they stay open.
const COLLAPSED_SECTIONS = ["Classes", "Schemas", "HTML Email Renders"]

document$.subscribe(() => {
  document.querySelectorAll(".md-sidebar--primary input.md-toggle--indeterminate").forEach(toggle => {
    const title = toggle.closest("li")?.querySelector(".md-ellipsis")?.textContent.trim()
    if (COLLAPSED_SECTIONS.includes(title)) toggle.classList.remove("md-toggle--indeterminate")
  })
})
