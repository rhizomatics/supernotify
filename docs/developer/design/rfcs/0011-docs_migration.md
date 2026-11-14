# RFC 0011: Migrate Documentation

2026-11-07 · Jey Burrows · Status: Partially Complete. Phase 1 done

Move off the unsupported, and potentially disruptive `mkdocs`, and the no longer updated Material for Mkdocs components.

At each phase, preserve existing links wherever possible, so that search engines and links from other sites do not break, and in general maintain SEO and agent compatibility.

## Phase 1 - Stabilize - DONE

Use `properdocs` in place of `mkdocs` and `materialX` as the theme. Retain `mike`.

## Phase 2 - Zensical.

When Zensical has support for required `properdocs` and `materialX` currently used.

Also review approach for translations and versioning.

- Current partial translation structure leads to many build warnings and poorer experience for non-English speakers
- `mike` versioning leads to enornmous branches and failing Github Pages uploads, plus broken builds
- There is no strong need to have versioned documentation all the way back, the primary need is to separate dev/beta/prod so that people using production release don't get confusing docs for things not yet released.
- Ideally, production docs can be improved independently of a production code release
