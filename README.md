# SKiscettAI · SKAI Kitchen OS v35

## v35 Visual QA Precision Refresh

Release basata sul report `skai-visual-beta-report`.

Fix principali:
- il CSS finale viene caricato dopo tutti i layer vecchi, quindi non viene più sovrascritto
- sidebar realmente chiara
- testi della sidebar scuri e leggibili
- bottoni sidebar con contrasto corretto
- sfondo light ma non bianco vuoto
- pagine corte meno “vuote”
- context bar above-fold su tutte le pagine
- Home mostra subito “schiscetta” e “Copilot”
- Radar mostra subito “catene nel raggio”
- Meal plan mostra subito “Piano pranzi”
- mantenuti hotfix Radar, copy UX, volantini visuali e multi-source offers

## Avvio

```bash
pip install -r requirements.txt
streamlit run app.py
```
