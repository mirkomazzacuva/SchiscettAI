# SKiscettAI · SKAI Ultra Complete v13

SKiscettAI è una web app Streamlit per risolvere tre problemi concreti:

1. **Ho ingredienti in casa** → genera una SKiscetta.
2. **Piano spesa settimanale** → crea un piano ricette + lista.
3. **Offerte vicino a me** → mostra mappa, negozi e offerte web pulite.

## Cosa include v13

- SKAI Copilot come schermata principale
- Missione, ingredienti, CAP e raggio in un blocco compatto
- Mappa immediatamente sotto il primo blocco
- Opzioni avanzate nascoste
- Dropdown/selectbox leggibili
- Parser web con quality gate
- QA automatico via Playwright
- Workflow GitHub Actions opzionale
- Tema Streamlit dark coerente

## Avvio locale

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Test QA opzionale

```bash
python -m pip install -r qa/requirements-qa.txt
python -m playwright install chromium
python qa/beta_test_skai.py --url http://localhost:8501
```
