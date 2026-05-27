# SchiscettAI Roadmap

## Stato attuale

SchiscettAI è una web app Streamlit per creare schiscette, pianificare la settimana e collegare ricette, lista spesa e offerte.

Funzioni attive:

- catalogo ricette
- generatore modulare
- preferiti
- lista spesa
- meal plan
- cluster visuali
- Spesa smart con CAP e raggio
- ricerca punti vendita tramite OpenStreetMap/Overpass
- mappa interattiva
- offerte manuali/CSV come fonte strutturata
- Offer Engine v1
- Parser PENNY v1 sperimentale

## Offer Engine v1

Il motore distingue:

- offerte manuali/CSV
- offerte web future
- supermercati trovati nel raggio
- catene riconosciute
- fonti web mappate
- parser collegati o ancora da collegare

## Parser PENNY v1

Il primo parser dedicato è sperimentale e sicuro:

- usa la pagina ufficiale PENNY offerte
- non blocca l'app se il sito non risponde
- estrae snippet con prezzi quando leggibili
- normalizza alcune parole chiave in ingredienti
- aggiunge le offerte come `origin = web_penny`
- mantiene il Google Sheet/CSV come fallback manuale

## Prossimi step

1. Testare Parser PENNY v1 su Streamlit.
2. Migliorare estrazione nome prodotto / ingrediente.
3. Aggiungere filtro fonte: manuale / PENNY web / tutte.
4. Evitare duplicati tra offerte manuali e web.
5. Aggiungere data validità quando disponibile.
6. Collegare il secondo parser: Coop o Conad.
7. Migliorare ranking negozio consigliato.
8. Calcolare convenienza per lista spesa completa.
9. Aggiungere avvisi offerte scadute.
10. Aggiornare README con limiti parser e fonti.

## Regola tecnica

Ogni fonte web deve avere un parser dedicato, isolato e con fallback. Non fare scraping fragile direttamente nella UI principale.
