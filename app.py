import json
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
    page_title="SchiscettAI",
    page_icon="🍱",
    layout="wide",
)


WORK_DAYS = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì"]

REMOTE_OFFERS_CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQADckMEswns4YcXqZyqaUxh_6YCPrFuPzLL3xJlg9UH6lBVtBJhk0T0RmK4aqLIucK1VV0XFCArepX/pub?gid=1684172085&single=true&output=csv"

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
                        "Chrome/125.0 Safari/537.36 SchiscettAI/1.0"
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
        "Non ho trovato un URL CSV valido tra le varianti provate. "
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
                "Non riesco a leggere il Google Sheet pubblicato. "
                f"Uso il CSV locale o il JSON di fallback. Dettaglio: {error}"
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
                "title": cluster.get("name", "Schiscetta smart"),
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

    lines = ["Lista della spesa SchiscettAI", ""]

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

        rows.append(
            {
                "ingrediente": offer.get("ingredient", ""),
                "prodotto": offer.get("product_name", ""),
                "prezzo": f"{offer.get('price', '')} {offer.get('unit', '')}",
                "prima": f"{offer.get('old_price', '')} {offer.get('unit', '')}",
                "negozio": store.get("name", offer.get("store_id", "")),
                "zona": store.get("area", ""),
                "distanza_km": round(distance, 1) if distance is not None else "",
                "note": offer.get("notes", ""),
            }
        )

    return rows



def parse_price(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None



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

    try:
        response = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={
                "postalcode": clean_postcode,
                "country": country,
                "format": "json",
                "limit": 1,
                "addressdetails": 1,
            },
            headers={
                "User-Agent": "SchiscettAI-demo/1.0 (Streamlit app; contact: demo)"
            },
            timeout=8,
        )

        if response.status_code != 200:
            return None

        data = response.json()

        if not data:
            return None

        result = data[0]

        return {
            "lat": float(result["lat"]),
            "lon": float(result["lon"]),
            "display_name": result.get("display_name", f"CAP {clean_postcode}"),
        }

    except Exception:
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
        headers={"User-Agent": "SchiscettAI-demo/1.0"},
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
        return nearby_manual, "Fallback manuale"

    return manual_stores, "Fallback manuale completo"



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
            "title": recipe.get("category", "Schiscetta smart"),
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
        "title_template": "Schiscetta smart con {base}, {protein} e {vegetable}",
        "description": "Una schiscetta semplice, pratica e pensata per la pausa pranzo.",
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
        "Schiscetta smart con {base}, {protein} e {vegetable}",
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
            "Una schiscetta modulare, pratica e pensata per la pausa pranzo.",
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
            "title": "Schiscetta smart",
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
offers_data = load_offers_data(REMOTE_OFFERS_CSV_URL, "data/offers_template.csv", "data/offers.json")

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
    "Crea schiscetta",
    "Spesa smart",
    "Ricette",
    "Lista spesa",
    "Meal plan",
    "Preferiti",
]

st.sidebar.title("🍱 SchiscettAI")

selected_page = st.sidebar.radio(
    "Menu",
    pages,
    index=pages.index(st.session_state.page),
)

st.session_state.page = selected_page

st.sidebar.divider()
st.sidebar.caption("Smart lunch planner")
st.sidebar.caption("GitHub + Streamlit + database locale")
st.sidebar.caption("Offerte: Google Sheet + fonti web")
st.sidebar.caption(f"Ricette modulari create: {len(st.session_state.custom_recipes)}")


st.title("🍱 SchiscettAI")
st.subheader("La schiscetta non è mai stata così smart.")

st.write("**La tua pausa pranzo intelligente**")
st.write("**Ricette smart per mangiare meglio ogni giorno**")
st.write("**Prepara, risparmia, gusta**")

st.write(
    "Trasforma quello che hai in frigo in una schiscetta bella, pratica e intelligente. "
    "Una web app gratuita, glamour e pensata per pranzi da portare al lavoro senza stress."
)

st.divider()


if st.session_state.page == "Home":
    st.markdown("## Benvenuto in SchiscettAI")

    m1, m2, m3, m4 = st.columns(4)

    with m1:
        st.metric("Ricette", len(all_recipes))

    with m2:
        st.metric("Preferiti", len(st.session_state.favorites))

    with m3:
        planned_count = len(get_meal_plan_recipes(all_recipes))
        st.metric("Giorni pianificati", planned_count)

    with m4:
        st.metric("Modulari", len(st.session_state.custom_recipes))

    st.write("")

    col1, col2, col3 = st.columns(3)

    with col1:
        with st.container(border=True):
            st.markdown("### 🥗 Crea")
            st.write(
                "Inserisci gli ingredienti che hai già e ricevi sia ricette dal catalogo "
                "sia una nuova schiscetta modulare originale."
            )
            if st.button("Crea la mia schiscetta"):
                go_to("Crea schiscetta")
                st.rerun()

    with col2:
        with st.container(border=True):
            st.markdown("### 🛒 Spesa smart")
            st.write("Trova offerte vicino al tuo CAP e scopri quali schiscette convengono oggi.")
            if st.button("Vai a Spesa smart"):
                go_to("Spesa smart")
                st.rerun()

    with col3:
        with st.container(border=True):
            st.markdown("### ✨ Esplora")
            st.write("Filtra ricette, salva preferiti e costruisci il meal plan della settimana.")
            if st.button("Vai alle ricette"):
                go_to("Ricette")
                st.rerun()

    st.write("")
    st.markdown("## Mood schiscetta")

    cluster_items = list(cluster_groups.items())[:6]
    cluster_cols = st.columns(3)

    for index, (cluster_id, cluster_recipes) in enumerate(cluster_items):
        with cluster_cols[index % 3]:
            cluster_tile(cluster_id, recipes_count=len(cluster_recipes))

    st.write("")
    st.markdown("## Ricette in evidenza")

    featured = all_recipes[:3]

    if featured:
        fcols = st.columns(3)

        for index, recipe in enumerate(featured):
            with fcols[index % 3]:
                compact_recipe_preview(recipe, key_prefix="home_featured")


elif st.session_state.page == "Crea schiscetta":
    st.markdown("## Crea la tua schiscetta")

    if not all_recipes:
        st.error(
            "Il database ricette non è stato caricato. Controlla che esista il file data/recipes.json."
        )

    with st.container(border=True):
        st.markdown("### Generatore smart gratuito")
        st.write(
            "SchiscettAI ora fa due cose: cerca nel catalogo le ricette più vicine "
            "e crea anche una schiscetta modulare originale usando base + proteina + verdura + salsa + topping."
        )

    with st.form("schiscetta_form"):
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

        submitted = st.form_submit_button("Genera la mia schiscetta")

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
        st.success("Ecco la tua schiscetta modulare più le ricette più vicine dal catalogo.")

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
            file_name="lista_spesa_schiscettai.txt",
            mime="text/plain",
        )

        if st.button("Svuota ingredienti extra"):
            st.session_state.extra_shopping_items = []
            st.rerun()



elif st.session_state.page == "Spesa smart":
    st.markdown("## Spesa smart")

    st.info(
        "Beta Siena: inserisci il CAP, scegli il raggio e SchiscettAI incrocia ricette, lista spesa, negozi vicini e offerte lette dal Google Sheet."
    )

    current_recipes = combined_recipes()
    favorite_recipes = get_favorite_recipes(current_recipes)
    meal_plan_recipes = get_meal_plan_recipes(current_recipes)

    with st.container(border=True):
        st.markdown("### Fonte offerte")
        st.write("Le offerte sono lette automaticamente dal Google Sheet pubblicato.")
        st.caption("Cache automatica: circa ogni 30 minuti. Usa il bottone per forzare subito la rilettura.")
        st.code(REMOTE_OFFERS_CSV_URL)

        if st.button("Aggiorna offerte ora", key="refresh_offers_admin"):
            st.cache_data.clear()
            st.success("Cache svuotata. Rileggo subito le offerte dal Google Sheet.")
            st.rerun()

        source_col1, source_col2, source_col3 = st.columns(3)

        with source_col1:
            st.metric("Offerte caricate", len(offers_data))

        with source_col2:
            st.metric("Punti vendita", len(stores_data))

        with source_col3:
            st.metric("Fonte", "Google Sheet")

        if st.button("Aggiorna offerte ora", key="refresh_offers_top"):
            st.cache_data.clear()
            st.success("Cache svuotata. Rileggo subito le offerte dal Google Sheet.")
            st.rerun()

        if not offers_data:
            st.warning(
                "Non vedo offerte caricate. Controlla che il Google Sheet abbia intestazioni corrette "
                "e almeno una riga di offerte, poi clicca Aggiorna offerte ora."
            )

    with st.container(border=True):
        st.markdown("### Scegli cosa vuoi ottimizzare")

        recipe_titles = ["Nessuna ricetta"] + [
            recipe.get("title", "Ricetta") for recipe in current_recipes
        ]

        selected_recipe_title = st.selectbox(
            "Ricetta da collegare alle offerte",
            recipe_titles,
        )

        selected_recipe = get_recipe_by_title(current_recipes, selected_recipe_title)

        selected_ingredients = []

        if selected_recipe:
            selected_ingredients.extend(selected_recipe.get("ingredients", []))
            st.write("Ingredienti ricetta:")
            st.write(", ".join(selected_recipe.get("ingredients", [])))

        use_current_shopping = st.checkbox(
            "Includi lista spesa da preferiti e meal plan",
            value=True,
        )

        if use_current_shopping:
            shopping_counter_for_map = aggregate_ingredients(
                favorite_recipes + meal_plan_recipes,
                st.session_state.extra_shopping_items,
            )
            selected_ingredients.extend(list(shopping_counter_for_map.keys()))

            if shopping_counter_for_map:
                st.caption(
                    f"Aggiunti {len(shopping_counter_for_map)} ingredienti dalla lista spesa attuale."
                )

        manual_ingredient = st.text_input(
            "Oppure cerca un ingrediente",
            placeholder="Esempio: pollo, riso basmati, zucchine",
        )

        if manual_ingredient.strip():
            selected_ingredients.append(manual_ingredient.strip())

        selected_ingredients = sorted(set([item for item in selected_ingredients if str(item).strip()]))

    with st.container(border=True):
        st.markdown("### Punto di partenza")

        start_mode = st.radio(
            "Come vuoi posizionare la mappa?",
            [
                "Usa CAP",
                "Usa zona demo Siena",
            ],
            horizontal=True,
        )

        location_centers = {
            "Siena centro": (43.3188, 11.3308),
            "Stazione / PortaSiena": (43.3311, 11.3223),
            "San Miniato": (43.3405, 11.3502),
            "Massetana Romana": (43.3068, 11.3108),
        }

        user_lat, user_lon = (43.3188, 11.3308)
        location_label = "Siena centro"

        if start_mode == "Usa CAP":
            cap = st.text_input(
                "Inserisci CAP",
                value="53100",
                placeholder="Esempio: 53100",
            )

            geocoded_location = geocode_postcode(cap, country="Italia")

            if geocoded_location:
                user_lat = geocoded_location["lat"]
                user_lon = geocoded_location["lon"]
                location_label = geocoded_location["display_name"]
                st.success(f"Mappa centrata su: {location_label}")
            else:
                st.warning(
                    "Non sono riuscito a geolocalizzare il CAP. Uso Siena centro come fallback."
                )

        else:
            location_choice = st.selectbox(
                "Zona demo",
                [
                    "Siena centro",
                    "Stazione / PortaSiena",
                    "San Miniato",
                    "Massetana Romana",
                ],
            )

            user_lat, user_lon = location_centers.get(location_choice, (43.3188, 11.3308))
            location_label = location_choice

        radius_km = st.select_slider(
            "Raggio ricerca negozi",
            options=[2, 5, 10, 20, 30],
            value=30,
            format_func=lambda value: f"{value} km",
        )

        st.caption(
            "La geolocalizzazione del CAP usa Nominatim/OpenStreetMap con cache giornaliera. "
            "Per ora i punti vendita restano quelli demo caricati in data/stores.json."
        )

    try:
        discovered_stores_raw = fetch_osm_supermarkets(user_lat, user_lon, radius_km)
    except Exception as error:
        discovered_stores_raw = []
        st.warning(
            "Ricerca automatica supermercati non disponibile in questo momento. "
            f"Uso i punti vendita manuali come fallback. Dettaglio: {error}"
        )

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

    offers_nearby = offers_for_nearby_context(
        offers_data,
        nearby_stores,
        stores_by_id,
        offer_sources_data,
    )

    nearby_chains, offer_chains, common_chains = chain_match_summary(
        offers_data,
        nearby_stores,
        stores_by_id,
        offer_sources_data,
    )

    if selected_ingredients:
        matched_offers = offers_for_ingredients(offers_nearby, selected_ingredients)
        offers_to_show = matched_offers
    else:
        matched_offers = offers_nearby
        offers_to_show = offers_nearby

    st.write("")
    st.markdown("### Supermercati trovati nel raggio")

    s1, s2, s3, s4 = st.columns(4)

    with s1:
        st.metric("Punti vendita", len(nearby_stores))

    with s2:
        st.metric("Fonte negozi", stores_source_label)

    with s3:
        chains_count = len(set(store.get("chain_normalized", store.get("chain", "")) for store in nearby_stores))
        st.metric("Catene", chains_count)

    with s4:
        st.metric("Raggio", f"{radius_km} km")

    source_rows = offer_sources_for_stores(nearby_stores, offer_sources_data)

    if source_rows:
        with st.expander("Fonti offerte per le catene trovate", expanded=False):
            st.dataframe(pd.DataFrame(source_rows), use_container_width=True, hide_index=True)

    if nearby_chains:
        st.caption("Catene trovate nel raggio: " + ", ".join(nearby_chains[:12]))

    if offer_chains:
        st.caption("Catene presenti nelle offerte caricate: " + ", ".join(offer_chains[:12]))

    if offers_data and not offers_nearby:
        st.warning(
            "Le offerte sono caricate, ma non corrispondono ai negozi trovati nel raggio. "
            "Mostro comunque tutte le offerte manuali sotto come fallback."
        )

    st.write("")
    st.markdown("### Offerte attive")

    o1, o2, o3, o4 = st.columns(4)

    with o1:
        st.metric("Offerte Google Sheet", len(offers_data))

    with o2:
        st.metric("Negozi nel raggio", len(nearby_stores))

    with o3:
        st.metric("Offerte nel raggio", len(offers_nearby))

    with o4:
        st.metric("Offerte collegate", len(matched_offers))

    if not offers_data:
        st.warning(
            "Non sto leggendo offerte dal Google Sheet. Apri Admin offerte e clicca Aggiorna offerte ora; "
            "se resta vuoto, controlla che il foglio pubblicato abbia intestazioni e righe compilate."
        )

    map_col, info_col = st.columns([1.4, 1])

    with map_col:
        st.markdown("### Mappa punti vendita")

        if MAP_AVAILABLE:
            stores_map = create_stores_map(
                nearby_stores,
                offers_to_show if "offers_to_show" in locals() and offers_to_show else offers_nearby,
                center_lat=user_lat,
                center_lon=user_lon,
            )
            st_folium(stores_map, width=760, height=520)
        else:
            st.warning(f"Mappa non disponibile: {MAP_ERROR}")

    with info_col:
        st.markdown("### Negozi più vicini")

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

        st.caption(f"Punti vendita nel raggio: {len(nearest_rows)}")

        for distance, store in nearest_rows[:6]:
            with st.container(border=True):
                st.markdown(f"**{store.get('name', '')}**")
                st.caption(f"{store.get('type', '')} · {store.get('area', '')}")
                st.write(store.get("address", ""))
                st.write(f"Distanza indicativa: {distance:.1f} km")

    st.write("")
    st.markdown("### Offerte visibili")

    if selected_ingredients:
        st.caption("Ingredienti considerati: " + ", ".join(selected_ingredients))
        offers_to_show = matched_offers
    else:
        st.caption("Nessuna ricetta/ingrediente selezionato: mostro tutte le offerte nel raggio.")
        offers_to_show = offers_nearby

    if not offers_to_show and offers_nearby:
        st.warning(
            "Nessuna offerta collegata agli ingredienti selezionati. "
            "Mostro comunque tutte le offerte nel raggio."
        )
        offers_to_show = offers_nearby

    if not offers_to_show and offers_data:
        st.warning(
            "Nessuna offerta associata alle catene nel raggio. "
            "Mostro tutte le offerte caricate come fallback, così puoi verificare subito i dati."
        )
        offers_to_show = offers_data

    if not offers_to_show:
        st.warning(
            "Nessuna offerta visibile. Clicca Aggiorna offerte ora o controlla il CSV pubblicato."
        )
    else:
        rows = offer_rows(offers_to_show, stores_by_id, user_lat=user_lat, user_lon=user_lon)
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        with st.expander("Vedi tutte le offerte caricate dal Google Sheet", expanded=False):
            all_rows = offer_rows(offers_data, stores_by_id, user_lat=user_lat, user_lon=user_lon)
            st.dataframe(pd.DataFrame(all_rows), use_container_width=True, hide_index=True)

    st.write("")
    st.markdown("### Negozio migliore per la tua spesa")

    recommendations = best_store_recommendations(
        offers_to_show if "offers_to_show" in locals() and offers_to_show else offers_nearby,
        stores_by_id,
        selected_ingredients,
        user_lat,
        user_lon,
    )

    if not selected_ingredients:
        st.info("Seleziona una ricetta, usa la lista spesa o cerca un ingrediente per calcolare il negozio migliore.")
    elif not recommendations:
        st.warning("Non ci sono abbastanza offerte demo per calcolare un negozio consigliato.")
    else:
        best_store = recommendations[0]
        store = best_store["store"]

        with st.container(border=True):
            st.markdown(f"### 🏆 {store.get('name', '')}")
            st.write(
                f"Copre **{best_store['covered']} ingredienti** della tua lista "
                f"con offerte demo disponibili."
            )
            st.write(f"Zona: **{store.get('area', '')}**")
            st.write(f"Distanza indicativa: **{best_store['distance']} km**")
            st.write(
                f"Totale prezzi demo considerati: **{best_store['total_price']} €** "
                f"su {best_store['priced_items']} prodotti."
            )
            st.caption(
                "Il totale è indicativo: le unità sono miste (kg, pezzo, confezione). "
                "Serve per confrontare la convenienza demo, non come scontrino reale."
            )

        st.markdown("#### Alternative")

        for item in recommendations[1:4]:
            store = item["store"]
            with st.container(border=True):
                st.write(
                    f"**{store.get('name', '')}** — copre {item['covered']} ingredienti, "
                    f"distanza {item['distance']} km, totale demo {item['total_price']} €."
                )
                st.caption("Ingredienti coperti: " + ", ".join(item["ingredients"]))

    st.write("")
    st.markdown("### Ricette convenienti con le offerte attive")

    deal_recipes = best_deal_recipes(
        current_recipes,
        offers_to_show if "offers_to_show" in locals() and offers_to_show else offers_nearby,
        stores_by_id,
        limit=5,
    )

    if not deal_recipes:
        st.info(
            "Non ci sono ancora abbastanza offerte collegate agli ingredienti delle ricette. "
            "Aggiungi offerte nel Google Sheet per vedere suggerimenti migliori."
        )
    else:
        for item in deal_recipes:
            recipe = item["recipe"]
            stores_names = [
                stores_by_id.get(store_id, {}).get("name", store_id)
                for store_id in item["store_ids"]
            ]

            with st.container(border=True):
                st.markdown(f"#### {recipe.get('title', 'Ricetta')}")
                st.write(recipe.get("description", ""))
                st.write(
                    f"Ingredienti coperti da offerte: **{item['coverage']} su {item['total_ingredients']}**"
                )
                st.write(
                    "Ingredienti in offerta: "
                    + ", ".join(item["covered_ingredients"])
                )
                st.write(
                    f"Totale prezzi demo considerati: **{item['total_demo_price']} €** "
                    f"su {item['priced_items']} prodotti."
                )
                if stores_names:
                    st.caption("Punti vendita coinvolti: " + " · ".join(stores_names[:4]))

                if st.button(
                    "Salva questa ricetta",
                    key=f"deal_recipe_save_{recipe['id']}",
                ):
                    save_favorite(recipe["id"])


    with st.expander("Admin offerte", expanded=False):
        st.markdown("### Fonte offerte automatica")
        st.write("Google Sheet pubblicato come CSV:")
        st.code(REMOTE_OFFERS_CSV_URL)
        st.caption("Cache aggiornamento: circa ogni 30 minuti. Se le offerte non compaiono, premi il bottone qui sotto.")

        if st.button("Aggiorna offerte ora"):
            st.cache_data.clear()
            st.success("Cache svuotata. Rileggo subito le offerte dal Google Sheet.")
            st.rerun()

        st.markdown("### Come aggiornare le offerte")
        st.write(
            "1. Apri il Google Sheet **SchiscettAI offerte**.\n"
            "2. Inserisci le offerte dalla riga 2 in poi.\n"
            "3. Non cambiare i nomi delle colonne nella prima riga.\n"
            "4. Usa `store_id` identici a quelli presenti in `data/stores.json`.\n"
            "5. Attendi qualche minuto o clicca **Aggiorna offerte ora**."
        )

        st.download_button(
            "Scarica offerte attualmente caricate",
            data=offers_to_csv_text(offers_data),
            file_name="offers_attuali_schiscettai.csv",
            mime="text/csv",
        )

        issues = validate_offers(offers_data, stores_by_id)

        q1, q2, q3 = st.columns(3)

        with q1:
            st.metric("Offerte caricate", len(offers_data))

        with q2:
            st.metric("Punti vendita", len(stores_data))

        with q3:
            st.metric("Problemi trovati", len(issues))

        if not issues:
            st.success("Formato offerte OK.")
        else:
            st.warning("Sono stati trovati problemi da correggere nel Google Sheet.")
            st.dataframe(pd.DataFrame(issues), use_container_width=True, hide_index=True)

        st.markdown("### Store ID disponibili")

        stores_table = []

        for store in stores_data:
            stores_table.append(
                {
                    "store_id": store.get("id", ""),
                    "nome": store.get("name", ""),
                    "catena": store.get("chain", ""),
                    "tipo": store.get("type", ""),
                    "zona": store.get("area", ""),
                    "indirizzo": store.get("address", ""),
                }
            )

        if stores_table:
            st.dataframe(pd.DataFrame(stores_table), use_container_width=True, hide_index=True)


    st.write("")
    st.markdown("### Come evolverà questa funzione")
    st.write(
        "Ora usiamo Google Sheet/CSV aggiornabile. Il prossimo step sarà collegare volantini reali "
        "e fonti ufficiali o scraping controllato dove consentito."
    )




elif st.session_state.page == "Meal plan":
    st.markdown("## Meal plan settimanale")

    current_recipes = combined_recipes()

    with st.container(border=True):
        st.markdown("### Organizza la tua settimana")
        st.write(
            "Scegli una schiscetta per ogni giorno lavorativo. "
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
