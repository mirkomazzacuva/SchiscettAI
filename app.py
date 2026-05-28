import json
import re
import html
from pathlib import Path
from collections import Counter
from io import StringIO
from urllib.parse import urlparse, parse_qs
from math import radians, sin, cos, sqrt, atan2

import pandas as pd
import requests
import streamlit as st

try:
    import folium
    from streamlit_folium import st_folium
    MAP_AVAILABLE = True
    MAP_ERROR = None
except Exception as error:
    folium = None
    st_folium = None
    MAP_AVAILABLE = False
    MAP_ERROR = error


st.set_page_config(
    page_title="SKiscettAI · SKAI Copilot",
    page_icon="⚡",
    layout="wide",
)


WORK_DAYS = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì"]

REMOTE_OFFERS_DISABLED = ""  # SKAI web-only mode

CLUSTER_VISUALS = {
    "riso_pollo": {
        "emoji": "🍚",
        "title": "Riso & proteine",
        "subtitle": "Bowl proteiche, sazianti e perfette da ufficio",
    },
    "pasta_fredda": {
        "emoji": "🍝",
        "title": "Pasta fredda",
        "subtitle": "Mediterranea, veloce e facile da trasportare",
    },
    "couscous_verdure": {
        "emoji": "🥙",
        "title": "Couscous & verdure",
        "subtitle": "Colorato, economico e pronto in pochi minuti",
    },
    "bowl_mediterranea": {
        "emoji": "🥗",
        "title": "Bowl mediterranea",
        "subtitle": "Fresca, bilanciata e molto meal prep",
    },
    "vegetariana_legumi": {
        "emoji": "🫘",
        "title": "Vegetariana smart",
        "subtitle": "Legumi, cereali e verdure in versione glamour",
    },
    "meal_prep_box": {
        "emoji": "🍱",
        "title": "Meal prep box",
        "subtitle": "Organizzata, pratica e pronta per la settimana",
    },
    "insalata_proteica": {
        "emoji": "🥬",
        "title": "Insalata proteica",
        "subtitle": "Leggera ma saziante, buona anche fredda",
    },
    "wrap_integrale": {
        "emoji": "🌯",
        "title": "Wrap integrale",
        "subtitle": "Compatto, veloce e perfetto da portare via",
    },
    "gourmet_light": {
        "emoji": "✨",
        "title": "Gourmet light",
        "subtitle": "Più curata, elegante e bella da vedere",
    },
}


def load_css(file_path):
    css_path = Path(file_path)
    if css_path.exists():
        css = css_path.read_text(encoding="utf-8")
        st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def load_json(file_path):
    path = Path(file_path)

    if not path.exists():
        return []

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as error:
        st.error(f"Errore nel caricamento di {file_path}: {error}")
        return []


def clean_offers_dataframe(df):
    df = df.fillna("")

    # Elimina righe completamente vuote o righe senza campi minimi.
    core_fields = ["id", "store_id", "ingredient", "product_name", "price"]

    for field in core_fields:
        if field not in df.columns:
            df[field] = ""

    df = df[
        df[core_fields]
        .astype(str)
        .apply(lambda row: any(value.strip() for value in row), axis=1)
    ]

    df = df[
        df[["store_id", "ingredient", "product_name"]]
        .astype(str)
        .apply(lambda row: all(value.strip() for value in row), axis=1)
    ]

    offers = df.to_dict(orient="records")

    for offer in offers:
        for numeric_field in ["price", "old_price"]:
            value = offer.get(numeric_field, "")
            if value == "":
                continue
            try:
                offer[numeric_field] = float(value)
            except ValueError:
                offer[numeric_field] = value

    return offers



def google_sheet_csv_url_variants(csv_url):
    clean_url = html.unescape(str(csv_url).strip())
    variants = []

    def add(url):
        if url and url not in variants:
            variants.append(url)

    add(clean_url)

    parsed = urlparse(clean_url)
    query = parse_qs(parsed.query)
    gid = query.get("gid", ["0"])[0]

    if "/spreadsheets/d/e/" in clean_url:
        try:
            pub_id = clean_url.split("/spreadsheets/d/e/", 1)[1].split("/", 1)[0]

            add(f"https://docs.google.com/spreadsheets/d/e/{pub_id}/pub?output=csv&gid={gid}")
            add(f"https://docs.google.com/spreadsheets/d/e/{pub_id}/pub?gid={gid}&output=csv")
            add(f"https://docs.google.com/spreadsheets/d/e/{pub_id}/pub?single=true&output=csv&gid={gid}")
            add(f"https://docs.google.com/spreadsheets/d/e/{pub_id}/pub?gid={gid}&single=true&output=csv")
            add(f"https://docs.google.com/spreadsheets/d/e/{pub_id}/gviz/tq?tqx=out:csv&gid={gid}")
        except Exception:
            pass

    if "/spreadsheets/d/" in clean_url and "/spreadsheets/d/e/" not in clean_url:
        try:
            sheet_id = clean_url.split("/spreadsheets/d/", 1)[1].split("/", 1)[0]

            add(f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}")
            add(f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&gid={gid}")
        except Exception:
            pass

    return variants


def response_looks_like_csv(text_value):
    if not text_value:
        return False

    start = text_value.strip()[:500].lower()

    if start.startswith("<!doctype") or start.startswith("<html") or "<html" in start:
        return False

    return "id,store_id,ingredient,product_name" in start


@st.cache_data(ttl=1800)
def load_offers_from_remote_csv(csv_url):
    if not csv_url:
        return []

    attempted = []
    last_preview = ""

    for candidate_url in google_sheet_csv_url_variants(csv_url):
        try:
            response = requests.get(
                candidate_url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/125.0 Safari/537.36 SKiscettAI/1.0"
                    ),
                    "Accept": "text/csv,text/plain,*/*",
                },
                timeout=20,
                allow_redirects=True,
            )

            preview = response.text[:300] if response.text else ""
            last_preview = preview
            attempted.append(f"{response.status_code} - {candidate_url}")

            if response.status_code != 200:
                continue

            csv_text = response.text.strip()

            if not response_looks_like_csv(csv_text):
                last_preview = csv_text[:300]
                continue

            df = pd.read_csv(StringIO(csv_text))
            return clean_offers_dataframe(df)

        except Exception as error:
            attempted.append(f"ERRORE - {candidate_url} - {error}")

    raise RuntimeError(
        "Non ho trovato un URL web valido tra le varianti provate. "
        f"Tentativi: {' | '.join(attempted[:6])}. "
        f"Ultima risposta iniziale: {last_preview}"
    )


def load_offers_data(remote_csv_url, local_csv_path, json_path):
    if remote_csv_url:
        try:
            offers = load_offers_from_remote_csv(remote_csv_url)
            if offers:
                return offers
        except Exception as error:
            st.warning(
                "Non riesco a leggere il parser web pubblicato. "
                f"Uso il web locale o il JSON di fallback. Dettaglio: {error}"
            )

    csv_file = Path(local_csv_path)

    if csv_file.exists():
        try:
            df = pd.read_csv(csv_file)
            offers = clean_offers_dataframe(df)

            if offers:
                return offers
        except Exception as error:
            st.warning(
                f"Non riesco a leggere {local_csv_path}. Uso il JSON di fallback. Errore: {error}"
            )

    return load_json(json_path)


def build_cluster_visuals(clusters):
    visuals = {}

    if not isinstance(clusters, list):
        return visuals

    for cluster in clusters:
        cluster_id = cluster.get("id", "")

        if cluster_id:
            visuals[cluster_id] = {
                "emoji": cluster.get("emoji", "🍽️"),
                "title": cluster.get("name", "SKiscetta smart"),
                "subtitle": cluster.get(
                    "description",
                    "Ricetta pratica e facile da portare",
                ),
                "color": cluster.get("color", "#F8F3EA"),
                "mood": cluster.get("mood", ""),
                "image_prompt": cluster.get("image_prompt", ""),
            }

    return visuals


def normalize_text(text):
    return str(text).strip().lower()


def parse_minutes(value):
    text = str(value)
    digits = "".join(char for char in text if char.isdigit())
    if digits:
        return int(digits)
    return 999


def go_to(page_name):
    st.session_state.page = page_name


def combined_recipes():
    return recipes + st.session_state.custom_recipes


def get_recipe_by_id(recipe_list, recipe_id):
    for recipe in recipe_list:
        if recipe.get("id") == recipe_id:
            return recipe
    return None


def get_recipe_by_title(recipe_list, title):
    for recipe in recipe_list:
        if recipe.get("title") == title:
            return recipe
    return None


def save_favorite(recipe_id):
    if recipe_id not in st.session_state.favorites:
        st.session_state.favorites.append(recipe_id)
        st.success("Ricetta salvata nei preferiti.")
    else:
        st.info("Questa ricetta è già nei preferiti.")


def remove_favorite(recipe_id):
    if recipe_id in st.session_state.favorites:
        st.session_state.favorites.remove(recipe_id)
        st.success("Ricetta rimossa dai preferiti.")


def get_favorite_recipes(recipe_list):
    return [
        recipe for recipe in recipe_list
        if recipe.get("id") in st.session_state.favorites
    ]


def get_meal_plan_recipes(recipe_list):
    selected = []

    for day in WORK_DAYS:
        title = st.session_state.get(f"meal_{day}", "Nessuna ricetta")
        recipe = get_recipe_by_title(recipe_list, title)
        if recipe:
            selected.append(recipe)

    return selected


def aggregate_ingredients(recipe_list, extra_items=None):
    counter = Counter()

    for recipe in recipe_list:
        for ingredient in recipe.get("ingredients", []):
            clean = str(ingredient).strip()
            if clean:
                counter[clean] += 1

    if extra_items:
        for item in extra_items:
            clean = str(item).strip()
            if clean:
                counter[clean] += 1

    return counter


def build_shopping_text(counter):
    if not counter:
        return "Lista della spesa vuota."

    lines = ["Lista della spesa SKiscettAI", ""]

    for ingredient, count in sorted(counter.items()):
        if count > 1:
            lines.append(f"- {ingredient} x{count}")
        else:
            lines.append(f"- {ingredient}")

    return "\n".join(lines)



def store_lookup(stores):
    lookup = {}
    for store in stores:
        store_id = store.get("id", "")
        if store_id:
            lookup[store_id] = store
    return lookup


def haversine_km(lat1, lon1, lat2, lon2):
    radius_km = 6371.0
    d_lat = radians(lat2 - lat1)
    d_lon = radians(lon2 - lon1)
    a = (
        sin(d_lat / 2) ** 2
        + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lon / 2) ** 2
    )
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return radius_km * c


def offers_for_ingredients(offers, ingredients):
    wanted = [normalize_text(item) for item in ingredients]
    matched = []

    for offer in offers:
        ingredient = normalize_text(offer.get("ingredient", ""))
        if ingredient and any(ingredient in item or item in ingredient for item in wanted):
            matched.append(offer)

    return matched


def offer_rows(offers, stores_by_id, user_lat=None, user_lon=None):
    rows = []

    for offer in offers:
        store = stores_by_id.get(offer.get("store_id", ""), {})
        distance = None

        if user_lat is not None and user_lon is not None and store.get("lat") and store.get("lon"):
            distance = haversine_km(user_lat, user_lon, store["lat"], store["lon"])

        origin = offer.get("origin", offer.get("offer_origin", "web"))
        chain = offer.get("chain", offer.get("chain_inferred", store.get("chain", "")))
        store_name = store.get("name", chain or offer.get("store_id", ""))

        rows.append(
            {
                "origine": format_offer_origin(origin) if "format_offer_origin" in globals() else origin,
                "catena": chain,
                "ingrediente": offer.get("ingredient", ""),
                "prodotto": clean_display_product_name(offer.get("product_name", "")) if "clean_display_product_name" in globals() else offer.get("product_name", ""),
                "prezzo": f"{offer.get('price', '')} {offer.get('unit', '')}",
                "prima": f"{offer.get('old_price', '')} {offer.get('unit', '')}",
                "negozio": store_name,
                "zona": store.get("area", ""),
                "distanza_km": round(distance, 1) if distance is not None else "",
                "fonte": offer.get("source", ""),
                "note": offer.get("notes", ""),
            }
        )

    return rows



def parse_price(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None




# =========================================================
# Multi-chain Offer Parser v1 - safe and non-blocking
# =========================================================

CHAIN_PARSER_URLS = {
    "PENNY": "https://www.penny.it/offerte",
    "Coop": "https://www.coopfirenze.it/negozi-e-promo/offerte-e-volantini",
    "Conad": "https://volantini.conad.it/",
    "PAM": "https://www.pampanorama.it/",
    "Lidl": "https://www.lidl.it/c/offerte/c10026788",
    "Eurospin": "https://www.eurospin.it/volantino/",
    "Esselunga": "https://www.esselunga.it/it-it/negozi/volantino.html",
    "Carrefour": "https://www.carrefour.it/promozioni/",
    "MD": "https://www.mdspa.it/volantino/",
}


def price_to_float(value):
    text = str(value or "").replace("€", "").replace(",", ".").strip()
    try:
        return float(text)
    except ValueError:
        return None


def infer_ingredient_from_product_text(product_text):
    text = normalize_for_match(product_text) if "normalize_for_match" in globals() else normalize_text(product_text)

    mapping = [
        ("pollo", "pollo"), ("tacchino", "tacchino"), ("tonno", "tonno"),
        ("salmone", "salmone"), ("merluzzo", "merluzzo"), ("uova", "uova"),
        ("yogurt", "yogurt"), ("hipro", "yogurt proteico"), ("tofu", "tofu"),
        ("ceci", "ceci"), ("lenticchie", "lenticchie"), ("fagioli", "fagioli"),
        ("cannellini", "fagioli"), ("piselli", "piselli"),
        ("pasta integrale", "pasta integrale"), ("fusilli", "pasta"),
        ("penne", "pasta"), ("spaghetti", "pasta"), ("riso", "riso"),
        ("basmati", "riso basmati"), ("farro", "farro"), ("orzo", "orzo"),
        ("couscous", "couscous"), ("passata", "passata pomodoro"),
        ("pomodoro", "pomodoro"), ("zucchine", "zucchine"),
        ("carote", "carote"), ("carciofi", "carciofi"), ("melanzane", "melanzane"),
        ("peperoni", "peperoni"), ("insalata", "insalata"), ("patate", "patate"),
        ("olio", "olio EVO"), ("limone", "limone"), ("feta", "feta"),
        ("mozzarella", "mozzarella"), ("ricotta", "ricotta"), ("pane", "pane"),
        ("wrap", "wrap"), ("piadina", "piadina"),
    ]

    for keyword, ingredient in mapping:
        if keyword in text:
            return ingredient

    words = [word for word in text.split() if len(word) > 3]
    return words[0] if words else "offerta"


def clean_offer_snippet(snippet):
    snippet = html.unescape(str(snippet or ""))
    snippet = re.sub(r"\s+", " ", snippet)
    snippet = snippet.strip(" -–—|•·")
    return snippet[:180]


def cleanup_product_candidate(value):
    text = html.unescape(str(value or ""))
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\\u[0-9a-fA-F]{4}", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" -–—|•·:,;")

    bad_fragments = [
        "prezzo al",
        "prezzo totale",
        "peso confezione",
        "per poter usare",
        "codice promozionale",
        "fino al",
        "privacy",
        "cookie",
        "newsletter",
        "javascript",
        "carrello",
        "login",
        "registrati",
    ]

    low = normalize_text(text)

    for fragment in bad_fragments:
        low = low.replace(fragment, " ")

    text = re.sub(r"\s+", " ", text).strip(" -–—|•·:,;")

    # Remove date-heavy / legal-like prefixes.
    text = re.sub(r"(?i)\bFino al\s+\d{2}/\d{2}/\d{4}.*", "", text).strip()
    text = re.sub(r"(?i)\bPrezzo al.*", "", text).strip()
    text = re.sub(r"(?i)\bPeso confezione.*", "", text).strip()

    return text[:110].strip()


def is_bad_offer_text(text):
    low = normalize_text(text)

    bad_words = [
        "privacy",
        "cookie",
        "newsletter",
        "termini",
        "accessibilità",
        "javascript",
        "facebook",
        "instagram",
        "prezzo al kg",
        "prezzo al l",
        "prezzo totale",
        "peso confezione",
        "per poter usare",
        "codice promozionale",
    ]

    if any(word in low for word in bad_words):
        return True

    # Reject snippets that are mostly units/dates/pricing mechanics and not product names.
    alpha_words = [word for word in re.findall(r"[a-zA-ZàèéìòùÀÈÉÌÒÙ]{4,}", text)]
    if len(alpha_words) < 2:
        return True

    return False


def extract_structured_price_products(text_body):
    raw = html.unescape(str(text_body or ""))
    results = []
    seen = set()

    patterns = [
        re.compile(
            r'"(?:name|productName|displayName|title)"\s*:\s*"(?P<name>[^"]{4,140})".{0,1200}?"(?:price|salePrice|currentPrice|value)"\s*:\s*"?(?P<price>\d{1,3}[,.]\d{2})',
            flags=re.I | re.S,
        ),
        re.compile(
            r'"(?:price|salePrice|currentPrice|value)"\s*:\s*"?(?P<price>\d{1,3}[,.]\d{2}).{0,1200}?"(?:name|productName|displayName|title)"\s*:\s*"(?P<name>[^"]{4,140})"',
            flags=re.I | re.S,
        ),
        re.compile(
            r'itemprop=["\']name["\'][^>]*>(?P<name>[^<]{4,140})<.{0,1200}?itemprop=["\']price["\'][^>]*content=["\'](?P<price>\d{1,3}[,.]\d{2})',
            flags=re.I | re.S,
        ),
    ]

    for pattern in patterns:
        for match in pattern.finditer(raw):
            name = cleanup_product_candidate(match.group("name"))
            price = price_to_float(match.group("price"))

            if not name or price is None:
                continue

            if is_bad_offer_text(name):
                continue

            key = (normalize_text(name), price)

            if key in seen:
                continue

            seen.add(key)
            results.append({"product": name, "snippet": name, "price": price})

            if len(results) >= 30:
                return results

    return results


def extract_price_snippets_from_text(text_body):
    structured = extract_structured_price_products(text_body)

    if structured:
        return structured

    cleaned = re.sub(r"<script.*?</script>", " ", text_body, flags=re.S | re.I)
    cleaned = re.sub(r"<style.*?</style>", " ", cleaned, flags=re.S | re.I)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    cleaned = html.unescape(cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    pattern = re.compile(
        r"(?P<before>.{0,120})(?P<price>\d{1,3}[,.]\d{2})\s*€(?P<after>.{0,90})",
        flags=re.I,
    )

    results = []
    seen = set()

    for match in pattern.finditer(cleaned):
        price = price_to_float(match.group("price"))

        if price is None:
            continue

        before = cleanup_product_candidate(match.group("before"))
        after = cleanup_product_candidate(match.group("after"))
        snippet = before or after

        if not snippet:
            continue

        if is_bad_offer_text(snippet):
            continue

        key = (normalize_text(snippet), price)

        if key in seen:
            continue

        seen.add(key)
        results.append({"product": snippet, "snippet": snippet, "price": price})

        if len(results) >= 20:
            break

    return results


@st.cache_data(ttl=3600)
def fetch_chain_offers_v1(chain, url):
    if not chain or not url:
        return {"chain": chain, "ok": False, "message": "Parser non configurato.", "offers": []}

    try:
        response = requests.get(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36 SKiscettAI/1.0"
                ),
                "Accept": "text/html,text/plain,*/*",
            },
            timeout=16,
            allow_redirects=True,
        )

        if response.status_code != 200:
            return {"chain": chain, "ok": False, "message": f"{chain}: fonte non leggibile ora, HTTP {response.status_code}.", "offers": []}

        snippets = extract_price_snippets_from_text(response.text)
        offers = []
        chain_slug = normalize_for_match(chain).replace(" ", "_")

        for index, item in enumerate(snippets, start=1):
            product_name = item.get("product", item.get("snippet", ""))
            snippet = item.get("snippet", product_name)
            ingredient = infer_ingredient_from_product_text(product_name or snippet)
            offers.append(
                {
                    "id": f"{chain_slug}_web_{index:03d}",
                    "store_id": f"{chain_slug}_web",
                    "chain": chain,
                    "ingredient": ingredient,
                    "product_name": product_name or snippet,
                    "price": item["price"],
                    "unit": "web",
                    "old_price": "",
                    "valid_from": "",
                    "valid_until": "",
                    "source": url,
                    "category": "offerte web",
                    "notes": f"Estratta automaticamente dal parser {chain} v1. Da verificare sul sito ufficiale.",
                    "origin": f"web_{chain_slug}",
                }
            )

        if offers:
            return {"chain": chain, "ok": True, "message": f"{chain}: {len(offers)} offerte/snippet estratti.", "offers": offers}

        return {"chain": chain, "ok": True, "message": f"{chain}: fonte raggiunta ma nessuna offerta strutturata estratta.", "offers": []}

    except Exception as error:
        return {"chain": chain, "ok": False, "message": f"{chain}: parser non disponibile: {error}", "offers": []}


def parser_url_for_chain(chain, offer_sources):
    source = get_offer_source_for_chain_v2(chain, offer_sources) if "get_offer_source_for_chain_v2" in globals() else {}
    if source and source.get("url"):
        return source.get("url")
    return CHAIN_PARSER_URLS.get(chain, "")


def chains_with_parser_enabled(nearby_stores, offer_sources):
    chains = sorted(
        set(
            infer_store_chain_v2(store, offer_sources)
            for store in nearby_stores
            if infer_store_chain_v2(store, offer_sources)
            and infer_store_chain_v2(store, offer_sources) != "Altro"
        )
    )

    priority = ["Coop", "Conad", "PAM", "PENNY", "Lidl", "Eurospin", "Carrefour", "MD", "Esselunga"]

    chains = sorted(
        chains,
        key=lambda chain: priority.index(chain) if chain in priority else 99,
    )

    return [chain for chain in chains if parser_url_for_chain(chain, offer_sources)]


def fetch_multi_chain_offers_v1(chains, offer_sources, max_chains=5):
    results = []
    web_offers = []
    for chain in chains[:max_chains]:
        url = parser_url_for_chain(chain, offer_sources)
        result = fetch_chain_offers_v1(chain, url)
        results.append(result)
        web_offers.extend(result.get("offers", []))
    return results, web_offers




# =========================================================
# Multi-chain Parser v1.1 utilities
# =========================================================

def format_offer_origin(origin):
    origin = str(origin or "manual")

    if origin == "manual":
        return "web"

    if origin.startswith("web_"):
        chain = origin.replace("web_", "").replace("_", " ").strip().upper()
        return f"web {chain}"

    return origin


def offer_origin_group(offer):
    origin = str(offer.get("origin", offer.get("offer_origin", "manual")))

    if origin == "manual":
        return "manual"

    if origin.startswith("web_"):
        return "web"

    return "manual"


def clean_display_product_name(value):
    text = html.unescape(str(value or ""))
    text = re.sub(r"\s+", " ", text).strip()

    # Remove very common website fragments when parser extracts surrounding text.
    noise_fragments = [
        "Aggiungi al carrello",
        "Scopri di più",
        "Mostra dettagli",
        "Offerte",
        "Volantino",
    ]

    for fragment in noise_fragments:
        text = text.replace(fragment, " ")

    text = re.sub(r"\s+", " ", text).strip(" -–—|•·")

    if len(text) > 140:
        text = text[:137].rstrip() + "..."

    return text


def offer_dedupe_key(offer):
    chain = normalize_for_match(offer.get("chain", offer.get("chain_inferred", "")))
    ingredient = normalize_for_match(offer.get("ingredient", ""))
    product = normalize_for_match(clean_display_product_name(offer.get("product_name", "")))[:60]
    price = str(offer.get("price", "")).replace(",", ".").strip()

    return (chain, ingredient, product, price)


def dedupe_offers(offers):
    seen = set()
    result = []

    # Prefer manual offers first because they are curated/override.
    sorted_offers = sorted(
        offers,
        key=lambda offer: 0 if offer_origin_group(offer) == "manual" else 1,
    )

    for offer in sorted_offers:
        key = offer_dedupe_key(offer)

        if key in seen:
            continue

        seen.add(key)
        result.append(offer)

    return result


def filter_offers_by_source(offers, source_filter):
    if source_filter == "Solo web":
        return [offer for offer in offers if offer_origin_group(offer) == "manual"]

    if source_filter == "Solo web":
        return [offer for offer in offers if offer_origin_group(offer) == "web"]

    return offers


def limit_web_offers(offers, limit):
    manual = [offer for offer in offers if offer_origin_group(offer) == "manual"]
    web = [offer for offer in offers if offer_origin_group(offer) == "web"]

    return manual + web[:limit]


def offer_source_counts(offers):
    manual = len([offer for offer in offers if offer_origin_group(offer) == "manual"])
    web = len([offer for offer in offers if offer_origin_group(offer) == "web"])
    return manual, web, len(offers)


def source_filter_label():
    return [
        "Tutte",
        "Solo web",
        "Solo web",
    ]

# =========================================================
# SKAI Black Label UX helpers
# =========================================================



def skai_parser_chain_candidates(nearby_stores, offer_sources, minimum=5):
    """Return parser chains to check.
    First use chains actually found nearby, then top configured sources so the app
    is not silently stuck on a single recognized OSM chain.
    """
    priority = ["Coop", "Conad", "PAM", "PENNY", "Lidl", "Eurospin", "Carrefour", "MD", "Esselunga"]

    found = []
    for store in nearby_stores:
        chain = infer_store_chain_v2(store, offer_sources)
        if chain and chain != "Altro" and parser_url_for_chain(chain, offer_sources):
            found.append(chain)

    ordered_found = []
    for chain in priority:
        if chain in found and chain not in ordered_found:
            ordered_found.append(chain)

    for chain in found:
        if chain not in ordered_found:
            ordered_found.append(chain)

    configured = [
        source.get("chain")
        for source in offer_sources
        if source.get("chain") and parser_url_for_chain(source.get("chain"), offer_sources)
    ]

    for chain in priority:
        if chain in configured and chain not in ordered_found and len(ordered_found) < minimum:
            ordered_found.append(chain)

    return ordered_found


def recipe_ingredient_score(recipe, ingredients):
    wanted = [normalize_text(item) for item in ingredients if str(item).strip()]
    recipe_ingredients = [normalize_text(item) for item in recipe.get("ingredients", [])]

    if not wanted:
        return 0

    score = 0
    for item in wanted:
        for recipe_item in recipe_ingredients:
            if item and (item in recipe_item or recipe_item in item):
                score += 1
                break

    return score


def skai_recipes_for_home_ingredients(recipes, ingredients, goal, limit=4):
    scored = []

    for recipe in recipes:
        score = recipe_ingredient_score(recipe, ingredients)
        meta = recipe.get("meta", {})
        goal_text = normalize_text(goal)

        if goal_text and goal_text in normalize_text(meta.get("goal", "")):
            score += 1

        scored.append((score, recipe))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [recipe for score, recipe in scored[:limit] if score > 0] or [recipe for _, recipe in scored[:limit]]


def skai_week_plan_from_recipes(recipes, offers, days=5):
    deal_items = best_deal_recipes(recipes, offers, {}, limit=max(days, 5)) if offers else []
    selected = []

    for item in deal_items:
        selected.append(
            {
                "recipe": item["recipe"],
                "reason": f"{item['coverage']} ingredienti coperti da offerte",
                "score": item.get("coverage", 0),
            }
        )

    if len(selected) < days:
        used = {item["recipe"].get("id") for item in selected}
        for recipe in recipes:
            if recipe.get("id") not in used:
                selected.append(
                    {
                        "recipe": recipe,
                        "reason": "scelta bilanciata dal catalogo",
                        "score": 0,
                    }
                )
            if len(selected) >= days:
                break

    return selected[:days]


def skai_store_label(store):
    name = store.get("name", "Punto vendita")
    chain = store.get("chain_normalized") or store.get("chain", "")
    distance = store.get("distance_km", "")
    parts = [name]

    if chain and chain != "Altro" and normalize_text(chain) not in normalize_text(name):
        parts.append(chain)

    if distance != "":
        parts.append(f"{distance} km")

    return " · ".join(str(part) for part in parts if str(part).strip())


def render_skai_action_plan(intent):
    if intent == "Crea una SKiscetta con quello che ho":
        title = "1. Scrivi cosa hai · 2. SKAI crea · 3. Salva la ricetta"
        subtitle = "Non devi scegliere una ricetta target: parti dagli ingredienti."
    elif intent == "Faccio il piano spesa settimanale":
        title = "1. Scegli giorni · 2. SKAI guarda le offerte · 3. Crea piano + lista"
        subtitle = "La spesa settimanale parte da ricette e offerte, non da una tabella vuota."
    else:
        title = "1. Inserisci CAP · 2. Guarda la mappa · 3. Confronta offerte pulite"
        subtitle = "Radar puro per capire cosa c'è vicino e quali parser danno dati leggibili."

    st.markdown(
        f"""
        <div class="skai-action-plan">
            <strong>{title}</strong>
            <span>{subtitle}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def is_offer_displayable(offer):
    product = clean_display_product_name(offer.get("product_name", ""))

    if not product:
        return False

    if is_bad_offer_text(product):
        return False

    price = parse_price(offer.get("price", None))

    if price is None:
        return False

    return True


def split_offer_quality(offers):
    clean = []
    raw = []

    for offer in offers:
        if is_offer_displayable(offer):
            clean.append(offer)
        else:
            raw.append(offer)

    return clean, raw



def skai_chain_summary(offers):
    summary = {}

    for offer in offers:
        chain = offer.get("chain", offer.get("chain_inferred", "Altro")) or "Altro"
        summary.setdefault(chain, {"count": 0, "min_price": None})
        summary[chain]["count"] += 1

        price = parse_price(offer.get("price", None))
        if price is not None:
            current = summary[chain]["min_price"]
            summary[chain]["min_price"] = price if current is None else min(current, price)

    rows = []

    for chain, data in summary.items():
        rows.append(
            {
                "catena": chain,
                "offerte": data["count"],
                "prezzo_min": data["min_price"] if data["min_price"] is not None else "",
            }
        )

    return sorted(rows, key=lambda row: row["offerte"], reverse=True)


def skai_best_offer(offers):
    priced = []

    for offer in offers:
        price = parse_price(offer.get("price", None))

        if price is not None:
            priced.append((price, offer))

    if not priced:
        return None

    priced.sort(key=lambda item: item[0])
    return priced[0][1]


def skai_radar_score(nearby_stores, nearby_chains, offers):
    stores_score = min(len(nearby_stores), 50) * 1.2
    chains_score = min(len(nearby_chains), 12) * 3
    offers_score = min(len(offers), 50) * 1.4
    score = int(min(100, stores_score + chains_score + offers_score))
    return score


def skai_format_money(value):
    price = parse_price(value)
    if price is None:
        return str(value or "")
    return f"{price:.2f} €"


def render_skai_offer_card(offer, index):
    chain = offer.get("chain", offer.get("chain_inferred", "Web")) or "Web"
    price = skai_format_money(offer.get("price", ""))
    product = clean_display_product_name(offer.get("product_name", ""))
    ingredient = offer.get("ingredient", "")
    origin = format_offer_origin(offer.get("origin", "web")) if "format_offer_origin" in globals() else "web"

    if not product or is_bad_offer_text(product):
        product = f"Offerta {chain} da verificare sul volantino"

    st.markdown(
        f"""
        <div class="skai-offer-card">
            <div class="skai-offer-top">
                <span>{chain}</span>
                <span>{origin}</span>
            </div>
            <div class="skai-offer-price">{price}</div>
            <div class="skai-offer-product">{product}</div>
            <div class="skai-offer-match">match · {ingredient if ingredient else "offerta"}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )



def render_skai_section_label(kicker, title, subtitle=""):
    st.markdown(
        f"""
        <div class="skai-section-label">
            <span>{kicker}</span>
            <h2>{title}</h2>
            <p>{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )






def deal_score_for_recipe(recipe, offers, stores_by_id):
    ingredients = [
        normalize_text(ingredient)
        for ingredient in recipe.get("ingredients", [])
        if str(ingredient).strip()
    ]

    if not ingredients:
        return None

    matched_offers = offers_for_ingredients(offers, ingredients)
    covered_ingredients = set()
    store_ids = set()
    total_demo_price = 0.0
    priced_items = 0

    for offer in matched_offers:
        offer_ingredient = normalize_text(offer.get("ingredient", ""))

        for ingredient in ingredients:
            if offer_ingredient and (offer_ingredient in ingredient or ingredient in offer_ingredient):
                covered_ingredients.add(ingredient)

        store_id = offer.get("store_id", "")
        if store_id:
            store_ids.add(store_id)

        price = parse_price(offer.get("price", None))
        if price is not None:
            total_demo_price += price
            priced_items += 1

    coverage = len(covered_ingredients)
    coverage_ratio = coverage / len(ingredients) if ingredients else 0

    return {
        "recipe": recipe,
        "matched_offers": matched_offers,
        "covered_ingredients": sorted(covered_ingredients),
        "store_ids": sorted(store_ids),
        "coverage": coverage,
        "total_ingredients": len(ingredients),
        "coverage_ratio": coverage_ratio,
        "total_demo_price": round(total_demo_price, 2),
        "priced_items": priced_items,
        "score": coverage * 100 + len(matched_offers) * 5 - total_demo_price,
    }


def best_deal_recipes(recipe_list, offers, stores_by_id, limit=5):
    scored = []

    for recipe in recipe_list:
        item = deal_score_for_recipe(recipe, offers, stores_by_id)

        if item and item["coverage"] > 0:
            scored.append(item)

    scored.sort(
        key=lambda item: (
            -item["coverage_ratio"],
            -item["coverage"],
            item["total_demo_price"],
        )
    )

    return scored[:limit]



def best_store_recommendations(offers, stores_by_id, target_ingredients, user_lat, user_lon):
    wanted = [normalize_text(item) for item in target_ingredients if str(item).strip()]
    if not wanted:
        return []

    by_store = {}

    for offer in offers:
        ingredient = normalize_text(offer.get("ingredient", ""))

        if not ingredient:
            continue

        is_match = any(ingredient in item or item in ingredient for item in wanted)

        if not is_match:
            continue

        store_id = offer.get("store_id", "")
        store = stores_by_id.get(store_id, {})

        if not store:
            continue

        price = parse_price(offer.get("price", None))

        if store_id not in by_store:
            distance = None

            if store.get("lat") and store.get("lon"):
                distance = haversine_km(user_lat, user_lon, store["lat"], store["lon"])

            by_store[store_id] = {
                "store": store,
                "distance": distance,
                "ingredients": set(),
                "offers": [],
                "total_price": 0.0,
                "priced_items": 0,
            }

        by_store[store_id]["ingredients"].add(ingredient)
        by_store[store_id]["offers"].append(offer)

        if price is not None:
            by_store[store_id]["total_price"] += price
            by_store[store_id]["priced_items"] += 1

    recommendations = []

    for store_id, data in by_store.items():
        covered = len(data["ingredients"])
        distance = data["distance"]
        total_price = data["total_price"]

        score = covered * 100
        score -= total_price
        if distance is not None:
            score -= distance * 2

        recommendations.append(
            {
                "store_id": store_id,
                "store": data["store"],
                "covered": covered,
                "ingredients": sorted(data["ingredients"]),
                "offers": data["offers"],
                "total_price": round(total_price, 2),
                "priced_items": data["priced_items"],
                "distance": round(distance, 1) if distance is not None else None,
                "score": score,
            }
        )

    recommendations.sort(
        key=lambda item: (
            -item["covered"],
            item["total_price"],
            item["distance"] if item["distance"] is not None else 999,
        )
    )

    return recommendations




@st.cache_data(ttl=86400)
def geocode_postcode(postcode, country="Italia"):
    clean_postcode = str(postcode).strip()

    if not clean_postcode:
        return None

    known_postcodes = {
        "53100": {
            "lat": 43.3188,
            "lon": 11.3308,
            "display_name": "53100 Siena, Toscana, Italia",
        }
    }

    if clean_postcode in known_postcodes:
        return known_postcodes[clean_postcode]

    queries = [
        {
            "postalcode": clean_postcode,
            "country": country,
            "format": "json",
            "limit": 1,
            "addressdetails": 1,
        },
        {
            "q": f"{clean_postcode}, {country}",
            "format": "json",
            "limit": 1,
            "addressdetails": 1,
        },
    ]

    for params in queries:
        try:
            response = requests.get(
                "https://nominatim.openstreetmap.org/search",
                params=params,
                headers={
                    "User-Agent": "SKiscettAI-demo/1.0 (Streamlit app; contact: demo)"
                },
                timeout=8,
            )

            if response.status_code != 200:
                continue

            data = response.json()

            if not data:
                continue

            result = data[0]

            return {
                "lat": float(result["lat"]),
                "lon": float(result["lon"]),
                "display_name": result.get("display_name", f"CAP {clean_postcode}"),
            }

        except Exception:
            continue

    return None



def stores_within_radius(stores, center_lat, center_lon, radius_km):
    nearby = []

    for store in stores:
        lat = store.get("lat")
        lon = store.get("lon")

        if lat is None or lon is None:
            continue

        distance = haversine_km(center_lat, center_lon, lat, lon)

        if distance <= radius_km:
            enriched_store = dict(store)
            enriched_store["distance_km"] = round(distance, 1)
            nearby.append(enriched_store)

    nearby.sort(key=lambda item: item.get("distance_km", 999))
    return nearby


def offers_for_stores(offers, stores):
    allowed_store_ids = {store.get("id") for store in stores}

    return [
        offer for offer in offers
        if offer.get("store_id") in allowed_store_ids
    ]


def text_for_chain_matching(*values):
    parts = []

    for value in values:
        if value:
            parts.append(str(value).replace("_", " ").replace("-", " "))

    return " ".join(parts)


def infer_offer_chain(offer, stores_by_id, offer_sources):
    store = stores_by_id.get(offer.get("store_id", ""), {})

    candidate_text = text_for_chain_matching(
        offer.get("store_id", ""),
        offer.get("source", ""),
        offer.get("notes", ""),
        store.get("name", ""),
        store.get("chain", ""),
        store.get("type", ""),
    )

    return normalize_chain_name(candidate_text, offer_sources)


def infer_store_chain(store, offer_sources):
    candidate_text = text_for_chain_matching(
        store.get("chain_normalized", ""),
        store.get("chain", ""),
        store.get("brand", ""),
        store.get("name", ""),
        store.get("id", ""),
    )

    return normalize_chain_name(candidate_text, offer_sources)


def offers_for_nearby_context(offers, nearby_stores, stores_by_id, offer_sources):
    nearby_store_ids = {store.get("id") for store in nearby_stores}

    nearby_chains = set()

    for store in nearby_stores:
        chain = infer_store_chain(store, offer_sources)
        if chain:
            nearby_chains.add(normalize_text(chain))

    matched = []

    for offer in offers:
        store_id = offer.get("store_id", "")

        if store_id in nearby_store_ids:
            matched.append(offer)
            continue

        offer_chain = infer_offer_chain(offer, stores_by_id, offer_sources)

        if normalize_text(offer_chain) in nearby_chains:
            matched.append(offer)

    return matched


def chain_match_summary(offers, nearby_stores, stores_by_id, offer_sources):
    nearby_chains = sorted(
        set(
            infer_store_chain(store, offer_sources)
            for store in nearby_stores
            if infer_store_chain(store, offer_sources)
        )
    )

    offer_chains = sorted(
        set(
            infer_offer_chain(offer, stores_by_id, offer_sources)
            for offer in offers
            if infer_offer_chain(offer, stores_by_id, offer_sources)
        )
    )

    common = sorted(
        set(normalize_text(chain) for chain in nearby_chains)
        & set(normalize_text(chain) for chain in offer_chains)
    )

    return nearby_chains, offer_chains, common




def validate_offers(offers, stores_by_id):
    required_fields = [
        "id",
        "store_id",
        "ingredient",
        "product_name",
        "price",
        "unit",
        "old_price",
        "valid_from",
        "valid_until",
        "source",
        "category",
        "notes",
    ]

    issues = []

    for index, offer in enumerate(offers, start=1):
        row_label = offer.get("id", f"riga {index}")

        for field in required_fields:
            if field not in offer or str(offer.get(field, "")).strip() == "":
                issues.append(
                    {
                        "offerta": row_label,
                        "campo": field,
                        "problema": "Campo mancante o vuoto",
                    }
                )

        store_id = offer.get("store_id", "")
        if store_id and store_id not in stores_by_id:
            issues.append(
                {
                    "offerta": row_label,
                    "campo": "store_id",
                    "problema": f"Negozio non trovato in stores.json: {store_id}",
                }
            )

        price = parse_price(offer.get("price", None))
        if price is None:
            issues.append(
                {
                    "offerta": row_label,
                    "campo": "price",
                    "problema": "Prezzo non numerico",
                }
            )

    return issues


def offers_template_text():
    return (
        "id,store_id,ingredient,product_name,price,unit,old_price,valid_from,valid_until,source,category,notes\n"
        "off_001,centro_siena_coop,pollo,Petto di pollo a fette,8.90,€/kg,10.90,2026-05-27,2026-06-03,volantino demo,proteine,Offerta da verificare\n"
        "off_002,pam_rosselli,riso basmati,Riso basmati 1 kg,2.29,pezzo,3.10,2026-05-27,2026-06-03,volantino demo,cereali,Offerta da verificare\n"
        "off_003,penny_massetana,ceci,Ceci lessati 3x400 g,1.99,conf.,2.59,2026-05-27,2026-06-03,volantino demo,legumi,Offerta da verificare\n"
    )


def offers_to_csv_text(offers):
    if not offers:
        return offers_template_text()

    rows = pd.DataFrame(offers)
    return rows.to_csv(index=False)




def source_lookup(offer_sources):
    lookup = {}

    if not isinstance(offer_sources, list):
        return lookup

    for source in offer_sources:
        chain = source.get("chain", "")
        aliases = source.get("aliases", [])

        if chain:
            lookup[normalize_text(chain)] = source

        for alias in aliases:
            lookup[normalize_text(alias)] = source

    return lookup


def normalize_chain_name(name, offer_sources):
    text_name = normalize_text(name)

    if not text_name:
        return "Altro"

    for source in offer_sources:
        chain = source.get("chain", "")
        aliases = source.get("aliases", [])

        candidates = [chain] + aliases

        for candidate in candidates:
            candidate_norm = normalize_text(candidate)
            if candidate_norm and candidate_norm in text_name:
                return chain

    known = {
        "coop": "Coop",
        "conad": "Conad",
        "penny": "PENNY",
        "pam": "PAM",
        "lidl": "Lidl",
        "eurospin": "Eurospin",
        "esselunga": "Esselunga",
        "carrefour": "Carrefour",
        "md": "MD",
        "aldi": "ALDI",
    }

    for key, value in known.items():
        if key in text_name:
            return value

    return name.strip().title()


@st.cache_data(ttl=3600)
def fetch_osm_supermarkets(lat, lon, radius_km):
    radius_m = int(radius_km * 1000)

    query = f"""
    [out:json][timeout:25];
    (
      node["shop"~"supermarket|convenience|greengrocer|grocery|mall"](around:{radius_m},{lat},{lon});
      way["shop"~"supermarket|convenience|greengrocer|grocery|mall"](around:{radius_m},{lat},{lon});
      relation["shop"~"supermarket|convenience|greengrocer|grocery|mall"](around:{radius_m},{lat},{lon});
    );
    out center tags;
    """

    response = requests.post(
        "https://overpass-api.de/api/interpreter",
        data={"data": query},
        headers={"User-Agent": "SKiscettAI-demo/1.0"},
        timeout=25,
    )

    if response.status_code != 200:
        raise RuntimeError(f"Overpass status code {response.status_code}")

    data = response.json()
    stores = []

    for element in data.get("elements", []):
        tags = element.get("tags", {})

        lat_value = element.get("lat")
        lon_value = element.get("lon")

        if lat_value is None or lon_value is None:
            center = element.get("center", {})
            lat_value = center.get("lat")
            lon_value = center.get("lon")

        if lat_value is None or lon_value is None:
            continue

        name = tags.get("name", "Punto vendita")
        brand = tags.get("brand", "")
        chain_name = brand or name

        store_id = "osm_" + str(element.get("type", "node")) + "_" + str(element.get("id", ""))

        street = tags.get("addr:street", "")
        housenumber = tags.get("addr:housenumber", "")
        city = tags.get("addr:city", "")
        address_parts = [part for part in [street, housenumber, city] if part]
        address = " ".join(address_parts)

        stores.append(
            {
                "id": store_id,
                "name": name,
                "chain": chain_name,
                "type": tags.get("shop", "supermarket"),
                "address": address,
                "lat": float(lat_value),
                "lon": float(lon_value),
                "area": city or "zona cercata",
                "source": "OpenStreetMap",
                "osm_type": element.get("type", ""),
                "osm_id": element.get("id", ""),
                "notes": "Punto vendita trovato automaticamente da OpenStreetMap/Overpass.",
            }
        )

    return stores


def enrich_discovered_stores(stores, offer_sources, user_lat, user_lon):
    enriched = []

    for store in stores:
        item = dict(store)
        chain = normalize_chain_name(
            item.get("chain") or item.get("name", ""),
            offer_sources,
        )
        item["chain_normalized"] = chain

        lat = item.get("lat")
        lon = item.get("lon")

        if lat is not None and lon is not None:
            item["distance_km"] = round(haversine_km(user_lat, user_lon, lat, lon), 1)

        source = get_offer_source_for_chain(chain, offer_sources)
        item["offer_source_status"] = source.get("status", "not_configured") if source else "not_configured"
        item["offer_source_url"] = source.get("url", "") if source else ""

        enriched.append(item)

    enriched.sort(key=lambda store: store.get("distance_km", 999))
    return enriched


def get_offer_source_for_chain(chain, offer_sources):
    chain_norm = normalize_text(chain)

    for source in offer_sources:
        if normalize_text(source.get("chain", "")) == chain_norm:
            return source

        for alias in source.get("aliases", []):
            if normalize_text(alias) == chain_norm:
                return source

    return {}


def offer_sources_for_stores(stores, offer_sources):
    chains = sorted(set(store.get("chain_normalized", store.get("chain", "")) for store in stores))
    rows = []

    for chain in chains:
        source = get_offer_source_for_chain(chain, offer_sources)

        rows.append(
            {
                "catena": chain,
                "stato": source.get("status", "not_configured") if source else "not_configured",
                "modalità": source.get("mode", "da configurare") if source else "da configurare",
                "fonte": source.get("url", "") if source else "",
                "note": source.get("notes", "Fonte offerte non ancora collegata.") if source else "Fonte offerte non ancora collegata.",
            }
        )

    return rows


def merge_discovered_and_manual_stores(discovered_stores, manual_stores, user_lat, user_lon, radius_km):
    if discovered_stores:
        return discovered_stores, "OpenStreetMap"

    nearby_manual = stores_within_radius(
        manual_stores,
        user_lat,
        user_lon,
        radius_km,
    )

    if nearby_manual:
        return nearby_manual, "Fallback web"

    return manual_stores, "Fallback web completo"




def fetch_offer_source_preview(url):
    return {
        "status": "parser_pending",
        "ok": False,
        "message": "Fonte predisposta. Parser dedicato da collegare nello step successivo.",
        "matches": [],
    }


def web_sources_for_nearby_chains(nearby_stores, offer_sources):
    chains = sorted(
        set(
            infer_store_chain(store, offer_sources)
            for store in nearby_stores
            if infer_store_chain(store, offer_sources)
        )
    )

    rows = []

    for chain in chains:
        source = get_offer_source_for_chain(chain, offer_sources)

        if not source:
            rows.append(
                {
                    "catena": chain,
                    "stato": "not_configured",
                    "fonte": "",
                    "prossimo_step": "Fonte da configurare",
                    "note": "Catena trovata nel raggio ma non ancora mappata.",
                }
            )
            continue

        rows.append(
            {
                "catena": chain,
                "stato": source.get("status", "source_available"),
                "fonte": source.get("url", ""),
                "prossimo_step": "Parser dedicato",
                "note": source.get("notes", ""),
            }
        )

    return rows


def web_offer_preview_cards(nearby_stores, offer_sources):
    chains = sorted(
        set(
            infer_store_chain(store, offer_sources)
            for store in nearby_stores
            if infer_store_chain(store, offer_sources)
        )
    )

    cards = []

    for chain in chains:
        source = get_offer_source_for_chain(chain, offer_sources)

        if not source:
            cards.append(
                {
                    "chain": chain,
                    "source": {
                        "url": "",
                        "status": "not_configured",
                        "notes": "Fonte da configurare.",
                    },
                    "preview": fetch_offer_source_preview(""),
                }
            )
            continue

        cards.append(
            {
                "chain": chain,
                "source": source,
                "preview": fetch_offer_source_preview(source.get("url", "")),
            }
        )

    return cards



# =========================================================
# Offer Engine v1
# =========================================================

def safe_text(value):
    return str(value or "").strip()


def normalize_for_match(value):
    text = normalize_text(value)
    text = re.sub(r"[^a-z0-9àèéìòùç\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def offer_source_status_label(status):
    labels = {
        "manual_active": "Offerte web attive",
        "source_mapped": "Fonte web mappata",
        "source_mapped_dynamic": "Fonte web dinamica",
        "parser_ready": "Parser pronto",
        "parser_pending": "Parser da collegare",
        "not_configured": "Fonte non configurata",
    }

    return labels.get(status, status or "Fonte non configurata")


def infer_chain_from_text(value, offer_sources):
    candidate = normalize_for_match(value)

    if not candidate:
        return "Altro"

    for source in offer_sources:
        chain = source.get("chain", "")
        aliases = source.get("aliases", [])
        candidates = [chain] + aliases

        for alias in candidates:
            alias_norm = normalize_for_match(alias)
            if alias_norm and alias_norm in candidate:
                return chain

    known = {
        "penny": "PENNY",
        "penny market": "PENNY",
        "coop": "Coop",
        "unicoop": "Coop",
        "conad": "Conad",
        "pam": "PAM",
        "panorama": "PAM",
        "lidl": "Lidl",
        "eurospin": "Eurospin",
        "esselunga": "Esselunga",
        "carrefour": "Carrefour",
        "md": "MD",
        "aldi": "ALDI",
        "despar": "Spar",
        "interspar": "Spar",
        "cra": "CRA",
    }

    for key, chain in known.items():
        if key in candidate:
            return chain

    return "Altro"



def infer_store_chain_v2(store, offer_sources):
    fields = [
        store.get("chain_normalized", ""),
        store.get("chain", ""),
        store.get("brand", ""),
        store.get("operator", ""),
        store.get("name", ""),
        store.get("id", ""),
    ]

    return infer_chain_from_text(" ".join(safe_text(field) for field in fields), offer_sources)


def infer_offer_chain_v2(offer, stores_by_id, offer_sources):
    store = stores_by_id.get(offer.get("store_id", ""), {})

    fields = [
        offer.get("chain", ""),
        offer.get("store_id", ""),
        offer.get("source", ""),
        offer.get("notes", ""),
        store.get("chain", ""),
        store.get("name", ""),
        store.get("id", ""),
    ]

    return infer_chain_from_text(" ".join(safe_text(field) for field in fields), offer_sources)


def get_offer_source_for_chain_v2(chain, offer_sources):
    chain_norm = normalize_for_match(chain)

    for source in offer_sources:
        if normalize_for_match(source.get("chain", "")) == chain_norm:
            return source

        for alias in source.get("aliases", []):
            if normalize_for_match(alias) == chain_norm:
                return source

    return {
        "chain": chain,
        "status": "not_configured",
        "mode": "not_configured",
        "url": "",
        "notes": "Fonte offerte non ancora configurata.",
    }


def classify_manual_offers(offers, stores_by_id, offer_sources):
    classified = []

    for offer in offers:
        item = dict(offer)
        item["chain_inferred"] = infer_offer_chain_v2(offer, stores_by_id, offer_sources)
        item["offer_origin"] = offer.get("origin", offer.get("offer_origin", "manual"))
        classified.append(item)

    return classified


def build_offer_engine_state(
    offers,
    nearby_stores,
    stores_by_id,
    offer_sources,
    selected_ingredients=None,
):
    selected_ingredients = selected_ingredients or []
    manual_offers = classify_manual_offers(offers, stores_by_id, offer_sources)

    nearby_chains = sorted(
        set(
            infer_store_chain_v2(store, offer_sources)
            for store in nearby_stores
            if infer_store_chain_v2(store, offer_sources)
            and infer_store_chain_v2(store, offer_sources) != "Altro"
        )
    )

    manual_offer_chains = sorted(
        set(
            offer.get("chain_inferred", "Altro")
            for offer in manual_offers
            if offer.get("chain_inferred")
            and offer.get("chain_inferred") != "Altro"
        )
    )

    nearby_chain_keys = {normalize_for_match(chain) for chain in nearby_chains}
    selected_offer_pool = []

    for offer in manual_offers:
        chain_key = normalize_for_match(offer.get("chain_inferred", ""))

        if chain_key in nearby_chain_keys:
            selected_offer_pool.append(offer)

    if not selected_offer_pool and manual_offers:
        selected_offer_pool = manual_offers

    if selected_ingredients:
        matched_by_ingredient = offers_for_ingredients(selected_offer_pool, selected_ingredients)
    else:
        matched_by_ingredient = selected_offer_pool

    missing_chain_rows = []

    for chain in nearby_chains:
        source = get_offer_source_for_chain_v2(chain, offer_sources)
        has_manual_offers = normalize_for_match(chain) in {
            normalize_for_match(item) for item in manual_offer_chains
        }

        if has_manual_offers:
            status = "manual_active"
            reason = "Sono presenti offerte web/web per questa catena."
        else:
            status = source.get("status", "not_configured")
            reason = source.get(
                "notes",
                "Fonte web non ancora collegata con parser dedicato.",
            )

        missing_chain_rows.append(
            {
                "catena": chain,
                "stato": offer_source_status_label(status),
                "offerte_web": "sì" if has_manual_offers else "no",
                "fonte_web": source.get("url", ""),
                "prossimo_step": "parser dedicato" if not has_manual_offers else "monitoraggio offerte",
                "nota": reason,
            }
        )

    return {
        "manual_offers": manual_offers,
        "nearby_chains": nearby_chains,
        "manual_offer_chains": manual_offer_chains,
        "offers_nearby": selected_offer_pool,
        "matched_offers": matched_by_ingredient,
        "offers_to_show": matched_by_ingredient if matched_by_ingredient else selected_offer_pool,
        "missing_chain_rows": missing_chain_rows,
    }


def offer_engine_summary_cards(engine_state, nearby_stores):
    return {
        "stores": len(nearby_stores),
        "nearby_chains": len(engine_state.get("nearby_chains", [])),
        "manual_offers": len(engine_state.get("manual_offers", [])),
        "visible_offers": len(engine_state.get("offers_to_show", [])),
    }


def offer_engine_explanation(engine_state):
    nearby = engine_state.get("nearby_chains", [])
    offer_chains = engine_state.get("manual_offer_chains", [])

    if not nearby:
        return "Non ho trovato catene nel raggio selezionato."

    if not offer_chains:
        return (
            "Ho trovato supermercati nel raggio, ma non ci sono ancora offerte web "
            "caricate per quelle catene."
        )

    common = sorted(
        set(normalize_for_match(chain) for chain in nearby)
        & set(normalize_for_match(chain) for chain in offer_chains)
    )

    if common:
        return "Ho trovato catene nel raggio con offerte web disponibili."

    return (
        "Le offerte web sono caricate, ma appartengono a catene diverse da quelle "
        "trovate nel raggio. Mostro comunque le offerte come fallback."
    )


def create_stores_map(stores, offers, center_lat=43.3188, center_lon=11.3308):
    if not MAP_AVAILABLE:
        return None

    store_offer_counts = Counter(offer.get("store_id", "") for offer in offers)

    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=13,
        tiles="OpenStreetMap",
    )

    folium.Marker(
        [center_lat, center_lon],
        popup="Centro Siena",
        tooltip="Centro Siena",
        icon=folium.Icon(color="green", icon="home"),
    ).add_to(m)

    for store in stores:
        lat = store.get("lat")
        lon = store.get("lon")

        if lat is None or lon is None:
            continue

        count = store_offer_counts.get(store.get("id", ""), 0)

        popup_html = f"""
        <b>{store.get('name', '')}</b><br>
        {store.get('type', '')}<br>
        {store.get('address', '')}<br>
        Offerte demo collegate: {count}
        """

        folium.Marker(
            [lat, lon],
            popup=popup_html,
            tooltip=store.get("name", ""),
            icon=folium.Icon(color="cadetblue", icon="shopping-cart", prefix="fa"),
        ).add_to(m)

    return m



def ingredient_lookup(ingredients):
    lookup = {}
    for ingredient in ingredients:
        name = normalize_text(ingredient.get("name", ""))
        if name:
            lookup[name] = ingredient
    return lookup


def recipe_goal_counts(recipe_list):
    return Counter(recipe.get("goal", "Altro") for recipe in recipe_list)


def recipes_by_cluster(recipe_list):
    grouped = {}
    for recipe in recipe_list:
        cluster = recipe.get("image_cluster", "smart")
        grouped.setdefault(cluster, []).append(recipe)
    return grouped


def get_cluster_visual(recipe):
    cluster = recipe.get("image_cluster", "")
    return CLUSTER_VISUALS.get(
        cluster,
        {
            "emoji": "🍽️",
            "title": recipe.get("category", "SKiscetta smart"),
            "subtitle": "Ricetta pratica, buona e facile da portare",
        },
    )


def get_module_options(modules, key):
    if isinstance(modules, dict):
        return modules.get(key, [])
    return []


def score_module(option, user_words, goal):
    name = normalize_text(option.get("name", ""))
    good_for = [normalize_text(item) for item in option.get("good_for", [])]
    score = 0

    for word in user_words:
        if word and word in name:
            score += 10
        elif word and name in word:
            score += 8

    if normalize_text(goal) in good_for:
        score += 5

    return score


def pick_module(options, user_words, goal, vegetarian_only=False):
    candidates = options

    if vegetarian_only:
        candidates = [
            item for item in options
            if normalize_text(item.get("type", "")) not in ["animale", "pesce"]
        ]

    if not candidates:
        candidates = options

    scored = [
        (score_module(item, user_words, goal), index, item)
        for index, item in enumerate(candidates)
    ]

    scored.sort(key=lambda item: (item[0], -item[1]), reverse=True)

    if scored:
        return scored[0][2]

    return {}


def pick_style(styles, goal):
    goal_norm = normalize_text(goal)

    for style in styles:
        if normalize_text(style.get("name", "")) == goal_norm:
            return style
        if normalize_text(style.get("id", "")) == goal_norm:
            return style

    if styles:
        return styles[0]

    return {
        "id": "smart",
        "name": "smart",
        "title_template": "SKiscetta smart con {base}, {protein} e {vegetable}",
        "description": "Una SKiscetta semplice, pratica e pensata per la pausa pranzo.",
    }


def estimate_nutrition(base, protein, vegetable, style_name):
    calories = 460
    protein_value = 24
    carbs = 55
    fat = 14

    protein_name = normalize_text(protein.get("name", ""))

    if protein_name in ["pollo", "tonno"]:
        protein_value += 10
        calories += 40

    if protein_name in ["ceci", "tofu"]:
        protein_value += 4
        fat += 3

    if normalize_text(style_name) == "light":
        calories -= 70
        fat -= 3

    if normalize_text(style_name) == "gourmet":
        calories += 60
        fat += 5

    if normalize_text(style_name) == "economica":
        calories -= 20

    return {
        "calories": max(calories, 300),
        "protein": max(protein_value, 12),
        "carbs": max(carbs, 25),
        "fat": max(fat, 7),
    }


def choose_cluster(base, protein, style):
    base_name = normalize_text(base.get("name", ""))
    protein_name = normalize_text(protein.get("name", ""))
    style_name = normalize_text(style.get("name", ""))

    if "pasta" in base_name:
        return "pasta_fredda"

    if "couscous" in base_name:
        return "couscous_verdure"

    if protein_name in ["ceci", "tofu"]:
        return "vegetariana_legumi"

    if protein_name == "pollo":
        return "riso_pollo"

    if style_name == "gourmet":
        return "gourmet_light"

    if style_name == "light":
        return "insalata_proteica"

    return "bowl_mediterranea"


def generate_modular_recipe(modules, user_ingredients, goal, max_time, preferences=""):
    if not isinstance(modules, dict) or not modules:
        return None

    user_words = [
        normalize_text(word)
        for word in user_ingredients.replace(";", ",").split(",")
        if word.strip()
    ]

    preference_words = [
        normalize_text(word)
        for word in preferences.replace(";", ",").split(",")
        if word.strip()
    ]

    all_words = user_words + preference_words

    bases = get_module_options(modules, "bases")
    proteins = get_module_options(modules, "proteins")
    vegetables = get_module_options(modules, "vegetables")
    sauces = get_module_options(modules, "sauces")
    toppings = get_module_options(modules, "toppings")
    styles = get_module_options(modules, "styles")

    vegetarian_only = normalize_text(goal) == "vegetariana"

    base = pick_module(bases, all_words, goal)
    protein = pick_module(proteins, all_words, goal, vegetarian_only=vegetarian_only)
    vegetable = pick_module(vegetables, all_words, goal)
    sauce = pick_module(sauces, all_words, goal)
    topping = pick_module(toppings, all_words, goal)
    style = pick_style(styles, goal)

    if not base or not protein or not vegetable:
        return None

    title_template = style.get(
        "title_template",
        "SKiscetta smart con {base}, {protein} e {vegetable}",
    )

    title = title_template.format(
        base=base.get("name", "base"),
        protein=protein.get("name", "proteina"),
        vegetable=vegetable.get("name", "verdura"),
    )

    style_name = style.get("name", goal)
    recipe_id = "modular_" + "_".join(
        [
            normalize_text(style_name).replace(" ", "_"),
            normalize_text(base.get("id", base.get("name", "base"))).replace(" ", "_"),
            normalize_text(protein.get("id", protein.get("name", "protein"))).replace(" ", "_"),
            normalize_text(vegetable.get("id", vegetable.get("name", "vegetable"))).replace(" ", "_"),
        ]
    )

    recipe = {
        "id": recipe_id,
        "title": title,
        "description": style.get(
            "description",
            "Una SKiscetta modulare, pratica e pensata per la pausa pranzo.",
        ),
        "category": "Ricetta modulare",
        "goal": goal,
        "prep_time": max_time,
        "difficulty": "Facile",
        "estimated_cost": "basso" if normalize_text(goal) == "economica" else "medio",
        "storage_info": "Si conserva 1-2 giorni in frigorifero in contenitore ermetico.",
        "transport_tip": "Tieni la salsa separata e aggiungila poco prima di mangiare.",
        "glamour_tip": f"Completa con {topping.get('name', 'un topping croccante')} per dare colore, texture e un effetto più curato.",
        "ingredients": [
            base.get("name", ""),
            protein.get("name", ""),
            vegetable.get("name", ""),
            sauce.get("name", ""),
            topping.get("name", ""),
        ],
        "steps": [
            f"Prepara la base: {base.get('prep_note', 'cuocila e lasciala raffreddare')}.",
            f"Prepara la proteina: {protein.get('prep_note', 'condiscila in modo semplice')}.",
            f"Aggiungi la verdura: {vegetable.get('prep_note', 'tagliala e aggiungila alla lunch box')}.",
            f"Completa con {sauce.get('name', 'una salsa leggera')}: {sauce.get('prep_note', 'meglio tenerla a parte')}.",
            f"Prima di chiudere, aggiungi {topping.get('name', 'un topping')}: effetto {topping.get('effect', 'più curato')}.",
        ],
        "nutrition": estimate_nutrition(base, protein, vegetable, style_name),
        "tags": [
            normalize_text(goal),
            "modulare",
            "svuota frigo",
            "facile da trasportare",
            "meal prep",
        ],
        "image_cluster": choose_cluster(base, protein, style),
        "is_modular": True,
    }

    return recipe


def upsert_custom_recipe(recipe):
    if not recipe:
        return

    existing_ids = [item.get("id") for item in st.session_state.custom_recipes]
    if recipe.get("id") not in existing_ids:
        st.session_state.custom_recipes.append(recipe)


def find_best_recipes(recipes, user_ingredients, goal, max_time, preferences=""):
    user_words = [
        normalize_text(word)
        for word in user_ingredients.replace(";", ",").split(",")
        if word.strip()
    ]

    preference_words = [
        normalize_text(word)
        for word in preferences.replace(";", ",").split(",")
        if word.strip()
    ]

    max_minutes = parse_minutes(max_time)
    scored = []

    for recipe in recipes:
        score = 0

        recipe_ingredients = normalize_text(" ".join(recipe.get("ingredients", [])))
        recipe_goal = normalize_text(recipe.get("goal", ""))
        recipe_tags = normalize_text(" ".join(recipe.get("tags", [])))
        recipe_title = normalize_text(recipe.get("title", ""))
        recipe_description = normalize_text(recipe.get("description", ""))
        recipe_minutes = parse_minutes(recipe.get("prep_time", ""))

        for word in user_words:
            if word and word in recipe_ingredients:
                score += 5
            if word and word in recipe_title:
                score += 3
            if word and word in recipe_tags:
                score += 2
            if word and word in recipe_description:
                score += 1

        for word in preference_words:
            if word and word in recipe_tags:
                score += 2
            if word and word in recipe_description:
                score += 1
            if word and word in recipe_title:
                score += 1

        if normalize_text(goal) in recipe_goal:
            score += 5

        if recipe_minutes <= max_minutes:
            score += 2

        if normalize_text(goal) in recipe_tags:
            score += 2

        scored.append((score, recipe))

    scored.sort(key=lambda item: item[0], reverse=True)
    best = [item[1] for item in scored if item[0] > 0]

    if best:
        return best[:3]

    return recipes[:3]


def filter_recipes(recipes, text_query, goal_filter, tag_filter, max_time_filter, cluster_filter):
    results = []

    query = normalize_text(text_query)
    max_minutes = parse_minutes(max_time_filter) if max_time_filter != "Qualsiasi" else 999

    for recipe in recipes:
        title = normalize_text(recipe.get("title", ""))
        description = normalize_text(recipe.get("description", ""))
        goal = normalize_text(recipe.get("goal", ""))
        tags = [normalize_text(tag) for tag in recipe.get("tags", [])]
        ingredients = normalize_text(" ".join(recipe.get("ingredients", [])))
        prep_minutes = parse_minutes(recipe.get("prep_time", ""))
        cluster = recipe.get("image_cluster", "smart")

        match_query = (
            not query
            or query in title
            or query in description
            or query in ingredients
            or any(query in tag for tag in tags)
        )

        match_goal = goal_filter == "Tutte" or normalize_text(goal_filter) == goal
        match_tag = tag_filter == "Tutti" or normalize_text(tag_filter) in tags
        match_time = prep_minutes <= max_minutes
        match_cluster = cluster_filter == "Tutti" or cluster_filter == cluster

        if match_query and match_goal and match_tag and match_time and match_cluster:
            results.append(recipe)

    return results


def cluster_tile(cluster_id, recipes_count=None):
    visual = CLUSTER_VISUALS.get(
        cluster_id,
        {
            "emoji": "🍽️",
            "title": "SKiscetta smart",
            "subtitle": "Idee pratiche per la pausa pranzo",
        },
    )

    with st.container(border=True):
        st.markdown(f"## {visual['emoji']}")
        st.markdown(f"### {visual['title']}")
        st.write(visual["subtitle"])
        if visual.get("mood"):
            st.caption(f"Mood: {visual['mood']}")
        if recipes_count is not None:
            st.caption(f"{recipes_count} ricette disponibili")


def compact_recipe_preview(recipe, key_prefix):
    visual = get_cluster_visual(recipe)

    with st.container(border=True):
        st.markdown(f"## {visual['emoji']}")
        st.markdown(f"### {recipe.get('title', 'Ricetta')}")
        st.write(recipe.get("description", ""))
        st.caption(
            f"{visual['title']} · {recipe.get('goal', '-')} · {recipe.get('prep_time', '-')}"
        )

        if st.button("Salva", key=f"{key_prefix}_save_{recipe['id']}"):
            save_favorite(recipe["id"])


def recipe_card(recipe, key_prefix, show_save=True, show_remove=False):
    visual = get_cluster_visual(recipe)

    with st.container(border=True):
        visual_col, content_col = st.columns([1, 3])

        with visual_col:
            st.markdown(f"# {visual['emoji']}")
            st.markdown(f"**{visual['title']}**")
            st.caption(visual["subtitle"])
            if recipe.get("is_modular"):
                st.caption("Ricetta modulare originale")

        with content_col:
            top_col, action_col = st.columns([4, 1])

            with top_col:
                st.subheader(recipe.get("title", "Ricetta"))
                st.write(recipe.get("description", ""))

            with action_col:
                if show_save:
                    if st.button("Salva", key=f"{key_prefix}_save_{recipe['id']}"):
                        save_favorite(recipe["id"])

                if show_remove:
                    if st.button("Rimuovi", key=f"{key_prefix}_remove_{recipe['id']}"):
                        remove_favorite(recipe["id"])
                        st.rerun()

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Obiettivo", recipe.get("goal", "-"))

        with col2:
            st.metric("Tempo", recipe.get("prep_time", "-"))

        with col3:
            st.metric("Difficoltà", recipe.get("difficulty", "-"))

        with col4:
            st.metric("Costo", recipe.get("estimated_cost", "-"))

        st.markdown("### Ingredienti")
        ingredients = recipe.get("ingredients", [])
        st.write(", ".join(ingredients) if ingredients else "-")

        with st.expander("Vedi procedimento"):
            steps = recipe.get("steps", [])
            if steps:
                for index, step in enumerate(steps, start=1):
                    st.write(f"{index}. {step}")
            else:
                st.write("-")

        nutrition = recipe.get("nutrition", {})
        n1, n2, n3, n4 = st.columns(4)

        with n1:
            st.metric("Kcal", nutrition.get("calories", "-"))

        with n2:
            st.metric("Proteine", f"{nutrition.get('protein', '-')} g")

        with n3:
            st.metric("Carboidrati", f"{nutrition.get('carbs', '-')} g")

        with n4:
            st.metric("Grassi", f"{nutrition.get('fat', '-')} g")

        with st.expander("Consigli trasporto e conservazione"):
            st.write(f"**Trasporto:** {recipe.get('transport_tip', '-')}")
            st.write(f"**Consiglio glamour:** {recipe.get('glamour_tip', '-')}")
            st.write(f"**Conservazione:** {recipe.get('storage_info', '-')}")

        tags = recipe.get("tags", [])
        if tags:
            st.caption(" · ".join(tags))


load_css("styles/custom.css")

recipes = load_json("data/recipes.json")
categories = load_json("data/categories.json")
tags = load_json("data/tags.json")
ingredients_data = load_json("data/ingredients.json")
modules = load_json("data/modules.json")
clusters_data = load_json("data/clusters.json")
stores_data = load_json("data/stores.json")
offer_sources_data = load_json("data/offer_sources.json")
offers_data = []  # SKAI web-only mode: manual offers disabled in the main flow

if clusters_data:
    CLUSTER_VISUALS.update(build_cluster_visuals(clusters_data))

ingredients_by_name = ingredient_lookup(ingredients_data)
stores_by_id = store_lookup(stores_data)

if "favorites" not in st.session_state:
    st.session_state.favorites = []

if "custom_recipes" not in st.session_state:
    st.session_state.custom_recipes = []

if "generated_recipe_ids" not in st.session_state:
    st.session_state.generated_recipe_ids = []

if "page" not in st.session_state:
    st.session_state.page = "Home"

if "extra_shopping_items" not in st.session_state:
    st.session_state.extra_shopping_items = []

for day in WORK_DAYS:
    key = f"meal_{day}"
    if key not in st.session_state:
        st.session_state[key] = "Nessuna ricetta"


all_recipes = combined_recipes()
cluster_groups = recipes_by_cluster(all_recipes)

pages = [
    "Home",
    "Crea SKiscetta",
    "SKAI Radar",
    "Ricette",
    "Lista spesa",
    "Meal plan",
    "Preferiti",
]

st.sidebar.markdown(
    """
    <div class="skai-sidebar-brand">
        <div class="skai-sidebar-icon">⚡🍱</div>
        <div class="skai-sidebar-main">SKAI</div>
        <div class="skai-sidebar-sub">SKiscettAI</div>
    </div>
    """,
    unsafe_allow_html=True,
)

selected_page = st.sidebar.radio(
    "Menu",
    pages,
    index=pages.index(st.session_state.page),
)

st.session_state.page = selected_page

st.sidebar.divider()
st.sidebar.caption("Smart lunch planner")
st.sidebar.caption("SKAI · web-only parser")
st.sidebar.caption("Radar offerte live")
st.sidebar.caption(f"Ricette modulari create: {len(st.session_state.custom_recipes)}")


st.markdown(
    """
    <section class="skai-hero skai-black-hero">
        <div class="skai-orb skai-orb-a"></div>
        <div class="skai-orb skai-orb-b"></div>
        <div class="skai-hero-kicker">SKAI · Smart Kitchen Artificial Intelligence</div>
        <div class="skai-hero-title">SKiscettAI</div>
        <div class="skai-hero-subtitle">Il sistema operativo futuristico per pranzi smart, supermercati vicini e offerte web.</div>
        <div class="skai-hero-pills">
            <span>⚡ web-only radar</span>
            <span>🗺️ map-first</span>
            <span>🥗 recipe intelligence</span>
            <span>💸 deal engine</span>
            <span>✨ black label UI</span>
        </div>
    </section>
    """,
    unsafe_allow_html=True,
)

st.divider()




if st.session_state.page == "Home":
    render_skai_section_label(
        "Command Center",
        "La tua cucina, in modalità autopilot.",
        "Un unico spazio per ricette, meal prep, radar supermercati e offerte web."
    )

    stat1, stat2, stat3, stat4 = st.columns(4)

    with stat1:
        st.metric("Ricette", len(all_recipes))

    with stat2:
        st.metric("Preferiti", len(st.session_state.favorites))

    with stat3:
        planned_count = len(get_meal_plan_recipes(all_recipes))
        st.metric("Meal plan", planned_count)

    with stat4:
        st.metric("SKiscette create", len(st.session_state.custom_recipes))

    st.markdown(
        """
        <div class="skai-black-strip">
            <div>
                <span class="skai-strip-number">01</span>
                <strong>Crea</strong>
                <p>Trasforma ingredienti casuali in una SKiscetta pronta.</p>
            </div>
            <div>
                <span class="skai-strip-number">02</span>
                <strong>Radar</strong>
                <p>Leggi supermercati nel raggio e offerte web disponibili.</p>
            </div>
            <div>
                <span class="skai-strip-number">03</span>
                <strong>Ottimizza</strong>
                <p>Combina tempo, costo, ricette e lista spesa.</p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.write("")

    action_col1, action_col2, action_col3 = st.columns(3)

    with action_col1:
        with st.container(border=True):
            st.markdown("### 🥗 Crea SKiscetta")
            st.write("Genera una ricetta partendo da quello che hai in casa.")
            if st.button("Avvia generatore", key="home_create_skiscetta"):
                go_to("Crea SKiscetta")
                st.rerun()

    with action_col2:
        with st.container(border=True):
            st.markdown("### 🗺️ SKAI Radar")
            st.write("Mappa, supermercati e offerte web, tutto in una vista.")
            if st.button("Apri Radar", key="home_open_radar"):
                go_to("SKAI Radar")
                st.rerun()

    with action_col3:
        with st.container(border=True):
            st.markdown("### ✨ Esplora")
            st.write("Filtra ricette, salva preferiti e prepara la settimana.")
            if st.button("Esplora ricette", key="home_open_recipes"):
                go_to("Ricette")
                st.rerun()

    st.write("")
    render_skai_section_label(
        "Mood Engine",
        "Scegli il mood, SKAI trova la direzione.",
        "Cluster ricette pensati per ufficio, palestra, low cost e meal prep."
    )

    current_clusters = recipes_by_cluster(all_recipes)
    cluster_items = list(current_clusters.items())[:6]

    mood_cols = st.columns(3)

    for index, (cluster_id, recipes_in_cluster) in enumerate(cluster_items):
        visual = CLUSTER_VISUALS.get(
            cluster_id,
            {
                "emoji": "🍱",
                "title": cluster_id.replace("_", " ").title(),
                "subtitle": "Ricette smart e pronte da portare.",
            },
        )

        with mood_cols[index % 3]:
            with st.container(border=True):
                st.markdown(f"<div class='skai-mood-emoji'>{visual['emoji']}</div>", unsafe_allow_html=True)
                st.markdown(f"### {visual['title']}")
                st.write(visual["subtitle"])
                st.caption(f"{len(recipes_in_cluster)} ricette disponibili")

    st.write("")
    render_skai_section_label(
        "Featured",
        "Tre idee per partire subito.",
        "Ricette selezionate per testare velocemente il flusso SKAI."
    )

    featured = all_recipes[:3]
    featured_cols = st.columns(3)

    for index, recipe in enumerate(featured):
        with featured_cols[index % 3]:
            with st.container(border=True):
                cluster_id = recipe.get("cluster", "")
                visual = CLUSTER_VISUALS.get(cluster_id, {"emoji": "🍱"})
                st.markdown(f"<div class='skai-mood-emoji'>{visual['emoji']}</div>", unsafe_allow_html=True)
                st.markdown(f"### {recipe.get('title', 'Ricetta')}")
                st.write(recipe.get("description", ""))
                meta = recipe.get("meta", {})
                st.caption(
                    f"{meta.get('goal', 'smart')} · {meta.get('time', '')} · {meta.get('difficulty', '')}"
                )
                if st.button("Apri", key=f"featured_open_{recipe['id']}"):
                    st.session_state.recipe_focus = recipe["id"]
                    go_to("Ricette")
                    st.rerun()

elif st.session_state.page == "Crea SKiscetta":
    st.markdown("## Crea la tua SKiscetta")

    if not all_recipes:
        st.error(
            "Il database ricette non è stato caricato. Controlla che esista il file data/recipes.json."
        )

    with st.container(border=True):
        st.markdown("### Generatore smart gratuito")
        st.write(
            "SKiscettAI ora fa due cose: cerca nel catalogo le ricette più vicine "
            "e crea anche una SKiscetta modulare originale usando base + proteina + verdura + salsa + topping."
        )

    with st.form("SKiscetta_form"):
        ingredienti = st.text_input(
            "Che ingredienti hai in casa?",
            placeholder="Esempio: pollo, riso, zucchine",
        )

        col1, col2 = st.columns(2)

        with col1:
            obiettivo = st.selectbox(
                "Qual è il tuo obiettivo?",
                [
                    "Svuota frigo",
                    "Proteica",
                    "Light",
                    "Economica",
                    "Vegetariana",
                    "Veloce",
                    "Gourmet",
                    "Meal prep",
                ],
            )

        with col2:
            tempo = st.selectbox(
                "Quanto tempo hai?",
                [
                    "10 minuti",
                    "20 minuti",
                    "30 minuti",
                    "45 minuti",
                ],
            )

        preferenze = st.text_input(
            "Preferenze o vincoli",
            placeholder="Esempio: senza pesce, più proteica, da mangiare fredda",
        )

        submitted = st.form_submit_button("Genera la mia SKiscetta")

    if submitted:
        if not ingredienti.strip():
            st.warning("Inserisci almeno un ingrediente.")
        else:
            modular_recipe = generate_modular_recipe(
                modules,
                ingredienti,
                obiettivo,
                tempo,
                preferences=preferenze,
            )

            if modular_recipe:
                upsert_custom_recipe(modular_recipe)

            matched_recipes = find_best_recipes(
                recipes,
                ingredienti,
                obiettivo,
                tempo,
                preferences=preferenze,
            )

            generated_ids = []

            if modular_recipe:
                generated_ids.append(modular_recipe["id"])

            generated_ids.extend([recipe["id"] for recipe in matched_recipes])
            st.session_state.generated_recipe_ids = generated_ids[:4]
            all_recipes = combined_recipes()

    if st.session_state.generated_recipe_ids:
        st.success("Ecco la tua SKiscetta modulare più le ricette più vicine dal catalogo.")

        current_recipes = combined_recipes()

        for recipe_id in st.session_state.generated_recipe_ids:
            recipe = get_recipe_by_id(current_recipes, recipe_id)

            if recipe:
                recipe_card(recipe, key_prefix="generated", show_save=True)


elif st.session_state.page == "Ricette":
    st.markdown("## Catalogo ricette")

    current_recipes = combined_recipes()
    current_clusters = recipes_by_cluster(current_recipes)

    with st.container(border=True):
        st.markdown("### Filtri")
        search_col, goal_col = st.columns(2)

        with search_col:
            text_query = st.text_input(
                "Cerca per ingrediente, nome o parola chiave",
                placeholder="Esempio: pollo, ceci, pasta, light",
            )

        with goal_col:
            goal_filter = st.selectbox(
                "Filtra per obiettivo",
                [
                    "Tutte",
                    "Proteica",
                    "Light",
                    "Economica",
                    "Vegetariana",
                    "Veloce",
                    "Gourmet",
                    "Meal prep",
                    "Svuota frigo",
                ],
            )

        tag_col, time_col, cluster_col = st.columns(3)

        with tag_col:
            tag_values = ["Tutti"] + sorted(set(tags + ["modulare"]))
            tag_filter = st.selectbox("Filtra per tag", tag_values)

        with time_col:
            max_time_filter = st.selectbox(
                "Tempo massimo",
                [
                    "Qualsiasi",
                    "10 minuti",
                    "20 minuti",
                    "30 minuti",
                    "45 minuti",
                ],
            )

        with cluster_col:
            cluster_values = ["Tutti"] + sorted(current_clusters.keys())
            cluster_filter = st.selectbox("Filtra per cluster", cluster_values)

        max_cards = st.slider(
            "Quante ricette mostrare",
            min_value=6,
            max_value=30,
            value=12,
            step=3,
        )

    filtered_recipes = filter_recipes(
        current_recipes,
        text_query,
        goal_filter,
        tag_filter,
        max_time_filter,
        cluster_filter,
    )

    st.write(f"Ricette trovate: {len(filtered_recipes)}")

    if not filtered_recipes:
        st.warning("Nessuna ricetta trovata con questi filtri.")

    for recipe in filtered_recipes[:max_cards]:
        recipe_card(recipe, key_prefix="catalog", show_save=True)

    if len(filtered_recipes) > max_cards:
        st.info(
            f"Stai vedendo {max_cards} ricette su {len(filtered_recipes)}. "
            "Aumenta il numero o restringi i filtri."
        )


elif st.session_state.page == "Preferiti":
    st.markdown("## Le tue ricette preferite")

    favorite_recipes = get_favorite_recipes(combined_recipes())

    if not favorite_recipes:
        st.info("Non hai ancora salvato ricette preferite.")
        if st.button("Vai al catalogo"):
            go_to("Ricette")
            st.rerun()
    else:
        st.success(
            "Le ricette preferite alimentano automaticamente anche la lista della spesa."
        )

        for recipe in favorite_recipes:
            recipe_card(
                recipe,
                key_prefix="favorite",
                show_save=False,
                show_remove=True,
            )


elif st.session_state.page == "Lista spesa":
    st.markdown("## Lista della spesa")

    current_recipes = combined_recipes()
    favorite_recipes = get_favorite_recipes(current_recipes)
    meal_plan_recipes = get_meal_plan_recipes(current_recipes)

    with st.container(border=True):
        st.markdown("### Fonti della lista")

        use_favorites = st.checkbox("Usa ricette preferite", value=True)
        use_meal_plan = st.checkbox("Usa meal plan settimanale", value=True)

        extra_item = st.text_input(
            "Aggiungi ingrediente extra",
            placeholder="Esempio: yogurt greco",
        )

        if st.button("Aggiungi extra"):
            if extra_item.strip():
                st.session_state.extra_shopping_items.append(extra_item.strip())
                st.success("Ingrediente extra aggiunto.")
                st.rerun()

    selected_recipes = []

    if use_favorites:
        selected_recipes.extend(favorite_recipes)

    if use_meal_plan:
        selected_recipes.extend(meal_plan_recipes)

    shopping_counter = aggregate_ingredients(
        selected_recipes,
        st.session_state.extra_shopping_items,
    )

    st.write("")

    source_col1, source_col2, source_col3 = st.columns(3)

    with source_col1:
        st.metric("Ricette preferite", len(favorite_recipes))

    with source_col2:
        st.metric("Ricette meal plan", len(meal_plan_recipes))

    with source_col3:
        st.metric("Ingredienti in lista", len(shopping_counter))

    if not shopping_counter:
        st.info(
            "La lista è vuota. Salva ricette nei preferiti o scegli ricette nel meal plan."
        )
    else:
        st.markdown("### Ingredienti da comprare")

        for ingredient, count in sorted(shopping_counter.items()):
            lookup_key = normalize_text(ingredient)
            info = ingredients_by_name.get(lookup_key, {})
            category = info.get("category", "categoria non disponibile")

            label = ingredient
            if count > 1:
                label = f"{ingredient} x{count}"

            st.checkbox(
                f"{label} — {category}",
                key=f"shop_{normalize_text(ingredient)}",
            )

        st.write("")

        shopping_text = build_shopping_text(shopping_counter)

        st.download_button(
            "Scarica lista della spesa",
            data=shopping_text,
            file_name="lista_spesa_skiscettai.txt",
            mime="text/plain",
        )

        if st.button("Svuota ingredienti extra"):
            st.session_state.extra_shopping_items = []
            st.rerun()



elif st.session_state.page == "SKAI Radar":
    render_skai_section_label(
        "SKAI Copilot",
        "Dimmi il problema. SKAI sceglie il flusso.",
        "Non è una dashboard da compilare: è un assistente operativo per pranzo, spesa e offerte."
    )

    current_recipes = combined_recipes()
    favorite_recipes = get_favorite_recipes(current_recipes)
    meal_plan_recipes = get_meal_plan_recipes(current_recipes)

    with st.container(border=True):
        st.markdown("### Cosa vuoi fare adesso?")
        intent = st.radio(
            "Scegli il risultato, non la funzione.",
            [
                "Crea una SKiscetta con quello che ho",
                "Faccio il piano spesa settimanale",
                "Vedo offerte vicino a me",
            ],
            horizontal=True,
            label_visibility="collapsed",
            key="skai_intent",
        )
        render_skai_action_plan(intent)

    with st.container(border=True):
        st.markdown("### Dove e quanto lontano?")
        loc1, loc2, loc3 = st.columns([0.9, 1.1, 1])

        with loc1:
            cap = st.text_input(
                "CAP",
                value="53100",
                placeholder="53100",
                key="skai_cap",
            )

        with loc2:
            radius_km = st.select_slider(
                "Raggio ricerca",
                options=[2, 5, 10, 20, 30],
                value=10,
                format_func=lambda value: f"{value} km",
                key="skai_radius",
            )

        with loc3:
            use_web_parsers = st.toggle(
                "Radar offerte web",
                value=True,
                key="skai_web_parser_toggle",
            )
            max_web_offers = st.select_slider(
                "Max offerte",
                options=[10, 20, 30, 50],
                value=20,
                key="skai_max_web_offers",
            )

    home_ingredients = ""
    goal = "Svuota frigo"
    max_time = "20 minuti"
    weekly_days = 5
    extra_weekly_items = ""
    selected_ingredients = []

    if intent == "Crea una SKiscetta con quello che ho":
        with st.container(border=True):
            st.markdown("### Ingredienti disponibili")
            h1, h2, h3 = st.columns([1.4, 0.8, 0.8])

            with h1:
                home_ingredients = st.text_area(
                    "Cosa hai in casa?",
                    placeholder="pollo, riso, zucchine, yogurt...",
                    height=95,
                    key="skai_home_ingredients",
                )

            with h2:
                goal = st.selectbox(
                    "Obiettivo",
                    [
                        "Svuota frigo",
                        "Proteica",
                        "Light",
                        "Economica",
                        "Vegetariana",
                        "Veloce",
                        "Gourmet",
                        "Meal prep",
                    ],
                    key="skai_home_goal",
                )

            with h3:
                max_time = st.selectbox(
                    "Tempo",
                    ["10 minuti", "20 minuti", "30 minuti", "45 minuti"],
                    key="skai_home_time",
                )

            selected_ingredients = [
                item.strip()
                for item in re.split(r"[,;\n]", home_ingredients)
                if item.strip()
            ]

    elif intent == "Faccio il piano spesa settimanale":
        with st.container(border=True):
            st.markdown("### Settimana intelligente")
            w1, w2, w3 = st.columns([0.8, 1, 1.2])

            with w1:
                weekly_days = st.select_slider(
                    "Giorni da pianificare",
                    options=[3, 4, 5],
                    value=5,
                    key="skai_weekly_days",
                )

            with w2:
                weekly_focus = st.selectbox(
                    "Stile settimana",
                    ["Bilanciata", "Low cost", "Proteica", "Light", "Vegetariana", "Meal prep"],
                    key="skai_weekly_focus",
                )

            with w3:
                extra_weekly_items = st.text_input(
                    "Ingredienti che vuoi usare",
                    placeholder="tonno, farro, verdure...",
                    key="skai_weekly_extra",
                )

            selected_ingredients = [
                item.strip()
                for item in re.split(r"[,;\n]", extra_weekly_items)
                if item.strip()
            ]

            if favorite_recipes or meal_plan_recipes:
                shopping_counter = aggregate_ingredients(
                    favorite_recipes + meal_plan_recipes,
                    st.session_state.extra_shopping_items,
                )
                selected_ingredients.extend(list(shopping_counter.keys()))

    else:
        with st.container(border=True):
            st.markdown("### Radar puro")
            radar_target = st.text_input(
                "Ingrediente o prodotto da cercare",
                placeholder="pollo, pasta, caffè, yogurt...",
                key="skai_radar_target",
            )
            selected_ingredients = [
                item.strip()
                for item in re.split(r"[,;\n]", radar_target)
                if item.strip()
            ]

    location_centers = {
        "53100": {
            "lat": 43.3188,
            "lon": 11.3308,
            "display_name": "53100 Siena, Toscana, Italia",
        }
    }

    geocoded_location = geocode_postcode(cap, country="Italia")

    if geocoded_location:
        user_lat = geocoded_location["lat"]
        user_lon = geocoded_location["lon"]
        location_label = geocoded_location["display_name"]
    else:
        fallback = location_centers["53100"]
        user_lat = fallback["lat"]
        user_lon = fallback["lon"]
        location_label = fallback["display_name"]
        st.info("Non ho riconosciuto il CAP. Per non bloccarti uso Siena come demo operativa.")

    try:
        discovered_stores_raw = fetch_osm_supermarkets(user_lat, user_lon, radius_km)
    except Exception as error:
        discovered_stores_raw = []
        st.info("OpenStreetMap non risponde ora: uso i punti vendita locali come fallback.")

    discovered_stores = enrich_discovered_stores(
        discovered_stores_raw,
        offer_sources_data,
        user_lat,
        user_lon,
    )

    nearby_stores, stores_source_label = merge_discovered_and_manual_stores(
        discovered_stores,
        stores_data,
        user_lat,
        user_lon,
        radius_km,
    )

    if use_web_parsers:
        parser_chains = skai_parser_chain_candidates(
            nearby_stores,
            offer_sources_data,
            minimum=6,
        )
        parser_results, web_offers = fetch_multi_chain_offers_v1(
            parser_chains,
            offer_sources_data,
            max_chains=6,
        )
    else:
        parser_chains = []
        parser_results = []
        web_offers = []

    clean_web_offers, raw_web_offers = split_offer_quality(web_offers)
    structured_offers = limit_web_offers(
        dedupe_offers(clean_web_offers),
        max_web_offers,
    )

    offer_engine = build_offer_engine_state(
        structured_offers,
        nearby_stores,
        stores_by_id,
        offer_sources_data,
        selected_ingredients=selected_ingredients,
    )

    offers_nearby = offer_engine["offers_nearby"]
    offers_to_show = offer_engine["offers_to_show"]
    nearby_chains = offer_engine["nearby_chains"]
    web_count = len([offer for offer in structured_offers if offer_origin_group(offer) == "web"])
    radar_score = skai_radar_score(nearby_stores, nearby_chains, offers_to_show)
    best_offer = skai_best_offer(offers_to_show)

    st.write("")
    k1, k2, k3, k4, k5 = st.columns(5)

    with k1:
        st.metric("SKAI score", f"{radar_score}/100")

    with k2:
        st.metric("Negozi", len(nearby_stores))

    with k3:
        st.metric("Catene", len(nearby_chains))

    with k4:
        st.metric("Offerte pulite", web_count)

    with k5:
        st.metric("Raw scartati", len(raw_web_offers))

    if parser_chains:
        st.caption("Parser controllati: " + ", ".join(parser_chains))

    if best_offer:
        st.markdown(
            f"""
            <div class="skai-deal-banner">
                <div>
                    <span>Best signal</span>
                    <strong>{best_offer.get('chain', 'Web')} · {skai_format_money(best_offer.get('price', ''))}</strong>
                </div>
                <p>{clean_display_product_name(best_offer.get('product_name', ''))}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with st.container(border=True):
        map_col, side_col = st.columns([1.55, 0.95])

        with map_col:
            st.markdown("### Mappa radar")
            if MAP_AVAILABLE:
                stores_map = create_stores_map(
                    nearby_stores,
                    offers_to_show if offers_to_show else offers_nearby,
                    center_lat=user_lat,
                    center_lon=user_lon,
                )
                st_folium(stores_map, width=820, height=500)
            else:
                st.warning(f"Mappa non disponibile: {MAP_ERROR}")

        with side_col:
            st.markdown("### Prossime mosse")
            st.caption(location_label)

            if intent == "Crea una SKiscetta con quello che ho":
                if selected_ingredients:
                    st.success("Ingredienti letti. SKAI può proporti una ricetta e controllare offerte correlate.")
                else:
                    st.info("Scrivi 3-5 ingredienti per generare una SKiscetta più precisa.")
            elif intent == "Faccio il piano spesa settimanale":
                st.success("SKAI userà ricette + offerte pulite per costruire una settimana più conveniente.")
            else:
                st.success("Guarda mappa, catene controllate e offerte pulite sotto.")

            st.markdown("#### Negozi vicini")
            nearest_rows = []
            for store in nearby_stores:
                distance = store.get(
                    "distance_km",
                    round(
                        haversine_km(
                            user_lat,
                            user_lon,
                            store.get("lat", user_lat),
                            store.get("lon", user_lon),
                        ),
                        1,
                    ),
                )
                nearest_rows.append((distance, store))

            nearest_rows.sort(key=lambda item: item[0])

            for distance, store in nearest_rows[:4]:
                with st.container(border=True):
                    st.markdown(f"**{store.get('name', '')}**")
                    st.caption(f"{store.get('type', '')} · {distance:.1f} km")

    st.write("")

    if intent == "Crea una SKiscetta con quello che ho":
        render_skai_section_label(
            "SKiscetta mode",
            "Da ingredienti casuali a pranzo pronto.",
            "SKAI parte da quello che hai e usa le offerte solo come acceleratore."
        )

        if selected_ingredients:
            modular_recipe = generate_modular_recipe(
                modules,
                ", ".join(selected_ingredients),
                goal,
                max_time,
                preferences="",
            )
            suggestions = skai_recipes_for_home_ingredients(
                current_recipes,
                selected_ingredients,
                goal,
                limit=3,
            )

            if modular_recipe:
                with st.container(border=True):
                    st.markdown(f"### {modular_recipe.get('title', 'SKiscetta smart')}")
                    st.write(modular_recipe.get("description", ""))
                    st.caption("Ingredienti: " + ", ".join(modular_recipe.get("ingredients", [])[:8]))
                    if st.button("Salva questa SKiscetta", key="save_copilot_modular"):
                        upsert_custom_recipe(modular_recipe)
                        save_favorite(modular_recipe["id"])

            st.markdown("### Alternative dal catalogo")
            cols = st.columns(3)
            for index, recipe in enumerate(suggestions):
                with cols[index % 3]:
                    with st.container(border=True):
                        st.markdown(f"#### {recipe.get('title', 'Ricetta')}")
                        st.write(recipe.get("description", ""))
                        st.caption(", ".join(recipe.get("ingredients", [])[:5]))
                        if st.button("Salva", key=f"copilot_save_{recipe['id']}"):
                            save_favorite(recipe["id"])
        else:
            st.info("Scrivi ingredienti in alto: SKAI genererà la SKiscetta qui.")

    elif intent == "Faccio il piano spesa settimanale":
        render_skai_section_label(
            "Weekly planner",
            "Piano spesa guidato dalle offerte.",
            "Se i parser trovano offerte pulite, SKAI dà priorità alle ricette più convenienti."
        )

        plan = skai_week_plan_from_recipes(
            current_recipes,
            offers_to_show,
            days=weekly_days,
        )

        if plan:
            plan_cols = st.columns(2)

            for index, item in enumerate(plan):
                day = WORK_DAYS[index] if index < len(WORK_DAYS) else f"Giorno {index + 1}"
                recipe = item["recipe"]

                with plan_cols[index % 2]:
                    with st.container(border=True):
                        st.caption(day)
                        st.markdown(f"#### {recipe.get('title', 'Ricetta')}")
                        st.write(recipe.get("description", ""))
                        st.caption(item["reason"])

            if st.button("Salva questo piano nel Meal plan", key="save_skai_week_plan"):
                for index, item in enumerate(plan):
                    if index < len(WORK_DAYS):
                        st.session_state[f"meal_{WORK_DAYS[index]}"] = item["recipe"].get("title", "Nessuna ricetta")
                st.success("Piano salvato nel Meal plan.")

            shopping_counter = aggregate_ingredients([item["recipe"] for item in plan], [])
            if shopping_counter:
                with st.expander("Lista spesa suggerita", expanded=True):
                    rows = [
                        {"ingrediente": ingredient, "ricette": count}
                        for ingredient, count in shopping_counter.most_common()
                    ]
                    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    else:
        render_skai_section_label(
            "Deal feed",
            "Offerte web pulite.",
            "Mostro solo card con prodotto e prezzo leggibili. I dati grezzi restano nel pannello tecnico."
        )

    if intent != "Faccio il piano spesa settimanale":
        if selected_ingredients:
            st.caption("Target: " + ", ".join(selected_ingredients[:12]))

        if not offers_to_show:
            st.warning(
                "I parser hanno raggiunto le fonti, ma non hanno estratto prodotti abbastanza leggibili per le card. "
                "Controlla il dettaglio parser o prova un raggio diverso."
            )
        else:
            offer_cards = offers_to_show[:12]
            card_cols = st.columns(3)

            for index, offer in enumerate(offer_cards):
                with card_cols[index % 3]:
                    render_skai_offer_card(offer, index)

    st.write("")
    with st.expander("Controllo tecnico parser e fonti", expanded=False):
        parser_rows = []
        for result in parser_results:
            extracted = len(result.get("offers", []))
            parser_rows.append(
                {
                    "catena": result.get("chain", ""),
                    "stato": "ok" if extracted > 0 else "nessuna offerta strutturata",
                    "offerte_raw": extracted,
                    "messaggio": result.get("message", ""),
                }
            )

        if parser_rows:
            st.dataframe(pd.DataFrame(parser_rows), use_container_width=True, hide_index=True)

        if offers_to_show:
            st.caption("Offerte pulite mostrate nelle card")
            rows = offer_rows(offers_to_show, stores_by_id, user_lat=user_lat, user_lon=user_lon)
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        if raw_web_offers:
            st.caption("Raw parser scartati dalle card perché non abbastanza leggibili")
            raw_rows = offer_rows(raw_web_offers[:30], stores_by_id, user_lat=user_lat, user_lon=user_lon)
            st.dataframe(pd.DataFrame(raw_rows), use_container_width=True, hide_index=True)




elif st.session_state.page == "Meal plan":
    st.markdown("## Meal plan settimanale")

    current_recipes = combined_recipes()

    with st.container(border=True):
        st.markdown("### Organizza la tua settimana")
        st.write(
            "Scegli una SKiscetta per ogni giorno lavorativo. "
            "Le ricette selezionate alimentano automaticamente la lista della spesa."
        )

    recipe_options = ["Nessuna ricetta"] + [
        recipe.get("title", "Ricetta") for recipe in current_recipes
    ]

    for day in WORK_DAYS:
        st.selectbox(day, recipe_options, key=f"meal_{day}")

    st.write("")
    st.markdown("### Riepilogo settimana")

    planned_recipes = get_meal_plan_recipes(current_recipes)

    if not planned_recipes:
        st.info("Non hai ancora selezionato ricette per la settimana.")
    else:
        for day in WORK_DAYS:
            title = st.session_state.get(f"meal_{day}", "Nessuna ricetta")
            recipe = get_recipe_by_title(current_recipes, title)

            if recipe:
                st.write(
                    f"**{day}:** {recipe.get('title')} "
                    f"— {recipe.get('goal', '-')} · {recipe.get('prep_time', '-')}"
                )
            else:
                st.write(f"**{day}:** Nessuna ricetta")

        st.write("")

        if st.button("Vai alla lista della spesa"):
            go_to("Lista spesa")
            st.rerun()
