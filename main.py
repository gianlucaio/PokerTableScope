#!/usr/bin/env python3
"""
PokerTableScope — Entry Point
Avvia la GUI di calibrazione universale per tavoli poker.
"""

import os
import sys

# Aggiungi la directory corrente al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def main():
    """Avvia l'applicazione GUI."""
    print("=" * 60)
    print("  PokerTableScope — Calibratore Universale")
    print("=" * 60)
    print()
    print("Avvio interfaccia grafica...")
    print("Assicurati che LM Studio sia attivo per l'analisi Vision.")
    print()

    try:
        from gui import App
        app = App()
        app.run()
    except KeyboardInterrupt:
        print("\n[MAIN] Interrutto dall'utente")
    except Exception as e:
        print(f"\n[MAIN] Errore: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
