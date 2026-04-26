# Kling AI Prompting Guide

Practical reference for writing prompts that produce consistent, controllable output
from Kling AI video generation (versions 2.6 Pro, 3.0). Applies to both
text-to-video (T2V) and image-to-video (I2V) modes. Grounded in fal.ai, atlabs.ai,
leonardo.ai, and invideo.io published guides (sources in §8).

---

## 1. Universal Prompt Frameworks

### SCALE Framework

The most transferable framework for Kling prompts (atlabs.ai):

| Letter | Stands for | Example |
|--------|------------|---------|
| S | **Shot type** | close-up, medium shot, aerial view |
| C | **Camera move** | dolly push-in, steady tracking shot |
| A | **Action** | subject turns head left, walks forward |
| L | **Lighting/atmosphere** | warm afternoon light, overcast diffused |
| E | **Emotion/tone** | optional last — use sparingly |

Camera-first principle: always open the prompt with camera move + shot type.
Kling reads left-to-right and weights early tokens heavily. A prompt that opens
with "A beautiful woman…" will produce generic motion. A prompt that opens with
"Slow dolly push-in…" gives Kling a concrete instruction before it interprets content.

### Four-Part Formula

Simpler alternative from invideo.io:

```
[Camera move]. [Subject action]. [Scene anchor]. [Pacing word].
```

Example:
```
Slow dolly push-in. Child lifts gaze from ground and meets camera. Dappled backyard light. Gently.
```

### Word Budget

Research from fal.ai, atlabs.ai, and invideo.io converges on 40–60 words as
the ideal range. Below 15 words: under-constrained, Kling guesses. Above 80 words:
Kling picks up conflicting signals and drops the weakest-placed instructions.
Hard max: 80 words for a single clip prompt.

---

## 2. The Image-to-Video Core Rule

**Do not redescribe the image. Describe only what should change.**

In I2V mode Kling has the source image already. Any words you spend restating
visible content (subject appearance, static scene elements, background description)
are wasted and can actively harm the result in two ways:

1. **Budget waste.** Words spent on description cannot be spent on motion instruction.
2. **Hallucination risk.** If your description of the source image is even slightly
   wrong (different hair color, wrong background detail), Kling may produce a frame
   that matches your text rather than the actual image. The video then drifts away
   from the source.

### The Test

Before submitting an I2V prompt, scan it for nouns and adjectives that describe
what you can *already see* in the source image. Remove every one of them.
What remains should be entirely about motion, camera, and end state.

**Bad (30 wasted words before any motion instruction):**
> "A young girl with blonde curly hair in a white dress stands in a sunny backyard
> next to a wooden fence. She is smiling. Slow dolly push-in."

**Good (every word earns its place):**
> "Slow dolly push-in. Expression shifts from neutral to a shy half-smile.
> Dappled backyard light holds steady. Gently."

Source: fal.ai Kling 3.0 prompting guide, Runway I2V prompting guide.

---

## 3. Camera Vocabulary That Works

Kling recognizes specific camera terminology. Using canonical phrases produces
more consistent output than paraphrasing.

### Tested Camera Moves

| ID | Canonical Phrase | Best Use |
|----|-----------------|----------|
| dolly_forward | `slow dolly push-in` | intimacy, face reveal, intensify emotion |
| dolly_back | `slow dolly pull-back` | isolation, context reveal |
| smooth_orbit | `smooth orbit around subject` | 360 reveal, static subject |
| steady_tracking_shot | `steady tracking shot` | follow moving subject laterally |
| crane_up | `crane up` | upward reveal, elevation transition |
| pull_back_reveal | `pull-back reveal` | start tight, end wide, expose context |
| dolly_zoom | `dolly zoom` | vertigo/tension effect |
| rack_focus | `rack focus` | shift attention foreground↔background |
| whip_pan | `whip pan` | high-energy transition within clip |
| aerial_view | `aerial view, slow drift` | scale establish, overhead context |
| POV | `POV shot` | first-person, immersive approach |
| profile_shot | `static profile shot` | side reveal, silhouette |
| macro_close_up | `macro close-up, static` | texture, small object detail |

### Pacing Modifiers

Append a single pacing word at the end of the prompt to modulate speed.

**Slow:** slowly, gently, gradually, unhurried, languid, softly
**Fast:** quickly, sharply, snaps to, rapid, swift, abrupt

One pacing modifier per prompt. Two or more creates ambiguity.

### Examples

```
Rack focus from foreground candle flame to subject face in background.
Subject's eyes open. Candlelight holds. No camera movement. Slowly.
```

```
Crane up. Camera lifts from ground level to eye level as subject stands
from seated position. Subject fully upright, facing camera. Autumn park,
warm afternoon light. Smoothly.
```

---

## 4. Motion Sequencing and Pacing

### One Primary Motion Rule

Kling processes one primary subject action reliably. Two or more primary actions
stacked without temporal ordering will cause Kling to:
- Execute only the first-mentioned action, or
- Blend them incoherently (common with Kling 2.6; less common but still present in 3.0)

**Primary motion:** subject turns head, subject stands up, subject raises arm.
**Secondary motion (acceptable alongside primary):** background leaves rustle,
lighting shifts from warm to cool, ambient crowd movement.

Secondary motions must be subordinate and non-conflicting with the primary.

### Temporal Ordering

When a sequence is genuinely needed, use explicit temporal markers:

```
Subject turns head left. Then eyes close. Finally shoulders drop.
```

Not:
```
Subject turns head left and closes eyes and shoulders drop.
```

The word "and" tells Kling simultaneous. "Then" tells Kling sequential.
Kling 3.0 honors sequential ordering more reliably than 2.6 (fal.ai, atlabs.ai).

### Start State → End State Pattern

The most reliable single technique for predictable motion: name where the
motion starts and where it ends.

```
[Camera move]. [Subject action]. [Start state] transitions to [end state].
[Environmental anchor]. [Pacing modifier].
```

Example:
```
Steady tracking shot. Subject walks left to right across frame.
Arms at sides transitions to arms swinging naturally.
Concrete sidewalk, midday sun. Gradually.
```

---

## 5. Multi-Shot Prompting (Kling 3.0)

Kling 3.0 introduced native multi-shot generation. A single prompt can describe
up to 6 shots; the model generates them as a continuous clip with internal
transitions (fal.ai Kling 3.0 guide, atlabs.ai Kling 3.0 guide).

### Parameters

- **Max shots:** 6
- **Sweet spot:** 4–6 shots
- **Sweet spot duration:** 10–15 seconds total
- **Format:** Number each shot explicitly

### Format

```
Shot 1: Slow dolly push-in. Subject reads letter. Expression neutral. Warm table lamp. Gently.
Shot 2: Rack focus from letter to subject face. Eyes begin to fill. Softly.
Shot 3: Pull-back reveal. Camera widens to show empty room around subject. Unhurried.
Shot 4: Static profile shot. Subject folds letter and sets it down. No camera movement. Slowly.
```

### Rules for Multi-Shot

1. Keep each shot prompt **self-contained**: camera move + action + anchor per shot.
   Kling processes shot prompts semi-independently; narrative carry-over between shots
   is unreliable.
2. Do not chain more than 2 primary actions per shot even in multi-shot mode.
3. Total combined prompt should not exceed 300 words.
4. Transitions between shots are handled by Kling — do not describe the transition itself.

---

## 6. What Doesn't Work: Forbidden Phrases and Patterns

### Forbidden Phrases

These generic quality/aesthetic adjectives are explicitly ignored by Kling 3.0
per fal.ai's published documentation. They occupy token budget without directing
any motion or camera behavior.

**Never use:**
cinematic, beautiful, high quality, 4K, masterpiece, stunning, amazing, epic,
breathtaking, gorgeous, professional, ultra-realistic, best quality, photorealistic,
hyper-detailed, perfect, incredible, spectacular, vivid, lifelike.

These terms train-washed into background noise — Kling's motion decoder
does not map any of them to a concrete operation. A prompt that is 50% these
words is effectively half-empty (fal.ai, leonardo.ai).

### Forbidden Patterns

**1. Conceptual-only prompt**
Describes mood, theme, or narrative without any physical instruction.
```
AVOID: "A moment of pure nostalgia. The warmth of memory embraces the scene.
Time stands still as love fills the air."
```
Kling has no motion to execute. Result: arbitrary slow zoom or still frame.

**2. Redescribing the source image (I2V)**
```
AVOID: "A young girl with blonde curly hair in a white dress stands in a sunny
backyard next to a wooden fence. She is smiling. Slow dolly push-in."
```
First 28 words are wasted in I2V mode and risk hallucination if any detail
diverges from the actual source image.

**3. Simultaneous stacked motions**
```
AVOID: "She turns her head to the left and raises her arms and walks toward
the camera."
```
Three primary motions, no temporal ordering. Kling drops two of them.

**4. Content that contradicts the source image**
```
AVOID: "Snow falls heavily as she shivers in the cold."
[When source image is a sunny outdoor picnic scene.]
```
Kling cannot synthesize content that physically contradicts the source frame.
Result: either the instruction is ignored or the output diverges catastrophically
from the source composition.

---

## 7. Worked Examples: Good vs. Bad

### Example A — Portrait close-up, I2V

**Bad:**
> "A beautiful woman with long brown hair and blue eyes is sitting in a warm kitchen.
> She is wearing a cozy sweater. The light is warm and cinematic. High quality 4K.
> She looks up at the camera."

Problems: 35 words of image redescription, 5 forbidden phrases, only 7 words
of actual instruction at the end. Net instruction density: ~17%.

**Good:**
> "Slow dolly push-in. Gaze lifts from off-frame left to direct camera contact.
> Neutral expression opens slightly. Kitchen ambient light holds. Gently."

All 24 words are motion or anchor instructions. Net instruction density: 100%.

---

### Example B — Walking scene, T2V

**Bad:**
> "An epic and stunning cinematic masterpiece showing a young professional woman
> walking confidently through a beautiful city street with amazing lighting
> and gorgeous bokeh. She is breathtaking."

Problems: 10 forbidden phrases, zero camera instruction, zero temporal ordering,
no end state defined.

**Good:**
> "Steady tracking shot. Subject walks left to right, confident stride.
> City street, late afternoon golden light, shallow depth of field.
> Arms swing naturally. Camera stays level. Gradually."

---

### Example C — Multi-shot sequence

**Bad:**
> "Shot 1: The whole beautiful and cinematic story of her life unfolds.
> Shot 2: Amazing and stunning memories. Shot 3: Epic conclusion."

Problems: no motion in any shot, all forbidden phrases, no camera instructions.

**Good:**
> "Shot 1: Slow dolly push-in. Child blows out birthday candles. Warm party light. Gently.
> Shot 2: Pull-back reveal. Same subject, now adult, in same kitchen. Overhead fluorescent. Slowly.
> Shot 3: Static profile shot. Subject looks left toward window. Expression contemplative. Softly.
> Shot 4: Crane up. Camera lifts as subject stands and walks to window. Midday light. Gradually."

---

### Example D — Environmental transition

**Bad:**
> "She walks from summer into winter magically and beautifully."

Problems: physically impossible from a single source frame, forbidden phrases,
no camera instruction, vague action.

**Good:**
> "Steady tracking shot. Subject walks forward. Background lighting transitions
> from warm amber to cool blue-white. Subject's pace slows. Indoor hallway.
> Gradually."

Note: lighting transition is achievable; season swap is not.

---

## 8. Sources

All claims in this guide are grounded in the following primary sources:

1. **fal.ai — Kling 3.0 Prompting Guide**
   https://blog.fal.ai/kling-3-0-prompting-guide/
   Primary source for forbidden phrases, multi-shot parameters, I2V core rule.

2. **fal.ai — Kling 2.6 Pro Prompt Guide**
   https://fal.ai/learn/devs/kling-2-6-pro-prompt-guide
   Camera vocabulary validation, word budget research, motion constraint testing.

3. **Leonardo.ai — Kling AI Prompts**
   https://leonardo.ai/news/kling-ai-prompts/
   SCALE framework, forbidden phrase list confirmation, practical examples.

4. **Atlabs.ai — Kling 3.0 Prompting Guide: Master AI Video Generation**
   https://www.atlabs.ai/blog/kling-3-0-prompting-guide-master-ai-video-generation
   Multi-shot workflow, temporal ordering best practices, motion sequencing rules.

5. **Runway ML — Image-to-Video Prompting Guide**
   https://help.runwayml.com/hc/en-us/articles/48324313115155-Image-to-Video-Prompting-Guide
   I2V core rule, source-image hallucination risk documentation, contradicts-source pattern.

6. **InVideo.io — Best Prompts for AI Image to Video**
   https://invideo.io/blog/best-prompts-for-ai-image-to-video/
   Four-part formula, word budget research, pacing modifier vocabulary.

---

*This document is a living reference. Update when new Kling versions ship or when
wet-test results contradict any claim above. See `data/kling_prompt_rules.yaml`
for the machine-readable version loaded by story.py and prompt_writer.py.*
