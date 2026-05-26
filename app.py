import json
from pathlib import Path

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


# -----------------------------
# Card ricetta Streamlit nativa
# -----------------------------

def recipe_card(recipe):
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
        if ingredients:
            st.write(", ".join(ingredients))
        else:
            st.write("-")

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
            st.markdown("### Tag")
            st.caption(" · ".join(tags))


# -----------------------------
# Motore ricerca ricette
# -----------------------------

def find_best_recipes(recipes, user_ingredients, goal):
    user_words = [
        normalize_text(word)
        for word in user_ingredients.replace(";", ",").split(",")
        if word.strip()
    ]

    scored = []

    for recipe in recipes:
        score = 0

        recipe_ingredients = normalize_text(" ".join(recipe.get("ingredients", [])))
        recipe_goal = normalize_text(recipe.get("goal", ""))
        recipe_tags = normalize_text(" ".join(recipe.get("tags", [])))
        recipe_title = normalize_text(recipe.get("title", ""))

        for word in user_words:
            if word in recipe_ingredients:
                score += 4
            if word in recipe_title:
                score += 2
            if word in recipe_tags:
                score += 1

        if normalize_text(goal) in recipe_goal:
            score += 3

        scored.append((score, recipe))

    scored.sort(key=lambda item: item[0], reverse=True)

    best = [item[1] for item in scored if item[0] > 0]

    if best:
        return best[:3]

    return recipes[:3]


# -----------------------------
# Caricamento dati
# -----------------------------

load_css("styles/custom.css")

recipes = load_json("data/recipes.json")
categories = load_json("data/categories.json")
tags = load_json("data/tags.json")


# -----------------------------
# Stato sessione
# -----------------------------

if "favorites" not in st.session_state:
    st.session_state.favorites = []

if "generated_recipe_ids" not in st.session_state:
    st.session_state.generated_recipe_ids = []

if "page" not in st.session_state:
    st.session_state.page = "Home"


# -----------------------------
# Sidebar
# -----------------------------

pages = [
    "Home",
    "Crea schiscetta",
    "Ricette",
    "Preferiti",
    "Meal plan"
]

st.sidebar.title("SchiscettAI")

selected_page = st.sidebar.radio(
    "Menu",
    pages,
    index=pages.index(st.session_state.page)
)

st.session_state.page = selected_page


# -----------------------------
# Header
# -----------------------------

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


# -----------------------------
# Home
# -----------------------------

if st.session_state.page == "Home":
    st.markdown("## Benvenuto in SchiscettAI")

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
                "Guarda il catalogo iniziale di ricette proteiche, vegetariane, "
                "economiche e veloci."
            )
            if st.button("Vai alle ricette"):
                go_to("Ricette")
                st.rerun()

    with col3:
        with st.container(border=True):
            st.markdown("### 🍱 Organizza")
            st.write(
                "Salva preferiti e prepara la tua settimana con un meal plan semplice."
            )
            if st.button("Crea meal plan"):
                go_to("Meal plan")
                st.rerun()

    st.info(f"Ricette disponibili nel database: {len(recipes)}")


# -----------------------------
# Crea schiscetta
# -----------------------------

elif st.session_state.page == "Crea schiscetta":
    st.markdown("## Crea la tua schiscetta")

    if not recipes:
        st.error(
            "Il database ricette non è stato caricato. Controlla che esista il file data/recipes.json."
        )

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
            matched_recipes = find_best_recipes(recipes, ingredienti, obiettivo)
            st.session_state.generated_recipe_ids = [
                recipe["id"] for recipe in matched_recipes
            ]

    if st.session_state.generated_recipe_ids:
        st.success("Ecco le idee più adatte alla tua schiscetta.")

        for recipe_id in st.session_state.generated_recipe_ids:
            recipe = get_recipe_by_id(recipes, recipe_id)

            if recipe:
                recipe_card(recipe)

                if st.button(
                    "Salva nei preferiti",
                    key=f"save_generated_{recipe['id']}"
                ):
                    save_favorite(recipe["id"])


# -----------------------------
# Catalogo ricette
# -----------------------------

elif st.session_state.page == "Ricette":
    st.markdown("## Catalogo ricette")

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
            "Meal prep"
        ]
    )

    if goal_filter == "Tutte":
        filtered_recipes = recipes
    else:
        filtered_recipes = [
            recipe for recipe in recipes
            if normalize_text(recipe.get("goal", "")) == normalize_text(goal_filter)
        ]

    st.write(f"Ricette trovate: {len(filtered_recipes)}")

    for recipe in filtered_recipes:
        recipe_card(recipe)

        if st.button(
            "Salva nei preferiti",
            key=f"save_catalog_{recipe['id']}"
        ):
            save_favorite(recipe["id"])


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
    else:
        for recipe in favorite_recipes:
            recipe_card(recipe)

            if st.button(
                "Rimuovi dai preferiti",
                key=f"remove_{recipe['id']}"
            ):
                st.session_state.favorites.remove(recipe["id"])
                st.rerun()


# -----------------------------
# Meal plan
# -----------------------------

elif st.session_state.page == "Meal plan":
    st.markdown("## Meal plan settimanale")

    with st.container(border=True):
        st.markdown("### Organizza la tua settimana")
        st.write(
            "Scegli una schiscetta per ogni giorno lavorativo. "
            "Questa è la prima versione del meal plan."
        )

    days = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì"]

    for day in days:
        st.selectbox(
            day,
            ["Nessuna ricetta"] + [recipe["title"] for recipe in recipes],
            key=f"meal_{day}"
        )