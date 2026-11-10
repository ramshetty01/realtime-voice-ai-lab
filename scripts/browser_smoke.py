"""Explicit browser check against an already running lab; may invoke its adapters."""

import argparse
import os
from pathlib import Path

from playwright.sync_api import sync_playwright


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:3000")
    parser.add_argument("--output", type=Path, default=Path("/tmp/voice-browser"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 1000})
        page.goto(args.url, wait_until="networkidle")
        page.get_by_role("heading", name="Voice Pipeline Lab").wait_for()
        page.get_by_text("API access", exact=True).click()
        page.get_by_label("Access token").fill(os.getenv("VOICE_SMOKE_TOKEN", ""))
        page.get_by_role("button", name="Connect", exact=True).click()
        page.get_by_role("button", name="Start voice recording").wait_for()
        page.wait_for_function("!document.querySelector('[aria-label=\"Start voice recording\"]').disabled")
        page.get_by_role("textbox", name="Message", exact=True).fill("Hello from the browser smoke check")
        page.get_by_role("button", name="Send", exact=True).click()
        page.get_by_role("button", name="Send", exact=True).wait_for(state="visible")
        page.locator(".status-badge.done, .status-badge.degraded").last.wait_for(timeout=60000)
        page.get_by_role("button", name="Toggle recent requests").click()
        page.get_by_role("button", name="Details", exact=True).first.click()
        with page.expect_download() as download:
            page.get_by_role("button", name="Export JSON").click()
        download.value.save_as(str(args.output / "trace.json"))
        page.screenshot(path=str(args.output / "desktop.png"), full_page=True)
        page.set_viewport_size({"width": 390, "height": 844})
        page.screenshot(path=str(args.output / "mobile.png"), full_page=True)
        browser.close()
    print("Authenticated socket, chat, trace inspection and protected download passed.")


if __name__ == "__main__":
    main()
