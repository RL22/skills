# Sketch notation

The **sketch grammar**, distilled from real product-planning notebooks: which mark stands for
which UI thing. Use it to choose components and to judge whether a render reads right.

## Paper & ink

| Token | Value | Use |
|---|---|---|
| `paper: "plain"` | `#FFFDE7` cream | landing-page concepts, state diagrams, loose flows |
| `paper: "grid"` | `#F8F4DC` + faint 22px grid | component specs, technical notes, dense UI |
| `ink` default | `#1E1E1E` felt-tip | all structure; frames heavier than details |
| `ink: "note"` | `#8A8A8A` | margin notes, leader lines, arrow labels |
| `ink: "red"` / `"green"` | `#D83A2E` / `#2E9A5A` | semantic role only (removed/kept, header/section) |

## What each mark means

| UI thing | Drawn as | Component |
|---|---|---|
| Primary / solid button | diagonal hatching | `button` (default variant) |
| Secondary button | heavy double outline | `button variant:"outline"` |
| Tertiary | thin outline / underlined text | `variant:"ghost"` / `"link"` |
| Copy / paragraph | squiggles; last line shorter | `squiggle`, `paragraph`, any `"~"` string |
| Headline | thick squiggle or real word, underlined | `squiggle thick`, `heading` |
| Image / media | box with corner-to-corner X | `image`, `video` (adds ▶) |
| Avatar / logo | circle with X (or head+shoulders) | `avatar`, `logo` |
| Add / empty state | dashed box with + | `add`, `plus` |
| Selected / editable | dashed box around element | `selected: true` on any component |
| Input | long thin box; scribble = entered value | `input`, `textarea` (`filled: true`) |
| Dropdown | box + boxed `v` | `dropdown` |
| Slider | thin track + small thumb + value right | `slider` |
| Toggle / checkbox / radio | pill+knob (hatched = on) / ✓ box / dot | `toggle`, `checkbox`, `radio` |
| Tabs | words in a row, active one underlined | `tabs` |
| Nav | logo, short squiggles or words, hatched CTA, ≡ | `nav` |
| Menu / popover | rounded box with caret, dividers | `menu` |
| Social icons | row of small circles (optionally lettered) | `icons` |
| More content | row of tick marks | `more` |
| Scrolls / continues | zigzag bottom edge | `screen zigzag:true` |
| Interaction point | cursor arrow | `cursor`, or `cursor:true` on a component |
| Data | ruled grid / rough bars | `table`, `chart` |

## Board composition

Each command file in `commands/` owns how its board is laid out (flow, screen, sheet, iterate, redesign).
