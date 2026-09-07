#!/usr/bin/env python3
"""
PokerTableScope — Formato Canonico JSON

Questo file definisce lo SCHEMA del dato prodotto dalla Table Recognition
e consumato dal PokerBotAgent. È il contratto tra i due progetti.

La Table Recognition produce un file .json per ogni tavolo/skin calibrato,
che PokerBotAgent carica all'avvio per sapere Dove Cliccare e Cosa Leggere.

Compatibilità:
  - I campi "game_state" seguono esattamente il formato di main._parse_vision_output()
  - I campi "calibration" sono NUOVI e aggiunti dalla Table Recognition
  - PokerBotAgent ignora i campi che non conosce (backward compatible)
"""

import json
import os
import time


# ============================================================
# SCHEMA CANONICO
# ============================================================

CANONICAL_VERSION = "1.0.0"

# Famiglia pulsanti azione (ordine di visualizzazione nella GUI).
# Convenzione coordinate: fold unico; check/call condividono posizione;
# raise/allin/bet condividono posizione. Aggiornare SOLO qui se cambia.
ACTION_BUTTONS = ("fold", "check", "call", "raise", "allin", "bet")

# Etichette GUI per i pulsanti azione (ordine = ACTION_BUTTONS).
ACTION_BUTTON_LABELS = {
    "fold": "FOLD", "check": "CHECK", "call": "CALL",
    "raise": "RAISE", "allin": "ALL-IN", "bet": "BET",
}

# Sottoinsieme minimo richiesto per validare/completare un profilo.
# fold/check/raise sono i 3 pulsanti sempre presenti; i restanti (call,
# allin, bet) condividono le loro coordinate e sono opzionali.
ACTION_BUTTONS_MIN = ("fold", "check", "raise")

def make_empty_profile():
    """Crea un profilo di calibrazione vuoto, pronto per essere popolato."""
    return {
        "version": CANONICAL_VERSION,
        "name": "",                    # Nome preset (es. 6max_899x742)
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),

        # --- INFO CLIENT ---
        "client": {
            "name": "",           # es. "6max", "9max"
            "platform": "",       # es. "web", "desktop", "mobile"
            "version": "",        # versione client (se riconosciuta)
            "language": "it",     # lingua interfaccia
        },

        # --- RISOLUZIONE ---
        "resolution": {
            "width": 0,           # larghezza area gioco (px)
            "height": 0,          # altezza area gioco (px)
        },

        # --- ROI TAVOLO (regione di interesse sullo schermo) ---
        # Definisce dove si trova il tavolo sullo schermo, così il bot
        # cattura SOLO quella regione (non l'intero schermo). Coordinata
        # relativa all'angolo 0,0 dello schermo.
        "table_roi": {
            "x": 0,
            "y": 0,
            "w": 0,
            "h": 0,
        },

        # --- SEAT MAP (posizioni fisse delle sedie) ---
        # Ogni seat ha coordinate x,y del CENTRO della zona avatar/nome.
        # Indipendente dal numero giocatori: un tavolo 6-max ha 6 seat,
        # un 9-max ne ha 9. Le prime sedie partono dal top e vanno
        # in senso orario.
        "seats": {
            # Esempio tavolo 6-max (coordinates in px rispetto all'angolo 0,0 del tavolo):
            # "1": {"x": 450, "y": 50},    # top center
            # "2": {"x": 750, "y": 180},   # top right
            # "3": {"x": 750, "y": 500},   # bottom right
            # "4": {"x": 450, "y": 650},   # bottom center
            # "5": {"x": 150, "y": 500},   # bottom left
            # "6": {"x": 150, "y": 180},   # top left
        },

        # --- HERO ---
        "hero": {
            "seat": None,         # numero seat Hero (es. 3)
            "name": "hero",       # nome display (per confronto Vision)
            "dynamic_seat": True, # True = Hero può spostarsi tra le sedie
        },

        # --- AZIONI (coordinate pulsanti di gioco) ---
        # Tutte le coordinate sono in px rispetto all'angolo 0,0 del tavolo.
        # x, y = centro del pulsante (dove cliccare)
        # w, h = dimensioni area cliccabile (per offset casuale anti-ban)
        "act_targets": {
            action: {"x": 0, "y": 0, "w": 0, "h": 0} for action in ACTION_BUTTONS
        },

        # --- BARRA TORNEO (ROI della barra in alto) ---
        "tournament_bar": {
            "enabled": False,
            "roi": {"x": 0, "y": 0, "w": 0, "h": 0},  # regione barra info
        },

        # --- BOARD (ROI delle 5 carte comuni) ---
        "board_roi": {
            "x": 0, "y": 0, "w": 0, "h": 0,
        },

        # --- OVERRIDE ROI (definite dall'utente con 2 click) ---
        # Per ogni campo override manuale, il rettangolo esatto dove il valore
        # è visibile nello screenshot. PokerBotAgent usa queste ROI per leggere
        # automaticamente pot/timer/blinds/ante/giocatori via Vision.
        "override_rois": {
            "pot":                {"x": 0, "y": 0, "w": 0, "h": 0},
            "timer":              {"x": 0, "y": 0, "w": 0, "h": 0},
            "sb":                 {"x": 0, "y": 0, "w": 0, "h": 0},
            "bb":                 {"x": 0, "y": 0, "w": 0, "h": 0},
            "ante":               {"x": 0, "y": 0, "w": 0, "h": 0},
            "players_remaining":  {"x": 0, "y": 0, "w": 0, "h": 0},
            "paid_positions":     {"x": 0, "y": 0, "w": 0, "h": 0},
            "rank_temporary":     {"x": 0, "y": 0, "w": 0, "h": 0},
            "hero_stack":         {"x": 0, "y": 0, "w": 0, "h": 0},
            "stacks": {
                str(i): {"x": 0, "y": 0, "w": 0, "h": 0}
                for i in range(1, 10)  # 1-9 (9-max include hero come seat 5, ma gli opponent sono 8 + 1 extra per sicurezza)
            },
        },

        # --- NOTE ---
        "notes": "",             # note libere dell'utente
    }


def make_game_state():
    """
    Crea uno stato di gioco vuoto, compatibile con main._parse_vision_output().
    Questo è il formato che la Vision produce a ogni ciclo durante il gioco.
    """
    return {
        # --- CAMPI COMPATIBILI CON POKERBOTAGENT ---
        "hole_cards": [],                  # es. ["As", "Kh"]
        "board": [],                       # es. ["7c", "8d", "2h", "9s"]
        "pot": None,                       # es. 5110
        "move_timer_seconds_remaining": None,  # es. 15
        "players": [],                     # lista player dicts
        "phase": "UNKNOWN",                # PREFLOP/FLOP/TURN/RIVER
        "tournament": {},                  # blind/ante/players_remaining/paid

        # --- CAMPI TABLE RECOGNITION (nuovi, PokerBotAgent li ignora) ---
        "hero_seat": None,                 # seat riconosciuto per Hero
        "client": "",                      # nome client riconosciuto
        "calibration_id": "",              # id del profilo usato
        "confidence": 0.0,                 # 0.0-1.0, affidabilità riconoscimento
    }


# ============================================================
# VALIDAZIONE
# ============================================================

def validate_profile(profile):
    """
    Valida un profilo di calibrazione.
    Ritorna (is_valid, list[str_errors]).
    """
    errors = []

    if not isinstance(profile, dict):
        return False, ["Profilo non è un dizionario"]

    # Versione
    if profile.get("version") != CANONICAL_VERSION:
        errors.append(f"Versione non supportata: {profile.get('version')} (attesa {CANONICAL_VERSION})")

    # Client
    client = profile.get("client", {})
    if not client.get("name"):
        errors.append("Nome client mancante")

    # Risoluzione
    res = profile.get("resolution", {})
    if not res.get("width") or not res.get("height"):
        errors.append("Risoluzione mancante (width/height)")
    elif res["width"] < 400 or res["height"] < 300:
        errors.append(f"Risoluzione troppo piccola: {res['width']}x{res['height']}")

    # Seats (almeno 6)
    seats = profile.get("seats", {})
    if len(seats) < 6:
        errors.append(f"Numero sedie insufficiente: {len(seats)} (minimo 6)")

    # Act targets (almeno fold/check/raise)
    act = profile.get("act_targets", {})
    for key in ACTION_BUTTONS_MIN:
        target = act.get(key, {})
        if not target.get("x") and not target.get("y"):
            errors.append(f"Coordinate azione '{key}' mancanti")

    # Hero
    hero = profile.get("hero", {})
    if not hero.get("name"):
        errors.append("Nome Hero mancante")

    return len(errors) == 0, errors


def validate_game_state(state):
    """
    Valida uno stato di gioco.
    Ritorna (is_valid, list[str_errors]).
    """
    errors = []

    if not isinstance(state, dict):
        return False, ["State non è un dizionario"]

    # Carte devono essere in formato Treys
    for card in state.get("hole_cards", []):
        if not isinstance(card, str) or len(card) < 2:
            errors.append(f"Carta non valida: {card}")

    # Board max 5
    board = state.get("board", [])
    if len(board) > 5:
        errors.append(f"Board troppo lunga: {len(board)} carte (max 5)")

    # Pot deve essere numerico
    pot = state.get("pot")
    if pot is not None and not isinstance(pot, (int, float)):
        errors.append(f"Pot non numerico: {pot}")

    # Phase deve essere valida
    valid_phases = {"PREFLOP", "FLOP", "TURN", "RIVER", "UNKNOWN"}
    if state.get("phase") not in valid_phases:
        errors.append(f"Fase non valida: {state.get('phase')}")

    return len(errors) == 0, errors


# ============================================================
# I/O
# ============================================================

def save_profile(profile, filepath):
    """Salva profilo di calibrazione su file JSON."""
    profile["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    os.makedirs(os.path.dirname(filepath) if os.path.dirname(filepath) else ".", exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(profile, f, indent=2, ensure_ascii=False)
    return filepath


def load_profile(filepath):
    """Carica profilo di calibrazione da file JSON."""
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def save_game_state(state, filepath):
    """Salva stato di gioco su file JSON."""
    os.makedirs(os.path.dirname(filepath) if os.path.dirname(filepath) else ".", exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
    return filepath


def load_game_state(filepath):
    """Carica stato di gioco da file JSON."""
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


# ============================================================
# COMPATIBILITÀ POKERBOTAGENT
# ============================================================

def profile_to_see_config(profile):
    """
    Converte un profilo Table Recognition nel formato che
    PokerBotAgent si aspetta da see.py (layout JSON).
    Questo permette al PokerBotAgent di usare i profili prodotti
    da questo strumento senza modifiche.
    """
    # Act targets: assicura che CHECK/CALL e RAISE/ALLIN/BET condividano
    # le coordinate quando non calibrate separatamente (come da convenzione).
    act = dict(profile.get("act_targets") or {})
    # CALL ← CHECK se manca
    if not _has_coords(act.get("call")):
        act["call"] = dict(act.get("check", {"x": 0, "y": 0, "w": 0, "h": 0}))
    # CHECK ← CALL se manca
    if not _has_coords(act.get("check")):
        act["check"] = dict(act.get("call", {"x": 0, "y": 0, "w": 0, "h": 0}))
    # ALLIN ← RAISE se manca
    if not _has_coords(act.get("allin")):
        act["allin"] = dict(act.get("raise", {"x": 0, "y": 0, "w": 0, "h": 0}))
    # BET ← RAISE se manca (BB non rilanciato: FOLD-CHECK-BET, stessa pos di RAISE)
    if not _has_coords(act.get("bet")):
        act["bet"] = dict(act.get("raise", {"x": 0, "y": 0, "w": 0, "h": 0}))

    layout = {
        "resolution": f"{profile['resolution']['width']}x{profile['resolution']['height']}",
        "hero_seat": profile["hero"].get("seat"),
        "seats": profile.get("seats", {}),
        "act_targets": act,
        "table_roi": profile.get("table_roi", {"x": 0, "y": 0, "w": 0, "h": 0}),
        "override_rois": profile.get("override_rois", {}),
    }
    return layout


def _has_coords(target):
    """True se un act target ha coordinate non zero."""
    if not isinstance(target, dict):
        return False
    return bool(target.get("x") or target.get("y"))


def game_state_to_pokerbot(state):
    """
    Converte uno stato Table Recognition nel formato esatto
    che main._parse_vision_output() produce.
    Questo è il formato che eval_engine.evaluate() consuma.
    """
    return {
        "hole_cards": state.get("hole_cards", []),
        "board": state.get("board", []),
        "pot": state.get("pot"),
        "move_timer_seconds_remaining": state.get("move_timer_seconds_remaining"),
        "players": state.get("players", []),
        "phase": state.get("phase", "UNKNOWN"),
        "tournament": state.get("tournament", {}),
    }


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":
    # Test: crea profilo vuoto, validalo, converti
    profile = make_empty_profile()
    profile["client"]["name"] = "test_client"
    profile["resolution"] = {"width": 899, "height": 742}
    profile["seats"] = {str(i): {"x": 100*i, "y": 100} for i in range(1, 10)}
    profile["hero"]["seat"] = 3
    profile["hero"]["name"] = "hero"
    profile["act_targets"] = {
        "fold": {"x": 456, "y": 686, "w": 80, "h": 30},
        "check": {"x": 606, "y": 686, "w": 80, "h": 30},
        "raise": {"x": 750, "y": 685, "w": 80, "h": 30},
    }

    valid, errors = validate_profile(profile)
    print(f"Profilo valido: {valid}")
    if errors:
        for e in errors:
            print(f"  - {e}")

    # Test: crea stato vuoto
    state = make_game_state()
    state["hole_cards"] = ["As", "Kh"]
    state["board"] = ["7c", "8d", "2h"]
    state["pot"] = 5110
    state["phase"] = "FLOP"

    valid2, errors2 = validate_game_state(state)
    print(f"\nStato valido: {valid2}")
    if errors2:
        for e in errors2:
            print(f"  - {e}")

    # Test: conversione compatibilità
    layout = profile_to_see_config(profile)
    pb_state = game_state_to_pokerbot(state)
    print(f"\nLayout per PokerBotAgent: {json.dumps(layout, indent=2)[:200]}...")
    print(f"Stato per PokerBotAgent: {json.dumps(pb_state, indent=2)[:200]}...")

    # Test: salva e ricarica
    save_profile(profile, "/tmp/test_profile.json")
    loaded = load_profile("/tmp/test_profile.json")
    assert loaded["client"]["name"] == "test_client"
    print("\n✓ Tutti i test passati!")
