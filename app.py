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
    page_title="SKiscettAI · SKAI God Mode",
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



# =========================================================
# SKAI v17 Dedicated Offer Parsers
# =========================================================

CHAIN_PARSER_PROFILES = {
    "Carrefour": {
        "name_keys": ["name", "productName", "displayName", "title", "description", "label"],
        "price_keys": ["price", "salePrice", "currentPrice", "finalPrice", "sellingPrice", "value", "amount"],
        "bad": ["punti vendita", "spesa online", "area utente", "newsletter", "carrefour"],
    },
    "Coop": {
        "name_keys": ["name", "productName", "title", "descrizione", "description", "label"],
        "price_keys": ["price", "prezzo", "salePrice", "currentPrice", "value", "amount"],
        "bad": ["volantino", "soci coop", "unicoop", "newsletter"],
    },
    "Conad": {
        "name_keys": ["name", "productName", "title", "description", "descrizione", "label"],
        "price_keys": ["price", "prezzo", "salePrice", "currentPrice", "value", "amount"],
        "bad": ["volantini", "negozi", "catalogo", "servizi", "conad"],
    },
    "PENNY": {
        "name_keys": ["name", "productName", "title", "description", "label"],
        "price_keys": ["price", "prezzo", "salePrice", "currentPrice", "value", "amount"],
        "bad": ["newsletter", "penny card", "punti vendita"],
    },
    "Lidl": {
        "name_keys": ["name", "productName", "title", "description", "label"],
        "price_keys": ["price", "priceValue", "currentPrice", "salePrice", "value", "amount"],
        "bad": ["newsletter", "lidl plus", "carrello"],
    },
    "Eurospin": {
        "name_keys": ["name", "productName", "title", "description", "label"],
        "price_keys": ["price", "prezzo", "salePrice", "currentPrice", "value", "amount"],
        "bad": ["volantino", "punti vendita", "newsletter"],
    },
    "Esselunga": {
        "name_keys": ["name", "productName", "title", "description", "label"],
        "price_keys": ["price", "prezzo", "salePrice", "currentPrice", "value", "amount"],
        "bad": ["fidaty", "negozi"],
    },
    "MD": {
        "name_keys": ["name", "productName", "title", "description", "label"],
        "price_keys": ["price", "prezzo", "salePrice", "currentPrice", "value", "amount"],
        "bad": ["volantino", "newsletter", "punti vendita"],
    },
    "PAM": {
        "name_keys": ["name", "productName", "title", "description", "label"],
        "price_keys": ["price", "prezzo", "salePrice", "currentPrice", "value", "amount"],
        "bad": ["newsletter", "punti vendita", "pam panorama"],
    },
}


def skai_v16_headers():
    return {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json;q=0.8,*/*;q=0.7",
        "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.7,en;q=0.6",
        "Cache-Control": "no-cache",
    }


def skai_v16_deep_iter(obj):
    if isinstance(obj, dict):
        yield obj
        for value in obj.values():
            yield from skai_v16_deep_iter(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from skai_v16_deep_iter(value)


def skai_v16_parse_json_safely(value):
    try:
        return json.loads(value)
    except Exception:
        return None


def skai_v16_find_json_objects(raw):
    objects = []

    for match in re.finditer(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        raw,
        flags=re.I | re.S,
    ):
        parsed = skai_v16_parse_json_safely(html.unescape(match.group(1)).strip())
        if parsed is not None:
            objects.append(parsed)

    for pattern in [
        r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>',
        r'window\.__NUXT__\s*=\s*(\{.*?\});',
        r'window\.__INITIAL_STATE__\s*=\s*(\{.*?\});',
        r'window\.__APOLLO_STATE__\s*=\s*(\{.*?\});',
    ]:
        for match in re.finditer(pattern, raw, flags=re.I | re.S):
            parsed = skai_v16_parse_json_safely(html.unescape(match.group(1)).strip())
            if parsed is not None:
                objects.append(parsed)

    return objects


def skai_v16_extract_price(value):
    if value is None:
        return None

    if isinstance(value, (int, float)):
        number = float(value)
        if 0.05 <= number <= 999:
            return round(number, 2)
        # possible cents
        if 50 <= number <= 99900:
            return round(number / 100, 2)
        return None

    text_value = str(value)
    candidates = re.findall(r"\d{1,3}(?:[,.]\d{1,2})", text_value)

    for candidate in candidates:
        price = price_to_float(candidate)
        if price is not None and 0.05 <= price <= 999:
            return round(price, 2)

    digits = re.findall(r"\b\d{2,5}\b", text_value)
    for item in digits:
        cents = int(item)
        if 50 <= cents <= 99900:
            price = cents / 100
            if 0.05 <= price <= 999:
                return round(price, 2)

    return None


def skai_v16_pick_name_from_dict(data, profile):
    names = []

    for key in profile.get("name_keys", []):
        if key in data and isinstance(data.get(key), (str, int, float)):
            names.append(str(data.get(key)))

    for key, value in data.items():
        key_norm = normalize_text(key)
        if any(token in key_norm for token in ["name", "title", "descr", "product", "label"]):
            if isinstance(value, (str, int, float)):
                names.append(str(value))

    for name in names:
        clean = skai_clean_product_title(name) if "skai_clean_product_title" in globals() else cleanup_product_candidate(name)
        if "skai_product_identity_score" in globals():
            if skai_product_identity_score(clean) >= 2:
                return clean
        elif not is_bad_offer_text(clean):
            return clean

    return ""


def skai_v16_pick_price_from_dict(data, profile):
    for key in profile.get("price_keys", []):
        if key in data:
            price = skai_v16_extract_price(data.get(key))
            if price is not None:
                return price

    for key, value in data.items():
        key_norm = normalize_text(key)
        if any(token in key_norm for token in ["price", "prezzo", "amount", "value", "sale"]):
            price = skai_v16_extract_price(value)
            if price is not None:
                return price

    for key in ["offers", "offer", "pricing", "priceInfo", "priceSpecification", "commercialOffer"]:
        nested = data.get(key)
        if isinstance(nested, dict):
            price = skai_v16_pick_price_from_dict(nested, profile)
            if price is not None:
                return price
        elif isinstance(nested, list):
            for item in nested:
                if isinstance(item, dict):
                    price = skai_v16_pick_price_from_dict(item, profile)
                    if price is not None:
                        return price

    return None


def skai_v16_product_score(name):
    if "skai_product_identity_score" in globals():
        return skai_product_identity_score(name)

    if not name or is_bad_offer_text(name):
        return 0

    words = re.findall(r"[a-zA-ZàèéìòùÀÈÉÌÒÙ]{3,}", name)
    return 2 if len(words) >= 2 else 0


def skai_v16_candidate_is_clean(name, chain, profile):
    low = normalize_text(name)

    if not name or len(name) < 4:
        return False

    if chain and normalize_text(chain) == low:
        return False

    if any(bad in low for bad in profile.get("bad", [])):
        return False

    if "BAD_PRODUCT_HINTS" in globals() and any(bad in low for bad in BAD_PRODUCT_HINTS):
        return False

    return skai_v16_product_score(name) >= 2


def skai_v16_add_candidate(candidates, seen, chain, name, price, url, parser_name):
    if not name or price is None:
        return

    key = (normalize_text(name), round(float(price), 2))
    if key in seen:
        return

    seen.add(key)
    candidates.append(
        {
            "product": name,
            "snippet": name,
            "price": round(float(price), 2),
            "parser": parser_name,
            "source_url": url,
        }
    )


def skai_v16_extract_from_json_objects(raw, chain, profile, url):
    candidates = []
    seen = set()

    for obj in skai_v16_find_json_objects(raw):
        for item in skai_v16_deep_iter(obj):
            if not isinstance(item, dict):
                continue

            name = skai_v16_pick_name_from_dict(item, profile)
            price = skai_v16_pick_price_from_dict(item, profile)

            if skai_v16_candidate_is_clean(name, chain, profile) and price is not None:
                skai_v16_add_candidate(candidates, seen, chain, name, price, url, "json-data")

            if len(candidates) >= 40:
                return candidates

    return candidates


def skai_v16_extract_from_html_cards(raw, chain, profile, url):
    candidates = []
    seen = set()

    clean = re.sub(r"<script.*?</script>", " ", raw, flags=re.I | re.S)
    clean = re.sub(r"<style.*?</style>", " ", clean, flags=re.I | re.S)

    blocks = re.findall(
        r"(<(?:article|li|div|section)[^>]*(?:product|card|offer|promo|item|tile|teaser)[^>]*>.*?</(?:article|li|div|section)>)",
        clean,
        flags=re.I | re.S,
    )

    if not blocks:
        text_body = re.sub(r"<[^>]+>", " ", clean)
        text_body = html.unescape(re.sub(r"\s+", " ", text_body))
        for match in re.finditer(r"(.{0,160})(\d{1,3}[,.]\d{2})\s*€(.{0,120})", text_body, flags=re.I):
            price = skai_v16_extract_price(match.group(2))
            before = skai_clean_product_title(match.group(1)) if "skai_clean_product_title" in globals() else cleanup_product_candidate(match.group(1))
            after = skai_clean_product_title(match.group(3)) if "skai_clean_product_title" in globals() else cleanup_product_candidate(match.group(3))
            name = before if skai_v16_product_score(before) >= skai_v16_product_score(after) else after
            if skai_v16_candidate_is_clean(name, chain, profile):
                skai_v16_add_candidate(candidates, seen, chain, name, price, url, "html-window")
            if len(candidates) >= 25:
                return candidates
        return candidates

    for block in blocks[:220]:
        block_text = html.unescape(re.sub(r"<[^>]+>", " ", block))
        block_text = re.sub(r"\s+", " ", block_text).strip()
        price = skai_v16_extract_price(block_text)
        if price is None:
            continue

        name_candidates = []

        for attr in ["alt", "title", "aria-label", "data-name", "data-product-name"]:
            for m in re.finditer(attr + r'=["\']([^"\']{4,160})["\']', block, flags=re.I):
                name_candidates.append(m.group(1))

        for m in re.finditer(
            r"<(?:h2|h3|h4|strong|span|p)[^>]*(?:title|name|product|descr|label)[^>]*>(.*?)</(?:h2|h3|h4|strong|span|p)>",
            block,
            flags=re.I | re.S,
        ):
            name_candidates.append(re.sub(r"<[^>]+>", " ", m.group(1)))

        name_candidates.append(re.sub(r"\d{1,3}[,.]\d{2}\s*€", " ", block_text))

        for candidate in name_candidates:
            name = skai_clean_product_title(candidate) if "skai_clean_product_title" in globals() else cleanup_product_candidate(candidate)
            if skai_v16_candidate_is_clean(name, chain, profile):
                skai_v16_add_candidate(candidates, seen, chain, name, price, url, "html-card")
                break

        if len(candidates) >= 40:
            break

    return candidates


def skai_v16_deduplicate_candidates(candidates):
    result = []
    seen = set()

    for item in candidates:
        key = (normalize_text(item.get("product", "")), item.get("price"))
        if key in seen:
            continue

        seen.add(key)
        result.append(item)

    return result


def skai_v16_parse_chain_offers(chain, url, raw):
    profile = CHAIN_PARSER_PROFILES.get(chain, CHAIN_PARSER_PROFILES.get("Carrefour", {}))
    json_candidates = skai_v16_extract_from_json_objects(raw, chain, profile, url)
    html_candidates = skai_v16_extract_from_html_cards(raw, chain, profile, url)
    candidates = skai_v16_deduplicate_candidates(json_candidates + html_candidates)
    return [item for item in candidates if skai_v16_product_score(item.get("product", "")) >= 2]



# =========================================================
# SKAI v26 Multi-Source Offer Engine
# =========================================================

CHAIN_FALLBACK_URLS_V26 = {
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
        "https://www.pampanorama.it/punti-vendita/",
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


def skai_v26_source_urls(chain, primary_url=""):
    urls = []
    if primary_url:
        urls.append(primary_url)
    urls.extend(CHAIN_FALLBACK_URLS_V26.get(chain, []))

    deduped = []
    seen = set()
    for url in urls:
        key = str(url).rstrip("/")
        if key and key not in seen:
            seen.add(key)
            deduped.append(str(url))
    return deduped


def skai_v26_source_name(url):
    low = str(url).lower()
    if "penny.it" in low or "coopfirenze" in low or "conad.it" in low or "pampanorama" in low or "carrefour.it" in low or "lidl.it" in low or "eurospin.it" in low or "esselunga.it" in low or "mdspa.it" in low:
        return "official"
    if "doveconviene" in low:
        return "doveconviene"
    if "promoqui" in low:
        return "promoqui"
    if "volantinofacile" in low:
        return "volantinofacile"
    if "zonavolantini" in low:
        return "zonavolantini"
    return "web"


def skai_v26_clean_catalog_product(raw_name, chain=""):
    text_value = html.unescape(str(raw_name or ""))
    text_value = re.sub(r"<[^>]+>", " ", text_value)
    text_value = re.sub(r"https?://\S+", " ", text_value)
    text_value = re.sub(r"\b(?:volantino|offerte|catalogo|supermercati|negozi|orari|scade|sfoglia|anteprima)\b", " ", text_value, flags=re.I)
    text_value = re.sub(r"\b(?:dal|al|fino al)\s+\d{1,2}[./]\d{1,2}(?:[./]\d{2,4})?", " ", text_value, flags=re.I)
    text_value = re.sub(r"\b\d{1,2}[./]\d{1,2}(?:[./]\d{2,4})?\b", " ", text_value)
    text_value = re.sub(r"\d{1,3}[,.]\d{2}\s*€", " ", text_value)
    text_value = re.sub(r"[-−]\s*\d{1,2}\s*%", " ", text_value)
    if chain:
        text_value = re.sub(re.escape(chain), " ", text_value, flags=re.I)
    text_value = re.sub(r"\s+", " ", text_value).strip(" -–—|•·:,;")
    text_value = skai_clean_product_title(text_value) if "skai_clean_product_title" in globals() else cleanup_product_candidate(text_value)

    # If a catalog page leaves a long breadcrumb, take the most product-like tail.
    tokens = text_value.split()
    if len(tokens) > 10:
        for size in [8, 7, 6, 5, 4]:
            candidate = " ".join(tokens[-size:])
            if "skai_v16_product_score" in globals() and skai_v16_product_score(candidate) >= 2:
                text_value = candidate
                break

    return text_value[:92].strip()


def skai_v26_catalog_candidates(raw, chain, url):
    text_body = re.sub(r"<script.*?</script>", " ", raw, flags=re.I | re.S)
    text_body = re.sub(r"<style.*?</style>", " ", text_body, flags=re.I | re.S)
    text_body = re.sub(r"<[^>]+>", " ", text_body)
    text_body = html.unescape(text_body)
    text_body = re.sub(r"\s+", " ", text_body).strip()

    candidates = []
    seen = set()

    # Generic catalog wording: product text near euro price.
    patterns = [
        re.compile(r"(?P<name>[A-Za-zÀ-ÿ0-9][^€]{10,135}?)\s+(?P<price>\d{1,3}[,.]\d{2})\s*€", flags=re.I),
        re.compile(r"(?P<price>\d{1,3}[,.]\d{2})\s*€\s+(?P<name>[A-Za-zÀ-ÿ0-9][^€]{10,120}?)\s+(?:Scade|Dal|Al|Offerta|Volantino|Catalogo|$)", flags=re.I),
        re.compile(r"(?P<name>[A-Za-zÀ-ÿ0-9][^€]{8,115}?)\s+(?:Prezzo|Promo|Offerta)\s+(?P<price>\d{1,3}[,.]\d{2})", flags=re.I),
    ]

    for pattern in patterns:
        for match in pattern.finditer(text_body):
            price = skai_v16_extract_price(match.group("price")) if "skai_v16_extract_price" in globals() else price_to_float(match.group("price"))
            name = skai_v26_clean_catalog_product(match.group("name"), chain=chain)
            if not name or price is None:
                continue

            if "skai_v16_product_score" in globals() and skai_v16_product_score(name) < 2:
                continue

            # Reject obvious catalog/meta strings.
            low = normalize_text(name)
            if any(bad in low for bad in ["negozi nelle vicinanze", "tutti i negozi", "volantino e offerte", "catalogo e prezzi", "privacy", "cookie"]):
                continue

            key = (normalize_text(name), round(float(price), 2), chain)
            if key in seen:
                continue

            seen.add(key)
            candidates.append(
                {
                    "product": name,
                    "snippet": name,
                    "price": round(float(price), 2),
                    "parser": f"multi-source-{skai_v26_source_name(url)}",
                    "source_url": url,
                }
            )
            if len(candidates) >= 30:
                return candidates

    return candidates


def skai_v26_parse_any_source(chain, url, raw):
    items = []
    try:
        items.extend(skai_v20_parse_chain_offers(chain, url, raw))
    except Exception:
        pass
    try:
        items.extend(skai_v26_catalog_candidates(raw, chain, url))
    except Exception:
        pass

    result = []
    seen = set()
    for item in items:
        product = skai_v26_clean_catalog_product(item.get("product", ""), chain=chain)
        price = item.get("price")
        if not product or price is None:
            continue
        if "skai_v16_product_score" in globals() and skai_v16_product_score(product) < 2:
            continue
        key = (normalize_text(product), round(float(price), 2), chain)
        if key in seen:
            continue
        seen.add(key)
        fixed = dict(item)
        fixed["product"] = product
        fixed["price"] = round(float(price), 2)
        fixed["source_url"] = item.get("source_url", url)
        result.append(fixed)
    return result



@st.cache_data(ttl=3600)
def fetch_chain_offers_v1(chain, url):
    """Multi-source dispatcher v26.
    It tries official pages first and then flyer/catalog aggregators.
    Only product+price+chain offers pass the final gate.
    """
    if not chain:
        return {"chain": chain, "ok": False, "message": "Parser non configurato.", "offers": []}

    source_urls = skai_v26_source_urls(chain, url)
    if not source_urls:
        return {"chain": chain, "ok": False, "message": f"{chain}: nessuna fonte configurata.", "offers": []}

    all_snippets = []
    attempts = []
    errors = []

    for source_url in source_urls[:4]:
        try:
            response = requests.get(
                source_url,
                headers=skai_v16_headers(),
                timeout=18,
                allow_redirects=True,
            )
            attempts.append(f"{skai_v26_source_name(source_url)}:{response.status_code}")

            if response.status_code != 200:
                continue

            raw = response.text or ""
            snippets = skai_v26_parse_any_source(chain, source_url, raw)
            all_snippets.extend(snippets)

            # Stop early if we already have enough clean offers for this chain.
            if len(all_snippets) >= 18:
                break

        except Exception as error:
            errors.append(f"{skai_v26_source_name(source_url)}:{str(error)[:80]}")

    offers = []
    seen = set()
    chain_slug = normalize_for_match(chain).replace(" ", "_")

    for item in all_snippets:
        product_name = skai_v26_clean_catalog_product(item.get("product", ""), chain=chain)
        ingredient = infer_ingredient_from_product_text(product_name)
        price = item.get("price")

        if not product_name or price is None:
            continue

        if skai_v16_product_score(product_name) < 2:
            continue

        key = (normalize_text(product_name), round(float(price), 2), chain)
        if key in seen:
            continue

        seen.add(key)
        offers.append(
            {
                "id": f"{chain_slug}_v26_{len(offers) + 1:03d}",
                "store_id": f"{chain_slug}_web",
                "chain": chain,
                "ingredient": ingredient,
                "product_name": product_name,
                "price": round(float(price), 2),
                "unit": "web",
                "old_price": "",
                "valid_from": "",
                "valid_until": "",
                "source": item.get("source_url", url),
                "category": "offerte web verificate",
                "notes": f"Multi-source {chain} v26 · {item.get('parser', 'smart')}. Verifica sempre sul sito/volantino ufficiale.",
                "origin": f"web_{chain_slug}",
                "parser": item.get("parser", "v26"),
            }
        )

        if len(offers) >= 20:
            break

    if offers:
        return {
            "chain": chain,
            "ok": True,
            "message": f"{chain}: {len(offers)} offerte verificate da {len(source_urls[:4])} fonti ({', '.join(attempts)}).",
            "offers": offers,
        }

    detail = ", ".join(attempts + errors) if (attempts or errors) else "nessuna risposta utile"
    return {
        "chain": chain,
        "ok": True,
        "message": f"{chain}: fonti controllate ma nessun prodotto+prezzo affidabile ({detail}).",
        "offers": [],
    }

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




# =========================================================
# SKAI v30 Parser Compatibility Hotfix
# =========================================================

def parser_url_for_chain(chain, offer_sources):
    """Return the configured parser URL for a supermarket chain.

    This function is intentionally defined near the parser selection code because
    SKAI Radar uses it before web parsing starts. It must exist even when QA fast
    mode disables scraping.
    """
    chain_norm = normalize_for_match(chain)

    for source in offer_sources or []:
        source_chain = source.get("chain", "")
        aliases = source.get("aliases", [])
        candidates = [source_chain] + aliases

        for candidate in candidates:
            if normalize_for_match(candidate) == chain_norm:
                return source.get("url", "")

    return ""


def chains_with_parser_enabled(nearby_stores, offer_sources):
    chains = []

    for store in nearby_stores or []:
        chain = infer_store_chain_v2(store, offer_sources)
        if chain and chain != "Altro" and chain not in chains and parser_url_for_chain(chain, offer_sources):
            chains.append(chain)

    priority = ["Coop", "Conad", "PAM", "PENNY", "Lidl", "Eurospin", "Carrefour", "MD", "Esselunga"]

    return sorted(
        chains,
        key=lambda chain: priority.index(chain) if chain in priority else 99,
    )


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




# =========================================================
# SKAI v14 Product Identity Gate
# =========================================================

PRODUCT_WORDS = [
    "pollo", "tacchino", "manzo", "bresaola", "prosciutto", "tonno", "salmone", "merluzzo",
    "uova", "latte", "yogurt", "formaggio", "mozzarella", "ricotta", "feta", "parmigiano",
    "pasta", "spaghetti", "penne", "fusilli", "riso", "basmati", "farro", "orzo", "couscous",
    "pane", "piadina", "wrap", "cracker", "cereali", "avena",
    "zucchine", "carote", "pomodori", "pomodoro", "insalata", "melanzane", "peperoni",
    "patate", "cipolle", "spinaci", "broccoli", "funghi", "legumi", "ceci", "fagioli",
    "lenticchie", "piselli", "olio", "passata", "pesto", "sugo", "caffè", "acqua",
    "banana", "mele", "arance", "limoni", "fragole", "frutta",
]

BAD_PRODUCT_HINTS = [
    "prezzo", "peso", "confezione", "codice", "promozionale", "volantino",
    "fino al", "scopri", "carrello", "newsletter", "privacy", "cookie",
    "registrati", "login", "punti vendita", "servizio clienti", "termini",
    "condizioni", "javascript", "facebook", "instagram", "whatsapp",
    "totale", "iva", "euro", "eur", "kg", "litro",
]


def skai_clean_product_title(value):
    text = html.unescape(str(value or ""))
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"https?://\\S+", " ", text)
    text = re.sub(r"\\b\\d{1,2}/\\d{1,2}/\\d{2,4}\\b", " ", text)
    text = re.sub(r"\\b\\d{1,3}[,.]\\d{2}\\s*€?\\b", " ", text)
    text = re.sub(r"\\s+", " ", text).strip(" -–—|•·:,;")

    # Cut common web fragments.
    for sep in [" Aggiungi", " Scopri", " Fino al", " Prezzo", " Peso", " Codice"]:
        if sep in text:
            text = text.split(sep)[0].strip()

    return text[:88].strip()


def skai_product_identity_score(value):
    product = skai_clean_product_title(value)
    low = normalize_text(product)

    if not product:
        return 0

    if any(hint in low for hint in BAD_PRODUCT_HINTS):
        return 0

    words = re.findall(r"[a-zA-ZàèéìòùÀÈÉÌÒÙ]{3,}", product)

    if len(words) < 2:
        return 0

    score = 1

    if any(word in low for word in PRODUCT_WORDS):
        score += 2

    if len(words) >= 3:
        score += 1

    # Brand + product pattern, common in grocery cards.
    if any(word[:1].isupper() for word in words):
        score += 1

    return score


def skai_offer_has_product_identity(offer):
    product = offer.get("product_name", "")
    return skai_product_identity_score(product) >= 2


def skai_offer_quality_reason(offer):
    product = skai_clean_product_title(offer.get("product_name", ""))
    price = parse_price(offer.get("price", None))

    if price is None:
        return "prezzo non valido"

    if not product:
        return "prodotto assente"

    if skai_product_identity_score(product) < 2:
        return "prodotto non abbastanza leggibile"

    return "ok"


def split_offer_quality_v14(offers):
    clean = []
    raw = []

    for offer in offers:
        if is_offer_displayable(offer) and skai_offer_has_product_identity(offer):
            item = dict(offer)
            item["product_name"] = skai_clean_product_title(item.get("product_name", ""))
            clean.append(item)
        else:
            item = dict(offer)
            item["quality_reason"] = skai_offer_quality_reason(item)
            raw.append(item)

    return clean, raw


def render_skai_quality_notice(raw_count, clean_count):
    if clean_count > 0:
        return

    if raw_count <= 0:
        st.info("Nessuna offerta web pulita trovata ora. Puoi comunque usare mappa, ricette e piano spesa.")
        return

    st.markdown(
        f"""
        <div class="skai-v14-quality-card">
            <strong>Ho nascosto {raw_count} prezzi non leggibili.</strong>
            <p>I parser hanno trovato prezzi, ma non un nome prodotto affidabile. Meglio non mostrarti numeri senza sapere cosa stai comprando.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


# =========================================================
# SKAI v16 Kitchen OS Helpers
# =========================================================

def skai_parse_user_items(text_value):
    return [
        item.strip().lower()
        for item in re.split(r"[,;\n]", str(text_value or ""))
        if item.strip()
    ]


def skai_recipe_match_points(recipe, items):
    if not items:
        return 0

    recipe_text = normalize_text(" ".join(recipe.get("ingredients", [])) + " " + recipe.get("title", ""))
    points = 0

    for item in items:
        item_norm = normalize_text(item)
        if item_norm and item_norm in recipe_text:
            points += 2
        elif any(token in recipe_text for token in item_norm.split() if len(token) > 3):
            points += 1

    return points


def skai_best_recipe_matches(recipes, items, goal="", limit=5):
    scored = []

    for recipe in recipes:
        score = skai_recipe_match_points(recipe, items)
        meta = recipe.get("meta", {})
        goal_norm = normalize_text(goal)

        if goal_norm and goal_norm in normalize_text(meta.get("goal", "")):
            score += 1

        # Prefer fast/meal-prep recipes for app UX.
        time_text = normalize_text(meta.get("time", ""))
        if "10" in time_text or "20" in time_text:
            score += 1

        scored.append((score, recipe))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [recipe for score, recipe in scored[:limit] if score > 0] or [recipe for _, recipe in scored[:limit]]


def skai_build_shopping_counter(recipes_list, extra_items=None):
    counter = Counter()

    for recipe in recipes_list:
        for ingredient in recipe.get("ingredients", []):
            if ingredient:
                counter[ingredient] += 1

    for item in extra_items or []:
        if item:
            counter[item] += 1

    return counter


def skai_make_week_plan(recipes, offers, days=5, focus="Bilanciata"):
    # Start from deal recipes, but do not depend on offers.
    selected = []
    deal_items = best_deal_recipes(recipes, offers, {}, limit=days) if offers else []

    for item in deal_items:
        selected.append(
            {
                "recipe": item["recipe"],
                "reason": f"{item['coverage']} ingredienti potenzialmente coperti da offerte",
            }
        )

    used = {item["recipe"].get("id") for item in selected}
    focus_norm = normalize_text(focus)

    candidates = []
    for recipe in recipes:
        score = 0
        full = normalize_text(recipe.get("title", "") + " " + recipe.get("description", "") + " " + " ".join(recipe.get("tags", [])))
        meta = normalize_text(" ".join(str(v) for v in recipe.get("meta", {}).values()))

        if focus_norm and (focus_norm in full or focus_norm in meta):
            score += 2
        if "meal prep" in full or "meal" in meta:
            score += 1
        if recipe.get("id") not in used:
            candidates.append((score, recipe))

    candidates.sort(key=lambda item: item[0], reverse=True)

    for score, recipe in candidates:
        selected.append({"recipe": recipe, "reason": "scelta bilanciata dal catalogo"})
        if len(selected) >= days:
            break

    return selected[:days]


def skai_nearest_stores(nearby_stores, user_lat, user_lon, limit=6):
    rows = []

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
        rows.append((distance, store))

    rows.sort(key=lambda item: item[0])
    return rows[:limit]


def render_skai_store_cards(stores, user_lat, user_lon):
    for distance, store in skai_nearest_stores(stores, user_lat, user_lon, limit=5):
        st.markdown(
            f"""
            <div class="skai-os-store-card">
                <strong>{store.get('name', 'Punto vendita')}</strong>
                <span>{store.get('type', 'supermarket')} · {distance:.1f} km</span>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_skai_recipe_card(recipe, reason="", save_key_prefix="skai_v15"):
    st.markdown(
        f"""
        <div class="skai-os-result-card">
            <div class="skai-os-recipe-title">{recipe.get('title', 'Ricetta')}</div>
            <div class="skai-os-recipe-desc">{recipe.get('description', '')}</div>
            <div class="skai-os-ingredient-list">
                {''.join([f'<span>{item}</span>' for item in recipe.get('ingredients', [])[:7]])}
            </div>
            {f'<div class="skai-os-mini-pill">{reason}</div>' if reason else ''}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_skai_no_clean_offers(raw_count):
    if raw_count:
        st.markdown(
            f"""
            <div class="skai-os-warning-card">
                <strong>Ho trovato {raw_count} prezzi, ma li ho nascosti.</strong>
                <p>Non era chiaro il prodotto collegato. Un prezzo senza prodotto non è utile, quindi SKAI non lo mostra nel feed principale.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            """
            <div class="skai-os-warning-card">
                <strong>Nessuna offerta pulita trovata ora.</strong>
                <p>La mappa e il piano restano utilizzabili. Il prossimo salto sarà costruire parser dedicati per catena.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_skai_shopping_list(counter, offers=None):
    offers = offers or []
    offer_ingredients = {normalize_text(offer.get("ingredient", "")) for offer in offers}

    rows = []
    for ingredient, count in counter.most_common():
        ingredient_norm = normalize_text(ingredient)
        rows.append(
            {
                "ingrediente": ingredient,
                "ricette": count,
                "offerta": "possibile" if any(token and token in ingredient_norm for token in offer_ingredients) else "",
            }
        )

    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


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
    product = skai_clean_product_title(offer.get("product_name", ""))
    ingredient = offer.get("ingredient", "")
    origin = format_offer_origin(offer.get("origin", "web")) if "format_offer_origin" in globals() else "web"

    if skai_product_identity_score(product) < 2:
        # Never show a price card without a credible product identity.
        return

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
st.markdown("""<style>
/* =========================================================
   SKAI v28 — Visual flyer fallback
   ========================================================= */

.skai-v28-visual-panel {
    margin: 0.85rem 0;
    padding: 1rem;
    border-radius: 26px;
    border: 1px solid rgba(157,255,122,0.24);
    background:
        linear-gradient(145deg, rgba(157,255,122,0.14), rgba(49,247,255,0.075)),
        rgba(255,255,255,0.055);
    box-shadow: 0 20px 68px rgba(0,0,0,0.25), inset 0 1px 0 rgba(255,255,255,0.16);
}

.skai-v28-visual-panel span {
    color: #9dff7a;
    font-size: 0.72rem;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    font-weight: 1000;
}

.skai-v28-visual-panel strong {
    display: block;
    color: #ffffff !important;
    font-size: 1.22rem;
    margin-top: 0.18rem;
    letter-spacing: -0.04em;
}

.skai-v28-visual-panel p {
    color: rgba(255,255,255,0.78) !important;
    margin: 0.25rem 0 0 0 !important;
    font-weight: 760;
}

.skai-v28-link-card {
    min-height: 225px;
    padding: 1rem;
    border-radius: 22px;
    background:
        linear-gradient(145deg, rgba(255,255,255,0.13), rgba(255,255,255,0.055));
    border: 1px solid rgba(255,255,255,0.16);
    box-shadow: 0 18px 52px rgba(0,0,0,0.24);
}

.skai-v28-link-card span {
    display: block;
    color: #31f7ff;
    font-size: 0.72rem;
    letter-spacing: 0.13em;
    text-transform: uppercase;
    font-weight: 1000;
}

.skai-v28-link-card strong {
    display: block;
    color: #fff !important;
    font-size: 1.25rem;
    margin-top: 0.25rem;
}

.skai-v28-link-card p {
    color: rgba(255,255,255,0.75) !important;
    font-weight: 760;
}

.skai-v28-link-card a {
    display: inline-flex;
    margin-top: 0.55rem;
    padding: 0.55rem 0.75rem;
    border-radius: 999px;
    background: linear-gradient(90deg, #31f7ff, #9dff7a);
    color: #05060b !important;
    font-weight: 1000;
    text-decoration: none !important;
}
</style>""", unsafe_allow_html=True)
st.markdown("""<style>
/* =========================================================
   SKAI v23 — Brighter premium UI + button QA layer
   ========================================================= */

:root {
    --skai-v23-bg: #09131f;
    --skai-v23-panel: rgba(255,255,255,0.125);
    --skai-v23-panel-soft: rgba(255,255,255,0.085);
    --skai-v23-border: rgba(255,255,255,0.18);
    --skai-v23-text: #ffffff;
    --skai-v23-muted: rgba(255,255,255,0.76);
}

.stApp {
    background:
        radial-gradient(circle at 8% 8%, rgba(49,247,255,0.26), transparent 28%),
        radial-gradient(circle at 86% 12%, rgba(255,79,216,0.22), transparent 34%),
        radial-gradient(circle at 46% 92%, rgba(157,255,122,0.18), transparent 36%),
        linear-gradient(135deg, #08111d 0%, #102235 46%, #1b0f2e 100%) !important;
}

.block-container {
    max-width: 1200px !important;
}

.skai-os-hero,
.skai-os-panel,
.skai-os-result-card,
.skai-os-store-card,
.skai-os-shopping-card,
.skai-v18-home,
.skai-v18-card,
.skai-v20-chain-panel,
[data-testid="stVerticalBlockBorderWrapper"] {
    background:
        linear-gradient(145deg, rgba(255,255,255,0.145), rgba(255,255,255,0.065)) !important;
    border-color: rgba(255,255,255,0.19) !important;
    box-shadow: 0 22px 74px rgba(0,0,0,0.28), inset 0 1px 0 rgba(255,255,255,0.16) !important;
}

.skai-v18-home {
    min-height: 475px !important;
}

.skai-v18-title,
.skai-os-title {
    text-shadow: 0 0 42px rgba(49,247,255,0.22), 0 8px 30px rgba(0,0,0,0.28) !important;
}

.skai-v18-subtitle,
.skai-os-subtitle,
.skai-v18-card p,
.skai-v20-chain-panel p,
.skai-os-recipe-desc,
.skai-os-step span {
    color: rgba(255,255,255,0.80) !important;
}

.skai-v20-chain-chip,
.skai-v18-score,
.skai-v18-tile,
.skai-os-step,
.skai-os-mission-card {
    background: rgba(255,255,255,0.10) !important;
    border-color: rgba(255,255,255,0.17) !important;
}

[data-testid="stSidebar"] {
    background:
        radial-gradient(circle at 0% 0%, rgba(49,247,255,0.18), transparent 35%),
        linear-gradient(180deg, rgba(12,18,34,0.98), rgba(18,12,32,0.98)) !important;
}

[data-testid="stSidebar"] .stButton > button {
    background: rgba(255,255,255,0.09) !important;
    border-color: rgba(255,255,255,0.16) !important;
}

.skai-v19-nav-active {
    background:
        linear-gradient(90deg, rgba(49,247,255,0.30), rgba(157,255,122,0.21)),
        rgba(255,255,255,0.11) !important;
}

.stButton > button {
    box-shadow: 0 12px 36px rgba(49,247,255,0.20) !important;
}

[data-testid="stMetric"] {
    background:
        linear-gradient(145deg, rgba(49,247,255,0.16), rgba(255,79,216,0.10)) !important;
}

/* Make Radar less tall before useful content */
.skai-os-shell {
    margin-top: 0.05rem !important;
    margin-bottom: 0.55rem !important;
}

.skai-os-hero {
    min-height: 235px !important;
    padding: 0.95rem !important;
}

.skai-os-title {
    font-size: clamp(2rem, 4.1vw, 4.1rem) !important;
}

.skai-os-panel {
    padding: 0.82rem !important;
}

.skai-os-step {
    padding: 0.62rem !important;
    margin-bottom: 0.42rem !important;
}

.skai-os-step-number {
    min-width: 1.72rem !important;
    height: 1.72rem !important;
}

.skai-os-step span {
    font-size: 0.82rem !important;
}

.skai-v23-qa-safe {
    display: none;
}
</style>""", unsafe_allow_html=True)
st.markdown("""<style>
/* =========================================================
   SKAI v20 — Offer Intelligence + QA
   ========================================================= */

.skai-v20-chain-panel {
    margin: 0.8rem 0;
    padding: 1rem;
    border-radius: 26px;
    border: 1px solid rgba(255,255,255,0.15);
    background:
        linear-gradient(145deg, rgba(255,255,255,0.115), rgba(255,255,255,0.045));
    box-shadow: 0 22px 70px rgba(0,0,0,0.30), inset 0 1px 0 rgba(255,255,255,0.12);
}

.skai-v20-chain-panel > div:first-child span {
    color: #9dff7a;
    font-size: 0.72rem;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    font-weight: 1000;
}

.skai-v20-chain-panel > div:first-child strong {
    display: block;
    color: #ffffff !important;
    font-size: 1.22rem;
    margin-top: 0.18rem;
    letter-spacing: -0.04em;
}

.skai-v20-chain-panel > div:first-child p {
    color: rgba(255,255,255,0.72) !important;
    margin: 0.25rem 0 0 0 !important;
    font-weight: 760;
}

.skai-v20-chain-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0,1fr));
    gap: 0.58rem;
    margin-top: 0.75rem;
}

.skai-v20-chain-chip {
    padding: 0.72rem;
    border-radius: 18px;
    background: rgba(255,255,255,0.075);
    border: 1px solid rgba(255,255,255,0.13);
}

.skai-v20-chain-chip span {
    display: block;
    color: #31f7ff;
    font-size: 0.74rem;
    font-weight: 1000;
    letter-spacing: 0.12em;
    text-transform: uppercase;
}

.skai-v20-chain-chip strong {
    display: block;
    color: #fff !important;
    font-size: 1.65rem;
    line-height: 1;
    margin-top: 0.20rem;
}

.skai-v20-chain-chip p {
    color: rgba(255,255,255,0.78) !important;
    margin: 0.22rem 0 0 0 !important;
    font-weight: 820;
    font-size: 0.82rem;
}

.skai-v20-chain-chip small {
    display: block;
    margin-top: 0.25rem;
    color: rgba(255,255,255,0.52);
    font-size: 0.70rem;
    line-height: 1.2;
}

@media (max-width: 900px) {
    .skai-v20-chain-grid {
        grid-template-columns: 1fr;
    }
}
</style>""", unsafe_allow_html=True)
st.markdown("""<style>
/* =========================================================
   SKAI v19 — instant sidebar navigation
   ========================================================= */

.skai-v19-nav-title {
    margin: 0.85rem 0 0.35rem 0;
    color: rgba(255,255,255,0.48);
    font-size: 0.70rem;
    font-weight: 1000;
    letter-spacing: 0.16em;
    text-transform: uppercase;
}

.skai-v19-nav-active {
    display: flex;
    align-items: center;
    gap: 0.48rem;
    width: 100%;
    padding: 0.70rem 0.78rem;
    margin: 0.18rem 0 0.35rem 0;
    border-radius: 18px;
    background:
        linear-gradient(90deg, rgba(49,247,255,0.24), rgba(157,255,122,0.17)),
        rgba(255,255,255,0.08);
    border: 1px solid rgba(255,255,255,0.20);
    box-shadow: 0 16px 42px rgba(0,0,0,0.28), inset 0 1px 0 rgba(255,255,255,0.14);
}

.skai-v19-nav-active span {
    font-size: 1rem;
}

.skai-v19-nav-active strong {
    color: #ffffff !important;
    font-size: 0.92rem;
    font-weight: 1000;
}

[data-testid="stSidebar"] .stButton > button {
    justify-content: flex-start !important;
    min-height: 2.55rem !important;
    padding: 0.58rem 0.72rem !important;
    border-radius: 17px !important;
    background: rgba(255,255,255,0.07) !important;
    color: rgba(255,255,255,0.86) !important;
    border: 1px solid rgba(255,255,255,0.12) !important;
    box-shadow: none !important;
}

[data-testid="stSidebar"] .stButton > button:hover {
    background:
        linear-gradient(90deg, rgba(49,247,255,0.18), rgba(255,79,216,0.12)) !important;
    color: #ffffff !important;
    border-color: rgba(255,255,255,0.22) !important;
}
</style>""", unsafe_allow_html=True)
st.markdown("""<style>
/* =========================================================
   SKAI v18 — Home App Store Hero
   ========================================================= */

.skai-v18-home {
    position: relative;
    overflow: hidden;
    min-height: 520px;
    border-radius: 34px;
    padding: 1.35rem;
    border: 1px solid rgba(255,255,255,0.16);
    background:
        radial-gradient(circle at 11% 10%, rgba(49,247,255,0.28), transparent 30%),
        radial-gradient(circle at 90% 15%, rgba(255,79,216,0.24), transparent 34%),
        radial-gradient(circle at 55% 100%, rgba(157,255,122,0.16), transparent 34%),
        linear-gradient(135deg, rgba(255,255,255,0.12), rgba(255,255,255,0.04));
    box-shadow: 0 32px 110px rgba(0,0,0,0.42), inset 0 1px 0 rgba(255,255,255,0.16);
    backdrop-filter: blur(26px);
}

.skai-v18-home::before {
    content: "";
    position: absolute;
    inset: -45%;
    background:
        conic-gradient(from 160deg,
        rgba(49,247,255,0.0),
        rgba(49,247,255,0.16),
        rgba(255,79,216,0.18),
        rgba(157,255,122,0.13),
        rgba(49,247,255,0.0));
    animation: skaiSpin 18s linear infinite;
    opacity: 0.9;
}

.skai-v18-home-grid {
    position: relative;
    z-index: 1;
    display: grid;
    grid-template-columns: minmax(0, 1.05fr) minmax(330px, 0.95fr);
    gap: 1rem;
    align-items: stretch;
}

.skai-v18-kicker {
    display: inline-flex;
    align-items: center;
    padding: 0.38rem 0.62rem;
    border-radius: 999px;
    background: rgba(255,255,255,0.11);
    border: 1px solid rgba(255,255,255,0.16);
    color: #9dff7a;
    font-size: 0.74rem;
    font-weight: 1000;
    letter-spacing: 0.15em;
    text-transform: uppercase;
}

.skai-v18-title {
    margin-top: 0.95rem;
    color: #ffffff;
    font-size: clamp(3.1rem, 7vw, 6.6rem);
    line-height: 0.86;
    letter-spacing: -0.095em;
    font-weight: 1000;
    max-width: 780px;
    text-shadow: 0 0 45px rgba(49,247,255,0.18);
}

.skai-v18-subtitle {
    max-width: 760px;
    margin-top: 1rem;
    color: rgba(255,255,255,0.78);
    font-size: clamp(1.02rem, 1.6vw, 1.22rem);
    line-height: 1.35;
    font-weight: 790;
}

.skai-v18-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 0.6rem;
    margin-top: 1.05rem;
}

.skai-v18-primary,
.skai-v18-secondary {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-height: 2.65rem;
    padding: 0.72rem 1.05rem;
    border-radius: 999px;
    font-weight: 1000;
    letter-spacing: -0.02em;
    text-decoration: none !important;
}

.skai-v18-primary {
    color: #05060b !important;
    background: linear-gradient(90deg, #31f7ff, #9dff7a);
    box-shadow: 0 15px 45px rgba(49,247,255,0.26);
}

.skai-v18-secondary {
    color: #ffffff !important;
    background: rgba(255,255,255,0.10);
    border: 1px solid rgba(255,255,255,0.16);
}

.skai-v18-tiles {
    display: grid;
    grid-template-columns: 1fr;
    gap: 0.75rem;
}

.skai-v18-tile {
    padding: 1rem;
    min-height: 118px;
    border-radius: 25px;
    background:
        linear-gradient(145deg, rgba(255,255,255,0.14), rgba(255,255,255,0.055));
    border: 1px solid rgba(255,255,255,0.16);
    box-shadow: 0 22px 70px rgba(0,0,0,0.30);
    backdrop-filter: blur(22px);
}

.skai-v18-tile span {
    display: block;
    color: #31f7ff;
    font-size: 0.74rem;
    text-transform: uppercase;
    letter-spacing: 0.13em;
    font-weight: 1000;
}

.skai-v18-tile strong {
    display: block;
    margin-top: 0.25rem;
    color: #ffffff !important;
    font-size: 1.28rem;
    letter-spacing: -0.045em;
    line-height: 1.05;
}

.skai-v18-tile p {
    margin: 0.35rem 0 0 0 !important;
    color: rgba(255,255,255,0.72) !important;
    font-weight: 760;
}

.skai-v18-scorebar {
    display: grid;
    grid-template-columns: repeat(4, minmax(0,1fr));
    gap: 0.65rem;
    margin: 0.85rem 0 1rem 0;
}

.skai-v18-score {
    padding: 0.82rem;
    border-radius: 22px;
    background: rgba(255,255,255,0.09);
    border: 1px solid rgba(255,255,255,0.14);
    box-shadow: 0 18px 58px rgba(0,0,0,0.22);
}

.skai-v18-score span {
    color: rgba(255,255,255,0.62);
    font-size: 0.78rem;
    font-weight: 900;
}

.skai-v18-score strong {
    display: block;
    margin-top: 0.16rem;
    color: #ffffff !important;
    font-size: 1.55rem;
    line-height: 1;
    letter-spacing: -0.05em;
}

.skai-v18-section-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0,1fr));
    gap: 0.8rem;
    margin-top: 1rem;
}

.skai-v18-card {
    padding: 1rem;
    border-radius: 25px;
    background:
        linear-gradient(145deg, rgba(255,255,255,0.115), rgba(255,255,255,0.045));
    border: 1px solid rgba(255,255,255,0.14);
    box-shadow: 0 20px 62px rgba(0,0,0,0.26);
    min-height: 175px;
}

.skai-v18-card span {
    display: block;
    color: #9dff7a;
    font-size: 0.74rem;
    font-weight: 1000;
    letter-spacing: 0.13em;
    text-transform: uppercase;
    margin-bottom: 0.35rem;
}

.skai-v18-card strong {
    display: block;
    color: #ffffff !important;
    font-size: 1.28rem;
    line-height: 1.08;
    letter-spacing: -0.045em;
    margin-bottom: 0.35rem;
}

.skai-v18-card p {
    color: rgba(255,255,255,0.72) !important;
    font-weight: 760;
    margin: 0 !important;
}

.skai-v18-card button {
    margin-top: 0.65rem;
}

@media (max-width: 900px) {
    .skai-v18-home-grid,
    .skai-v18-scorebar,
    .skai-v18-section-grid {
        grid-template-columns: 1fr;
    }

    .skai-v18-home {
        min-height: auto;
    }
}
</style>""", unsafe_allow_html=True)
st.markdown("""<style>
/* =========================================================
   SKAI v17 — App Store Grade layer
   ========================================================= */

.skai-v17-brief {
    display: grid;
    grid-template-columns: minmax(0,1.4fr) repeat(3, minmax(120px,0.55fr));
    gap: 0.7rem;
    margin: 0.85rem 0;
}

.skai-v17-brief-main,
.skai-v17-brief-stat {
    border-radius: 22px;
    border: 1px solid rgba(255,255,255,0.14);
    background:
        linear-gradient(145deg, rgba(255,255,255,0.115), rgba(255,255,255,0.045));
    box-shadow: 0 18px 58px rgba(0,0,0,0.30), inset 0 1px 0 rgba(255,255,255,0.12);
    backdrop-filter: blur(22px);
    padding: 0.88rem;
}

.skai-v17-brief-main span {
    color: #9dff7a;
    font-size: 0.72rem;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    font-weight: 1000;
}

.skai-v17-brief-main strong {
    display: block;
    color: #fff !important;
    font-size: 1.35rem;
    letter-spacing: -0.045em;
    line-height: 1.05;
    margin-top: 0.18rem;
}

.skai-v17-brief-main p {
    margin: 0.35rem 0 0 0 !important;
    color: rgba(255,255,255,0.72) !important;
    font-weight: 760;
}

.skai-v17-brief-stat span {
    color: rgba(255,255,255,0.62);
    font-weight: 880;
    font-size: 0.78rem;
}

.skai-v17-brief-stat strong {
    display: block;
    color: #fff !important;
    margin-top: 0.22rem;
    font-size: 1.55rem;
    letter-spacing: -0.06em;
}

.skai-v17-tabbar {
    display: flex;
    flex-wrap: wrap;
    gap: 0.45rem;
    margin: 0.65rem 0 0 0;
}

.skai-v17-tabbar span {
    padding: 0.38rem 0.58rem;
    border-radius: 999px;
    background: rgba(255,255,255,0.09);
    border: 1px solid rgba(255,255,255,0.14);
    color: rgba(255,255,255,0.82);
    font-weight: 850;
    font-size: 0.80rem;
}

.skai-v17-store-pick {
    margin-top: 0.7rem;
    padding: 0.82rem;
    border-radius: 20px;
    background:
        linear-gradient(135deg, rgba(157,255,122,0.13), rgba(49,247,255,0.10));
    border: 1px solid rgba(157,255,122,0.24);
}

.skai-v17-store-pick span {
    display: block;
    color: #9dff7a;
    font-size: 0.70rem;
    font-weight: 1000;
    letter-spacing: 0.13em;
    text-transform: uppercase;
}

.skai-v17-store-pick strong {
    display: block;
    color: #fff !important;
    font-size: 1.05rem;
    margin-top: 0.25rem;
}

.skai-v17-store-pick p {
    margin: 0.28rem 0 0 0 !important;
    color: rgba(255,255,255,0.72) !important;
    font-weight: 760;
    font-size: 0.86rem;
}

.skai-v17-empty {
    padding: 1rem;
    border-radius: 24px;
    background:
        linear-gradient(145deg, rgba(255,179,92,0.12), rgba(255,255,255,0.045));
    border: 1px solid rgba(255,179,92,0.25);
    box-shadow: 0 20px 60px rgba(0,0,0,0.28);
}

.skai-v17-empty strong {
    color: #fff !important;
    display: block;
    font-size: 1.1rem;
    margin-bottom: 0.25rem;
}

.skai-v17-empty p {
    margin: 0 !important;
    color: rgba(255,255,255,0.73) !important;
    font-weight: 760;
}

.skai-os-hero {
    min-height: 280px !important;
    border-radius: 30px !important;
}

.skai-os-title {
    font-size: clamp(2.35rem, 5vw, 4.95rem) !important;
}

.skai-os-panel {
    border-radius: 30px !important;
}

.skai-os-step {
    border-radius: 20px !important;
}

.skai-os-shell {
    grid-template-columns: minmax(0, 1.2fr) minmax(320px, 0.8fr) !important;
}

[data-testid="stMetric"] {
    background:
        linear-gradient(145deg, rgba(49,247,255,0.12), rgba(255,79,216,0.08)) !important;
    border: 1px solid rgba(255,255,255,0.16) !important;
    border-radius: 20px !important;
}

.stButton > button {
    background: linear-gradient(90deg, #31f7ff, #9dff7a) !important;
    color: #05060b !important;
    border-radius: 999px !important;
    border: 0 !important;
    font-weight: 1000 !important;
}

@media (max-width: 900px) {
    .skai-v17-brief {
        grid-template-columns: 1fr;
    }

    .skai-os-shell {
        grid-template-columns: 1fr !important;
    }
}
</style>""", unsafe_allow_html=True)
st.markdown("""<style>
/* =========================================================
   SKAI v17 — Kitchen OS redesign
   ========================================================= */

:root {
    --skai-bg: #05060b;
    --skai-ink: #ffffff;
    --skai-muted: rgba(255,255,255,0.70);
    --skai-soft: rgba(255,255,255,0.10);
    --skai-line: rgba(255,255,255,0.15);
    --skai-cyan: #31f7ff;
    --skai-lime: #9dff7a;
    --skai-pink: #ff4fd8;
    --skai-orange: #ffb35c;
    --skai-blue: #6d7dff;
}

.stApp {
    background:
        radial-gradient(circle at 7% 7%, rgba(49,247,255,0.22), transparent 24%),
        radial-gradient(circle at 88% 12%, rgba(255,79,216,0.20), transparent 28%),
        radial-gradient(circle at 44% 92%, rgba(157,255,122,0.12), transparent 34%),
        linear-gradient(135deg, #05060b 0%, #0a1020 48%, #16071f 100%) !important;
}

.block-container {
    max-width: 1180px !important;
    padding-top: 0.45rem !important;
    padding-bottom: 4rem !important;
}

#MainMenu, footer, header { visibility: hidden; }

.skai-os-shell {
    display: grid;
    grid-template-columns: minmax(0, 1.12fr) minmax(320px, 0.88fr);
    gap: 1rem;
    align-items: stretch;
    margin: 0.2rem 0 0.75rem 0;
}

.skai-os-hero,
.skai-os-panel,
.skai-os-result-card,
.skai-os-store-card,
.skai-os-shopping-card,
.skai-os-warning-card {
    border-radius: 26px;
    border: 1px solid var(--skai-line);
    background:
        linear-gradient(145deg, rgba(255,255,255,0.118), rgba(255,255,255,0.045));
    box-shadow: 0 24px 80px rgba(0,0,0,0.34), inset 0 1px 0 rgba(255,255,255,0.13);
    backdrop-filter: blur(24px);
}

.skai-os-hero {
    position: relative;
    overflow: hidden;
    min-height: 310px;
    padding: 1.1rem;
}

.skai-os-hero:before {
    content: "";
    position: absolute;
    inset: -40%;
    background:
        conic-gradient(from 180deg, rgba(49,247,255,0.0), rgba(49,247,255,0.18), rgba(255,79,216,0.18), rgba(157,255,122,0.14), rgba(49,247,255,0.0));
    animation: skaiSpin 14s linear infinite;
    opacity: 0.75;
}

.skai-os-hero > * {
    position: relative;
    z-index: 1;
}

@keyframes skaiSpin {
    to { transform: rotate(360deg); }
}

.skai-os-kicker {
    display: inline-flex;
    padding: 0.36rem 0.58rem;
    border-radius: 999px;
    background: rgba(255,255,255,0.10);
    border: 1px solid rgba(255,255,255,0.16);
    color: var(--skai-lime);
    font-size: 0.72rem;
    font-weight: 1000;
    letter-spacing: 0.14em;
    text-transform: uppercase;
}

.skai-os-title {
    color: #fff;
    font-size: clamp(2.2rem, 5vw, 4.6rem);
    line-height: 0.90;
    letter-spacing: -0.085em;
    font-weight: 1000;
    max-width: 780px;
    margin-top: 0.75rem;
    text-shadow: 0 0 38px rgba(49,247,255,0.18);
}

.skai-os-subtitle {
    color: rgba(255,255,255,0.78);
    max-width: 760px;
    font-size: 1.02rem;
    font-weight: 780;
    margin-top: 0.8rem;
}

.skai-os-pill-row {
    display: flex;
    flex-wrap: wrap;
    gap: 0.45rem;
    margin-top: 1rem;
}

.skai-os-pill-row span,
.skai-os-mini-pill {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
    padding: 0.38rem 0.62rem;
    border-radius: 999px;
    background: rgba(255,255,255,0.10);
    border: 1px solid rgba(255,255,255,0.15);
    color: rgba(255,255,255,0.90);
    font-weight: 880;
    font-size: 0.82rem;
}

.skai-os-panel {
    padding: 1rem;
}

.skai-os-panel h3,
.skai-os-result-card h3,
.skai-os-shopping-card h3 {
    margin: 0 0 0.45rem 0 !important;
    color: #fff !important;
    letter-spacing: -0.04em !important;
}

.skai-os-step {
    display: flex;
    gap: 0.72rem;
    align-items: flex-start;
    padding: 0.78rem;
    border-radius: 18px;
    background: rgba(255,255,255,0.065);
    border: 1px solid rgba(255,255,255,0.11);
    margin-bottom: 0.55rem;
}

.skai-os-step-number {
    min-width: 2rem;
    height: 2rem;
    border-radius: 999px;
    display: grid;
    place-items: center;
    color: #05060b;
    background: linear-gradient(90deg, var(--skai-cyan), var(--skai-lime));
    font-weight: 1000;
}

.skai-os-step strong {
    color: #fff !important;
    display: block;
    margin-bottom: 0.1rem;
}

.skai-os-step span {
    color: rgba(255,255,255,0.72);
    font-weight: 760;
    font-size: 0.90rem;
}

.skai-os-mission-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0,1fr));
    gap: 0.75rem;
    margin: 0.35rem 0 0.95rem 0;
}

.skai-os-mission-card {
    padding: 0.82rem;
    border-radius: 20px;
    background: rgba(255,255,255,0.075);
    border: 1px solid rgba(255,255,255,0.14);
}

.skai-os-mission-card strong {
    color: #fff !important;
    display: block;
    font-size: 0.95rem;
    margin-bottom: 0.22rem;
}

.skai-os-mission-card span {
    color: rgba(255,255,255,0.70);
    font-size: 0.84rem;
    font-weight: 760;
}

.skai-os-result-grid {
    display: grid;
    grid-template-columns: minmax(0,1fr) minmax(0,1fr);
    gap: 0.9rem;
    margin-top: 0.9rem;
}

.skai-os-result-card,
.skai-os-shopping-card,
.skai-os-warning-card {
    padding: 1rem;
}

.skai-os-recipe-title {
    color: #fff;
    font-weight: 1000;
    font-size: 1.38rem;
    letter-spacing: -0.05em;
    line-height: 1.05;
    margin-bottom: 0.35rem;
}

.skai-os-recipe-desc {
    color: rgba(255,255,255,0.76);
    font-weight: 760;
    margin-bottom: 0.6rem;
}

.skai-os-ingredient-list {
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem;
    margin-top: 0.45rem;
}

.skai-os-ingredient-list span {
    padding: 0.30rem 0.48rem;
    border-radius: 999px;
    background: rgba(255,255,255,0.09);
    border: 1px solid rgba(255,255,255,0.11);
    color: rgba(255,255,255,0.85);
    font-size: 0.76rem;
    font-weight: 820;
}

.skai-os-map-grid {
    display: grid;
    grid-template-columns: minmax(0,1.5fr) minmax(300px,0.8fr);
    gap: 0.9rem;
    margin-top: 0.8rem;
}

.skai-os-store-card {
    padding: 0.82rem;
    margin-bottom: 0.55rem;
}

.skai-os-store-card strong {
    color: #fff !important;
    display: block;
    font-size: 0.92rem;
}

.skai-os-store-card span {
    color: rgba(255,255,255,0.66);
    font-weight: 760;
    font-size: 0.82rem;
}

.skai-os-warning-card {
    border-color: rgba(255,179,92,0.32);
    background:
        linear-gradient(145deg, rgba(255,179,92,0.15), rgba(255,255,255,0.05));
}

.skai-os-warning-card strong {
    color: #fff !important;
    display: block;
    margin-bottom: 0.25rem;
}

.skai-os-warning-card p {
    color: rgba(255,255,255,0.74) !important;
    margin: 0 !important;
    font-weight: 760;
}

.skai-os-command {
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    padding: 0.7rem 0.85rem;
    border-radius: 16px;
    background: rgba(0,0,0,0.32);
    border: 1px solid rgba(255,255,255,0.12);
    color: rgba(255,255,255,0.86);
    font-weight: 760;
}

.skai-offer-card {
    min-height: 230px;
    padding: 1rem;
    border-radius: 22px;
    background:
        linear-gradient(145deg, rgba(255,255,255,0.13), rgba(255,255,255,0.055)),
        radial-gradient(circle at 20% 0%, rgba(49,247,255,0.18), transparent 34%);
    border: 1px solid rgba(255,255,255,0.18);
    box-shadow: 0 20px 58px rgba(0,0,0,0.34), inset 0 1px 0 rgba(255,255,255,0.16);
    backdrop-filter: blur(20px);
    margin-bottom: 0.85rem;
}

.skai-offer-top {
    display: flex;
    justify-content: space-between;
    gap: 0.75rem;
    align-items: center;
    margin-bottom: 0.7rem;
}

.skai-offer-top span {
    font-size: 0.72rem;
    line-height: 1;
    padding: 0.38rem 0.52rem;
    border-radius: 999px;
    background: rgba(255,255,255,0.10);
    border: 1px solid rgba(255,255,255,0.16);
    color: rgba(255,255,255,0.86);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-weight: 900;
}

.skai-offer-price {
    font-size: 2.15rem;
    line-height: 1;
    letter-spacing: -0.055em;
    font-weight: 1000;
    color: #ffffff;
    text-shadow: 0 0 22px rgba(49,247,255,0.20);
    margin-bottom: 0.7rem;
}

.skai-offer-product {
    color: #ffffff;
    font-size: 1rem;
    line-height: 1.3;
    font-weight: 850;
    min-height: 3.6rem;
}

.skai-offer-match {
    margin-top: 0.85rem;
    color: rgba(157,255,122,0.92);
    font-weight: 850;
    font-size: 0.86rem;
}

/* Dropdown/selectbox hard fix */
[data-baseweb="select"],
[data-baseweb="select"] > div,
[data-baseweb="select"] div,
[data-testid="stSelectbox"] *,
[data-testid="stMultiSelect"] * {
    color: #ffffff !important;
    -webkit-text-fill-color: #ffffff !important;
}

[data-baseweb="select"] input {
    color: #ffffff !important;
    -webkit-text-fill-color: #ffffff !important;
}

[data-baseweb="popover"],
[data-baseweb="popover"] > div,
[data-baseweb="menu"],
[data-baseweb="menu"] *,
[role="listbox"],
[role="listbox"] *,
[role="option"],
[role="option"] * {
    background: #0b1022 !important;
    color: #ffffff !important;
    -webkit-text-fill-color: #ffffff !important;
}

/* Inputs */
[data-testid="stTextInput"] input,
[data-testid="stTextArea"] textarea {
    background: rgba(255,255,255,0.96) !important;
    color: #101225 !important;
    -webkit-text-fill-color: #101225 !important;
    border-radius: 15px !important;
    font-weight: 760 !important;
}

[data-testid="stTextInput"] input::placeholder,
[data-testid="stTextArea"] textarea::placeholder {
    color: rgba(16,18,37,0.52) !important;
    -webkit-text-fill-color: rgba(16,18,37,0.52) !important;
}

div[role="radiogroup"] label {
    min-height: 2.35rem !important;
    padding: 0.40rem 0.62rem !important;
    font-size: 0.86rem !important;
    border-radius: 999px !important;
}

[data-testid="stVerticalBlockBorderWrapper"],
[data-testid="stForm"] {
    border-radius: 22px !important;
}

.element-container {
    margin-bottom: 0.24rem !important;
}

iframe {
    min-height: 430px !important;
    border-radius: 22px !important;
}

@media (max-width: 900px) {
    .skai-os-shell,
    .skai-os-map-grid,
    .skai-os-result-grid,
    .skai-os-mission-grid {
        grid-template-columns: 1fr;
    }
}
</style>""", unsafe_allow_html=True)

st.markdown("""
<style>

/* =========================================================
   SKAI v14 — app-only premium overrides
   ========================================================= */

.skai-v14-hero {
    margin: 0.05rem 0 0.55rem 0;
    padding: 0.75rem 0.95rem;
    border-radius: 18px;
    background:
        linear-gradient(135deg, rgba(255,255,255,0.10), rgba(255,255,255,0.035)),
        radial-gradient(circle at 14% 0%, rgba(40,248,255,0.18), transparent 34%);
    border: 1px solid rgba(255,255,255,0.14);
    box-shadow: 0 20px 60px rgba(0,0,0,0.28);
    backdrop-filter: blur(22px);
}

.skai-v14-hero span {
    display: block;
    color: #5dffbf;
    font-size: 0.72rem;
    font-weight: 1000;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    margin-bottom: 0.15rem;
}

.skai-v14-hero h1 {
    margin: 0 !important;
    font-size: clamp(1.7rem, 3vw, 2.55rem) !important;
    line-height: 1 !important;
    letter-spacing: -0.065em !important;
}

.skai-v14-hero p {
    margin: 0.35rem 0 0 0 !important;
    color: rgba(255,255,255,0.78) !important;
    font-weight: 800;
    font-size: 0.92rem;
}

.skai-v14-mission {
    padding: 0.75rem;
    border-radius: 18px;
    background: rgba(255,255,255,0.055);
    border: 1px solid rgba(255,255,255,0.13);
}

.skai-v14-result-pill {
    display: inline-flex;
    gap: 0.4rem;
    align-items: center;
    padding: 0.35rem 0.58rem;
    border-radius: 999px;
    margin: 0.18rem 0.18rem 0.18rem 0;
    background: rgba(255,255,255,0.08);
    border: 1px solid rgba(255,255,255,0.14);
    color: rgba(255,255,255,0.88);
    font-weight: 850;
    font-size: 0.82rem;
}

.skai-v14-quality-card {
    padding: 0.85rem;
    border-radius: 18px;
    background:
        linear-gradient(135deg, rgba(255,184,107,0.14), rgba(255,255,255,0.055));
    border: 1px solid rgba(255,184,107,0.25);
    margin: 0.65rem 0;
}

.skai-v14-quality-card strong {
    color: #ffffff !important;
    display: block;
    margin-bottom: 0.25rem;
}

.skai-v14-quality-card p {
    margin: 0 !important;
    color: rgba(255,255,255,0.78) !important;
    font-weight: 760;
}

.skai-offer-card {
    min-height: 232px;
    padding: 1rem;
    border-radius: 22px;
    background:
        linear-gradient(145deg, rgba(255,255,255,0.13), rgba(255,255,255,0.055)),
        radial-gradient(circle at 20% 0%, rgba(40,248,255,0.18), transparent 34%);
    border: 1px solid rgba(255,255,255,0.18);
    box-shadow: 0 20px 58px rgba(0,0,0,0.34), inset 0 1px 0 rgba(255,255,255,0.16);
    backdrop-filter: blur(20px);
    margin-bottom: 0.85rem;
}

.skai-offer-top {
    display: flex;
    justify-content: space-between;
    gap: 0.75rem;
    align-items: center;
    margin-bottom: 0.7rem;
}

.skai-offer-top span {
    font-size: 0.72rem;
    line-height: 1;
    padding: 0.38rem 0.52rem;
    border-radius: 999px;
    background: rgba(255,255,255,0.10);
    border: 1px solid rgba(255,255,255,0.16);
    color: rgba(255,255,255,0.86);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-weight: 900;
}

.skai-offer-price {
    font-size: 2.15rem;
    line-height: 1;
    letter-spacing: -0.055em;
    font-weight: 1000;
    color: #ffffff;
    text-shadow: 0 0 22px rgba(40,248,255,0.20);
    margin-bottom: 0.7rem;
}

.skai-offer-product {
    color: #ffffff;
    font-size: 1rem;
    line-height: 1.3;
    font-weight: 850;
    min-height: 3.6rem;
}

.skai-offer-match {
    margin-top: 0.85rem;
    color: rgba(93,255,191,0.92);
    font-weight: 850;
    font-size: 0.86rem;
}

.skai-mini-deal {
    margin-top: 0.65rem;
    padding: 0.75rem;
    border-radius: 18px;
    background: rgba(255,255,255,0.075);
    border: 1px solid rgba(255,255,255,0.14);
}

.skai-mini-deal span {
    display: block;
    color: #5dffbf;
    text-transform: uppercase;
    font-weight: 1000;
    letter-spacing: 0.10em;
    font-size: 0.68rem;
}

.skai-mini-deal strong {
    display: block;
    color: #fff !important;
    margin-top: 0.2rem;
    font-size: 1rem;
}

.skai-mini-deal p {
    margin: 0.25rem 0 0 0 !important;
    color: rgba(255,255,255,0.76) !important;
    font-size: 0.82rem;
}

/* Dropdown/selectbox hard fix */
[data-baseweb="select"],
[data-baseweb="select"] > div,
[data-baseweb="select"] div,
[data-testid="stSelectbox"] *,
[data-testid="stMultiSelect"] * {
    color: #ffffff !important;
    -webkit-text-fill-color: #ffffff !important;
}

[data-baseweb="select"] input {
    color: #ffffff !important;
    -webkit-text-fill-color: #ffffff !important;
}

[data-baseweb="popover"],
[data-baseweb="popover"] > div,
[data-baseweb="menu"],
[data-baseweb="menu"] *,
[role="listbox"],
[role="listbox"] *,
[role="option"],
[role="option"] * {
    background: #0b1022 !important;
    color: #ffffff !important;
    -webkit-text-fill-color: #ffffff !important;
}

[role="option"]:hover,
[data-baseweb="menu"] li:hover {
    background: linear-gradient(90deg, rgba(40,248,255,0.24), rgba(255,79,216,0.18)) !important;
}

/* Keep text inputs readable */
[data-testid="stTextInput"] input,
[data-testid="stTextArea"] textarea {
    background: rgba(255,255,255,0.96) !important;
    color: #101225 !important;
    -webkit-text-fill-color: #101225 !important;
}

[data-testid="stTextInput"] input::placeholder,
[data-testid="stTextArea"] textarea::placeholder {
    color: rgba(16,18,37,0.54) !important;
    -webkit-text-fill-color: rgba(16,18,37,0.54) !important;
}

.block-container {
    max-width: 1120px !important;
    padding-top: 0.42rem !important;
}

.element-container {
    margin-bottom: 0.20rem !important;
}

[data-testid="stVerticalBlockBorderWrapper"],
[data-testid="stForm"] {
    border-radius: 18px !important;
}

div[role="radiogroup"] label {
    min-height: 2.18rem !important;
    padding: 0.36rem 0.58rem !important;
    font-size: 0.84rem !important;
}

iframe {
    min-height: 420px !important;
}

.stButton > button {
    min-height: 2.35rem !important;
    padding: 0.62rem 1rem !important;
}

</style>
""", unsafe_allow_html=True)


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



# =========================================================
# SKAI v19 Instant Sidebar Navigation
# =========================================================

PAGE_ICONS = {
    "Home": "🏠",
    "Crea SKiscetta": "🥗",
    "SKAI Radar": "⚡",
    "Ricette": "📚",
    "Lista spesa": "🛒",
    "Meal plan": "📅",
    "Preferiti": "⭐",
}

def page_slug_for_name(page_name):
    slug_map = {
        "Home": "home",
        "Crea SKiscetta": "crea",
        "SKAI Radar": "radar",
        "Ricette": "ricette",
        "Lista spesa": "lista",
        "Meal plan": "meal",
        "Preferiti": "preferiti",
    }
    return slug_map.get(page_name, normalize_for_match(page_name).replace(" ", "_"))


def go_to_page_now(page_name):
    st.session_state.page = page_name
    st.session_state.sidebar_page_active = page_name
    try:
        st.query_params["qa_page"] = page_slug_for_name(page_name)
    except Exception:
        pass
    st.rerun()


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

PAGE_SLUGS = {
    "home": "Home",
    "crea": "Crea SKiscetta",
    "radar": "SKAI Radar",
    "ricette": "Ricette",
    "lista": "Lista spesa",
    "meal": "Meal plan",
    "preferiti": "Preferiti",
}

try:
    qa_page = st.query_params.get("qa_page", None)
except Exception:
    qa_page = None

if isinstance(qa_page, list):
    qa_page = qa_page[0] if qa_page else None

if qa_page in PAGE_SLUGS:
    st.session_state.page = PAGE_SLUGS[qa_page]

try:
    skai_qa_fast = str(st.query_params.get("qa_fast", "")).lower() in ["1", "true", "yes"]
except Exception:
    skai_qa_fast = False

try:
    skai_qa_boot = str(st.query_params.get("qa_boot", "")).lower() in ["1", "true", "yes"]
except Exception:
    skai_qa_boot = False

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

st.sidebar.markdown('<div class="skai-v19-nav-title">Navigation</div>', unsafe_allow_html=True)

for page_name in pages:
    icon = PAGE_ICONS.get(page_name, "•")
    is_active = st.session_state.page == page_name

    if is_active:
        st.sidebar.markdown(
            f"""
            <div class="skai-v19-nav-active">
                <span>{icon}</span>
                <strong>{page_name}</strong>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        if st.sidebar.button(
            f"{icon} {page_name}",
            key=f"nav_{page_slug_for_name(page_name)}",
            use_container_width=True,
        ):
            go_to_page_now(page_name)

st.sidebar.divider()
st.sidebar.caption("Smart lunch planner")
st.sidebar.caption("SKAI · instant navigation")
st.sidebar.caption("Radar offerte live")
st.sidebar.caption(f"Ricette modulari create: {len(st.session_state.custom_recipes)}")


st.markdown(
    """
    <section class="skai-topbar">
        <div>
            <span class="skai-topbar-kicker">SKAI · Copilot Mode</span>
            <strong>SKiscettAI</strong>
        </div>
        <p>Dimmi cosa vuoi risolvere: SKiscetta, spesa settimanale o offerte vicino a te.</p>
    </section>
    """,
    unsafe_allow_html=True,
)

st.divider()






# =========================================================
# SKAI v17 App Store Grade Helpers
# =========================================================

def skai_v17_trust_level(clean_offers, raw_offers):
    clean = len(clean_offers or [])
    raw = len(raw_offers or [])

    if clean >= 8:
        return "alto", "feed offerte utile"
    if clean >= 3:
        return "medio", "alcune offerte leggibili"
    if raw > 0:
        return "protetto", "prezzi grezzi nascosti"
    return "pulito", "nessun dato sporco mostrato"


def skai_v17_best_store(nearby_stores, offers, user_lat, user_lon):
    if not nearby_stores:
        return None

    offer_chains = Counter(normalize_text(offer.get("chain", "")) for offer in offers or [])
    scored = []

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
        chain = infer_store_chain_v2(store, offer_sources_data) if "offer_sources_data" in globals() else store.get("chain", "")
        score = max(0, 20 - distance) + (offer_chains.get(normalize_text(chain), 0) * 2)
        scored.append((score, distance, store, chain))

    scored.sort(key=lambda item: (-item[0], item[1]))
    return scored[0] if scored else None


def skai_v17_mission_copy(mission, selected_items):
    count = len(selected_items or [])

    if mission == "Creo una SKiscetta":
        if count:
            return "Autopilot ricetta", f"Creo una proposta usando {count} ingredienti e alternative dal catalogo."
        return "Autopilot ricetta", "Scrivi 2-3 ingredienti: SKAI genererà una SKiscetta."

    if mission == "Organizzo la spesa settimanale":
        return "Autopilot spesa", "Costruisco piano ricette, lista ingredienti e controllo se ci sono offerte affidabili."

    return "Autopilot radar", "Controllo negozi vicini e mostro solo offerte con prodotto identificato."


def render_skai_v17_brief(mission, selected_items, nearby_stores, nearby_chains, offers_to_show, raw_web_offers):
    title, subtitle = skai_v17_mission_copy(mission, selected_items)
    trust, trust_label = skai_v17_trust_level(offers_to_show, raw_web_offers)

    st.markdown(
        f"""
        <div class="skai-v17-brief">
            <div class="skai-v17-brief-main">
                <span>{title}</span>
                <strong>{subtitle}</strong>
                <p>Un obiettivo, pochi input, risultato subito.</p>
                <div class="skai-v17-tabbar">
                    <span>mission-first</span>
                    <span>map-first</span>
                    <span>verified offers</span>
                    <span>weekly planner</span>
                </div>
            </div>
            <div class="skai-v17-brief-stat"><span>Negozi</span><strong>{len(nearby_stores or [])}</strong></div>
            <div class="skai-v17-brief-stat"><span>Catene</span><strong>{len(nearby_chains or [])}</strong></div>
            <div class="skai-v17-brief-stat"><span>Trust</span><strong>{trust}</strong><span>{trust_label}</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_skai_v17_store_pick(nearby_stores, offers_to_show, user_lat, user_lon):
    pick = skai_v17_best_store(nearby_stores, offers_to_show, user_lat, user_lon)

    if not pick:
        return

    score, distance, store, chain = pick

    st.markdown(
        f"""
        <div class="skai-v17-store-pick">
            <span>negozio consigliato ora</span>
            <strong>{store.get('name', 'Punto vendita')}</strong>
            <p>{chain or store.get('type', 'supermarket')} · {distance:.1f} km · scelto combinando distanza e dati offerta leggibili.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_skai_v17_no_offer_feed(raw_count):
    st.markdown(
        f"""
        <div class="skai-v17-empty">
            <strong>Niente offerte spazzatura.</strong>
            <p>SKAI ha nascosto {raw_count} prezzi non affidabili o senza prodotto chiaro. La lista spesa e la mappa restano utilizzabili.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )



# =========================================================
# SKAI v23 Offer Intelligence + Beta-Test Helpers
# =========================================================

def skai_v20_clean_offer_product(value):
    text_value = html.unescape(str(value or ""))
    text_value = re.sub(r"<[^>]+>", " ", text_value)
    text_value = re.sub(r"\bOFFERTE\b", " ", text_value, flags=re.I)
    text_value = re.sub(r"\bQUANTIT[ÀA]\s+LIMITATA\b", " ", text_value, flags=re.I)
    text_value = re.sub(r"\bSenza\s+\w+Card\b", " ", text_value, flags=re.I)
    text_value = re.sub(r"\bCon\s+\w+Card\b", " ", text_value, flags=re.I)
    text_value = re.sub(r"[-−]?\s*\d{1,2}\s*%", " ", text_value)
    text_value = re.sub(r"\bda\s+\w+\s+\d{1,2}[./]\d{1,2}[./]\d{2,4}.*", " ", text_value, flags=re.I)
    text_value = re.sub(r"\b\d{1,3}[,.]\d{2}\s*€", " ", text_value)
    text_value = re.sub(r"\s+", " ", text_value).strip(" -–—|•·:,;")
    text_value = skai_clean_product_title(text_value) if "skai_clean_product_title" in globals() else cleanup_product_candidate(text_value)
    return text_value[:96].strip()


def skai_v20_plain_text_candidates(raw, chain, url):
    """Extract product+price pairs from pages whose rendered/plain text contains flyer offers.
    This is especially useful for PENNY-like pages where the crawler-visible text is:
    Product · brand weight date validity price old-price unit-price.
    """
    text_body = re.sub(r"<script.*?</script>", " ", raw, flags=re.I | re.S)
    text_body = re.sub(r"<style.*?</style>", " ", text_body, flags=re.I | re.S)
    text_body = re.sub(r"<[^>]+>", " ", text_body)
    text_body = html.unescape(text_body)
    text_body = re.sub(r"\s+", " ", text_body).strip()

    candidates = []
    seen = set()

    # Pattern for flyers with validity dates.
    patterns = [
        re.compile(
            r"(?P<name>.{8,170}?)\s+da\s+\w+\s+\d{1,2}[./]\d{1,2}[./]\d{2,4}\s+a\s+\w+\s+\d{1,2}[./]\d{1,2}[./]\d{2,4}\s+(?P<price>\d{1,3}[,.]\d{2})\s*€",
            flags=re.I,
        ),
        re.compile(
            r"(?P<name>.{8,150}?)\s+(?:Senza\s+\w+Card|Con\s+\w+Card)\s+(?P<price>\d{1,3}[,.]\d{2})\s*€",
            flags=re.I,
        ),
        re.compile(
            r"(?P<name>[A-ZÀ-Ýa-zà-ÿ0-9][^€]{8,145}?)\s+(?P<price>\d{1,3}[,.]\d{2})\s*€(?:\s+\d{1,3}[,.]\d{2}\s*€)?",
            flags=re.I,
        ),
    ]

    for pattern in patterns:
        for match in pattern.finditer(text_body):
            raw_name = match.group("name")
            price = skai_v16_extract_price(match.group("price")) if "skai_v16_extract_price" in globals() else price_to_float(match.group("price"))
            name = skai_v20_clean_offer_product(raw_name)

            # Avoid giant chunks by taking the most product-like ending.
            if len(name.split()) > 12:
                tokens = name.split()
                for size in [8, 7, 6, 5]:
                    short = " ".join(tokens[-size:])
                    if skai_v16_product_score(short) >= 2:
                        name = short
                        break

            if not name or price is None:
                continue

            if "skai_v16_candidate_is_clean" in globals():
                profile = CHAIN_PARSER_PROFILES.get(chain, {})
                if not skai_v16_candidate_is_clean(name, chain, profile):
                    continue
            elif is_bad_offer_text(name):
                continue

            key = (normalize_text(name), round(float(price), 2), chain)
            if key in seen:
                continue

            seen.add(key)
            candidates.append(
                {
                    "product": name,
                    "snippet": name,
                    "price": round(float(price), 2),
                    "parser": "plain-text-flyer",
                    "source_url": url,
                }
            )

            if len(candidates) >= 50:
                return candidates

    return candidates


def skai_v20_parse_chain_offers(chain, url, raw):
    base = skai_v16_parse_chain_offers(chain, url, raw) if "skai_v16_parse_chain_offers" in globals() else []
    plain = skai_v20_plain_text_candidates(raw, chain, url)

    candidates = []
    seen = set()

    for item in list(base) + list(plain):
        product = skai_v20_clean_offer_product(item.get("product", ""))
        price = item.get("price")
        if not product or price is None:
            continue

        if "skai_v16_product_score" in globals() and skai_v16_product_score(product) < 2:
            continue

        key = (normalize_text(product), round(float(price), 2), chain)
        if key in seen:
            continue

        seen.add(key)
        new_item = dict(item)
        new_item["product"] = product
        new_item["price"] = round(float(price), 2)
        candidates.append(new_item)

    return candidates


def skai_v20_nearby_chain_names(nearby_stores, offer_sources):
    found = []

    for store in nearby_stores or []:
        chain = infer_store_chain_v2(store, offer_sources)
        if chain and chain != "Altro" and chain not in found:
            found.append(chain)

    priority = ["Coop", "Conad", "PAM", "PENNY", "Lidl", "Eurospin", "Carrefour", "MD", "Esselunga"]

    return sorted(
        found,
        key=lambda chain: priority.index(chain) if chain in priority else 99,
    )


def skai_v20_offer_counts_by_chain(offers):
    counts = Counter()

    for offer in offers or []:
        chain = offer.get("chain", "Web") or "Web"
        counts[chain] += 1

    return counts


def render_skai_v20_chain_coverage(nearby_stores, offer_sources, offers_to_show, parser_results):
    nearby_chains = skai_v20_nearby_chain_names(nearby_stores, offer_sources)
    counts = skai_v20_offer_counts_by_chain(offers_to_show)
    parser_map = {result.get("chain", ""): result for result in parser_results or []}

    chips = []

    if nearby_chains:
        for chain in nearby_chains:
            clean_count = counts.get(chain, 0)
            parser_message = parser_map.get(chain, {}).get("message", "Fonte non controllata in questa sessione.")
            status = "offerte verificate" if clean_count else "controllato · nessun prodotto verificato"

            chips.append(
                '<div class="skai-v20-chain-chip">'
                f'<span>{html.escape(str(chain))}</span>'
                f'<strong>{clean_count}</strong>'
                f'<p>{html.escape(status)}</p>'
                f'<small>{html.escape(str(parser_message))}</small>'
                '</div>'
            )
    else:
        chips.append(
            '<div class="skai-v20-chain-chip">'
            '<span>raggio selezionato</span>'
            '<strong>0</strong>'
            '<p>nessuna insegna riconosciuta</p>'
            '<small>La mappa resta attiva; aumenta il raggio o cambia CAP.</small>'
            '</div>'
        )

    html_block = (
        '<div class="skai-v20-chain-panel">'
        '<div>'
        '<span>catene nel raggio selezionato</span>'
        f'<strong>{len(nearby_chains)} insegne controllate</strong>'
        '<p>La mappa mostra tutti i supermercati trovati. Le card offerta appaiono solo se prodotto, prezzo e catena sono leggibili.</p>'
        '</div>'
        '<div class="skai-v20-chain-grid">'
        + ''.join(chips) +
        '</div>'
        '</div>'
    )

    st.markdown(html_block, unsafe_allow_html=True)


# =========================================================
# SKAI v28 Visual Flyer Fallback
# =========================================================

SHOPFULLY_PUBLICATION_IDS_V28 = {
    "Conad": "845643",
    "PAM": "842001",
    "Lidl": "846952",
    "Eurospin": "840074",
    "Esselunga": "846913",
    "MD": "837822",
}

STATIC_VISUAL_FLYERS_V28 = {
    "Coop": [
        {
            "url": "https://data.volantinofacile.it/pages/images/028/501/280/medium/page1.jpg?1775214225",
            "source": "VolantinoFacile",
        },
        {
            "url": "https://data.volantinofacile.it/pages/images/028/537/887/medium/page1.jpg?1775747845",
            "source": "VolantinoFacile",
        },
        {
            "url": "https://data.volantinofacile.it/pages/images/028/550/056/medium/page1.jpg?1776202654",
            "source": "VolantinoFacile",
        },
    ],
    "Carrefour": [
        {
            "url": "https://www.promoqui.it/volantino/carrefour",
            "source": "PromoQui",
            "is_link": True,
        }
    ],
    "PENNY": [
        {
            "url": "https://www.penny.it/offerte",
            "source": "PENNY ufficiale",
            "is_link": True,
        }
    ],
}


def skai_v28_visual_flyer_sources(chain, max_pages=3):
    chain = str(chain or "")
    sources = []

    publication_id = SHOPFULLY_PUBLICATION_IDS_V28.get(chain)
    if publication_id:
        for page_number in range(1, max_pages + 1):
            sources.append(
                {
                    "url": f"https://shopfully-publication-api.global.ssl.fastly.net/publication_pages/it_it/{publication_id}/{page_number}?format=webp",
                    "source": "ShopFully/DoveConviene",
                    "page": page_number,
                    "is_link": False,
                }
            )

    sources.extend(STATIC_VISUAL_FLYERS_V28.get(chain, []))
    return sources[:max_pages]


def skai_v28_chains_with_text_offers(offers):
    return {
        str(offer.get("chain", "") or "").strip()
        for offer in offers or []
        if offer.get("product_name") and offer.get("price") not in [None, ""]
    }


def skai_v28_visual_chains_for_radius(nearby_stores, offer_sources, offers_to_show):
    nearby = skai_v20_nearby_chain_names(nearby_stores, offer_sources)
    with_text = skai_v28_chains_with_text_offers(offers_to_show)
    result = []

    for chain in nearby:
        visual_sources = skai_v28_visual_flyer_sources(chain)
        if not visual_sources:
            continue
        result.append(
            {
                "chain": chain,
                "has_text_offers": chain in with_text,
                "sources": visual_sources,
            }
        )

    return result


def render_skai_v28_visual_flyers(nearby_stores, offer_sources, offers_to_show):
    visual_chains = skai_v28_visual_chains_for_radius(nearby_stores, offer_sources, offers_to_show)

    if not visual_chains:
        return

    st.markdown(
        """
        <div class="skai-v28-visual-panel">
            <span>volantini visuali</span>
            <strong>Offerte leggibili anche quando il sito non espone testo strutturato</strong>
            <p>Per alcune catene il prodotto+prezzo è dentro immagini/volantini. SKAI mostra la pagina del volantino invece di inventare card testuali non affidabili.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.expander("Apri volantini visuali delle catene nel raggio", expanded=False):
        for group in visual_chains:
            chain = group["chain"]
            label = "ha anche card testuali" if group["has_text_offers"] else "solo visuale affidabile ora"
            st.markdown(f"#### {chain} · {label}")

            cols = st.columns(3)
            for index, source in enumerate(group["sources"]):
                with cols[index % 3]:
                    url = source["url"]
                    page = source.get("page", index + 1)
                    source_name = source.get("source", "web")

                    if source.get("is_link"):
                        st.markdown(
                            f"""
                            <div class="skai-v28-link-card">
                                <span>{html.escape(chain)}</span>
                                <strong>{html.escape(source_name)}</strong>
                                <p>Apri il volantino/offerte direttamente dalla fonte.</p>
                                <a href="{html.escape(url)}" target="_blank">Apri fonte</a>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )
                    else:
                        st.image(
                            url,
                            caption=f"{chain} · pagina {page} · {source_name}",
                            use_container_width=True,
                        )


if st.session_state.page == "Home":
    planned_count = len(get_meal_plan_recipes(all_recipes))
    favorite_count = len(st.session_state.favorites)
    custom_count = len(st.session_state.custom_recipes)

    st.markdown(
        f"""
        <section class="skai-v18-home">
            <div class="skai-v18-home-grid">
                <div>
                    <div class="skai-v18-kicker">SKiscettAI · Kitchen OS</div>
                    <div class="skai-v18-title">Pranzo smart. Spesa furba. Zero caos.</div>
                    <div class="skai-v18-subtitle">
                        SKAI trasforma ingredienti casuali, offerte leggibili e supermercati vicini in una decisione semplice:
                        cosa mangiare, cosa comprare e dove andare.
                    </div>
                    <div class="skai-v18-actions">
                        <span class="skai-v18-primary">Apri SKAI Copilot</span>
                        <span class="skai-v18-secondary">Crea piano settimanale</span>
                        <span class="skai-v18-secondary">Controlla negozi vicini</span>
                    </div>
                    <div class="skai-v18-scorebar">
                        <div class="skai-v18-score"><span>Ricette</span><strong>{len(all_recipes)}</strong></div>
                        <div class="skai-v18-score"><span>Preferiti</span><strong>{favorite_count}</strong></div>
                        <div class="skai-v18-score"><span>Meal plan</span><strong>{planned_count}</strong></div>
                        <div class="skai-v18-score"><span>Create</span><strong>{custom_count}</strong></div>
                    </div>
                </div>
                <div class="skai-v18-tiles">
                    <div class="skai-v18-tile">
                        <span>01 · pantry intelligence</span>
                        <strong>Dimmi cosa hai in frigo.</strong>
                        <p>SKAI costruisce una SKiscetta veloce e alternative dal catalogo.</p>
                    </div>
                    <div class="skai-v18-tile">
                        <span>02 · weekly autopilot</span>
                        <strong>Organizza la settimana.</strong>
                        <p>Ricette, lista spesa e offerte verificate quando disponibili.</p>
                    </div>
                    <div class="skai-v18-tile">
                        <span>03 · trust filter</span>
                        <strong>Niente prezzi finti.</strong>
                        <p>Se il prodotto non è chiaro, il prezzo resta fuori dal feed principale.</p>
                    </div>
                </div>
            </div>
        </section>
        """,
        unsafe_allow_html=True,
    )

    st.write("")

    quick1, quick2, quick3 = st.columns(3)

    with quick1:
        with st.container(border=True):
            st.markdown(
                """
                <div class="skai-v18-card">
                    <span>Start here</span>
                    <strong>SKAI Copilot</strong>
                    <p>Il flusso principale: missione, zona, mappa, ricette, spesa e offerte pulite.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button("Apri Copilot", key="home_v18_open_copilot"):
                go_to("SKAI Radar")
                st.rerun()

    with quick2:
        with st.container(border=True):
            st.markdown(
                """
                <div class="skai-v18-card">
                    <span>Meal prep</span>
                    <strong>Piano settimanale</strong>
                    <p>Organizza pranzi, lista ingredienti e ricette salvate in pochi click.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button("Apri Meal plan", key="home_v18_open_meal"):
                go_to("Meal plan")
                st.rerun()

    with quick3:
        with st.container(border=True):
            st.markdown(
                """
                <div class="skai-v18-card">
                    <span>Explore</span>
                    <strong>Ricette</strong>
                    <p>Scopri il catalogo, salva preferiti e costruisci la tua base pranzo.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button("Esplora ricette", key="home_v18_open_recipes"):
                go_to("Ricette")
                st.rerun()

    st.write("")

    render_skai_section_label(
        "Featured flows",
        "Tre modi per usare SKAI oggi.",
        "Meno dashboard, più decisioni pronte."
    )

    flow_cols = st.columns(3)

    flows = [
        ("ingredienti → ricetta", "Scrivi pollo, riso, zucchine. SKAI crea la SKiscetta."),
        ("ricette → lista spesa", "Scegli i giorni, ottieni ingredienti aggregati."),
        ("negozi → fiducia", "Mappa vicina e offerte mostrate solo se il prodotto è chiaro."),
    ]

    for index, (title, subtitle) in enumerate(flows):
        with flow_cols[index]:
            st.markdown(
                f"""
                <div class="skai-v18-card">
                    <span>Flow {index + 1}</span>
                    <strong>{title}</strong>
                    <p>{subtitle}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

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
    current_recipes = combined_recipes()
    favorite_recipes = get_favorite_recipes(current_recipes)
    meal_plan_recipes = get_meal_plan_recipes(current_recipes)

    st.markdown(
        """
        <div class="skai-os-shell">
            <section class="skai-os-hero">
                <div class="skai-os-kicker">SKAI Kitchen OS</div>
                <div class="skai-os-title">Il tuo pranzo diventa un sistema operativo.</div>
                <div class="skai-os-subtitle">
                    Ingredienti, ricette, lista spesa, negozi e offerte verificate in un unico flusso. Se il prodotto non è chiaro, il prezzo non appare.
                </div>
                <div class="skai-os-pill-row">
                    <span>🥗 Pantry → recipe</span>
                    <span>🛒 Weekly plan</span>
                    <span>🗺️ Store radar</span>
                    <span>🛡️ verified prices</span><span>✨ App Store grade</span>
                </div>
            </section>
            <aside class="skai-os-panel">
                <h3>Come lavora SKAI</h3>
                <div class="skai-os-step">
                    <div class="skai-os-step-number">1</div>
                    <div><strong>Scegli il problema</strong><span>Ingredienti in casa, spesa settimanale o offerte vicine.</span></div>
                </div>
                <div class="skai-os-step">
                    <div class="skai-os-step-number">2</div>
                    <div><strong>SKAI semplifica</strong><span>Mostra pochi campi e nasconde la parte tecnica.</span></div>
                </div>
                <div class="skai-os-step">
                    <div class="skai-os-step-number">3</div>
                    <div><strong>Risultato leggibile</strong><span>Niente prezzi senza prodotto. Meglio meno dati, ma affidabili.</span></div>
                </div>
            </aside>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.container(border=True):
        st.markdown("### Mission Control")
        mission = st.radio(
            "Cosa vuoi ottenere?",
            [
                "Creo una SKiscetta",
                "Organizzo la spesa settimanale",
                "Controllo negozi e offerte",
            ],
            horizontal=True,
            label_visibility="collapsed",
            key="skai_v15_mission",
        )

        mission_col, input_col, zone_col = st.columns([0.9, 1.45, 0.85])

        with mission_col:
            st.markdown(
                """
                <div class="skai-os-mission-card">
                    <strong>Missione attiva</strong>
                    <span>SKAI cambia output in base al risultato scelto.</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
            focus = st.radio(
                "Stile",
                ["Veloce", "Low cost", "Proteica", "Light"],
                horizontal=False,
                key="skai_v15_focus",
            )

        pantry_items = []
        weekly_days = 5
        search_items = []

        with input_col:
            if mission == "Creo una SKiscetta":
                pantry_text = st.text_input(
                    "Ingredienti disponibili",
                    placeholder="pollo, riso, zucchine...",
                    key="skai_v15_pantry",
                )
                pantry_items = skai_parse_user_items(pantry_text)

            elif mission == "Organizzo la spesa settimanale":
                weekly_days = st.radio(
                    "Giorni",
                    [3, 4, 5],
                    horizontal=True,
                    key="skai_v15_days",
                )
                weekly_text = st.text_input(
                    "Ingredienti/preferenze",
                    placeholder="verdure, tonno, low cost...",
                    key="skai_v15_weekly",
                )
                search_items = skai_parse_user_items(weekly_text)

            else:
                search_text = st.text_input(
                    "Cosa vuoi cercare",
                    placeholder="pasta, caffè, yogurt, pollo...",
                    key="skai_v15_search",
                )
                search_items = skai_parse_user_items(search_text)

        with zone_col:
            cap = st.text_input("CAP", value="53100", key="skai_v15_cap")
            radius_km = st.select_slider(
                "Raggio",
                options=[2, 5, 10, 20, 30],
                value=5,
                format_func=lambda value: f"{value} km",
                key="skai_v15_radius",
            )

        with st.expander("Impostazioni tecniche", expanded=False):
            use_web_parsers = st.toggle("Leggi offerte web", value=True, key="skai_v15_web")
            max_web_offers = st.select_slider("Max offerte pulite", options=[6, 12, 20, 30], value=12, key="skai_v15_max_offers")

    selected_ingredients = pantry_items if mission == "Creo una SKiscetta" else search_items
    use_web_parsers = False if skai_qa_fast else st.session_state.get("skai_v15_web", True)
    max_web_offers = st.session_state.get("skai_v15_max_offers", 12)

    geocoded_location = geocode_postcode(cap, country="Italia")

    if geocoded_location:
        user_lat = geocoded_location["lat"]
        user_lon = geocoded_location["lon"]
        location_label = geocoded_location["display_name"]
    else:
        user_lat, user_lon = 43.3188, 11.3308
        location_label = "53100 Siena, Toscana, Italia"
        st.info("CAP non riconosciuto: uso Siena come fallback per non bloccarti.")

    with st.spinner("SKAI sta preparando ricette, mappa e dati puliti..."):
        if skai_qa_fast or skai_qa_boot:
            discovered_stores_raw = []
        else:
            try:
                discovered_stores_raw = fetch_osm_supermarkets(user_lat, user_lon, radius_km)
            except Exception:
                discovered_stores_raw = []
                st.info("Mappa live non disponibile: uso i punti vendita locali come fallback.")

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

        if use_web_parsers or skai_qa_boot:
            parser_chains = skai_parser_chain_candidates(
                nearby_stores,
                offer_sources_data,
                minimum=6,
            )

            if skai_qa_boot:
                parser_results = [
                    {
                        "chain": chain,
                        "ok": True,
                        "message": "QA boot: parser selection OK, external fetch skipped.",
                        "offers": [],
                    }
                    for chain in parser_chains
                ]
                web_offers = []
            else:
                parser_results, web_offers = fetch_multi_chain_offers_v1(
                    parser_chains,
                    offer_sources_data,
                    max_chains=6,
                )
        else:
            parser_chains = []
            parser_results = []
            web_offers = []

        clean_web_offers, raw_web_offers = split_offer_quality_v14(web_offers)
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

    st.write("")
    render_skai_v17_brief(mission, selected_ingredients, nearby_stores, nearby_chains, offers_to_show, raw_web_offers)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Negozi", len(nearby_stores))
    with c2:
        st.metric("Catene", len(nearby_chains))
    with c3:
        st.metric("Offerte pulite", len(offers_to_show))
    with c4:
        st.metric("Prezzi nascosti", len(raw_web_offers))

    render_skai_v20_chain_coverage(nearby_stores, offer_sources_data, offers_to_show, parser_results)
    render_skai_v28_visual_flyers(nearby_stores, offer_sources_data, offers_to_show)

    with st.container(border=True):
        st.markdown("### Radar negozi")
        map_col, store_col = st.columns([1.55, 0.9])

        with map_col:
            if MAP_AVAILABLE:
                stores_map = create_stores_map(
                    nearby_stores,
                    offers_to_show if offers_to_show else offers_nearby,
                    center_lat=user_lat,
                    center_lon=user_lon,
                )
                st_folium(stores_map, width=820, height=430)
            else:
                st.warning(f"Mappa non disponibile: {MAP_ERROR}")

        with store_col:
            st.caption(location_label)
            render_skai_store_cards(nearby_stores, user_lat, user_lon)
            render_skai_v17_store_pick(nearby_stores, offers_to_show, user_lat, user_lon)

    st.write("")

    if mission == "Creo una SKiscetta":
        st.markdown("## SKiscetta generata")

        if pantry_items:
            modular_recipe = generate_modular_recipe(
                modules,
                ", ".join(pantry_items),
                focus,
                "20 minuti",
                preferences="",
            )
            matches = skai_best_recipe_matches(current_recipes, pantry_items, focus, limit=4)

            if modular_recipe:
                with st.container(border=True):
                    st.markdown(f"### {modular_recipe.get('title', 'SKiscetta smart')}")
                    st.write(modular_recipe.get("description", ""))
                    st.caption("Ingredienti: " + ", ".join(modular_recipe.get("ingredients", [])[:8]))
                    if st.button("Salva questa SKiscetta", key="skai_v15_save_modular"):
                        upsert_custom_recipe(modular_recipe)
                        save_favorite(modular_recipe["id"])
                        st.success("Salvata nei preferiti.")

            st.markdown("### Alternative intelligenti")
            cols = st.columns(2)
            for index, recipe in enumerate(matches[:4]):
                with cols[index % 2]:
                    render_skai_recipe_card(recipe, reason="match ingredienti", save_key_prefix="v15_match")
                    if st.button("Salva", key=f"skai_v15_save_match_{recipe['id']}"):
                        save_favorite(recipe["id"])
                        st.success("Salvata.")
        else:
            st.markdown(
                """
                <div class="skai-os-warning-card">
                    <strong>Scrivi almeno 2-3 ingredienti.</strong>
                    <p>Esempio: pollo, riso, zucchine. SKAI genererà una ricetta e alternative dal catalogo.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

    elif mission == "Organizzo la spesa settimanale":
        st.markdown("## Piano spesa settimanale")

        plan = skai_make_week_plan(current_recipes, offers_to_show, days=weekly_days, focus=focus)

        if plan:
            cols = st.columns(2)
            for index, item in enumerate(plan):
                recipe = item["recipe"]
                day = WORK_DAYS[index] if index < len(WORK_DAYS) else f"Giorno {index + 1}"
                with cols[index % 2]:
                    render_skai_recipe_card(recipe, reason=f"{day} · {item['reason']}", save_key_prefix="v15_plan")

            if st.button("Salva nel Meal plan", key="skai_v15_save_plan"):
                for index, item in enumerate(plan):
                    if index < len(WORK_DAYS):
                        st.session_state[f"meal_{WORK_DAYS[index]}"] = item["recipe"].get("title", "Nessuna ricetta")
                st.success("Piano salvato nel Meal plan.")

            st.markdown("### Lista spesa intelligente")
            shopping_counter = skai_build_shopping_counter([item["recipe"] for item in plan], search_items)
            with st.container(border=True):
                render_skai_shopping_list(shopping_counter, offers_to_show)

    else:
        st.markdown("## Offerte identificate")

        if offers_to_show:
            card_cols = st.columns(3)
            for index, offer in enumerate(offers_to_show[:12]):
                with card_cols[index % 3]:
                    render_skai_offer_card(offer, index)
        else:
            render_skai_v17_no_offer_feed(len(raw_web_offers))
            render_skai_no_clean_offers(len(raw_web_offers))

    if mission != "Controllo negozi e offerte" and raw_web_offers and not offers_to_show:
        render_skai_no_clean_offers(len(raw_web_offers))

    with st.expander("Tecnico: parser e dati grezzi", expanded=False):
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
            st.caption("Offerte pulite")
            st.dataframe(pd.DataFrame(offer_rows(offers_to_show, stores_by_id, user_lat=user_lat, user_lon=user_lon)), use_container_width=True, hide_index=True)

        if raw_web_offers:
            st.caption("Prezzi nascosti perché senza prodotto chiaro")
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
