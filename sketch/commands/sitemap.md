# sketch sitemap

Information architecture as a tree of page thumbnails: the home page on top, sections fanned out in a
row, each section's pages stacked on a rail below it, numbered badges tied to a footnote legend.
Template: `examples/sitemap.json`.

## Gather

- Every page (or page type) and its parent. Group repeated pages into one type ("Post", "Case study").
- The 2–5 decisions worth explaining: new pages, removed dead ends, merged sections.

## Compose

1. One `tree` item. `root` is the home page; each node is `{ id, label, template?, badge?, dashed?, children }`.
   Section pages are the root's children; their children stack below; deeper pages continue to the right.
2. Give nodes a `template` (see [../references/pages.md](../references/pages.md)) so each thumbnail reads as its
   archetype — `pricing`, `blog`, `contact`. Nodes without one draw as a titled page with squiggles.
3. `dashed: true` on pages that leave the site (external links, third-party checkout).
4. `badge: n` on the nodes you explain, then one `legend` item after the tree with the n-th explanation.
5. Optional grey `note`s for global elements ("main nav", "footer links").

## Checks

- Every node sits under its real parent; no connector crosses a thumbnail.
- Badge numbers and legend entries match one-to-one.
