#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import traceback
from datetime import datetime, UTC
from pathlib import Path
from urllib.parse import urlencode, urlparse, urlunparse, parse_qs

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


PAGES = [
    ("Home", "home", ["schiscetta giusta", "SKiscettAI", "Inizia dal Copilot"]),
    ("Crea SKiscetta", "crea", ["Crea", "SKiscetta"]),
    ("SKAI Radar", "radar", ["Radar negozi", "catene nel raggio", "Scegli cosa vuoi risolvere", "Volantini visuali"]),
    ("Ricette", "ricette", ["Ricette", "Catalogo"]),
    ("Lista spesa", "lista", ["Lista", "spesa"]),
    ("Meal plan", "meal", ["Piano", "pranzi"]),
    ("Preferiti", "preferiti", ["Preferiti"]),
]

NAV_LABELS = {
    "Home",
    "Crea SKiscetta",
    "SKAI Radar",
    "Ricette",
    "Lista spesa",
    "Meal plan",
    "Preferiti",
}

ERROR_MARKERS = [
    "NameError",
    "Traceback",
    "ModuleNotFoundError",
    "AttributeError",
    "TypeError",
    "SyntaxError",
    "This app has encountered an error",
]

BANNED_COPY = [
    "App Store grade",
    "pantry intelligence",
    "weekly autopilot",
    "trust filter",
    "mission-first",
    "map-first",
    "verified offers",
    "no fake prices",
]


def page_url(base_url: str, slug: str, qa_fast: bool = True, extra: dict | None = None) -> str:
    parsed = urlparse(base_url)
    query = parse_qs(parsed.query)
    query["qa_page"] = [slug]
    if qa_fast:
        query["qa_fast"] = ["1"]
    if extra:
        for key, value in extra.items():
            query[key] = [str(value)]
    return urlunparse(parsed._replace(query=urlencode(query, doseq=True)))


def write_reports(report: dict, reports: Path) -> None:
    reports.mkdir(exist_ok=True)
    (reports / "skai_beta_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = ["# SKAI Beta Test Report", ""]
    if report.get("fatal_error"):
        lines.extend(["## Fatal error", "", "```text", str(report["fatal_error"]), "```", ""])

    lines.append("## Page checks")
    for check in report.get("checks", []):
        status = "✅" if check.get("passed") else "❌"
        lines.append(f"- {status} {check.get('name')}")

    lines.append("")
    lines.append("## Button smoke tests")
    for check in report.get("button_checks", []):
        status = "✅" if check.get("passed") else "❌"
        label = str(check.get("label", ""))[:100].replace("\n", " ")
        lines.append(f"- {status} {check.get('page')} · {label}")

    if report.get("skipped_buttons"):
        lines.append("")
        lines.append("## Skipped buttons")
        for check in report["skipped_buttons"]:
            label = str(check.get("label", ""))[:100].replace("\n", " ")
            lines.append(f"- ⏭️ {check.get('page')} · {label} · {check.get('reason', '')}")

    if report.get("failed_buttons"):
        lines.append("")
        lines.append("## Failed buttons")
        for check in report["failed_buttons"]:
            label = str(check.get("label", ""))[:100].replace("\n", " ")
            lines.append(f"- ❌ {check.get('page')} · {label} · {check.get('error', '')[:220]}")

    (reports / "skai_beta_report.md").write_text("\n".join(lines), encoding="utf-8")


def wait_app(page, markers=None, timeout_loops: int = 45):
    page.wait_for_selector('[data-testid="stAppViewContainer"], .stApp', timeout=45000)
    markers = markers or []
    for _ in range(timeout_loops):
        text = page.inner_text("body")
        if not markers or any(marker.lower() in text.lower() for marker in markers):
            return text
        page.wait_for_timeout(1000)
    return page.inner_text("body")


def has_error(text: str) -> bool:
    low = text.lower()
    return any(marker.lower() in low for marker in ERROR_MARKERS)


def check_no_literal_html(text: str) -> bool:
    low = text.lower()
    bad = ['<div class="skai-', "</div>", "<span>", "</span>", "<strong>", "</strong>"]
    return not any(marker in low for marker in bad)


def banned_copy_found(text: str) -> list[str]:
    low = text.lower()
    return [item for item in BANNED_COPY if item.lower() in low]


def normalize_label(label: str) -> str:
    return re.sub(r"^[^\wÀ-ÿ]+", "", label).strip()


def is_navigation_button(label: str) -> bool:
    cleaned = normalize_label(label)
    return cleaned in NAV_LABELS or "keyboard_double_arrow" in label


def visible_main_buttons(page, limit: int):
    """Return visible enabled buttons that belong to the main content area.
    Sidebar navigation is tested separately, so it is intentionally excluded here.
    """
    buttons = page.locator("button")
    count = buttons.count()
    result = []
    skipped = []

    for index in range(count):
        try:
            button = buttons.nth(index)
            if not (button.is_visible() and button.is_enabled()):
                continue

            label = button.inner_text(timeout=1200).strip()
            if not label:
                continue

            if is_navigation_button(label):
                skipped.append((index, label, "sidebar/navigation tested separately"))
                continue

            box = button.bounding_box()
            if box and box.get("x", 0) < 260:
                skipped.append((index, label, "sidebar area"))
                continue

            result.append((index, label))
        except Exception:
            continue

        if len(result) >= limit:
            break

    return result, skipped


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8501")
    parser.add_argument("--button-limit-per-page", type=int, default=18)
    args = parser.parse_args()

    root = Path(__file__).resolve().parent
    reports = root / "reports"
    shots = root / "screenshots"
    shots.mkdir(exist_ok=True)

    report = {
        "url": args.url,
        "generated_at": datetime.now(UTC).isoformat(),
        "checks": [],
        "button_checks": [],
        "skipped_buttons": [],
        "errors": [],
        "fatal_error": "",
    }

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1440, "height": 1000})
            page = context.new_page()

            # Default page.
            page.goto(args.url, wait_until="domcontentloaded", timeout=60000)
            default_text = wait_app(page, ["schiscetta giusta", "SKiscettAI", "Inizia dal Copilot"])
            page.screenshot(path=shots / "00_default_home.png", full_page=True)
            report["checks"].append({
                "name": "default_opens_home",
                "passed": any(marker.lower() in default_text.lower() for marker in ["schiscetta giusta", "SKiscettAI", "Inizia dal Copilot"]) and not has_error(default_text),
            })

            # Radar parser-selection smoke test: qa_boot runs parser selection but skips slow external fetch.
            try:
                page.goto(page_url(args.url, "radar", qa_fast=False, extra={"qa_boot": "1"}), wait_until="domcontentloaded", timeout=60000)
                radar_boot_text = wait_app(page, ["Radar negozi", "catene nel raggio", "Scegli cosa vuoi risolvere"], timeout_loops=35)
                page.screenshot(path=shots / "radar_boot_parser_selection.png", full_page=True)
                report["checks"].append({
                    "name": "radar_boot_parser_selection",
                    "passed": ("radar negozi" in radar_boot_text.lower() or "catene nel raggio" in radar_boot_text.lower()) and not has_error(radar_boot_text),
                    "text_length": len(radar_boot_text),
                })
            except Exception as error:
                report["checks"].append({
                    "name": "radar_boot_parser_selection",
                    "passed": False,
                    "error": str(error),
                })
                try:
                    page.screenshot(path=shots / "radar_boot_parser_selection_fail.png", full_page=True)
                except Exception:
                    pass

            # Sidebar one-click navigation is the dedicated navigation test.
            for page_name, slug, expected_markers in PAGES:
                try:
                    page.goto(page_url(args.url, "home", qa_fast=True, extra={"navcheck": slug}), wait_until="domcontentloaded", timeout=60000)
                    wait_app(page, ["schiscetta giusta", "SKiscettAI"])

                    if page_name == "Home":
                        report["checks"].append({
                            "name": f"sidebar_one_click_{slug}",
                            "page": page_name,
                            "passed": True,
                        })
                        continue

                    nav_button = page.locator("button").filter(has_text=page_name).first
                    nav_button.click(timeout=9000, force=True)
                    nav_text = wait_app(page, expected_markers, timeout_loops=20)
                    nav_passed = any(marker.lower() in nav_text.lower() for marker in expected_markers) and not has_error(nav_text)

                    report["checks"].append({
                        "name": f"sidebar_one_click_{slug}",
                        "page": page_name,
                        "passed": nav_passed,
                        "text_length": len(nav_text),
                    })
                except Exception as error:
                    report["checks"].append({
                        "name": f"sidebar_one_click_{slug}",
                        "page": page_name,
                        "passed": False,
                        "error": str(error),
                    })
                    try:
                        page.screenshot(path=shots / f"sidebar_fail_{slug}.png", full_page=True)
                    except Exception:
                        pass

            # Page open and main-content button smoke tests.
            for page_name, slug, expected_markers in PAGES:
                try:
                    page.goto(page_url(args.url, slug, qa_fast=True), wait_until="domcontentloaded", timeout=60000)
                    text = wait_app(page, expected_markers)
                    page.screenshot(path=shots / f"{slug}.png", full_page=True)

                    markers_ok = any(marker.lower() in text.lower() for marker in expected_markers)
                    literal_ok = check_no_literal_html(text)
                    page_ok = markers_ok and literal_ok and not has_error(text)

                    report["checks"].append({
                        "name": f"open_{slug}",
                        "page": page_name,
                        "passed": page_ok,
                        "text_length": len(text),
                        "literal_html_ok": literal_ok,
                    })

                    found_banned = banned_copy_found(text)
                    report["checks"].append({
                        "name": f"copy_jargon_check_{slug}",
                        "page": page_name,
                        "passed": not found_banned,
                        "found": found_banned,
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
                            "literal_html_visible": not literal_ok,
                        }

                        report["checks"].append({
                            "name": "radar_offer_quality",
                            "passed": radar_checks["chain_panel"] and radar_checks["bad_price_only_cards"] == 0 and not radar_checks["literal_html_visible"],
                            "details": radar_checks,
                        })

                    buttons, skipped = visible_main_buttons(page, args.button_limit_per_page)
                    for button_index, label, reason in skipped:
                        report["skipped_buttons"].append({
                            "page": page_name,
                            "slug": slug,
                            "button_index": button_index,
                            "label": label[:120],
                            "reason": reason,
                        })

                    for button_index, label in buttons:
                        check = {
                            "page": page_name,
                            "slug": slug,
                            "button_index": button_index,
                            "label": label[:120],
                            "clicked": False,
                            "passed": False,
                            "error": "",
                        }
                        try:
                            page.goto(page_url(args.url, slug, qa_fast=True, extra={"button": button_index}), wait_until="domcontentloaded", timeout=60000)
                            wait_app(page, expected_markers)
                            target = page.locator("button").nth(button_index)
                            target.scroll_into_view_if_needed(timeout=4000)
                            target.click(timeout=9000)
                            page.wait_for_timeout(1000)
                            after_text = page.inner_text("body")
                            check["clicked"] = True
                            check["passed"] = not has_error(after_text) and check_no_literal_html(after_text)
                            check["after_text_length"] = len(after_text)
                        except PlaywrightTimeoutError as error:
                            check["error"] = f"timeout: {error}"
                        except Exception as error:
                            check["error"] = str(error)

                        report["button_checks"].append(check)

                        if not check["passed"]:
                            try:
                                page.screenshot(path=shots / f"button_fail_{slug}_{button_index}.png", full_page=True)
                            except Exception:
                                pass
                except Exception as error:
                    report["checks"].append({
                        "name": f"open_{slug}",
                        "page": page_name,
                        "passed": False,
                        "error": str(error),
                    })
                    try:
                        page.screenshot(path=shots / f"page_fail_{slug}.png", full_page=True)
                    except Exception:
                        pass

            browser.close()
    except Exception:
        report["fatal_error"] = traceback.format_exc()

    failed = [check for check in report["checks"] if not check.get("passed")]
    failed_buttons = [check for check in report["button_checks"] if not check.get("passed")]
    report["failed"] = failed
    report["failed_buttons"] = failed_buttons

    write_reports(report, reports)

    if report.get("fatal_error") or failed or failed_buttons:
        raise SystemExit(f"Beta test failed: checks={len(failed)} buttons={len(failed_buttons)} fatal={bool(report.get('fatal_error'))}")


if __name__ == "__main__":
    main()
