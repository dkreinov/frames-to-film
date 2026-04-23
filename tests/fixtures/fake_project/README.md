# Pixar fixture project

Generated 2026-04-23 for Phase 1 watermark-cleaner integration tests.

## Story

Astronaut-cat **Cosmo** on the moon, 6-frame Pixar-style sequence:

1. Lands on the moon, waves next to his rocket with Earth behind
2. Finds a glowing cyan mushroom growing out of moon dust
3. Shares a space-snack with the mushroom
4. Mushroom bends to hum goodbye
5. Mushroom offers him a tiny star gift
6. Cosmo waves from inside the rocket, blasting off

## Frames

All six frames were generated via the Gemini web Pro chat interface (Dennis's account, 2026-04-23). They carry the standard **48×48 "G" sparkle watermark at bottom-right** — except frame 1 whose watermark sits below the cleaner's default detection threshold. This gives the test suite coverage of both cleaner paths:

| File | Source | Resolution | Watermark detected | Exercises |
|---|---|---|---|---|
| `frame_1_gemini.png` | Gemini web Pro chat | 1024×572 | no (auto-detect below threshold) | **passthrough** path |
| `frame_2_gemini.png` | Gemini web Pro chat | 1376×768 | yes, bbox `(1296, 688, 1344, 736)` | **clean** path |
| `frame_3_gemini.png` | Gemini web Pro chat | 1376×768 | yes, bbox `(1296, 688, 1344, 736)` | **clean** path |
| `frame_4_gemini.png` | Gemini web Pro chat | 1376×768 | yes, bbox `(1296, 688, 1344, 736)` | **clean** path |
| `frame_5_gemini.png` | Gemini web Pro chat | 1376×768 | yes, bbox `(1296, 688, 1344, 736)` | **clean** path |
| `frame_6_gemini.png` | Gemini web Pro chat | 1376×768 | yes, bbox `(1296, 688, 1344, 736)` | **clean** path |

## Provenance

Obtained via Gemini's "Share conversation" feature → public URL → `tools/fetch_gemini_share.py`.

Share URLs used:

- Frames 1–2 (original conversation `56a9e319a808a605`) — saved during automation discovery
- Frame 3: `https://gemini.google.com/share/c1db42c9cbf6`
- Frame 4: `https://gemini.google.com/share/e3b6855edbe4`
- Frame 5: `https://gemini.google.com/share/f699cf942bdd`
- Frame 6: `https://gemini.google.com/share/c3f24a2e5b4a`

## Verification snapshot (2026-04-23)

Running `gemini-watermark.exe -i <frame> -o <out>` on each frame:

```
frame_1: NO_WATERMARK_DETECTED (passthrough)
frame_2: cleaner changed 48x48 patch at (1296, 688, 1344, 736)
frame_3: cleaner changed 48x48 patch at (1296, 688, 1344, 736)
frame_4: cleaner changed 48x48 patch at (1296, 688, 1344, 736)
frame_5: cleaner changed 48x48 patch at (1296, 688, 1344, 736)
frame_6: cleaner changed 48x48 patch at (1296, 688, 1344, 736)
```

## Reuse

Do NOT hand-edit these images — Phase 6 E2E tests byte-compare against this exact set. If a frame needs to be regenerated, update the table above with a new verification snapshot.
