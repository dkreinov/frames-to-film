# Phase 4 Sub-Plan 4 — Generate Screen (hand-design notes)

Stitch timed out on the single-attempt budget (4/4 sub-plans now).
This file is the authoritative UX spec for `GenerateScreen` until
superseded by a design-review pass.

## Purpose

Step 4 of 5 in the wizard. Input: ordered 16:9 frames from the
Storyboard screen. Output: a `kling_test/videos/seg_*.mp4` per
consecutive pair, with per-pair prompt text the user can tune
before (or after) firing the render job.

## Route

`/projects/:projectId/generate` — lazy-loaded in `router.tsx`.

## Layout (desktop, 1280×720 target)

```
┌─ AppBar (Upload ✓ Prepare ✓ Storyboard ✓ Generate ● Review) ──┐
│                                                                │
│  PageContainer                                                 │
│   ├─ Title "Write prompts and render"                          │
│   ├─ Subtitle "Each clip is a 1-second transition between two  │
│   │   frames. Edit the prompts, then hit Generate videos."    │
│   ├─ "Saving…/Saved" pill (aria-live=polite)                   │
│   │                                                            │
│   ├─ <if prompts loading>                                      │
│   │     JobProgressCard "Writing starter prompts…"             │
│   │                                                            │
│   ├─ <else if prompts error>                                   │
│   │     ErrorCard "Couldn't write prompts" + Try again button  │
│   │                                                            │
│   ├─ <else (prompts ready)>                                    │
│   │     Vertical list of PromptRow cards, one per pair,        │
│   │     in the current Storyboard order.                       │
│   │                                                            │
│   └─ <if generate done>                                        │
│        VideoPosterGrid (4 col) under the prompt list; each     │
│        poster opens a VideoLightbox dialog.                    │
│                                                                │
└─ Footer                                                        │
   ├─ left: back to Storyboard (ghost text button, Phase 6)      │
   └─ right: [Generate videos] (primary, sticky)                 │
       then becomes [Next: Review →] once generate done          │
```

## Per-pair card (`PromptRow`)

```
┌─────────────────────────────────────────────────────────────┐
│  ┌────────┐ → ┌────────┐     1_to_2                         │
│  │ thumb  │   │ thumb  │     (monospace, muted)             │
│  │  a.jpg │   │  b.jpg │                                    │
│  └────────┘   └────────┘                                    │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ <textarea aria-label="Prompt for pair 1_to_2">      │   │
│  │  Slow cinematic dolly. Transition smoothly between  │   │
│  │  the two source frames…                             │   │
│  │ </textarea>                                         │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  <optional> VideoPoster (once generate done) ───────────────│
└─────────────────────────────────────────────────────────────┘
```

- Thumbnails: `img src={artifactUrl(projectId, 'kling_test', 'a.jpg')}`
  with `alt="Frame {n}"`, 96×54 (16:9). Arrow is Unicode → inside a
  `<span aria-hidden>`.
- Pair-key: `<code className="text-xs text-muted-foreground">1_to_2</code>`
- Textarea: shadcn `Textarea`, `rows={3}`, `className="font-sans"`.
  `onChange` bubbles the new value to the parent.
- Aria-label on the textarea: exactly `Prompt for pair {pairKey}` —
  Playwright + testing-library target by role+name.
- Card padding: `p-4`, `space-y-3`. Width: responsive, `max-w-3xl`.

## Video lightbox (`VideoLightbox`)

- Triggered by clicking a VideoPoster (a thumbnail button with a
  centered ▶ icon and a border).
- shadcn `Dialog` with `DialogContent` sized `max-w-2xl`.
- Inside: `<video src={videoUrl(projectId, name)} controls autoplay playsInline>`.
- aria-label on the poster button: `Play {pair_key}`.
- Closes on Escape / backdrop click (stock Dialog behaviour).

## State machine (`GenerateScreen`)

See the plan file for the formal description. Summary:

1. On mount, `GET /prompts`.
2. If 404 OR `set(keys) != set(expectedPairKeys)`, fire one
   `POST /prompts/generate`, poll, re-GET. Guarded by a single-shot
   `regenAttempted` ref so a second mismatch surfaces as an error
   instead of looping.
3. Once prompts resolve, render PromptRows; each edit updates local
   state; `useDebouncedSave(order === null ? null : prompts, 300, savePrompts)`
   debounces the PUT. (Same null-gated pattern as Storyboard —
   prevents the seed save.)
4. "Generate videos" button dispatches `startGenerate` mutation.
5. Poll the generate job with the frozen pattern (`startMutation.isError`
   branch included). While running, replace the Page body with a
   `JobProgressCard` ("Rendering your 1-second clips…").
6. On `done`, `listVideos()` + render `VideoPoster` beneath each
   PromptRow that has a matching `pair_key`. Footer button becomes
   "Next: Review →" and navigates to `/projects/:projectId/review`.

## Copy strings (by state)

| State | Headline | Subhead |
|---|---|---|
| prompts loading | Writing starter prompts… | A one-time setup before your first render. |
| prompts error | Couldn't write prompts | Check the backend is running, then try again. |
| prompts ready, no generate | Write prompts and render | Each clip is a 1-second transition between two frames. |
| generate running | Rendering your 1-second clips… | Usually under a minute in mock mode. |
| generate error | Rendering failed | {error message} — no partial clips kept. |
| generate done | Your clips are ready | Click a thumbnail to preview. Edit a prompt and hit Generate videos again to re-render. |

## Accessibility

- Page heading: `<h1>` on the title via `PageContainer`.
- Each PromptRow is a landmark-less group. The textarea's `aria-label`
  is sufficient; no extra region role.
- `Saving…/Saved` pill uses `role="status" aria-live="polite"`.
- Running/error cards reuse `JobProgressCard` which already sets
  `role="status"` (running) and `role="alert"` (error).
- Video poster is a `<button>` (keyboard-activatable), not a clickable
  `div`. Lightbox is a shadcn Dialog → focus trap handled.

## Visual tokens

- Cards: `border rounded-lg bg-card` (zinc).
- Thumbs: `rounded-md overflow-hidden` with a 1px border.
- Textarea: default shadcn (border + focus ring).
- Monospace pair-key: inherit shadcn `--font-mono`.
- Spacing: `gap-6` between rows, `p-4` inside a card. 8-point grid.

## Non-goals (this sub-plan)

- No per-pair re-generate toggle — the current "Generate videos" button
  re-renders every pair. Good enough for mock; real api-mode tuning
  belongs in Review.
- No prompts-version history.
- No video scrub/compare. Lightbox is plain `<video controls>`.
- No responsive mobile layout (desktop-only until Phase 6 polish).
