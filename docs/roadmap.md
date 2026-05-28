# SKiscettAI Roadmap

## Nome progetto

Il progetto si chiama **SKiscettAI**.

Acronimo: **SKAI**.

## Stato attuale

SKiscettAI è una web app Streamlit per creare SKiscette, pianificare la settimana e collegare ricette, lista spesa, supermercati nel raggio e offerte web.

Funzioni attive:

- catalogo ricette
- generatore modulare
- preferiti
- lista spesa
- meal plan
- cluster visuali
- SKAI Radar con CAP e raggio
- ricerca punti vendita tramite OpenStreetMap/Overpass
- mappa interattiva
- Multi-chain Web Parser sperimentale
- modalità web-only nel flusso principale

## SKAI Web-only Parser v2

Le offerte manuali/CSV sono rimosse dal flusso principale.

Il motore ora:

- cerca le catene nel raggio scelto dall'utente
- attiva i parser web per le catene trovate
- non blocca l'app se una fonte non risponde
- mostra lo stato parser per ogni catena
- usa solo offerte web nella UI principale

## Prossimi 20 step

1. Migliorare parser PENNY.
2. Migliorare parser Carrefour.
3. Collegare parser Coop.
4. Collegare parser Conad.
5. Collegare parser Lidl.
6. Collegare parser Eurospin.
7. Collegare parser PAM se tecnicamente fattibile.
8. Migliorare estrazione prodotto/prezzo.
9. Estrarre validità offerta.
10. Rimuovere duplicati cross-catena.
11. Calcolare convenienza lista spesa completa.
12. Migliorare ranking negozio consigliato.
13. Aggiungere preferenze catene utente.
14. Aggiungere warning offerte non verificate.
15. Salvare cache offerte web.
16. Aggiungere filtro categoria.
17. Aggiungere ordinamento prezzo/distanza/copertura.
18. Migliorare UX mobile.
19. Aggiornare README.
20. Preparare demo pubblica stabile.

## Regola tecnica

Ogni parser deve essere isolato, non bloccante e con fallback. Nessun errore di parser deve rompere la UI principale.
