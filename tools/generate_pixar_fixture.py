#!/usr/bin/env python3
"""Generate the 6-frame Pixar fixture for Phase 1 watermark tests.

3 frames via Gemini web (carry watermark) + 3 via ChatGPT web (clean).
Uses Playwright persistent Chrome profiles — no Claude-in-Chrome MCP involved,
so no CDP/extension interference with the target sites' XHR buses.

Usage (Windows):
  C:\\Users\\nishtiak\\AppData\\Local\\Programs\\Python\\Python312\\python.exe ^
    D:\\Programming\\olga_movie\\tools\\generate_pixar_fixture.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

try:
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    from playwright.sync_api import sync_playwright
except ModuleNotFoundError as exc:
    raise SystemExit(
        "Missing dependency: playwright.\n"
        "  python -m pip install playwright && python -m playwright install chromium\n"
    ) from exc


ROOT_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT_DIR / "tests" / "fixtures" / "fake_project"
GEMINI_PROFILE = ROOT_DIR / ".gemini_chrome_profile"
CHATGPT_PROFILE = ROOT_DIR / ".chatgpt_chrome_profile"


GEMINI_PROMPTS = [
    (
        "frame_1_gemini.png",
        "Generate a Pixar 3D cinematic 16:9 widescreen image. "
        "An orange tabby kitten named Cosmo wearing a white astronaut spacesuit "
        "with a round glass helmet. He just landed on the gray cratered surface of the moon, "
        "next to a tiny silver rocket. Earth glows blue-green in the black starry sky. "
        "Warm rim lighting, joyful curious mood.",
    ),
    (
        "frame_2_gemini.png",
        "Generate a Pixar 3D cinematic 16:9 widescreen image. "
        "Same orange tabby kitten Cosmo in his white astronaut suit with glass helmet. "
        "He is kneeling on the moon's surface, looking with wide eyes at a small glowing "
        "cyan-blue mushroom growing out of moon dust. Earth visible in the black starry sky. "
        "Magical soft light, warm highlights on Cosmo's helmet, wonder-filled mood.",
    ),
    (
        "frame_3_gemini.png",
        "Generate a Pixar 3D cinematic 16:9 widescreen image. "
        "Same orange tabby kitten Cosmo in his white astronaut suit on the moon. "
        "He is sitting next to the glowing cyan mushroom and sharing a cheese-shaped "
        "space-snack, holding it out toward the mushroom. Earth in the starry sky. "
        "Warm friendship mood, soft rim light, Pixar quality.",
    ),
]

CHATGPT_PROMPTS = [
    (
        "frame_4_gpt.png",
        "Generate an image in Pixar 3D cinematic style, 16:9 widescreen. "
        "An orange tabby kitten named Cosmo wearing a white astronaut suit with a round "
        "glass helmet, sitting on the gray cratered moon surface. A glowing cyan mushroom "
        "gently hums beside him, bending as if saying goodbye. Earth glows in the background. "
        "Soft bittersweet lighting, tender mood.",
    ),
    (
        "frame_5_gpt.png",
        "Generate an image in Pixar 3D cinematic style, 16:9 widescreen. "
        "Same orange tabby kitten Cosmo in his astronaut suit on the moon. "
        "The glowing cyan mushroom is giving him a tiny bright star gift, floating between them. "
        "Earth in the black starry sky. Warm golden light on Cosmo's helmet, magical gift moment.",
    ),
    (
        "frame_6_gpt.png",
        "Generate an image in Pixar 3D cinematic style, 16:9 widescreen. "
        "Same orange tabby kitten Cosmo in his white astronaut suit, standing inside his tiny "
        "silver rocket and waving his paw at the glowing cyan mushroom on the moon surface "
        "below. Earth visible in the black starry sky. Warm farewell lighting, hopeful mood, "
        "Pixar quality 3D rendering.",
    ),
]


# -------- Gemini --------

def gemini_wait_for_login(page, timeout_s: int = 600) -> None:
    page.goto("https://gemini.google.com/app?hl=en", wait_until="domcontentloaded")
    start = time.time()
    while time.time() - start < timeout_s:
        time.sleep(3)
        if page.locator("button[aria-label^='Google Account:']").count():
            print("  Gemini login detected.", flush=True)
            return
        try:
            if "accounts.google.com" not in page.url and page.locator("textarea, [role='textbox']").count():
                print("  Gemini textbox detected (assumed logged in).", flush=True)
                return
        except Exception:
            pass
        remaining = int(timeout_s - (time.time() - start))
        print(f"  Waiting for Gemini login... {remaining}s left. Log in in the browser window.", flush=True)
    print("  Login wait timed out; proceeding anyway (generation will fail if not logged in).", flush=True)


def gemini_dismiss_popups(page) -> None:
    for label in ("Not now", "Got it", "Skip"):
        try:
            btn = page.get_by_role("button", name=label).first
            if btn.is_visible(timeout=1000):
                btn.click()
                time.sleep(0.5)
        except Exception:
            pass


def gemini_generate_one(page, prompt: str, out_path: Path) -> Path:
    page.goto("https://gemini.google.com/app?hl=en", wait_until="load")
    time.sleep(2)
    gemini_dismiss_popups(page)

    try:
        page.get_by_role("link", name="New chat").first.click(timeout=5000)
        time.sleep(1)
    except PlaywrightTimeoutError:
        pass

    box = page.get_by_role("textbox", name="Enter a prompt for Gemini")
    box.fill(prompt)
    time.sleep(0.5)
    page.get_by_role("button", name="Send message").click()

    # Wait for the "Show more options" button that appears on the generated image result.
    page.get_by_role("button", name="Show more options").wait_for(timeout=240000)
    time.sleep(2)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with page.expect_download(timeout=120000) as download_info:
        page.locator('[data-test-id="download-generated-image-button"]').last.click(force=True)
    download = download_info.value
    tmp = OUTPUT_DIR / f"_raw_{out_path.name}"
    download.save_as(str(tmp))

    # Re-save under the canonical name, preserving format.
    from PIL import Image
    img = Image.open(tmp)
    if img.mode != "RGB":
        img = img.convert("RGB")
    img.save(out_path, "PNG")
    tmp.unlink(missing_ok=True)
    return out_path


def generate_gemini_frames() -> list[Path]:
    results: list[Path] = []
    with sync_playwright() as pw:
        context = pw.chromium.launch_persistent_context(
            user_data_dir=str(GEMINI_PROFILE),
            channel="chrome",
            headless=False,
            accept_downloads=True,
            viewport={"width": 1440, "height": 1000},
        )
        try:
            page = context.pages[0] if context.pages else context.new_page()
            gemini_wait_for_login(page)
            for filename, prompt in GEMINI_PROMPTS:
                out_path = OUTPUT_DIR / filename
                print(f"  Gemini -> {filename}", flush=True)
                try:
                    saved = gemini_generate_one(page, prompt, out_path)
                    results.append(saved)
                    print(f"    SAVED {saved}", flush=True)
                except Exception as exc:
                    print(f"    FAIL {filename}: {exc}", flush=True)
        finally:
            context.close()
    return results


# -------- ChatGPT --------

def chatgpt_wait_for_login(page, timeout_s: int = 120) -> None:
    page.goto("https://chatgpt.com/", wait_until="domcontentloaded")
    start = time.time()
    while time.time() - start < timeout_s:
        time.sleep(3)
        if page.locator("div[contenteditable='true']").count() or page.locator("textarea#prompt-textarea").count():
            print("  ChatGPT composer detected.", flush=True)
            return
        remaining = int(timeout_s - (time.time() - start))
        print(f"  Waiting for ChatGPT login... {remaining}s left. Log in in the browser window.", flush=True)
    print("  Login wait timed out; proceeding anyway (generation will fail if not logged in).", flush=True)


def chatgpt_generate_one(page, prompt: str, out_path: Path) -> Path:
    page.goto("https://chatgpt.com/", wait_until="load")
    time.sleep(3)

    composer = page.locator("div[contenteditable='true']").first
    composer.click()
    composer.type(prompt, delay=5)
    time.sleep(0.5)
    # Submit via Enter (ChatGPT uses Enter to send by default).
    page.keyboard.press("Enter")

    # Wait until an image src appears in the response.
    img_locator = page.locator("img[src*='oaiusercontent'], img[src*='dalle'], img[src*='images']")
    img_locator.first.wait_for(timeout=240000)
    time.sleep(3)

    # Pull the first generated image src and download via JS fetch.
    src = img_locator.first.get_attribute("src")
    if not src:
        raise RuntimeError("Could not locate ChatGPT image src.")

    # Download the image bytes directly using Playwright request API (reuses cookies).
    response = page.request.get(src)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    raw = OUTPUT_DIR / f"_raw_{out_path.name}"
    raw.write_bytes(response.body())

    from PIL import Image
    img = Image.open(raw)
    if img.mode != "RGB":
        img = img.convert("RGB")
    img.save(out_path, "PNG")
    raw.unlink(missing_ok=True)
    return out_path


def generate_chatgpt_frames() -> list[Path]:
    results: list[Path] = []
    with sync_playwright() as pw:
        context = pw.chromium.launch_persistent_context(
            user_data_dir=str(CHATGPT_PROFILE),
            channel="chrome",
            headless=False,
            accept_downloads=True,
            viewport={"width": 1440, "height": 1000},
        )
        try:
            page = context.pages[0] if context.pages else context.new_page()
            chatgpt_wait_for_login(page)
            for filename, prompt in CHATGPT_PROMPTS:
                out_path = OUTPUT_DIR / filename
                print(f"  ChatGPT -> {filename}", flush=True)
                try:
                    saved = chatgpt_generate_one(page, prompt, out_path)
                    results.append(saved)
                    print(f"    SAVED {saved}", flush=True)
                except Exception as exc:
                    print(f"    FAIL {filename}: {exc}", flush=True)
        finally:
            context.close()
    return results


def write_fixture_readme(gemini_files: list[Path], gpt_files: list[Path]) -> None:
    lines = [
        "# Pixar fixture project",
        "",
        "Generated for Phase 1 watermark-cleaner integration tests.",
        "",
        "## Story",
        "",
        "Astronaut-cat Cosmo: (1) lands on moon, (2) finds glowing mushroom,",
        "(3) shares snack, (4) mushroom hums goodbye, (5) mushroom gives star, (6) cat waves and blasts off.",
        "",
        "## Frames",
        "",
        "| File | Source | Expected cleaner behavior |",
        "|---|---|---|",
    ]
    for p in gemini_files:
        lines.append(f"| `{p.name}` | Gemini web | `clean` (watermark should be removed) |")
    for p in gpt_files:
        lines.append(f"| `{p.name}` | ChatGPT web | `passthrough` (no watermark, image unchanged) |")
    lines += [
        "",
        "## Generated by",
        "",
        "`tools/generate_pixar_fixture.py` via Playwright persistent Chrome profiles:",
        "- `.gemini_chrome_profile/` (Gemini web)",
        "- `.chatgpt_chrome_profile/` (ChatGPT web)",
        "",
    ]
    (OUTPUT_DIR / "README.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Generate the 6-frame Pixar fixture.")
    parser.add_argument("--provider", choices=["gemini", "chatgpt", "both"], default="both")
    args = parser.parse_args()

    print(f"Generating Pixar fixture (provider={args.provider})...", flush=True)
    gemini_files: list[Path] = []
    gpt_files: list[Path] = []
    if args.provider in {"gemini", "both"}:
        gemini_files = generate_gemini_frames()
    if args.provider in {"chatgpt", "both"}:
        gpt_files = generate_chatgpt_frames()
    write_fixture_readme(gemini_files, gpt_files)
    print(f"\nDone. Gemini: {len(gemini_files)}/3, ChatGPT: {len(gpt_files)}/3", flush=True)
    if args.provider == "gemini":
        return 0 if gemini_files else 1
    if args.provider == "chatgpt":
        return 0 if gpt_files else 1
    return 0 if (gemini_files and gpt_files) else 1


if __name__ == "__main__":
    sys.exit(main())
