#!/usr/bin/env python3
"""
SKAI Beta Tester
Runs a real Chromium browser against a Streamlit app and generates screenshots + UX report.

Usage:
    python qa/beta_test_skai.py --url https://skiscettai.streamlit.app/
    python qa/beta_test_skai.py --url http://localhost:8501
"""

from __future__ import annotations

import argparse
import json
import math
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


PAGES = [
    "Home",
    "Crea SKiscetta",
    "SKAI Radar",
    "Ricette",
    "Lista spesa",
    "Meal plan",
    "Preferiti",
]


def parse_rgb(value: str):
    nums = [int(x) for x in re.findall(r"\d+", value or "")[:3]]
    if len(nums) != 3:
        return None
    return tuple(nums)


def luminance(rgb):
    def channel(c):
        c = c / 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = rgb
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def contrast_ratio(fg, bg):
    if fg is None or bg is None:
        return None
    l1 = luminance(fg)
    l2 = luminance(bg)
    high = max(l1, l2)
    low = min(l1, l2)
    return (high + 0.05) / (low + 0.05)


def safe_name(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "_", name.strip().lower()).strip("_")


def collect_visual_issues(page) -> List[Dict[str, Any]]:
    script = """
    () => {
      const selectors = [
        'button',
        'input',
        'textarea',
        '[role="button"]',
        '[role="combobox"]',
        '[data-baseweb="select"]',
        '[data-testid="stSelectbox"]',
        '[data-testid="stTextInput"]',
        '[data-testid="stTextArea"]',
        '[data-testid="stCheckbox"]',
        '[data-testid="stRadio"]',
        '[data-testid="stSlider"]',
        '[data-testid="stMetric"]',
        '[data-testid="stAlert"]',
        'label',
        'p',
        'span',
        'h1',
        'h2',
        'h3'
      ];

      const nodes = Array.from(document.querySelectorAll(selectors.join(',')));
      const out = [];
      for (const el of nodes.slice(0, 500)) {
        const rect = el.getBoundingClientRect();
        if (rect.width < 4 || rect.height < 4) continue;
        const style = window.getComputedStyle(el);
        const text = (el.innerText || el.value || el.getAttribute('aria-label') || el.getAttribute('placeholder') || '').trim();
        if (!text && !['INPUT', 'TEXTAREA'].includes(el.tagName)) continue;

        out.push({
          tag: el.tagName,
          role: el.getAttribute('role') || '',
          testid: el.getAttribute('data-testid') || '',
          baseweb: el.getAttribute('data-baseweb') || '',
          text: text.slice(0, 120),
          color: style.color,
          backgroundColor: style.backgroundColor,
          fontSize: style.fontSize,
          fontWeight: style.fontWeight,
          x: Math.round(rect.x),
          y: Math.round(rect.y),
          width: Math.round(rect.width),
          height: Math.round(rect.height)
        });
      }
      return out;
    }
    """
    raw = page.evaluate(script)
    issues = []

    for item in raw:
        fg = parse_rgb(item.get("color", ""))
        bg = parse_rgb(item.get("backgroundColor", ""))
        ratio = contrast_ratio(fg, bg)

        item["contrast_ratio"] = round(ratio, 2) if ratio is not None else None

        text = item.get("text", "")
        is_control = item.get("tag") in {"BUTTON", "INPUT", "TEXTAREA"} or item.get("role") in {"button", "combobox"}

        # Flag low contrast. For transparent backgrounds, CSS may report rgba(0,0,0,0);
        # those are noisy, so focus on actual white-on-white / dark-on-dark controls.
        color = item.get("color", "")
        bgc = item.get("backgroundColor", "")

        white_text = "255, 255, 255" in color
        white_bg = "255, 255, 255" in bgc
        dark_text = "0, 0, 0" in color or "16, 18, 37" in color
        dark_bg = "0, 0, 0" in bgc or "5, 5, 13" in bgc

        if is_control and white_text and white_bg:
            issues.append({**item, "issue": "white_text_on_white_control"})
        elif is_control and dark_text and dark_bg:
            issues.append({**item, "issue": "dark_text_on_dark_control"})
        elif ratio is not None and ratio < 3.0 and len(text) > 1:
            issues.append({**item, "issue": "low_contrast"})

    return issues


def click_sidebar_page(page, label: str) -> bool:
    # Robust Streamlit sidebar navigation.
    # Streamlit radio labels can be wrapped in several nested spans/divs.
    attempts = [
        lambda: page.get_by_text(label, exact=True).click(timeout=3000),
        lambda: page.locator(f'text={label}').first.click(timeout=3000),
        lambda: page.locator('[data-testid="stSidebar"]').get_by_text(label, exact=True).click(timeout=3000),
    ]

    for attempt in attempts:
        try:
            attempt()
            page.wait_for_timeout(1400)
            return True
        except Exception:
            pass

    try:
        clicked = page.evaluate(
            """
            (label) => {
              const sidebar = document.querySelector('[data-testid="stSidebar"]') || document.body;
              const nodes = Array.from(sidebar.querySelectorAll('*'));
              const target = nodes.find(el => (el.innerText || '').trim() === label);
              if (!target) return false;
              const clickable = target.closest('label, button, [role="radio"], [role="button"]') || target;
              clickable.scrollIntoView({block: 'center'});
              clickable.dispatchEvent(new MouseEvent('mousedown', {bubbles: true}));
              clickable.dispatchEvent(new MouseEvent('mouseup', {bubbles: true}));
              clickable.dispatchEvent(new MouseEvent('click', {bubbles: true}));
              return true;
            }
            """,
            label,
        )
        if clicked:
            page.wait_for_timeout(1400)
            return True
    except Exception:
        pass

    return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="https://skiscettai.streamlit.app/")
    parser.add_argument("--headful", action="store_true")
    parser.add_argument("--timeout", type=int, default=45000)
    args = parser.parse_args()

    root = Path(__file__).resolve().parent
    screenshots_dir = root / "screenshots"
    reports_dir = root / "reports"
    screenshots_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    report: Dict[str, Any] = {
        "url": args.url,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "public_access_ok": False,
        "auth_or_login_detected": False,
        "pages": [],
        "console_errors": [],
        "critical_issues": [],
        "recommendations": [],
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not args.headful)
        context = browser.new_context(
            viewport={"width": 1440, "height": 1000},
            device_scale_factor=1,
        )

        page = context.new_page()

        page.on("console", lambda msg: report["console_errors"].append({
            "type": msg.type,
            "text": msg.text,
        }) if msg.type in {"error", "warning"} else None)

        try:
            page.goto(args.url, wait_until="networkidle", timeout=args.timeout)
        except PlaywrightTimeoutError:
            report["critical_issues"].append("Initial page load timed out.")

        page.wait_for_timeout(2500)
        current_url = page.url
        body_text = page.locator("body").inner_text(timeout=10000) if page.locator("body").count() else ""

        if "share.streamlit.io/-/auth" in current_url or "Sign in" in body_text or "Log in" in body_text:
            report["auth_or_login_detected"] = True
            report["critical_issues"].append(
                f"App redirected to authentication/login: {current_url}"
            )
        else:
            report["public_access_ok"] = True

        page.screenshot(path=screenshots_dir / "00_initial.png", full_page=True)

        # Test each navigation item.
        for page_name in PAGES:
            opened = click_sidebar_page(page, page_name)
            page.wait_for_timeout(1400)

            screenshot_path = screenshots_dir / f"{safe_name(page_name)}.png"
            page.screenshot(path=screenshot_path, full_page=True)

            text = page.locator("body").inner_text(timeout=10000) if page.locator("body").count() else ""
            issues = collect_visual_issues(page)

            page_report = {
                "page": page_name,
                "opened": opened,
                "screenshot": str(screenshot_path.relative_to(root)),
                "url": page.url,
                "text_length": len(text),
                "visual_issues_count": len(issues),
                "visual_issues": issues[:30],
            }

            # Page-specific heuristics.
            if page_name == "SKAI Radar":
                lower = text.lower()
                if "usa demo siena" in lower:
                    page_report.setdefault("ux_issues", []).append("Contains 'Usa demo Siena' in main flow.")
                if "ricetta target" in lower:
                    page_report.setdefault("ux_issues", []).append("Contains 'Ricetta target' in main flow.")
                if "cosa vuoi fare" not in lower and "cosa vuoi ottenere" not in lower:
                    page_report.setdefault("ux_issues", []).append("Radar does not start from user intent.")
                if "mappa" not in lower:
                    page_report.setdefault("ux_issues", []).append("Radar page does not show map text.")

            report["pages"].append(page_report)

        browser.close()

    # Aggregate recommendations.
    total_visual_issues = sum(p["visual_issues_count"] for p in report["pages"])
    if total_visual_issues:
        report["recommendations"].append(
            f"Fix contrast/readability issues detected across controls: {total_visual_issues} possible issues."
        )

    if report["auth_or_login_detected"]:
        report["recommendations"].append(
            "Check Streamlit sharing settings or run this test locally from a normal browser session."
        )

    radar = next((p for p in report["pages"] if p["page"] == "SKAI Radar"), None)
    if radar and radar.get("ux_issues"):
        report["recommendations"].append(
            "Simplify SKAI Radar: hide demo controls, remove recipe-target-first workflow, start from user intent."
        )

    json_path = reports_dir / "skai_beta_report.json"
    md_path = reports_dir / "skai_beta_report.md"

    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = []
    lines.append("# SKAI Beta Test Report")
    lines.append("")
    lines.append(f"- URL: `{report['url']}`")
    lines.append(f"- Generated: `{report['generated_at']}`")
    lines.append(f"- Public access OK: `{report['public_access_ok']}`")
    lines.append(f"- Auth/login detected: `{report['auth_or_login_detected']}`")
    lines.append("")

    if report["critical_issues"]:
        lines.append("## Critical issues")
        for issue in report["critical_issues"]:
            lines.append(f"- {issue}")
        lines.append("")

    lines.append("## Pages")
    for page_report in report["pages"]:
        lines.append(f"### {page_report['page']}")
        lines.append(f"- Opened: `{page_report['opened']}`")
        lines.append(f"- Screenshot: `{page_report['screenshot']}`")
        lines.append(f"- Visual issues: `{page_report['visual_issues_count']}`")

        if page_report.get("ux_issues"):
            lines.append("- UX issues:")
            for issue in page_report["ux_issues"]:
                lines.append(f"  - {issue}")

        if page_report["visual_issues"]:
            lines.append("- First visual issues:")
            for issue in page_report["visual_issues"][:8]:
                lines.append(
                    f"  - `{issue['issue']}` · {issue['tag']} · {issue.get('testid') or issue.get('role') or ''} · "
                    f"text=`{issue.get('text','')[:80]}` · color={issue.get('color')} · bg={issue.get('backgroundColor')} · contrast={issue.get('contrast_ratio')}"
                )
        lines.append("")

    if report["recommendations"]:
        lines.append("## Recommendations")
        for rec in report["recommendations"]:
            lines.append(f"- {rec}")
        lines.append("")

    md_path.write_text("\n".join(lines), encoding="utf-8")

    print(f"Report written to: {md_path}")
    print(f"JSON written to: {json_path}")
    print(f"Screenshots written to: {screenshots_dir}")


if __name__ == "__main__":
    main()
