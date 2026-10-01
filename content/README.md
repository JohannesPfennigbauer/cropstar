# Content

Markdown sources for the blog, rendered by Nuxt Content in `apps/web`.

```
blog/de/<slug>.md     German posts      → /blog/<slug>
blog/en/<slug>.md     English posts     → /en/blog/<slug>
authors/<id>.yml      Author profiles, referenced by id
media/<slug>/…        Images            → /media/<slug>/…
```

## Frontmatter

```yaml
---
title: Zwischenfrüchte und Stickstoff
description: One or two sentences for the card and search engines.
date: 2026-10-01
updated: 2026-11-15          # optional
authors: [jpf]               # ids from authors/
topic: practice              # practice | modeling
tags: [cover-crops, nitrogen]
cover:                       # optional
  src: /media/zwischenfruechte/cover.jpg
  alt: Phacelia in bloom between wheat stubble
translationOf: willkommen    # optional: slug of the original in another locale
translatedBy: machine        # optional: shows a notice and links the original
draft: true                  # optional: visible in `just dev` only
sources:                     # optional: rendered under the post
  - label: Author (Year). Title. Journal.
    url: https://doi.org/…
---
```

`pnpm --filter @cropstar/web test` validates every file against this schema and checks that
authors, covers and `translationOf` targets exist. CI runs it before the build.

## Translations

- Same file name in both folders, or `translationOf` pointing at the original's slug.
- A post without a translation still appears in the other language's list, with a notice.

## Rules for posts

- Every number in the prose gets a citation: a Markdown footnote (`[^1]`) or a `sources:` entry.
- Interactive widgets live in `apps/web/app/components/content/` and are embedded with MDC:

  ```md
  ::illustrative-yield
  ::
  ```

  They must show an uncertainty band, their provenance and a clear "illustrative" label.
- Describe consequences; never recommend.
