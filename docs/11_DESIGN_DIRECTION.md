# 11 — Design Direction

| | |
|---|---|
| Status | Draft v0.3, amended by decisions 0016, 0017 and 0018 on 2026-11-12 |
| Date | 2026-11-12 |
| Owner | albarami |
| Purpose | Fix how the product looks, moves and tells its story, with values concrete enough to build from and to audit. |
| Read first | [01_PROJECT_BRIEF.md](01_PROJECT_BRIEF.md), [GLOSSARY.md](GLOSSARY.md), [06_PRIVACY_AND_DISCLOSURE_CONTROL.md](06_PRIVACY_AND_DISCLOSURE_CONTROL.md), [10_FRONTEND.md](10_FRONTEND.md), [decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md), [decision 0017](decisions/0017-public-data-additions-and-public-splits.md) |

## In brief

- Nothing is built yet. Every colour, size and duration here is a value to implement; every statement about legibility, frame rate or timing is a target to be measured.
- The look is to be a quiet dark map with one lit layer of evidence at a time and large plain numbers, with a light theme of the same structure for projectors. Version 1 makes that map a living map of Qatar ([decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md)): real roads and business points, synthetic firms and workers as density, and estimated people and traffic that play through the day.
- Impact comes from nine honest moments, not decoration: an opening on real public evidence, the Qatari day hour by hour with the dial, the drawn area through the day, the snap to the grid, the thread behind any number, the flip to Arabic with identical numbers, weights you can change beside a stability sentence, the invitation to break the privacy rule, and a case that starts with one click.
- Every number is a Fact chip. Its class is carried by line style, texture and a word, never by colour alone: solid for Public, dotted for Synthetic, moving dashes for Simulated, grey hatch with a lock for Suppressed. An estimated count always shows its range; a named synthetic firm always carries the Synthetic mark; a Public split or an FDI figure carries the Public mark with its year.
- Simulated animation steps through stored hours only: crowd density and traffic play hour by hour and cross-fade between stored values, never inventing a frame between them. Both use the one five-class magnitude ramp; traffic adds line width as a second cue. Dots and dashes stay reserved for provenance, so a projection is marked by a divider, open markers and a word.
- Type is IBM Plex Sans and IBM Plex Sans Arabic. Digits are Western in both languages. Arabic mirrors the chrome and the reading order, never the map, charts, numerals, the dial or the time controls.
- The guided story has ten scenes on one Stage. It opens on the living map's real public evidence, shows the Qatari day hour by hour, gives the reading guidance, makes the flagship location choice with a drawn area, an event day and traffic by hour, ranks where else fits, then runs costs, the privacy attack, the oversight minute and the four cases as one-click stories, and hands over to free exploration with a permanent Reset.
- No slice that changes the interface passes with an open Blocker or Major design finding.

## 1. Scope, vocabulary and conventions

This document owns appearance, motion, wording on screen, the storyboard and the design audit. [10_FRONTEND.md](10_FRONTEND.md) owns components, state and code: where both speak, this document decides how a thing looks and behaves, and that document decides how it is built. The presenter's script and fallbacks are in [16_DEMO_RUNBOOK.md](16_DEMO_RUNBOOK.md).

The interface vocabulary is pinned (see [GLOSSARY.md](GLOSSARY.md)) and is used here unchanged: Stage (the map), Brief (the answer column), Plan rail, Evidence card, Fact chip, Evidence drawer, Dial, Snap report, Privacy receipt, Trust centre, Proof room, Oversight seat, "Viewing as" badge, Standing strip. Version 1 adds the component names of [10_FRONTEND.md](10_FRONTEND.md): Hour control, Day selector, Month selector, Drawing tools, Ranking panel, Reverse view, Similar areas, What changed, Labour-market view, Firm list, Business list, FDI list, Agency records, Journey home, Case gallery, Case stepper and Sample-file loader. Journeys are written "journey D1" to "journey D7", services "service S1" to "service S3" and cases "case C1" to "case C4". Two axes are never merged. Provenance (Public, Synthetic, Simulated, Suppressed) says where data comes from. Evidence status has exactly three values: Observed, Inferred and Still to test. Not measured is a coverage label.

Every row of a table whose first column is an ID is a requirement. Rows are written in the present tense for brevity; read each as "must". None describes something that exists today.

| ID | Requirement |
|---|---|
| DES-01 | All sizes are CSS pixels. The three layouts and their breakpoints are those of [10_FRONTEND.md](10_FRONTEND.md): wall (1600 px wide or more, or presenter mode, `EII_PRESENTER=1`), laptop (1200 to 1599 px) and tablet (768 to 1199 px), with one notice asking for a larger screen below 768 px. The Wall columns of the tables here apply in presenter mode on its 1920 × 1080 canvas; a window 1600 px wide or more outside presenter mode takes the wall arrangement with the Laptop sizes. The Laptop and Tablet columns are drawn for 1440 × 900 and 1024 × 768. ASSUMPTION for the wide window: the pack does not say which sizes it takes, and 28 px text on a desk monitor would waste the screen. |
| DES-02 | Every colour, type size, space, radius, elevation and duration in the interface is a design token defined in this document and exposed as a CSS custom property with the name given here. A check must fail the build when component code carries a literal colour, font size or duration. |
| DES-03 | A value marked "target" is measured before anyone claims it. A value marked ASSUMPTION is a default chosen here because the binding decisions are silent; each is listed again at the end of this document. |
| DES-04 | English strings in this document are the source text. Arabic strings come from the reviewed string catalogue (open item OI-09). The only Arabic words fixed here are the four provenance words, the three evidence-status words and the separate Not measured coverage label, all pending native review. |

## 2. Design principles

| ID | Principle | Rules in | Rules out |
|---|---|---|---|
| DES-05 | Evidence is the hero. Each screen carries one idea: one hero layer on the Stage, one hero number in a card or caption, one caveat. | One lit layer; a caption of a headline, a Fact chip and a caveat; splitting a crowded scene in two. | Small-multiple dashboards; two hero layers at once; decorative 3D; more than one headline on a screen. |
| DES-06 | Real first. The first thing an audience sees is Public evidence, and Public always has the calmest treatment: solid and still. | Opening on public series; the living map's real roads and business points; real named places with their sources. | Opening on a simulated crowd or a synthetic pay surface; any Synthetic or Simulated figure attached to a real named place or business; a named synthetic firm drawn as a point. |
| DES-07 | Honesty is drawn, not footnoted. Class, coverage and limits are part of the picture. | Line style, texture and word on every number; the standing strip; the watermark; the coverage bar; blanks that explain themselves. | Colour-only coding; a disclaimer slide; Suppressed drawn as zero, as blank land or as a pale value; "Observed" styled so that it reads as "real". |
| DES-08 | Motion must mean something. A thing moves only when a quantity, a class, the stored hour or the camera position changes. | The snap; the dial cross-fade; moving dashes for Simulated; hour-by-hour playback of crowd density and traffic, stepping between stored hours ([decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md), item 19); the thread; short camera moves. | Idle loops, glow, parallax, rolling counters, per-character typing, playback of any other layer through the day, interpolated frames between stored hours, trails. |
| DES-09 | Legible from the back of the room. | A 28 px floor on the wall; 7:1 text contrast; the density of a phone; everything reachable without hover. | Thin or condensed type; tooltips; desktop density on a wall; pure white; large saturated warm fills. |
| DES-10 | Two languages, one truth. Arabic is designed, not translated chrome; numbers and charts are the same object in both languages. | Mirrored reading order; Arabic type rules; Western digits; identical chart geometry. | Arabic-Indic digits; a mirrored map, chart or dial; letter-spaced or slanted Arabic; unreviewed strings. |
| DES-11 | Safe to hand over. A Minister can tap anything without training and can always get back. | A question-first home with the seven decisions, three services and four cases; areas from a pin, a preset radius, a travel time or a drawn polygon; two levels of depth; a permanent Reset. | Modes that need explaining; dead ends; any control that can produce an unprotected or unexplained result, such as a protected figure for a drawn shape without the snap. |

## 3. Where the impact comes from

A map and a chat assistant are no longer remarkable to this audience (design research, 2026-11-11). The impact has to come from what is shown and from how visibly it can be trusted. Nine sources are designed for. Each is a real property of the product, so each can be shown without exaggeration.

| Source of impact | What the audience sees | Why it is honest | Scene |
|---|---|---|---|
| Opening on real public evidence | The living map's real roads and business points; then zones brighten in the order of real electricity growth, and three public figures land with their sources | Every mark is Public; nothing invented is on screen | 0 |
| The Qatari day, hour by hour | Crowd density plays through a stored day, one stored hour at a time; one turn of the dial re-weights who is present and re-lights the city; then an event day plays | Every frame is a stored, released hour; nothing is drawn between hours; the layer, the dial ring and the chips are marked Simulated | 1 |
| The drawn area through the day | A shape drawn around one location shows estimated people with their range hour by hour, an event day beside a regular day, and a drive-time outline that re-forms with the traffic of the hour | The shape is the user's; the estimates are Simulated with ranges and never a building's footfall | 3, act 1 |
| The snap to the grid | The area that was asked for visibly becomes whole release units before any protected figure is read | The animation is the privacy rule itself, and the snap report states what changed | 3, act 2 |
| Follow the thread | A tap on any number draws a line to the units and the source behind it | The path is read from lineage records, not drawn for effect | 5, and everywhere |
| The flip to Arabic | Words change; the numerals stay on screen and do not change | The same fact objects render both languages | 3, act 3 |
| Weights you can change | One weight moves and the ranked areas re-order, with the rank-stability sentence beside every rank | The order is the output of visible criteria and weights; the stability sentence says how firm it is; nothing is advised | 4 |
| The privacy attack | A prepared safety regression shows named-entity pay declined; two shapes returning one identical answer; one fixture id on `POST /api/proof/scene` (PRV-119) selecting two prepared requests; the typed subtraction phrase declined separately; and catalogue rejection, one invalid repair and playbook fallback | The signed fixtures and their outcomes are described as prepared; the unprotected comparison is a labelled replay | 6 |
| A case in one click | One tap starts a company's case story, which ends with a test to run, not a verdict | The case is illustrative, its company fictional and its sample file Synthetic | 8 |

| ID | Requirement |
|---|---|
| DES-12 | Each scene has exactly one signature moment, named in section 11; the flagship scene has three acts and one signature moment for each, and the cases scene one for each case. While a signature moment plays, no other transition longer than 400 ms starts on screen; the continuous motion allowed by DES-50 is exempt. |
| DES-13 | Every moving, textured or extruded element maps to a quantity, a provenance class or a camera position that the screen names. Glow, bloom and other post-processing effects, parallax, decorative particles and sound are not used. |

## 4. Colour

### 4.1 Tokens

The dark theme is to be the default; the light theme is for projectors and bright rooms. The accent and role colours of the dark theme are taken from the Okabe and Ito palette as tabulated by Wong (2011): orange, sky blue, bluish green and reddish purple. The light-theme blue is from the same palette; the other light-theme accent and role colours are darker variants chosen here. All other values are design values of this document.

| Token | Role | Dark theme | Light theme |
|---|---|---|---|
| `--eii-bg` | application background | `#10151C` | `#D8D5CE` |
| `--eii-surface-1` | top bar, Brief, cards, caption plates, standing strip | `#18202B` | `#E2DFD9` |
| `--eii-surface-2` | Evidence drawer, popovers, the expanded card | `#212B38` | `#EBE9E4` |
| `--eii-surface-3` | modal panels (attack replay, pack preview), oversight top bar | `#2B3747` | `#EBE9E4` with a 2 px `--eii-line-strong` border |
| `--eii-line` | decorative dividers and card edges | `#445266` | `#AFACA4` |
| `--eii-line-strong` | control boundaries, chart axes, the Suppressed hatch, the Not measured outline | `#8492A3` | `#6A675F` |
| `--eii-text` | primary text and all numerals | `#E6EAEB` | `#14181D` |
| `--eii-text-2` | secondary text | `#C2CAD3` | `#363D46` |
| `--eii-text-3` | non-essential captions | `#9AA5B1` | `#4E5660` |
| `--eii-accent` | the user's own things: pin, area lines, focus ring, selected state, the "Your inputs" marker | `#E69F00` | `#A85400` |
| `--eii-role-work` | people who work within reach | `#56B4E9` | `#0072B2` |
| `--eii-role-live` | people who live within reach | `#009E73` | `#00735A` |
| `--eii-role-visit` | visitors | `#CC79A7` | `#9C3F7A` |
| `--eii-housing-family` | family housing in the housing split | `#009E73` (same as `--eii-role-live`) | `#00735A` (same as `--eii-role-live`) |
| `--eii-housing-labour` | labour accommodation in the housing split | `#5EBF9A` | `#0E6B4C` |
| `--eii-seq-1` to `--eii-seq-5` | five-class magnitude ramp, low to high | `#2F4A5E` `#3F6F86` `#5E97A6` `#9CC4BB` `#EBE3B0` | `#CBC48E` `#93AD9B` `#63899A` `#3F6680` `#27425A` |
| `--eii-map-land`, `--eii-map-water` | basemap land and water (midday preset; see section 8 for the others) | `#1E2630`, `#121B24` | `#E4E1DB`, `#C3CED6` |
| `--eii-map-road-minor`, `--eii-map-road-major` | roads | `#27313D`, `#3A4757` | `#D6D2CA`, `#C2BEB5` |
| `--eii-map-building` | buildings, base colour before lighting | `#364252` | `#D3CFC7` |
| `--eii-map-boundary` | coastline, municipality and zone lines | `#66758A` | `#75716A` |
| `--eii-map-label-1`, `--eii-map-label-2` | primary and secondary map labels | `#D5DBE0`, `#A3AEBA` | `#22282F`, `#4E5660` |
| `--eii-scrim` | veil behind modal panels | `rgba(16,21,28,0.72)` | `rgba(20,24,29,0.40)` |

### 4.2 Contrast and use

| ID | Requirement |
|---|---|
| DES-14 | All text uses `--eii-text`, `--eii-text-2` or `--eii-text-3`. Accent, role and ramp colours are never used for text. |
| DES-15 | Contrast is computed with the WCAG 2.2 relative-luminance formula. `--eii-text` and `--eii-text-2` reach at least 7:1 on every surface they sit on. `--eii-text-3` and map labels reach at least 4.5:1. Every graphic needed to read the content (control boundaries, chart marks, role colours, the accent, map boundaries, the Suppressed hatch) reaches at least 3:1 against the colour beside it; the classes of the ramp follow DES-20 instead. An automated test must compute these ratios from the token file for both themes and fail the build when any ratio is below its threshold. |
| DES-16 | Television-safe range: every neutral token (background, surface, line, text, map) keeps all three channels between 16 and 235, and no token of any kind has a channel above 235. Pure white and pure black are not used. Source: Microsoft's television design guidance, which names 16 to 235 as the traditional safe range and warns that extreme intensities band or bloom (via the design research). |
| DES-17 | Both themes are complete and pass every requirement in this document. One presenter control switches theme without a reload, with a cross-fade of `--eii-dur-scene`. The theme is chosen at the venue check (DES-142). |
| DES-18 | The accent marks only the user's own things and keyboard focus. It is never a data colour, never a provenance signal and never a fill larger than a pin, a knob or a selected-state marker. Accent lines on the Stage carry a 2 px casing in `--eii-bg` so that they stay visible over any data fill. |

Calculated worst cases for the values above (author's calculation, 2026-11-11; the automated test of DES-15 is the authority):

| Pair | Required | Dark | Light |
|---|---|---|---|
| `--eii-text` on any surface | 7:1 | 9.96:1 | 12.16:1 |
| `--eii-text-2` on any surface | 7:1 | 7.29:1 | 7.49:1 |
| `--eii-text-3` on any surface | 4.5:1 | 4.82:1 | 5.07:1 |
| `--eii-line-strong` on any surface | 3:1 | 3.81:1 | 3.85:1 |
| `--eii-accent` on any surface, land or water | 3:1 | 5.36:1 | 3.34:1 |
| role colours on any surface, land or water | 3:1 | 3.53:1 | 3.24:1 |
| `--eii-map-boundary` on land or water, all lighting presets | 3:1 | 3.26:1 | 3.03:1 |
| `--eii-map-label-2` on land or water, all lighting presets | 4.5:1 | 6.78:1 | 4.65:1 |

### 4.3 Data colour

| ID | Requirement |
|---|---|
| DES-19 | Magnitude uses one five-class ramp, `--eii-seq-1` to `--eii-seq-5`. In the dark theme lighter means more; in the light theme darker means more; every legend states the direction in words. No rainbow ramp, no diverging ramp and no second sequential ramp exists in v1. |
| DES-20 | The ramp varies lightness along a blue-to-yellow axis, the approach of published ramps built for colour-vision deficiency (Nuñez, Anderton and Renslow, 2018). A test must show that CIELAB lightness is strictly monotonic, with a step of at least 10 between neighbouring classes, in normal vision and under simulated protanopia, deuteranopia and tritanopia. Calculated for normal vision: steps of 13.6 to 16.9 (dark) and 10.2 to 14.5 (light). Against the land the lowest class reaches at least 1.3:1 and the highest at least 7:1 (calculated: 1.64:1 and 11.74:1 dark, 1.36:1 and 7.99:1 light); neighbouring units are also parted by the separator of DES-61, and every value can be read from the legend and from "Show as table". |
| DES-21 | Categorical colour is limited to the three role colours, always paired with a fixed glyph, a word and a fixed order: work, live, visit. Ordered breakdowns (wage bands) use the magnitude ramp. The housing split shows `family_housing` with `--eii-housing-family`, `labour_accommodation` with `--eii-housing-labour`, and `institution`, `unknown` and, when pooling occurred, `other` with tints of `--eii-text-2`. The not-measured count is separate from those rows: an unfilled `--eii-line-strong` outline, not a housing class. Every segment has a direct label. Other breakdowns (cost shares, origins, occupation groups `0` to `9`, `unmapped`, and `other` when pooling occurred, and the sex and nationality categories of a Public split, in the order the source publishes them) use tints of `--eii-text-2` with direct labels. No chart uses more than three hues. Both housing tokens and the institutional tint are included in the DES-15 contrast test at 3:1 against the card surface. |
| DES-22 | Colour never carries provenance, evidence status, success or failure. There is no red for bad and no green for good; an outcome is a word with a glyph. |
| DES-23 | A Suppressed, not-measured or no-data element is left out of the ramp and its legend scale. Suppressed is drawn as the grey hatch; not measured and no data are drawn as an unfilled outline in `--eii-line-strong`; each is named in the legend. None is ever drawn as zero, as the lowest class, as unmarked land or as a paler value. |
| DES-165 | Crowd density uses the five-class ramp of DES-19 on release-unit fills, with the Simulated dash texture of DES-66 over every class and the separator of DES-61. Its legend reads "Estimated people per square kilometre", names the day and the stored hour on screen, states the direction in words and shows the class breaks as `compact` chips. The breaks hold for the whole day on screen, so that playback shows change and not a picture re-scaled each hour; they are facts computed by code ([07_ECONOMIC_METHODS.md](07_ECONOMIC_METHODS.md)), never by the interface. Because the ramp's lightness is monotonic and tested under three simulated colour-vision deficiencies (DES-20), the layer reads in greyscale in both themes. ASSUMPTION for the day-fixed breaks: a re-scaled hour would make a quiet hour look as full as a busy one. |
| DES-166 | Traffic is drawn on the road links of the real network in the five classes of DES-19, by simulated speed against free-flow speed: the lowest class nearest free flow, the highest slowest. Line width is a second cue: it steps evenly from the data-outline width to the area-line width of the mark table in section 9.1, and the legend shows each class as a line sample of its width. Road links carry the Simulated dash as a static texture: dashes moving along a road would read as vehicles in motion, which DES-147 forbids, so the motion stays on the legend sample and the chip underline (the form DES-67 already allows). Links in the lowest class sit quietly over the basemap's own road lines. No red, amber or green is used, and no colour stands for good or bad (DES-22). The legend reads "Simulated traffic: speed against free flow" and states the direction in words. |

## 5. Typography

### 5.1 Families and scale

| ID | Requirement |
|---|---|
| DES-24 | Latin text is set in IBM Plex Sans and Arabic text in IBM Plex Sans Arabic, both under the SIL Open Font Licence 1.1 (IBM Plex repository, retrieved 2026-11-11). The font files and the licence text are served by the application; no font is fetched from a third-party host at run time. |
| DES-25 | Weights used: Regular 400, Medium 500 and SemiBold 600 in each family (availability to be confirmed in the font files at slice S0). Thin, light, condensed and italic styles, and bold or oblique styles synthesised by the browser, are not used (thin and condensed faces read more slowly at a glance: Nielsen Norman Group, via the design research). |
| DES-26 | No audience ever sees a fallback typeface: fonts are loaded before the first screen is shown, and a visual test compares the rendered face in both languages. |
| DES-27 | Sizes follow the scale below. No text is smaller than 28 px on the wall (the floor in published television design guidance, via the design research) or 14 px on laptop and tablet. |
| DES-28 | Arabic text is set at 1.12 times the Latin size of the same role, rounded to a whole pixel, with a line height of 1.6 times its own size (for example 36/58 for body text on the wall). ASSUMPTION: a design judgement from the design research (about 10 to 15% larger) and from the W3C note that Arabic ascenders and descenders extend further than Latin ones; the native reviewer confirms it. |
| DES-29 | Room scale: presenter mode offers a factor of 1.0, 1.15 or 1.3 applied to every wall type token, chosen at the venue check. No layout clips, overlaps or scrolls at 1.3. As an estimate drawn from the design research's reading of a published display-size standard, factor 1.0 serves a farthest viewer about three image heights away. ASSUMPTION: the room is unknown (open item OI-02), so the scale must be adjustable. |

Sizes are font size / line height in pixels for Latin text.

| Token | Use | Wall | Laptop | Tablet | Weight |
|---|---|---|---|---|---|
| `--eii-type-display` | scene headline | 72/80 | 40/48 | 32/40 | 600 |
| `--eii-type-title` | card and section titles, dial centre | 40/48 | 22/28 | 20/28 | 600 |
| `--eii-type-body` | Brief sentences, caption text | 32/44 | 16/24 | 16/24 | 400 |
| `--eii-type-label` | buttons, legends, map labels, class words | 28/36 | 14/20 | 14/20 | 500 |
| `--eii-type-caption` | period, source and caveat lines, in `--eii-text-2` | 28/36 | 14/20 | 14/20 | 400 |
| `--eii-num-hero` | the one Stage caption figure of a screen | 120/120 | 64/64 | 56/56 | 500 |
| `--eii-num-large` | the hero fact of a card | 64/68 | 36/40 | 32/36 | 600 |
| `--eii-num-standard` | supporting facts | 40/48 | 22/28 | 20/28 | 600 |

### 5.2 Numerals

| ID | Requirement |
|---|---|
| DES-30 | Digits are Western (0 to 9) in both languages. Every displayed number is produced by deterministic tested code in `eii_core.calc`, the release build, or a fixed application-schema read function listed by the data contracts and covered by tests. Nothing else computes, rounds or compares a number, and no model ever does; the browser never computes a comparison or an aggregate, and only formats values it receives. Numbers, percentages, dates and compact forms are formatted by the platform's internationalisation functions: for Arabic with the locale `ar-QA-u-nu-latn` and the Gregorian calendar, for English with the locale pinned in [10_FRONTEND.md](10_FRONTEND.md). The browser default for Qatar Arabic is Arabic-Indic digits, so the numbering system is always stated (Unicode CLDR, via the design research). No number string is assembled by hand, and a date always shows its month as a word. |
| DES-31 | Every numeral is set in IBM Plex Sans in both languages, with lining figures of equal advance width. A test must measure the ten digits at each numeral size and fail if their widths differ. The tabular-figure feature of the font was not confirmed for this pack; if the shipped file lacks it, the Fact chip lays each digit in a fixed cell 0.6 em wide. ASSUMPTION: the fixed cell is the simplest fallback that keeps one typeface. |
| DES-32 | A numeral never animates through intermediate values. When a fact changes, the old value cross-fades to the new one in `--eii-dur-fast`. No counting-up, rolling or odometer effect exists, because a photographed intermediate value would be a false number. |
| DES-33 | A range is one isolated left-to-right run with the lower bound on the left and an en dash, in both languages. A change carries an explicit plus or minus sign and a word from the catalogue, never an arrow or a colour alone. ASSUMPTION: lower bound on the left matches the unmirrored charts; the native reviewer confirms it for Arabic. |
| DES-34 | The interface never changes precision: it prints the value the fact carries, rounded as released, and adds no decimals. |
| DES-167 | An estimated count is always shown with its range. On a chip the estimate is the value, and the range sits beneath it in caption size as one range run (DES-33) after the word "Range"; the chip's label is "Estimated people around this location" or its short catalogue form. In a chart, each estimate is a bar in its class texture and its range is a thin interval line in `--eii-line-strong` with flat end caps no wider than the bar, drawn over the bar; the legend names it "Range of the estimate". A range is never a band of colour alone, never dotted or dashed, and never left out to save space. The range is the one the fact carries, as the method of [07_ECONOMIC_METHODS.md](07_ECONOMIC_METHODS.md) defines it and its Source chain names. |

### 5.3 Line length and text blocks

| ID | Requirement |
|---|---|
| DES-35 | Running text is set at 45 to 75 characters a line on laptop and tablet, never more than 80 (WCAG 2.2, criterion 1.4.8), and at 30 to 50 on the wall. Text is aligned to the start edge, never justified and never hyphenated. A headline has at most two lines and a caption at most three. |
| DES-36 | On the wall no panel scrolls. The Brief shows one section at a time, and text that does not fit is paged with a visible "More" control. A prepared story answer fits its panel without paging at room scale 1.0 in both languages. ASSUMPTION: scrolling text cannot be read from a distance. |

### 5.4 Arabic typographic rules

| ID | Requirement |
|---|---|
| DES-37 | Arabic text has zero letter spacing everywhere, including labels that are letter-spaced or upper-cased in English. Emphasis uses weight or size, never slant, tracking or stretched joins. Source: W3C Arabic layout requirements, which state that moving joined letters apart or together gives undesirable results. |
| DES-38 | The Fact chip root is a `bdi` isolate in the page direction. The numeric value, the range, the identifier and any Latin name are each an inner left-to-right isolate with `lang` set to `en`. Arabic words inside the chip keep the page direction and `lang=ar`. Every other Latin name, identifier and code inside Arabic text outside a chip is an isolated left-to-right run (the `bdi` element or an equivalent isolate) with its own language attribute. Text of unknown direction, such as a place name from a public source, sits in its own isolated run with automatic direction. Source: W3C guidance on inline bidirectional markup, via the design research. |
| DES-39 | Text is never revealed character by character. After the accounting gate has passed, a brief item may be revealed for legibility a sentence at a time, or a word at a time at the least, because Arabic letters change shape as their neighbours arrive (joining forms: W3C Arabic layout requirements). The rule applies to both languages. Evidence cards may appear earlier. |
| DES-40 | Line boxes never clip Arabic marks: no single-line box is lower than 1.6 times its font size, and no text line that can carry marks has hidden overflow. Headlines wrap; they are never cut with an ellipsis. |
| DES-41 | Prepared Arabic strings are Modern Standard Arabic and are reviewed by a native reader before an audience sees them (open item OI-09). An unreviewed string on a presented screen is a Blocker in the design audit. |

## 6. Space, grid, elevation and icons

Spacing tokens: `--eii-space-1` to `--eii-space-9` are 4, 8, 12, 16, 24, 32, 48, 64 and 96 px. Radius tokens: `--eii-radius-s` 6 px (chips), `--eii-radius-m` 12 px (cards), `--eii-radius-l` 20 px (drawers and sheets).

| Property | Wall | Laptop | Tablet |
|---|---|---|---|
| Safe margin, inline and block | 96 and 54 px (5% of the canvas) | 32 and 24 px | 24 and 16 px |
| Columns and gutter | 12 and 24 px (column 122 px) | 12 and 16 px | 8 and 16 px |
| Top bar height | 72 px | 56 px | 56 px |
| Standing strip height, one row | 56 px | 36 px | 36 px |
| Brief width | 5 columns (706 px) | 4 columns (448 px at 1440) | bottom sheet, full width |
| Card padding and gap | 24 and 16 px | 16 and 12 px | 16 and 12 px |
| Minimum target size | 44 × 44 px (buttons are 56 px high) | 24 × 24 px | 44 × 44 px |
| Focus ring | 4 px accent, 4 px offset | 3 px, 3 px offset | 3 px, 3 px offset |

| ID | Requirement |
|---|---|
| DES-42 | Layout uses the spacing tokens and the grid above. Essential content stays inside the safe margins; only the Stage, the scrim and the watermark reach the screen edge. |
| DES-43 | Elevation has four levels, shown by surface tone and a line: level 0 the Stage; level 1 `--eii-surface-1` with a 1 px `--eii-line` edge; level 2 `--eii-surface-2` with the shadow `0 8px 24px rgba(0,0,0,0.45)` (dark) or `0 4px 16px rgba(20,24,29,0.18)` (light); level 3 `--eii-surface-3` above `--eii-scrim`. Panels are opaque: no translucent or blurred panel sits over the map. |
| DES-44 | Every interactive element meets the target size in the table (the minimums of [10_FRONTEND.md](10_FRONTEND.md); WCAG 2.2 sets 24 px as the minimum and 44 px as the enhanced level), has a visible focus ring, and works by keyboard, pointer and touch. Nothing is revealed by hover alone. |
| DES-45 | Icons are one outline set on a 24 px grid with a 2 px stroke (wall: 40 px and 3 px), vendored locally, with the licence recorded in the repository. An icon never stands alone for a meaning the audience must get: it sits beside its word. ASSUMPTION: the Carbon icon set, whose repository is licensed Apache 2.0 (retrieved 2026-11-11; the icons package licence is to be confirmed at slice S0), because it is the icon set of the design system that uses IBM Plex. |
| DES-46 | Custom glyphs are drawn once and reused everywhere: the four provenance line samples; the lock (Suppressed only); the three evidence-status shapes and the separate Not measured outline; pin; hexagon; dial; thread; receipt; the three role glyphs; the three seat glyphs; play and pause for the Hour control; the three event days; the polygon, radius and travel-time tools; the range mark; the projection's open marker; the case and sample-file glyphs. No glyph depicts an eye, a camera, a tracked person or a vehicle. |
| DES-47 | No State emblem, ministry lockup, official typeface or national-identity colour scheme is used. The wordmark is the working title set in IBM Plex Sans SemiBold: its short form "EII" in the top bar, the full title on the home screen and the briefing pack (open items OI-05 and OI-06). Any official identity needs written permission from its owner first; the brand guidelines published by the Government Communications Office restrict the emblem and parts of the palette (via the design research). |

## 7. Motion

| Token | Value | Use |
|---|---|---|
| `--eii-dur-fast` | 150 ms | press, focus, value swap, word cross-fade |
| `--eii-dur-base` | 250 ms | card expand, section change, the snap itself |
| `--eii-dur-slow` | 400 ms | drawer, sheet, card landing, thread, dial knob |
| `--eii-dur-scene` | 800 ms | layer cross-fade, lighting change, theme change |
| `--eii-dur-fly-short`, `--eii-dur-fly-medium`, `--eii-dur-fly-long` | 1,200, 2,500 and 3,500 ms | camera: door to door, city to door, country to city |
| `--eii-ease-enter` | `cubic-bezier(0.16, 1, 0.3, 1)` | things arriving |
| `--eii-ease-exit` | `cubic-bezier(0.7, 0, 0.84, 0)` | things leaving |
| `--eii-ease-move` | `cubic-bezier(0.65, 0, 0.35, 1)` | things that stay on screen and move; the camera |
| `--eii-stagger` | 60 ms an item, 300 ms in total at most | lists, release units, chain nodes |
| `--eii-dash-speed` | 24 px a second, linear | moving dashes (Simulated) |
| `--eii-hour-hold` | equal to `--eii-dur-fly-medium` (ASSUMPTION: a starting value, tuned at the visual review of the flagship) | how long each stored hour stays on screen during playback |

| ID | Requirement |
|---|---|
| DES-48 | All motion uses these tokens; a hold between two motions is stated where it occurs. There is no bounce, overshoot or elastic easing. |
| DES-49 | Camera: a scripted move lasts at most 3,500 ms. In the guided story, input is ignored during a scripted move and Next jumps to the scene's end state; in exploration any input interrupts a move at once. Pitch never exceeds 55 degrees, so no horizon is drawn. Drift, a change of bearing of at most 0.5 degrees a second, is allowed only in scenes 0 and 9; there is no continuous orbit. |
| DES-50 | Continuous motion is limited to the Simulated moving dashes, the drift of DES-49, the hour playback of DES-168 and, where used, the flow particles of DES-62. A "Pause motion" control is reachable on every screen in at most two taps and stops all four (WCAG 2.2, criterion 2.2.2, asks for a way to pause motion that starts by itself and lasts more than five seconds). |
| DES-51 | Reduced motion applies when the operating system asks for it, when "Pause motion" is on, or when the presenter sets it for a display that smears movement. Then: a camera move is a cut with a cross-fade of `--eii-dur-base`; cross-fades shorten to `--eii-dur-fast`; the snap shows its end state and report at once; moving dashes become static dashes of the same length; the dial knob jumps; drift, stagger and particles are off; hour playback does not start and the hour changes only when the user steps it; the thread appears whole. Every class and state stays distinguishable. |
| DES-168 | Hour playback shows only the hours the release stores. Each stored hour holds for `--eii-hour-hold` and then cross-fades to the next in `--eii-dur-scene`; no frame, fill or value between two stored hours is ever drawn, and the chips of the hour cross-fade as DES-32 sets, never counting through values. Only crowd density and traffic play ([decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md), item 19), each marked Simulated throughout. Play and Pause sit on the Hour control, playback stops at the last stored hour of the day, and the lighting does not animate with the hour (DES-59). |
| DES-52 | Waiting is shown without spinners. Progress is the Plan rail's steps completing; a loading card or chip is a skeleton block in `--eii-surface-2` with no shimmer and no placeholder numeral. A wait longer than 2 seconds shows one plain sentence saying what is being fetched. The pack's latency targets are targets to be measured: evidence within 2 s; the checked brief within 6 s when no live model is called (template writer or recorded provider) and within 20 s when a live model composes it. The brief stays buffered until the accounting gate has passed; evidence cards may appear earlier. |

## 8. The map

The Stage is to be one self-hosted vector basemap restyled with the map tokens, with data layers interleaved beneath its labels. The map and overlay libraries are newer than most model training data: before writing the style or a layer, the builder must read the current official MapLibre GL JS and deck.gl documentation. Exact version pins are confirmed at the spike in slice S1 with written retreat pins (see [10_FRONTEND.md](10_FRONTEND.md)).

| ID | Requirement |
|---|---|
| DES-53 | The basemap is quiet. Its style starts from the `dark` flavour of the Protomaps basemap style in the dark theme and the `light` flavour in the light theme (Protomaps documentation, retrieved 2026-11-11), with every colour overridden by the map tokens. It draws land, water, a 1 px coastline in `--eii-map-boundary`, two road classes, municipality and zone boundaries, buildings and labels. Points of interest, land-use colours, transit symbols, terrain shading and numeric-only labels (house numbers, road reference numbers) are removed. The attribution text that the data licences require is always visible in `--eii-type-caption` at the inline-end of the Stage footer row, the one row directly above the standing strip. |
| DES-54 | Every named place on the Stage other than a basemap label comes from the gazetteer, the public places table or a public listing, and is therefore a Public fact with lineage. No Synthetic or Simulated figure is placed on, inside or beside a real place's label or marker; synthetic aggregates are drawn as release-unit fills or as separate strips. The living map's real business points are solid Public dots; while a Synthetic or Simulated hero layer is on they carry no label, and a tap opens their Public facts in a Public-only panel. A named synthetic firm is never on the Stage as a point, label or marker; selecting one outlines its area only. |
| DES-55 | No label is drawn outside Qatar's land and coast by default. The name of the sea and of any neighbouring territory appears only from an allow-list approved by the owner. ASSUMPTION: hiding is the simplest safe default until the owner reviews the names in both languages. |
| DES-56 | Labels follow the hierarchy below, in the interface language only. Tiers 1 to 3 have reviewed names in both languages before slice S3 passes. A road with no name in the interface language is left unlabelled, not shown in the other script. Labels sit above all data fills, with a 2 px halo in `--eii-map-land` and no blur. Map labels use the self-hosted map glyph faces named in [10_FRONTEND.md](10_FRONTEND.md) (Noto Sans and Noto Sans Arabic); Arabic labels are shaped by the map library itself (MapLibre GL JS release notes, version 6.9.0, retrieved 2026-11-11). ASSUMPTION for the road rule: mixed scripts on one map look careless to this audience. |
| DES-57 | Buildings are flat footprints below zoom 14 and extruded from zoom 14 in `--eii-map-building` at 0.9 opacity, with the heights resolved by [10_FRONTEND.md](10_FRONTEND.md) (the basemap height where present, the estimation rule set at slice S1, a curated list of landmark heights). No shadow is cast or drawn by any library or effect. Buildings are context only: their height, colour and outline never encode data, no building is highlighted as the subject of a figure, and the legend says "Building heights are estimates." whenever buildings are extruded. |
| DES-58 | Height never encodes data in v1. Every data layer is a flat fill, line or point on the ground plane. |
| DES-59 | Lighting has the three presets below, tied to the dial. It is indicative and is not computed from the sun's position. A preset changes the light on extruded buildings in both themes and, in the dark theme only, the land and water tones; the light theme keeps one basemap so that its contrast does not move. A preset change cross-fades in `--eii-dur-scene` together with the presence layer. The summer switch does not change the lighting, and Friday evening shares the evening preset on purpose: the dial label, not the light, tells them apart. With an event day selected, as when no dial is shown, the lighting is `midday`. During hour playback the lighting keeps its preset and does not animate with the hour, so that the only thing changing is the data. ASSUMPTION: the values are starting points, tuned at the visual review of slice S6. |
| DES-60 | Camera framings are computed, not hard-coded. "Country" fits the national boundary with 8% padding at pitch 0, north up. "City" fits the Greater Doha grid extent at pitch 45 degrees and bearing minus 15 degrees. "Door" centres the pin in the free part of the Stage (outside the Brief, the plates and the unfolded dial) so that the snapped area fills 70% of that part's shorter side, within 5 points, at pitch 50 degrees. Reset returns to "city". |
| DES-61 | Release-unit fills are drawn at 0.85 opacity with a 1 px separator in `--eii-map-land`. The Stage shows one hero layer and one snapped outline at a time: those of the active card. It never shows outlines of several unit sets together. |
| DES-62 | Flow particles are the `flows` hero layer of [10_FRONTEND.md](10_FRONTEND.md) and appear only as that layer, never over another hero layer. Each is a 3 px dot that lives at most 1.5 seconds on a straight or gently arced line between the centres of two release units, never along a road and never with a trail; density follows the released flow value; the legend says "Simulated flows between areas. A dot is not a person, a vehicle or a trip." Under reduced motion the layer shows static dashed lines between the same centres. No scene of the guided story uses this layer. ASSUMPTION: the pack defines the layer but names no scene that needs it, so this document only limits how it looks. |

| Tier | What | Source | Shown at zoom (target) | Style on the wall |
|---|---|---|---|---|
| 1 | Municipalities | frame table `municipality` | up to 10 | label size, weight 600, `--eii-map-label-1`; upper case and 0.08 em tracking in English only |
| 2 | Zones (public zone code and name) | frame table `zone` | 10 to 13 | label size, weight 500, `--eii-map-label-1` |
| 3 | Showcase areas and landmarks | `gazetteer` | 11 and above | label size, weight 500, `--eii-map-label-1` |
| 4 | Major roads | basemap | 13 and above | caption size, `--eii-map-label-2` |
| 5 | Public places, when a places layer is on | `pub_place` | with the layer | label size beside a solid marker; name as published, isolated |

Light angles follow the MapLibre style specification's light position (retrieved 2026-11-11): the azimuthal angle is clockwise from north with the map anchor, and the polar angle is 0 directly overhead.

| Preset | Dial situations | Light azimuth and polar angle | Light colour and intensity | Dark-theme land and water |
|---|---|---|---|---|
| `midday` | `weekday_lunch`; also the default when no dial is shown | 180 and 25 degrees | `#EBEBEB`, 0.30 | `#1E2630`, `#121B24` |
| `sunset` | `ramadan_iftar` | 270 and 75 degrees | `#EBC79F`, 0.50 | `#211F27`, `#141820` |
| `evening` | `weekday_evening`, `friday_evening` | 315 and 50 degrees | `#A9B9D6`, 0.20 | `#161D26`, `#101820` |

## 9. Provenance and evidence-status language

### 9.1 The four classes

Arabic words are proposals pending native review. On a line of width w, a dot is w across with gaps of 2w, and a dash is 4w long with gaps of 2w.

| Class | Line | Fill texture | Word and extras | Motion |
|---|---|---|---|---|
| Public · عام | solid | solid fill | the word | none |
| Synthetic · اصطناعي | dotted, round dots | regular dot grid | the word | none |
| Simulated · محاكاة | dashed | rows of short dashes, alternate rows offset by half a period | the word | dashes move at `--eii-dash-speed` |
| Suppressed · محجوب | none: no value is drawn | continuous 45 degree hatch in `--eii-line-strong`, no data colour | the word, the lock glyph and "Why can't I see this?" | none |

| Mark | Wall | Laptop and tablet |
|---|---|---|
| Chip underline thickness | 3 px | 2 px |
| Dot texture | 4 px dots at a 10 px pitch | 3 px dots at an 8 px pitch |
| Dash texture | 16 × 3 px dashes, 8 px gap, rows 10 px apart | 12 × 2 px dashes, 6 px gap, rows 8 px apart |
| Hatch | 2 px stroke, 8 px spacing | 1.5 px stroke, 6 px spacing |
| Data outline and area line | 2 px and 4 px | 2 px and 3 px |

| ID | Requirement |
|---|---|
| DES-63 | The four classes are drawn exactly as in the tables, in every theme, layout, chart, map layer and export. The mapping is fixed: nothing else in the interface uses a dotted line, a dashed line, a dot grid, a dash texture, a diagonal hatch or a lock; a projection, a range and a drawn shape are therefore never dotted or dashed. The one variation is the traffic layer, whose Simulated dashes stay still on the road links (DES-166). |
| DES-64 | Class is readable without colour and without motion: a greyscale screenshot and a single still frame each let a reviewer name the class of every number and layer. A static dash is at least four times as long as a dot is wide. |
| DES-65 | The class shown is the fact's `provenance` field, which the code computes with the least-real rule. The interface never decides, upgrades or hides a class. A composite shows its least-real class on the chip and every input class in the Evidence drawer. |
| DES-66 | Texture marks over a filled class are drawn in the theme's darkest neutral (`--eii-bg` in the dark theme, `--eii-text` in the light theme) at 80% opacity, so that every class of the ramp shows its texture at 1.5:1 or better (calculated minimum: 1.78:1 dark, 1.58:1 light). Textures keep a constant size on screen at every zoom, within the tolerance the overlay library documents for pixel-sized patterns (deck.gl documentation, fill style extension, retrieved 2026-11-11: within a factor of the square root of two), and run unbroken across neighbouring units of one layer. |
| DES-67 | The technique for moving dashes on map fills and outlines is chosen in [10_FRONTEND.md](10_FRONTEND.md) and proved before the first Simulated layer ships; the overlay library's documented dash extension has no control for dash phase (deck.gl documentation, path style extension, retrieved 2026-11-11). If the technique cannot hold the frame-rate target, the written fallback is a static dash texture on the map, with motion kept on the legend sample, the dial ring, the chip underline and the area line drawn above the map. |
| DES-68 | Every data layer on the Stage has a legend plate at the upper inline-start of the Stage: what is shown, unit and period; five swatches from low to high, left to right in both languages, with their breaks as `compact` chips; the direction in words; the class word with its line sample; swatches for Suppressed, not measured and no data whenever one of them is in view; and the "Show as table" control of [10_FRONTEND.md](10_FRONTEND.md). |
| DES-69 | Evidence status is a separate language and never shares a mark with provenance. Its three words are Observed (مرصود), Inferred (مستنتج) and Still to test (يحتاج إلى اختبار), Arabic pending native review. Each is a word with a shape glyph (filled disc, ring or open diamond) on a Brief section or sentence. Not measured (غير مقيس, pending native review) is a coverage label, not an evidence status; it is drawn as an unfilled outline in `--eii-line-strong` with its word and is never hatched or zero. |
| DES-70 | "Observed" never makes a Synthetic or Simulated number read as real: every chip inside an Observed sentence keeps its own class line, and an Observed section that contains such chips names their classes at its end. |

### 9.2 The Fact chip

The Fact chip is the only component allowed to render a numeral. The values in this sketch are illustrative, not data.

```
QAR 6,000–8,000  (i)        1 value and unit      2 caveat glyph
· · · · · · · · ·           3 provenance line (dotted = Synthetic)
Synthetic · Q2 2026 · △ Small count     4 class word   5 period   6 reliability mark
```

| ID | Requirement |
|---|---|
| DES-71 | The chip family has the four variants of [10_FRONTEND.md](10_FRONTEND.md): `value`, `compact`, `input` and `reference`. The `value` variant has four sizes: `hero` (one Stage caption figure a screen), `large` (a card's hero fact), `standard` and `inline` (inside a sentence, body size, weight 600). The `compact` variant (axis, legend and bar labels) uses the label size. |
| DES-72 | Parts of a `value` chip, in reading order: the value with its unit; for an estimated count, its range (DES-167); the provenance line directly under the value and never under a word (for Suppressed, a hatched block with the lock in place of the value); the class word; period and geography in `--eii-type-caption`; the reliability mark, an open triangle with the words "Small count", shown only when the fact's `reliability` field marks a small count (the bands are in [03_DATA_CONTRACTS.md](03_DATA_CONTRACTS.md)); a caveat glyph where the fact carries caveat keys. Unit strings and their side of the value come from the reviewed catalogue. |
| DES-73 | `value` chips at `hero`, `large` and `standard` size always show the class word. `inline` and `compact` chips keep the provenance line but may leave the visible word out (it stays in the accessible name), because the provenance legend is always on screen and their container (a sentence group, a chart, a legend) names the classes it holds. The exception is DES-169: a chip from a dataset added by decision 0017, a Public split or an FDI project keeps its year visible at every size. ASSUMPTION: one word on each of five axis labels lowers legibility on a wall and adds no information. |
| DES-74 | Every chip is a button. One tap, click or Enter opens the Evidence drawer for its fact. The provenance line doubles as the sign that the number can be opened, and the hit area meets the target size even where the glyphs are smaller. |
| DES-75 | A chip never shows a value the release does not carry. A fact without a complete source chain is not rendered: the chip refuses it, the validator rejects the brief and the release build fails (the sanad rule). `SUPPRESSED` shows the hatch, the lock and the word. `NO_DATA` shows the words chosen by the application's template (Not measured or No data) with the reason one tap away. A loading chip is a skeleton. None of these shows a zero, a dash or "N/A" (official statistics guidance keeps zero for a true zero: UK Government Analysis Function, via the design research). |
| DES-76 | A value the user chose or typed (an area cut-off or radius preset; a ranking weight; the calculator's rent, seats and average bill) is rendered by the `input` variant: an accent square marker and the words "Your inputs", with no provenance line. A figure computed from such values keeps the "Your inputs" marker, shows the provenance line of the least-real class among its other inputs, and sits in an Inferred sentence or section. ASSUMPTION for area cut-offs: [10_FRONTEND.md](10_FRONTEND.md) names the variant for calculator inputs only, and a cut-off is equally the user's own choice. |
| DES-77 | Chrome carries no visible numerals: the story stepper shows dots and the scene title, the dial shows situation names, and counts of steps or attempts are not displayed. The one exception is the time controls: the hour labels of the Hour control, the month labels of the Month selector and a retrieval date in a source line are `reference` chips, formatted as DES-30 sets, with the month always a word. Digits that belong to an identifier or a code (a release identifier, a brief identifier, a rules version, an activity or classification code) are rendered by the `reference` variant, which carries no provenance line. Labels drawn inside the map canvas follow the basemap-label rule of [10_FRONTEND.md](10_FRONTEND.md). ASSUMPTION for codes and rules versions: that document names the variant for release and brief identifiers only. |
| DES-169 | A chip of a figure from the portal datasets added by [decision 0017](decisions/0017-public-data-additions-and-public-splits.md), of an official Public split or of an announced investment project shows its class word followed by its reference year or month ("Public · 2023") on every variant and size, `inline` and `compact` included, because the age of these figures varies from one dataset to the next. The card or list that holds them names the source and its geography under its title and gives the retrieval date in its footer source line (DES-82). |

### 9.3 Standing strip, watermark and badge

| ID | Requirement |
|---|---|
| DES-78 | The standing strip is docked at the bottom of every screen, seat, room and modal, above the scrim, with the provenance legend in the same band at its inline-end. On the wall the strip occupies the 56 px immediately above the 54 px bottom margin. Its text sits entirely inside the safe area. The Stage may paint the margin below the strip. In the guided story both dock within the first three seconds of scene 0, before the first figure appears; anywhere else they are present from the first frame. They cannot be hidden, collapsed or covered. The strip holds the notice "Demonstrator. Only figures marked Public describe Qatar."; the legend shows the four classes, each a live sample of its line with its word, with the class of the hero layer now on the Stage outlined in `--eii-line-strong`. The band may wrap to two rows and never truncates. ASSUMPTION for the wording: a short form of the binding honesty position that fits one row on the wall. |
| DES-79 | The watermark is drawn inside the map canvas, so that a capture of the canvas carries it, and on every exported page. It has two parts. A tile repeats across the whole Stage at 20 degrees: the word "Demonstrator" and the word of the least-real class now on the Stage (the word "Demonstrator" alone when no data layer is drawn), in `--eii-text` at 14% opacity (dark) or 20% (light), about 1.5:1 against the land. The tile is set in `--eii-type-label`, which is 28 px on the wall, at the opacities already stated. A full-contrast stamp at the inline-start of the Stage footer row lists "Demonstrator" and every class now on the Stage, least real first, in `--eii-type-label`. Any 960 × 540 px crop of the wall Stage contains the complete tile text at least once; a visual test samples crops to check it. The text is computed from the layers on the Stage and cannot be switched off. ASSUMPTION for the two-part form: a faint tile survives cropping and a clear stamp survives a photograph. |
| DES-80 | The "Viewing as" badge sits at the inline-start of the top bar on every screen and in the header of every export. It shows the seat glyph and the words "Viewing as:" with the seat's display name: "Company A (fictional)", "Company B (fictional)" or "Oversight". Its content comes from the session's seat (`company_a`, `company_b`, `oversight`), never from interface state; it cannot be edited or dismissed. Seats differ by glyph and words, not by colour. |
| DES-81 | Each company seat shows, beside the ask bar, the standing sentence "Questions asked here appear in the oversight ledger. The oversight seat does not show which organisation asked." ASSUMPTION: this follows the default of open item OI-08; the owner rules on the wording. |

## 10. Components

### 10.1 Evidence card, Brief and Plan rail

| ID | Requirement |
|---|---|
| DES-82 | Card anatomy, top to bottom: (1) a title in plain words, with the card's class word and line sample (the least-real class among its facts, computed in code); (2) one `large` Fact chip; (3) at most two supporting visuals, a list among them showing at most six rows on the card face; (4) the coverage bar, on every card whose facts carry coverage keys; (5) one caveat sentence chosen by the application from the caveat keys; (6) a footer: "More evidence", "Why can't I see this?" when anything is withheld, the period, the short release identifier and, on a card holding Public facts from the added portal datasets or the two investment sources, a source line naming each source with its retrieval date. The two pay cards are the exception: each may show the count, the quartile range and the band bar, and the residents' card also shows the housing split, besides the median band. Every catalogue component obeys DES-94's place rule: a Synthetic or Simulated fact appears only when that component's subject is an area (the shape the user drew or the area around the pin), or, for a named synthetic firm's own record, that fictional firm; never a real named place. |
| DES-83 | Card states: collapsed (one row, 72 px high on the wall: the title, then the hero fact as a `standard` chip with its class word on the same line), expanded, loading (skeleton), suppressed (hatch, lock, the reason sentence and the nearest publishable alternative as a button), no data (the template's sentence and its reason), and error (one sentence and a Retry control, with evidence already shown left in place). On the wall at most one card is expanded at a time. |
| DES-84 | The coverage bar shows the C8 Public proxy from the finest admitted geography (PUB-82) and names that geography. Its remainder is labelled "outside this proxy", never Not measured. The separate protected `not_measured_count` comes only from `resident_pay` on `rp_housing_count` and appears beside the housing split as its own population. |
| DES-85 | Mean wage and wage bill never appear on a card face. They sit under "More evidence", directly beneath the fixed sentence "The average alone is not enough." The one exception is the reading-guidance pair of scene 2, where the two means are the subject. |
| DES-86 | The licensed-versus-operating strip, like any Synthetic aggregate, never shares a container, list or row with real named places. It is its own strip with its own title, class word and dot texture, at least 32 px away on the wall and 24 px elsewhere. |
| DES-87 | Charts are plain: bars start at zero; axes are never truncated; labels are direct; no pie, no 3D, no gridlines beyond a baseline in `--eii-line-strong`. A chart's geometry is identical in both languages. |
| DES-88 | The Brief column holds, top to bottom: the Plan rail, the Understanding chips, the decision sentence (lead and cheapest test, from the application-owned template keyed by `decision_template_key`), the validated layout (catalogue components only; an invalid layout shows the playbook default), then the evidence-status sections Observed, Inferred and Still to test under their word and glyph, followed by the separate coverage section Not measured. Each Observed and Inferred sentence is a claim-catalogue template filled only by Fact chips; no model-written sentence is on screen. On each Inferred sentence the strength word (`strong`, `indicative` or `illustrative`) sits beside the evidence-status glyph. No sentence appears before the evidence it refers to is on screen. A declined question shows a scope card with three in-scope suggestions in place of the sections. The footer holds the short release identifier, the Privacy receipt link (including the accounting-gate result under the label "Checked before display"; Arabic label pending the owner's review), the action row, Regenerate (enabled only when the mode is `live`) and the status words of DES-89 that describe this answer. |
| DES-89 | Status badges are a word with a glyph on `--eii-surface-2`, never a colour alone: "Prepared" on a replayed answer, "Template writer" when no model wrote the words, "Offline", "Embedded store", "Spend cap reached" (go-live only, once the live adapter is on) and, on the oversight seat, "Paused". They sit in the top bar before the language control, are hidden when nothing is unusual, and the two that describe an answer ("Prepared", "Template writer") are repeated in that answer's Brief footer. |
| DES-90 | The Plan rail is one row of at most six step chips and always includes the running step. Earlier completed steps collapse into one chip labelled Done, with their count in a `reference` chip. Each visible step chip is a label of at most two words from the catalogue with one of five states: pending (ring), running (half-filled ring, not animated), done (tick), suppressed (lock), failed (broken ring). Tapping a step shows its tool and status, and replays its Stage directive where it has one. |
| DES-91 | The Understanding chips, titled "We understood your question as…", sit under the Plan rail: the commerce activity code, the ISIC class and the public place category as three named chips joined by a solid line, because the links are Public. An ambiguous reading shows its candidates as chips under the words "Which place?". A legacy code that cannot be mapped is shown in a chip with the Not measured outline and the words "Not mappable"; it is never hidden and never guessed. A tap opens the mapping in the Evidence drawer. |

### 10.2 The four hero cards of the flagship

| Slot | Title on screen | Hero fact | Supporting visuals | Class | Caveat sentence |
|---|---|---|---|---|---|
| 1 | "Estimated people around this location" | the estimated count with its range for the selected stored hour | role composition bar (work, live, visit); the people-by-hour chart with range marks; the day and the hour | Simulated | "Simulated estimate with its range. Not the footfall of this building or of any business." |
| 2 | "Places like yours within reach" | network distance to the nearest listed place of the same kind | up to six named places, nearest first, each with its network distance | Public | "Open listings are incomplete." |
| 3 | "Pay within reach" | each side: the median wage band | each side: rounded count of covered earners, quartile band range, band distribution bar; residents' side: housing split bar | Synthetic; coverage shares Public | "Covered private-sector jobs only. Wages paid are not wealth." |
| 4 | "What a restaurant costs to run" | goods as a share of output | one stacked bar of output shares with direct labels | Public | "National figures for all restaurant types." |

| ID | Requirement |
|---|---|
| DES-92 | The flagship shows exactly these four hero cards, in this order, each landing on its own presenter beat. Further evidence sits behind "More evidence", where a sale price per square metre is always shown with its deal count beside it; no fifth card lands in the story. Slot 2 never leads with a count of places, because open listings are incomplete. ASSUMPTION for the hero facts of slots 2 and 4: the pack names the four cards but not their lead figures. |
| DES-93 | Slot 3 is the pair of pay cards side by side: "People who work within reach" at the inline-start and "People who live within reach" at the inline-end, each with its role glyph and colour, equal in width, with rows aligned so that the two sides compare line by line. They remain two Evidence cards, each with its own class word, coverage bar and drawer. On each card the count and the adjacent non-ratio band shares come from one additive family (PRV-30). Mean wage and the coverage, irregular and deployed-elsewhere shares are the closed ratio-statistic exception: each uses numerator and denominator columns from the same stored rows — one table, one partition, one unit set and one measure where applicable — and its Source chain names both additive families. The residents' card always shows `family_housing`, `labour_accommodation`, `institution` and `unknown` for covered earners, an explicit `other` row when pooling occurred, beside the count that is not measured. That split's count and its shares come from that split's one additive family. The not-measured count is a separate population. The two cards do not set two routes to one population side by side as two numbers. |
| DES-94 | Words say "around this location", "around this door", "within reach" or "within the area you drew"; an estimate of people is always "estimated people around this location", never "footfall of" a named building or business ([decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md)). No card, caption or sentence uses a possessive or a preposition that attributes a Simulated or Synthetic figure to a building, a tenant or a named business; the fixed denial sentences (slot 1's caveat and the "estimated people" caveat of section 10.13) are the only places such wording appears, and they deny it. |

### 10.3 Evidence drawer and thread

| ID | Requirement |
|---|---|
| DES-95 | The Source chain (the evidence drawer; Arabic label proposed, pending the owner's review: "السند") opens for one fact at a time. On wall and laptop it slides from the inline-end over the Brief column, at the Brief's width, so that the Stage stays clear (in a Stage-led scene it takes the Brief's place); on tablet it is a full-height sheet. Its title reads "Source chain" in every language. Content, top to bottom: the fact's label (`label_en` or `label_ar`) and its `large` chip; the class word and the evidence-status word on separate lines; the why-path; every input class of a composite; coverage and caveats as sentences; the reliability band in words; a link to the Privacy receipt. |
| DES-96 | The why-path is a vertical chain drawn in SVG and read top to bottom in both languages: fact, release, rule or treatment applied, release table, source, licence with retrieval date. It shows at most six nodes by default and never more than fifteen. Connectors use the fact's provenance line style. It is built from lineage records only: a node with no record is not drawn, and a sentence says that it is missing. |
| DES-97 | Follow the thread: on tap the drawer opens in `--eii-dur-slow` with the fact's chip repeated at its head; then one line in the fact's provenance line style draws in `--eii-dur-slow` from that chip to the contributing release units or public geography on the Stage, which are outlined once, and the chain nodes arrive in order. The camera does not move. For a fact with no geography the line runs from the chip straight into the chain. |
| DES-98 | Custodian-type sources are named in the drawer by their neutral record-type names (business register, employment, wages, residence, mobility) with the word Synthetic or Simulated. Public sources show publisher, dataset, licence and retrieval date. Open item OI-06 governs any other labelling. |

### 10.4 Snap animation and snap report

| Step | Starts at | Lasts | What happens |
|---|---|---|---|
| 1 Pin | 0 ms | 150 ms | The pin drops at the door with `--eii-ease-enter`. |
| 2 Ask | 150 ms | 400 ms | The requested shape draws outward from the pin as a 2 px accent line: a circle for `distance`, the travel-time outline for `walk` or `drive`. A shape the user drew is already on screen and stays as drawn. |
| 3 Hold | 550 ms | 250 ms | Nothing moves. The audience sees what was asked. |
| 4 Units | 800 ms | 400 ms | The release units that cover the shape appear as thin outlines from the pin outward. |
| 5 Snap | 1,200 ms | 250 ms | The requested shape fades to 35% opacity; the union of the units takes the area line with its casing. This is the only quick movement. |
| 6 Report | 1,450 ms | 250 ms | The snap report appears, attached to the area. |

| ID | Requirement |
|---|---|
| DES-99 | The snap runs only when a figure of a protected record type (business register, employment, residence, wages) is first shown for an area, and always before that figure; Public points and Simulated estimates are shown for the exact shape with no snap ([decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md), item 6). In the guided story the snap follows the six steps above and takes 1,700 ms. In exploration steps 3 and 4 are dropped and it takes 900 ms (150, 250, 250 and 250 ms). Evidence that is ready lands as soon as step 5 ends; the animation never holds back evidence. |
| DES-100 | The requested or drawn shape is a solid 2 px accent line; after a snap it stays visible at 35% opacity for as long as the area is selected, so that the asked and released areas can be compared. A drive area shaped by the simulated link speeds of a situation or an hour (`traffic_hourly`) uses a Simulated moving-dash outline. Every other outline uses the hero layer's class, and is solid accent when no hero is on. Public chips stay solid when the outline is Simulated, and the legend reads: The outline is a simulated drive time. The places are public. |
| DES-101 | The snap report is a caption attached to the area. It holds the fixed sentence "Your area was fitted to whole grid cells under the release's disclosure-control rules. The figure describes the fitted area."; Fact chips for the requested area, the released area and the number of release units; the rules version; and a link to the Privacy receipt. When the released area is more than twice the requested area it adds "The released area is larger than you asked for, because smaller groups cannot be released." ASSUMPTION for the factor of two: a visible gap needs a stated trigger. |
| DES-102 | Two requests that snap to the same units show the same outline, and the word "Identical" appears beside the second snap report. |

### 10.5 The dial

| ID | Requirement |
|---|---|
| DES-103 | Form: a ring 280 px across on the wall, 168 px on laptop and 144 px on tablet, with four equal quadrant detents and one knob. Clockwise from the top: `weekday_lunch` centred at 45 degrees, `weekday_evening` at 135, `friday_evening` at 225, `ramadan_iftar` at 315. It selects one of four stored situations and is not a clock: it has no hour marks, no hands and no position between detents. Choosing a situation also sets its day type and season and moves the Hour control to the situation's first hour (DES-170), which is the clock. It sits at the lower inline-end of the free Stage, above the Stage footer row. When the presence card is not the active card it folds to a compact form, a ring of 72 px (wall) or 48 px with the active name beside it, and a tap unfolds it. ASSUMPTION for the geometry: the pack fixes the four situations, not the form. |
| DES-104 | Labels: "Weekday lunch", "Weekday evening", "Friday evening" and "Ramadan iftar" beside their quadrants in `--eii-type-label`; the active name in the centre in `--eii-type-title`, above the Fact chip of estimated people around the selected area at the selected hour, with its range (DES-167). With no area selected the centre reads "Pick a place to see who is present." With an event day selected no quadrant is active, and the centre shows the event day's name. The dial's order, angles and clockwise motion are the same in Arabic. |
| DES-105 | The ring is drawn in the Simulated line style, with dashes moving clockwise at `--eii-dash-speed`, and the word "Simulated" sits under the dial at all times. |
| DES-106 | States: selected (knob on the quadrant, quadrant outlined in accent, name in the centre); focus; pressed; dragging (the knob follows the pointer and nothing on the map changes until release, when the knob settles on the nearest detent); changing (the knob moves in `--eii-dur-slow` with `--eii-ease-move`, while the presence layer, the lighting and the affected chips cross-fade in `--eii-dur-scene`; a new selection during a change retargets it); unavailable (ring in `--eii-line`, a sentence and "Why can't I see this?"). The default is `weekday_lunch` with summer off. ASSUMPTION for the default: the first situation in the pinned list. |
| DES-107 | Input: tap or click a quadrant or its label; drag the knob; arrow keys step one detent (Right and Down clockwise, Left and Up anticlockwise, in both languages); the `stage` directive sets the dial in the story. |
| DES-108 | The summer switch sits under the dial: the word "Summer", a two-position switch and the state word "On" or "Off". It applies to the first three situations. With `ramadan_iftar` selected it is disabled and shows "Off" with the caption "Summer does not apply to Ramadan iftar."; with an event day for which the release holds no summer profile it is disabled the same way, with the caption "Summer does not apply to this day."; its earlier state returns when another situation is selected. Turning it cross-fades the presence layer and chips. ASSUMPTION for restoring the state: it avoids a silent change of the user's setting. |
| DES-109 | Public monthly context series are shown beside the dial on their own solid-line Public cards under the title "Public context". They are not matched to the dial hour by hour. The July–August metro ratio is used only as the ANCHORED summer discretionary proxy defined in [05 Synthetic world and simulation](05_SYNTHETIC_WORLD_AND_SIMULATION.md); every context card remains a separate Public fact. |

### 10.6 Break-even, supplier and national pay panels

| ID | Requirement |
|---|---|
| DES-110 | The break-even panel shows six inputs, in this order: monthly rent in QAR, seats (whole number, at least 1), average bill in QAR, opening days (default 30, editable), expected covers per day (optional), monthly staff cost in QAR (optional). It posts them to the server method in [07_ECONOMIC_METHODS.md](07_ECONOMIC_METHODS.md). Results are inferred "Your inputs" chips: 2022 covers per day, and the minimum and maximum of that figure across 2018–2022. Breakpoints appear only when expected covers is filled: maximum rent, minimum bill and, in mode B (the user's staff cost), maximum staff cost; the track's tick is maximum rent and the marker is the entered rent. With expected covers empty, no breakpoint is shown. The optional second result line is labelled "to earn the sector's 2022 surplus share" and is never called break-even. Rent opens empty. After the six inputs, an optional selector offers the incentive packages of the agency's pages ([decision 0017](decisions/0017-public-data-additions-and-public-splits.md)): each package by its published name with its source page and retrieval date, its parameters as solid Public chips, and "None" as the first choice; a chosen package carries the "Your inputs" marker, because the choice is the user's, and changes no Public figure. The panel is hidden while open item OI-03 is open (MTH-29). Results carry the "Your inputs" marker and sit under the word Inferred. |
| DES-111 | The `supplier_lens` panel shows one block for each input of the basket: the input's name; up to five origins as ranked horizontal bars of share, longest first, each with a chip labelled "Calculated import unit value (QAR per kg)" and the valuation basis as the source states it or "not stated by the source"; a concentration chip; and a trend line. The browser draws the tool's list and does not truncate, rank or recompute it. Every mark is solid, because every figure is Public. Origins are countries; no company is named. Heading-level tariff figures from blended codes are not on screen (PUB-44). |
| DES-112 | The national pay card is one horizontal bridge: the start mean and the end mean as `large` chips at its two ends, and between them two segments sized by their share of the change, labelled "Pay within occupation groups" and "Workforce mix", each with its chip. The published table is named under the title. The card uses the published table combined across sexes (MTH-24) and shows no split; official splits by sex appear only on their own Public split cards (DES-179). It never says or implies that pay did not rise. The card is hidden while open item OI-03 is open (MTH-23). |

### 10.7 Time controls: hour, day and month

| ID | Requirement |
|---|---|
| DES-170 | The Hour control is a horizontal strip under the dial: one tick for each hour the release stores for the selected day, a knob on the selected hour, the window of the selected dial situation outlined on the strip, and Play and Pause beside it. Hour labels are `reference` chips at the two ends of the strip and above the knob. Time runs from left to right in both languages and the strip never mirrors (DES-144). Steps are by tap, by drag (the knob settles on the nearest stored hour on release, as the dial knob does), by the arrow keys and by the `stage` directive. The strip is drawn in the Simulated line style with the word "Simulated" under it, like the dial ring (DES-105). |
| DES-171 | The Day selector sits beside the dial as three chips under the words "Event days": "National Day", "A day in Ramadan" and "A major match", each with its event glyph. Choosing one leaves the dial with no active situation (DES-104), sets the Hour control to that day's stored hours and shows the caveat "Simulated day profile. Not a measurement of the event or the attendance of any venue." Tapping the active chip again, or choosing a dial situation, returns to the regular days. ASSUMPTION for the chip words: decision 0016 names the three event days, not their labels. |
| DES-172 | The Month selector is a horizontal list of the release's months, latest at the right, in the header of a workspace that uses monthly figures; each month is a `reference` chip with the month as a word. The comparison control chooses the month compared and opens What changed: a list of rows, each with the item, a Fact chip of the change with its explicit sign and catalogue word (DES-33) and its class line. Every Synthetic row carries the sentence "A change between synthetic months shows how the method reads change. It is not a change in Qatar." Selecting a row outlines its area on the Stage. Openings and closures are two hero layers on the magnitude ramp, never a net map in two colours (DES-19). |

### 10.8 Drawing tools and the exact shape

| ID | Requirement |
|---|---|
| DES-173 | The drawing tools sit in one group at the Stage's inline-start edge: polygon, radius and travel time, each a glyph beside its word. A polygon draws as a 2 px accent line with its casing; its vertices are accent knobs that meet the target size; the shape closes with a tap on the first vertex or with Enter and stays editable until "Use this area" is tapped. The radius tool offers the closed presets and the travel-time tool the closed cut-offs, as `input` chips; a drive time shows the hour of the Hour control beside it. By keyboard, a crosshair moves with the arrow keys and Enter places a vertex. A shape the server refuses keeps its outline in `--eii-line-strong`, with the governed reason and the presets as buttons. The assistant never draws or edits a shape. |
| DES-174 | When the figures on screen for a drawn shape are Public points and Simulated estimates only, no snap runs, and the caption attached to the shape reads: "Public points and simulated estimates are computed for the shape you drew. Simulated estimates are apportioned to it from released area units by the method named in the Source chain." A Public statistic apportioned to the shape shows the word Inferred and names its method and its official geography. When a protected figure is first opened, the snap of section 10.4 runs and the snap report joins the caption. |

### 10.9 Ranking, reverse and similar areas

| ID | Requirement |
|---|---|
| DES-175 | The Ranking panel is titled "Areas ranked by the criteria you set". It is a table: one row per area in rank order, each with its rank as a `standard` Fact chip and, in the same row, the rank-stability sentence of section 10.13; one column per criterion, each value a `compact` chip in its own class line; a header row of weights as `input` chips under the words "Weights are a judgement". Changing a weight dims the ranks until the server returns the new order; the rows then move to their new places in `--eii-dur-slow`, never through intermediate ranks. A switch "Public criteria only" sits above the table. There are no medals, podium, stars, scores out of a maximum or colours for good and bad, and no words such as "best", "winner", "recommended" or "you should". The Stage outlines the ranked areas in the least-real class line of the criteria and the selected area in the accent. |
| DES-176 | The Reverse view uses the Ranking panel's table for activities, titled "Activities ranked by fit for this area, by the criteria you set", with the caveat "A fit is not a forecast of a tenant's success." Similar areas is a list of at most three area types, each with its name, its stability figure as a Fact chip and, for the selected type, its areas outlined on the Stage; its caption is the `area_types_limit` sentence of section 10.13. |

### 10.10 Firms, businesses, investment projects, splits and agency records

| ID | Requirement |
|---|---|
| DES-177 | A named synthetic firm's name is always set with the dotted Synthetic underline and the tag "Synthetic · fictional firm" beside it, in every list, card, drawer and export, and a firm list's title begins with the words "Fictional firms". A firm row shows only the name, activity, size band and area; a rank, where the journey ranks, is a Fact chip with its stability sentence. The Firm list and the Business list of real businesses are separate panels with their own titles and class words, at least 32 px apart on the wall and 24 px elsewhere (as DES-86), and never share a row, a list, a sort or a search. Real business names are set as published, isolated, under a solid Public line. |
| DES-178 | Announced investment projects are drawn on the Stage as solid Public marks at the geography the source states, never at a building or an address, with each mark's count as a `compact` chip in the legend. The FDI list shows one row per project as a published announcement: company and source country as published (isolated), sector, function, project type, date and stated location, with capex and jobs as Fact chips carrying the caveat glyph. Directly under the list's title sits the fixed note of `fdi_estimates` (section 10.13). The filters are sector, source country, period and stated location; there is no search by name. |
| DES-179 | A Public split card shows an official figure split by sex or by nationality as the source publishes it: the categories in the source's order and words (for nationality, Qatari and non-Qatari), bars in one tint family with direct labels, no colour or glyph that stands for a sex or a nationality, and the source, geography and year under the title (DES-169). It is never set on a drawn shape, in a pay card, or on one chart with a Synthetic or Simulated figure; its caption is the `public_split_as_published` sentence. |
| DES-180 | Agency records show the set-up steps as a vertical stepper in their published order, joined by a line and carrying no numerals; sector context and opportunities as titled source blocks; incentive packages as named rows with their parameters as Public chips; and laws as titled links. Each record carries its page link and its retrieval date, and its text sits in its own isolate with its language marked (in the publisher's language where only one exists). The footer carries the `agency_page` sentence. |

### 10.11 Trends, projections and the labour-market view

| ID | Requirement |
|---|---|
| DES-181 | A projection continues its series in the series' own class line past a vertical divider at the last published or released period. The divider is a solid `--eii-line-strong` rule labelled "Projection", with the method and the period in caption size. Published or released points are filled markers; projected points are open markers of the same size. The projected value at the end of the line is a `compact` chip with the word "Projection", and the caption is the `projection_not_forecast` sentence. A projection is never dotted or dashed for being a projection, never shaded as a cone or a fan, and never extends a series of revenue, demand or success. |
| DES-182 | The Labour-market view is Brief-led, one chart or table at a time, with the Month selector in its header. Its views, each separate, in this order: area pay (earner counts and pay bands with middle ranges, read only from permitted released units: the whole release units of a snapped area, a municipality unit of the four pay partitions or the national unit, each labelled with its own released area, and each statistic from the one partition that MTH-55 assigns it: for a snapped area as MTH-55 gives it; for a municipality, the one earner count from its unit of `rp_all_money` or `wp_all_money` and the bands, band shares and their denominator from its unit of `rp_all_quartile` or `wp_all_quartile`, that denominator never displayed as a second earner count; nationally, the earner count from `rp_all_count` or `wp_all_count` and the bands from `rp_all_quartile` or `wp_all_quartile`; Synthetic); occupations (band bars under the family rules of DES-93); the wage trend of the same earners (Synthetic; only for a municipality unit or the national unit, never for a smaller area and never by sector); wage trends by economic activity (Public and national only, from the activity table `wage_act`: each activity's mean monthly pay beside its paid-worker count in adjacent published years, and the national change split into pay change within sectors and change in the employment mix, the two set side by side, never one line hiding the other; shown once OI-03 is closed, MTH-97); Public series and splits on their own cards (DES-179); projections (DES-181). No view shows protected pay bands by sector, or a sector figure for an area or a municipality. A Synthetic mean never appears without the median band, the distribution and the earner count (DES-85); a Public activity mean appears only beside its paid-worker count and the caveat of the public-data gap "pay percentiles or pay by area" (PUB-78). Every Synthetic figure carries its dot texture, and the sentence "Covered private-sector jobs only." sits under the title of every Synthetic view. |

### 10.12 Journey home, cases and sample files

| ID | Requirement |
|---|---|
| DES-183 | The Journey home sits under the ask bar as a three-way switch, "Decisions", "Services" and "Cases", with Decisions shown first: seven decision cards, three service cards and four case cards, each with its title, a one-line question and the class words of the evidence it will show. A decision or service card's tap starts its prepared example; a case card's Start starts its case story. One group shows at a time on every layout, so the wall keeps its type sizes; the card order is fixed and mirrors in Arabic. |
| DES-184 | Each case card carries its question, the words "Illustrative case. The company is fictional." and a Start button. A started case story shows its steps as dots with its title, like the story stepper, and "Prepared" on prepared answers. It ends on the case's answer of [09_AI_ASSISTANT.md](09_AI_ASSISTANT.md) section 3 (an assessment, a prospect list, a trial or a test to run), set as the decision sentence's lead and cheapest test, never as a verdict. |
| DES-185 | The Sample-file loader of cases C3 and C4 shows the loaded file as a card with the dotted Synthetic line, the words "Sample file · Synthetic", the `sample_file` sentence and an "Unload" button. Every chip computed from it carries the "Your inputs" marker beside its class line. A refused file shows only the governed refusal sentence and nothing of the file. |

### 10.13 Fixed sentences of the version 1 families

The English source text of the caveat keys of [09_AI_ASSISTANT.md](09_AI_ASSISTANT.md) section 5.1. Arabic comes from the reviewed catalogue (open item OI-09). Every brace is a fact slot rendered by a Fact chip.

| Key | English source text |
|---|---|
| `estimate_not_footfall` | "Estimated people around this location. Not the footfall of any building or business." |
| `density_estimated` | "Estimated people per square kilometre, simulated." |
| `traffic_simulated` | "Simulated traffic from released flows on the real road network. Not a measurement." |
| `ranking_not_advice` | "Ranked by the criteria and weights shown. Not advice, and not a forecast." |
| `weights_judgement` | "Weights are a judgement. Change them to see how the order moves." |
| `fit_not_success` | "A fit is not a forecast of a tenant's success." |
| `area_types_limit` | "Only area types that proved stable are shown, each with its stability figure." |
| `firms_fictional` | "Fictional firms, marked Synthetic. They show the kind of firm the method finds; none is a real business." |
| `listings_incomplete` | "Open listings are incomplete." |
| `public_split_as_published` | "An official figure, split as the source publishes it, for its own geography and year." |
| `fdi_estimates` | "Capex and jobs are the source's estimates of publicly announced projects. The source does not capture every project, and its data may change." |
| `agency_page` | "From the agency's published page, as retrieved on the date shown." |
| `projection_not_forecast` | "A projection by the method named, over the period shown. Not a forecast of revenue, demand or success." |
| `synthetic_change` | "A change between synthetic months shows how the method reads change. It is not a change in Qatar." |
| `published_count` | "A published visitor count for this named place. Not an estimate of people present." |
| `trip_from_area` | "Times are for trips from this area. They are not figures of the destination." |
| `screen_not_opportunity` | "A screen of public trade and production figures. Not an opportunity or a recommendation." |
| `sample_file` | "From the synthetic sample file loaded in this session. It stands for your own records and stays in this session." |
| `rank_stability` | "Stays in the top {top_n} in {share} of weight draws. Rank between {rank_low} and {rank_high} in the middle {middle_share} of draws." (method card C11 of [07_ECONOMIC_METHODS.md](07_ECONOMIC_METHODS.md)) |

| ID | Requirement |
|---|---|
| DES-186 | The fixed sentences of this section and of sections 10.7 to 10.12 are the English source text. They contain no numeral and no number word (every number is a slot), pass the build-time scans of [09_AI_ASSISTANT.md](09_AI_ASSISTANT.md), and are reviewed in Arabic before an audience sees them (DES-41). |

## 11. The guided story

| ID | Requirement |
|---|---|
| DES-113 | The story is ten scenes, 0 to 9, on one persistent Stage, driven by a stepper: Next and Back by key, clicker or on-screen button, with position shown as ten dots and the scene title. Target durations keep their earlier values, to be confirmed in rehearsal, for scene 0 (30 seconds), scene 2 (60), scene 5 (60), scene 6 (90), scene 7 (60) and scene 9 (30). Scenes 1 and 3 had targets of 40 and 150 seconds before [decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md) added the day hour by hour and the drawn area; the targets of scenes 1, 3, 4 and 8 are set at the first full rehearsal of slice S11 and recorded in [16_DEMO_RUNBOOK.md](16_DEMO_RUNBOOK.md), so that the total keeps the 8 to 9 minute target of BRF-33 unless the owner changes that target. Every scene can be entered directly and replayed. Keys keep their physical meaning in both languages: the Right arrow and the clicker's next key always mean Next. |
| DES-114 | Scenes 0, 1 and 9 are Stage-led: there is no Brief column, and one caption plate at the lower inline-start of the Stage, above the Stage footer row and at most six columns wide, holds a headline, at most one `hero` chip and two `standard` chips, and one caveat. Scene 2 uses the reading-guidance pair described in its table: a headline, and under each half of the Stage one guidance plate that gains at most two elements on each beat. Scenes 3 to 8 are answer-led: the Brief column is shown. |
| DES-115 | Scene 0 shows Public facts only. No Synthetic or Simulated layer, figure, texture or word is on screen before scene 1, apart from the provenance legend. |
| DES-116 | No pay figure and no pay layer is on screen before scene 2, and in scene 2 the resident pay view appears only together with the housing split, the not-measured count and the sentence "The average alone is not enough." |
| DES-117 | The words on screen are the strings of this section. They contain no numeral outside a Fact chip and nothing that the prohibited-claims list of [01_PROJECT_BRIEF.md](01_PROJECT_BRIEF.md) forbids. The presenter lines here are the design intent; the spoken script is in [16_DEMO_RUNBOOK.md](16_DEMO_RUNBOOK.md). |
| DES-118 | The flip: one tap on the language control. Words fade out in `--eii-dur-fast`, the layout mirrors, and words fade in in `--eii-dur-fast`. Through the whole change the numerals of every visible Fact chip stay fully opaque and travel to their new places in `--eii-dur-slow`. The Stage does not move; its labels cross-fade to the other language. At no frame is a numeral absent from the screen. Under reduced motion, and as the written fallback if the travel cannot be built reliably, the numerals jump to their new places without blanking. |
| DES-119 | Identical numbers: for any brief, the ordered list of digit-and-separator strings shown by its Fact chips is byte-identical in English and Arabic, and the release identifier is the same. A test checks this for every prepared question. |
| DES-187 | Every scene and every case story keeps the honesty lines. Every Synthetic or Simulated figure carries its mark; none is about a real named building, business or place; an estimate of people is "estimated people around this location", never the footfall of a named building or business; there is no revenue, demand or success forecast and no go or no-go verdict, probability or confidence claim; a ranking or fit is shown as the output of tested code over visible criteria with its rank-stability sentence, never as advice; no formal differential-privacy claim is made; the synthetic records carry no sex, gender or nationality, and official splits appear only as Public facts with source and year. |

Figures in the tables below are regression examples that the release is expected to carry, from the Qatar Open Data Portal (CC BY), checked 2026-11-11 and to be re-verified by the fetchers once they are built (see [04_PUBLIC_DATA_PACK.md](04_PUBLIC_DATA_PACK.md)). The screen prints whatever the release holds. While open item OI-03 is open, the unit-economics hero (slot 4), the break-even panel (scene 5) and the national pay card (scene 7) stay off screen; the presenter says that those two published tables stay off screen until they are reconciled.

### Scene 0 — The living map, real public evidence first (30 s)

| Aspect | Design |
|---|---|
| On screen | The national map, then Greater Doha: first the living map's real base, its roads and the business points of public places data as small unlabelled solid dots. Then three Public hero layers in turn, one at a time, each with one caption chip: zone electricity growth from 2021 to 2025 on the five-class ramp (example: zone 69, Lusail, at 3.34 times against 1.34 times nationally); restaurant licences per 10,000 residents by municipality (example: 32 in Al Daayen against 15 nationally); metro and tram stations with the riders of the latest month and the change on a year earlier (example: 7.38 million metro riders in December 2025, up 33%). |
| Camera | "Country" for 3 seconds, then `--eii-dur-fly-long` to "city"; drift after arrival. No globe is used. |
| Motion | First the standing strip and the provenance legend slide up, and each legend sample draws itself once. Then the business points fade in over the roads in `--eii-dur-scene`. Then the zones fade in class by class from low to high, one `--eii-dur-base` apart: the map is lit in the order of the real figure. The second and third layers each replace the one before by cross-fade, about eight seconds apart. |
| Words on screen | Headline "Real public evidence first." Caveat while the business points lead: "Business points from public places data. Open listings are incomplete."; then "Electricity use is a sign of activity, not a count of people." |
| Marks present | Public only: solid. Watermark "Demonstrator · Public". |
| Presenter says | "Everything on this first screen is real, public and cited: the roads and business points of the map, electricity by zone, licences, metro riders. From here on, every number tells you which kind it is." |
| Signature moment | The city lit by a real number. |

### Scene 1 — The Qatari day, hour by hour (target set at rehearsal)

| Aspect | Design |
|---|---|
| On screen | Greater Doha. Hero layer: crowd density, estimated people per square kilometre on release units, with the dash texture (DES-165). The dial with its summer switch, the Hour control under it and the event-day chips beside it. Separate Public context cards beside them. Municipality, zone, landmark and place labels and the business points are off for the whole scene. No pay figure anywhere. |
| Camera | "City", fixed. Only the data and the light change. |
| Motion | Beat 1: the Hour control plays a weekday through its stored hours (DES-168). Beat 2: the dial is turned through the four situations, each moving the Hour control to its window, then summer is switched on and off at `weekday_lunch`; each turn: knob, cross-fade, lighting. Beat 3: the chip "National Day" plays that day's stored hours. |
| Words on screen | Headline "The Qatari day, hour by hour." Caption "Simulated estimates of people present, for the city as a whole. Not any named place's footfall." On National Day the caption becomes "Simulated day profile. Not a measurement of the event or the attendance of any venue." |
| Marks present | Simulated on the layer, the dial ring, the Hour control and every chip; Public on the context cards. The screen states that the Public series are not matched to the hour. Watermark "Demonstrator · Simulated". |
| Presenter says | "Movement here is simulated from published rules, and no telecom operator is involved. Watch the estimated number of people change through a weekday, in the evening, on a Friday, in Ramadan, in summer and on National Day." |
| Signature moment | The city filling and emptying through the day, hour by hour. |

### Scene 2 — Read it honestly (60 s)

| Aspect | Design |
|---|---|
| On screen | The Stage splits into two halves, each centred on one group of release units, labelled "Area A" and "Area B"; no place name is used in a caption. Under each half, a guidance plate: the mean chip, then the median band, the band distribution bar, the housing split bar and the coverage bar. The resident pay layer is drawn only inside the two outlines, and map labels are switched off in both halves so that no real place name sits beside a synthetic figure. |
| Camera | Two fixed framings at the same zoom and pitch, north up. |
| Motion | Beat 1: the two mean chips land and an equals glyph joins them. Beat 2: the band bars grow from their baseline and differ. Beat 3: `family_housing`, `labour_accommodation`, `institution` and `unknown` draw, then `other` when that leaf is present, then the separate Not measured outline. |
| Words on screen | Headline "Same average. Different markets." Fixed sentence "The average alone is not enough." Caveat "Covered private-sector jobs only. Not measured is not zero." |
| Marks present | Synthetic on every pay figure and on the layer; Public on the coverage shares; the Not measured outline. Watermark "Demonstrator · Synthetic". |
| Presenter says | "These two areas have the same average wage and they are different markets, so read the band, the count, the housing split and what is not measured before any average. Every pay figure here is synthetic." |
| Signature moment | Two equal averages separating into two different distributions. |

### Scene 3 — The flagship: one location, drawn (target set at rehearsal)

| Aspect | Design |
|---|---|
| On screen | Act 1, the area through the day: the prepared question; the "We understood your question as…" chips (commerce activity code, ISIC class, public place category); the Plan rail; the area drawn around the door (the prepared shape of the story script); the exact-shape caption (DES-174); hero slot 1 with estimated people and their range by hour, split into workers, residents and visitors; a major match day beside a regular weekday; then the traffic layer with the drive-time outline at a morning and an evening hour. Act 2, the door: hero slot 2; the snap as the pay cards of slot 3 open (section 10.4); hero slot 4. Act 3, the brief: the three Brief sections; then the same screen in Arabic. |
| Camera | `--eii-dur-fly-medium` from "city" to "door". Fixed while cards land; one `--eii-dur-fly-short` move only if a card needs the drive area in view. |
| Motion | Beat 1: question and chips. Beat 2: fly; the prepared shape draws itself vertex by vertex in the accent, and the exact-shape caption lands. Beat 3: slot 1 lands and the Hour control plays the day; then the chip "A major match" plays the same hours, and a returned comparison fact lands beside the regular day. Beat 4: the hero layer becomes traffic, and the drive-time outline re-forms between a morning and an evening hour. Beat 5: slot 2 lands. Beat 6: the snap runs as the pay cards of slot 3 open; the snap report joins the caption. Beat 7: slot 4 lands, or is skipped when OI-03 is open. In every beat the card before collapses and the Stage shows the active card's layer and outline. Beat 8: each sentence is a claim-catalogue template filled by Fact chips; the layout is the validated component list, and an invalid list shows the playbook default; no model-written sentence is on screen. Beat 9: the language control is tapped once (DES-118). |
| Words on screen | Question "I want to open an Italian restaurant at {building} in Lusail. What should I know?" The exact-shape caption (DES-174). The event-day caveat (DES-171). The snap sentence (DES-101). Card titles (section 10.2). Section words Observed, Inferred, Still to test. |
| Marks present | Simulated (slot 1, the traffic layer, the drive-time outline), Public (slots 2 and 4, coverage), Synthetic (slot 3), Suppressed wherever the release withholds. The watermark names what the Stage shows at each beat. |
| Presenter says | Act 1: "Draw any area and you see an estimate of the people around this location through the day, with its range, and the traffic of each hour. It is simulated, and it is not this building's footfall." Act 2: "Pay is different: the area is fitted to whole grid cells before any pay figure is read, and that fit is the privacy rule." At the flip: "One tap: the words change and the numbers do not." |
| Signature moments | Act 1: the drive-time outline re-forming with the hour. Act 2: the snap. Act 3: the flip. |

### Scene 4 — Where else fits (target set at rehearsal)

| Aspect | Design |
|---|---|
| On screen | The Ranking panel (DES-175) in the Brief for the same activity, with the ranked areas outlined on the Stage; then the Reverse view for the flagship area (DES-176); then Similar areas. |
| Camera | `--eii-dur-fly-medium` from "door" to "city"; fixed. |
| Motion | Beat 1: the ranked table lands, each rank with its stability sentence. Beat 2: one prepared weight change, typed from the story script; the ranks dim, then the rows move to their new places in `--eii-dur-slow` and the stability sentences change with them. Beat 3: the switch "Public criteria only". Beat 4: the Reverse view, activities ranked by fit for the flagship area. Beat 5: Similar areas with their stability figures. |
| Words on screen | Headline "Where else fits, by your criteria." Table title "Areas ranked by the criteria you set". The caveats of `ranking_not_advice` and `weights_judgement` (section 10.13); on the Reverse view, `fit_not_success`. |
| Marks present | On each rank, the least-real class of its criteria (Public in public-only mode); the "Your inputs" marker on the weights. The watermark names the classes on the Stage. |
| Presenter says | "The order comes from criteria you can see and weights you can change, and the sentence beside each rank says how much it depends on those weights. It is not advice and not a forecast." |
| Signature moment | One weight changes and the order re-forms. |

### Scene 5 — Costs and suppliers (60 s)

| Aspect | Design |
|---|---|
| On screen | When OI-03 is closed: in the Brief, the break-even panel (DES-110) and the `supplier_lens` panel (ranked bars per basket input). The optional target-surplus line reads "to earn the sector's 2022 surplus share" and is not labelled break-even. When OI-03 is open, only the supplier panel may show; the break-even panel and any unit-economics hero from scene 3 stay off screen. The Stage dims to 60% and keeps the door. Heading-level 1902 figures are not on screen. |
| Camera | "Door", fixed. |
| Motion | The panel opens empty. The presenter console types the worked example into the wall: rent 40000, seats 60, bill 120, opening days 30, expected covers 50. Beat 2 changes rent to 60000, which is past the maximum-rent breakpoint, and the marker changes side. When the release holds an incentive package that the method of [07_ECONOMIC_METHODS.md](07_ECONOMIC_METHODS.md) accepts for this activity, a beat chooses it from the selector, its source page and retrieval date show, and the results change under "Your inputs". The last beat opens the Source chain on a basket-line "Calculated import unit value (QAR per kg)" and the thread runs down the why-path node by node (basket, tariff line, origin, customs table, licence). |
| Words on screen | Headline "Your numbers against public norms." Caveats "A scenario from your inputs. Not a forecast." and "Unit values are calculated from customs records. The basket is an editorial choice." Fixed words "Origins, not companies." |
| Marks present | Public on norms, shares and unit values; the "Your inputs" marker on inputs and results. Watermark "Demonstrator" alone, because no data layer is on the Stage. |
| Presenter says | "The cost structure is the published national one; rent, seats and bill are yours, so the result is your scenario and not a forecast. Tap any number and it shows where it came from." |
| Signature moment | The thread from a number to its source. |

### Scene 6 — Try to break it (90 s)

| Aspect | Design |
|---|---|
| On screen | The prepared safety-regression panel in place of the Brief, with four attempts in a fixed list; the Stage with the door's area; the Privacy receipt; last, the replay panel (section 12). |
| Camera | "Door", fixed; one `--eii-dur-fly-short` pull back to "city" for the third attempt. |
| Motion | One attempt a beat. In the second, the second outline draws exactly over the first and the two result cards slide together into one. |
| Words on screen | Headline "Try to break it." Caption "Prepared safety regression." Outcome words "Declined", "Identical", "Fixtures passed", "Declined" (the typed phrase, separate from the fixture result), "Fallback shown". Replay label "Replay of signed build-time results. Controls off." |
| Marks present | Suppressed on declined results; Synthetic on every pay figure and on the replay; the standing strip above the replay panel. |
| Presenter says | "This is a prepared safety regression: named-entity pay is declined; two shapes snap to one answer; one fixture id on POST /api/proof/scene (PRV-119) selects two prepared requests; the typed subtraction phrase is declined separately; and invalid structured output is rejected, including its one prepared repair, for the playbook fallback. This shows the method on synthetic data; the real thresholds are for the data owners to set." |
| Signature moment | Two different shapes, one identical answer. |

### Scene 7 — The Minister minute (60 s)

| Aspect | Design |
|---|---|
| On screen | When OI-03 is closed: first the national pay card (DES-112): the start mean, the end mean and two segments between them, the change within occupation groups and the change from workforce mix, with the published table named (example: QAR 10,084 to 11,855 from 2020 to 2025, of which QAR 38 within groups and QAR 1,733 from mix). When OI-03 is open, the pay card stays off screen and the presenter states that the published wage tables stay off screen until they are reconciled. Then the `oversight` window: the ledger with rows arriving, and the roll-up "Where and what companies are asking". |
| Camera | "Country" behind the pay card; the oversight seat's own map at "country". |
| Motion | The two segments grow in turn, `--eii-dur-slow` each. After the window switch, a question asked from a company window arrives as a new ledger row at the top. |
| Words on screen | Pay card headline "What moved the national average." Caveat "In the published table, by occupation group." Oversight headline "Every question, on the record." Row tag "This session". Roll-up note "Seeded history is synthetic." |
| Marks present | Public on the pay card. On the oversight seat: Synthetic on seeded history; live rows tagged "This session"; Suppressed where the distinct-organisation minimum is not met. |
| Presenter says | "This is a real public figure: in the published table, most of the rise in the average came from a change in who is employed. And this is the seat an operating ministry would have: every question arrives with its release and what was sent to the AI, and no company is named." |
| Signature moment | A live question arriving in the ledger. |

### Scene 8 — The four cases (target set at rehearsal)

| Aspect | Design |
|---|---|
| On screen | The "Cases" group of the Journey home (DES-183), then each case story in turn from its card. Case C1, an industrial services firm: employer scale by size and activity, industrial capacity and announced investment projects with their estimate note. Case C2, a technology supplier: licensed activities and employer concentrations by sector, then a prospect list of fictional firms. Case C3, a distributor: its shipped sample delivery file, customer concentrations by area, drive-time areas by hour from two candidate sites and their shared reach. Case C4, a retail chain: its shipped sample branch sales, estimated people around the branch by hour, residential pay bands after the snap, and what changed in the area between months. |
| Camera | Each case moves as its first step needs: "city" for cases C1 and C2, "door" for cases C3 and C4. |
| Motion | Each case: one tap on Start; its steps advance by Next; for cases C3 and C4 the first step loads the shipped sample file and its card lands (DES-185); the case ends as its answer lands as the decision sentence's lead and cheapest test. |
| Words on screen | Headline "Each company, its own question." Each case card's question and "Illustrative case. The company is fictional."; the `sample_file` sentence; "Fictional firms" on the prospect list; the `fdi_estimates` note. No headline or label carries a number word (DES-186). |
| Marks present | Every class as its figures carry it: Public with its year on employer scale, capacity and investment projects; Synthetic on fictional firms, on pay and on the sample files, with "Your inputs" on the files; Simulated on estimated people and drive times; Suppressed wherever the release withholds. |
| Presenter says | "Four illustrative companies, each with its own question. Each case ends with a test to run, not a verdict, and every firm on these lists is fictional." |
| Signature moment | For each case, its answer landing after one click: a test to run, not a verdict. |

### Scene 9 — Hand-over (30 s)

| Aspect | Design |
|---|---|
| On screen | The briefing pack as a page preview; then the exploration home over the same Stage: ask bar, the Journey home, Reset. |
| Camera | `--eii-dur-fly-medium` back to "city"; drift. |
| Motion | The pack page rises as a sheet in `--eii-dur-slow` and is dismissed; the stepper fades and the home controls arrive in its place. |
| Words on screen | Pack title: the question. Home headline "Ask about a place." Button "Reset". |
| Marks present | The pack keeps every chip's class line and word, the watermark and the strip notice on each page. |
| Presenter says | "This page is what a company takes away, with every figure marked. Now it is yours: ask it something, and Reset is always there." |
| Signature moment | The controls unlocking on the same map. |

| ID | Requirement |
|---|---|
| DES-120 | The briefing pack is one A4 portrait page in the light theme whatever the screen theme, with a second page only when the content overflows. It is bilingual on the same page: a facts table with the English label at the left, the Fact chip in the centre and the Arabic label at the right, so that each number is printed once for both languages; sentences are set in two columns, English at the left and Arabic at the right. Every chip keeps its line style and word, and Simulated prints as static dashes. The header carries the badge and the short release identifier; the footer carries the watermark words and the strip notice. ASSUMPTION for the format: the pack asks for a bilingual printable page and fixes neither its size nor its arrangement. |

## 12. Two designed moments

### 12.1 Try to break it

| Attempt | Prepared input | What the screen shows | Outcome word |
|---|---|---|---|
| 1 Named-entity pay | A signed fixture identified only by its scenario label asks for one named entity's pay | The application declines it, shows the hatch and lock, the fixed decline sentence and what can be asked instead | "Declined" |
| 2 Two shapes | Two different areas at the same door that snap to the same units | The second outline draws exactly over the first; the two result cards merge under one word | "Identical" |
| 3 Complement regression | One manifest-listed fixture id is sent to `POST /api/proof/scene` (PRV-119). That id selects two prepared pin, mode and cut-off requests whose snapped unit sets differ by one published merged unit of at least two base cells. Separately, the typed phrase "the city minus this cell" is sent to the application. This row does not restate the endpoint schema | The endpoint returns the two pre-validated unit sets; both prepared area answers match their signed results; no figure exists for any member base cell alone. The typed phrase is declined by the application; no production tool accepts a complement shape | "Fixtures passed", then "Declined" |
| 4 Catalogue regression | A signed fixture supplies invalid structured output, including one prepared invalid repair | Catalogue validation rejects the response, rejects that one repair, and the playbook fallback appears. The ledger row is logged from the signed fixture identity. The scene makes no claim of general injection detection | "Fallback shown" |

| ID | Requirement |
|---|---|
| DES-121 | The attack panel is labelled "Prepared safety regression" and lists the four attempts above in this order. Each row has a scenario label, a "Run" control and, after it runs, its outcome word with a neutral glyph. Attempt 3 keeps the fixture result and the separate typed-phrase decline as two outcome words on that one row. The panel is also reachable from the Proof room through a "Try to break it" tile. |
| DES-122 | Outcomes are words and glyphs on neutral surfaces: no red, no green, no alarm styling and no score. |
| DES-123 | The Privacy receipt is open during attempts 2 and 3 as a panel of labelled rows: release, rules version, units used, treatments applied, anything withheld with its reason, the snap report, and the accounting-gate result under "Checked before display" (Arabic label pending the owner's review). Every number in it is a Fact chip. |
| DES-124 | The unprotected comparison is a replay panel at elevation level 3, entered last. A slab across its top reads "Replay of signed build-time results. Controls off." at all times. Its only control is "Check signature", whose result is a sentence produced by code. Its figures are Fact chips marked Synthetic, and any planted canary is named only by its scenario label; no canary marker, value or identifier is rendered or exported. It has no ask bar, no pin and no dial, so that nothing in it can be taken for a live query. |
| DES-125 | The panel footer carries the fixed sentence "This shows the method on synthetic data. It is not a certification, and the real thresholds are for the data owners to set." (open item OI-11). |

### 12.2 The oversight seat

| ID | Requirement |
|---|---|
| DES-126 | The `oversight` window is recognisable at a glance: the badge "Viewing as: Oversight", its seat glyph, a top bar in `--eii-surface-3` and no ask bar. The ledger takes the inline-end five columns on the wall; the roll-up map and a ranked list of activities take the rest. |
| DES-127 | A ledger row shows, in reading order: the arrival tag ("This session" for live rows; the Synthetic word and dotted line for seeded history); the understood activity; the area at municipality level; the playbook; the short release identifier; and "Sent to the AI", which opens the egress record. A new row slides in at the top in `--eii-dur-slow` and keeps a `--eii-line-strong` outline for two seconds. No row shows an organisation's name, a seat key or the text the user typed. ASSUMPTION for municipality level, here and in DES-128: the coarsest geography is the safest default until open item OI-08 is ruled on. |
| DES-128 | The roll-up shows where and what companies are asking as municipality-level aggregates, with the Suppressed hatch wherever the distinct-organisation minimum is not met and the fixed sentence "A live question enters this view only when enough different organisations have asked." Seeded history carries the Synthetic word and texture. |
| DES-129 | While PostgreSQL is away the ledger header shows the word "Paused" and the sentence "Showing the local ledger. Live rows resume when the database returns." No row animates. |
| DES-130 | When a company seat opens a brief that it may not see, the Brief shows the lock and the sentence "This brief is not available to this seat." and nothing else. The message does not say whether the brief exists, and it is not styled as an error. |

## 13. Exploration

| ID | Requirement |
|---|---|
| DES-131 | Home is question-first. Over a dimmed Stage at "city", the living map, it shows the ask bar (eight columns wide on the wall) with bilingual autocomplete for places and activities, and under it the Journey home of DES-183: the seven decisions, the three services and the four cases. Each decision and service card has a one-line question, one prepared example that starts on a tap, and the class words of the evidence it will show; each case card starts its case story. Nothing else is on the home screen except the top bar, the standing strip and the links "Trust centre" and "Proof room". |
| DES-132 | An area comes from a pin or from the drawing tools (DES-173): tap the Stage or choose a place, then choose `distance`, `walk` or `drive` and a cut-off, shown as `input` chips, or draw a polygon. Distance offers the radius presets 250 m, 500 m and 1,000 m. Walk offers 5, 10 and 15 minutes. Drive offers 5, 10 and 15 minutes at the hour of the Hour control, and the staffing playbook also offers 30 minutes. A polygon's vertices are editable until the shape is used. The interface has no lasso and no free radius, and the assistant never draws or edits a shape. |
| DES-133 | Every brief ends with the same action row, in this order: Explain, Compare, Pin, Pack. Explain opens the Source chain on the brief's first fact. Pin drops the brief's pin and runs the snap. Compare and Pack behave as in [10_FRONTEND.md](10_FRONTEND.md). Under the row sit exactly three suggested next questions as buttons of at most 60 characters. A Minister can continue by tapping alone. |
| DES-134 | Every blank explains itself. Each Suppressed mark, each `NO_DATA` or `OUT_OF_SCOPE` result and each Not measured share carries "Why can't I see this?", which opens the drawer on the reason, the rule in plain words and the nearest publishable alternative. A tap on empty land offers "Ask about here". |
| DES-135 | Reset is always visible at the inline-end of the top bar, in story and exploration, on every seat; it is disabled only while a scripted camera move of the story is running. One tap, with no confirmation, closes every panel, removes pins, drawn shapes and areas, clears ranking weights, unloads a sample file, returns the dial, the hour, the day and the month to their defaults and the camera to "city", and shows the home screen; on the oversight seat it returns the ledger and the roll-up to their opening state. It does not change the language, the theme or the seat. |
| DES-136 | Depth: home, workspace (with the journey views and the case stories) and one level below it (Trust centre, Proof room, drawer, pack). Nothing sits deeper (more than two levels of disclosure loses users: Nielsen Norman Group, via the design research), and every room has a way back to the workspace in the same place on screen. The Trust centre and the Proof room are pages of Evidence cards and Fact chips under the same tokens; they add no new kind of component. The Proof room may show survival figures for parameter sets A and B but protected tables for exactly the set exported in the mounted release. It names any canary only by scenario label. It carries one line, read from the review log, and nothing else from the typed-decision gateway: "N activity codes; review order machine-assisted; every mapping signed by a person." No score, no badge, no panel and no other gateway text or control exists. |
| DES-137 | The resident pay and worker pay layers never appear without the reading-guidance block docked beside them: the housing split, the not-measured count and the sentence "The average alone is not enough." The block cannot be dismissed while either layer is visible, and neither layer can be the first layer a session shows. |
| DES-138 | In a comparison of two doors the Stage splits into two halves with the same zoom and pitch. Each door keeps the accent and its letter, A or B. Release units that lie in both areas are each outlined with a 2 px accent line, while the rest of an area shows only its outer line; the legend names them "Shared reach", and the overlap is never worded as lost sales. |

## 14. Big screen, layouts and right-to-left

| ID | Requirement |
|---|---|
| DES-139 | Presenter mode expects a 1920 × 1080 CSS viewport; a 4K display is run at an operating-system scale that resolves to it. Text and other page content always render at the display's native pixel ratio; only the map canvas is capped, at the value set at the spike in slice S1 from the frame-rate measurement (see [10_FRONTEND.md](10_FRONTEND.md)). |
| DES-140 | The density of the wall is that of a phone: a Stage-led scene shows one headline, at most three Fact chips and one caveat; the reading-guidance pair of scene 2 adds at most two elements a side on each beat; an answer-led scene shows one expanded card or one Brief section at a time. Source for the principle: Microsoft's television design guidance, via the design research. |
| DES-141 | Nothing essential depends on hover, on a tooltip or on colour. In presenter mode the pointer is drawn as a 40 px ring so that the room can follow it. ASSUMPTION for the ring: a standard cursor cannot be seen from a distance. |
| DES-142 | Venue check: before a session the wall is checked on the real display for edge cropping, black level, colour range and text sharpness, in both themes; the theme and the room scale are chosen there and recorded (see [16_DEMO_RUNBOOK.md](16_DEMO_RUNBOOK.md)). The presenter-control cluster on the presenter console exposes theme (dark or light), room scale (1.0, 1.15, 1.3) and Pause motion beside the other session controls; the top bar repeats theme and Pause motion in exploration. The values in this document are not proof of legibility in a given room. |
| DES-143 | Direction and language are set once at the document root, and every layout rule uses logical start and end properties; no component hard-codes left or right. The language control is one tap in the top bar and shows the name of the other language in that language's own script, from the reviewed catalogue. The ask bar takes the direction of the text typed into it, and keyboard focus follows the reading order of the active language. |
| DES-144 | Mirroring follows the table below (source for the split: Material Design bidirectionality guidance and W3C guidance on bidirectional text, via the design research). A visual test compares the geometry of every chart and of the dial in English and Arabic, and fails on any difference other than text. |

| Region | Wall | Laptop | Tablet |
|---|---|---|---|
| Stage | full canvas | full viewport | full viewport |
| Top bar | wordmark and badge; stepper or ask bar; status badges, "Pause motion", language, Reset | the same | badge; stepper or ask bar; language, Reset; the rest in a menu |
| Brief | inline-end column, 5 columns, one card or section at a time | inline-end column, 4 columns, scrolls | bottom sheet: collapsed to headline and hero chip, half, or full |
| Plan rail | one row at the top of the Brief (not a third column: at 28 px a separate rail would leave the Stage less than half of the canvas) | the same | one row at the top of the sheet |
| Evidence drawer | over the Brief column, same width | over the Brief column, same width | full-height sheet |
| Dial | lower inline-end of the free Stage, 280 px; compact 72 px | 168 px; compact 48 px | 144 px above the collapsed sheet; compact 48 px |
| Hour control, event days and drawing tools | the Hour control under the dial at the dial's width, the event-day chips beside the dial; the drawing tools at the Stage's inline-start edge | the same | the Hour control above the collapsed sheet, full width; event days and drawing tools in a menu |
| Stage footer row | watermark stamp at the inline-start, data attribution at the inline-end | the same | the same |
| Standing strip | bottom, one or two rows | bottom | bottom; the sheet rests above it |

| Mirrors in Arabic | Does not mirror |
|---|---|
| The side of the Brief, the drawer and the dial's place on screen; the order of the top bar; the stepper and its Next and Back arrows; text alignment; the order of chips in a row and of label and value; the side panels slide from; directional icons; the order of the journey, service and case cards; the column order of tables | The Stage and everything on it; charts, bars, axes and legends (low at the left, time from left to right); the Hour control and the Month selector; numerals, ranges and identifiers; the dial's quadrant order and clockwise motion; the why-path; the snap; replay controls; the lock, the tick and other non-directional glyphs; the wordmark |

## 15. Do-not list

| ID | Do not | Reason |
|---|---|---|
| DES-145 | Build 3D wage towers or any extruded data | Tall columns hide what is behind them, and a synthetic pay surface in 3D over real districts is the image most likely to be photographed and quoted as fact (panel judges, 2026-11-11). |
| DES-146 | Draw live or computed shadows, or sun-position effects | They add stage risk and no information; the overlay library documents its shadow effect as experimental (deck.gl documentation, via the design research). |
| DES-147 | Draw agent trails, or any trace of one simulated person or vehicle | Simulated movement would look more real than the real data; the product holds aggregates only. |
| DES-148 | Animate any layer other than crowd density and traffic through the day, draw a frame or value between two stored hours, or allow a position between dial detents or between stored hours | The release holds stored situations and stored hours only; anything between them would be invented frames. [Decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md) allows the hour-by-hour animation of those two Simulated layers and nothing else. |
| DES-149 | Read a protected figure for a drawn shape without the snap, or let the assistant draw or edit a shape | Drawn areas return with decision 0016, but a free shape adds subtraction risk, so figures of the protected record types snap to whole release units before they are read; the shape is the user's own input. |
| DES-150 | Show a hero wage map before the reading guidance | A pay surface without the housing split and the not-measured count is misread (DES-116, DES-137). |
| DES-151 | Open a second WebGL canvas for graphs | A why-path has at most fifteen nodes; SVG draws it, stays correct in right-to-left layout and avoids a second GPU context on a 4K wall. |
| DES-152 | Draw any network of firms, owners or partners | Synthetic firms drawn as a web read as real recommendations or as surveillance; the release holds no firm-level edge. |
| DES-153 | Use Arabic-Indic digits, or mirror the map, a chart or the dial | Numbers must be identical in both languages; geography and charts are not text. |
| DES-154 | Carry class, status or outcome by colour alone | It fails on washed-out displays and for viewers with a colour-vision deficiency (WCAG 2.2, criterion 1.4.1). |
| DES-155 | Render a numeral outside the Fact chip, or roll a counter | A number without lineage, or a passing value, can be photographed as a fact. |
| DES-156 | Rely on tooltips or hover | They cannot be seen by the room or used with a clicker or by touch (television design guidance, via the design research). |
| DES-157 | Place a Synthetic or Simulated figure on or beside a real named place, word a figure as belonging to a building, or word an estimate as the footfall of a named building or business | No invented attribute may attach to a real named business or place; the wording is "estimated people around this location". |
| DES-158 | Add glow, bloom, translucent panels, parallax, sound or voice | They decorate without informing and lower contrast; voice is dropped from v1. |
| DES-159 | Draw a world map or origin arcs in the supplier lens | A ranked list answers which origins supply an input, without unreviewed labels for other territories. ASSUMPTION: a design choice of this document. |
| DES-188 | Draw a named synthetic firm as a point, a label or a marker, or set it in one list, row, sort or search with real businesses | A fictional firm beside real ones, or at a place, reads as a claim about a real business. |
| DES-189 | Use red, amber and green, a diverging ramp or a second ramp for traffic, crowd density or change | Traffic-light colours fail for colour-blind viewers and read as good and bad (DES-22); one tested ramp keeps every magnitude comparable (DES-19, DES-20). |
| DES-190 | Mark a projection with dots, dashes, a cone or a fan, or call it a forecast | Dots and dashes are provenance (DES-63); a fan reads as a probability, which the product never states. |
| DES-191 | Word a ranking, fit or suggestion as advice ("best", "recommended", "you should"), or show a rank without its stability sentence | A rank is the output of visible criteria and weights; a verdict or a bare rank would be a recommendation the product does not make. |
| DES-192 | Show an FDI capex or jobs figure without the source's estimate note, or offer a search by company name | The source states that these are estimates and that it is incomplete; a name search would be a lookup of a firm. |
| DES-193 | Set an official split by sex or nationality on a drawn shape, in a pay card or beside a Synthetic or Simulated figure | Official splits are Public facts of their own geography only, and the synthetic records carry no sex, gender or nationality ([decision 0017](decisions/0017-public-data-additions-and-public-splits.md)). |
| DES-194 | Show a count of people without its range, or a published visitor count of a named place beside an estimate | A count without its range reads as measured; a published count beside an estimate reads as its source. |

## 16. Design audit gates

The design audit is an independent review of the running interface against this document, by a reviewer from a different maker than the builder (see [15_REVIEWER_CHECKLIST.md](15_REVIEWER_CHECKLIST.md)). It applies to every slice that changes what an audience sees: slice S3, slice S6, slice S7, slice S8, slice S9, slice S10 and slice S11, and every build phase of [decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md) that changes the screen (see [14_IMPLEMENTATION_PLAN.md](14_IMPLEMENTATION_PLAN.md)).

| Severity | Definition | Examples |
|---|---|---|
| Blocker | Misstates data, class or coverage; breaks a prohibited-claims rule; or makes essential content unreadable or wrong in either language | A numeral outside a Fact chip; a class mark missing or wrong; Suppressed drawn as zero; the strip, watermark or badge absent; Arabic-Indic digits; different numbers in the two languages; a mirrored map or chart; an unreviewed Arabic string on a presented screen; a Synthetic figure beside a real place name |
| Major | Breaks a numbered requirement here in a way an audience can see or that blocks a user | Contrast below DES-15; text below the size floor; information on hover only; motion with no reduced-motion form; a clipped Arabic line; a missing focus ring; a wall panel that scrolls; a signature moment upstaged |
| Minor | A deviation with no effect on meaning, legibility or use | A spacing or radius off its token; a duration off its token by less than 100 ms |

| ID | Requirement |
|---|---|
| DES-160 | A slice that changes the interface passes only when its design audit has no open Blocker and no open Major finding. Blocker and Major findings are fixed, and each fix is audited again, before any Minor finding is worked on and before the slice is merged. Minor findings are recorded with an owner and a target slice. |
| DES-161 | Evidence committed with each audit: screenshots of every changed screen at each viewport pinned for visual tests in [12_TESTING_AND_QUALITY.md](12_TESTING_AND_QUALITY.md), in English and Arabic, in the dark and light themes; a greyscale copy of the wall set; one run under reduced motion; and the results of the automated checks for contrast, the numerals lint, digit width, identical numbers and chart geometry. |
| DES-162 | The reviewer walks at least the checklist below and records pass or fail for each line, with the screenshot that shows it. |
| DES-163 | Automated visual tests cover the same matrix of viewports, two languages and two themes for every prepared story beat, and run in continuous integration. A changed baseline needs the reviewer's approval. |
| DES-164 | The Trust centre shows this sentence: "Figures from different tables can differ slightly because each table is protected on its own." |

| Check | Passes when |
|---|---|
| Provenance | Every number and layer names its class in a greyscale still (DES-63 to DES-65) |
| Standing marks | Strip, watermark and badge are on every screen and export (DES-78 to DES-80) |
| Numerals | The lint is clean; no value rolls; precision is as released (DES-32, DES-34, DES-155) |
| Two languages | Numbers are identical; the mirroring table holds; no Arabic line is clipped or letter-spaced; strings are reviewed (DES-37 to DES-41, DES-119, DES-144) |
| Legibility | Size floor, contrast, safe margins and density hold at every pinned viewport (DES-15, DES-27, DES-42, DES-140) |
| Motion | Only tokens are used; one signature moment a scene; the reduced-motion run is complete (DES-12, DES-48 to DES-51) |
| Map | No points of interest in the basemap; labels from the allow-list; buildings carry no data; no shadow (DES-53 to DES-58) |
| Honest wording | Fixed sentences are present; no possessive about a building; no prohibited claim; the honesty lines hold in every scene and case story (DES-94, DES-117, DES-186, DES-187) |
| Estimates and ranks | Every count of people has its range and the "estimated people around this location" wording; every rank and fit has its stability sentence; no advice or verdict wording (DES-167, DES-175, DES-176) |
| Firms, splits and sources | Named synthetic firms carry their mark and never sit with real businesses or on the map; Public split and FDI chips show their year; the FDI note is present; source lines carry retrieval dates (DES-169, DES-177 to DES-180) |
| Time | Only stored hours and months are drawn; playback pauses and has a reduced-motion form; only crowd density and traffic play through the day (DES-168, DES-170 to DES-172) |
| Hand-over | Reset works from every state; every blank offers "Why can't I see this?"; depth holds (DES-134 to DES-136) |
| Do-not list | None of DES-145 to DES-159 or DES-188 to DES-194 is present |

## Open questions and assumptions

Open items are tracked in [OPEN_ITEMS.md](../OPEN_ITEMS.md). Those that touch this document:

| Open item | Effect here |
|---|---|
| OI-01 | The key is supplied for go-live and is not used during the build; throughout the build the story runs on the template writer and recorded answers; the status badges of DES-89 say so. |
| OI-02 | No venue or date is known, so theme and room scale are chosen at the venue check (DES-29, DES-142). |
| OI-03 | The restaurant totals and the two wage-table means must be reconciled before the figures of scenes 5 and 7 and hero slot 4 are displayed. |
| OI-04 | Closed for version 1 by [decision 0017](decisions/0017-public-data-additions-and-public-splits.md) item 10: the census map layers enter the local release, each figure with its source and retrieval date, and are never committed. The coverage bar uses the finest admitted geography or returns `NO_DATA`. |
| OI-05 | The wordmark is the working title; no Arabic name is shown until the owner clears one (DES-47). |
| OI-06 | Source labels use neutral record-type names by default (DES-98). |
| OI-08 | Labels of live ledger rows, the distinct-organisation minimum and the roll-up geography (DES-81, DES-127, DES-128). |
| OI-09 | Every Arabic string, including the four provenance words, three evidence-status words and the separate coverage label, awaits native review (DES-04, DES-41). |
| OI-11 | Thresholds are proposals; the attack scene says so on screen (DES-125). |
| OI-14 | No typed-decision gateway route is used at run time; the gateway remains behind the stage (DES-136). |
| OI-17 | No gateway measurement panel appears in the Proof room; only the activity-spine lineage line appears (DES-136). |

Assumptions made in this document, each stated where it is used:

| Assumption | Where |
|---|---|
| A window 1600 px wide or more outside presenter mode takes the wall arrangement with the Laptop sizes | DES-01 |
| Arabic at 1.12 times the Latin size with a line height of 1.6; a room scale of 1.0, 1.15 or 1.3 | DES-28, DES-29 |
| A fixed digit cell if the font has no tabular figures; ranges with the lower bound on the left in Arabic | DES-31, DES-33 |
| No scrolling panel on the wall; the Brief pages one section at a time | DES-36 |
| The Carbon icon set, subject to a licence check at slice S0 | DES-45 |
| No labels outside Qatar by default; unlabelled roads where a name is missing in the interface language | DES-55, DES-56 |
| The values of the three lighting presets, and one basemap in the light theme | DES-59 |
| Limits on how the flow particle layer looks; no scene of the story uses it | DES-62 |
| `inline` and `compact` chips may omit the visible class word; area cut-offs use the `input` variant; codes and rules versions use the `reference` variant | DES-73, DES-76, DES-77 |
| The wording of the strip notice; the two-part form of the watermark | DES-78, DES-79 |
| The disclosure sentence on company seats; municipality level for ledger areas and the roll-up | DES-81, DES-127 |
| The lead figures of hero slots 2 and 4 (slot 3 as the two pay cards side by side follows from them being two cards in one of four slots) | DES-92 |
| The factor of two that triggers the larger-area sentence | DES-101 |
| The dial's geometry and compact form, its default situation, and the summer switch restoring its state | DES-103, DES-106, DES-108 |
| One bilingual A4 page for the briefing pack, with each number printed once between its two labels | DES-120 |
| The pointer ring; no world map in the supplier lens | DES-141, DES-159 |
| Class breaks of crowd density fixed for the whole day on screen | DES-165 |
| The hold of each stored hour during playback, starting at `--eii-dur-fly-medium` | section 7, DES-168 |
| The on-screen words of the three event days | DES-171 |

Open points from decisions 0016 and 0017:

- OPEN: the targets of scenes 1, 3, 4 and 8, and the story's total, are set at the first full rehearsal of slice S11 (DES-113).
- OPEN: how the four dial situations map onto the hourly day types of the release, and whether the summer switch applies to an event day, are fixed in [03_DATA_CONTRACTS.md](03_DATA_CONTRACTS.md) and [05_SYNTHETIC_WORLD_AND_SIMULATION.md](05_SYNTHETIC_WORLD_AND_SIMULATION.md); DES-103, DES-108 and DES-170 follow them.
- OPEN: the day-fixed class breaks of DES-165 need the method of [07_ECONOMIC_METHODS.md](07_ECONOMIC_METHODS.md) to supply breaks per day rather than per hour.
- OPEN: [decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md) item 17 keeps decision 0006 items 3 and 4 for protected figures; DES-99 and DES-174 read that as the snap of any requested or drawn shape before a protected figure.
- OPEN: the steps of the structured qualification route of journey D4 and service S3 are set with the catalogue of [09_AI_ASSISTANT.md](09_AI_ASSISTANT.md); this document fixes only how they look (a list without numerals, as DES-180).

Questions for the lead, where this document and others in the pack meet: whether moving dashes on map layers join the spike proofs (DES-67); whether the numerals rule is worded the same way here (DES-76, DES-77), in [10_FRONTEND.md](10_FRONTEND.md) and in [12_TESTING_AND_QUALITY.md](12_TESTING_AND_QUALITY.md); whether the Plan rail is a row in the Brief (section 14 here) or a third column, and whether the requested area is a solid line (DES-100) or dashed, as [10_FRONTEND.md](10_FRONTEND.md) sketches; whether the pack is one bilingual page (DES-120) or one language at a time; and that the light theme (DES-17) is a requirement the front-end document does not yet carry.

## Sources

| Source | Used for | Retrieved |
|---|---|---|
| W3C, Web Content Accessibility Guidelines 2.2, `https://www.w3.org/TR/WCAG22/` (criteria 1.4.1, 1.4.3, 1.4.6, 1.4.8, 1.4.11, 2.2.2, 2.5.5, 2.5.8) | contrast, colour, line length, target size, pausing motion | 2026-11-11 |
| W3C, Arabic and Persian Layout Requirements, `https://www.w3.org/TR/alreq/` | direction of numbers, joined letters, line height, alignment | 2026-11-11 |
| W3C, Inline markup and bidirectional text in HTML; Google, Material Design version 1 bidirectionality guidance | isolation of opposite-direction runs; what mirrors and what does not | 2026-11-11, via the design research |
| Unicode CLDR number data for the Qatar Arabic locale; MDN reference for number formatting | default digits and the numbering-system key | 2026-11-11, via the design research |
| Microsoft Learn, designing for television; Android Developers, television layout and typography guides; Amazon Fire TV design guidelines | 1920 × 1080 canvas, 5% safe margins, 28 px floor, density, safe colour range, no tooltips | 2026-11-11, via the design research |
| AVIXA, display image size standard, learning pages | room scale estimate | 2026-11-11, via the design research |
| Nielsen Norman Group, articles on progressive disclosure and on glanceable fonts | depth of two levels; no thin or condensed type | 2026-11-11, via the design research |
| UK Government Analysis Function, guidance on symbols in tables | never zero or "N/A" for a withheld or missing value | 2026-11-11, via the design research |
| Segel and Heer (2010), Narrative Visualization: Telling Stories with Data | author-driven story that opens into exploration | 2026-11-11, via the design research |
| Okabe and Ito, Color Universal Design, `https://jfly.uni-koeln.de/color/`; Wong (2011), Points of view: Color blindness, Nature Methods 8, 441 | accent and role colours | 2026-11-11 |
| Nuñez, Anderton and Renslow (2018), Optimizing colormaps with consideration for color vision deficiency, PLOS ONE 13(7) | reasoning for the blue-to-yellow lightness ramp | 2026-11-11 |
| IBM, IBM Plex repository, `https://github.com/IBM/plex` | typefaces and their licence | 2026-11-11 |
| Carbon Design System repository, `https://github.com/carbon-design-system/carbon` | icon set licence | 2026-11-11 |
| MapLibre Style Specification, light and layers pages, `https://maplibre.org/maplibre-style-spec/`; MapLibre GL JS release notes, version 6.9.0 | light position, building extrusion without shadows, Arabic label shaping | 2026-11-11 |
| Protomaps documentation, basemap flavours, `https://docs.protomaps.com/basemaps/flavors` | starting flavours of the basemap style | 2026-11-11 |
| deck.gl documentation, fill style and path style extensions, `https://deck.gl/docs/api-reference/extensions/fill-style-extension` | pixel-sized textures; no dash-phase control; experimental shadows (via the design research) | 2026-11-11 |
| Government Communications Office, State of Qatar, government brand guidelines | restriction on emblem and palette | 2026-11-11, via the design research |
| Qatar Open Data Portal (CC BY) | example figures in the storyboard; datasets named in [04_PUBLIC_DATA_PACK.md](04_PUBLIC_DATA_PACK.md) | 2026-11-11 |
| Project evidence of 2026-11-11: design research, two design panels and four judges' reports | impact sources, story order, do-not reasons | 2026-11-11 |
| [Decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md) and [decision 0017](decisions/0017-public-data-additions-and-public-splits.md) | the living map, hour-by-hour animation of crowd density and traffic, event days, drawn areas, rankings, named synthetic firms, monthly periods, cases, Public splits, published visitor counts, FDI projects and the agency's pages | 2026-11-12 |
| FDI projects dashboard of the national investment promotion agency, `https://fdiprojects.invest.qa/` (data from fDi Markets) | the substance of the estimate note: estimates of publicly announced projects, not every project captured, subject to change | 2026-11-12, as recorded in decision 0017 |
