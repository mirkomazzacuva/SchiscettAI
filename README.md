# SKiscettAI · SKAI Kitchen OS v26

## v26 Multi-Source Offer Engine

Questa release prova finalmente a recuperare offerte anche dalle altre catene, non solo PENNY/Carrefour:

- official source first
- fallback su cataloghi/volantini pubblici quando la fonte ufficiale non espone prodotto+prezzo
- parser multi-source per prodotto + prezzo + catena
- niente card con solo prezzo
- pannello catene con fonti provate
- live offer audit aggiornato sulle fonti fallback
- QA corretto v25 mantenuto

## Avvio

```bash
pip install -r requirements.txt
streamlit run app.py
```
