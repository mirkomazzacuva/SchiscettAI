# SKiscettAI · SKAI Kitchen OS v30

## v30 Radar Hotfix definitivo

Correzione urgente:
- `parser_url_for_chain` presente
- `chains_with_parser_enabled` presente
- SKAI Radar non crasha più in modalità normale
- QA `qa_boot=1`: esegue la selezione parser ma salta fetch esterne lente
- il workflow controlla anche via grep che la funzione esista
- v28 visual flyers e v26 multi-source offers mantenuti

## Avvio

```bash
pip install -r requirements.txt
streamlit run app.py
```
