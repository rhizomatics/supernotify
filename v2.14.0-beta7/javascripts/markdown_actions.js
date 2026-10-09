// Page-level "View as Markdown" / "Copy as Markdown" buttons.
// The markdown files come from the llmstxt plugin, which only publishes pages listed in its
// sections, so the buttons stay hidden unless the markdown file exists.
document$.subscribe(() => {
  const view = document.querySelector("[data-md-view]")
  const copy = document.querySelector("[data-md-copy]")
  if (!view || !copy) return

  fetch(view.href, { method: "HEAD" })
    .then(response => {
      if (response.ok) view.hidden = copy.hidden = false
    })
    .catch(() => {})

  copy.addEventListener("click", async event => {
    event.preventDefault()
    const response = await fetch(view.href)
    await navigator.clipboard.writeText(await response.text())
    copy.querySelector("[data-md-copy-icon]").hidden = true
    copy.querySelector("[data-md-done-icon]").hidden = false
    setTimeout(() => {
      copy.querySelector("[data-md-copy-icon]").hidden = false
      copy.querySelector("[data-md-done-icon]").hidden = true
    }, 2000)
  })
})
