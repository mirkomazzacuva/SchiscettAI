import json
import re
from pathlib import Path
from collections import Counter, defaultdict

import streamlit as st


st.set_page_config(
    page_title="SchiscettAI",
    page_icon="🍱",
    layout="wide"
)


# -----------------------------
# Utility
# -----------------------------

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


def normalize_text(text):
    return str(text).strip().lower()


def parse_minutes(text):
    match = re.search(r"\d+", str(text))
    if match:
        return int(match.group())
    return 999


def extract_user_words(text):
    chunks = [
        normalize_text(chunk)
        for chunk in re.split(r"[,;]+", str(text))
        if chunk.strip()
    ]

    single_words = [
        normalize_text(word)
        for word in re.split(r"\s+", str(text))
        if len(word.strip()) >= 3
    ]

    return list(dict.fromkeys(chunks + single_words))


def go_to(page_name):
    st.session_state.page = page_name


def get_recipe_by_id(recipes, recipe_id):
    for recipe in recipes:
        if recipe.get("id") == recipe_id:
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


def all_goals(recipes):
    goals = sorted(
        {
            recipe.get("goal", "").strip()
            for recipe in recipes
            if recipe.get("goal", "").strip()
        }
    )
    return ["Tutte"] + goals


def all_categories(recipes):
    categories = sorted(
        {
            recipe.get("category", "").strip()
            for recipe in recipes
            if recipe.get("category", "").strip()
        }
    )
    return ["Tutte"] + categories


# -----------------------------
# Card ricetta Streamlit nativa
# -----------------------------

def recipe_card(recipe, button_mode=None, button_key_prefix="recipe"):
    with st.container(border=True):
        st.subheader(recipe.get("title", "Ricetta"))
        st.write(recipe.get("description", ""))

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

        st.markdown("### Procedimento")
        steps = recipe.get("steps", [])
        if steps:
            for index, step in enumerate(steps, start=1):
                st.write(f"{index}. {step}")
        else:
            st.write("-")

        st.markdown("### Valori indicativi")
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

        st.markdown("### Consigli")
        st.write(f"**Trasporto:** {recipe.get('transport_tip', '-')}")
        st.write(f"**Consiglio glamour:** {recipe.get('glamour_tip', '-')}")
        st.write(f"**Conservazione:** {recipe.get('storage_info', '-')}")

        tags = recipe.get("tags", [])
        if tags:
            st.caption(" · ".join(tags))

        recipe_id = recipe.get("id")

        if button_mode == "save":
            if st.button(
                "Salva nei preferiti",
                key=f"{button_key_prefix}_save_{recipe_id}"
            ):
                save_favorite(recipe_id)

        if button_mode == "remove":
            if st.button(
                "Rimuovi dai preferiti",
                key=f"{button_key_prefix}_remove_{recipe_id}"
            ):
                remove_favorite(recipe_id)
                st.rerun()


def compact_recipe_card(recipe, key_prefix):
    with st.container(border=True):
        st.markdown(f"### {recipe.get('title', 'Ricetta')}")
        st.write(recipe.get("description", ""))
        st.caption(
            f"{recipe.get('goal', '-')} · {recipe.get('prep_time', '-')} · "
            f"{recipe.get('estimated_cost', '-')}"
        )

        if st.button("Apri nel catalogo", key=f"{key_prefix}_{recipe.get('id')}"):
            go_to("Ricette")
            st.session_state.catalog_search = recipe.get("title", "")
            st.rerun()


# -----------------------------
# Motore ricerca ricette
# -----------------------------

def find_best_recipes(recipes, user_ingredients, goal, available_time):
    user_words = extract_user_words(user_ingredients)
    max_minutes = parse_minutes(available_time)

    scored = []

    for recipe in recipes:
        score = 0

        recipe_ingredients = normalize_text(" ".join(recipe.get("ingredients", [])))
        recipe_goal = normalize_text(recipe.get("goal", ""))
        recipe_tags = normalize_text(" ".join(recipe.get("tags", [])))
        recipe_title = normalize_text(recipe.get("title", ""))
        recipe_category = normalize_text(recipe.get("category", ""))
        recipe_time = parse_minutes(recipe.get("prep_time", ""))

        for word in user_words:
            if word and word in recipe_ingredients:
                score += 5
            if word and word in recipe_title:
                score += 2
            if word and word in recipe_tags:
                score += 1

        goal_norm = normalize_text(goal)

        if goal_norm == "svuota frigo":
            score += len(user_words)
        elif goal_norm in recipe_goal:
            score += 4
        elif goal_norm in recipe_tags or goal_norm in recipe_category:
            score += 2

        if recipe_time <= max_minutes:
            score += 2
        else:
            score -= 1

        scored.append((score, recipe))

    scored.sort(key=lambda item: item[0], reverse=True)

    best = [item[1] for item in scored if item[0] > 0]

    if best:
        return best[:3]

    return recipes[:3]


# -----------------------------
# Lista spesa
# -----------------------------

def get_meal_plan_recipe_ids():
    days = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì"]
    recipe_ids = []

    for day in days:
        recipe_id = st.session_state.get(f"meal_{day}", "")
        if recipe_id:
            recipe_ids.append(recipe_id)

    return recipe_ids


def build_shopping_list(selected_recipes):
    counter = Counter()
    sources = defaultdict(list)

    for recipe in selected_recipes:
        title = recipe.get("title", "Ricetta")
        for ingredient in recipe.get("ingredients", []):
            normalized = normalize_text(ingredient)
            counter[normalized] += 1
            sources[normalized].append(title)

    rows = []

    for ingredient, count in counter.most_common():
        rows.append(
            {
                "Ingrediente": ingredient,
                "Presente in ricette": count,
                "Ricette": ", ".join(sources[ingredient][:3])
            }
        )

    return rows


# -----------------------------
# Caricamento dati
# -----------------------------

load_css("styles/custom.css")

recipes = load_json("data/recipes.json")
categories = load_json("data/categories.json")
tags = load_json("data/tags.json")

recipes_by_id = {
    recipe.get("id"): recipe
    for recipe in recipes
    if recipe.get("id")
}


# -----------------------------
# Stato sessione
# -----------------------------

if "favorites" not in st.session_state:
    st.session_state.favorites = []

if "generated_recipe_ids" not in st.session_state:
    st.session_state.generated_recipe_ids = []

if "page" not in st.session_state:
    st.session_state.page = "Home"

if "catalog_search" not in st.session_state:
    st.session_state.catalog_search = ""


# -----------------------------
# Sidebar
# -----------------------------

pages = [
    "Home",
    "Crea schiscetta",
    "Ricette",
    "Preferiti",
    "Lista spesa",
    "Meal plan"
]

st.sidebar.title("🍱 SchiscettAI")

selected_page = st.sidebar.radio(
    "Menu",
    pages,
    index=pages.index(st.session_state.page)
)

st.session_state.page = selected_page

st.sidebar.divider()
st.sidebar.caption("MVP gratuito con Streamlit, GitHub e database locale.")
st.sidebar.metric("Ricette", len(recipes))
st.sidebar.metric("Preferiti", len(st.session_state.favorites))


# -----------------------------
# Header
# -----------------------------

st.title("🍱 SchiscettAI")
st.subheader("La schiscetta non è mai stata così smart.")

h1, h2, h3 = st.columns(3)

with h1:
    st.write("**La tua pausa pranzo intelligente**")

with h2:
    st.write("**Ricette smart per mangiare meglio ogni giorno**")

with h3:
    st.write("**Prepara, risparmia, gusta**")

st.write(
    "Trasforma quello che hai in frigo in una schiscetta bella, pratica e intelligente. "
    "Una web app gratuita, glamour e pensata per pranzi da portare al lavoro senza stress."
)

st.divider()


# -----------------------------
# Home
# -----------------------------

if st.session_state.page == "Home":
    st.markdown("## Benvenuto in SchiscettAI")

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.metric("Ricette disponibili", len(recipes))

    with c2:
        st.metric("Preferiti salvati", len(st.session_state.favorites))

    with c3:
        st.metric("Giorni meal plan", 5)

    with c4:
        st.metric("Costo app", "Gratis")

    st.write("")

    col1, col2, col3 = st.columns(3)

    with col1:
        with st.container(border=True):
            st.markdown("### 🥗 Crea")
            st.write(
                "Inserisci gli ingredienti che hai già e ricevi idee pratiche "
                "per la tua pausa pranzo."
            )
            if st.button("Crea la mia schiscetta"):
                go_to("Crea schiscetta")
                st.rerun()

    with col2:
        with st.container(border=True):
            st.markdown("### ✨ Esplora")
            st.write(
                "Sfoglia il catalogo, filtra per obiettivo e cerca ispirazioni "
                "proteiche, light, veloci o gourmet."
            )
            if st.button("Vai alle ricette"):
                go_to("Ricette")
                st.rerun()

    with col3:
        with st.container(border=True):
            st.markdown("### 🛒 Organizza")
            st.write(
                "Salva preferiti, costruisci il meal plan e genera una prima "
                "lista della spesa."
            )
            if st.button("Vai alla lista spesa"):
                go_to("Lista spesa")
                st.rerun()

    st.write("")
    st.markdown("## Ricette in evidenza")

    featured = recipes[:3]

    if featured:
        f1, f2, f3 = st.columns(3)
        columns = [f1, f2, f3]

        for index, recipe in enumerate(featured):
            with columns[index]:
                compact_recipe_card(recipe, key_prefix=f"featured_{index}")
    else:
        st.warning("Nessuna ricetta trovata nel database.")


# -----------------------------
# Crea schiscetta
# -----------------------------

elif st.session_state.page == "Crea schiscetta":
    st.markdown("## Crea la tua schiscetta")

    if not recipes:
        st.error(
            "Il database ricette non è stato caricato. Controlla che esista il file data/recipes.json."
        )

    left, right = st.columns([1, 1])

    with left:
        with st.form("schiscetta_form"):
            ingredienti = st.text_input(
                "Che ingredienti hai in casa?",
                placeholder="Esempio: pollo, riso, zucchine"
            )

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
                    "Meal prep"
                ]
            )

            tempo = st.selectbox(
                "Quanto tempo hai?",
                [
                    "10 minuti",
                    "20 minuti",
                    "30 minuti",
                    "45 minuti"
                ]
            )

            submitted = st.form_submit_button("Genera la mia schiscetta")

        if submitted:
            if not ingredienti.strip():
                st.warning("Inserisci almeno un ingrediente.")
            else:
                matched_recipes = find_best_recipes(
                    recipes,
                    ingredienti,
                    obiettivo,
                    tempo
                )
                st.session_state.generated_recipe_ids = [
                    recipe["id"] for recipe in matched_recipes
                ]

    with right:
        with st.container(border=True):
            st.markdown("### Come ragiona SchiscettAI")
            st.write(
                "In questa versione gratuita il generatore confronta gli ingredienti "
                "che inserisci con il database locale e seleziona le ricette più coerenti."
            )
            st.write(
                "La logica considera ingredienti, obiettivo, tag e tempo disponibile."
            )
            st.caption(
                "Prossimo upgrade: motore modulare base + proteina + verdura + salsa + topping."
            )

    if st.session_state.generated_recipe_ids:
        st.success("Ecco le idee più adatte alla tua schiscetta.")

        for recipe_id in st.session_state.generated_recipe_ids:
            recipe = get_recipe_by_id(recipes, recipe_id)

            if recipe:
                recipe_card(
                    recipe,
                    button_mode="save",
                    button_key_prefix="generated"
                )


# -----------------------------
# Catalogo ricette
# -----------------------------

elif st.session_state.page == "Ricette":
    st.markdown("## Catalogo ricette")

    filter_col1, filter_col2, filter_col3 = st.columns([1.2, 1, 1])

    with filter_col1:
        search = st.text_input(
            "Cerca ricetta o ingrediente",
            value=st.session_state.catalog_search,
            placeholder="Esempio: pollo, couscous, feta..."
        )
        st.session_state.catalog_search = search

    with filter_col2:
        goal_filter = st.selectbox(
            "Obiettivo",
            all_goals(recipes)
        )

    with filter_col3:
        category_filter = st.selectbox(
            "Categoria",
            all_categories(recipes)
        )

    filtered_recipes = recipes

    if search.strip():
        search_norm = normalize_text(search)
        filtered_recipes = [
            recipe for recipe in filtered_recipes
            if search_norm in normalize_text(recipe.get("title", ""))
            or search_norm in normalize_text(recipe.get("description", ""))
            or search_norm in normalize_text(" ".join(recipe.get("ingredients", [])))
            or search_norm in normalize_text(" ".join(recipe.get("tags", [])))
        ]

    if goal_filter != "Tutte":
        filtered_recipes = [
            recipe for recipe in filtered_recipes
            if normalize_text(recipe.get("goal", "")) == normalize_text(goal_filter)
        ]

    if category_filter != "Tutte":
        filtered_recipes = [
            recipe for recipe in filtered_recipes
            if normalize_text(recipe.get("category", "")) == normalize_text(category_filter)
        ]

    st.write(f"Ricette trovate: {len(filtered_recipes)}")

    show_limit = st.slider(
        "Quante ricette vuoi visualizzare?",
        min_value=6,
        max_value=min(60, max(6, len(filtered_recipes))),
        value=min(12, max(6, len(filtered_recipes))),
        step=6
    )

    for recipe in filtered_recipes[:show_limit]:
        recipe_card(
            recipe,
            button_mode="save",
            button_key_prefix="catalog"
        )

    if len(filtered_recipes) > show_limit:
        st.info(
            f"Stai vedendo {show_limit} ricette su {len(filtered_recipes)}. "
            "Usa ricerca e filtri per restringere i risultati."
        )


# -----------------------------
# Preferiti
# -----------------------------

elif st.session_state.page == "Preferiti":
    st.markdown("## Le tue ricette preferite")

    favorite_recipes = [
        recipe for recipe in recipes
        if recipe.get("id") in st.session_state.favorites
    ]

    if not favorite_recipes:
        st.info("Non hai ancora salvato ricette preferite.")
        if st.button("Vai al catalogo"):
            go_to("Ricette")
            st.rerun()
    else:
        st.success(f"Hai {len(favorite_recipes)} ricette preferite.")

        if st.button("Crea lista spesa dai preferiti"):
            go_to("Lista spesa")
            st.rerun()

        for recipe in favorite_recipes:
            recipe_card(
                recipe,
                button_mode="remove",
                button_key_prefix="favorite"
            )


# -----------------------------
# Lista spesa
# -----------------------------

elif st.session_state.page == "Lista spesa":
    st.markdown("## Lista della spesa")

    meal_plan_ids = get_meal_plan_recipe_ids()

    source = st.radio(
        "Da quali ricette vuoi generare la lista?",
        [
            "Preferiti",
            "Meal plan",
            "Preferiti + Meal plan"
        ],
        horizontal=True
    )

    selected_ids = []

    if source in ["Preferiti", "Preferiti + Meal plan"]:
        selected_ids.extend(st.session_state.favorites)

    if source in ["Meal plan", "Preferiti + Meal plan"]:
        selected_ids.extend(meal_plan_ids)

    selected_ids = list(dict.fromkeys(selected_ids))

    selected_recipes = [
        recipes_by_id[recipe_id]
        for recipe_id in selected_ids
        if recipe_id in recipes_by_id
    ]

    if not selected_recipes:
        st.info(
            "Non ci sono ancora ricette selezionate. Salva qualche ricetta nei preferiti "
            "o compila il meal plan."
        )

        col_a, col_b = st.columns(2)

        with col_a:
            if st.button("Vai alle ricette"):
                go_to("Ricette")
                st.rerun()

        with col_b:
            if st.button("Vai al meal plan"):
                go_to("Meal plan")
                st.rerun()

    else:
        st.success(
            f"Lista generata da {len(selected_recipes)} ricette selezionate."
        )

        shopping_rows = build_shopping_list(selected_recipes)

        st.markdown("### Ingredienti da controllare o acquistare")

        for row in shopping_rows:
            item = row["Ingrediente"]
            count = row["Presente in ricette"]
            recipe_names = row["Ricette"]

            checked = st.checkbox(
                f"{item}  — presente in {count} ricetta/e",
                key=f"shopping_{item}"
            )

            if recipe_names:
                st.caption(f"Usato in: {recipe_names}")

        st.markdown("### Ricette considerate")

        for recipe in selected_recipes:
            st.write(f"- {recipe.get('title', 'Ricetta')}")

        export_text = "Lista spesa SchiscettAI\n\n"
        for row in shopping_rows:
            export_text += f"- {row['Ingrediente']} ({row['Presente in ricette']} ricetta/e)\n"

        st.download_button(
            "Scarica lista spesa in TXT",
            data=export_text,
            file_name="lista_spesa_schiscettai.txt",
            mime="text/plain"
        )


# -----------------------------
# Meal plan
# -----------------------------

elif st.session_state.page == "Meal plan":
    st.markdown("## Meal plan settimanale")

    with st.container(border=True):
        st.markdown("### Organizza la tua settimana")
        st.write(
            "Scegli una schiscetta per ogni giorno lavorativo. "
            "Poi passa alla Lista spesa per aggregare gli ingredienti."
        )

    days = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì
