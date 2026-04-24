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
        "Gentle push-in. Transition naturally from the larger indoor family gathering into the tighter portrait of the parents and two children indoors. Preserve the same family with stable faces and a warm home-photo feeling without inventing a new scene."
    ),
    "9_to_10": (
        "Slow pull-back. Transition naturally from the indoor family portrait into the sunny garden bench portrait, keeping the same parents and two children with stable faces and relaxed family continuity. Let the move from indoors to daylight feel warm and natural."
    ),
    "10_to_11": (
        "Gentle lateral drift. Transition naturally from the sunny garden bench portrait into the winter snow outing, keeping the same family with stable faces through the seasonal jump. Preserve a soft, playful family-photo feeling."
    ),
    "11_to_12": (
        "Slow push-in. Transition naturally from the winter family outing into "
        "the sunny three-generation selfie under the trees. Preserve the same "
        "family line with stable faces and let the season shift feel warm and "
        "natural."
    ),

    # --- adolescence / young woman ---

    "12_to_13": (
        "Gentle pull-back. Transition naturally from the sunny family selfie "
        "under the trees into the closer city-travel selfie. Preserve the same "
        "older woman and younger woman with stable faces, dark hair, and natural "
        "smiles as the extra family members fade from the frame."
    ),
    "13_to_14": (
        "Slow lateral drift. Transition naturally from the close three-woman "
        "selfie into the playful trail pose. Preserve the same three women with "
        "stable faces and relaxed daytime travel continuity."
    ),
    "14_to_15": (
        "Gentle pull-back. Transition naturally from the three-woman trail pose "
        "into the larger family travel portrait in the open square. Preserve the "
        "same central woman with stable face as the family group widens around "
        "her."
    ),
    "15_to_16": (
        "Slow lateral drift. Transition naturally from the open-square family "
        "travel photo into the mountain family portrait. Preserve the same core "
        "family with stable faces and bright outdoor travel continuity."
    ),
    "16_to_17": (
        "Gentle pull-back. Transition naturally from the mountain family portrait "
        "into the city three-woman pose by the historic building. Preserve the "
        "same main woman with stable face and natural expression."
    ),

    # --- B&W studio series ---

    "17_to_18": (
        "Slow push-in. Transition naturally from the city three-woman travel pose "
        "into the warm restaurant table portrait. Preserve the same women with "
        "stable faces and keep the indoor evening mood intimate and natural."
    ),
    "18_to_19": (
        "Gentle tracking shot. Transition naturally from the three-woman "
        "restaurant portrait into the family dinner table at home. Preserve the "
        "same woman with stable facial features and keep the change from dining "
        "out to home calm and real."
    ),
    "19_to_20": (
        "Slow push-in. Transition naturally from the family dinner table into the "
        "playful children portrait by the yellow flower wall. Preserve the same "
        "children with stable faces and natural expressions as the focus settles "
        "away from the adults."
    ),
    "20_to_21": (
        "Gentle lateral drift. Transition naturally from the children's indoor "
        "portrait into the bright outdoor three-woman selfie. Preserve the same "
        "main woman with stable face and let the shift from indoors to daylight "
        "feel natural."
    ),
    "21_to_22": (
        "Slow pull-back. Transition naturally from the outdoor three-woman selfie "
        "into the family kitchen portrait with flowers. Preserve the same woman "
        "and family with stable faces. Keep the scene change calm and believable."
    ),
    "22_to_23": (
        "Gentle tracking shot. Transition naturally from the family kitchen "
        "portrait into the indoor mother-and-daughter hallway pose. Preserve the "
        "same woman and little girl with stable faces. Keep the home setting "
        "consistent."
    ),

    # --- young adult / social life ---

    "23_to_24": (
        "Slow pull-back. Transition naturally from the indoor mother-and-daughter "
        "portrait into the mountain family selfie. Preserve the same woman and "
        "child with stable faces as the family opens into the travel landscape."
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
        "Slow push-in. Transition naturally from the playful event portrait into "
        "the daylight roadside selfie with the second woman. Preserve the same "
        "woman and keep faces stable, natural, and unmorphed."
    ),

    # --- dance / performance ---

    "29_to_30": (
        "Gentle tracking shot. Transition naturally from the roadside two-woman selfie into the indoor family group portrait. Preserve the same woman with stable face and keep every family member natural, without extra people or face morphing."
    ),
    "30_to_31": (
        "Slow pull-back. Transition naturally from the indoor family group into "
        "the old-town travel group portrait. Preserve the same core family with "
        "stable faces and keep the move to the city square clean and realistic."
    ),
    "31_to_32": (
        "Gentle lateral drift. Transition naturally from the old-town travel "
        "group into the home family portrait. Preserve the same family with "
        "stable faces and make the travel-to-home jump feel calm and natural."
    ),
    "32_to_33": (
        "Slow push-in. Transition naturally from the home family portrait into "
        "the Times Square travel photo. Preserve the same family with stable "
        "faces and keep the final jump bright, clean, and celebratory."
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
        "into the dance-floor couple frame. Preserve the same woman with stable "
        "face, hair, teal dress, and natural expression throughout the transition. "
        "Keep the warm reception setting and avoid inventing a new scene."
    ),
    "3_to_4": (
        "Slow lateral drift. Transition naturally from the dance-floor embrace "
        "into the close reception hug with the second woman. Preserve the same "
        "woman in teal with stable facial features and natural anatomy. Keep the "
        "same formal party atmosphere and avoid morphing faces."
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
        "Gentle push-in. Transition naturally from the larger indoor family "
        "gathering into the tighter portrait of the parents and two children "
        "indoors. Preserve the same family with stable faces and a warm home-photo "
        "feeling without inventing a new scene."
    ),
    "9_to_10": (
        "Slow pull-back. Transition naturally from the indoor family portrait into "
        "the sunny garden bench portrait, keeping the same parents and two "
        "children with stable faces and relaxed family continuity. Let the move "
        "from indoors to daylight feel warm and natural."
    ),
    "10_to_11": (
        "Gentle lateral drift. Transition naturally from the sunny garden bench "
        "portrait into the winter snow outing, keeping the same family with "
        "stable faces through the seasonal jump. Preserve a soft, playful family-"
        "photo feeling."
    ),
    "11_to_12": (
        "Slow push-in. Transition naturally from the winter family outing into "
        "the sunny three-generation selfie under the trees. Preserve the same "
        "family line with stable faces and let the season shift feel warm and "
        "natural."
    ),
    "12_to_13": (
        "Gentle pull-back. Transition naturally from the sunny family selfie "
        "under the trees into the closer city-travel selfie. Preserve the same "
        "older woman and younger woman with stable faces, dark hair, and natural "
        "smiles as the extra family members fade from the frame."
    ),
    "13_to_14": (
        "Slow lateral drift. Transition naturally from the close three-woman "
        "selfie into the playful trail pose. Preserve the same three women with "
        "stable faces and relaxed daytime travel continuity."
    ),
    "14_to_15": (
        "Gentle pull-back. Transition naturally from the three-woman trail pose "
        "into the larger family travel portrait in the open square. Preserve the "
        "same central woman with stable face as the family group widens around "
        "her."
    ),
    "15_to_16": (
        "Slow lateral drift. Transition naturally from the open-square family "
        "travel photo into the mountain family portrait. Preserve the same core "
        "family with stable faces and bright outdoor travel continuity."
    ),
    "16_to_17": (
        "Gentle pull-back. Transition naturally from the mountain family portrait "
        "into the city three-woman pose by the historic building. Preserve the "
        "same main woman with stable face and natural expression."
    ),
    "17_to_18": (
        "Slow push-in. Transition naturally from the city three-woman travel pose "
        "into the warm restaurant table portrait. Preserve the same women with "
        "stable faces and keep the indoor evening mood intimate and natural."
    ),
    "18_to_19": (
        "Gentle tracking shot. Transition naturally from the three-woman "
        "restaurant portrait into the family dinner table at home. Preserve the "
        "same woman with stable facial features and keep the change from dining "
        "out to home calm and real."
    ),
    "19_to_20": (
        "Slow push-in. Transition naturally from the family dinner table into the "
        "playful children portrait by the yellow flower wall. Preserve the same "
        "children with stable faces and natural expressions as the focus settles "
        "away from the adults."
    ),
    "20_to_21": (
        "Gentle lateral drift. Transition naturally from the children's indoor "
        "portrait into the bright outdoor three-woman selfie. Preserve the same "
        "main woman with stable face and let the shift from indoors to daylight "
        "feel natural."
    ),
    "21_to_22": (
        "Slow pull-back. Transition naturally from the outdoor three-woman selfie "
        "into the family kitchen portrait with flowers. Preserve the same woman "
        "and family with stable faces. Keep the scene change calm and believable."
    ),
    "22_to_23": (
        "Gentle tracking shot. Transition naturally from the family kitchen "
        "portrait into the indoor mother-and-daughter hallway pose. Preserve the "
        "same woman and little girl with stable faces. Keep the home setting "
        "consistent."
    ),
    "23_to_24": (
        "Slow pull-back. Transition naturally from the indoor mother-and-daughter "
        "portrait into the mountain family selfie. Preserve the same woman and "
        "child with stable faces as the family opens into the travel landscape."
    ),
    "24_to_24_b": (
        "Gentle push-in. Transition naturally from the mountain family selfie into the solo lakeside portrait. Preserve the same woman with stable face, hair, and expression. Let the landscape widen into a calmer, more cinematic frame without inventing a new scene."
    ),
    "24_b_to_24_c": (
        "Slow lateral drift. Transition naturally from the solo mountain portrait into the bright park selfie. Preserve the same woman, stable facial features, and natural outdoor continuity. Avoid morphing or changing her expression unnaturally."
    ),
    "24_c_to_25": (
        "Gentle pull-back. Transition naturally from the solo garden selfie into the garden portrait with the two children. Preserve the same woman with stable face and keep both children natural and unmorphed."
    ),
    "25_to_25_b": (
        "Slow push-in. Transition naturally from the sunny garden portrait of the mother and two children into the playful birthday jumping scene. Preserve the same children with stable faces and keep the home celebration joyful but natural."
    ),
    "25_b_to_26": (
        "Gentle tracking shot. Transition naturally from the playful birthday scene into the warm indoor portrait of the mother holding her son. Preserve the same woman and boy with stable faces and calm family continuity."
    ),
    "26_to_27_b": (
        "Slow lateral drift. Transition naturally from the indoor mother-and-son portrait into the garden two-woman portrait. Preserve the same woman with stable face and let the scene open back into daylight."
    ),
    "27_b_to_28": (
        "Gentle pull-back. Transition naturally from the daytime garden two-woman portrait into the playful event snapshot with the costumed companion. Preserve the same woman with stable face and keep the festive outdoor mood fun and natural."
    ),
    "28_to_29": (
        "Slow push-in. Transition naturally from the playful event portrait into "
        "the daylight roadside selfie with the second woman. Preserve the same "
        "woman and keep faces stable, natural, and unmorphed."
    ),
    "29_to_30": (
        "Gentle tracking shot. Transition naturally from the daylight two-woman "
        "selfie into the indoor family group portrait. Preserve all original "
        "people exactly once with stable faces and natural anatomy. Avoid "
        "inventing extra guests or morphing any face."
    ),
    "30_to_31": (
        "Slow pull-back. Transition naturally from the indoor family group into "
        "the old-town travel group portrait. Preserve the same core family with "
        "stable faces and keep the move to the city square clean and realistic."
    ),
    "31_to_32": (
        "Gentle lateral drift. Transition naturally from the old-town travel "
        "group into the home family portrait. Preserve the same family with "
        "stable faces and make the travel-to-home jump feel calm and natural."
    ),
    "32_to_33": (
        "Slow push-in. Transition naturally from the home family portrait into "
        "the Times Square travel photo. Preserve the same family with stable "
        "faces and keep the final jump bright, clean, and celebratory."
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
