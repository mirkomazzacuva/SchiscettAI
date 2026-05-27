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
- Offer Engine v1 per separare offerte manuali, catene trovate e fonti web future

## Offer Engine v1

Obiettivo: rendere stabile la logica offerte prima di collegare parser automatici.

Il motore ora distingue:

- offerte manuali/CSV
- supermercati trovati nel raggio
- catene riconosciute
- fonti web mappate
- parser ancora da collegare

La UI mostra perché una catena non ha ancora offerte automatiche e mantiene visibili le offerte manuali come fallback.

## Prossimi step

1. Collegare il primo parser dedicato per una sola catena.
2. Testare il parser su dati reali e limitarlo per non rompere l'app.
3. Salvare le offerte web in una struttura compatibile con le offerte manuali.
4. Unire offerte manuali e offerte web con campo `origin`.
5. Aggiungere filtro fonte: manuale / web / tutte.
6. Calcolare convenienza per lista spesa completa.
7. Migliorare ranking negozio consigliato.
8. Aggiungere data validità e avvisi offerte scadute.
9. Preparare import/export offerte.
10. Aggiornare README con uso e limiti della funzione Spesa smart.

## Regola tecnica

Non fare scraping live fragile nella UI principale. Ogni fonte web deve avere un parser dedicato, isolato e con fallback.
