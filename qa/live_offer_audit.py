#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from datetime import datetime, UTC
from pathlib import Path
from urllib.request import Request, urlopen


def fetch(url: str) -> tuple[int, str]:
    request = Request(url, headers={
        "User-Agent": "Mozilla/5.0 SKAI-LiveOfferAudit/1.0",
        "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
    })
    with urlopen(request, timeout=18) as response:
        body = response.read(750000).decode("utf-8", errors="ignore")
        return response.status, body


def rough_product_price_pairs(html: str) -> int:
    text = re.sub(r"<script.*?</script>", " ", html, flags=re.I | re.S)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    matches = re.findall(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ0-9 '.,-]{8,90}\s+\d{1,3}[,.]\d{2}\s*€", text)
    return len(matches)


def main():
    root = Path(__file__).resolve().parents[1]
    sources = json.loads((root / "data" / "offer_sources.json").read_text(encoding="utf-8"))
    reports = root / "qa" / "reports"
    reports.mkdir(exist_ok=True)

    rows = []
    for source in sources:
        chain = source.get("chain", "")
        url = source.get("url", "")
        item = {"chain": chain, "url": url, "ok": False, "status": None, "rough_pairs": 0, "error": ""}
        try:
            status, body = fetch(url)
            item["status"] = status
            item["rough_pairs"] = rough_product_price_pairs(body)
            item["ok"] = status == 200 and item["rough_pairs"] > 0
        except Exception as error:
            item["error"] = str(error)[:250]
        rows.append(item)

    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "note": "Non-blocking audit: segnala quali fonti sembrano esporre prodotto+prezzo leggibili.",
        "sources": rows,
    }
    (reports / "skai_live_offer_audit.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md = ["# SKAI Live Offer Audit", ""]
    for row in rows:
        status = "✅" if row["ok"] else "⚠️"
        md.append(f"- {status} {row['chain']} · rough_pairs={row['rough_pairs']} · status={row['status']} · {row.get('error','')}")
    (reports / "skai_live_offer_audit.md").write_text("\n".join(md), encoding="utf-8")


if __name__ == "__main__":
    main()
