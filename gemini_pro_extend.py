#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import sys
import time
from pathlib import Path

from PIL import Image

try:
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    from playwright.sync_api import sync_playwright
except ModuleNotFoundError as exc:
    raise SystemExit(
        "Missing dependency: playwright\n"
        "Install with:\n"
        "  C:\\Users\\nishtiak\\AppData\\Local\\Programs\\Python\\Python312\\python.exe -m pip install playwright\n"
    ) from exc


ROOT_DIR = Path(__file__).resolve().parent
DEFAULT_SOURCE_DIR = ROOT_DIR / "Olia_continue"
DEFAULT_OUTPUT_DIR = DEFAULT_SOURCE_DIR / "extend"
DEFAULT_PROFILE_DIR = ROOT_DIR / ".gemini_chrome_profile"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extend images in Gemini Web, then redo them with Pro.")
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--user-data-dir", type=Path, default=DEFAULT_PROFILE_DIR)
    parser.add_argument("--limit", type=int, default=0, help="Process at most this many images. 0 means all.")
    parser.add_argument("--force", action="store_true", help="Overwrite files that already exist in the output folder.")
    return parser.parse_args()


def load_extension_prompt() -> str:
    script_path = ROOT_DIR / "outpaint_16_9.py"
    module = ast.parse(script_path.read_text(encoding="utf-8"))
    for node in module.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "PROMPT":
                return ast.literal_eval(node.value)
    raise RuntimeError("Could not find PROMPT in outpaint_16_9.py")


def discover_images(source_dir: Path, output_dir: Path, force: bool) -> list[Path]:
    images = []
    for path in sorted(source_dir.iterdir(), key=lambda item: item.name.lower()):
        if not path.is_file() or path.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        if output_dir in path.parents:
            continue
        if not force and (output_dir / path.name).exists():
            continue
        images.append(path)
    return images


def save_download_as_source_type(download_path: Path, destination_path: Path) -> None:
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.open(download_path)
    suffix = destination_path.suffix.lower()
    if suffix == ".png":
        if image.mode not in {"RGB", "RGBA"}:
            image = image.convert("RGBA" if "A" in image.getbands() else "RGB")
        image.save(destination_path, format="PNG")
        return

    if image.mode != "RGB":
        image = image.convert("RGB")
    image.save(destination_path, format="JPEG", quality=95)


def wait_for_login(page) -> None:
    page.goto("https://gemini.google.com/app?hl=en", wait_until="load")
    time.sleep(2)
    if page.locator("button[aria-label^='Google Account:']").count():
        return

    print("Gemini login is required in the opened Chrome window.", flush=True)
    print("Log in, wait until Gemini opens, then press Enter here to continue.", flush=True)
    input()
    page.goto("https://gemini.google.com/app?hl=en", wait_until="load")
    time.sleep(2)
    if not page.locator("button[aria-label^='Google Account:']").count():
        raise RuntimeError("Gemini login was not detected.")


def click_new_chat(page) -> None:
    page.goto("https://gemini.google.com/app?hl=en", wait_until="load")
    page.get_by_role("link", name="New chat").first.click()
    time.sleep(1)


def upload_image(page, image_path: Path) -> None:
    with page.expect_file_chooser() as chooser_info:
        page.get_by_role("button", name="Open upload file menu").click()
        page.get_by_role("menuitem", name="Upload files. Documents, data, code files").click()
    chooser_info.value.set_files(str(image_path))
    page.get_by_role("button", name=f"Remove file {image_path.name}").wait_for(timeout=30000)


def send_prompt(page, prompt: str) -> None:
    page.get_by_role("textbox", name="Enter a prompt for Gemini").fill(prompt)
    page.get_by_role("button", name="Send message").click()


def wait_for_base_image(page) -> None:
    page.get_by_role("button", name="Show more options").wait_for(timeout=240000)


def redo_with_pro(page) -> None:
    page.get_by_role("button", name="Show more options").last.click()
    page.get_by_role("menuitem", name="🍌 Redo with Pro").click()
    page.get_by_text("2 / 2").wait_for(timeout=240000)


def download_current_image(page, download_dir: Path) -> Path:
    download_dir.mkdir(parents=True, exist_ok=True)
    with page.expect_download(timeout=120000) as download_info:
        page.locator('[data-test-id="download-generated-image-button"]').last.click(force=True)
    download = download_info.value
    destination = download_dir / download.suggested_filename
    download.save_as(str(destination))
    return destination


def process_image(page, image_path: Path, output_dir: Path, prompt: str) -> Path:
    click_new_chat(page)
    upload_image(page, image_path)
    send_prompt(page, prompt)
    wait_for_base_image(page)
    redo_with_pro(page)
    downloaded = download_current_image(page, output_dir / "_downloads")
    destination = output_dir / image_path.name
    save_download_as_source_type(downloaded, destination)
    return destination


def main() -> int:
    args = parse_args()
    source_dir = args.source_dir.resolve()
    output_dir = args.output_dir.resolve()
    user_data_dir = args.user_data_dir.resolve()

    if not source_dir.exists():
        raise SystemExit(f"Source folder does not exist: {source_dir}")

    prompt = load_extension_prompt()
    images = discover_images(source_dir, output_dir, args.force)
    if args.limit > 0:
        images = images[: args.limit]

    if not images:
        print("No images to process.", flush=True)
        return 0

    print(f"Source: {source_dir}", flush=True)
    print(f"Output: {output_dir}", flush=True)
    print(f"Images to process: {len(images)}", flush=True)

    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=str(user_data_dir),
            channel="chrome",
            headless=False,
            accept_downloads=True,
            viewport={"width": 1440, "height": 1100},
        )
        try:
            page = context.pages[0] if context.pages else context.new_page()
            wait_for_login(page)

            for index, image_path in enumerate(images, start=1):
                print(f"[{index}/{len(images)}] {image_path.name}", flush=True)
                try:
                    result_path = process_image(page, image_path, output_dir, prompt)
                except PlaywrightTimeoutError as exc:
                    print(f"  TIMEOUT: {exc}", flush=True)
                    continue
                except Exception as exc:  # noqa: BLE001
                    print(f"  ERROR: {exc}", flush=True)
                    continue
                print(f"  SAVED: {result_path}", flush=True)
        finally:
            context.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
