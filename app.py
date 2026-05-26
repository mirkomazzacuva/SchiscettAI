import streamlit as st

st.set_page_config(
    page_title="SchiscettAI",
    page_icon="🍱",
    layout="wide"
)

st.title("🍱 SchiscettAI")
st.subheader("La schiscetta non è mai stata così smart.")

st.write(
    "Crea pranzi buoni, belli e intelligenti usando quello che hai già in casa."
)

ingredienti = st.text_input("Che ingredienti hai in casa?")

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

if st.button("Genera la mia schiscetta"):
    if ingredienti:
        st.success("Ecco una prima idea per la tua schiscetta!")

        st.markdown("### Bowl smart mediterranea")
        st.write(f"Ingredienti usati: {ingredienti}")
        st.write(f"Obiettivo: {obiettivo}")
        st.write(f"Tempo disponibile: {tempo}")

        st.markdown("""
        **Procedimento base:**

        1. Scegli una base: riso, couscous, farro o pasta fredda.
        2. Aggiungi una fonte proteica.
        3. Aggiungi verdure croccanti o grigliate.
        4. Condisci con olio EVO, limone, spezie o salsa yogurt.
        5. Conserva in contenitore ermetico.
        """)
    else:
        st.warning("Inserisci almeno un ingrediente.")