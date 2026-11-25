// A header button to hide the navigation sidebar, pinned from 60em wide by docgen/sidebar_breakpoint.py.
// The choice is remembered between pages and visits, and applied before the page is drawn by overrides/main.html.
const NAV_COLLAPSED = "sn-nav-collapsed"

const navToggle = document.createElement("button")
navToggle.type = "button"
navToggle.className = "md-header__button md-icon sn-nav-toggle"
navToggle.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M3 6h18v2H3zm0 5h18v2H3zm0 5h18v2H3z"/></svg>'

function labelNavToggle() {
  const collapsed = document.documentElement.classList.contains(NAV_COLLAPSED)
  const label = collapsed ? "Show navigation" : "Hide navigation"
  navToggle.title = label
  navToggle.setAttribute("aria-label", label)
  navToggle.setAttribute("aria-expanded", String(!collapsed))
}

navToggle.addEventListener("click", () => {
  const collapsed = document.documentElement.classList.toggle(NAV_COLLAPSED)
  try {
    localStorage.setItem(NAV_COLLAPSED, collapsed ? "1" : "0")
  } catch {
    // storage blocked, so the choice lasts only until the page is reloaded
  }
  labelNavToggle()
})

labelNavToggle()
document.querySelector('.md-header__inner label[for="__drawer"]')?.after(navToggle)
