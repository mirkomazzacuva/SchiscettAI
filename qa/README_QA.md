# SKAI Beta Tester Pack

Questo pack serve a testare l'app live con un browser reale, senza fare screenshot manuali.

## Setup

Da terminale nella root del progetto:

```bash
python -m pip install -r qa/requirements-qa.txt
python -m playwright install chromium
```

## Test app pubblica

```bash
python qa/beta_test_skai.py --url https://skiscettai.streamlit.app/
```

## Test app locale

Avvia Streamlit:

```bash
streamlit run app.py
```

Poi in un secondo terminale:

```bash
python qa/beta_test_skai.py --url http://localhost:8501
```

## Output

Il test crea:

```text
qa/reports/skai_beta_report.md
qa/reports/skai_beta_report.json
qa/screenshots/*.png
```

Mandami lo ZIP della cartella `qa/reports` e `qa/screenshots`, oppure carica qui il file `skai_beta_report.md`.

## Cosa controlla

- accessibilità pubblica della pagina
- redirect/login/auth
- screenshot full-page delle pagine principali
- menu laterale
- dropdown/selectbox
- input testo
- bottoni
- contrasto testo/sfondo
- presenza di testo bianco su sfondo bianco
- navigazione Home / Crea SKiscetta / SKAI Radar / Ricette / Lista spesa / Meal plan / Preferiti
- errori console browser
