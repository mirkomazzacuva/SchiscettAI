# SKiscettAI · SKAI Kitchen OS v28

## v28 Visual Flyer Fallback

Dai report v27:
- PENNY: prodotto+prezzo testuale
- Carrefour: prodotto+prezzo testuale via fallback
- Eurospin: prodotto+prezzo testuale via fallback
- Coop/Conad/PAM/Lidl/Esselunga/MD: spesso offerte in immagini/API viewer

v28 aggiunge una soluzione utile subito:
- card testuali quando prodotto+prezzo sono affidabili
- volantini visuali per le catene dove il testo non è estraibile
- l'utente vede comunque prodotto, prezzo e supermercato nella pagina volantino
- niente card inventate o con solo prezzo
- deep audit mantenuto per costruire parser futuri

## Avvio

```bash
pip install -r requirements.txt
streamlit run app.py
```
