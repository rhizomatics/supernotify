// Clicking a tag bubble in a tagged index narrows the list to the pages with that tag;
// clicking the selected tag again shows them all. One listener on the document, so it
// carries on working across instant navigation.
document.addEventListener("click", event => {
  const clicked = event.target.closest(".index-tag")
  const list = clicked?.closest("ul")
  if (!list) return
  const tag = clicked.classList.contains("index-tag--selected") ? null : clicked.textContent
  list.querySelectorAll("li").forEach(item => {
    const bubbles = [...item.querySelectorAll(".index-tag")]
    bubbles.forEach(bubble => {
      const selected = bubble.textContent === tag
      bubble.classList.toggle("index-tag--selected", selected)
      bubble.setAttribute("aria-pressed", selected)
    })
    item.hidden = tag !== null && !bubbles.some(bubble => bubble.textContent === tag)
  })
})
