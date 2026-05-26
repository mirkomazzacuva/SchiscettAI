import streamlit as st
from pathlib import Path

st.set_page_config(
    page_title="SchiscettAI",
    page_icon="🍱",
    layout="wide"
)


def load_css(file_path):
    css_path = Path(file_path)
    if css_path.exists():
        st.markdown(
            f"<style>{css_path.read_text()}</style>",
            unsafe_allow_html=True
        )


load_css("styles/custom.css")


st.markdown(
    """
    <div class="hero-box">
        <h1>🍱 SchiscettAI</h1>
        <h3>La schiscetta non è mai stata così smart.</h3>
        <p>
            Crea pranzi buoni, belli e intelligenti usando quello che hai già in casa.
            Un assistente glamour per trasformare ingredienti semplici in idee da portare ovunque.
        </p>
    </div>
    """,
    unsafe_allow_html=True
)

st.write("")

col1, col2 = st.columns([1.1, 0.9])

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
            "Gourmet"
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
            <h3>✨ Come funziona</h3>
            <p>
                Inserisci gli ingredienti che hai già, scegli il tuo obiettivo
                e SchiscettAI ti propone una schiscetta pratica, bella e intelligente.
            </p>
            <p>
                Questa è la prima versione gratuita: niente API a pagamento,
                niente installazioni sul PC, solo Streamlit e GitHub.
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )


if genera:
    if ingredienti:
        st.success("Ecco una prima idea per la tua schiscetta!")

        st.markdown(
            f"""
            <div class="schiscetta-card">
                <h2>🥗 Bowl smart mediterranea</h2>
                <p><strong>Ingredienti usati:</strong> {ingredienti}</p>
                <p><strong>Obiettivo:</strong> {obiettivo}</p>
                <p><strong>Tempo disponibile:</strong> {tempo}</p>

                <h3>Procedimento base</h3>
                <ol>
                    <li>Scegli una base: riso, couscous, farro o pasta fredda.</li>
                    <li>Aggiungi una fonte proteica tra gli ingredienti disponibili.</li>
                    <li>Completa con verdure croccanti o grigliate.</li>
                    <li>Condisci con olio EVO, limone, spezie o salsa yogurt.</li>
                    <li>Conserva in un contenitore ermetico e portala con te.</li>
                </ol>

                <p><strong>Consiglio glamour:</strong> aggiungi semi, erbe fresche o scorza di limone
                per renderla più bella e appetitosa.</p>
            </div>
            """,
            unsafe_allow_html=True
        )
    else:
        st.warning("Inserisci almeno un ingrediente.")