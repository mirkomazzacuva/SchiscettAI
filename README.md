# SKiscettAI · SKAI Kitchen OS v27

## v27 Deep Browser Offer Audit

v26 ha sbloccato PENNY, Carrefour ed Eurospin via fonti testuali/fallback.

v27 mantiene l'app v26 e aggiunge un audit profondo non bloccante che usa anche browser rendering per scoprire:
- offerte visibili solo dopo JavaScript
- testo renderizzato non presente nell'HTML statico
- possibili URL API / JSON / GraphQL
- coppie prodotto+prezzo candidate per Coop, Conad, PAM, Lidl, Esselunga, MD

Il deploy resta bloccato solo dai test UI e bottoni; il deep audit produce report da leggere per costruire i parser v28.

## Avvio

```bash
pip install -r requirements.txt
streamlit run app.py
```
