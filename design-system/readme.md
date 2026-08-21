# Oripio Design System

Oripio is a personal-finance web app: one signed-in dashboard where an individual watches their
money — total balance across several currency wallets, expenses vs. savings, an earnings chart,
savings goals, and a running transaction log. The product voice is calm and custodial: it *monitors*
and *controls*, it does not sell.

## Sources

| Source | What it gave us |
| --- | --- |
| `uploads/ec5fe68b55cbefac884d2fa29ac65fe2.jpg` | The single source of truth: a 1200×900 render of the signed-in dashboard ("Welcome back Sajibur Rahman"). |

That is the **entire** brief. There is no codebase, no Figma file, no deck, no font binaries and no
written brand guide. Everything in this system is measured or sampled from that one render, and
anything not visible in it is either omitted or explicitly flagged as extrapolated. If you have the
real repo or Figma file, attach it — several values below can then move from "measured" to "exact".

**Products represented:** one — the Oripio web dashboard. No marketing site, mobile app, docs site or
slide template exists in the source, so none were authored.

## Index

| Path | What it is |
| --- | --- |
| `styles.css` | The one stylesheet consumers link. `@import`s only. |
| `tokens/` | `fonts.css`, `colors.css`, `typography.css`, `spacing.css`, `radius.css`, `elevation.css`, `motion.css`, `base.css`. |
| `components/core/` | Button, IconButton, Icon, Badge, StatusPill, Card + CardHeader, IconTile, SearchField, Select, Avatar. |
| `components/navigation/` | SidebarNav + SidebarItem + SidebarSectionLabel, TopBar + BrandLockup, PromoCard. |
| `components/data/` | StatCard, WalletTile, GoalRow, BarChart, DataTable. |
| `ui_kits/dashboard/` | Interactive recreation of the dashboard. Start at `index.html`; read its `README.md` for fidelity notes. |
| `guidelines/` | 18 specimen cards for colour, type, spacing and brand foundations. |
| `assets/` | `logo-mark.png`, `logo-lockup.png`, `avatar-user.png`, `flag-{usd,eur,bdt,gbp}.png`. |
| `thumbnail.html` | Homepage tile. |
| `SKILL.md` | Agent-Skills front matter for use outside this project. |

### Components

Core: **Button**, **IconButton**, **Icon**, **Badge**, **StatusPill**, **Card**, **CardHeader**,
**IconTile**, **SearchField**, **Select**, **Avatar**.
Navigation: **SidebarNav**, **SidebarItem**, **SidebarSectionLabel**, **TopBar**, **BrandLockup**, **PromoCard**.
Data: **StatCard**, **WalletTile**, **GoalRow**, **BarChart**, **DataTable**.

Every component maps to something visible in the render. Two **intentional additions**:

- **Icon** — a thin wrapper over the Lucide CDN set. The source is a raster, so glyphs had to be
  re-sourced; a wrapper keeps size/stroke consistent instead of scattering `<i data-lucide>` tags.
- **SidebarSectionLabel / CardHeader / BrandLockup** — named sub-parts of patterns that appear
  verbatim in the render, split out only so screens can compose them.

Nothing else was invented. There is no Tabs, Toast, Tooltip, Modal, Checkbox, Radio, Switch or
Textarea component, because the source shows none — the UI kit's Send Money sheet and toast are
one-off compositions inside the kit, deliberately *not* promoted to primitives.

---

## CONTENT FUNDAMENTALS

**Voice.** Second person, present tense, plainly reassuring. The one full sentence in the product is
the dashboard subhead: *"Monitor and control what happens with your money today for financial
health."* Note what it does — it names the user's control, not the product's cleverness. No
exclamation, no hype, no "we".

**Greeting.** The page title is a greeting, not a label: *"Welcome back Sajibur Rahman"* — full name,
no comma, no punctuation at the end. Never "Dashboard" as an H1 on the home view.

**Casing.** Title Case for everything nameable: card titles (*Account Balance*, *Total Expenses*,
*My Wallet*, *My Savings Plan*, *Recent Transaction*), buttons (*Send Money*, *Request Money*,
*Add New*, *Export*, *Upgrade*), table headers (*Activity*, *Date*, *Price*, *Status*), nav items
(*Dashboard*, *Help Desk*, *Log out* — note the sentence-cased second word). Sidebar group labels are
the only ALL-CAPS text: *MAIN MENU*, *FEATURES*, *GENERAL*.

**Singular where you'd expect plural.** *Recent Transaction*, not Transactions. Keep that quirk.

**Possessive first person for the user's own things.** *My Wallet*, *My Savings Plan* — the user owns
these. Everything analytical stays impersonal: *Overview*, *Total Expenses*, *Total Savings*.

**Numbers.** Always full precision with a currency symbol and grouped thousands: `$35,340.89`,
`€18,345.00`, `£15,000.00`, and lakh grouping for Bengali taka: `৳1,22,678.00`. Deltas are signed
percentages with one decimal plus an arrow: `+3.2% ↑`, `-2.1% ↓`, and the comparison basis is spelled
out beside them in grey — *from last month*. Chart axes abbreviate: `$0k`–`$40k`. Dates are
`Wed, 12 Jun 2026` in tables and `Sun, 12 June 2026` in the header date pill.

**Status words.** One word, never a sentence: *Success*, *Active*, *Inactive*. Failure and pending
states aren't in the source; use *Failed* and *Pending* to match.

**Emoji.** Used exactly once, as a reward marker on the upsell: *Upgrade Pro! 🏆*. That is the whole
budget. Emoji never appear in nav, table cells, metrics, or body copy — and the one exclamation mark
in the product lives in that same string.

**Length.** Card titles 1–3 words. Button labels 1–2 words. Body copy one sentence, ~12 words. If a
sentence needs a comma to survive, it is too long for this product.

---

## VISUAL FOUNDATIONS

**The desk metaphor.** A flat light-grey canvas (`--page #eaeaea`) holds one white rounded
application shell (radius 20, `--shadow-shell`). Inside the shell the content area returns to grey,
so white cards float on grey inside white. That double inset is the layout signature — reproduce it,
don't flatten it.

**Colour.** One hue does all the work: a deep emerald green (`--green-600 #059055`). It appears as the
primary button fill, the active nav label and tick, the saturated chart bar, the logo tile and the
sidebar upsell gradient — and nowhere else. Green tints (`--green-50`, `--green-100`) carry icon
tiles, the active nav pill and resting chart bars. Type is near-black (`#1d1e22` headings,
`#6e7178` body, `#9a9ca3` muted). Semantics are used sparingly and only for meaning: red `#e0453a`
for a negative delta, amber `#e0a03c` for *Inactive*. Two greys total behind surfaces —
`--page` for the canvas and `--ink-50/75` for nested tiles. No second brand hue exists; don't add one.

**Type.** One family throughout, a geometric humanist sans (see the substitution note below), in four
weights: 500 for nav and table cells, 600 for buttons and small labels, 700 for card titles, 800 for
balances and the page greeting. Tracking tightens to −0.02em at 17px and above and stays at 0 below.
Numerals are tabular and lining everywhere money is shown (`.o-num`). Ladder: 30 / 26 / 20 / 17 / 15
/ 13 / 12 / 11px — compact, and never below 11px.

**Spacing.** 18px inside every card, 16px between cards, 14px shell inset, 196px sidebar, 38px nav
rows, control heights 32 / 38 / 44. Card grid is a 1:2 split — the balance column narrow, the
analytical column wide.

**Backgrounds.** Solid fills only. No photography, no illustration, no texture, no pattern, no
noise. Exactly one gradient exists in the product: the sidebar upsell card, vertical
`--green-600 → --green-800`. A second, softer gradient family lives inside the chart bars, where each
bar fades from its colour at the cap to fully transparent at the baseline. That's it — treat any
other gradient as off-brand.

**Cards.** White, radius 16, 18px padding, no border, and a shadow so faint it reads as flat
(`0 1px 2px rgba(21,22,27,.04)`). Nested tiles inside cards drop to radius 12 on `--ink-75` with no
shadow at all. Depth is expressed by *fill*, not by shadow: sunken grey = nested, white = raised.
Only the shell (`--shadow-shell`) and floating overlays (`--shadow-overlay`) cast a real shadow.

**Radii.** 6 / 8 / 12 / 16 / 20 / pill. Pills for anything interactive and horizontal (buttons,
search, badges, statuses, chart bar caps, progress tracks); rounded squares for containers and icon
tiles. Buttons are never square-cornered.

**Borders.** Almost none. A single hairline `--ink-200` appears on outline buttons (the date pill,
Filter) and between table rows. Cards, inputs and tiles have no border — a fill change does that job.

**Shadows, protection & blur.** No protection gradients or scrim capsules anywhere, because no text
sits on imagery. Transparency appears in two places only: 78%-white body copy on the green upsell
card, and the transparent tail of chart bars. Blur is reserved for modal backdrops
(`rgba(21,22,27,.28)` + 2px blur) — never as decoration, never frosted panels.

**Iconography in layout.** Every card title is preceded by a 28px tinted rounded-square icon tile;
every card header can carry a right-aligned `⋯` overflow. That pairing is the most repeated motif in
the product.

**Hover.** Fills darken one step (`--green-600 → --green-700`, `--ink-100 → --ink-200`); transparent
things pick up `--ink-50`. Never opacity fades, never colour *lightening*, never a shadow lift, never
scale-up on hover. Nav rows fill grey on hover and green-tinted when active.

**Press.** `scale(.985)` with the hover fill retained. No ripple, no shadow change.

**Focus.** 2px `--green-600` outline at 2px offset, or a 3px `--focus-ring` halo on filled controls.

**Disabled.** 45% opacity, `cursor: not-allowed`, colour unchanged.

**Animation.** Restrained and functional: 120ms for control state changes, 180ms default, 280ms for
things that grow (progress fills, chart bars) on `cubic-bezier(.2,.8,.2,1)`. Transitions are on
colour, size and position; there are no entrance animations, no bounces, no parallax, no
scroll-triggered reveals, and no looping motion. If motion is not communicating a state change,
it doesn't exist here.

**Charts.** One chart type only: pill-capped vertical bars fading to transparent, a hairline grid of
`--ink-100` rules, `$k` axis labels in 11px muted grey, month labels bolding to near-black for the
active column. The active bar is saturated green, capped by an 11px dot with a 3px white ring, with a
white radius-12 tooltip floating above it (`--shadow-overlay`, label in 11px grey over the value in
15px bold). Exactly one bar is saturated at a time.

**Layout rules.** Sidebar and top bar are fixed; only the content column scrolls. The upsell card is
pinned to the bottom of the sidebar. The page header (greeting + date pill + Export) sits inside the
scrolling column, not the fixed bar. Content is a 12-column-ish two-track grid, never centred with
max-width — the app fills its shell.

**Imagery.** There is none, beyond the user avatar and small square flag bitmaps. If a design needs
imagery, ask for it rather than importing stock: the product's visual character is white space plus
green, and photography would be a new decision, not an application of this system.

---

## ICONOGRAPHY

**The set.** A 2px-stroke, round-cap, round-join outline set at 16–17px in the chrome and 14–15px
inside icon tiles — geometrically identical to **Lucide**. The source render is a raster, so no icon
files could be copied; the system therefore links Lucide from CDN and wraps it in `Icon`.
**⚠️ Substitution flagged:** if Oripio ships its own icon set (or uses Phosphor / Iconoir / a custom
font), send it and swap the wrapper's implementation — nothing else needs to change.

```html
<script src="https://unpkg.com/lucide@0.474.0/dist/umd/lucide.js"></script>
```

**Names in use.** `layout-grid`, `chart-pie`, `credit-card`, `file-text`, `layers`,
`badge-dollar-sign`, `users`, `settings`, `circle-help`, `log-out`, `search`, `mail`, `bell`,
`chevrons-left`, `chevrons-up-down`, `upload`, `download`, `calendar`, `plus`, `more-horizontal`,
`list-filter`, `arrow-up-down`, `lightbulb`, `wallet`, `piggy-bank`, `banknote`,
`chart-no-axes-column`, `target`, `umbrella`, `house`.

**Rules.**
- Icons are monochrome and inherit `currentColor` — never multi-colour, never filled.
- A card-title icon always sits in a 28px `IconTile` tinted with the pale version of its meaning
  colour (green by default, amber for warnings). A bare icon never precedes a card title.
- Nav icons are un-tiled and take the row's text colour; the active row turns its icon green too.
- Two non-icon glyphs are used deliberately: `⋮` for the wallet-tile menu and `↑ / ↓` inside delta
  badges. `⋯` (`more-horizontal`) is the card-level overflow. Keep that distinction.
- No icon font, no PNG icons, no inline hand-drawn SVG, no emoji-as-icon (see the single 🏆
  exception in copy).

**Logo.** `assets/logo-mark.png` (green rounded-square tile with a white wing/leaf mark) and
`assets/logo-lockup.png` (mark + "Oripio" wordmark) were extracted from the source render, so they
are low-resolution raster crops. **Ask the Oripio team for vector originals** before any print or
large-format use. The mark is never recoloured, outlined, rotated or placed on a busy background;
the wordmark is 20px/700 in `--ink-900` beside a 30px mark with a 9px gap.

---

## Known substitutions & gaps

1. **Fonts — substituted.** No binaries were provided. The render's geometric humanist sans is
   approximated with **Plus Jakarta Sans** (Google Fonts), plus **JetBrains Mono** for the rare
   monospace use (which does not appear in the source at all — it's a reasoned addition for IDs and
   token names). **Please send the real font files or the family name.**
2. **Icons — substituted.** Lucide, as described above.
3. **Logo — low-res raster.** Extracted crops; vectors needed.
4. **Colours — sampled from a JPEG.** Values are accurate to a couple of units, not exact. The red
   and amber semantics in particular were read from antialiased 12px text and should be confirmed.
5. **Only one screen exists.** Analytics, Invoices, Recurring, Subscriptions, Feedback, Settings and
   Help Desk are rendered as explicit blank states in the UI kit rather than invented.
6. **Third-party marks not redistributed.** The source's transaction rows use App Store / Adobe /
   Walmart logos; neutral Lucide glyphs stand in.
