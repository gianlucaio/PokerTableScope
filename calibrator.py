#!/usr/bin/env python3
"""
PokerTableScope — Calibrator
Gestisce i profili di calibrazione: creazione, modifica, salvataggio, export.
"""

import os
import json
import time
from canonical import (
    make_empty_profile, validate_profile, save_profile, load_profile,
    profile_to_see_config, CANONICAL_VERSION
)
from config import PROFILES_DIR, OUTPUT_DIR, BASE_DIR


class Calibrator:
    """
    Gestisce il ciclo di vita di un profilo di calibrazione:
    creazione → modifica → validazione → salvataggio → export per PokerBotAgent.
    """

    def __init__(self):
        os.makedirs(PROFILES_DIR, exist_ok=True)
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        self.current_profile = None
        self.current_file = None

    # ============================================================
    # RINOMINA PROFILO
    # ============================================================

    def rename_profile(self, new_name):
        """Rinomina il profilo corrente (campo name usato come preset ID)."""
        if not self.current_profile:
            return
        self.current_profile["name"] = new_name

    # ============================================================
    # CREAZIONE
    # ============================================================

    def new_profile(self, client_name="unknown", platform="web", width=899, height=742):
        """Crea un nuovo profilo vuoto con i parametri base."""
        self.current_profile = make_empty_profile()
        self.current_profile["client"]["name"] = client_name
        self.current_profile["client"]["platform"] = platform
        self.current_profile["resolution"]["width"] = width
        self.current_profile["resolution"]["height"] = height
        self.current_file = None
        return self.current_profile

    # ============================================================
    # CARICAMENTO / SALVATAGGIO
    # ============================================================

    def load(self, filepath=None):
        """Carica un profilo da file. Se None, carica l'ultimo salvato."""
        if filepath is None:
            filepath = self._find_latest_profile()
            if filepath is None:
                print("[CALIBRATOR] Nessun profilo trovato")
                return None

        self.current_profile = load_profile(filepath)
        self.current_file = filepath
        print(f"[CALIBRATOR] Profilo caricato: {filepath}")
        return self.current_profile

    @staticmethod
    def _sanitize_name(name):
        """Sanifica un nome preset per usarlo come filename sicuro.
        Rimuove caratteri pericolosi (/, \\, :, *, ?, \", <, >, |), spazi
        iniziali/finali, e rifiuta nomi riservati/collisioni col filesystem.
        """
        if not name:
            return ""
        name = name.strip()
        # Sostituisci caratteri non sicuri per il filesystem
        import re
        cleaned = re.sub(r'[\\/:*?"<>|]', "_", name)
        # Rifiuta path traversal e nomi riservati
        if cleaned in (".", "..") or cleaned.lower() in (
                "con", "prn", "aux", "nul",
                "com1", "com2", "com3", "com4", "com5",
                "com6", "com7", "com8", "com9",
                "lpt1", "lpt2", "lpt3", "lpt4", "lpt5",
                "lpt6", "lpt7", "lpt8", "lpt9"):
            return ""
        return cleaned.strip()

    def save(self, filepath=None):
        """Salva il profilo corrente. Il filename usa il name preset se disponibile."""
        if self.current_profile is None:
            print("[CALIBRATOR] Nessun profilo da salvare")
            return None

        old_file = self.current_file  # per pulizia file orfano al rename

        if filepath is None:
            # Determina il nome preset (se possibile) → salva SEMPRE in PROFILES_DIR
            preset_name = self._sanitize_name(
                self.current_profile.get("name", "") or "")
            client = self.current_profile.get("client", {}).get("name", "unknown")
            # Usa current_file SOLO se è già dentro PROFILES_DIR (per non smarrire
            # i profili in altre cartelle durante salvataggi ripetuti)
            if preset_name:
                filepath = os.path.join(PROFILES_DIR, f"{preset_name}.json")
            elif self.current_file and os.path.realpath(
                    os.path.dirname(self.current_file)) == os.path.realpath(PROFILES_DIR):
                filepath = self.current_file
            else:
                ts = time.strftime("%Y%m%d_%H%M%S_%f")[:-3]  # con millisecondi
                filepath = os.path.join(PROFILES_DIR, f"profile_{client}_{ts}.json")

        # Se il nome è cambiato (nuovo file) e c'era un vecchio file dentro
        # PROFILES_DIR, rimuovi il vecchio per evitare file orfani 'ghost'.
        if old_file and os.path.realpath(os.path.dirname(old_file)) == os.path.realpath(PROFILES_DIR):
            old_abs = os.path.realpath(old_file)
            new_abs = os.path.realpath(filepath)
            if old_abs != new_abs:
                try:
                    os.remove(old_file)
                    print(f"[CALIBRATOR] Rimosso vecchio profilo orfano: {old_file}")
                except OSError:
                    pass  # se non esiste, ignora

        save_profile(self.current_profile, filepath)
        self.current_file = filepath
        print(f"[CALIBRATOR] Profilo salvato: {filepath}")
        return filepath

    # ============================================================
    # TEMPLATE OVERRIDE
    # ============================================================

    TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

    def save_override_template(self, name):
        """Salva i campi manuali del profilo corrente come template riutilizzabile."""
        if not self.current_profile:
            return None
        os.makedirs(self.TEMPLATES_DIR, exist_ok=True)
        p = self.current_profile
        template = {}
        # Copia solo i campi manuali e gli override
        for key in ("_manual_board", "_manual_hero_cards", "_manual_pot",
                     "_manual_timer", "_manual_blinds", "_manual_tournament"):
            if key in p:
                template[key] = p[key]
        # Copia override_rois
        if p.get("override_rois"):
            template["override_rois"] = p["override_rois"]
        filepath = os.path.join(self.TEMPLATES_DIR, f"{name}.json")
        with open(filepath, "w") as f:
            json.dump(template, f, indent=2, ensure_ascii=False)
        print(f"[CALIBRATOR] Template salvato: {filepath}")
        return filepath

    def load_override_template(self, name):
        """Carica un template e lo applica al profilo corrente."""
        if not self.current_profile:
            return False
        filepath = os.path.join(self.TEMPLATES_DIR, f"{name}.json")
        if not os.path.exists(filepath):
            print(f"[CALIBRATOR] Template non trovato: {name}")
            return False
        with open(filepath) as f:
            template = json.load(f)
        # Applica tutti i campi del template al profilo corrente
        for key, val in template.items():
            if key == "override_rois":
                self.current_profile.setdefault("override_rois", {}).update(val)
            else:
                self.current_profile[key] = val
        print(f"[CALIBRATOR] Template applicato: {name}")
        return True

    def list_templates(self):
        """Elenca i template disponibili."""
        if not os.path.exists(self.TEMPLATES_DIR):
            return []
        return [f[:-5] for f in os.listdir(self.TEMPLATES_DIR)
                if f.endswith(".json")]

    # ============================================================
    # MODIFICA
    # ============================================================

    def set_client(self, name=None, platform=None, language=None):
        """Aggiorna info client."""
        if not self.current_profile:
            return
        if name:
            self.current_profile["client"]["name"] = name
        if platform:
            self.current_profile["client"]["platform"] = platform
        if language:
            self.current_profile["client"]["language"] = language

    def set_resolution(self, width, height):
        """Aggiorna risoluzione."""
        if not self.current_profile:
            return
        self.current_profile["resolution"]["width"] = width
        self.current_profile["resolution"]["height"] = height

    def set_seat(self, seat_num, x, y):
        """Imposta coordinate di un seat."""
        if not self.current_profile:
            return
        self.current_profile["seats"][str(seat_num)] = {"x": x, "y": y}

    def remove_seat(self, seat_num):
        """Rimuove un seat."""
        if not self.current_profile:
            return
        self.current_profile["seats"].pop(str(seat_num), None)

    def set_hero(self, seat=None, name=None, dynamic=None):
        """Aggiorna info Hero."""
        if not self.current_profile:
            return
        if seat is not None:
            self.current_profile["hero"]["seat"] = seat
        if name:
            self.current_profile["hero"]["name"] = name
        if dynamic is not None:
            self.current_profile["hero"]["dynamic_seat"] = dynamic

    def set_button(self, action, x, y):
        """Imposta coordinate di un pulsante azione (centro click)."""
        if not self.current_profile:
            return
        # Preserva w,h esistenti se presenti
        existing = self.current_profile["act_targets"].get(action, {})
        self.current_profile["act_targets"][action] = {
            "x": x, "y": y,
            "w": existing.get("w", 0), "h": existing.get("h", 0),
        }

    def set_button_size(self, action, w, h):
        """Imposta le dimensioni (w, h) dell'area cliccabile di un pulsante azione.
        Serve per l'offset casuale anti-ban: PokerBotAgent genererà click
        casuali dentro il rettangolo (x, y, w, h) invece che sempre allo stesso pixel."""
        if not self.current_profile:
            return
        existing = self.current_profile["act_targets"].get(action, {})
        self.current_profile["act_targets"][action] = {
            "x": existing.get("x", 0), "y": existing.get("y", 0),
            "w": w, "h": h,
        }

    def set_notes(self, notes):
        """Imposta note."""
        if not self.current_profile:
            return
        self.current_profile["notes"] = notes

    def set_table_roi(self, x, y, w, h):
        """Imposta la regione di interesse del tavolo (ROI) sullo schermo."""
        if not self.current_profile:
            return
        self.current_profile["table_roi"] = {"x": x, "y": y, "w": w, "h": h}

    def set_override_roi(self, field, x, y, w, h):
        """
        Imposta la ROI di un campo override (es. 'pot', 'hero_stack').
        Per gli stack avversari usare 'stacks:N' (N = 1..9).
        Crea automaticamente override_rois se mancante (profilo retro-compatibile).
        """
        if not self.current_profile:
            return
        rois = self.current_profile.setdefault("override_rois", {})
        if ":" in field:
            parent, key = field.split(":", 1)
            rois.setdefault(parent, {})[key] = {"x": x, "y": y, "w": w, "h": h}
        else:
            rois[field] = {"x": x, "y": y, "w": w, "h": h}

    def import_from_analyzer(self, calibration_data):
        """
        Importa dati di calibrazione estratti dall'analyzer Vision.
        Sovrascrive i campi esistenti con quelli nuovi.
        """
        if not self.current_profile or not calibration_data:
            return

        # Client
        client = calibration_data.get("client", {})
        if client.get("name"):
            self.current_profile["client"]["name"] = client["name"]
        if client.get("platform"):
            self.current_profile["client"]["platform"] = client["platform"]

        # Resolution
        res = calibration_data.get("resolution", {})
        if res.get("width") and res.get("height"):
            self.current_profile["resolution"]["width"] = res["width"]
            self.current_profile["resolution"]["height"] = res["height"]

        # Seats
        seats = calibration_data.get("seats", {})
        if seats:
            self.current_profile["seats"] = seats

        # Hero
        hero = calibration_data.get("hero", {})
        if hero.get("seat"):
            self.current_profile["hero"]["seat"] = hero["seat"]
        if hero.get("name"):
            self.current_profile["hero"]["name"] = hero["name"]

        # Act targets
        act = calibration_data.get("act_targets") or {}
        if act:
            self.current_profile["act_targets"] = act

    # ============================================================
    # VALIDAZIONE E EXPORT
    # ============================================================

    def validate(self):
        """Valida il profilo corrente. Ritorna (is_valid, errors)."""
        if not self.current_profile:
            return False, ["Nessun profilo caricato"]
        return validate_profile(self.current_profile)

    def export_for_pokerbot(self, output_name=None, copy_to_pokerbot=False):
        """
        Esporta il profilo nel formato che PokerBotAgent si aspetta.
        Salva in output/ come file JSON compatibile con see.py layout.
        Se copy_to_pokerbot=True, copia anche in ~/Documenti/PokerBotAgent/layouts/
        """
        if not self.current_profile:
            print("[CALIBRATOR] Nessun profilo da esportare")
            return None

        valid, errors = self.validate()
        if not valid:
            print(f"[CALIBRATOR] Profilo non valido: {errors}")
            return None

        # Converti in formato PokerBotAgent
        layout = profile_to_see_config(self.current_profile)

        # Aggiungi metadati
        export = {
            "_metadata": {
                "generator": "PokerTableScope",
                "version": CANONICAL_VERSION,
                "created_at": self.current_profile.get("created_at"),
                "profile_file": self.current_file,
                "preset_name": self.current_profile.get("name", ""),
            },
            **layout,
        }

        # Salva
        client_name = self.current_profile["client"]["name"]
        if output_name is None:
            preset_name = self.current_profile.get("name", "")
            if preset_name:
                output_name = f"layout_{preset_name}.json"
            else:
                output_name = f"layout_{client_name}.json"

        filepath = os.path.join(OUTPUT_DIR, output_name)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(export, f, indent=2, ensure_ascii=False)

        print(f"[CALIBRATOR] Esportato per PokerBotAgent: {filepath}")

        # Copia nella cartella layouts di PokerBotAgent
        if copy_to_pokerbot:
            pokerbot_layouts = self._find_pokerbot_layouts_dir()
            if pokerbot_layouts:
                dst = os.path.join(pokerbot_layouts, output_name)
                import shutil
                shutil.copy(filepath, dst)
                print(f"[CALIBRATOR] Copiato in PokerBotAgent: {dst}")
            else:
                print("[CALIBRATOR] ⚠ Cartella layouts di PokerBotAgent non trovata")
                print("[CALIBRATOR] Copia manualmente il file in layouts/")
                return filepath

        return filepath

    def _find_pokerbot_layouts_dir(self):
        """Cerca la cartella layouts di PokerBotAgent."""
        import os
        home = os.path.expanduser("~")
        candidates = [
            os.path.join(home, "Documenti", "PokerBotAgent", "layouts"),
            os.path.join(home, "Documenti", "PokerbotAgent", "layouts"),
            os.path.join(home, "Scrivania", "PokerBotAgent v 0.1.0", "layouts"),
            os.path.join(home, "Documenti", "PokerBotAgent"),
        ]
        for c in candidates:
            if os.path.isdir(c):
                return c
        return None

    # ============================================================
    # LISTA PROFILI
    # ============================================================

    def list_profiles(self):
        """Elenca tutti i profili salvati."""
        profiles = []
        if not os.path.exists(PROFILES_DIR):
            return profiles

        for f in sorted(os.listdir(PROFILES_DIR)):
            if f.endswith(".json"):
                filepath = os.path.join(PROFILES_DIR, f)
                try:
                    p = load_profile(filepath)
                    profiles.append({
                        "file": filepath,
                        "client": p.get("client", {}).get("name", "?"),
                        "platform": p.get("client", {}).get("platform", "?"),
                        "resolution": f"{p.get('resolution', {}).get('width', '?')}x{p.get('resolution', {}).get('height', '?')}",
                        "seats": len(p.get("seats", {})),
                        "updated": p.get("updated_at", "?"),
                    })
                except Exception:
                    pass

        return profiles

    def _find_latest_profile(self):
        """Trova l'ultimo profilo salvato."""
        profiles = self.list_profiles()
        if profiles:
            return profiles[-1]["file"]
        return None


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":
    cal = Calibrator()

    # Test creazione
    p = cal.new_profile("test_web", "web", 899, 742)
    print(f"Profilo creato: {p['client']['name']}")

    # Test set seat
    for i in range(1, 7):
        cal.set_seat(i, 100 * i, 100)
    cal.set_hero(seat=3, name="hero")
    cal.set_button("fold", 456, 686)
    cal.set_button("check", 606, 686)
    cal.set_button("raise", 750, 685)

    # Test validazione
    valid, errors = cal.validate()
    print(f"Valido: {valid}, errori: {errors}")

    # Test salvataggio
    filepath = cal.save()
    print(f"Salvato: {filepath}")

    # Test export PokerBotAgent
    export_path = cal.export_for_pokerbot()
    print(f"Esportato: {export_path}")

    # Test lista
    profiles = cal.list_profiles()
    print(f"Profili trovati: {len(profiles)}")

    print("\n✓ Calibrator module OK")
