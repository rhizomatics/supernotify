# Building

## Prerequisites

- uv
- python3.14
- pre-commit

A `mise.toml` is provided for these.

For documentation build:

* pngquant

## Updating Dependencies

```bash
./refresh-deps.sh
```

## Editing Releases

GitHub CLI can move a published release back to draft:

`gh release edit v2.11.0-beta2 --draft=true`
`gh release edit v2.11.0-beta2 --draft=false --prerelease`

The second command publishes it again, which fires published and starts the workflow.

## Refreshing Diagram Thumbnails

The `diagram-thumbnails` pre-commit hook refreshes the PNG thumbnail of any diagram HTML being
committed, when the thumbnail is older than the diagram. To regenerate them all, run `node docgen/diagram_thumbnails.mjs`. Both need Google Chrome and the archify skill under `.agents/`.

## Skills

### Archify

```bash
npx -y skills add tt-a1i/archify --skill archify --agent codex --copy --yes
```
