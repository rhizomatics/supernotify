// Clicking a tag bubble in a tagged index narrows the list to the pages with that tag;
// clicking the selected tag again shows them all. One listener on the document, so it
// carries on working across instant navigation.
function filterByTag(list, tag) {
  list.querySelectorAll("li").forEach(item => {
    const bubbles = [...item.querySelectorAll(".index-tag")]
    bubbles.forEach(bubble => {
      const selected = bubble.textContent === tag
      bubble.classList.toggle("index-tag--selected", selected)
      bubble.setAttribute("aria-pressed", selected)
    })
    item.hidden = tag !== null && !bubbles.some(bubble => bubble.textContent === tag)
  })
}

document.addEventListener("click", event => {
  const clicked = event.target.closest(".index-tag")
  const list = clicked?.closest("ul")
  if (!list) return
  filterByTag(list, clicked.classList.contains("index-tag--selected") ? null : clicked.textContent)
})

// A link ending #tag=name, as the sidebar has for each tag, opens the index narrowed to that tag
function filterByHash(hash = location.hash) {
  const list = document.querySelector(".md-content .index-tag")?.closest("ul")
  if (list) filterByTag(list, new URLSearchParams(hash.slice(1)).get("tag"))
}

window.addEventListener("hashchange", () => filterByHash())
document$.subscribe(() => filterByHash())
// instant navigation moves within a page by history.pushState, which fires neither of the above
location$.subscribe(url => filterByHash(url.hash))
