# Vision: Resourcery

**Tagline:** Your digital curation engine.

---

## Central promise

> Bookmark what interests you and forget about it. Rediscover it later.

---

## The problem

Bookmark managers have four jobs:

| Job | What it means | State of the art |
|-----|---------------|------------------|
| **Display** | Show me my bookmarks | ✅ Done — lists, grids, cards |
| **Indexing** | Structure, tag, describe, enrich | ✅ Done — auto-tagging, LLM descriptions, full-text |
| **Search** | Find what I'm looking for | ✅ Done — full-text, filters, boolean |
| **Discovery** | Show me what I forgot I had, surface connections, reveal how my interests shift | ❌ Barely attempted |

Every manager nails the first three. **Discovery** is the missing layer —
the "forgetful's entry" that doesn't require you to remember what you stored
or what you called it. Resourcery exists to own that fourth job.

---

## What it does

**Inputs:**
- Raw markdown notes (current)
- Browser bookmark exports — Firefox, Chrome, and any tool that can export
  bookmarks.html (near future)
- Any structured or semi-structured list of references (long-term)

**Process (the pipeline):**
A 7-step LLM pipeline extracts links, enriches metadata, generates a
taxonomy, classifies everything, designs the visual identity, and builds the
output. The user provides raw material; the pipeline provides structure,
design, and coherence.

**Outputs:**
- A fully navigable **static HTML/CSS/JS site** with categories, tags,
  full-text search, dark mode, and a **discovery dashboard** that visualises
  how interests cluster and shift over time

**Future outputs:**
- A **lightweight dynamic site** (client-heavy, thin backend) that enables
  persistent reading lists, view/click tracking, richer temporal analytics,
  and incremental updates without a full rebuild
- An **API layer** exposing the structured collection for other tools to
  consume

---

## Key differentiator

**Discovery — the fourth job.**

Instead of a list you search, you get an **explorable map of your interests**:
- What themes dominate your collection right now?
- How did your focus shift over the last year?
- What did you save that you've completely forgotten about?
- What clusters of topics are emerging?
- What should I look at today based on what I was interested in last month?

This is the "ignorant's entry" — a way back into your own collection without
remembering labels, tags, or keywords.

---

## Architectural north star

**Client-heavy, always.**

The browser is the runtime. Even when we add a dynamic backend (future), it
will be thin — a data API with minimal business logic. The heavy lifting
(layout, navigation, search, visualisation, interactivity) stays in the
client. This keeps the core product:

- **Hostable anywhere** — static hosts, CDNs, S3, a USB stick
- **Offline-capable** — no runtime dependencies
- **Decoupled** — the pipeline is a separate concern from the viewer

---

## What it is not (out of scope)

- **Not a note-taking app.** We ingest notes; we don't replace them.
- **Not a social platform.** No sharing feeds, no follows, no likes.
- **Not a write-back tool.** We don't modify your source of truth.
- **Not a real-time synchroniser.** Collections are built on demand.
- **Not an all-in-one CMS.** The pipeline produces a specific kind of output
  (curated link collections) and owns that niche.

---

## Success looks like

Six months from now:

1. You can dump a Firefox bookmarks export into the pipeline and get a
   beautiful, explorable site with zero config.
2. The discovery dashboard shows you something you didn't expect — a cluster
   of interests you'd forgotten about, a topic that's been growing, a
   connection between two saved links you never made.
3. A small but engaged group of people use Resourcery to maintain their
   personal link collections, and some of them have published public sites.
4. The codebase has clean bookmark import, an improved discovery dashboard,
   and a growing test suite.

---

## Future horizons

- **Dynamic site mode** with interest evolution graphs, reading history, and
  per-link engagement tracking
- **Scheduled re-builds** for freshness (dead link detection, re-summarisation)
- **Export to other formats** (RSS, JSON API, plain markdown index)
- **Plugin system** for custom input parsers and output builders

But all of these come *after* the core promise is solid: bookmark, forget,
rediscover.
