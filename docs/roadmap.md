# SchiscettAI Roadmap

## Stato attuale

SchiscettAI collega ricette, lista spesa, punti vendita nel raggio e offerte.

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
- Multi-chain Offer Parser v1.1 sperimentale

## Multi-chain Offer Parser v1.1

Il parser è applicato alle catene trovate nel raggio scelto dall'utente.

Miglioramenti v1.1:

- filtro fonte: tutte / solo manuali / solo web
- deduplica manuale-web
- limite massimo offerte web
- colonna origine nella tabella offerte
- nomi prodotto più puliti
- stato parser più leggibile
- fallback manuale sempre attivo
- ranking ricette basato sulle offerte visibili

## Prossimi step

1. Migliorare parser dedicato PENNY.
2. Aggiungere parser dedicato Coop o Conad.
3. Migliorare estrazione nome prodotto / validità.
4. Aggiungere controllo offerte scadute.
5. Rafforzare deduplica prodotto/prezzo.
6. Calcolare convenienza su lista spesa completa.
7. Migliorare ranking negozio consigliato.
8. Aggiungere impostazioni utente per preferenze catene.
9. Aggiornare README con limiti e fonti.
10. Preparare rilascio demo stabile.

## Regola tecnica

Ogni parser deve essere isolato, non bloccante e sempre accompagnato da fallback manuale.
