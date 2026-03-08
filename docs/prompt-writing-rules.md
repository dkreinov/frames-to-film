# Prompt Writing Rules For Kling Pair Prompts

This document defines the exact writing rules for future updates to
[`image_pair_prompts.py`](D:/Programming/olga_movie/image_pair_prompts.py).
It is grounded in the current pair-by-pair flow:

- start frame
- end frame
- one Kling image-to-video prompt

The goal is not more poetic prompts. The goal is more reliable prompts.

## 1. Current Prompt Audit

### What the current prompts do well

1. They start from camera language instead of abstract storytelling.
2. They preserve the movie's tone and life-stage progression well.
3. They are short enough for Kling to follow without excessive clutter.

### What the current prompts do poorly

1. Many prompts are too lyrical and underconstrain the actual transition.
2. Identity continuity is often implied instead of stated when the face is fragile.
3. Several prompts describe mood better than they describe what must stay stable.

### Common current patterns

These examples capture the current prompt style:

1. Portrait-to-portrait:
   `Slow dolly push-in. Warm sepia tones deepen. Gentle focus shift. Innocent, intimate childhood close-up.`
2. Color or setting transition:
   `Gentle dolly push-in. Color bedroom warmth fades into dramatic B&W studio lighting. Draped curtain. Artistic transformation.`
3. Performance or motion scene:
   `Gentle tracking drift. Sepia stillness gives way to vibrant color and movement. Living-room flash. Dancing with abandon.`

### Strength summary

- The prompts usually choose a clear shot language.
- They support emotional continuity across the life-story sequence.
- They avoid long overloaded prompt paragraphs.

### Weakness summary

- They often leave too much room for face drift and scene invention.
- They rely too much on soft mood phrases like `warmth`, `nostalgia`, or `transformation`.
- They do not consistently separate shot direction from continuity constraints.

## 2. Canonical Prompt Architecture

All future pair prompts should follow this order:

1. Camera move.
2. Transition behavior between the two source frames.
3. Subject continuity when needed.
4. Scene, lighting, and style continuity.
5. Optional hard constraint for fragile pairs.

### Canonical template

```text
[Camera move]. Transition naturally between the two source frames. [Subject continuity when needed]. Preserve the setting, lighting continuity, and photographic style.
```

### Short fallback template

```text
Gentle camera move. Natural frame-to-frame transition. Preserve the same setting, lighting continuity, and photographic tone.
```

### Retry template

```text
[Camera move]. The same person remains stable from start to end with natural facial features and realistic anatomy. Keep the transition calm, gentle, and anchored to the two source frames. Preserve the setting, lighting continuity, and photographic style.
```

### Old style vs new style

Old:

```text
Gentle dolly push-in. Color bedroom warmth fades into dramatic B&W studio lighting. Draped curtain. Artistic transformation.
```

New:

```text
Gentle dolly push-in. Transition naturally from warm bedroom color into dramatic black-and-white studio lighting. The same woman remains consistent from start to end with stable facial features. Preserve the draped-curtain setting and photographic continuity.
```

## 3. Exact Writing Rules

### Do

1. Use 2 to 4 short sentences.
2. Start with a camera move in the first sentence.
3. Name the transition behavior directly: `transition naturally`, `dissolve gently`, `drift into`.
4. State identity continuity explicitly when the pair is face-sensitive.
5. State scene continuity explicitly when the pair risks inventing a new location.
6. Use concrete visual anchors like `draped-curtain studio`, `winter trees`, or `fairy-light reception`.
7. Keep emotional tone secondary to continuity and physical plausibility.
8. Use simple, film-like wording rather than abstract art language.

### Don't

1. Do not rely on mood alone to explain the transition.
2. Do not ask for a transformation unless the source frames truly imply one.
3. Do not use vague phrases like `artistic transformation` as the main instruction.
4. Do not describe a new third scene unless the two frames clearly justify it.
5. Do not stack multiple camera moves in one prompt.
6. Do not bury continuity constraints inside decorative prose.
7. Do not overuse sentimental words like `tender`, `warmth`, or `nostalgia` if they replace physical direction.
8. Do not write prompts as mini screenplays.

### Recommended phrase patterns

1. `Gentle dolly push-in.`
2. `Slow lateral drift.`
3. `Transition naturally between the two source frames.`
4. `The same woman remains consistent from start to end.`
5. `Preserve the setting, lighting continuity, and photographic style.`

### Discouraged phrase patterns

1. `Artistic transformation.`
2. `A quiet passage of time.`
3. `Warm, tender nostalgia.`
4. `New chapter on the horizon.`
5. `A journey complete, new life in full bloom.`

These phrases are not banned forever, but they should not carry the prompt by themselves.

## 4. Preferred Wording Style

### Sentence count

- Default to 3 sentences.
- Use 2 when the pair is visually simple.
- Use 4 only when continuity needs an extra hard constraint.

### Camera wording

Use one move only:

- `Gentle dolly push-in`
- `Slow pull-back`
- `Gentle lateral drift`
- `Slow tracking shot`
- `Soft handheld drift`

### Identity wording

Use identity wording when:

- the pair is a close-up
- the pair has already shown face drift
- the pair moves between very different lighting setups
- the pair transitions between portrait and action

Preferred identity wording:

- `The same woman remains consistent from start to end.`
- `Keep the same face and stable facial structure throughout.`
- `Preserve the same person, age, and identity.`

### Scene continuity wording

Use scene continuity wording when:

- the frames are in the same room
- the transition must not invent a new location
- the pair risks turning into fantasy or horror

Preferred scene wording:

- `Preserve the same setting implied by the two frames.`
- `Stay anchored to the existing room and lighting continuity.`
- `Do not invent a different environment.`

### Tone wording

Tone should support, not lead.

Good:

- `quiet confidence`
- `gentle celebration`
- `warm domestic light`
- `restrained stage energy`

Less useful unless supported by hard direction:

- `nostalgia`
- `transformation`
- `radiance`
- `new beginnings`

### B&W and color transitions

State them literally:

- `Transition from warm color into black-and-white studio lighting.`
- `Monochrome softens into faded summer color.`
- `Warm sepia gives way to bright resort color.`

Avoid turning the color change into metaphor.

## 5. Transition-Type Variants

### Portrait-to-portrait

```text
Gentle dolly push-in. Transition naturally between the two portraits with stable facial features and restrained motion. Preserve the same studio mood, lighting continuity, and photographic style.
```

### Same-room pose change

```text
Slow lateral drift. Keep the same room, the same person, and a natural shift in pose or expression. Preserve the existing lighting and background details.
```

### Indoor-to-outdoor

```text
Slow pull-back. Transition naturally from the indoor frame into the outdoor frame without inventing a third location. Preserve the same person and let the lighting change follow the two source images.
```

### Outdoor-to-indoor

```text
Gentle push-in. Transition naturally from outdoor daylight into the interior frame while keeping the same person and mood continuity. Preserve the real setting implied by the two source images.
```

### B&W-to-color or color-to-B&W

```text
Gentle camera move. Transition clearly from [source tone] into [target tone] while keeping the same subject and realistic continuity. Preserve the photographic texture and avoid surreal morphing.
```

### Milestone or ceremony scene

```text
Slow tracking shot. Transition naturally between the two milestone moments while keeping the same people and emotional continuity. Preserve the lighting, wardrobe logic, and event setting.
```

### Dance or motion-heavy scene

```text
Gentle tracking drift. Keep the same performer and let the motion build naturally between the two frames without anatomy distortion. Preserve the scene, lighting continuity, and controlled kinetic energy.
```

## 6. Current-State Rules For This Repo

Use these rules today, before face-consistency reference is added:

1. Identity continuity should be explicit on fragile pairs.
2. Retry prompts should be stricter than first-pass prompts.
3. If a pair has already failed on face drift, state `same woman` or `same person` directly.
4. If a pair has already failed on transition tone, state `calm`, `gentle`, or `non-scary` directly.

### First-pass example

```text
Gentle dolly push-in. Transition naturally from warm bedroom color into dramatic black-and-white studio lighting. The same woman remains consistent from start to end. Preserve the draped-curtain setting and photographic continuity.
```

### Retry example for face_bad + identity_drift + transition_bad

```text
Gentle dolly push-in. The same woman remains stable from start to end with natural facial features and no morphing. Keep the transition calm, gentle, and non-scary while staying anchored to the two source frames. Preserve the draped-curtain studio continuity and black-and-white lighting.
```

## 7. Future Rules With Face Consistency Enabled

Once Kling element-based face consistency is added, prompts should carry less identity burden.

### What changes

- The prompt should still mention continuity.
- The prompt should no longer spend half its length proving identity.
- The element reference should carry most of the subject lock.

### With face consistency enabled

Prefer:

```text
Gentle dolly push-in. Transition naturally between the two source frames with restrained, realistic motion. Preserve the setting, lighting continuity, and photographic style.
```

Use stronger identity wording only when:

- the pair is a close-up with known drift risk
- the age or lighting gap is large
- a prior retry already failed

### Retry rules with face consistency enabled

These issue tags should still trigger explicit hard constraints:

- `face_bad`
- `identity_drift`
- `hands_body_bad`
- `transition_bad`
- `scenario_wrong`
- `background_wrong`

### Prompt simplification note

When `element_list` is added to Kling requests, prompts should become more operational:

- more about motion
- more about frame-to-frame continuity
- less about pleading for identity stability

That should improve prompt clarity and reduce redundant wording.
