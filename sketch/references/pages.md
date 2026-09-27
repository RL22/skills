# Page templates

Page templates are compact, recognisable page archetypes for `page` components.

| Template | What it shows | Options |
|---|---|---|
| `basic` | A single full-page image placeholder | — |
| `cart` | Product rows, total divider, and checkout action | `count` (1–4) |
| `landing` | Navigation, hero copy, image, and primary action | — |
| `grid` | A two-row card grid | `cols` (2–4) |
| `columns` | Parallel text columns | `cols` (2–4) |
| `rows` | Repeated horizontal media rows | `count` (2–4) |
| `list` | A simple marked list | `count` (1–4) |
| `article` | Headline, byline, hero image, and body copy | — |
| `blog` | A grid of article cards | — |
| `calendar` | Calendar controls and a seven-column date table | — |
| `event` | Event image, date, description, and join action | — |
| `team` | A grid of avatar cards | `count` (1–6) |
| `bio` | Portrait, identity, biography, and social icons | — |
| `features` | A grid of feature summaries | — |
| `gallery` | A compact image gallery | `count` (1–8) |
| `slideshow` | One large image with previous/next controls | — |
| `video` | Video player with title and description | — |
| `news` | Lead story with secondary headlines | — |
| `magazine` | Editorial lead image, columns, and teaser row | — |
| `board` | Three task-board columns with cards and add areas | — |
| `contact` | Contact fields, message area, and send action | — |
| `form` | A generic multi-field form | — |
| `login` | Credentials and log-in action | — |
| `signup` | Registration fields, consent, and sign-up action | — |
| `chat` | Alternating message bubbles and composer | — |
| `comments` | Avatar-led comments and reply field | — |
| `documents` | Document toolbar and file table | — |
| `profile` | User identity, follow action, tabs, and media | — |
| `products` | A product-card catalog | `count` (1–8) |
| `product` | Product image, details, option, and buy action | — |
| `checkout` | Payment fields, summary divider, and pay action | — |
| `pricing` | Three tier cards with one featured action | — |
| `tabs` | Tab navigation and its active content | — |
| `map` | Search field, labelled map, and map markers | — |
| `directory` | Searchable avatar directory | — |
| `search` | Query field, result count, and result list | — |
| `sitemap` | A compact hierarchy table | — |
| `dashboard` | Summary cards and a chart | — |
| `settings` | Settings tabs, field, toggle, and save action | — |
| `thanks` | Confirmation mark, message, and continue action | — |
| `error404` | 404 message, missing-page image, and home action | — |
| `external` | Dashed external-content placeholder and visit action | — |

Use `{"type":"page","template":"pricing","w":150}` as an item in a flow to show the pricing step as a page thumbnail.
Use the same page object as a sitemap node; add `id` and placement fields when arrows or explicit positioning are needed.
