#!/bin/bash
# ============================================================
# Pokerbot Table Recognition — Script di Avvio
# Crea venv, installa dipendenze, avvia la GUI
# ============================================================

set -e

# Rileva directory dello script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ============================================================
# Rileva se giriamo in un terminale
# Se l'utente avvia con un CLICK (non da terminale), l'output
# non è visibile: mostriamo popup grafici durante la preparazione.
# ============================================================
if [ -t 1 ]; then
    TERMINAL_MODE=1
else
    TERMINAL_MODE=0
fi

# Le funzioni popup (show_setup_notice ecc.) sono definite più avanti,
# dopo il rilevamento di PYTHON, perché lo usano.

# ============================================================
# 1. Verifica Python
# ============================================================

PYTHON=""
for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
        version=$("$cmd" -c "import sys; print(sys.version_info[:2])" 2>/dev/null)
        if [ $? -eq 0 ]; then
            PYTHON="$cmd"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo "ERRORE: Python 3 non trovato."
    echo "Installa Python 3.10 o superiore."
    exit 1
fi

PYTHON_VERSION=$($PYTHON -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "Python trovato: $PYTHON (v$PYTHON_VERSION)"

# ============================================================
# Funzioni popup (usano $PYTHON, definito sopra)
# ============================================================

setup_notice_pid=""

show_setup_notice() {
    [ "$TERMINAL_MODE" -eq 1 ] && return 0
    # Passa il PID del processo padre (avvio.sh) al popup:
    # se il padre muore, il popup si chiude da solo (anti-orfano).
    PARENT_PID=$$
    "$PYTHON" -c "
import tkinter as tk
import os, sys, time

parent_pid = int('$PARENT_PID')

def check_parent():
    # Se il processo padre (avvio.sh) non esiste più, chiudi il popup
    try:
        os.kill(parent_pid, 0)
    except (OSError, ProcessLookupError):
        root.destroy()
        return
    root.after(1000, check_parent)

root = tk.Tk()
root.title('PokerTableScope')
root.geometry('500x230')
root.configure(bg='#1e1e2e')
root.attributes('-topmost', True)
tk.Label(root, text='Preparazione ambiente in corso...', font=('Helvetica', 14, 'bold'), fg='#f9e2af', bg='#1e1e2e').pack(pady=(24, 8))
tk.Label(root, text='Prima esecuzione: sto scaricando e installando', fg='#cdd6f4', bg='#1e1e2e').pack()
tk.Label(root, text='le dipendenze necessarie al programma.', fg='#cdd6f4', bg='#1e1e2e').pack()
tk.Label(root, text='Questo puo richiedere 1-2 minuti.', fg='#cdd6f4', bg='#1e1e2e').pack(pady=6)
tk.Label(root, text='Attendi. E normale che per qualche secondo non ci sia attivita.', fg='#cdd6f4', bg='#1e1e2e', wraplength=460).pack()
tk.Label(root, text='Non chiudere questa finestra...', fg='#6c7086', bg='#1e1e2e').pack(pady=8)
root.after(1000, check_parent)
root.mainloop()
" &
    setup_notice_pid=$!
}

close_setup_notice() {
    if [ -n "$setup_notice_pid" ]; then
        kill "$setup_notice_pid" 2>/dev/null || true
        setup_notice_pid=""
    fi
}

show_done_notice() {
    [ "$TERMINAL_MODE" -eq 1 ] && return 0
    close_setup_notice
    PARENT_PID=$$
    "$PYTHON" -c "
import tkinter as tk
import os

parent_pid = int('$PARENT_PID')

def check_parent():
    try:
        os.kill(parent_pid, 0)
    except (OSError, ProcessLookupError):
        root.destroy()
        return
    root.after(1000, check_parent)

root = tk.Tk()
root.title('PokerTableScope')
root.geometry('380x140')
root.configure(bg='#1e1e2e')
root.attributes('-topmost', True)
tk.Label(root, text='Ambiente pronto!', font=('Helvetica', 14, 'bold'), fg='#a6e3a1', bg='#1e1e2e').pack(pady=(24, 8))
tk.Label(root, text='Avvio dell applicazione in corso...', fg='#cdd6f4', bg='#1e1e2e').pack()
root.after(2500, root.destroy)
root.after(1000, check_parent)
root.mainloop()
" &
}

show_error_notice() {
    [ "$TERMINAL_MODE" -eq 1 ] && return 0
    close_setup_notice
    PARENT_PID=$$
    "$PYTHON" -c "
import tkinter as tk
import os

parent_pid = int('$PARENT_PID')

def check_parent():
    try:
        os.kill(parent_pid, 0)
    except (OSError, ProcessLookupError):
        root.destroy()
        return
    root.after(1000, check_parent)

root = tk.Tk()
root.title('PokerTableScope')
root.geometry('440x170')
root.configure(bg='#1e1e2e')
root.attributes('-topmost', True)
tk.Label(root, text='Errore', font=('Helvetica', 14, 'bold'), fg='#f38ba8', bg='#1e1e2e').pack(pady=(24, 8))
tk.Label(root, text='Si e verificato un errore durante la preparazione.', fg='#cdd6f4', bg='#1e1e2e').pack()
tk.Label(root, text='Riprova avviando lo script da un terminale per vedere il dettaglio.', fg='#6c7086', bg='#1e1e2e').pack(pady=6)
tk.Button(root, text='OK', command=root.destroy).pack(pady=8)
root.after(1000, check_parent)
root.mainloop()
" &
}

# ============================================================
# 2. Crea venv se non esiste
# ============================================================

VENV_DIR="$SCRIPT_DIR/.venv"
VENV_PYTHON="$VENV_DIR/bin/python3"

# Cronometro per il primo avvio (preparazione ambiente)
START_TIME=$(date +%s)

if [ ! -d "$VENV_DIR" ]; then
    # Se avviato con click (senza terminale) mostra popup di attesa
    show_setup_notice
    echo ""
    echo "══════════════════════════════════════════════════"
    echo "  ⏳ PREPARAZIONE AMBIENTE — PRIMA ESECUZIONE"
    echo "══════════════════════════════════════════════════"
    echo ""
    echo "  Sto creando l'ambiente virtuale (.venv) e"
    echo "  scaricando le dipendenze necessarie."
    echo ""
    echo "  ⚠  Questo può richiedere 1-2 minuti."
    echo "  ⚠  NON chiudere questa finestra."
    echo "  ⚠  È normale che non succeda nulla per un po'."
    echo ""
    echo "  Creazione ambiente virtuale..."
    $PYTHON -m venv "$VENV_DIR"
    if [ $? -ne 0 ]; then
        echo "ERRORE: impossibile creare il venv"
        show_error_notice
        exit 1
    fi
    echo "✓ venv creato"
fi

# ============================================================
# 3. Verifica e installa dipendenze
# ============================================================

echo ""
echo "Verifica dipendenze..."

MISSING=""
"$VENV_PYTHON" -c "import cv2" 2>/dev/null || MISSING="$MISSING opencv-python"
"$VENV_PYTHON" -c "import numpy" 2>/dev/null || MISSING="$MISSING numpy"
"$VENV_PYTHON" -c "import PIL" 2>/dev/null || MISSING="$MISSING Pillow"
"$VENV_PYTHON" -c "import requests" 2>/dev/null || MISSING="$MISSING requests"

if [ -n "$MISSING" ]; then
    # Se avviato con click, il popup di attesa è già visibile
    echo ""
    echo "  ⏳ Installazione dipendenze in corso..."
    echo "  ($MISSING )"
    echo "  Questo può richiedere qualche minuto. Attendere..."
    echo ""

    if command -v uv &>/dev/null; then
        echo "  [uv] Installazione rapida..."
        uv pip install --python "$VENV_PYTHON" -r requirements.txt
    else
        echo "  [pip] Installazione..."
        "$VENV_PYTHON" -m pip install -r requirements.txt
    fi

    if [ $? -eq 0 ]; then
        echo "✓ Dipendenze installate"
    else
        echo "ERRORE: impossibile installare le dipendenze"
        show_error_notice
        exit 1
    fi
else
    echo "✓ Tutte le dipendenze presenti"
fi

# Riepilogo tempo trascorso (solo per primo avvio con preparazione)
ELAPSED=$(( $(date +%s) - START_TIME ))
if [ -n "$MISSING" ] || [ ! -d "$VENV_DIR" ] || [ $ELAPSED -gt 30 ]; then
    show_done_notice
    echo ""
    echo "══════════════════════════════════════════════════"
    echo "  ✅ AMBIENTE PRONTO in ${ELAPSED} secondi"
    echo "══════════════════════════════════════════════════"
    echo ""
fi

# ============================================================
# 4. Verifica file critici
# ============================================================

echo ""
echo "Verifica file di progetto..."

CRITICAL_FILES="main.py gui.py config.py canonical.py analyzer.py calibrator.py screenshot.py requirements.txt"
MISSING_FILES=""
for f in $CRITICAL_FILES; do
    if [ ! -f "$SCRIPT_DIR/$f" ]; then
        MISSING_FILES="$MISSING_FILES $f"
    fi
done

if [ -n "$MISSING_FILES" ]; then
    echo "ERRORE: File mancanti:$MISSING_FILES"
    exit 1
fi
echo "✓ Tutti i file presenti"

# ============================================================
# 5. Verifica LM Studio
# ============================================================

echo ""
echo "Verifica LM Studio..."

if curl -s http://localhost:1234/v1/models &>/dev/null; then
    echo "✓ LM Studio raggiungibile"
else
    echo "⚠ LM Studio non raggiungibile (localhost:1234)"
    echo "  L'analisi Vision non funzionerà senza LM Studio."
    echo "  Puoi comunque usare il calibratore manuale."
fi

# ============================================================
# 6. Avvia GUI
# ============================================================

echo ""
echo "══════════════════════════════════════════════════"
echo "  🚀 Avvio PokerTableScope..."
echo "  (Se vedi la finestra della GUI, è tutto pronto!)"
echo "══════════════════════════════════════════════════"
echo ""

"$VENV_PYTHON" main.py
