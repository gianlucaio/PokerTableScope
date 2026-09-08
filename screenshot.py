#!/usr/bin/env python3
"""
PokerTableScope — Screenshot Module
Gestisce cattura schermo, caricamento file, salvataggio e gestione immagini.
"""

import os
import time
import cv2
import numpy as np
from PIL import ImageGrab

from config import SCREENSHOTS_DIR


class ScreenshotManager:
    """Gestisce cattura, caricamento, salvataggio e visualizzazione di screenshot."""

    def __init__(self):
        os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
        self.current_image = None
        self.current_path = None

    # ============================================================
    # CATTURA SCHERMO
    # ============================================================

    def capture_screen(self, region=None):
        """
        Cattura l'intero schermo o una regione specifica.
        Args:
            region: tuple (x, y, w, h) o None per schermo intero
        Returns:
            numpy array RGB
        """
        try:
            screenshot = ImageGrab.grab(bbox=region)
            img = np.array(screenshot)
            # PIL restituisce RGB, OpenCV usa BGR internamente
            return cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        except Exception as e:
            print(f"[SCREENSHOT] Errore cattura schermo: {e}")
            return None

    def capture_region(self, x, y, w, h):
        """Cattura una regione specifica dello schermo."""
        return self.capture_screen(region=(x, y, w, h))

    # ============================================================
    # CARICAMENTO FILE
    # ============================================================

    def load_image(self, filepath):
        """
        Carica un'immagine da file.
        Returns:
            numpy array BGR o None se errore
        """
        if not os.path.exists(filepath):
            print(f"[SCREENSHOT] File non trovato: {filepath}")
            return None

        img = cv2.imread(filepath)
        if img is None:
            print(f"[SCREENSHOT] Impossibile leggere: {filepath}")
            return None

        self.current_image = img
        self.current_path = filepath
        print(f"[SCREENSHOT] Caricato: {filepath} ({img.shape[1]}x{img.shape[0]})")
        return img

    def load_latest_screenshot(self):
        """Carica l'ultimo screenshot nella cartella screenshots/."""
        files = [f for f in os.listdir(SCREENSHOTS_DIR)
                 if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
        if not files:
            print("[SCREENSHOT] Nessuno screenshot trovato")
            return None

        # Ordina per data modifica (più recente prima)
        files.sort(key=lambda f: os.path.getmtime(os.path.join(SCREENSHOTS_DIR, f)), reverse=True)
        latest = os.path.join(SCREENSHOTS_DIR, files[0])
        return self.load_image(latest)

    # ============================================================
    # SALVATAGGIO
    # ============================================================

    def save_screenshot(self, img, name="screenshot"):
        """
        Salva uno screenshot nella cartella screenshots/.
        Args:
            img: numpy array BGR
            name: prefisso nome file
        Returns:
            path del file salvato
        """
        if img is None:
            return None

        ts = time.strftime("%Y%m%d_%H%M%S")
        filename = f"{name}_{ts}.png"
        filepath = os.path.join(SCREENSHOTS_DIR, filename)
        cv2.imwrite(filepath, img)
        print(f"[SCREENSHOT] Salvato: {filepath}")
        return filepath

    # ============================================================
    # UTILITÀ
    # ============================================================

    def get_image_info(self, img):
        """Ritorna info sull'immagine: dimensioni, canali, dimensione file."""
        if img is None:
            return None
        h, w = img.shape[:2]
        channels = img.shape[2] if len(img.shape) > 2 else 1
        return {
            "width": w,
            "height": h,
            "channels": channels,
            "size_kb": img.nbytes / 1024,
        }

    def resize_for_display(self, img, max_width=800, max_height=600):
        """Ridimensiona l'immagine per la visualizzazione nella GUI."""
        if img is None:
            return None

        h, w = img.shape[:2]
        scale = min(max_width / w, max_height / h, 1.0)

        if scale < 1.0:
            new_w = int(w * scale)
            new_h = int(h * scale)
            return cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
        return img

    def annotate_image(self, img, points, labels=None):
        """
        Annota un'immagine con punti e etichette.
        Args:
            img: numpy array BGR
            points: dict {label: (x, y)} o lista di tuple (x, y, label)
            labels: lista di etichette (se points è lista di tuple)
        Returns:
            immagine annotata (copia, non modifica l'originale)
        """
        if img is None:
            return None

        annotated = img.copy()

        if isinstance(points, dict):
            for label, (x, y) in points.items():
                cv2.circle(annotated, (x, y), 8, (0, 255, 0), -1)
                cv2.putText(annotated, label, (x + 12, y + 5),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        elif isinstance(points, list):
            for i, pt in enumerate(points):
                x, y = pt[0], pt[1]
                label = pt[2] if len(pt) > 2 else str(i)
                cv2.circle(annotated, (x, y), 8, (0, 255, 0), -1)
                cv2.putText(annotated, label, (x + 12, y + 5),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

        return annotated

    def crop_region(self, img, x, y, w, h):
        """Ritaglia una regione dall'immagine."""
        if img is None:
            return None
        return img[y:y+h, x:x+w].copy()


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":
    manager = ScreenshotManager()

    # Test info
    test_img = np.zeros((742, 899, 3), dtype=np.uint8)
    info = manager.get_image_info(test_img)
    print(f"Test image info: {info}")

    # Test resize
    resized = manager.resize_for_display(test_img, max_width=400, max_height=300)
    print(f"Resized: {resized.shape[1]}x{resized.shape[0]}")

    # Test annotate
    annotated = manager.annotate_image(test_img, {"seat1": (100, 100), "seat2": (700, 100)})
    print(f"Annotated: {annotated.shape}")

    print("\n✓ Screenshot module OK")
