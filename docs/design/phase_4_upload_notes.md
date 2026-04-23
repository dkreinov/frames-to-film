# Phase 4 Upload Screen — Design Notes

**Status:** Stitch generation timed out twice (see `phase_4_upload_stitch.json`). Hand-designed from the prompt below using shadcn/ui primitives. This document is the **design-of-record** for Step 4's implementation.

## Design prompt (would-have-been-sent to Stitch)

An "Upload Photos" screen for a commercial tool that turns family photographs into AI-generated movies. This is Step 1 of a 5-step wizard (Upload → Prepare → Storyboard → Generate → Review & Export). Minimal, modern, light/dark aware, shadcn/ui aesthetic (zinc base, muted tones, generous whitespace, rounded-xl cards).

**Desktop layout:**

- **Top app bar (64px)** — left: small logo mark + "olga_movie" wordmark; center: 5-step wizard progress bar (Upload=active, others dim); right: subtle settings gear icon.
- **Main content** centered, max-width ~960px:
  - Page heading "Upload your photos" (text-3xl font-semibold) + one-line subtitle "Drop images here to get started — JPG, PNG, or WebP, up to 100 per project."
  - **Dropzone card** (rounded-2xl, dashed border, ~320px tall) with cloud-upload icon, "Drag photos here or click to browse" CTA, muted hint "We'll preserve every face exactly." Accepts drop + click-to-browse via hidden `<input type="file" multiple>`.
  - **Uploaded-files list** below the dropzone: each row has a 48px square thumbnail, filename (truncate), filesize (human-readable), and a small remove (×) icon. Empty state: muted "No photos yet" line centered.
- **Footer bar** with a disabled "Next: Prepare photos" primary button on the right (enabled once ≥1 photo uploaded).

**Tone:** calm, patient, serious. This is the user's family memories. No cute/playful elements. No sparkles. No gradients. No glass. No loud colors.

## Component inventory (for Step 4 implementation)

Using shadcn primitives where they exist, hand-rolling where they don't:

| Component | shadcn primitive? | Notes |
|---|---|---|
| `AppBar` | no | thin top bar; logo + stepper + settings icon |
| `WizardStepper` | no | 5 steps: Upload / Prepare / Storyboard / Generate / Review. `currentStep` prop. |
| `DropzoneCard` | no (uses `Card`) | react's built-in drag events; no extra dep needed |
| `UploadedFilesList` | no (uses list primitives) | row = thumbnail + filename + size + remove |
| `Button` | **yes** (shadcn) | install via `npx shadcn add button` |
| `Card` | **yes** (shadcn) | install via `npx shadcn add card` |
| Icons | `lucide-react` | already installed — CloudUpload, Settings, X, ImageIcon |

## Accessibility baseline (pre `/app-design`)

- Dropzone is a `role="button"` with `tabIndex={0}` + keyboard Enter/Space handler, so keyboard users can open the file picker.
- File-list rows have `aria-label` with filename for the remove button.
- Wizard stepper uses `aria-current="step"` on the active one.
- Color contrast: text uses `text-foreground` / `text-muted-foreground` which are both ≥4.5:1 in both schemes.

## Constraints that flow into later sub-plans

- AppBar + WizardStepper are **shared** across all 5 screens. Put them in `frontend/src/components/layout/`.
- Footer bar with "Next" button is **per-screen**; the shape (right-aligned primary button) is the pattern.
- All screens use the same `max-w-[960px] mx-auto` container.
