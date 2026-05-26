# Roadmap SchiscettAI

SchiscettAI è una web app gratuita in Streamlit per creare schiscette intelligenti, belle e personalizzate usando ingredienti disponibili, ricette modulari, immagini per cluster e una grafica avorio, greige e verde salvia.

## Visione

SchiscettAI deve aiutare l’utente a preparare pranzi da portare al lavoro che siano:

- buoni
- belli
- pratici
- economici
- personalizzati
- adatti al meal prep
- facili da trasportare

## Stile dell'app

L’app deve avere uno stile:

- glamour
- caldo
- elegante
- italiano
- appetitoso
- pulito
- premium ma accessibile

Palette principale:

- Avorio
- Greige
- Verde salvia
- Taupe/cacao per i testi

## Sottotitoli

I tre sottotitoli principali sono:

- La tua pausa pranzo intelligente
- Ricette smart per mangiare meglio ogni giorno
- Prepara, risparmia, gusta

## Feature principali MVP

### 1. Home glamour

La home deve avere:

- titolo SchiscettAI
- claim principale
- tre sottotitoli
- descrizione breve
- grafica elegante
- card introduttive
- call to action per creare una schiscetta

### 2. Generatore schiscetta

L’utente deve poter inserire:

- ingredienti disponibili
- obiettivo
- tempo disponibile
- preferenze alimentari

Obiettivi:

- Svuota frigo
- Proteica
- Light
- Economica
- Vegetariana
- Veloce
- Gourmet
- Meal prep

### 3. Motore modulare ricette

Per la prima versione gratuita non usiamo API a pagamento.

Il generatore deve combinare:

- base
- proteina
- verdura
- salsa
- topping
- stile

Esempio:

base + proteina + verdura + salsa + topping + stile

### 4. Output ricetta completo

Ogni ricetta generata deve mostrare:

- nome ricetta
- descrizione appetitosa
- ingredienti
- procedimento
- tempo di preparazione
- obiettivo
- difficoltà
- costo stimato
- conservabilità
- consiglio per il trasporto
- consiglio glamour
- valori nutrizionali indicativi
- tag

### 5. Database locale

I dati iniziali saranno salvati in file locali:

- data/recipes.json
- data/ingredients.json
- data/categories.json
- data/tags.json

### 6. Catalogo ricette

L’app deve avere una sezione per esplorare ricette:

- ricette proteiche
- ricette light
- ricette economiche
- ricette vegetariane
- ricette veloci
- ricette gourmet
- meal prep

### 7. Immagini per cluster

Invece di creare una foto per ogni ricetta, si useranno immagini per gruppi:

- bowl mediterranea
- pasta fredda
- insalata proteica
- wrap integrale
- couscous verdure
- riso pollo
- vegetariana legumi
- meal prep box
- gourmet light

### 8. Preferiti

L’utente deve poter salvare ricette preferite nella sessione.

### 9. Lista della spesa

L’app deve generare una lista della spesa partendo dalle ricette selezionate.

### 10. Meal plan settimanale

L’app deve permettere di organizzare schiscette da lunedì a venerdì.

### 11. Mappa Folium

In una fase successiva verrà aggiunta una mappa per mercati, supermercati o luoghi utili per acquistare ingredienti.

### 12. Scraping progressivo

In una fase successiva si potrà usare scraping controllato solo per:

- trend
- categorie
- ingredienti frequenti
- abbinamenti
- ispirazione generale

Non bisogna copiare ricette intere da altri siti.

## Ordine di sviluppo

1. Creare roadmap
2. Creare design system
3. Creare database JSON iniziali
4. Trasformare app.py in app a sezioni
5. Creare Home glamour
6. Creare Generatore modulare
7. Creare card ricette
8. Creare catalogo ricette
9. Aggiungere preferiti
10. Aggiungere lista spesa
11. Aggiungere meal plan
12. Aggiungere immagini per cluster
13. Aggiungere mappa Folium
14. Valutare scraping progressivo