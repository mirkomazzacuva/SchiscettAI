#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from datetime import datetime, UTC
from pathlib import Path
from urllib.request import Request, urlopen


FALLBACKS = {
    "PENNY": [
        "https://www.penny.it/offerte",
        "https://www.promoqui.it/volantino/penny-market",
        "https://zonavolantini.com/penny",
    ],
    "Coop": [
        "https://www.coopfirenze.it/negozi-e-promo/offerte-e-volantini/offerte-per-i-soci",
        "https://www.volantinofacile.it/coop/volantino-coop/firenze",
    ],
    "Conad": [
        "https://www.doveconviene.it/volantino/conad-superstore",
        "https://www.volantinofacile.it/conad-superstore/volantino-conad-superstore",
    ],
    "PAM": [
        "https://www.doveconviene.it/volantino/panorama",
        "https://www.volantinofacile.it/pam/volantino-pam",
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


def fetch(url: str) -> tuple[int, str]:
    request = Request(url, headers={
        "User-Agent": "Mozilla/5.0 SKAI-LiveOfferAudit/1.0",
        "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
    })
    with urlopen(request, timeout=18) as response:
        body = response.read(900000).decode("utf-8", errors="ignore")
        return response.status, body


def rough_product_price_pairs(html: str) -> int:
    text = re.sub(r"<script.*?</script>", " ", html, flags=re.I | re.S)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    matches = re.findall(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ0-9 '.,%/-]{8,110}\s+\d{1,3}[,.]\d{2}\s*€", text)
    return len(matches)


def main():
    root = Path(__file__).resolve().parents[1]
    reports = root / "qa" / "reports"
    reports.mkdir(exist_ok=True)

    rows = []
    for chain, urls in FALLBACKS.items():
        chain_rows = []
        for url in urls:
            item = {"chain": chain, "url": url, "ok": False, "status": None, "rough_pairs": 0, "error": ""}
            try:
                status, body = fetch(url)
                item["status"] = status
                item["rough_pairs"] = rough_product_price_pairs(body)
                item["ok"] = status == 200 and item["rough_pairs"] > 0
            except Exception as error:
                item["error"] = str(error)[:250]
            chain_rows.append(item)
        best = max(chain_rows, key=lambda row: row.get("rough_pairs", 0))
        rows.append({"chain": chain, "best_pairs": best.get("rough_pairs", 0), "best_url": best.get("url", ""), "sources": chain_rows})

    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "note": "Non-blocking audit: controlla official+fallback. Rough pairs significa testo che somiglia a prodotto+prezzo.",
        "chains": rows,
    }
    (reports / "skai_live_offer_audit.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    md = ["# SKAI Live Offer Audit", ""]
    for row in rows:
        status = "✅" if row["best_pairs"] > 0 else "⚠️"
        md.append(f"- {status} {row['chain']} · best_pairs={row['best_pairs']} · {row['best_url']}")
        for source in row["sources"]:
            md.append(f"  - {source['rough_pairs']} pairs · status={source['status']} · {source['url']} · {source.get('error','')}")
    (reports / "skai_live_offer_audit.md").write_text("\n".join(md), encoding="utf-8")


if __name__ == "__main__":
    main()
