# SKiscettAI · SKAI Kitchen OS v16

SKAI è un Kitchen OS per pranzo, spesa e negozi.

## Missioni

1. **Creo una SKiscetta**: parti dagli ingredienti in casa.
2. **Organizzo la spesa settimanale**: piano ricette + lista spesa.
3. **Controllo negozi e offerte**: mappa e offerte solo se il prodotto è identificato.

## Novità v16

- parser dedicati per Carrefour, Coop, Conad, PENNY, Lidl, Eurospin, Esselunga, MD e PAM
- extraction da JSON-LD, Next/Nuxt data e card HTML
- Product Identity Gate: niente prezzi senza nome prodotto
- feed offerte più onesto e più utile
- UX Kitchen OS ridisegnata
- mappa centrale
- pannello tecnico nascosto

## Avvio

```bash
pip install -r requirements.txt
streamlit run app.py
```
