#!/usr/bin/env python3
"""Download every image from a Gemini share page (public URL, no auth).

Usage:
  python fetch_gemini_share.py <share_url> <out_name_base>

Saves images as <out_name_base>_0.png, _1.png, ... into tests/fixtures/fake_project/.
Picks the LAST image (newest in the conversation) when combined with --only-last.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import requests


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "tests" / "fixtures" / "fake_project"
CDN_PATTERN = re.compile(r'https://lh3\.googleusercontent\.com/gg/[A-Za-z0-9_\-=/?]+')


def fetch_share_images(share_url: str) -> list[str]:
    resp = requests.get(share_url, timeout=30)
    resp.raise_for_status()
    seen: set[str] = set()
    ordered: list[str] = []
    for m in CDN_PATTERN.findall(resp.text):
        if m not in seen:
            seen.add(m)
            ordered.append(m)
    return ordered


def upscale_url(url: str, target_px: int = 2048) -> str:
    # Replace trailing size suffix (=s1024-rj, =s512-rw, etc.) with larger
    return re.sub(r"=s\d+-[a-z]+$", f"=s{target_px}-rw", url)


def download(url: str, dest: Path) -> int:
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(r.content)
    return len(r.content)


def main() -> int:
    args = sys.argv[1:]
    if len(args) < 2:
        print("Usage: fetch_gemini_share.py <share_url> <out_name_base> [--only-last]")
        return 1
    share_url, base = args[0], args[1]
    only_last = "--only-last" in args
    urls = fetch_share_images(share_url)
    if not urls:
        print(f"No images found on {share_url}")
        return 2
    targets = urls[-1:] if only_last else urls
    for i, u in enumerate(targets):
        # If only one, use exact base name; else append index
        name = f"{base}.png" if len(targets) == 1 else f"{base}_{i}.png"
        u_big = upscale_url(u)
        dest = OUT_DIR / name
        size = download(u_big, dest)
        print(f"SAVED {dest} ({size} bytes) from {u_big[:80]}...")
    return 0


if __name__ == "__main__":
    sys.exit(main())
