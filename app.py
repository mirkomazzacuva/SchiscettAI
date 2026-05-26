import json
from pathlib import Path

import streamlit as st


st.set_page_config(
    page_title="SchiscettAI",
    page_icon="🍱",
    layout="wide"
)


def load_css(file_path):
    css_path = Path(file_path)
    if css_path.exists():
        st.markdown(
            f"<style>{css_path.read_text(encoding='utf-8')}</style>",
            unsafe_allow_html=True
        )


def load_json(file_path):
    path = Path(file_path)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return []


def recipe_card(recipe):
    tags_html = " ".join(
        [f"<span class='tag-pill'>{tag}</span>" for tag in recipe.get("tags", [])]
    )

    nutrition = recipe.get("nutrition", {})

    st.markdown(
        f"""
        <div class="schiscetta-card">
            <h2>{recipe.get("title", "Ricetta")}</h2>
            <p>{recipe.get("description", "")}</p>

            <p>
                <strong>Obiettivo:</strong> {recipe.get("goal", "-")} ·
                <strong>Tempo:</strong> {recipe.get("prep_time", "-")} ·
                <strong>Difficoltà:</strong> {recipe.get("difficulty", "-")} ·
                <strong>Costo:</strong> {recipe.get("estimated_cost", "-")}
            </p>

            <h3>Ingredienti</h3>
            <p>{", ".join(recipe.get("ingredients", []))}</p>

            <h3>Procedimento</h3>
            <ol>
                {"".join([f"<li>{step}</li>" for step in recipe.get("steps", [])])}
            </ol>

            <h3>Valori indicativi</h3>
            <p>
                {nutrition.get("calories", "-")} kcal ·
                Proteine {nutrition.get("protein", "-")} g ·
                Carboidrati {nutrition.get("carbs", "-")} g ·
                Grassi {nutrition.get("fat", "-")} g
            </p>

            <h3>Consigli</h3>
            <p><strong>Trasporto:</strong> {recipe.get("transport_tip", "-")}</p>
            <p><strong>Consiglio glamour:</strong> {recipe.get("glamour_tip", "-")}</p>
            <p><strong>Conservazione:</strong> {recipe.get("storage_info", "-")}</p>

            <div>{tags_html}</div>
        </div>
        """,
        unsafe_allow_html=True
    )


def find_best_recipes(recipes, user_ingredients, goal):
    user_words = [
        word.strip().lower()
        for word in user_ingredients.replace(";", ",").split(",")
        if word.strip()
    ]

    scored = []

    for recipe in recipes:
        score = 0
        recipe_ingredients = " ".join(recipe.get("ingredients", [])).lower()
        recipe_goal = recipe.get("goal", "").lower()
        recipe_tags = " ".join(recipe.get("tags", [])).lower()

        for word in user_words:
            if word in recipe_ingredients:
                score += 3
            if word in recipe_tags:
                score += 1

        if goal.lower() in recipe_goal:
            score += 2

        scored.append((score, recipe))

    scored.sort(key=lambda item: item[0], reverse=True)

    if scored and scored[0][0] > 0:
        return [item[1] for item in scored[:3]]

    return recipes[:3]


load_css("styles/custom.css")

recipes = load_json("data/recipes.json")
categories = load_json("data/categories.json")
tags = load_json("data/tags.json")

if "favorites" not in st.session_state:
    st.session_state.favorites = []


st.markdown(
    """
    <div class="hero-box">
        <h1>🍱 SchiscettAI</h1>
        <h3>La schiscetta non è mai stata così smart.</h3>
        <p><strong>La tua pausa pranzo intelligente</strong></p>
        <p><strong>Ricette smart per mangiare meglio ogni giorno</strong></p>
        <p><strong>Prepara, risparmia, gusta</strong></p>
        <p>
            Trasforma quello che hai in frigo in una schiscetta bella,
            pratica e intelligente. Una web app gratuita, glamour e pensata
            per pranzi da portare al lavoro senza stress.
        </p>
    </div>
    """,
    unsafe_allow_html=True
)

st.write("")

tab_home, tab_generator, tab_recipes, tab_favorites, tab_plan = st.tabs(
    [
        "Home",
        "Crea schiscetta",
        "Ricette",
        "Preferiti",
        "Meal plan"
    ]
)


with tab_home:
    st.markdown("## Benvenuto in SchiscettAI")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown(
            """
            <div class="schiscetta-card">
                <h3>🥗 Crea</h3>
                <p>
                    Inserisci gli ingredienti che hai già e ricevi idee
                    pratiche per la tua pausa pranzo.
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )

    with col2:
        st.markdown(
            """
            <div class="schiscetta-card">
                <h3>✨ Personalizza</h3>
                <p>
                    Scegli obiettivo, tempo disponibile e stile:
                    proteica, light, economica, veloce o gourmet.
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )

    with col3:
        st.markdown(
            """
            <div class="schiscetta-card">
                <h3>🍱 Organizza</h3>
                <p>
                    Esplora ricette, salva preferiti e prepara la settimana
                    con un meal plan semplice.
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )

    st.write("")
    st.markdown("## Ricette già disponibili")

    st.info(f"Al momento il database contiene {len(recipes)} ricette iniziali.")


with tab_generator:
    st.markdown("## Crea la tua schiscetta")

    col1, col2 = st.columns([1, 1])

    with col1:
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

        genera = st.button("Genera la mia schiscetta")

    with col2:
        st.markdown(
            """
            <div class="schiscetta-card">
                <h3>Come ragiona SchiscettAI</h3>
                <p>
                    Per ora usiamo un motore gratuito basato sul database locale:
                    l'app confronta gli ingredienti che inserisci con le ricette
                    disponibili e ti propone le combinazioni più adatte.
                </p>
                <p>
                    È il primo passo verso un generatore modulare più intelligente:
                    base + proteina + verdura + salsa + topping + stile.
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )

    if genera:
        if ingredienti:
            matched_recipes = find_best_recipes(recipes, ingredienti, obiettivo)

            st.success("Ecco le idee più adatte alla tua schiscetta.")

            for recipe in matched_recipes:
                recipe_card(recipe)

                if st.button(
                    "Salva nei preferiti",
                    key=f"save_generated_{recipe['id']}"
                ):
                    if recipe["id"] not in st.session_state.favorites:
                        st.session_state.favorites.append(recipe["id"])
                        st.success("Ricetta salvata nei preferiti.")
                    else:
                        st.info("Questa ricetta è già nei preferiti.")
        else:
            st.warning("Inserisci almeno un ingrediente.")


with tab_recipes:
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
            if recipe.get("goal", "").lower() == goal_filter.lower()
        ]

    st.write(f"Ricette trovate: {len(filtered_recipes)}")

    for recipe in filtered_recipes:
        recipe_card(recipe)

        if st.button(
            "Salva nei preferiti",
            key=f"save_catalog_{recipe['id']}"
        ):
            if recipe["id"] not in st.session_state.favorites:
                st.session_state.favorites.append(recipe["id"])
                st.success("Ricetta salvata nei preferiti.")
            else:
                st.info("Questa ricetta è già nei preferiti.")


with tab_favorites:
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


with tab_plan:
    st.markdown("## Meal plan settimanale")

    st.markdown(
        """
        <div class="schiscetta-card">
            <h3>Organizza la tua settimana</h3>
            <p>
                Questa è la prima bozza del meal plan. Nel prossimo step
                collegheremo ogni giorno a una ricetta del catalogo.
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )

    days = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì"]

    for day in days:
        st.selectbox(
            day,
            ["Nessuna ricetta"] + [recipe["title"] for recipe in recipes],
            key=f"meal_{day}"
        )