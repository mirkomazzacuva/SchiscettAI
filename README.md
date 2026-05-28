# SKiscettAI · SKAI

**SKiscettAI** è una web app Streamlit per creare SKiscette intelligenti, pianificare la settimana e collegare ricette, lista spesa, supermercati nel raggio e offerte web.

Acronimo: **SKAI**.

## Funzioni principali

- Generazione SKiscette da ingredienti e obiettivi
- Catalogo ricette
- Preferiti
- Lista spesa
- Meal plan
- SKAI Radar con CAP e raggio
- Mappa supermercati tramite OpenStreetMap/Overpass
- Multi-chain Web Parser sperimentale
- UI premium neon/glass

## Modalità offerte

La UI principale è in modalità **web-only**.

Le offerte manuali/CSV non sono più parte del flusso utente principale. I parser web sono sperimentali, non bloccanti e sempre protetti da fallback.

## Avvio locale

```bash
pip install -r requirements.txt
streamlit run app.py
```

## File principali

```text
app.py
requirements.txt
README.md
styles/custom.css
docs/roadmap.md
data/recipes.json
data/stores.json
data/offer_sources.json
```
