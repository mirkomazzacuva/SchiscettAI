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
- Multi-chain Offer Parser v1 sperimentale

## Multi-chain Offer Parser v1

Il parser non è più centrato su una sola catena. Ora:

- legge le catene trovate nel raggio scelto dall'utente
- prova a collegare solo le fonti mappate per quelle catene
- non blocca l'app se una fonte non risponde
- somma offerte web e manuali
- mantiene fallback manuale/CSV
- mostra lo stato parser per ogni catena

## Prossimi step

1. Migliorare il parser generico per singola catena.
2. Aggiungere filtro fonte: manuale / web / tutte.
3. Rimuovere duplicati manuale-web.
4. Migliorare estrazione nome prodotto / ingrediente.
5. Aggiungere data validità quando disponibile.
6. Collegare parser dedicato Coop o Conad.
7. Migliorare ranking negozio consigliato.
8. Calcolare convenienza per lista spesa completa.
9. Aggiungere avvisi offerte scadute.
10. Aggiornare README con limiti parser e fonti.

## Regola tecnica

Ogni fonte web deve avere fallback. Nessun errore di parser deve rompere la UI principale.
