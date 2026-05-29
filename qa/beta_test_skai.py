#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, UTC
from pathlib import Path
from urllib.parse import urlencode, urlparse, urlunparse, parse_qs

from playwright.sync_api import sync_playwright


PAGES = [
    ("Home", "home", ["Pranzo smart", "SKiscettAI", "Kitchen OS"]),
    ("SKAI Radar", "radar", ["Radar negozi", "catene nel raggio", "Mission Control"]),
    ("Ricette", "ricette", ["Ricette"]),
    ("Lista spesa", "lista", ["Lista", "spesa"]),
    ("Meal plan", "meal", ["Meal", "plan"]),
    ("Preferiti", "preferiti", ["Preferiti"]),
]


def page_url(base_url: str, slug: str, qa_fast: bool = True) -> str:
    parsed = urlparse(base_url)
    query = parse_qs(parsed.query)
    query["qa_page"] = [slug]
    if qa_fast:
        query["qa_fast"] = ["1"]
    return urlunparse(parsed._replace(query=urlencode(query, doseq=True)))


def wait_app(page, markers=None):
    page.wait_for_selector('[data-testid="stAppViewContainer"], .stApp', timeout=45000)
    markers = markers or []

    for _ in range(40):
        text = page.inner_text("body")
        if not markers or any(marker.lower() in text.lower() for marker in markers):
            return text
        page.wait_for_timeout(1000)

    return page.inner_text("body")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8501")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent
    reports = root / "reports"
    shots = root / "screenshots"
    reports.mkdir(exist_ok=True)
    shots.mkdir(exist_ok=True)

    report = {
        "url": args.url,
        "generated_at": datetime.now(UTC).isoformat(),
        "checks": [],
        "errors": [],
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 1000})
        page = context.new_page()

        page.goto(args.url, wait_until="domcontentloaded", timeout=60000)
        default_text = wait_app(page, ["Pranzo smart", "Kitchen OS", "SKiscettAI"])
        page.screenshot(path=shots / "00_default_home.png", full_page=True)

        report["checks"].append({
            "name": "default_opens_home",
            "passed": any(marker.lower() in default_text.lower() for marker in ["Pranzo smart", "Kitchen OS", "SKiscettAI"]),
        })

        for page_name, slug, expected_markers in PAGES:
            page.goto(page_url(args.url, slug, qa_fast=True), wait_until="domcontentloaded", timeout=60000)
            text = wait_app(page, expected_markers)
            page.screenshot(path=shots / f"{slug}.png", full_page=True)

            passed = any(marker.lower() in text.lower() for marker in expected_markers)
            report["checks"].append({
                "name": f"open_{slug}",
                "page": page_name,
                "passed": passed,
                "text_length": len(text),
            })

            if slug == "radar":
                cards = page.locator(".skai-offer-card")
                card_count = cards.count()
                bad_cards = 0

                for i in range(card_count):
                    card_text = cards.nth(i).inner_text()
                    has_price = bool(re.search(r"\d+[,.]\d{2}\s*€", card_text))
                    words = re.findall(r"[A-Za-zÀ-ÿ]{3,}", card_text)
                    if has_price and len(words) < 4:
                        bad_cards += 1

                radar_checks = {
                    "chain_panel": "catene nel raggio" in text.lower(),
                    "map_text": "radar negozi" in text.lower() or "mappa" in text.lower(),
                    "bad_price_only_cards": bad_cards,
                }

                report["checks"].append({
                    "name": "radar_offer_quality",
                    "passed": radar_checks["chain_panel"] and radar_checks["bad_price_only_cards"] == 0,
                    "details": radar_checks,
                })

        browser.close()

    failed = [check for check in report["checks"] if not check.get("passed")]
    report["failed"] = failed

    (reports / "skai_beta_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = ["# SKAI Beta Test Report", ""]
    for check in report["checks"]:
        status = "✅" if check.get("passed") else "❌"
        lines.append(f"- {status} {check['name']}")

    (reports / "skai_beta_report.md").write_text("\n".join(lines), encoding="utf-8")

    if failed:
        raise SystemExit(f"Beta test failed: {failed}")


if __name__ == "__main__":
    main()
