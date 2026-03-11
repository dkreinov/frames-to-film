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
    "Gentle push-in. Transition naturally between the two source frames. "
    "Preserve the same setting, lighting continuity, and photographic style."
)

PAIR_PROMPTS = {
    # --- childhood (B&W / sepia vintage) ---

    "3_to_4": (
        "Slow lateral drift. Transition naturally between the two childhood "
        "moments in vintage black-and-white. Preserve soft lamplight, film "
        "grain, and gentle nostalgic continuity."
    ),
    "4_to_5": (
        "Slow dolly push-in. Transition naturally into a closer childhood "
        "portrait. Preserve warm sepia tones, soft focus, and the same "
        "innocent mood."
    ),
    "5_to_6": (
        "Gentle pull-back. Transition naturally from the close portrait into "
        "a wider vintage portrait. Preserve black-and-white film grain, soft "
        "directional light, and period continuity."
    ),
    "6_to_7": (
        "Slow crossfade drift. Transition from monochrome studio portrait "
        "into faded sun-washed garden color. Preserve the same child and keep "
        "the motion gentle and realistic."
    ),
    "7_to_8": (
        "Gentle lateral pan. Transition naturally within the summer garden "
        "setting. Preserve warm faded color, soft bokeh, and carefree "
        "childhood continuity."
    ),
    "8_to_9": (
        "Slow dolly push-in. Transition naturally from the outdoor frame into "
        "the warm interior frame without inventing a new location. Preserve "
        "the playful childhood tone and sepia carryover."
    ),
    "9_to_10": (
        "Gentle tracking shot. Transition naturally from playful candid "
        "energy into a composed studio portrait. Preserve warm tonal "
        "continuity and a natural sense of growing poise."
    ),
    "10_to_11": (
        "Slow pull-back. Transition naturally from the studio portrait into "
        "the autumn outdoor frame. Preserve dappled light, soft breeze, and "
        "adolescent continuity."
    ),
    "11_to_12": (
        "Gentle push-in with soft handheld drift. Transition naturally from "
        "outdoor autumn light into warm indoor lamplight. Preserve the same "
        "family warmth and photographic continuity."
    ),

    # --- adolescence / young woman ---

    "12_to_13": (
        "Slow dolly push-in. Transition naturally from the candid family "
        "frame into the poised studio portrait. Preserve warm amber tones "
        "and quiet confidence."
    ),
    "13_to_14": (
        "Gentle tracking drift. Transition naturally from the studio backdrop "
        "into the outdoor fence setting. Preserve black-and-white film grain "
        "and the same bright, curious presence."
    ),
    "14_to_15": (
        "Slow push-in. Transition naturally from outdoor daylight into even "
        "studio light. Preserve the same young woman, black-and-white "
        "continuity, and radiant smile."
    ),
    "15_to_16": (
        "Gentle lateral drift. Transition naturally between the two studio "
        "portraits. Preserve sepia warmth, film-strip texture, and growing "
        "self-assurance."
    ),
    "16_to_17": (
        "Slow pull-back. Transition naturally from the posed portrait into "
        "the candid intimate scene. Preserve the same woman, the "
        "black-and-white to warm domestic shift, and emotional continuity."
    ),

    # --- B&W studio series ---

    "17_to_18": (
        "Gentle dolly push-in. Transition naturally from warm bedroom color "
        "into dramatic black-and-white studio lighting. The same woman "
        "remains consistent from start to end. Preserve the draped-curtain "
        "setting and photographic continuity."
    ),
    "18_to_19": (
        "Slow lateral drift. Keep the same black-and-white draped studio and "
        "the same woman as the pose shifts into playful confidence. Preserve "
        "soft directional light and natural continuity."
    ),
    "19_to_20": (
        "Soft handheld drift. Keep the same black-and-white studio and the "
        "same woman as stillness gives way to subtle movement. Preserve "
        "stable facial features, flowing hair, and controlled energy."
    ),
    "20_to_21": (
        "Slow tracking shot. Keep the same black-and-white draped studio as "
        "the motion settles into a more elegant pose. Preserve soft "
        "directional light, stable anatomy, and poised continuity."
    ),
    "21_to_22": (
        "Gentle push-in. Transition naturally from the black-and-white studio "
        "frame into the winter outdoor close-up without inventing a third "
        "setting. Preserve the same woman and soft bokeh continuity."
    ),
    "22_to_23": (
        "Slow dolly push-in. Keep the same winter black-and-white setting as "
        "the frame tightens and the shadows deepen. Preserve the same face, "
        "dramatic lighting, and contemplative tone."
    ),

    # --- young adult / social life ---

    "23_to_24": (
        "Gentle pull-back. Transition naturally from the dramatic "
        "black-and-white portrait into the warm table scene. The same woman "
        "remains consistent from start to end. Preserve a calm, natural "
        "transition and celebration continuity."
    ),
    "24_to_25": (
        "Slow tracking shot. Transition naturally from the table scene "
        "toward the doorway portrait without inventing a different setting. "
        "Preserve the same woman, winter wardrobe, and warm festive light."
    ),
    "25_to_26": (
        "Gentle push-in. Transition naturally from the doorway frame into "
        "the lived-in interior scene. Preserve warm interior light, the same "
        "woman, and a relaxed celebratory mood."
    ),
    "26_to_27": (
        "Slow lateral drift. Transition naturally from the cozy room into "
        "the cafe interior. Preserve wood-panel warmth, the same woman, and "
        "everyday continuity."
    ),
    "27_to_28": (
        "Gentle pull-back. Transition naturally from the cafe frame into "
        "the bright resort family scene. Preserve the same woman, stable "
        "facial features, and clean daylight continuity."
    ),
    "28_to_29": (
        "Slow dolly push-in. Transition naturally from bright resort color "
        "into warm sepia studio tones. Preserve the same woman, the lace "
        "shawl detail, and reflective continuity."
    ),

    # --- dance / performance ---

    "29_to_30": (
        "Gentle tracking drift. Transition naturally from sepia stillness "
        "into vibrant living-room movement. Preserve the same performer, "
        "stable facial features, and controlled dance energy."
    ),
    "30_to_31": (
        "Slow lateral pan. Keep the same dancer and let one dance pose flow "
        "naturally into the next. Preserve vibrant color, costume "
        "continuity, and natural body motion."
    ),
    "31_to_32": (
        "Gentle pull-back. Transition naturally from living-room practice "
        "into stage lights. Preserve the same performer, intensifying color, "
        "and rehearsal-to-performance continuity."
    ),
    "32_to_33": (
        "Slow dolly push-in. Transition naturally from stage light into soft "
        "domestic lamplight. Preserve the same woman, casual denim, and a "
        "calm return to everyday life."
    ),

    # --- professional / milestone ---

    "33_to_33_b": (
        "Gentle tracking shot. Transition naturally from the living room "
        "into the bright classroom. Preserve the same woman, warm steady "
        "light, and a grounded teaching atmosphere."
    ),
    "33_b_to_34": (
        "Slow push-in. Transition naturally from classroom light into warm "
        "fairy-light wedding bokeh. Preserve the same woman, the white dress "
        "and veil, and gentle milestone continuity."
    ),
    "34_to_35": (
        "Gentle lateral drift. Transition naturally from the wedding couple "
        "frame into the family gathering under fairy lights. Preserve the "
        "ceremony setting, warm light, and the same people."
    ),
    "35_to_35_b": (
        "Slow pull-back. Transition naturally from the ceremony into the "
        "joyful reception. Preserve fairy-light continuity, the same people, "
        "and controlled celebratory movement."
    ),

    # --- pregnancy / family ---

    "35_b_to_36": (
        "Gentle dolly out. Transition naturally from the indoor celebration "
        "into the panoramic overlook without inventing a third setting. "
        "Preserve open daylight and a calm sense of forward movement."
    ),
    "36_to_37": (
        "Slow push-in. Transition naturally from the daytime panorama into "
        "the apartment night window scene. Preserve the same woman, stable "
        "facial features, and quiet anticipation."
    ),
    "37_to_38": (
        "Gentle pull-back. Transition naturally from the solo window "
        "silhouette into the couple frame. Preserve night-glow continuity, "
        "the same woman, and warm partnership."
    ),
    "38_to_39": (
        "Slow lateral drift. Transition naturally from the living-room "
        "couple frame into the hallway mirror reflection. Preserve golden "
        "tones, the same people, and domestic continuity."
    ),
    "39_to_40": (
        "Gentle tracking shot forward. Transition naturally from the mirror "
        "selfie into the neighborhood sidewalk frame. Preserve the same "
        "couple, overcast daylight, and early-parenthood continuity."
    ),
    "40_to_41": (
        "Slow dolly push-in. Transition naturally from the street scene into "
        "the overhead view of twin babies. Preserve warm blankets, soft "
        "light, and the sense of one life chapter becoming the next."
    ),
}

OLIA_CONTINUE_EXTEND_API_PAIR_PROMPTS = {
    "2_to_3": (
        "Gentle pull-back. Transition naturally from the solo evening portrait "
        "into the dance-floor couple frame. Preserve the same woman, teal dress, "
        "and warm reception lighting."
    ),
    "3_to_4": (
        "Slow lateral drift. Transition naturally from the dance-floor embrace "
        "into the close reception hug with the second woman. Preserve the same "
        "woman in teal and the same formal party atmosphere."
    ),
    "4_to_5": (
        "Gentle pull-back. Transition naturally from the reception portrait into "
        "the later home snapshot of the two small children on the sofa. Keep the "
        "time jump calm and memory-like without inventing a third scene."
    ),
    "5_to_6": (
        "Slow push-in. Transition naturally from the indoor children portrait "
        "into the outdoor family garden scene. Preserve the same family and let "
        "the move from home to daylight feel warm and natural."
    ),
    "6_to_7": (
        "Gentle lateral drift. Transition naturally between the two outdoor "
        "family portraits. Preserve the same parents and children, bright garden "
        "light, and relaxed summer mood."
    ),
    "7_to_8": (
        "Slow pull-back. Transition naturally from the garden portrait into the "
        "indoor family snapshot. Preserve the same parents and children and keep "
        "the shift playful and natural."
    ),
    "8_to_9": (
        "Gentle tracking shot. Transition naturally from the indoor family moment "
        "into the sunny park bench portrait. Preserve the same family and a calm "
        "daytime continuity."
    ),
    "9_to_10": (
        "Slow pull-back. Transition naturally from the sunny park portrait into "
        "the winter snow scene. Preserve the same children and family-story "
        "continuity through the seasonal jump."
    ),
    "10_to_11": (
        "Gentle push-in. Transition naturally from the snowy family outing into "
        "the close portrait of the two children. Preserve the same children and "
        "keep the winter mood soft and natural."
    ),
    "11_to_12": (
        "Slow lateral drift. Transition naturally from the children’s close "
        "portrait into the bright two-woman selfie. Keep faces natural and let "
        "the family timeline move forward without inventing a new scene."
    ),
    "12_to_13": (
        "Gentle pull-back. Transition naturally from the close selfie into the "
        "outdoor walking scene. Preserve the same woman and keep the daylight "
        "travel mood calm and realistic."
    ),
    "13_to_14": (
        "Slow tracking drift. Transition naturally from the walking path into the "
        "waterfront trio selfie. Preserve the same woman, open daylight, and "
        "travel-day continuity."
    ),
    "14_to_15": (
        "Gentle push-in. Transition naturally between the two outdoor trio "
        "portraits. Preserve the same women, soft daylight, and relaxed holiday "
        "continuity."
    ),
    "15_to_16": (
        "Slow lateral drift. Transition naturally from the trio portrait into the "
        "city travel frame. Preserve the same woman, bright outdoor light, and "
        "tourist-day continuity."
    ),
    "16_to_17": (
        "Gentle pull-back. Transition naturally from the two-woman city portrait "
        "into the larger group travel shot. Preserve the same woman and the same "
        "European city atmosphere."
    ),
    "17_to_18": (
        "Slow push-in. Transition naturally from the city-square group portrait "
        "into the warm café table selfie. Preserve the same woman and keep the "
        "travel mood intimate and natural."
    ),
    "18_to_19": (
        "Gentle tracking shot. Transition naturally from the café selfie into the "
        "family table celebration at home. Preserve the same woman and keep the "
        "change from travel to home feeling calm and real."
    ),
    "19_to_20": (
        "Slow push-in. Transition naturally from the family dinner table into the "
        "portrait with the strawberry tart and children. Preserve the same woman "
        "and children and keep the home celebration continuity."
    ),
    "20_to_21": (
        "Gentle lateral drift. Transition naturally from the home celebration "
        "portrait into the three-woman outdoor selfie. Preserve the same woman "
        "and let the shift from indoors to bright daylight feel natural."
    ),
    "21_to_22": (
        "Slow pull-back. Transition naturally from the outdoor selfie into the "
        "family kitchen portrait with flowers. Preserve the same woman and family "
        "and keep the scene change calm and believable."
    ),
    "22_to_23": (
        "Gentle tracking shot. Transition naturally from the bouquet family "
        "portrait into the playful costume moment at home. Preserve the same "
        "woman and child and keep the house setting consistent."
    ),
    "23_to_24": (
        "Slow pull-back. Transition naturally from the indoor costume scene into "
        "the mountain family selfie. Preserve the same family and make the jump "
        "to the travel landscape feel clear but gentle."
    ),
    "24_to_24_b": (
        "Gentle push-in. Transition naturally from the mountain family selfie "
        "into the solo lakeside portrait. Preserve the same woman and let the "
        "landscape widen into a calmer, more cinematic frame."
    ),
    "24_b_to_24_c": (
        "Slow lateral drift. Transition naturally from the solo mountain portrait "
        "into the bright park selfie. Preserve the same woman, stable facial "
        "features, and natural outdoor continuity."
    ),
    "24_c_to_25": (
        "Gentle pull-back. Transition naturally from the outdoor selfie into the "
        "garden portrait with the two children. Preserve the same woman and keep "
        "the family mood warm and natural."
    ),
    "25_to_25_b": (
        "Slow push-in. Transition naturally from the sunny garden family portrait "
        "into the birthday scene with cake. Preserve the same parents and "
        "children and keep every face stable and natural."
    ),
    "25_b_to_26": (
        "Gentle tracking shot. Transition naturally from the birthday cake group "
        "into the warm restaurant portrait with mother and son. Preserve the same "
        "woman and child and keep the indoor celebration continuity."
    ),
    "26_to_27_b": (
        "Slow lateral drift. Transition naturally from the restaurant portrait "
        "into the garden two-woman portrait. Preserve the same woman, stable "
        "face, and warm daylight continuity."
    ),
    "27_b_to_28": (
        "Gentle pull-back. Transition naturally from the garden portrait into the "
        "night street celebration scene. Preserve the same couple and keep the "
        "move from daylight to nightlife playful and natural."
    ),
    "28_to_29": (
        "Slow push-in. Transition naturally from the playful night-street couple "
        "portrait into the daylight two-woman selfie. Preserve the same woman "
        "and keep faces stable and natural."
    ),
    "29_to_30": (
        "Gentle tracking shot. Transition naturally from the daylight two-woman "
        "selfie into the indoor family group portrait. Preserve all original "
        "people exactly once and avoid inventing extra guests."
    ),
    "30_to_31": (
        "Slow pull-back. Transition naturally from the indoor family group into "
        "the old-town travel portrait. Preserve the same core family and keep "
        "the move to the city square clean and realistic."
    ),
    "31_to_32": (
        "Gentle lateral drift. Transition naturally from the city-square tourist "
        "portrait into the home birthday scene with the fruit tray. Preserve the "
        "same family and make the travel-to-home jump feel calm and natural."
    ),
    "32_to_33": (
        "Slow push-in. Transition naturally from the home birthday portrait into "
        "the Times Square family travel photo. Preserve the same family and keep "
        "the final jump bright, clean, and celebratory."
    ),
}


def normalize_prompt_folder_label(folder_label: str) -> str:
    return folder_label.replace("/", "\\").strip().lower()


def get_pair_prompt(pair_key: str, folder_label: str = "") -> str:
    normalized_folder = normalize_prompt_folder_label(folder_label)
    if normalized_folder == "olia_continue\\extend_api":
        return OLIA_CONTINUE_EXTEND_API_PAIR_PROMPTS.get(
            pair_key,
            PAIR_PROMPTS.get(pair_key, FALLBACK_PROMPT),
        )
    return PAIR_PROMPTS.get(pair_key, FALLBACK_PROMPT)
