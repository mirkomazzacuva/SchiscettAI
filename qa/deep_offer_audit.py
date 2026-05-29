#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from datetime import datetime, UTC
from pathlib import Path
from urllib.request import Request, urlopen

from playwright.sync_api import sync_playwright


FALLBACKS = {
    "PENNY": [
        "https://www.penny.it/offerte",
        "https://www.promoqui.it/volantino/penny-market",
        "https://zonavolantini.com/penny",
    ],
    "Coop": [
        "https://www.coopfirenze.it/negozi-e-promo/offerte-e-volantini/offerte-per-i-soci",
        "https://www.coopfirenze.it/negozi-e-promo/offerte-e-volantini",
        "https://www.volantinofacile.it/coop/volantino-coop/firenze",
    ],
    "Conad": [
        "https://www.doveconviene.it/volantino/conad-superstore",
        "https://www.volantinofacile.it/conad-superstore/volantino-conad-superstore",
        "https://www.conad.it/app-internal/home_leaflets",
    ],
    "PAM": [
        "https://www.doveconviene.it/volantino/panorama",
        "https://www.volantinofacile.it/pam/volantino-pam",
        "https://www.pampanorama.it/",
    ],
    "Carrefour": [
        "https://www.carrefour.it/promozioni/",
        "https://www.promoqui.it/volantino/carrefour",
        "https://www.doveconviene.it/volantino/carrefour",
    ],
    "Lidl": [
        "https://www.lidl.it/c/offerte/c10026788",
        "https://www.doveconviene.it/volantino/lidl",
        "https://www.promoqui.it/volantino/lidl",
    ],
    "Eurospin": [
        "https://www.eurospin.it/volantino/",
        "https://www.doveconviene.it/volantino/eurospin",
        "https://www.promoqui.it/volantino/eurospin",
    ],
    "Esselunga": [
        "https://www.esselunga.it/it-it/negozi/volantino.html",
        "https://www.doveconviene.it/volantino/esselunga",
        "https://www.promoqui.it/volantino/esselunga",
    ],
    "MD": [
        "https://www.mdspa.it/volantino/",
        "https://www.doveconviene.it/volantino/md",
        "https://www.promoqui.it/volantino/md",
    ],
}


PRICE_RE = re.compile(r"\d{1,3}[,.]\d{2}\s*€")
PAIR_RE = re.compile(r"([A-Za-zÀ-ÿ0-9][A-Za-zÀ-ÿ0-9 '.,%/+&-]{8,120}?)\s+(\d{1,3}[,.]\d{2})\s*€", re.I)


def clean_text(value: str) -> str:
    value = re.sub(r"<script.*?</script>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<style.*?</style>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def extract_pairs(text: str, limit: int = 15):
    pairs = []
    seen = set()
    for match in PAIR_RE.finditer(text):
        name = re.sub(r"\s+", " ", match.group(1)).strip(" -–—|•·:,;")
        price = match.group(2).replace(",", ".")
        if len(name) < 6:
            continue
        low = name.lower()
        if any(bad in low for bad in ["privacy", "cookie", "volantino", "newsletter", "negozi vicino", "sfoglia", "catalogo"]):
            continue
        if len(name.split()) > 14:
            name = " ".join(name.split()[-10:])
        key = (name.lower(), price)
        if key in seen:
            continue
        seen.add(key)
        pairs.append({"product": name[:120], "price": price})
        if len(pairs) >= limit:
            break
    return pairs


def static_fetch(url: str):
    try:
        request = Request(url, headers={
            "User-Agent": "Mozilla/5.0 SKAI-DeepOfferAudit/1.0",
            "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
        })
        with urlopen(request, timeout=18) as response:
            html = response.read(950000).decode("utf-8", errors="ignore")
            text = clean_text(html)
            return {
                "ok": True,
                "status": response.status,
                "text_length": len(text),
                "price_count": len(PRICE_RE.findall(text)),
                "pairs": extract_pairs(text),
                "error": "",
            }
    except Exception as error:
        return {
            "ok": False,
            "status": None,
            "text_length": 0,
            "price_count": 0,
            "pairs": [],
            "error": str(error)[:300],
        }


def looks_like_api(url: str) -> bool:
    low = url.lower()
    useful = ["api", "graphql", "json", "offer", "promo", "leaflet", "volantino", "catalog", "product", "search"]
    noisy = ["google", "facebook", "doubleclick", "analytics", "googletag", "clarity", "hotjar", "cookie"]
    return any(token in low for token in useful) and not any(token in low for token in noisy)


def rendered_fetch(page, url: str, screenshot_path: Path):
    api_urls = []
    response_summaries = []

    def on_response(response):
        try:
            response_url = response.url
            if looks_like_api(response_url):
                api_urls.append(response_url)
                ct = response.headers.get("content-type", "")
                response_summaries.append({
                    "url": response_url,
                    "status": response.status,
                    "content_type": ct[:120],
                })
        except Exception:
            pass

    page.on("response", on_response)

    try:
        page.goto(url, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(5000)

        # Try to close common cookie overlays without failing.
        for label in ["Accetta", "Accetto", "Accept", "OK", "Ho capito", "Continua"]:
            try:
                button = page.get_by_role("button", name=re.compile(label, re.I)).first
                if button.count() > 0 and button.is_visible():
                    button.click(timeout=2000)
                    page.wait_for_timeout(800)
                    break
            except Exception:
                pass

        text = page.inner_text("body", timeout=10000)
        html = page.content()
        text = re.sub(r"\s+", " ", text).strip()

        try:
            page.screenshot(path=screenshot_path, full_page=True, timeout=20000)
        except Exception:
            pass

        return {
            "ok": True,
            "text_length": len(text),
            "html_length": len(html),
            "price_count": len(PRICE_RE.findall(text)),
            "pairs": extract_pairs(text),
            "api_urls": sorted(set(api_urls))[:40],
            "responses": response_summaries[:40],
            "error": "",
        }

    except Exception as error:
        return {
            "ok": False,
            "text_length": 0,
            "html_length": 0,
            "price_count": 0,
            "pairs": [],
            "api_urls": sorted(set(api_urls))[:40],
            "responses": response_summaries[:40],
            "error": str(error)[:500],
        }
    finally:
        try:
            page.remove_listener("response", on_response)
        except Exception:
            pass


def main():
    root = Path(__file__).resolve().parents[1]
    reports = root / "qa" / "reports"
    shots = root / "qa" / "screenshots" / "deep_offer_audit"
    reports.mkdir(parents=True, exist_ok=True)
    shots.mkdir(parents=True, exist_ok=True)

    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "note": "Deep browser audit: static+rendered pages, pair candidates and possible API URLs. Non-blocking.",
        "chains": [],
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 1100})

        for chain, urls in FALLBACKS.items():
            chain_result = {
                "chain": chain,
                "best_static_pairs": 0,
                "best_rendered_pairs": 0,
                "best_url": "",
                "sources": [],
            }

            for idx, url in enumerate(urls):
                page = context.new_page()
                static = static_fetch(url)
                rendered = rendered_fetch(page, url, shots / f"{chain.lower()}_{idx}.png")
                page.close()

                item = {
                    "url": url,
                    "static": static,
                    "rendered": rendered,
                }
                chain_result["sources"].append(item)

                best_for_url = max(len(static.get("pairs", [])), len(rendered.get("pairs", [])))
                if best_for_url > max(chain_result["best_static_pairs"], chain_result["best_rendered_pairs"]):
                    chain_result["best_static_pairs"] = max(chain_result["best_static_pairs"], len(static.get("pairs", [])))
                    chain_result["best_rendered_pairs"] = max(chain_result["best_rendered_pairs"], len(rendered.get("pairs", [])))
                    chain_result["best_url"] = url

            report["chains"].append(chain_result)

        browser.close()

    (reports / "skai_deep_offer_audit.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    md = ["# SKAI Deep Offer Audit", ""]
    for chain in report["chains"]:
        ok = "✅" if max(chain["best_static_pairs"], chain["best_rendered_pairs"]) > 0 else "⚠️"
        md.append(f"- {ok} {chain['chain']} · static={chain['best_static_pairs']} · rendered={chain['best_rendered_pairs']} · best={chain['best_url']}")
        for source in chain["sources"]:
            static_pairs = len(source["static"].get("pairs", []))
            rendered_pairs = len(source["rendered"].get("pairs", []))
            api_count = len(source["rendered"].get("api_urls", []))
            md.append(f"  - static_pairs={static_pairs} rendered_pairs={rendered_pairs} api_urls={api_count} · {source['url']}")
            for pair in (source["static"].get("pairs", []) or source["rendered"].get("pairs", []))[:3]:
                md.append(f"    - {pair['product']} · {pair['price']}€")
            for api in source["rendered"].get("api_urls", [])[:3]:
                md.append(f"    - api? {api}")
    (reports / "skai_deep_offer_audit.md").write_text("\n".join(md), encoding="utf-8")


if __name__ == "__main__":
    main()
