# PokerTableScope v1.2.0

Calibratore e estrattore di layout universale per client di poker. Genera file JSON compatibili con **PokerBotAgent** (unico bot supportato).

---

## Indice

- [Scopo](#scopo)
- [Architettura](#architettura)
- [Cartelle da non spostare](#cartelle-da-non-spostare)
- [Requisiti](#requisiti)
- [Installazione](#installazione)
- [Avvio](#avvio)
- [Guida all'uso](#guida-alluso)
- [Esportazione verso PokerBotAgent](#esportazione-verso-pokerbotagent)
- [Formato dei profili e dei layout](#formato-dei-profili-e-dei-layout)
- [Test](#test)
- [Note tecniche](#note-tecniche)
- [Risoluzione problemi](#risoluzione-problemi)

---

## Scopo

PokerTableScope è lo strumento di **calibrazione grafica** che affianca PokerBotAgent. Il suo compito è:

1. **Acquisire screenshot** di un tavolo di poker (qualsiasi client, web o desktop).
2. **Calibrare le coordinate** dei pulsanti di azione (fold, check, call, raise, all-in, bet), dei seat giocatori, delle ROI di lettura (pot, timer, blind, stack, carte, rank, ecc.).
3. **Salvare profili** con tutte le coordinate calibrate.
4. **Esportare layout JSON** nel formato che PokerBotAgent carica direttamente per giocare.

**Non fa gioco**: non prende decisioni, non clicca i pulsanti durante una partita, non comunica con modelli LLM per il ragionamento. Si occupa solo di dire a PokerBotAgent **dove cliccare** e **dove leggere**.

---

## Architettura

```
PokerTableScope                              PokerBotAgent
┌─────────────────────┐                      ┌─────────────────────┐
│  Calibra tavolo     │   layout_*.json      │  Carica layout      │
│  Salva profilo      │ ──────────────────►  │  Gioca partite      │
│  Esporta per bot    │   (output/ → layouts/)│  See → Eval → Act   │
└─────────────────────┘                      └─────────────────────┘
```

- **PokerTableScope** produce i file `layout_*.json` nella cartella `output/`.
- **PokerBotAgent** li legge dalla sua cartella `layouts/`.
- La copia da `output/` a `layouts/` puoi farla con il pulsante **"Esporta e Copia in PokerBotAgent"**, manualmente, o con un symlink (solo sviluppo).

---

## Cartelle da non spostare

> **Attenzione**: Spostare o rinominare le seguenti cartelle rompe il funzionamento di entrambi i tool.

| Cartella | Progetto | Contiene | Perché non spostare |
|----------|----------|----------|---------------------|
| `profiles/` | PokerTableScope | Profili JSON calibrati | Sorgente dei dati di calibrazione |
| `output/` | PokerTableScope | Layout esportati per PokerBotAgent | PokerBotAgent legge da qui (o da `layouts/` dopo copia) |
| `screenshots/` | PokerTableScope | Screenshot usati per calibrare | Riferimento per i profili |
| `assets/deck_labels/` | PokerTableScope | Immagini semi per template matching | Usate da `analyzer.py` |
| `scripts/` | PokerTableScope | Script di conversione formati | Utility per importazione profili |
| `templates/` | PokerTableScope | Override template salvati | Riutilizzabili tra profili |

**Percorsi assoluti hardcoded** in `config.py`:
- `SCREENSHOTS_DIR` → `{BASE_DIR}/screenshots/`
- `PROFILES_DIR` → `{BASE_DIR}/profiles/`
- `OUTPUT_DIR` → `{BASE_DIR}/output/`

Dove `BASE_DIR` = directory contenente `config.py` (= la root del progetto).

---

## Requisiti

| Componente | Minimo | Consigliato |
|------------|--------|-------------|
| OS | Linux (X11) | Ubuntu 22.04+ / Debian 12+ |
| Python | 3.10 | 3.11 o 3.12 |
| RAM | 8 GB | 16 GB |
| Tkinter | Sì | Incluso con Python su Linux |
| GPU | Nessuna per la calibrazione | Per Vision: qwen3-vl-8b-instruct via LM Studio |

**Per la Visione (opzionale)**:
- [LM Studio](https://lmstudio.ai) installato e in esecuzione
- Modello `qwen3-vl-8b-instruct` caricato
- Max dimensione input: 768px lato più lungo, JPEG q80

---

## Installazione

### 1. Dipendenze di sistema (Ubuntu/Debian)

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv python3-tk
```

### 2. Estrai il progetto

```bash
cd ~/Documenti
unzip PokerTableScope.zip
cd PokerTableScope
```

### 3. Avvia (primo avvio)

```bash
chmod +x avvio.sh
./avvio.sh
```

Lo script `avvio.sh`:
1. Verifica che Python 3 sia installato
2. Crea il virtual environment `.venv/` se non esiste
3. Installa le dipendenze da `requirements.txt`
4. Verifica che tutti i file critici siano presenti
5. Avvia la GUI

**Se il venv è corrotto o mancano dipendenze**:
```bash
rm -rf .venv && ./avvio.sh
```

### Avvio manuale

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 main.py
```

---

## Avvio

### Script automatico (consigliato)

```bash
cd ~/Documenti/PokerTableScope
./avvio.sh
```

Lo script gestisce:
- Creazione automatica del venv
- Installazione dipendenze
- Verifica file di sistema
- Avvio della GUI

### Finestra di avvio

Se avvii con doppio click (senza terminale), appare una finestra popup che mostra lo stato della preparazione. Si chiude automaticamente quando tutto è pronto.

---

## Guida all'uso

### Flusso di lavoro tipico

```
1. Carica screenshot
2. Calibra Table ROI (confine tavolo)
3. Calibra coordinate pulsanti (fold, check, call, raise, all-in, bet)
4. Calibra dimensioni pulsanti (📏, area cliccabile anti-ban)
5. Calibra override ROI (pot, timer, stack, carte, rank)
6. Salva profilo
7. Esporta per PokerBotAgent
8. Avvia PokerBotAgent con il layout esportato
```

### 1. Carica uno screenshot

- Clicca **"Carica Screenshot"** nella GUI
- Seleziona un file `.png` o `.jpg` del tavolo
- Lo screenshot viene visualizzato nell'area canvas

**Consiglio**: carica diversi screenshot dello stesso tavolo per coprire diverse fasi della partita (preflop, postflop, turni diversi).

### 2. Table ROI

Il **Table ROI** definisce i confini del tavolo visibile (dove il gioco effettivo avviene).

- Clicca il pulsante **"ROI Table"** nella GUI
- Clicca due punti nell'immagine: angolo alto-sinistra e angolo basso-destra del tavolo
- Viene disegnato un rettangolo verde che indica l'area calibrata

Le coordinate salvate sono: `(x, y, width, height)` in pixel.

### 3. Coordinate pulsanti

Per ogni pulsante di azione, imposta le coordinate dove PokerBotAgent dovrà cliccare:

| Pulsante | Descrizione |
|----------|-------------|
| **Fold** | Passa la mano |
| **Check** | Controlla (stessa posizione di Call quando disponibile) |
| **Call** | Chiama la puntata (stessa posizione di Check) |
| **Raise** | Rilancia (stessa posizione di All-In) |
| **All-In** | Tutto il stack (stessa posizione di Raise) |
| **Bet** | Scommetti (condivide coordinate con Raise/All-In; usato quando il BB non è rilanciato) |

**Nota**: Check e Call hanno spesso le stesse coordinate. Raise, All-In e Bet condividono le stesse coordinate.

**Metodo** (2 step per pulsante):
1. Clicca il pulsante corrispondente nella GUI (es. FOLD)
2. Clicca sul punto esatto (centro) nello screenshot → salva le coordinate `x, y`

### 3bis. Dimensioni pulsanti (anti-ban, 📏)

Per ogni pulsante azione puoi (consigliato) definire le **dimensioni dell'area cliccabile** con il pulsante **"📏"** accanto a ogni pulsante. Questo permette a PokerBotAgent di generare un **offset casuale** dentro l'area del pulsante (anti-ban), evitando di cliccare sempre nello stesso pixel identico.

| Elemento | Descrizione |
|----------|-------------|
| **Pulsante 📏** | Accanto a ogni pulsante azione (FOLD, CHECK, CALL, RAISE, ALL-IN, BET) |
| **Metodo** | 2 click: angolo alto-sinistra + angolo basso-destra del pulsante |
| **Risultato** | Salva le dimensioni `w, h` dell'area cliccabile |
| **Indicatore** | ✅ = dimensioni impostate, ⬜ = mancanti |
| **Opzionale** | Se non calibrate (w,h=0), PokerBotAgent clicca al centro (nessuna variazione) |

**Regole**:
- `w, h` vengono salvati nel profilo come `act_targets[azione].w` e `.h`
- All'export, i fallback (call←check, allin←raise, bet←raise) copiano anche `w, h`
- Dimensioni troppo piccole (w<2 o h<2 px) vengono scartate

### 4. Override ROI

Gli **Override ROI** sono aree specifiche dove PokerBotAgent legge informazioni dallo schermo:

| Campo | Colore | Visibilità |
|-------|--------|------------|
| `pot` | Giallo | Sempre |
| `timer` | Arancione | Sempre |
| `sb` | Azzurro | Sempre |
| `bb` | Azzurro | Sempre |
| `ante` | Azzurro | Sempre |
| `players_remaining` | Rosso | Solo a iscrizioni chiuse |
| `paid_positions` | Rosso | Sempre |
| `rank_temporary` | Viola | Sempre |
| `hero_stack` | Verde | Sempre |
| `stacks.1` – `stacks.9` | Grigio | Per ogni seat |

**Metodo** (2 click per campo):
1. Clicca il pulsante ROI accanto al campo
2. Clicca angolo alto-sinistra nell'immagine
3. Clicca angolo basso-destra nell'immagine
4. Indicatore ✅ = coordinate impostate, ⬜ = mancante

**Inserimento manuale**: puoi anche digitare direttamente le coordinate negli entry accanto a ogni campo.

### 5. Salva profilo

- Inserisci il nome del profilo nella casella in alto (es. `nome-room-9max-4colori`)
- Clicca **"Salva Profilo"**
- Il profilo viene salvato in `profiles/{nome}.json`

**Regole di naming**:
- Caratteri permessi: lettere, numeri, trattini, underscore
- Caratteri rimossi: `/ \ : * ? " < > |`
- Il file viene salvato sempre in `profiles/`, indipendentemente dal percorso precedente

### 6. Carica un profilo esistente

- Usa il menu o la lista profili per caricare uno salvato precedentemente
- Tutti i campi vengono ripopolati (coordinate pulsanti, ROI, override)

---

## Esportazione verso PokerBotAgent

### Pulsante "Esporta per PokerBotAgent"

- Genera il file `layout_{nome_profilo}.json` nella cartella `output/`
- Non copia nulla in PokerBotAgent
- Utile per esportare senza modificare il bot

**Prerequisito**: devi prima caricare un profilo (clicca su uno nella lista profili o usa "Carica Profilo").

### Pulsante "Esporta e Copia in PokerBotAgent"

- Genera il file in `output/`
- Lo copia automaticamente in `../PokerBotAgent/layouts/`
- Se il file esiste già, mostra un **diff sintetico** (righe modificate, differenze) e chiede conferma prima di sovrascrivere

**Prerequisiti**:
- Un profilo deve essere caricato e valido
- La cartella `../PokerBotAgent/layouts/` deve esistere
- PokerBotAgent deve trovarsi nella stessa directory padre (`~/Documenti/`)

### Verifica manuale

```bash
# Controlla i layout esportati
ls -l ~/Documenti/PokerTableScope/output/

# Controlla i layout nel bot
ls -l ~/Documenti/PokerBotAgent/layouts/
```

---

## Formato dei profili e dei layout

### Profilo canonico (`profiles/*.json`)

Il formato interno di PokerTableScope, con tutte le informazioni di calibrazione:

```json
{
  "name": "nome-room-9max-4colori",
  "client": {
    "name": "nome-room",
    "platform": "web",
    "resolution": [1936, 1056],
    "format": "9max"
  },
  "table_roi": { "x": 2, "y": 2, "w": 1022, "h": 721 },
  "seats": {
    "hero": 5,
    "hero_name": "gianlucaio3",
    "players": { "1": {...}, "2": {...}, ... }
  },
  "act_targets": {
    "fold": {"x": ..., "y": ..., "w": ..., "h": ...},
    "check": {"x": ..., "y": ..., "w": ..., "h": ...},
    "call": {"x": ..., "y": ..., "w": ..., "h": ...},
    "raise": {"x": ..., "y": ..., "w": ..., "h": ...},
    "allin": {"x": ..., "y": ..., "w": ..., "h": ...},
    "bet": {"x": ..., "y": ..., "w": ..., "h": ...}
  },
  "override_rois": {
    "pot": {"x": ..., "y": ..., "w": ..., "h": ...},
    "timer": { ... },
    "sb": { ... },
    "bb": { ... },
    "ante": { ... },
    "players_remaining": { ... },
    "paid_positions": { ... },
    "rank_temporary": { ... },
    "hero_stack": { ... },
    "stacks": {
      "1": { ... }, "2": { ... }, ... "9": { ... }
    }
  }
}
```

### Layout esportato (`output/layout_*.json`)

Il formato che PokerBotAgent consuma, generato da `canonical.py:profile_to_see_config()`. Contiene le stesse informazioni ma strutturate come si aspetta `see.py` del bot.

**Campi principali**:
- `table_roi` → coordinate area tavolo
- `act_targets` → coordinate pulsanti azione (con `w,h` = dimensioni area cliccabile anti-ban)
- `override_rois` → coordinate ROI di lettura
- `seats` → mappatura seat e coordinate carte

**Compatibilità retroattiva**: PokerBotAgent ignora i campi che non conosce.

### Semi delle carte (schema colore)

Questo schema è **obbligatorio** sia in PokerTableScope che in PokerBotAgent:

| Seme | Colore |
|------|--------|
| ♥ Hearts | ROSSO |
| ♠ Spades | NERO |
| ♦ Diamonds | BLU |
| ♣ Clubs | VERDE |

**Mai usare** GREEN=Spades o Yellow=Clubs (errore documentato).

---

## Test

### Test GUI headless

Verificano la logica della GUI senza aprire finestre grafiche:

```bash
cd ~/Documenti/PokerTableScope
source .venv/bin/activate
python3 test_gui_headless.py
```

**Risultato atteso**: 67/67 test passati.

### Test con pytest

```bash
source .venv/bin/activate
pip install pytest
python3 -m pytest test_gui_headless.py -v
```

---

## Note tecniche

### Modello Vision (opzionale)

- **Modello**: `qwen3-vl-8b-instruct` via LM Studio (`localhost:1234`)
- **Max dimensione**: 768px lato più lungo
- **Formato**: JPEG qualità 80
- **Prompt**:nessun `system` role, nessuna `temperature`
- **Prompt Vision**: definito in `analyzer.py` (include mapping semi e crop board/hero)
- **Crop**: `analyze_with_crops()` esegue crop delle aree board e hero con upscale/downscale a 768px

### Keyboard shortcuts nella GUI

| Tasto | Azione |
|-------|--------|
| `Shift+1..9` | Seleziona seat |
| `F` | Fold |
| `C` | Check/Call |
| `K` | Check |
| `R` | Raise |
| `A` | All-In |
| `B` | Bet |
| `D` | Table ROI |
| `Esc` | Annulla operazione corrente |

Le shortcuts non funzionano quando il focus è su un campo di testo (entry).

### Autosave

La GUI salva automaticamente lo stato in `session.json` dopo ogni modifica:
- Cliccata sul canvas (calibrazione coordinate)
- Finalizzazione ROI
- Applicazione override manuali

Al riavvio, il session viene caricato dopo 500ms.

### UNDO

- Pulsante **"↩ UNDO"** nell'area coordinate
- Salva uno snapshot dello stato prima di ogni operazione
- Capacità massima: 50 operazioni
- I marker verde (coordinate pulsanti) e gli indicatori ROI vengono cancellati correttamente

### Template Override

- **"💾 Salva Template"**: salva gli override ROI correnti come template riutilizzabile
- **"📂 Carica Template"**: carica un template e applica le coordinate a un profilo diverso
- I template sono salvati in `templates/`

### Piattaforma (web/client)

La GUI ha un menu a tendina **"Piattaforma"** con due opzioni:
- **web**: versione browser (es. 1936×1056 fullscreen)
- **client**: versione desktop (es. 1024×726)

La piattaforma influisce sulle dimensioni di riferimento per la calibrazione.

### Dimensioni pulsanti anti-ban

- Ogni `act_target` del profilo contiene `{x, y, w, h}`:
  - `x, y` = centro del pulsante (dove il bot clicca)
  - `w, h` = dimensioni dell'area cliccabile reale del pulsante
- PokerBotAgent usa `w, h` per generare un **offset casuale** dentro l'area → mai lo stesso pixel identico (anti-ban)
- Le dimensioni si calibrano con il pulsante **"📏"** (2 click: angolo alto-sx + basso-dx)
- Sono **opzionali**: se `w, h = 0`, il bot clicca al centro (comportamento backward-compatible)
- All'export, i fallback (call←check, allin←raise, bet←raise) copiano anche `w, h`

### Finestra e pannello

- Finestra: **1860×1000**
- Pannello destro: **760px**
- Entry compatte (width fisso, niente fill/expand)

---

## Risoluzione problemi

### "Nessun profilo da esportare"

**Causa**: nessun profilo è caricato come "profilo attivo".
**Soluzione**: clicca su un profilo nella lista o usa "Carica Profilo" prima di esportare.

### "Cartella layouts di PokerBotAgent non trovata"

**Causa**: PokerBotAgent non si trova nella directory padre attesa.
**Soluzione**: assicurati che la struttura sia:
```
~/Documenti/
├── PokerTableScope/
└── PokerBotAgent/
    └── layouts/
```

### GUI non parte

**Possibili cause**:
- Python 3 non installato: `sudo apt install python3 python3-tk`
- venv corrotto: `rm -rf .venv && ./avvio.sh`
- Tkinter mancante: `sudo apt install python3-tk`

### Test falliscono

**Possibili cause**:
- Dipendenze mancanti nel venv: `rm -rf .venv && ./avvio.sh`
- Modifiche alla GUI non compatibili con i test

---

## File della distribuzione

```
PokerTableScope/
├── avvio.sh                 # Avvio automatico
├── main.py                  # Entry point
├── gui.py                   # GUI calibratore
├── config.py                # Costanti e configurazioni
├── calibrator.py            # Logica salvataggio/esportazione
├── canonical.py             # Schema JSON e conversione
├── analyzer.py              # Modello Vision (opzionale)
├── screenshot.py            # Cattura schermo e caricamento
├── requirements.txt         # Dipendenze Python
├── test_gui_headless.py     # Test (67 test)
├── profiles/                # Profili calibrati (NON eliminare)
├── output/                  # Layout esportati (NON eliminare)
├── screenshots/             # Screenshot di riferimento
├── assets/deck_labels/      # Immagini semi per template matching
├── scripts/                 # Utility di conversione
├── templates/               # Override template salvati
└── README.md                # Questo file
```

---

## Licenza e utilizzo

Progetto privato per uso personale. Non distribuire profili calibrati contenenti coordinate specifiche di piattaforme di poker — ogni utente deve calibrare i propri tavoli.
