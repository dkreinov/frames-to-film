"""Per-pair cinematic prompts for Kling AI video generation.

Each key maps a transition pair (e.g. "3_to_4") to a short,
camera-first cinematic prompt optimised for Kling 3.0 start+end-frame
video generation. Kling infers motion from the two frames; the prompt
should guide camera movement, transition behavior, and continuity rather
than inventing a new scene.

Canonical prompt shape for future rewrites:
1. Camera move.
2. Frame-to-frame transition behavior.
3. Subject or identity continuity when needed.
4. Scene, lighting, and style continuity.

See docs/prompt-writing-rules.md for the exact writing rules, transition
variants, and future face-consistency guidance.
"""

FALLBACK_PROMPT = (
    "Gentle push-in, cinematic continuity, soft lighting carryover, "
    "vintage warmth. Smooth transition."
)

PAIR_PROMPTS = {
    # --- childhood (B&W / sepia vintage) ---

    "3_to_4": (
        "Slow lateral tracking shot drifting right. Vintage B&W film grain. "
        "Soft lamplight dissolves one childhood moment into the next. "
        "Warm, tender nostalgia."
    ),
    "4_to_5": (
        "Slow dolly push-in toward the face. Warm sepia tones deepen. "
        "Gentle focus shift. Innocent, intimate childhood close-up."
    ),
    "5_to_6": (
        "Gentle pull-back revealing a vintage portrait. B&W film grain. "
        "Soft directional light. A quiet passage of time."
    ),
    "6_to_7": (
        "Slow crossfade drift. Monochrome gives way to faded sun-washed color. "
        "Gentle handheld sway. From portrait studio into a sunlit garden."
    ),
    "7_to_8": (
        "Gentle lateral pan through a summer garden. Warm faded color. "
        "Soft bokeh. Carefree childhood afternoon light."
    ),
    "8_to_9": (
        "Slow dolly push-in from outdoors through a window into a warm interior. "
        "Faded color settles into soft sepia. Playful energy, childhood joy."
    ),
    "9_to_10": (
        "Gentle tracking shot, steadicam. From playful candid to composed studio portrait. "
        "Warm tones deepen. Growing up, gaining poise."
    ),
    "10_to_11": (
        "Slow pull-back revealing autumn foliage. Studio warmth opens into "
        "dappled natural light. Gentle breeze. Adolescence emerging."
    ),
    "11_to_12": (
        "Gentle push-in with soft handheld drift. Outdoor autumn light "
        "transitions to warm indoor lamplight. Familial tenderness."
    ),

    # --- adolescence / young woman ---

    "12_to_13": (
        "Slow dolly push-in. Warm amber tones. From a candid family moment "
        "into a poised studio portrait. Quiet confidence."
    ),
    "13_to_14": (
        "Gentle tracking drift from studio backdrop out through a fence "
        "into dappled outdoor light. B&W film grain. Curiosity, openness."
    ),
    "14_to_15": (
        "Slow push-in. Outdoor daylight softens into even studio light. "
        "B&W film look. A bright, radiant smile emerges."
    ),
    "15_to_16": (
        "Gentle lateral tracking. One studio portrait dissolves into another. "
        "Sepia warmth. Film-strip edges. Growing self-assurance."
    ),
    "16_to_17": (
        "Slow pull-back from posed portrait into a candid intimate scene. "
        "B&W gives way to warm domestic color. Tender closeness."
    ),

    # --- B&W studio series ---

    "17_to_18": (
        "Gentle dolly push-in. Color bedroom warmth fades into dramatic "
        "B&W studio lighting. Draped curtain. Artistic transformation."
    ),
    "18_to_19": (
        "Slow lateral tracking across draped fabric. B&W studio continuity. "
        "Elegant pose shifts to playful confidence. Same space, new energy."
    ),
    "19_to_20": (
        "Gentle handheld drift. B&W studio. Hat and stillness give way to "
        "flowing hair and dynamic movement. Building energy."
    ),
    "20_to_21": (
        "Slow tracking shot. B&W draped studio. Movement settles into "
        "graceful elegance. Soft directional light. Poise."
    ),
    "21_to_22": (
        "Gentle push-in dissolving studio interior into a winter outdoor "
        "close-up. B&W continuity. Bokeh trees. Warm despite the cold."
    ),
    "22_to_23": (
        "Slow dolly push-in tightening the frame. B&W. Winter warmth "
        "deepens into dramatic shadow. Contemplative intensity."
    ),

    # --- young adult / social life ---

    "23_to_24": (
        "Gentle pull-back. Dramatic B&W portrait opens into a warm color "
        "scene around a table. Laughter replaces solitude. Celebration."
    ),
    "24_to_25": (
        "Slow tracking shot drifting from table to doorway. Color warmth "
        "continues. Winter fur and a confident smile. Festive elegance."
    ),
    "25_to_26": (
        "Gentle push-in from doorway into a lived-in room. Warm interior light. "
        "Champagne raised. Companionship and joy."
    ),
    "26_to_27": (
        "Slow lateral tracking. From a cozy room into a cafe interior. "
        "Wood-panel warmth. Everyday purpose and craft."
    ),
    "27_to_28": (
        "Gentle pull-back revealing tropical greenery. Cafe warmth "
        "opens into bright resort light. Family together on holiday."
    ),
    "28_to_29": (
        "Slow dolly push-in. Bright resort color softens into warm "
        "sepia studio tones. Vintage lace shawl. Reflective intimacy."
    ),

    # --- dance / performance ---

    "29_to_30": (
        "Gentle tracking drift. Sepia stillness gives way to vibrant color "
        "and movement. Living-room flash. Dancing with abandon."
    ),
    "30_to_31": (
        "Slow lateral pan. One dance flows into another. Floral dress "
        "becomes lavender costume. Barefoot passion."
    ),
    "31_to_32": (
        "Gentle pull-back from living room practice into stage lights. "
        "Color intensifies. From rehearsal to the spotlight."
    ),
    "32_to_33": (
        "Slow dolly push-in. Stage lights dim into soft domestic lamplight. "
        "Casual denim. From performer back to everyday life."
    ),

    # --- professional / milestone ---

    "33_to_33_b": (
        "Gentle tracking shot. Living room dissolves into a bright classroom. "
        "Warm steady light. Teaching, sharing knowledge."
    ),
    "33_b_to_34": (
        "Slow push-in. Classroom light transforms into warm fairy-light bokeh. "
        "White dress and veil emerge. Love, new beginnings."
    ),
    "34_to_35": (
        "Gentle lateral tracking. Wedding couple with document transitions "
        "to family gathered under fairy lights. Ceremony warmth."
    ),
    "35_to_35_b": (
        "Slow pull-back from ceremony into joyful reception. Fairy lights "
        "become dance-floor glow. Celebration and movement."
    ),

    # --- pregnancy / family ---

    "35_b_to_36": (
        "Gentle dolly out from indoor celebration into a panoramic overlook. "
        "Blue sky opens wide. A new chapter on the horizon."
    ),
    "36_to_37": (
        "Slow push-in. Bright daytime panorama dissolves into city lights "
        "through apartment windows at night. Quiet anticipation."
    ),
    "37_to_38": (
        "Gentle pull-back. Solo silhouette by the window widens to reveal "
        "a couple together. Night glow. Warmth of partnership."
    ),
    "38_to_39": (
        "Slow lateral tracking. Living-room couple shot drifts into a "
        "hallway mirror reflection. Golden tones. Counting the days."
    ),
    "39_to_40": (
        "Gentle tracking shot moving forward. Mirror selfie opens into "
        "a neighborhood sidewalk. Overcast daylight. Parenthood begins."
    ),
    "40_to_41": (
        "Slow dolly push-in. Street scene softens into a close overhead view "
        "of twin babies side by side. Warm blankets, soft light. "
        "A journey complete, new life in full bloom."
    ),
}
