#!/usr/bin/env python3
"""
PokerTableScope — Configurazione
"""

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# LM Studio
LMSTUDIO_URL = "http://localhost:1234/v1/chat/completions"
VISION_MODEL = "qwen3-vl-8b-instruct"
VISION_MAX_TOKENS = 1000

# Screenshot
SCREENSHOTS_DIR = os.path.join(BASE_DIR, "screenshots")
PROFILES_DIR = os.path.join(BASE_DIR, "profiles")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

# Crea cartelle se non esistono
for d in [SCREENSHOTS_DIR, PROFILES_DIR, OUTPUT_DIR]:
    os.makedirs(d, exist_ok=True)

# Formati tavolo supportati
TABLE_FORMATS = ["6max", "9max"]

# Risoluzioni comuni
RESOLUTIONS = {
    "899x742": (899, 742),
    "1280x720": (1280, 720),
    "1366x768": (1366, 768),
    "1920x1080": (1920, 1080),
}

# GUI
GUI_TITLE = "PokerTableScope — Calibratore Universale"
# Nome hero (usato nel prompt Vision per identificare il giocatore principale)
HERO_NAME = "hero"

