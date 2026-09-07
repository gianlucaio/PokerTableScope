#!/usr/bin/env python3
"""
PokerTableScope — Vision Analyzer
Estrae informazioni strutturate dagli screenshot usando LM Studio Vision.
"""

import base64
import json
import cv2
import requests

from config import LMSTUDIO_URL, VISION_MODEL, VISION_MAX_TOKENS, HERO_NAME
from canonical import ACTION_BUTTONS


# ============================================================
# PROMPT ANALISI SINGOLO SCREENSHOT
# ============================================================

VISION_SYSTEM_PROMPT = f"""# RUOLO
Sei uno specialista nell'analisi visiva di tavoli da poker online tramite
screenshot. Il tuo unico compito è osservare l'immagine fornita ed estrarre
con precisione le informazioni richieste. Non sei un assistente generico e
non fornisci consigli di gioco, strategie o commenti — esegui esclusivamente
il compito di rilevamento assegnato.

# REGOLA FONDAMENTALE — NESSUNA INVENZIONE
Riporta SOLO ciò che vedi effettivamente nell'immagine. Se una carta, un nome,
un valore o un seme non è leggibile con certezza (per bassa risoluzione,
carta coperta, angolo di ripresa, sfocatura), NON indovinare e NON dedurre
per completezza logica. Dichiara esplicitamente l'elemento come "non
leggibile" o "non visibile" invece di inventare un valore plausibile.
Non presumere carte, giocatori o informazioni che non sono visibili
nello screenshot, anche se ti sembrano "probabili" in base al contesto
di gioco.

# IDENTIFICAZIONE DEI SEMI TRAMITE COLORE
In questo tavolo i semi NON usano i colori standard (rosso/nero classici),
ma uno schema personalizzato. Identifica il seme di ogni carta osservando
il colore del simbolo, secondo questa mappatura fissa e vincolante:
- Colore VERDE → seme Fiori (Clubs)
- Colore NERO → seme Picche (Spades)
- Colore ROSSO → seme Cuori / Hearts
- Colore BLU → seme Denari / Diamonds (attenzione: non standard, il seme
  "denari/diamonds" qui è BLU, non rosso come nei mazzi tradizionali)

Applica sempre e solo questa mappatura specifica di questo tavolo. Non usare
convenzioni di colore di mazzi da poker standard.

# COSA DEVI RILEVARE NELLO SCREENSHOT
Per ogni carta visibile sul tavolo (carte comuni al centro e, se visibili,
carte in mano ai giocatori):
- Valore della carta (es. Asso, K, Q, J, 10, 9... fino a 2)
- Seme della carta, dedotto dal colore secondo la mappatura sopra

Per ogni giocatore visibile al tavolo:
- Nome utente esatto, così come appare nello screenshot (riportalo carattere
  per carattere, senza correggere errori di battitura o abbreviazioni)
- Stack di fiches visibile accanto al nome
- Stato del seat: indica se il giocatore è ancora "attivo" (in mano, partecipa
  alla mano corrente) oppure "oscuro" (non più in gioco perché ha foldato od è
  in sit-out). Come guida visiva: una zona del seat chiara/accesa con nome e
  stack visibili indica di norma un giocatore attivo; una zona attenuata/scura
  indica un giocatore che ha foldato o è in sit-out. ATTENZIONE: anche se la
  zona appare chiara, un giocatore che ha foldato in un round precedente non è
  più attivo nella mano corrente — lo stato "attivo" si riferisce alla presenza
  nella mano corrente, non alla luminosità della zona da sola. Riporta
  esplicitamente lo stato (attivo/oscuro) per ogni giocatore, anche quando
  nome e stack sono visibili.

# INFORMAZIONI TORNEO (barra in alto)
Se nella parte superiore dello schermo è visibile una barra informativa del
torneo, leggi e riporta:
- Prossimo livello blind (es. "300/600" o "Next: 500/1000")
- Ante (se presente, es. "Ante 75" o "A75")
- Giocatori rimasti sul totale (es. "45/200" o "45 left")
- Posizioni paganti in finale (es. "Paid: 30" o "ITM: 30")
Se la barra non è visibile o un campo non è leggibile, dichiaralo come
"non visibile" — non inventare valori.

# IDENTIFICAZIONE DELL'HERO
Il giocatore chiamato "{HERO_NAME}" è l'HERO (il punto
di vista principale della mano). Identificalo esplicitamente come tale nella
risposta, distinguendolo dagli altri giocatori al tavolo. Se il nome utente
non è visibile o leggibile nello screenshot, dichiaralo esplicitamente invece
di assumere quale giocatore sia l'hero.

# FORMATO DI OUTPUT
Rispondi in modo strutturato, ad esempio:

Carte comuni sul tavolo:
- [valore] di [seme]
- [valore] di [seme]
...

Giocatori rilevati:
- [nome utente] — [carte in mano, se visibili, altrimenti "non visibili"] — [stato seat: attiva/oscura]
...

Hero: [nome utente, con le sue carte se visibili — oppure "non identificato
nello screenshot" se il nome non compare]

Info torneo (se visibili nella barra in alto):
- "blind": [prossimo livello] (es. "300/600")
- "ante": [valore, se presente, altrimenti "0"]
- "players_remaining": [rimasti/totale] (es. "45/200")
- "paid_positions": [numero posizioni paganti, se visibile]

Elementi non leggibili/non visibili: [elenco, se presenti]"""


# ============================================================
# PROMPT PER CROP ROI (analisi zoomata delle carte)
# ============================================================

CROP_BOARD_PROMPT = f"""# RUOLO
Sei uno specialista nell'analisi visiva di TAVOLE DA POKER ONLINE.
Questa immagine è un CROP (ritaglio) della zona del board di un tavolo poker.
Il tuo compito è identificare con precisione le CARTE COMUNI visibili.

# REGOLA FONDAMENTALE — NESSUNA INVENZIONE
Riporta SOLO ciò che vedi effettivamente. Se una carta non è leggibile,
dichiara "non leggibile" invece di inventare.

# IDENTIFICAZIONE SEMI tramite COLORE (4-color deck):
- VERDE → Fiori (Clubs)
- NERO → Picche (Spades)
- ROSSO → Cuori (Hearts)
- BLU → Denari (Diamonds)

# FORMATO OUTPUT
Carte comuni sul tavolo:
- [valore] di [seme]
...
(Dichiara "non visibile" se il board è vuoto o non leggibile)"""


CROP_HERO_PROMPT = f"""# RUOLO
Sei uno specialista nell'analisi visiva di TAVOLE DA POKER ONLINE.
Questa immagine è un CROP (ritaglio) della zona delle CARTE IN MANO all'HERO
(nome utente: {HERO_NAME}).

# REGOLA FONDAMENTALE — NESSUNA INVENZIONE
Riporta SOLO le carte che vedi effettivamente. Se non sono leggibili,
dichiara "non leggibile".

# IDENTIFICAZIONE SEMI tramite COLORE (4-color deck):
- VERDE → Fiori (Clubs)
- NERO → Picche (Spades)
- ROSSO → Cuori (Hearts)
- BLU → Denari (Diamonds)

# FORMATO OUTPUT
Carte Hero:
- [valore] di [seme]
- [valore] di [seme]
(Se non visibili: "non visibili")"""


# ============================================================
# CLASS
# ============================================================

class VisionAnalyzer:
    """Analizza screenshot usando il modello Vision di LM Studio."""

    def __init__(self, url=LMSTUDIO_URL, model=VISION_MODEL):
        self.url = url
        self.model = model
        self.timeout = 60

    def encode_image(self, image_path):
        """Codifica un'immagine in base64 per l'API Vision.

        Riduce a max 768px lato lungo (limite server LM Studio)
        e usa JPEG q80 per ridurre il base64.
        """
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"Immagine non leggibile: {image_path}")
        h, w = img.shape[:2]
        max_dim = 768
        scale = max_dim / max(h, w)
        if scale < 1:
            img = cv2.resize(img, (int(w * scale), int(h * scale)))
        ok, buf = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 80])
        return base64.b64encode(buf.tobytes()).decode("utf-8")

    def _encode_image_crop(self, image_path, roi):
        """Crop una regione dall'immagine e la codifica in base64.
        roi: dict con x, y, w, h in pixel originali.
        Il crop viene ridimensionato a max 768px lato lungo con upscale
        (zoom massimo consentito dal server Vision).
        """
        img = cv2.imread(image_path)
        if img is None:
            return None
        h_orig, w_orig = img.shape[:2]
        x, y, w, h = int(roi["x"]), int(roi["y"]), int(roi["w"]), int(roi["h"])
        # Clamp ai bordi immagine
        x = max(0, min(x, w_orig - 1))
        y = max(0, min(y, h_orig - 1))
        w = max(1, min(w, w_orig - x))
        h = max(1, min(h, h_orig - y))
        crop = img[y:y+h, x:x+w].copy()
        # Ridimensiona il crop a max 768px lato lungo
        ch, cw = crop.shape[:2]
        scale = 768 / max(ch, cw)
        if scale != 1:
            crop = cv2.resize(crop, (int(cw * scale), int(ch * scale)),
                              interpolation=cv2.INTER_CUBIC if scale > 1 else cv2.INTER_AREA)
        ok, buf = cv2.imencode('.jpg', crop, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if not ok:
            return None
        return base64.b64encode(buf.tobytes()).decode("utf-8")

    def _call_vision(self, image_b64, prompt, max_tokens=None):
        """Chiamata Vision generica: immagine base64 + prompt → risposta testo."""
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {
                            "url": f"data:image/jpeg;base64,{image_b64}"
                        }}
                    ]
                }
            ],
            "max_tokens": max_tokens or VISION_MAX_TOKENS,
        }
        try:
            resp = requests.post(self.url, json=payload, timeout=self.timeout)
            resp.raise_for_status()
            result = resp.json()
            return result["choices"][0]["message"]["content"]
        except requests.exceptions.ConnectionError:
            print("[ANALYZER] ERRORE: LM Studio non raggiungibile.")
            return None
        except requests.exceptions.Timeout:
            print("[ANALYZER] Timeout: modello troppo lento")
            return None
        except Exception as e:
            print(f"[ANALYZER] Errore Vision: {e}")
            return None

    def analyze_with_crops(self, image_path, profile=None):
        """Analisi avanzata con crop ROI per lettura carte precisa.

        Se il profilo fornisce table_roi e/o override_rois (board, hero),
        estrae le regioni interessate dall'immagine originale, le upscale
        a 768px e le analizza con un prompt dedicato alle carte.

        Args:
            image_path: percorso immagine
            profile: profilo calibrazione (opzionale, per ottenere i ROI)

        Returns:
            dict risultato unificato (stesso formato di analyze_screenshot)
        """
        print(f"[ANALYZER] Analisi con crop: {image_path}")

        # --- FASE 1: analisi intera (seats, pulsanti, timer, blind) ---
        img_b64 = self.encode_image(image_path)
        content = self._call_vision(img_b64, VISION_SYSTEM_PROMPT)
        if not content:
            return None
        result = self._parse_response(content)
        if result is None:
            return None

        # --- FASE 2: cropROI per carte (se profilo fornisce ROI) ---
        if not profile:
            return result

        crops = []  # (roi_dict, prompt)
        table_roi = profile.get("table_roi")
        override_rois = profile.get("override_rois") or {}

        # Board ROI: crop centrato sul board
        if table_roi and table_roi.get("w", 0) > 0:
            # Il board è circa nella zona centrale-inferiore del tavolo
            # Crop una striscia orizzontale centrale (~40% altezza, parte bassa)
            tr = table_roi
            board_crop = {
                "x": tr["x"] + int(tr["w"] * 0.25),
                "y": tr["y"] + int(tr["h"] * 0.55),
                "w": int(tr["w"] * 0.50),
                "h": int(tr["h"] * 0.25),
            }
            crops.append((board_crop, CROP_BOARD_PROMPT))

        # Hero cards ROI (se definito negli override_rois)
        hero_roi = override_rois.get("hero_cards") or override_rois.get("hero_stack")
        if hero_roi and hero_roi.get("w", 0) > 0:
            crops.append((hero_roi, CROP_HERO_PROMPT))

        # Board ROI esplicito (se definito negli override_rois)
        board_roi = override_rois.get("board") or profile.get("board_roi")
        if board_roi and board_roi.get("w", 0) > 0 and board_roi != (crops[0][0] if crops else None):
            crops.append((board_roi, CROP_BOARD_PROMPT))

        for roi, prompt in crops:
            crop_b64 = self._encode_image_crop(image_path, roi)
            if not crop_b64:
                continue
            crop_content = self._call_vision(crop_b64, prompt)
            if not crop_content:
                continue
            crop_result = self._parse_response(crop_content)
            if crop_result:
                result = self._merge_crop_result(result, crop_result)

        return result

    def _merge_crop_result(self, base, crop):
        """Unisce un risultato crop al risultato base.
        Il crop ha priorità su board e hero (più preciso).
        """
        if not crop:
            return base

        # Board: sovrascrivi se il crop ha carte valide
        crop_board = crop.get("board") or []
        valid_board = [c for c in crop_board if c and c != "??" and c.strip()]
        if valid_board:
            base["board"] = valid_board

        # Hero: sovrascrivi se il crop ha carte
        crop_hero = crop.get("hero", {})
        if isinstance(crop_hero, dict) and crop_hero.get("cards"):
            if "hero" not in base or not isinstance(base["hero"], dict):
                base["hero"] = {}
            base["hero"]["cards"] = crop_hero["cards"]

        # Seats: mantieni dal base (il crop non li vede tutti)
        # Timer/blinds/pulsanti: mantieni dal base

        return base

    def analyze_screenshot(self, image_path):
        """
        Analizza uno screenshot e restituisce il JSON strutturato.
        Returns:
            dict con i dati estratti, o None se errore
        """
        print(f"[ANALYZER] Analisi: {image_path}")

        img_b64 = self.encode_image(image_path)

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": VISION_SYSTEM_PROMPT
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{img_b64}"
                            }
                        }
                    ]
                }
            ],
            "max_tokens": VISION_MAX_TOKENS,
        }

        try:
            resp = requests.post(self.url, json=payload, timeout=self.timeout)
            resp.raise_for_status()
            result = resp.json()
            content = result["choices"][0]["message"]["content"]
            return self._parse_response(content)
        except requests.exceptions.ConnectionError:
            print("[ANALYZER] ERRORE: LM Studio non raggiungibile. Assicurati che sia attivo.")
            return None
        except requests.exceptions.Timeout:
            print("[ANALYZER] Timeout: modello troppo lento o sovraccarico")
            return None
        except Exception as e:
            print(f"[ANALYZER] Errore: {e}")
            return None

    def analyze_image_array(self, img):
        """
        Analizza un numpy array (BGR) invece di un file.
        Salva temporaneamente e analizza.
        """
        import tempfile
        import os

        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        cv2.imwrite(tmp.name, img)  # imwrite accetta BGR direttamente
        result = self.analyze_screenshot(tmp.name)
        os.unlink(tmp.name)
        return result

    def _parse_response(self, content):
        """Estrae i dati dalla risposta del modello.

        Supporta due formati:
        1. JSON valido (vecchio prompt) — parsing diretto
        2. Testo strutturato (nuovo prompt ottimizzato) — converte in dict

        Ritorna un dict con i dati estratti, o None se non riconosce nulla.
        """
        text = content.strip()
        if not text:
            return None

        # 1. Tentativo JSON
        start = text.find('{')
        end = text.rfind('}') + 1
        if start >= 0 and end > start:
            json_str = text[start:end]
            try:
                parsed = json.loads(json_str)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                pass  # non era JSON, prova testo strutturato

        # 2. Testo strutturato (nuovo prompt)
        return self._parse_structured_text(text)

    def _parse_structured_text(self, text):
        """Converte l'output testuale strutturato del nuovo prompt in dict.

        Input atteso (dalla guida PokerBotAgent vision_prompt.py):
          Carte comuni sul tavolo:
          - K di Picche
          ...

          Giocatori rilevati:
          - Maccarone120 — non visibili — attivo
          ...

          Hero: gianlucaio, con le sue carte se visibili
          Info torneo (se visibili nella barra in alto):
          - "blind": 300/600
          - "ante": 25
          - "players_remaining": 45/200
          - "paid_positions": 30

          Elementi non leggibili/non visibili: [...]
        """
        result = {
            "client_name": None,
            "platform": None,
            "resolution": None,
            "seats": {},
            "hero": {},
            "board": [],
            "pot": None,
            "blinds": {},
            "timer": None,
            "buttons": {},
        }
        lines = text.splitlines()
        section = None

        # Mappatura seme italiano → codice Treys
        suit_map = {
            "fiori": "c", "clubs": "c", "denari": "d", "diamonds": "d",
            "cuori": "h", "hearts": "h", "picche": "s", "spades": "s",
        }
        rank_map = {
            "asso": "A", "ace": "A", "re": "K", "king": "K", "regina": "Q",
            "queen": "Q", "jack": "J", "fante": "J", "dieci": "T", "10": "T",
        }

        for line in lines:
            line = line.strip()
            if not line:
                continue
            low = line.lower()

            # Cambio sezione
            if "carte comuni" in low:
                section = "board"
                continue
            if "carte hero" in low or ("hero" in low and "carte" in low):
                section = "hero_cards"
                continue
            if "giocatori" in low and "rilevati" in low:
                section = "players"
                continue
            if low.startswith("hero") or low.startswith("hero:"):
                section = "hero"
                continue
            if "info torneo" in low or "torneo" in low:
                section = "tournament"
                continue
            if "non leggibili" in low or "non visibili" in low:
                section = "unreadable"
                continue

            if section == "board" and line.startswith("-"):
                # "K di Picche" → "Ks"
                card_str = line.lstrip("- ").strip()
                parts = card_str.split(" di ")
                if len(parts) == 2:
                    rank = parts[0].strip().lower()
                    suit_word = parts[1].strip().lower()
                    suit_word = suit_word.split(" (")[0].strip()
                    rank_code = rank_map.get(rank, rank.upper() if len(rank) == 1 else None)
                    suit_code = suit_map.get(suit_word)
                    if rank_code and suit_code:
                        result["board"].append(f"{rank_code}{suit_code}")
                    else:
                        result["board"].append("??")

            elif section == "hero_cards" and line.startswith("-"):
                # "K di Picche" → "Ks" (carte hero dal crop)
                card_str = line.lstrip("- ").strip()
                parts = card_str.split(" di ")
                if len(parts) == 2:
                    rank = parts[0].strip().lower()
                    suit_word = parts[1].strip().lower()
                    suit_word = suit_word.split(" (")[0].strip()
                    rank_code = rank_map.get(rank, rank.upper() if len(rank) == 1 else None)
                    suit_code = suit_map.get(suit_word)
                    if rank_code and suit_code:
                        if "cards" not in result.get("hero", {}):
                            result.setdefault("hero", {})["cards"] = []
                        result["hero"]["cards"].append(f"{rank_code}{suit_code}")

            elif section == "players" and line.startswith("-"):
                # "Maccarone120 — non visibili — attivo"
                parts = [p.strip() for p in line.lstrip("- ").split("—")]
                if len(parts) >= 1:
                    name = parts[0]
                    # Stack: cerca numeri nel nome/stack
                    seat_num = str(len(result["seats"]) + 1)
                    result["seats"][seat_num] = {
                        "name": name,
                        "stack": None,
                        "x": 0,
                        "y": 0,
                    }

            elif section == "hero" and ":" in line:
                # "Hero: gianlucaio, con le sue carte se visibili"
                hero_part = line.split(":", 1)[1].strip()
                hero_name = hero_part.split(",")[0].strip()
                if hero_name and hero_name.lower() not in ("non identificato", "non visibile", "non leggibile"):
                    result["hero"]["name"] = hero_name
                    # Trova il seat con lo stesso nome
                    for seat_num, seat_data in result["seats"].items():
                        if seat_data.get("name", "").lower() == hero_name.lower():
                            result["hero"]["seat"] = int(seat_num)
                            break

            elif section == "tournament" and line.startswith("-"):
                # '- "blind": 300/600'
                if "blind" in line:
                    blind_val = line.split(":", 1)[1].strip().strip('"').strip()
                    parts = blind_val.split("/")
                    if len(parts) == 2:
                        result["blinds"]["sb"] = int(parts[0]) if parts[0].isdigit() else None
                        result["blinds"]["bb"] = int(parts[1]) if parts[1].isdigit() else None
                elif "ante" in line:
                    ante_val = line.split(":", 1)[1].strip().strip('"').strip()
                    result["blinds"]["ante"] = int(ante_val) if ante_val.isdigit() else 0
                elif "players_remaining" in line or "rimasti" in line:
                    pr_val = line.split(":", 1)[1].strip().strip('"').strip()
                    result["players_remaining"] = pr_val

        return result if result["seats"] or result["board"] else None

    def extract_game_state(self, analysis_result):
        """
        Converte il risultato dell'analisi in formato game_state canonico.
        Compatibile con main._parse_vision_output() del PokerBotAgent.
        """
        if not analysis_result:
            return None

        state = {
            "hole_cards": [],
            "board": [],
            "pot": None,
            "move_timer_seconds_remaining": None,
            "players": [],
            "phase": "UNKNOWN",
            "tournament": {},
        }

        # Board
        if analysis_result.get("board"):
            state["board"] = [c for c in analysis_result["board"]
                             if c and c != "??"]

        # Pot
        if analysis_result.get("pot") is not None:
            try:
                state["pot"] = int(analysis_result["pot"])
            except (ValueError, TypeError):
                pass

        # Timer
        timer_data = analysis_result.get("timer")
        if isinstance(timer_data, dict) and timer_data.get("value") is not None:
            try:
                state["move_timer_seconds_remaining"] = int(timer_data["value"])
            except (ValueError, TypeError):
                pass

        # Players
        seats = analysis_result.get("seats", {})
        hero_info = analysis_result.get("hero", {})

        for seat_num, seat_data in seats.items():
            if not isinstance(seat_data, dict):
                continue
            player = {
                "seat": int(seat_num) if seat_num.isdigit() else None,
                "name": seat_data.get("name"),
                "stack": seat_data.get("stack"),
                "bet_amount": 0,
                "action": None,
                "active": True,
                "is_hero": (seat_data.get("name", "").lower() ==
                           hero_info.get("name", "").lower() if hero_info.get("name") else False),
            }
            state["players"].append(player)

        # Phase dal board
        board_len = len(state["board"])
        if board_len == 0:
            state["phase"] = "PREFLOP"
        elif board_len == 3:
            state["phase"] = "FLOP"
        elif board_len == 4:
            state["phase"] = "TURN"
        elif board_len == 5:
            state["phase"] = "RIVER"

        return state

    def extract_calibration(self, analysis_result):
        """
        Converte il risultato dell'analisi in dati di calibrazione.
        Ritorna un profilo parziale pronto per essere salvato.
        """
        if not analysis_result:
            return None

        profile = {
            "client": {
                "name": analysis_result.get("client_name", "unknown"),
                "platform": analysis_result.get("platform", "unknown"),
            },
            "resolution": {
                "width": analysis_result.get("resolution", {}).get("w", 0),
                "height": analysis_result.get("resolution", {}).get("h", 0),
            },
            "seats": {},
            "hero": {
                "seat": analysis_result.get("hero", {}).get("seat"),
                "name": analysis_result.get("hero", {}).get("name", "hero"),
            },
            "act_targets": {},
        }

        # Seats (solo coordinate, senza nomi/stack)
        for seat_num, seat_data in analysis_result.get("seats", {}).items():
            if isinstance(seat_data, dict):
                profile["seats"][seat_num] = {
                    "x": seat_data.get("x", 0),
                    "y": seat_data.get("y", 0),
                }

        # Pulsanti
        buttons = analysis_result.get("buttons", {})
        for btn_name in ACTION_BUTTONS:
            btn_data = buttons.get(btn_name, {})
            if isinstance(btn_data, dict):
                profile["act_targets"][btn_name] = {
                    "x": btn_data.get("x", 0),
                    "y": btn_data.get("y", 0),
                }

        return profile


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":
    analyzer = VisionAnalyzer()
    print(f"[TEST] Modello: {analyzer.model}")
    print(f"[TEST] URL: {analyzer.url}")

    # Test connessione
    try:
        resp = requests.get("http://localhost:1234/v1/models", timeout=5)
        models = resp.json().get("data", [])
        print(f"[TEST] Modelli disponibili: {[m['id'] for m in models]}")
    except:
        print("[TEST] LM Studio non raggiungibile")

    print("\n✓ Analyzer module OK")
