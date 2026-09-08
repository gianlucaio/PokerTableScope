#!/usr/bin/env python3
"""
PokerTableScope — GUI (tkinter)
Interfaccia grafica per calibrazione tavoli poker universale.
4 temi colori (come PokerBotAgent), tab Test, coordinate mouse, override manuali.
Multi-screenshot support, auto-resolution, carte hero, indicatore completamento.
"""

import os
import sys
import time
import threading
import json
import copy
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk

from config import (
    BASE_DIR, GUI_TITLE, SCREENSHOTS_DIR, PROFILES_DIR, OUTPUT_DIR
)
from screenshot import ScreenshotManager
from analyzer import VisionAnalyzer
from calibrator import Calibrator
from canonical import (
    validate_profile, validate_game_state, make_game_state,
    save_game_state, CANONICAL_VERSION, ACTION_BUTTONS,
    ACTION_BUTTON_LABELS, ACTION_BUTTONS_MIN, make_empty_profile
)


# ============================================================
# TEMA COLORI (specchio PokerBotAgent)
# ============================================================

THEMES = {
    "Scuro": {
        "BG": "#1e1e2e", "BG_LIGHT": "#2d2d3f", "BG_CARD": "#383850",
        "FG": "#cdd6f4", "FG_DIM": "#6c7086", "ACCENT": "#89b4fa",
        "GREEN": "#a6e3a1", "RED": "#f38ba8", "YELLOW": "#f9e2af",
        "CANVAS_BG": "#11111b",
    },
    "Classica": {
        "BG": "#f0f0f0", "BG_LIGHT": "#ffffff", "BG_CARD": "#e0e0e0",
        "FG": "#1a1a1a", "FG_DIM": "#666666", "ACCENT": "#2979ff",
        "GREEN": "#2e7d32", "RED": "#c62828", "YELLOW": "#f57f17",
        "CANVAS_BG": "#cccccc",
    },
    "Poker Verde": {
        "BG": "#0a3d0a", "BG_LIGHT": "#145214", "BG_CARD": "#1a6b1a",
        "FG": "#d4e8c0", "FG_DIM": "#7a9a6a", "ACCENT": "#76ff03",
        "GREEN": "#a5d6a7", "RED": "#ef5350", "YELLOW": "#fff176",
        "CANVAS_BG": "#062606",
    },
    "Blu": {
        "BG": "#0d1b2a", "BG_LIGHT": "#1b2838", "BG_CARD": "#243447",
        "FG": "#c0d6e4", "FG_DIM": "#5a7a8a", "ACCENT": "#4fc3f7",
        "GREEN": "#66bb6a", "RED": "#ef5350", "YELLOW": "#ffd54f",
        "CANVAS_BG": "#091520",
    },
}

# ============================================================
# OVERRIDE ROI FIELDS
# Definiscono i campi override con la rispettiva ROI (2-click).
# field = chiave in profile["override_rois"]. label = etichetta GUI.
# Per gli stack avversari il field usa "stacks:N" (N = numero seat).
# ============================================================

OVERRIDE_ROI_FIELDS = [
    {"field": "pot",               "label": "💰 Pot:",           "color": "YELLOW"},
    {"field": "timer",             "label": "⏱️ Timer:",         "color": "ORANGE"},
    {"field": "sb",                "label": "SB:",               "color": "BLUE"},
    {"field": "bb",                "label": "BB:",               "color": "BLUE"},
    {"field": "ante",              "label": "Ante:",             "color": "BLUE"},
    {"field": "players_remaining", "label": "Rimasti:",          "color": "RED"},
    {"field": "paid_positions",    "label": "Paganti:",          "color": "RED"},
    {"field": "rank_temporary",    "label": "Rank:",             "color": "PURPLE"},
    {"field": "hero_stack",        "label": "Stack Hero:",       "color": "GREEN"},
]

# Stack avversari per seat (1..9)
OVERRIDE_ROI_STACKS = [
    {"field": f"stacks:{i}", "label": f"Stack {i}:", "color": "GRAY"}
    for i in range(1, 10)
]

# Colori extra ROI (oltre a quelli del tema)
ROI_EXTRA_COLORS = {
    "ORANGE": "#ffa726",
    "PURPLE": "#b39ddb",
    "GRAY":   "#9e9e9e",
}


# ============================================================
# APP
# ============================================================

class App:
    """GUI principale del calibratore."""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title(GUI_TITLE)
        self.root.geometry("1860x1000")

        # Tema corrente
        self.current_theme = "Scuro"
        self._apply_theme()

        # Moduli
        self.screenshot_mgr = ScreenshotManager()
        self.analyzer = VisionAnalyzer()
        self.calibrator = Calibrator()
        self.current_image = None
        self.current_analysis = None
        self.photo_image = None
        self.canvas_image_id = None
        self.scale_factor = 1.0

        # Multi-screenshot
        self.loaded_images = []       # list of (path, cv2_image)
        self.current_image_index = -1 # index in loaded_images

        # Coordinate mouse
        self.coord_tracking = False
        self.coord_label = None

        # Click mode
        self.click_mode = None
        self.roi_points = []  # 2 punti per definire il rettangolo ROI

        # UNDO stack (snapshot del profilo)
        self.undo_stack = []
        self.undo_max = 50  # limite snapshot

        # Override ROI: entry campi e indicatori (✅/⬜)
        self._roi_entries = {}       # field → tk.Entry (valore override)
        self._roi_indicators = {}    # field → tk.Label (✅/⬜ indicatore ROI)
        self._roi_pending_field = None  # campo ROI in attesa dei 2 click

        # Test state
        self.test_results = {}

        self._build_ui()

    # ============================================================
    # TEMA
    # ============================================================

    def _apply_theme(self):
        """Applica il tema corrente."""
        t = THEMES[self.current_theme]
        self.BG = t["BG"]
        self.BG_LIGHT = t["BG_LIGHT"]
        self.BG_CARD = t["BG_CARD"]
        self.FG = t["FG"]
        self.FG_DIM = t["FG_DIM"]
        self.ACCENT = t["ACCENT"]
        self.GREEN = t["GREEN"]
        self.RED = t["RED"]
        self.YELLOW = t["YELLOW"]
        self.CANVAS_BG = t["CANVAS_BG"]
        try:
            self.root.configure(bg=self.BG)
        except Exception:
            pass

    def _switch_theme(self, theme_name):
        """Cambia tema e ricostruisce la GUI."""
        if theme_name not in THEMES:
            return
        self.current_theme = theme_name
        self._apply_theme()
        # Ricostruisci tutta la GUI
        for widget in self.root.winfo_children():
            widget.destroy()
        self._build_ui()
        # Riapplica immagine se c'era
        if self.current_image is not None:
            self._refresh_canvas()

        # Carica sessione precedente (se esiste)
        self.root.after(500, self._load_session)

    # ============================================================
    # BUILD UI
    # ============================================================

    def _build_ui(self):
        """Costruisce l'interfaccia grafica."""
        # --- Header ---
        header = tk.Frame(self.root, bg=self.BG_LIGHT, height=50)
        header.pack(fill=tk.X, padx=5, pady=(5, 0))
        header.pack_propagate(False)

        tk.Label(header, text="♠ PokerTableScope",
                 bg=self.BG_LIGHT, fg=self.ACCENT,
                 font=("Helvetica", 16, "bold")).pack(side=tk.LEFT, padx=10)

        tk.Label(header, text=f"v{CANONICAL_VERSION}",
                 bg=self.BG_LIGHT, fg=self.FG_DIM,
                 font=("Helvetica", 10)).pack(side=tk.LEFT)

        # Selettore tema
        tk.Label(header, text="Tema:", bg=self.BG_LIGHT, fg=self.FG,
                 font=("Helvetica", 10)).pack(side=tk.RIGHT, padx=(0, 5))
        theme_var = tk.StringVar(value=self.current_theme)
        theme_menu = ttk.OptionMenu(header, theme_var, self.current_theme,
                                     *THEMES.keys(),
                                     command=self._switch_theme)
        theme_menu.pack(side=tk.RIGHT, padx=5)

        # --- Coordinate mouse (barra in basso) ---
        self.coord_bar = tk.Frame(self.root, bg=self.BG_LIGHT, height=30)
        self.coord_bar.pack(fill=tk.X, padx=5, pady=(0, 5))
        self.coord_bar.pack_propagate(False)

        self.coord_label = tk.Label(self.coord_bar, text="Mouse: —",
                                     bg=self.BG_LIGHT, fg=self.FG_DIM,
                                     font=("Courier", 10))
        self.coord_label.pack(side=tk.LEFT, padx=10)

        self.btn_coord_toggle = tk.Button(
            self.coord_bar, text="📍 Attiva Coordinate",
            command=self._toggle_coord_tracking,
            bg=self.BG_CARD, fg=self.FG, font=("Helvetica", 9),
            relief=tk.FLAT, padx=10)
        self.btn_coord_toggle.pack(side=tk.RIGHT, padx=5, pady=3)

        # --- Corpo principale ---
        body = tk.Frame(self.root, bg=self.BG)
        body.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Pannello sinistro: immagine
        left = tk.Frame(body, bg=self.BG_CARD)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(left, bg=self.CANVAS_BG, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.canvas.bind("<Button-1>", self._on_canvas_click)
        self.canvas.bind("<Motion>", self._on_canvas_motion)

        # --- KEYBOARD SHORTCUTS ---
        # Seat: Shift+1..9 (C1-C9) → click seat direttamente
        for i in range(1, 10):
            self.root.bind(f"<Shift-KeyPress-{i}>", lambda e, n=i: self._kb_click_seat(n))
        # Pulsanti azione: F=Fold, C=Check, K=Call, R=Raise, A=All-in, B=Bet
        self.root.bind("<KeyPress-f>", lambda e: self._kb_click_button("fold"))
        self.root.bind("<KeyPress-c>", lambda e: self._kb_click_button("check"))
        self.root.bind("<KeyPress-k>", lambda e: self._kb_click_button("call"))
        self.root.bind("<KeyPress-r>", lambda e: self._kb_click_button("raise"))
        self.root.bind("<KeyPress-a>", lambda e: self._kb_click_button("allin"))
        self.root.bind("<KeyPress-b>", lambda e: self._kb_click_button("bet"))
        # D = Definisci ROI tavolo
        self.root.bind("<KeyPress-d>", lambda e: self._kb_define_roi())
        # Esc = Annulla modalit click corrente
        self.root.bind("<Escape>", lambda e: self._kb_cancel_click())

        self.img_status = tk.Label(left, text="Nessuna immagine caricata",
                                    bg=self.BG_CARD, fg=self.FG_DIM,
                                    font=("Helvetica", 9))
        self.img_status.pack(fill=tk.X, padx=5, pady=(0, 5))

        # Pannello destro: tab
        right = tk.Frame(body, bg=self.BG, width=760)
        right.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))
        right.pack_propagate(False)

        self._build_tabs(right)

    def _build_tabs(self, parent):
        """Costruisce i 5 tab."""
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TNotebook", background=self.BG, borderwidth=0)
        style.configure("TNotebook.Tab", background=self.BG_LIGHT, foreground=self.FG,
                        padding=[8, 5], font=("Helvetica", 9))
        style.map("TNotebook.Tab",
                  background=[("selected", self.BG_CARD)],
                  foreground=[("selected", self.ACCENT)])

        self.notebook = ttk.Notebook(parent)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Tab 1: Screenshot
        tab1 = tk.Frame(self.notebook, bg=self.BG)
        self.notebook.add(tab1, text=" 📷 Screenshot ")
        self._build_tab_screenshot(tab1)

        # Tab 2: Vision
        tab2 = tk.Frame(self.notebook, bg=self.BG)
        self.notebook.add(tab2, text=" 🔍 Vision ")
        self._build_tab_vision(tab2)

        # Tab 3: Calibra
        tab3 = tk.Frame(self.notebook, bg=self.BG)
        self.notebook.add(tab3, text=" 🎯 Calibra ")
        self._build_tab_calibrate(tab3)

        # Tab 4: Test
        tab4 = tk.Frame(self.notebook, bg=self.BG)
        self.notebook.add(tab4, text=" ✅ Test ")
        self._build_tab_test(tab4)

        # Tab 5: Profili
        tab5 = tk.Frame(self.notebook, bg=self.BG)
        self.notebook.add(tab5, text=" 💾 Profili ")
        self._build_tab_profiles(tab5)

    # ============================================================
    # TAB 1: SCREENSHOT (con supporto multi-screenshot)
    # ============================================================

    def _build_tab_screenshot(self, parent):
        frame = tk.Frame(parent, bg=self.BG)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        tk.Button(frame, text="📂 Carica Screenshot",
                  command=self._load_screenshot,
                  bg=self.ACCENT, fg="#1e1e2e", font=("Helvetica", 11, "bold"),
                  relief=tk.FLAT, padx=15, pady=8).pack(fill=tk.X, pady=3)

        tk.Button(frame, text="📂📂 Carica più Screenshot",
                  command=self._load_multiple_screenshots,
                  bg=self.YELLOW, fg="#1e1e2e", font=("Helvetica", 10, "bold"),
                  relief=tk.FLAT, padx=15, pady=6).pack(fill=tk.X, pady=3)

        tk.Button(frame, text="📷 Carica Ultimo",
                  command=self._load_latest,
                  bg=self.BG_LIGHT, fg=self.FG, font=("Helvetica", 10),
                  relief=tk.FLAT, padx=15, pady=6).pack(fill=tk.X, pady=2)

        tk.Button(frame, text="📸 Cattura Schermo",
                  command=self._capture_screen,
                  bg=self.BG_LIGHT, fg=self.FG, font=("Helvetica", 10),
                  relief=tk.FLAT, padx=15, pady=6).pack(fill=tk.X, pady=2)

        # --- Navigazione multi-screenshot ---
        nav_row = tk.Frame(frame, bg=self.BG)
        nav_row.pack(fill=tk.X, pady=5)
        self.btn_prev = tk.Button(nav_row, text="◀ Precedente",
                                  command=self._prev_image,
                                  bg=self.BG_LIGHT, fg=self.FG,
                                  font=("Helvetica", 9), relief=tk.FLAT, padx=8)
        self.btn_prev.pack(side=tk.LEFT, padx=2)
        self.btn_prev.config(state=tk.DISABLED)
        self.img_nav_label = tk.Label(nav_row, text="", bg=self.BG, fg=self.FG,
                                       font=("Helvetica", 10, "bold"))
        self.img_nav_label.pack(side=tk.LEFT, padx=10, expand=True)
        self.btn_next = tk.Button(nav_row, text="Successivo ▶",
                                  command=self._next_image,
                                  bg=self.BG_LIGHT, fg=self.FG,
                                  font=("Helvetica", 9), relief=tk.FLAT, padx=8)
        self.btn_next.pack(side=tk.RIGHT, padx=2)
        self.btn_next.config(state=tk.DISABLED)

        # Info dimensioni
        self.shot_info = tk.Label(frame, text="", bg=self.BG, fg=self.FG_DIM,
                                   font=("Helvetica", 9), justify=tk.LEFT)
        self.shot_info.pack(fill=tk.X, pady=5)

        # Info resize
        tk.Label(frame, text="ℹ Lo screenshot si adatta a qualsiasi dimensione.\n"
                             "Il programma scala automaticamente le coordinate.\n"
                             "Carica più screenshot per completare la calibrazione.",
                 bg=self.BG, fg=self.FG_DIM, font=("Helvetica", 8),
                 justify=tk.LEFT).pack(fill=tk.X, pady=5)

    def _load_screenshot(self):
        path = filedialog.askopenfilename(
            filetypes=[("Image", "*.png *.jpg *.jpeg *.bmp")],
            initialdir=SCREENSHOTS_DIR
        )
        if path:
            self._add_image(path)

    def _load_multiple_screenshots(self):
        paths = filedialog.askopenfilenames(
            filetypes=[("Image", "*.png *.jpg *.jpeg *.bmp")],
            initialdir=SCREENSHOTS_DIR
        )
        if paths:
            for p in paths:
                self._add_image(p)
            # Mostra il primo
            if self.loaded_images:
                self._show_image_index(0)

    def _add_image(self, path):
        """Aggiunge un'immagine alla lista multi-screenshot."""
        import cv2
        img = cv2.imread(path)
        if img is None:
            messagebox.showerror("Errore", f"Impossibile leggere: {path}")
            return
        self.loaded_images.append((path, img))
        idx = len(self.loaded_images) - 1
        self._show_image_index(idx)
        # Auto-imposta risoluzione dal primo screenshot caricato
        if len(self.loaded_images) == 1:
            h, w = img.shape[:2]
            try:
                self.entry_res_w.delete(0, tk.END)
                self.entry_res_w.insert(0, str(w))
                self.entry_res_h.delete(0, tk.END)
                self.entry_res_h.insert(0, str(h))
            except AttributeError:
                pass  # la GUI non è ancora pronta

    def _show_image_index(self, idx):
        """Mostra lo screenshot alla posizione index nella lista."""
        if idx < 0 or idx >= len(self.loaded_images):
            return
        self.current_image_index = idx
        path, img = self.loaded_images[idx]
        self.current_image = img
        info = self.screenshot_mgr.get_image_info(img)
        self.shot_info.config(
            text=f"File: {os.path.basename(path)}\n"
                 f"Dimensioni: {info['width']}x{info['height']} px\n"
                 f"Dimensione: {info['size_kb']:.1f} KB\n"
                 f"Fattore scala: {self.scale_factor:.2f}x"
        )
        self._refresh_canvas()
        self._update_nav()

    def _update_nav(self):
        """Aggiorna i pulsanti navigazione e contatore."""
        total = len(self.loaded_images)
        if total == 0:
            self.img_nav_label.config(text="")
            self.btn_prev.config(state=tk.DISABLED)
            self.btn_next.config(state=tk.DISABLED)
            return
        self.img_nav_label.config(
            text=f"Immagine {self.current_image_index + 1}/{total}"
        )
        self.btn_prev.config(state=tk.NORMAL if self.current_image_index > 0 else tk.DISABLED)
        self.btn_next.config(state=tk.NORMAL if self.current_image_index < total - 1 else tk.DISABLED)

    def _prev_image(self):
        if self.current_image_index > 0:
            self._show_image_index(self.current_image_index - 1)

    def _next_image(self):
        if self.current_image_index < len(self.loaded_images) - 1:
            self._show_image_index(self.current_image_index + 1)

    def _load_latest(self):
        img = self.screenshot_mgr.load_latest_screenshot()
        if img is not None:
            self.current_image = img
            self._refresh_canvas()
        else:
            messagebox.showinfo("Info", "Nessuno screenshot nella cartella screenshots/")

    def _capture_screen(self):
        img = self.screenshot_mgr.capture_screen()
        if img is not None:
            self.current_image = img
            path = self.screenshot_mgr.save_screenshot(img, "capture")
            self._add_image(path)
        else:
            messagebox.showerror("Errore", "Impossibile catturare lo schermo")

    def _show_image(self, path):
        img = self.screenshot_mgr.load_image(path)
        if img is not None:
            self.current_image = img
            info = self.screenshot_mgr.get_image_info(img)
            self.shot_info.config(
                text=f"File: {os.path.basename(path)}\n"
                     f"Dimensioni originali: {info['width']}x{info['height']} px\n"
                     f"Dimensione: {info['size_kb']:.1f} KB\n"
                     f"Fattore scala: {self.scale_factor:.2f}x"
            )
            self._refresh_canvas()

    def _refresh_canvas(self):
        if self.current_image is None:
            return
        self.canvas.delete("all")
        canvas_w = self.canvas.winfo_width()
        canvas_h = self.canvas.winfo_height()
        if canvas_w < 10 or canvas_h < 10:
            canvas_w, canvas_h = 800, 600

        import cv2
        h, w = self.current_image.shape[:2]
        self.scale_factor = min(canvas_w / w, canvas_h / h, 1.0)
        new_w = int(w * self.scale_factor)
        new_h = int(h * self.scale_factor)

        img_rgb = cv2.cvtColor(self.current_image, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(img_rgb)
        pil_img = pil_img.resize((new_w, new_h), Image.LANCZOS)
        self.photo_image = ImageTk.PhotoImage(pil_img)
        self.canvas_image_id = self.canvas.create_image(0, 0, anchor=tk.NW, image=self.photo_image)

    # ============================================================
    # TAB 2: VISION
    # ============================================================

    def _build_tab_vision(self, parent):
        frame = tk.Frame(parent, bg=self.BG)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        tk.Button(frame, text="🔍 Analizza con Vision",
                  command=self._run_analysis,
                  bg=self.ACCENT, fg="#1e1e2e", font=("Helvetica", 11, "bold"),
                  relief=tk.FLAT, padx=15, pady=8).pack(fill=tk.X, pady=5)

        self.vision_status = tk.Label(frame, text="Pronto per analisi",
                                       bg=self.BG, fg=self.FG_DIM,
                                       font=("Helvetica", 9))
        self.vision_status.pack(fill=tk.X, pady=3)

        tk.Label(frame, text="Risultato Vision:", bg=self.BG, fg=self.FG,
                 font=("Helvetica", 10, "bold"), anchor=tk.W).pack(fill=tk.X)
        self.vision_result = tk.Text(frame, bg=self.BG_LIGHT, fg=self.FG,
                                     font=("Courier", 9), height=12, wrap=tk.WORD)
        self.vision_result.pack(fill=tk.BOTH, expand=True, pady=5)

        tk.Button(frame, text="✅ Importa nel Profilo",
                  command=self._import_analysis,
                  bg=self.GREEN, fg="#1e1e2e", font=("Helvetica", 10, "bold"),
                  relief=tk.FLAT, padx=15, pady=6).pack(fill=tk.X, pady=5)

    def _run_analysis(self):
        if self.current_image is None:
            messagebox.showwarning("Attenzione", "Carica prima uno screenshot")
            return
        self.vision_status.config(text="⏳ Analisi in corso...", fg=self.YELLOW)
        self.root.update()

        def _do():
            import tempfile, cv2
            tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
            cv2.imwrite(tmp.name, self.current_image)
            result = self.analyzer.analyze_screenshot(tmp.name)
            os.unlink(tmp.name)
            self.root.after(0, self._on_analysis_done, result)

        threading.Thread(target=_do, daemon=True).start()

    def _on_analysis_done(self, result):
        self.current_analysis = result
        if result:
            self.vision_result.delete("1.0", tk.END)
            self.vision_result.insert(tk.END, json.dumps(result, indent=2, ensure_ascii=False))
            self.vision_status.config(text="✅ Analisi completata", fg=self.GREEN)
        else:
            self.vision_result.delete("1.0", tk.END)
            self.vision_result.insert(tk.END, "Errore. Verifica LM Studio attivo.")
            self.vision_status.config(text="❌ Analisi fallita", fg=self.RED)

    def _import_analysis(self):
        if not self.current_analysis:
            messagebox.showwarning("Attenzione", "Nessun risultato da importare")
            return
        if self.calibrator.current_profile is None:
            self.calibrator.new_profile()
        self._snapshot()
        self.calibrator.import_from_analyzer(self.current_analysis)
        self._update_cal_status()
        messagebox.showinfo("Importato", "Dati Vision importati nel profilo")

    # ============================================================
    # TAB 3: CALIBRA (con override manuali completi)
    # ============================================================

    def _build_tab_calibrate(self, parent):
        canvas = tk.Canvas(parent, bg=self.BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scroll_frame = tk.Frame(canvas, bg=self.BG)

        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        sf = scroll_frame

        # --- UNDO (annulla ultima modifica) ---
        undo_row = tk.Frame(sf, bg=self.BG); undo_row.pack(fill=tk.X, pady=(0, 3))
        tk.Button(undo_row, text="↩ UNDO (annulla ultima modifica)",
                  command=self._undo,
                  bg=self.YELLOW, fg="#1e1e2e", font=("Helvetica", 10, "bold"),
                  relief=tk.FLAT, padx=10, pady=5).pack(side=tk.LEFT, padx=2)
        self.undo_count_label = tk.Label(undo_row, text="0", bg=self.BG,
                                          fg=self.FG_DIM, font=("Helvetica", 9))
        self.undo_count_label.pack(side=tk.LEFT, padx=5)

        # --- NOME PRESET ---
        self._section_label(sf, "🏷️ Nome Preset")
        row = tk.Frame(sf, bg=self.BG); row.pack(fill=tk.X, pady=2)
        tk.Label(row, text="Nome:", bg=self.BG, fg=self.FG, width=10, anchor=tk.W).pack(side=tk.LEFT)
        self.entry_preset = tk.Entry(row, bg=self.BG_LIGHT, fg=self.FG, font=("Helvetica", 10), width=20)
        self.entry_preset.insert(0, "")
        self.entry_preset.pack(side=tk.LEFT)
        tk.Label(row, text="es. ipoker_9max_1936x1056", bg=self.BG, fg=self.FG_DIM,
                 font=("Helvetica", 8)).pack(side=tk.LEFT, padx=5)

        # --- CLIENT ---
        self._section_label(sf, "🖥️ Client")
        row = tk.Frame(sf, bg=self.BG); row.pack(fill=tk.X, pady=2)
        tk.Label(row, text="Nome:", bg=self.BG, fg=self.FG, width=10, anchor=tk.W).pack(side=tk.LEFT)
        self.entry_client = tk.Entry(row, bg=self.BG_LIGHT, fg=self.FG, font=("Helvetica", 10), width=15)
        self.entry_client.pack(side=tk.LEFT)

        row2 = tk.Frame(sf, bg=self.BG); row2.pack(fill=tk.X, pady=2)
        tk.Label(row2, text="Piattaforma:", bg=self.BG, fg=self.FG, width=10, anchor=tk.W).pack(side=tk.LEFT)
        self.platform_var = tk.StringVar(value="web")
        self.entry_platform = tk.OptionMenu(row2, self.platform_var, "web", "client")
        self.entry_platform.config(bg=self.BG_LIGHT, fg=self.FG, font=("Helvetica", 10),
                                   highlightthickness=0, bd=1)
        self.entry_platform.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # --- RISOLUZIONE (auto-dallo screenshot) ---
        self._section_label(sf, "📐 Risoluzione")
        row = tk.Frame(sf, bg=self.BG); row.pack(fill=tk.X, pady=2)
        tk.Label(row, text="Larghezza:", bg=self.BG, fg=self.FG, width=10, anchor=tk.W).pack(side=tk.LEFT)
        self.entry_res_w = tk.Entry(row, bg=self.BG_LIGHT, fg=self.FG, font=("Helvetica", 10), width=8)
        self.entry_res_w.insert(0, "0")
        self.entry_res_w.pack(side=tk.LEFT, padx=5)
        tk.Label(row, text="Altezza:", bg=self.BG, fg=self.FG, anchor=tk.W).pack(side=tk.LEFT)
        self.entry_res_h = tk.Entry(row, bg=self.BG_LIGHT, fg=self.FG, font=("Helvetica", 10), width=8)
        self.entry_res_h.insert(0, "0")
        self.entry_res_h.pack(side=tk.LEFT, padx=5)
        tk.Label(row, text="(auto dal primo screenshot)", bg=self.BG, fg=self.FG_DIM,
                 font=("Helvetica", 8)).pack(side=tk.LEFT, padx=5)

        # --- HERO ---
        self._section_label(sf, "🃏 Hero")
        row = tk.Frame(sf, bg=self.BG); row.pack(fill=tk.X, pady=2)
        tk.Label(row, text="Nome:", bg=self.BG, fg=self.FG, width=10, anchor=tk.W).pack(side=tk.LEFT)
        self.entry_hero = tk.Entry(row, bg=self.BG_LIGHT, fg=self.FG, font=("Helvetica", 10))
        self.entry_hero.insert(0, "hero")
        self.entry_hero.pack(side=tk.LEFT, fill=tk.X, expand=True)

        row = tk.Frame(sf, bg=self.BG); row.pack(fill=tk.X, pady=2)
        tk.Label(row, text="Seat:", bg=self.BG, fg=self.FG, width=10, anchor=tk.W).pack(side=tk.LEFT)
        self.spin_hero_seat = tk.Spinbox(row, from_=1, to=10, width=5,
                                          bg=self.BG_LIGHT, fg=self.FG)
        self.spin_hero_seat.pack(side=tk.LEFT, padx=5)
        self.hero_dynamic = tk.BooleanVar(value=True)
        tk.Checkbutton(row, text="Dinamico", variable=self.hero_dynamic,
                       bg=self.BG, fg=self.FG, selectcolor=self.BG_LIGHT).pack(side=tk.LEFT, padx=10)

        # --- CARTE HERO (override manuale) ---
        self._section_label(sf, "🂡 Carte Hero (override manuale)")
        row = tk.Frame(sf, bg=self.BG); row.pack(fill=tk.X, pady=2)
        tk.Label(row, text="Carte:", bg=self.BG, fg=self.FG, width=10, anchor=tk.W).pack(side=tk.LEFT)
        self.entry_hero_cards = tk.Entry(row, bg=self.BG_LIGHT, fg=self.FG, font=("Helvetica", 10), width=8)
        self.entry_hero_cards.insert(0, "")
        self.entry_hero_cards.pack(side=tk.LEFT)
        tk.Label(row, text="es. As Kh (opposite: 4c 4h)", bg=self.BG, fg=self.FG_DIM,
                 font=("Helvetica", 8)).pack(side=tk.LEFT, padx=5)

        # --- SEAT (click-to-place) ---
        self._section_label(sf, "📍 Seat — Click pulsante poi click immagine (1=ore12, senso orario)")
        seat_row = tk.Frame(sf, bg=self.BG); seat_row.pack(fill=tk.X, pady=3)
        for i in range(1, 10):
            tk.Button(seat_row, text=str(i), width=3,
                      command=lambda n=i: self._set_click_mode(f"seat_{n}"),
                      bg=self.BG_LIGHT, fg=self.FG, font=("Helvetica", 9)).pack(side=tk.LEFT, padx=2)

        # --- ROI TAVOLO (disegna rettangolo) ---
        self._section_label(sf, "🖼️ ROI Tavolo — 2 click (angolo alto-sx + basso-dx)")
        roi_row = tk.Frame(sf, bg=self.BG); roi_row.pack(fill=tk.X, pady=3)
        tk.Button(roi_row, text="📐 Definisci ROI",
                  command=lambda: self._set_click_mode("roi"),
                  bg=self.ACCENT, fg="#1e1e2e", font=("Helvetica", 10, "bold"),
                  relief=tk.FLAT, padx=10, pady=5).pack(side=tk.LEFT, padx=2)
        self.roi_status = tk.Label(roi_row, text="Non definito", bg=self.BG,
                                    fg=self.FG_DIM, font=("Helvetica", 9))
        self.roi_status.pack(side=tk.LEFT, padx=10)

        # --- AZIONI (click-to-place) ---
        self._section_label(sf, "🎮 Pulsanti Azione — Click pulsante poi click immagine")
        btn_row = tk.Frame(sf, bg=self.BG); btn_row.pack(fill=tk.X, pady=3)
        self._btn_size_indicators = {}  # action → Label ✅/⬜
        for action in ACTION_BUTTONS:
            btn_frame = tk.Frame(btn_row, bg=self.BG)
            btn_frame.pack(side=tk.LEFT, padx=(0, 6))
            tk.Button(btn_frame, text=ACTION_BUTTON_LABELS[action], width=7,
                      command=lambda a=action: self._set_click_mode(f"btn_{a}"),
                      bg=self.BG_LIGHT, fg=self.FG, font=("Helvetica", 9)).pack(side=tk.LEFT)
            # Pulsante 📏 ROI per dimensioni area cliccabile
            tk.Button(btn_frame, text="📏", width=2,
                      command=lambda a=action: self._set_click_mode(f"btn_size_{a}"),
                      bg="#404040", fg="#e0e0e0", font=("Helvetica", 8),
                      relief=tk.FLAT).pack(side=tk.LEFT, padx=(1, 0))
            # Indicatore ✅/⬜ dimensioni
            ind = tk.Label(btn_frame, text="⬜", bg=self.BG, fg=self.FG_DIM, font=("Helvetica", 8))
            ind.pack(side=tk.LEFT)
            self._btn_size_indicators[action] = ind
        tk.Label(btn_row, text="(BET = BB non rilanciato,\nstessa pos di RAISE)",
                 bg=self.BG, fg=self.FG_DIM, font=("Helvetica", 7)).pack(side=tk.LEFT, padx=5)

        # --- OVERRIDE ROI (pot/timer/blinds/ante/torneo/stack) ---
        # Ogni campo ha un entry per l'override manuale + un pulsante ROI
        # che definisce il rettangolo dove il valore è visibile.
        self._section_label(sf, "🎯 Override con ROI (definisci area valore)")

        # BOARD (override manuale, senza ROI — carta comune)
        self._section_label(sf, "🃏 Board (override manuale)")
        brow = tk.Frame(sf, bg=self.BG); brow.pack(fill=tk.X, pady=2)
        tk.Label(brow, text="Carte:", bg=self.BG, fg=self.FG,
                 width=14, anchor=tk.W).pack(side=tk.LEFT)
        self.entry_board = tk.Entry(brow, bg=self.BG_LIGHT, fg=self.FG, font=("Helvetica", 9), width=12)
        self.entry_board.insert(0, "")
        self.entry_board.pack(side=tk.LEFT, padx=(0, 4))
        tk.Label(brow, text="es. 7c 8d 2h", bg=self.BG, fg=self.FG_DIM,
                 font=("Helvetica", 8)).pack(side=tk.LEFT)

        # POT e TIMER
        self._section_label(sf, "💰 Valori")
        self._add_roi_row(sf, "pot")
        self._add_roi_row(sf, "timer")

        # BLINDS / ANTE
        self._section_label(sf, "🎯 Blinds / Ante")
        for field in ("sb", "bb", "ante"):
            self._add_roi_row(sf, field)

        # TORNEO: rimasti (solo iscrizioni chiuse), paganti, rank
        self._section_label(sf, "🏆 Torneo")
        self._add_roi_row(sf, "players_remaining")
        self._add_roi_row(sf, "paid_positions")
        self._add_roi_row(sf, "rank_temporary")

        # STACK
        self._section_label(sf, "🥞 Stack (hero + avversari)")
        self._add_roi_row(sf, "hero_stack")
        for stack in OVERRIDE_ROI_STACKS:
            self._add_roi_row(sf, stack["field"])

        # --- INDICATORE COMPLETAMENTO ---
        self.completion_frame = tk.Frame(sf, bg=self.BG_CARD, highlightbackground=self.ACCENT,
                                          highlightthickness=1)
        self.completion_frame.pack(fill=tk.X, pady=10, padx=5)
        self.completion_bar = tk.Label(self.completion_frame, text="Completamento: 0%",
                                        bg=self.BG_CARD, fg=self.FG_DIM,
                                        font=("Helvetica", 10, "bold"))
        self.completion_bar.pack(pady=(5, 2))
        self.completion_detail = tk.Label(self.completion_frame, text="",
                                           bg=self.BG_CARD, fg=self.FG_DIM,
                                           font=("Helvetica", 8), justify=tk.LEFT, wraplength=550)
        self.completion_detail.pack(pady=(0, 5), padx=10)
        self._update_completion()

        # --- STATUS ---
        self.cal_status = tk.Label(sf, text="", bg=self.BG, fg=self.FG_DIM,
                                   font=("Helvetica", 9), justify=tk.LEFT, anchor=tk.W)
        self.cal_status.pack(fill=tk.X, pady=10)

        # --- APPlica tutti gli override manuali ---
        tk.Button(sf, text="📝 Applica Override Manuali al Profilo",
                  command=self._apply_manual_overrides,
                  bg=self.YELLOW, fg="#1e1e2e", font=("Helvetica", 10, "bold"),
                  relief=tk.FLAT, padx=15, pady=6).pack(fill=tk.X, pady=5)

        # --- TEMPLATE OVERRIDE (salva/carica blocchi) ---
        tmpl_row = tk.Frame(sf, bg=self.BG)
        tmpl_row.pack(fill=tk.X, pady=2)
        tk.Button(tmpl_row, text="💾 Salva Template",
                  command=self._save_override_template,
                  bg=self.ACCENT, fg="white", font=("Helvetica", 9),
                  relief=tk.FLAT, padx=8, pady=3).pack(side=tk.LEFT, padx=(0, 5))
        tk.Button(tmpl_row, text="📂 Carica Template",
                  command=self._load_override_template,
                  bg=self.ACCENT, fg="white", font=("Helvetica", 9),
                  relief=tk.FLAT, padx=8, pady=3).pack(side=tk.LEFT)

    def _section_label(self, parent, text):
        tk.Label(parent, text=text, bg=self.BG, fg=self.ACCENT,
                 font=("Helvetica", 10, "bold"), anchor=tk.W).pack(fill=tk.X, pady=(8, 2))

    def _roi_hex(self, color_name):
        """Converte nome colore ROI in esadecimale (tema o extra)."""
        if hasattr(self, color_name):
            return getattr(self, color_name)
        return ROI_EXTRA_COLORS.get(color_name, "#9e9e9e")

    def _roi_field_label(self, field):
        """Restituisce l'etichetta GUI data la chiave override field."""
        for f in OVERRIDE_ROI_FIELDS:
            if f["field"] == field:
                return f["label"], f["color"]
        for f in OVERRIDE_ROI_STACKS:
            if f["field"] == field:
                return f["label"], f["color"]
        return field, "GRAY"

    def _add_roi_row(self, parent, field):
        """Aggiunge una riga: label + entry(value) + pulsante ROI + indicatore."""
        label_text, color = self._roi_field_label(field)
        row = tk.Frame(parent, bg=self.BG)
        row.pack(fill=tk.X, pady=2)

        tk.Label(row, text=label_text, bg=self.BG, fg=self.FG,
                 width=14, anchor=tk.W).pack(side=tk.LEFT)

        # Entry per il valore (override manuale)
        entry = tk.Entry(row, bg=self.BG_LIGHT, fg=self.FG, font=("Helvetica", 9), width=7)
        entry.pack(side=tk.LEFT, padx=(0, 4))
        self._roi_entries[field] = entry

        # Pulsante ROI
        tk.Button(row, text="📍 ROI", command=lambda f=field: self._set_click_mode(f"roi_{f}"),
                  bg=self._roi_hex(color), fg="#1e1e2e", font=("Helvetica", 8, "bold"),
                  relief=tk.FLAT, padx=4).pack(side=tk.LEFT)

        # Indicatore ✅/⬜
        ind = tk.Label(row, text="⬜", bg=self.BG, fg=self.FG_DIM, font=("Helvetica", 10))
        ind.pack(side=tk.LEFT, padx=3)
        self._roi_indicators[field] = ind

    def _set_click_mode(self, mode):
        self.click_mode = mode
        self.roi_points = []  # reset punti ROI
        self.img_status.config(text=f"Modalità: {mode} — Click sull'immagine per posizionare")

    def _snapshot(self):
        """Salva lo stato attuale del profilo prima di una modifica."""
        if self.calibrator.current_profile is None:
            return
        snap = copy.deepcopy(self.calibrator.current_profile)
        self.undo_stack.append(snap)
        if len(self.undo_stack) > self.undo_max:
            self.undo_stack.pop(0)
        try:
            self.undo_count_label.config(text=str(len(self.undo_stack)))
        except AttributeError:
            pass

    def _undo(self):
        """Ripristina l'ultimo snapshot (annulla l'ultima modifica)."""
        if not self.undo_stack:
            messagebox.showinfo("UNDO", "Niente da annullare")
            return
        snap = self.undo_stack.pop()
        self.calibrator.current_profile = snap
        # Pulisci tutti i marker (punti colorati) disegnati sul canvas
        self.canvas.delete("marker")
        self._update_cal_status()
        self.img_status.config(text=f"↩ UNDO: ripristinato stato precedente ({len(self.undo_stack)} rimasti)")
        try:
            self.undo_count_label.config(text=str(len(self.undo_stack)))
        except AttributeError:
            pass
        # Ridisegna ROI se presente
        roi = snap.get("table_roi", {})
        if roi.get("w") and roi.get("h"):
            self.roi_status.config(
                text=f"ROI: x={roi['x']}, y={roi['y']}, w={roi['w']}, h={roi['h']}",
                fg=self.GREEN
            )
        else:
            self.roi_status.config(text="Non definito", fg=self.FG_DIM)
        self._update_completion()
        # Aggiorna indicatori ROI e dimensioni pulsanti dopo UNDO
        rois = snap.get("override_rois", {})
        for field in self._roi_indicators:
            has = False
            if ":" in field:
                parent, key = field.split(":", 1)
                sub = rois.get(parent, {})
                has = bool(sub.get(key, {}).get("w")) if isinstance(sub, dict) else False
            else:
                has = bool(rois.get(field, {}).get("w")) if isinstance(rois, dict) else False
            self._roi_indicators[field].config(text="✅" if has else "⬜",
                                               fg=self.GREEN if has else self.FG_DIM)
        act = snap.get("act_targets", {})
        for action in self._btn_size_indicators:
            has_size = bool(act.get(action, {}).get("w")) and bool(act.get(action, {}).get("h"))
            self._btn_size_indicators[action].config(text="✅" if has_size else "⬜",
                                                     fg=self.GREEN if has_size else self.FG_DIM)

    def _finalize_roi(self):
        """Calcola e salva il rettangolo ROI dai 2 punti selezionati."""
        if len(self.roi_points) != 2:
            return
        (x1, y1), (x2, y2) = self.roi_points
        # Normalizza (gestisce click fuori ordine)
        x = min(x1, x2)
        y = min(y1, y2)
        w = abs(x2 - x1)
        h = abs(y2 - y1)

        self._snapshot()
        self.calibrator.set_table_roi(x, y, w, h)
        self.roi_status.config(
            text=f"ROI: x={x}, y={y}, w={w}, h={h}",
            fg=self.GREEN
        )

        # Disegna rettangolo sul canvas (scala)
        scale = self.scale_factor
        sx1, sy1 = int(x * scale), int(y * scale)
        sx2, sy2 = int((x + w) * scale), int((y + h) * scale)
        self.canvas.create_rectangle(sx1, sy1, sx2, sy2,
                                     outline=self.GREEN, width=2, tags="marker")
        self._autosave_session()

        self._update_cal_status()
        self._update_completion()
        self.img_status.config(
            text=f"ROI definito: {w}x{h} px a ({x},{y})"
        )
        self.click_mode = None  # esci dalla modalità

    def _finalize_override_roi(self, field):
        """Calcola e salva il rettangolo ROI per un campo override dai 2 punti."""
        if len(self.roi_points) != 2:
            return
        (x1, y1), (x2, y2) = self.roi_points
        x = min(x1, x2)
        y = min(y1, y2)
        w = abs(x2 - x1)
        h = abs(y2 - y1)

        self._snapshot()
        self.calibrator.set_override_roi(field, x, y, w, h)

        # Aggiorna indicatore: ⬜ → ✅
        if field in self._roi_indicators:
            self._roi_indicators[field].config(text="✅", fg=self.GREEN)

        # Disegna rettangolo colorato sul canvas
        _, color = self._roi_field_label(field)
        color_hex = self._roi_hex(color)
        scale = self.scale_factor
        sx1, sy1 = int(x * scale), int(y * scale)
        sx2, sy2 = int((x + w) * scale), int((y + h) * scale)
        self.canvas.create_rectangle(sx1, sy1, sx2, sy2,
                                     outline=color_hex, width=2, tags="marker")

        self._update_cal_status()
        self._update_completion()
        self.img_status.config(text=f"ROI {field}: {w}x{h} px a ({x},{y})")
        self.click_mode = None  # esci dalla modalità
        self._autosave_session()

    def _finalize_button_size(self, action):
        """Calcola e salva le dimensioni (w, h) dell'area cliccabile di un pulsante dai 2 punti."""
        if len(self.roi_points) != 2:
            return
        (x1, y1), (x2, y2) = self.roi_points
        w = abs(x2 - x1)
        h = abs(y2 - y1)

        if w < 2 or h < 2:
            self.img_status.config(text=f"📏 {ACTION_BUTTON_LABELS[action]}: dimensione troppo piccola ({w}x{h}), riprova")
            self.click_mode = None
            return

        self._snapshot()
        self.calibrator.set_button_size(action, w, h)

        # Aggiorna indicatore: solo se w>0 e h>0
        if action in self._btn_size_indicators:
            self._btn_size_indicators[action].config(text="✅", fg=self.GREEN)

        # Disegna rettangolo grigio sul canvas
        scale = self.scale_factor
        # Usa le coordinate del centro del pulsante esistente per il rettangolo
        btn = self.calibrator.current_profile["act_targets"].get(action, {})
        cx, cy = btn.get("x", 0), btn.get("y", 0)
        sx1, sy1 = int((cx - w // 2) * scale), int((cy - h // 2) * scale)
        sx2, sy2 = int((cx + w // 2) * scale), int((cy + h // 2) * scale)
        self.canvas.create_rectangle(sx1, sy1, sx2, sy2,
                                     outline="#808080", width=1, dash=(4, 2), tags="marker")

        self._update_cal_status()
        self.img_status.config(text=f"📏 {ACTION_BUTTON_LABELS[action]} area: {w}x{h} px")
        self.click_mode = None  # esci dalla modalità
        self._autosave_session()

    def _on_canvas_click(self, event):
        if self.current_image is None:
            return
        real_x = int(event.x / self.scale_factor)
        real_y = int(event.y / self.scale_factor)

        # Se non c'è un profilo attivo, creane uno nuovo
        if self.calibrator.current_profile is None:
            self.calibrator.new_profile()
            self.calibrator.current_profile["name"] = "new_preset"

        if self.click_mode and self.click_mode.startswith("seat_"):
            self._snapshot()
            seat_num = self.click_mode.replace("seat_", "")
            self.calibrator.set_seat(int(seat_num), real_x, real_y)
            self._update_cal_status()
            self._update_completion()
        elif self.click_mode and self.click_mode.startswith("btn_") and not self.click_mode.startswith("btn_size_"):
            self._snapshot()
            action = self.click_mode.replace("btn_", "")
            self.calibrator.set_button(action, real_x, real_y)
            self._update_cal_status()
            self._update_completion()
        elif self.click_mode and self.click_mode.startswith("btn_size_"):
            # Dimensioni pulsante: 2 click = angolo alto-sx e basso-dx
            self.roi_points.append((real_x, real_y))
            action = self.click_mode.replace("btn_size_", "")
            self.canvas.create_oval(event.x-5, event.y-5, event.x+5, event.y+5,
                                    fill="#808080", outline="", tags="marker")
            if len(self.roi_points) == 2:
                self._finalize_button_size(action)
                return
            else:
                self.img_status.config(text=f"📏 {ACTION_BUTTON_LABELS[action]}: 1° punto (alto-sx) ✓ — click per 2° punto (basso-dx)")
                return
        elif self.click_mode == "roi":
            # Raccogli 2 punti: angolo alto-sx e basso-dx
            self.roi_points.append((real_x, real_y))
            self.canvas.create_oval(event.x-5, event.y-5, event.x+5, event.y+5,
                                    fill=self.YELLOW, outline="", tags="marker")
            self.canvas.create_text(event.x+12, event.y-8, text=f"ROI pt{len(self.roi_points)}",
                                   fill=self.YELLOW, font=("Helvetica", 9), tags="marker")
            if len(self.roi_points) == 2:
                self._finalize_roi()
                return
            else:
                self.img_status.config(text="ROI: 1° punto (alto-sx) ✓ — click per 2° punto (basso-dx)")
                return
        elif self.click_mode and self.click_mode.startswith("roi_"):
            # Override ROI (pot/timer/sb/...): 2 click = rettangolo
            self.roi_points.append((real_x, real_y))
            field = self.click_mode.replace("roi_", "")
            _, color = self._roi_field_label(field)
            color_hex = self._roi_hex(color)
            self.canvas.create_oval(event.x-5, event.y-5, event.x+5, event.y+5,
                                    fill=color_hex, outline="", tags="marker")
            if len(self.roi_points) == 2:
                self._finalize_override_roi(field)
                return
            else:
                self.img_status.config(text=f"ROI {field}: 1° punto ✓ — click per 2° punto (basso-dx)")
                return

        # Disegna punto
        self.canvas.create_oval(event.x-5, event.y-5, event.x+5, event.y+5,
                                fill=self.GREEN, outline="", tags="marker")
        label = self.click_mode or f"{real_x},{real_y}"
        self.canvas.create_text(event.x+12, event.y-8, text=label,
                               fill=self.GREEN, font=("Helvetica", 9), tags="marker")
        # Autosave dopo modifica
        self._autosave_session()

    def _on_canvas_motion(self, event):
        """Aggiorna coordinate mouse in tempo reale."""
        if self.coord_tracking and self.current_image is not None:
            real_x = int(event.x / self.scale_factor)
            real_y = int(event.y / self.scale_factor)
            h, w = self.current_image.shape[:2]
            self.coord_label.config(
                text=f"Mouse: canvas({event.x},{event.y}) → immagine({real_x},{real_y}) | "
                     f"Risoluzione: {w}x{h} | Scala: {self.scale_factor:.2f}x"
            )

    def _toggle_coord_tracking(self):
        self.coord_tracking = not self.coord_tracking
        if self.coord_tracking:
            self.btn_coord_toggle.config(text="📍 Disattiva Coordinate", bg=self.GREEN)
        else:
            self.btn_coord_toggle.config(text="📍 Attiva Coordinate", bg=self.BG_CARD)
            self.coord_label.config(text="Mouse: —")

    # ============================================================
    # KEYBOARD SHORTCUTS
    # ============================================================

    def _is_entry_focused(self):
        """True se un entry/widget di testo ha il focus (ignora shortcuts)."""
        w = self.root.focus_get()
        return isinstance(w, (tk.Entry, tk.Text, ttk.Entry))

    def _kb_click_seat(self, n):
        """Shortcut: Shift+1..9 → arma modalit seat_n (poi click sul canvas)."""
        if self._is_entry_focused() or self.current_image is None:
            return
        self.click_mode = f"seat_{n}"
        self.roi_points = []
        self.img_status.config(text=f"Seat {n}: click sul canvas per posizionare")

    def _kb_click_button(self, action):
        """Shortcut: F/C/K/R/A/B → arma modalit btn_action (poi click sul canvas)."""
        if self._is_entry_focused() or self.current_image is None:
            return
        label = ACTION_BUTTON_LABELS.get(action, action.upper())
        self.click_mode = f"btn_{action}"
        self.roi_points = []
        self.img_status.config(text=f"{label}: click sul canvas per posizionare")

    def _kb_define_roi(self):
        """Shortcut: D → arma modalit ROI tavolo (poi 2 click sul canvas)."""
        if self._is_entry_focused() or self.current_image is None:
            return
        self.click_mode = "roi"
        self.roi_points = []
        self.img_status.config(text="ROI: click alto-sx (primo di 2)")

    def _kb_cancel_click(self):
        """Shortcut: Esc → annulla modalit click corrente."""
        self.click_mode = None
        self.roi_points = []
        self.img_status.config(text="Modalit click annullata")

    # ============================================================
    # AUTOSAVE SESSIONE
    # ============================================================

    SESSION_FILE = "session.json"

    def _autosave_session(self):
        """Salva automaticamente lo stato di lavoro corrente in session.json.
        Permette di riprendere la calibrazione se la GUI crasha.
        """
        if not self.calibrator.current_profile:
            return
        try:
            state = {
                "profile": self.calibrator.current_profile,
                "theme": self.current_theme,
                "last_screenshot": getattr(self, '_last_screenshot_path', None),
            }
            session_path = os.path.join(BASE_DIR, self.SESSION_FILE)
            with open(session_path, "w") as f:
                json.dump(state, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[AUTOSAVE] Errore: {e}")

    def _load_session(self):
        """Carica sessione precedente se esiste. Richiede conferma."""
        session_path = os.path.join(BASE_DIR, self.SESSION_FILE)
        if not os.path.exists(session_path):
            return
        try:
            with open(session_path) as f:
                state = json.load(f)
            profile = state.get("profile")
            if not profile or not profile.get("name"):
                return
            # Chiedi conferma
            if not messagebox.askyesno(
                "Sessione precedente",
                f"Trovata sessione precedente: '{profile.get('name', '?')}'.\n"
                "Ripristinare lo stato di lavoro?"
            ):
                return
            # Ripristina
            self.calibrator.current_profile = profile
            self._populate_fields_from_profile(profile)
            theme = state.get("theme")
            if theme and theme in THEMES:
                self._apply_theme(theme)
            # Carica immagine se disponibile
            img_path = state.get("last_screenshot")
            if img_path and os.path.exists(img_path):
                self._load_image(img_path)
            self._update_cal_status()
            self._update_completion()
            print(f"[AUTOSAVE] Sessione ripristinata: {profile.get('name')}")
        except Exception as e:
            print(f"[AUTOSAVE] Errore caricamento sessione: {e}")

    # ============================================================
    # INDICATORE COMPLETAMENTO
    # ============================================================

    def _update_completion(self):
        """Aggiorna la barra di completamento del profilo."""
        p = self.calibrator.current_profile if self.calibrator.current_profile else {}
        items = []
        done = 0
        total = 9

        # 1. Seat (almeno 6)
        seats = p.get("seats", {})
        n_seats = len(seats)
        items.append(("Seat", n_seats >= 6, f"{n_seats}/9"))
        if n_seats >= 6:
            done += 1

        # 2. ROI
        roi = p.get("table_roi", {})
        has_roi = roi.get("w", 0) > 0 and roi.get("h", 0) > 0
        items.append(("ROI", has_roi, "✓" if has_roi else "mancante"))
        if has_roi:
            done += 1

        # 3. Pulsanti (almeno fold/check/raise)
        act = p.get("act_targets", {})
        btns = sum(1 for k in ACTION_BUTTONS_MIN
                   if act.get(k, {}).get("x") or act.get(k, {}).get("y"))
        items.append(("Pulsanti", btns >= 3, f"{btns}/3 min"))
        if btns >= 3:
            done += 1

        # 4. Hero name
        hero_name = p.get("hero", {}).get("name", "")
        has_name = hero_name and hero_name != "hero"
        items.append(("Nome Hero", has_name, hero_name or "mancante"))
        if has_name:
            done += 1

        # 5. Hero seat
        hero_seat = p.get("hero", {}).get("seat")
        items.append(("Seat Hero", hero_seat is not None, str(hero_seat) if hero_seat else "mancante"))
        if hero_seat:
            done += 1

        # 6. Risoluzione
        res = p.get("resolution", {})
        has_res = res.get("width", 0) > 0 and res.get("height", 0) > 0
        items.append(("Risoluzione", has_res,
                       f"{res.get('width',0)}x{res.get('height',0)}" if has_res else "mancante"))
        if has_res:
            done += 1

        # 7. Client name
        client = p.get("client", {}).get("name", "")
        items.append(("Client", bool(client), client or "mancante"))
        if client:
            done += 1

        # 8. Board manuale
        board = p.get("_manual_board", [])
        items.append(("Board", len(board) > 0, f"{len(board)} carte" if board else "mancante"))
        if board:
            done += 1

        # 9. Carte hero manuale
        hero_cards = p.get("_manual_hero_cards", [])
        items.append(("Carte Hero", len(hero_cards) > 0,
                       f"{len(hero_cards)} carte" if hero_cards else "mancante"))
        if hero_cards:
            done += 1

        # Aggiorna UI
        pct = int(done / total * 100)
        if pct == 100:
            color = self.GREEN
        elif pct >= 60:
            color = self.YELLOW
        else:
            color = self.RED
        self.completion_bar.config(text=f"Completamento: {pct}% ({done}/{total})", fg=color)

        missing = [f"❌ {name}" for name, ok, _ in items if not ok]
        if missing:
            self.completion_detail.config(text="Manca: " + " | ".join(missing))
        else:
            self.completion_detail.config(text="✅ Tutti i campi obbligatori compilati!", fg=self.GREEN)

    def _apply_manual_overrides(self):
        """Applica tutti i campi manuali al profilo."""
        if not self.calibrator.current_profile:
            self.calibrator.new_profile()
        else:
            self._snapshot()

        p = self.calibrator.current_profile

        # Nome preset
        if self.entry_preset.get():
            self.calibrator.rename_profile(self.entry_preset.get().strip())

        # Client
        if self.entry_client.get():
            p["client"]["name"] = self.entry_client.get()
        if self.platform_var.get():
            p["client"]["platform"] = self.platform_var.get()

        # Risoluzione
        try:
            rw = int(self.entry_res_w.get())
            rh = int(self.entry_res_h.get())
            if rw > 0 and rh > 0:
                p["resolution"]["width"] = rw
                p["resolution"]["height"] = rh
        except (ValueError, TypeError):
            pass

        # Hero
        if self.entry_hero.get():
            p["hero"]["name"] = self.entry_hero.get()
        try:
            p["hero"]["seat"] = int(self.spin_hero_seat.get())
        except (ValueError, TypeError):
            pass
        p["hero"]["dynamic_seat"] = self.hero_dynamic.get()

        # Carte Hero
        hero_cards_text = self.entry_hero_cards.get().strip()
        if hero_cards_text:
            cards = hero_cards_text.split()
            p["_manual_hero_cards"] = cards
        else:
            p.pop("_manual_hero_cards", None)

        # Board
        board_text = self.entry_board.get().strip()
        if board_text:
            cards = board_text.split()
            p["_manual_board"] = cards
        else:
            p.pop("_manual_board", None)

        # Pot (override manuale)
        pot_text = self._roi_entries["pot"].get().strip()
        if pot_text:
            try:
                p["_manual_pot"] = int(pot_text)
            except ValueError:
                pass
        else:
            p.pop("_manual_pot", None)

        # Timer (override manuale)
        timer_text = self._roi_entries["timer"].get().strip()
        if timer_text:
            try:
                p["_manual_timer"] = int(timer_text)
            except ValueError:
                pass
        else:
            p.pop("_manual_timer", None)

        # Blinds (sb/bb/ante)
        blinds = {}
        for label in ("sb", "bb", "ante"):
            val = self._roi_entries[label].get().strip()
            if val:
                try:
                    blinds[label] = int(val)
                except ValueError:
                    pass
        if blinds:
            p["_manual_blinds"] = blinds
        else:
            p.pop("_manual_blinds", None)

        # Torneo (rimasti/paganti/rank/stack hero)
        t = p.get("_manual_tournament", {})
        if not isinstance(t, dict):
            t = {}
        for key, field in [("players_remaining", "players_remaining"),
                           ("paid_positions", "paid_positions"),
                           ("rank_temporary", "rank_temporary"),
                           ("hero_stack", "hero_stack")]:
            val = self._roi_entries[field].get().strip()
            if val:
                t[key] = val
            else:
                t.pop(key, None)
        if t:
            p["_manual_tournament"] = t
        else:
            p.pop("_manual_tournament", None)

        # ROI Tavolo
        p["table_roi"] = p.get("table_roi", {"x": 0, "y": 0, "w": 0, "h": 0})

        self._update_cal_status()
        self._update_completion()
        self._autosave_session()
        messagebox.showinfo("Applicato", "Override manuali applicati al profilo")

    def _save_override_template(self):
        """Salva gli override manuali correnti come template riutilizzabile."""
        if not self.calibrator.current_profile:
            messagebox.showwarning("Attenzione", "Nessun profilo attivo")
            return
        from tkinter import simpledialog
        name = simpledialog.askstring("Salva Template",
                                       "Nome template (es. ipoker_9max):",
                                       parent=self.root)
        if not name:
            return
        path = self.calibrator.save_override_template(name)
        if path:
            messagebox.showinfo("Template salvato",
                                f"Template '{name}' salvato in:\n{path}")

    def _load_override_template(self):
        """Carica un template override e lo applica al profilo corrente."""
        if not self.calibrator.current_profile:
            messagebox.showwarning("Attenzione", "Nessun profilo attivo")
            return
        templates = self.calibrator.list_templates()
        if not templates:
            messagebox.showinfo("Template", "Nessun template salvato.\nSalva un template dalla stessa room prima di caricarlo.")
            return
        # Mostra selezione
        from tkinter import simpledialog
        name = simpledialog.askstring("Carica Template",
                                       f"Template disponibili:\n{', '.join(templates)}\n\nInserisci il nome:",
                                       parent=self.root)
        if not name:
            return
        ok = self.calibrator.load_override_template(name.strip())
        if ok:
            self._populate_fields_from_profile(self.calibrator.current_profile)
            self._update_cal_status()
            self._update_completion()
            messagebox.showinfo("Template caricato", f"Template '{name}' applicato al profilo")
        else:
            messagebox.showerror("Errore", f"Template '{name}' non trovato")

    def _update_cal_status(self):
        if not self.calibrator.current_profile:
            self.cal_status.config(text="Nessun profilo attivo")
            return
        p = self.calibrator.current_profile
        seats = len(p.get("seats", {}))
        hero = p.get("hero", {})
        act_all = p.get("act_targets", {})
        buttons = sum(1 for a in ACTION_BUTTONS
                      if isinstance(act_all.get(a), dict) and (act_all[a].get("x") or act_all[a].get("y")))
        self.cal_status.config(
            text=f"Client: {p.get('client',{}).get('name','?')} | "
                 f"Seat: {seats}/9 | Hero: {hero.get('name','?')} seat {hero.get('seat','?')} | "
                 f"Pulsanti: {buttons}/{len(ACTION_BUTTONS)}"
        )

    # ============================================================
    # TAB 4: TEST (confronto + lista mancanti)
    # ============================================================

    def _build_tab_test(self, parent):
        frame = tk.Frame(parent, bg=self.BG)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        tk.Label(frame, text="✅ Test di Confronto",
                 bg=self.BG, fg=self.ACCENT, font=("Helvetica", 12, "bold"),
                 anchor=tk.W).pack(fill=tk.X)

        tk.Label(frame, text="Verifica che la Vision legga correttamente tutti gli elementi.",
                 bg=self.BG, fg=self.FG_DIM, font=("Helvetica", 9),
                 anchor=tk.W).pack(fill=tk.X, pady=(0, 5))

        tk.Button(frame, text="▶ Esegui Test Completo",
                  command=self._run_full_test,
                  bg=self.GREEN, fg="#1e1e2e", font=("Helvetica", 11, "bold"),
                  relief=tk.FLAT, padx=15, pady=8).pack(fill=tk.X, pady=5)

        self.test_status = tk.Label(frame, text="Pronto", bg=self.BG, fg=self.FG_DIM,
                                     font=("Helvetica", 9))
        self.test_status.pack(fill=tk.X, pady=3)

        # Lista risultati
        self.test_result_text = tk.Text(frame, bg=self.BG_LIGHT, fg=self.FG,
                                         font=("Courier", 9), height=20, wrap=tk.WORD)
        self.test_result_text.pack(fill=tk.BOTH, expand=True, pady=5)

    def _run_full_test(self):
        """Esegue test completo: analizza e confronta con atteso."""
        if self.current_image is None:
            messagebox.showwarning("Attenzione", "Carica prima uno screenshot")
            return

        self.test_status.config(text="⏳ Test in corso...", fg=self.YELLOW)
        self.test_result_text.delete("1.0", tk.END)
        self.root.update()

        def _do():
            import tempfile, cv2
            tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
            cv2.imwrite(tmp.name, self.current_image)
            result = self.analyzer.analyze_screenshot(tmp.name)
            os.unlink(tmp.name)

            self.root.after(0, self._on_test_done, result)

        threading.Thread(target=_do, daemon=True).start()

    def _on_test_done(self, result):
        """Mostra risultati del test con check elementi."""
        self.test_result_text.delete("1.0", tk.END)
        lines = []

        if result is None:
            lines.append("❌ ANALISI FALLITA — LM Studio non raggiungibile o errore")
            self.test_status.config(text="❌ Test fallito", fg=self.RED)
            self.test_result_text.insert(tk.END, "\n".join(lines))
            return

        # Check elementi
        checks = [
            ("Client", bool(result.get("client_name"))),
            ("Seats", bool(result.get("seats"))),
            ("Hero", bool(result.get("hero", {}).get("name"))),
            ("Board", bool(result.get("board"))),
            ("Pot", result.get("pot") is not None),
            ("Blinds", bool(result.get("blinds", {}).get("sb"))),
            ("Timer", result.get("timer") is not None),
            ("Pulsanti", bool(result.get("buttons"))),
            # BET: appare solo quando Hero è BB non rilanciato
            ("BET (n/a se no BB)", result.get("buttons", {}).get("bet") is not None),
        ]

        passed = 0
        for name, ok in checks:
            icon = "✅" if ok else "❌"
            lines.append(f"  {icon} {name}")
            if ok:
                passed += 1

        lines.append(f"\n  Risultato: {passed}/{len(checks)} elementi rilevati")
        lines.append(f"\n  Dati Vision:\n{json.dumps(result, indent=2, ensure_ascii=False)[:2000]}")

        self.test_result_text.insert(tk.END, "\n".join(lines))
        self.test_status.config(
            text=f"✅ Test completato — {passed}/{len(checks)}",
            fg=self.GREEN if passed == len(checks) else self.YELLOW
        )

    # ============================================================
    # TAB 5: PROFILI
    # ============================================================

    def _build_tab_profiles(self, parent):
        frame = tk.Frame(parent, bg=self.BG)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        btn_frame = tk.Frame(frame, bg=self.BG)
        btn_frame.pack(fill=tk.X, pady=5)

        tk.Button(btn_frame, text="💾 Salva",
                  command=self._save_profile,
                  bg=self.GREEN, fg="#1e1e2e", font=("Helvetica", 10, "bold"),
                  relief=tk.FLAT, padx=10, pady=5).pack(side=tk.LEFT, padx=2)

        tk.Button(btn_frame, text="📂 Carica",
                  command=self._load_profile,
                  bg=self.BG_LIGHT, fg=self.FG, font=("Helvetica", 10),
                  relief=tk.FLAT, padx=10, pady=5).pack(side=tk.LEFT, padx=2)

        tk.Button(btn_frame, text="🔄 Nuovo",
                  command=self._new_profile,
                  bg=self.BG_LIGHT, fg=self.FG, font=("Helvetica", 10),
                  relief=tk.FLAT, padx=10, pady=5).pack(side=tk.LEFT, padx=2)

        tk.Button(frame, text="🚀 Esporta per PokerBotAgent",
                  command=self._export_profile,
                  bg=self.ACCENT, fg="#1e1e2e", font=("Helvetica", 11, "bold"),
                  relief=tk.FLAT, padx=15, pady=8).pack(fill=tk.X, pady=10)

        tk.Button(frame, text="📦 Esporta e Copia in PokerBotAgent",
                  command=self._export_and_copy_to_pokerbot,
                  bg=self.GREEN, fg="#1e1e2e", font=("Helvetica", 10, "bold"),
                  relief=tk.FLAT, padx=15, pady=6).pack(fill=tk.X, pady=2)

        tk.Label(frame, text="Profili salvati:", bg=self.BG, fg=self.FG,
                 font=("Helvetica", 10, "bold"), anchor=tk.W).pack(fill=tk.X)

        self.profile_list = tk.Text(frame, bg=self.BG_LIGHT, fg=self.FG,
                                    font=("Courier", 9), height=10, state=tk.DISABLED)
        self.profile_list.pack(fill=tk.BOTH, expand=True, pady=5)

        self._refresh_profile_list()

    def _new_profile(self):
        self.calibrator.new_profile()
        self._update_cal_status()
        self._update_completion()
        self.undo_stack = []
        try:
            self.undo_count_label.config(text="0")
        except AttributeError:
            pass

    def _save_profile(self):
        if not self.calibrator.current_profile:
            return
        gui_name = self.entry_preset.get().strip() if hasattr(self, "entry_preset") else ""
        current_name = self.calibrator.current_profile.get("name", "")
        renamed = bool(gui_name) and gui_name != current_name
        target_name = gui_name or current_name

        # Assicura che il nome del campo GUI (in cima al tab Calibra) sia
        # sempre trasferito al profilo PRIMA di salvare, così il file assume
        # il nome scelto dall'utente anche se non è stato premuto
        # "Applica Override Manuali".
        if gui_name and gui_name != current_name:
            self.calibrator.current_profile["name"] = gui_name
            renamed = True
            target_name = gui_name

        # Se esiste già un preset con lo stesso nome, chiedi conferma
        if target_name:
            existing_path = os.path.join(PROFILES_DIR, f"{target_name}.json")
            if os.path.exists(existing_path):
                if not messagebox.askyesno("Sovrascrivi?",
                        f"Esiste già il preset '{target_name}'.\nSovrascrivere con i dati aggiornati?"):
                    return

        if renamed:
            # Il nome preset è cambiato: aggiorna il profilo.
            # NOTA: NON azzeriamo current_file qui — save() usa il vecchio file
            # per rimuovere l'eventuale profilo orfano durante il rename.
            self.calibrator.rename_profile(gui_name)

        path = self.calibrator.save()
        if path:
            self._refresh_profile_list()
            messagebox.showinfo("Salvato", f"Profilo salvato:\n{path}")

    def _load_profile(self):
        path = filedialog.askopenfilename(
            filetypes=[("JSON", "*.json")], initialdir=PROFILES_DIR)
        if path:
            self.calibrator.load(path)
            self._update_cal_status()
            self._update_completion()
            self._refresh_profile_list()
            # Popola i campi GUI dal profilo caricato
            p = self.calibrator.current_profile
            if p:
                self._populate_fields_from_profile(p)

    def _populate_fields_from_profile(self, p):
        """Riempie i campi GUI dai dati del profilo caricato."""
        self.entry_preset.delete(0, tk.END)
        self.entry_preset.insert(0, p.get("name", ""))
        self.entry_client.delete(0, tk.END)
        self.entry_client.insert(0, p.get("client", {}).get("name", ""))
        plat = p.get("client", {}).get("platform", "web")
        if plat not in ("web", "client"):
            plat = "web"  # valore storico sconosciuto → default web
        self.platform_var.set(plat)
        # Risoluzione
        res = p.get("resolution", {})
        self.entry_res_w.delete(0, tk.END)
        self.entry_res_w.insert(0, str(res.get("width", 0)))
        self.entry_res_h.delete(0, tk.END)
        self.entry_res_h.insert(0, str(res.get("height", 0)))
        # Hero
        hero = p.get("hero", {})
        self.entry_hero.delete(0, tk.END)
        self.entry_hero.insert(0, hero.get("name", "hero"))
        self.spin_hero_seat.delete(0, tk.END)
        self.spin_hero_seat.insert(0, str(hero.get("seat", 1) if hero.get("seat") is not None else 1))
        # Carte hero
        hero_cards = p.get("_manual_hero_cards", [])
        self.entry_hero_cards.delete(0, tk.END)
        self.entry_hero_cards.insert(0, " ".join(hero_cards) if hero_cards else "")
        # Board
        board = p.get("_manual_board", [])
        self.entry_board.delete(0, tk.END)
        self.entry_board.insert(0, " ".join(board) if board else "")
        # Override entries (pot/timer/blinds/torneo via _roi_entries)
        for field in ("pot", "timer", "sb", "bb", "ante"):
            e = self._roi_entries.get(field)
            if e:
                e.delete(0, tk.END)
        # Pot
        pot = p.get("_manual_pot")
        if "pot" in self._roi_entries:
            if pot is not None:
                self._roi_entries["pot"].insert(0, str(pot))
        # Timer
        timer = p.get("_manual_timer")
        if "timer" in self._roi_entries:
            if timer is not None:
                self._roi_entries["timer"].insert(0, str(timer))
        # Blinds
        blinds = p.get("_manual_blinds", {})
        if not isinstance(blinds, dict):
            blinds = {}
        for label in ("sb", "bb", "ante"):
            e = self._roi_entries.get(label)
            if e:
                e.delete(0, tk.END)
                val = blinds.get(label)
                if val is not None:
                    e.insert(0, str(val))
        # Torneo (rimasti/paganti/rank/stack hero)
        torn = p.get("_manual_tournament", {})
        if not isinstance(torn, dict):
            torn = {}
        for field, key in [("players_remaining", "players_remaining"),
                           ("paid_positions", "paid_positions"),
                           ("rank_temporary", "rank_temporary"),
                           ("hero_stack", "hero_stack")]:
            e = self._roi_entries.get(field)
            if e:
                e.delete(0, tk.END)
                val = torn.get(key)
                if val is not None:
                    e.insert(0, str(val))

        # Override ROIs: aggiorna indicatori ⬜/✅
        rois = p.get("override_rois", {})
        for field in self._roi_indicators:
            has = False
            if ":" in field:
                parent, key = field.split(":", 1)
                sub = rois.get(parent, {})
                has = bool(sub.get(key, {}).get("w")) if isinstance(sub, dict) else False
            else:
                has = bool(rois.get(field, {}).get("w")) if isinstance(rois, dict) else False
            self._roi_indicators[field].config(text="✅" if has else "⬜",
                                               fg=self.GREEN if has else self.FG_DIM)
        # Dimensioni pulsanti (w/h): aggiorna indicatori ⬜/✅
        act = p.get("act_targets", {})
        for action in self._btn_size_indicators:
            has_size = bool(act.get(action, {}).get("w")) and bool(act.get(action, {}).get("h"))
            self._btn_size_indicators[action].config(text="✅" if has_size else "⬜",
                                                     fg=self.GREEN if has_size else self.FG_DIM)
        # Hero dynamic
        if hero.get("dynamic_seat") is not None:
            self.hero_dynamic.set(bool(hero["dynamic_seat"]))
        # ROI
        roi = p.get("table_roi", {})
        if roi.get("w") and roi.get("h"):
            self.roi_status.config(
                text=f"ROI: x={roi['x']}, y={roi['y']}, w={roi['w']}, h={roi['h']}",
                fg=self.GREEN)
        else:
            self.roi_status.config(text="Non definito", fg=self.FG_DIM)

    def _refresh_profile_list(self):
        self.profile_list.config(state=tk.NORMAL)
        self.profile_list.delete("1.0", tk.END)
        profiles = self.calibrator.list_profiles()
        if profiles:
            for p in profiles:
                name = os.path.splitext(os.path.basename(p.get("file", "")))[0]
                self.profile_list.insert(
                    tk.END,
                    f"  📄 {name}\n"
                    f"     Client: {p.get('client','?')} | {p.get('platform','?')} | "
                    f"{p.get('resolution','?')} | Seat: {p.get('seats','?')}\n"
                )
        else:
            self.profile_list.insert(tk.END, "  Nessun profilo salvato\n")
        self.profile_list.config(state=tk.DISABLED)

    def _export_profile(self):
        path = self.calibrator.export_for_pokerbot()
        if path:
            messagebox.showinfo("Esportato", f"Layout esportato:\n{path}")
        else:
            messagebox.showerror("Errore", "Nessun profilo valido da esportare. Completa la calibrazione prima di esportare.")

    def _export_and_copy_to_pokerbot(self):
        """Esporta e copia in PokerBotAgent con dry-run diff se esiste già."""
        path = self.calibrator.export_for_pokerbot(copy_to_pokerbot=False)
        if not path:
            return
        # Controlla se esiste già il file destinazione
        dest_dir = self.calibrator._find_pokerbot_layouts_dir()
        if not dest_dir:
            messagebox.showerror("Errore", "Cartella layouts di PokerBotAgent non trovata. Assicurati che PokerBotAgent sia nella directory corretta.")
            return
        dest_name = os.path.basename(path)
        dest_path = os.path.join(dest_dir, dest_name)
        if os.path.exists(dest_path):
            # Leggi vecchio e nuovo
            with open(dest_path) as f:
                old = f.read()
            with open(path) as f:
                new = f.read()
            if old == new:
                messagebox.showinfo("Nessuna modifica",
                                    "Il layout esistente è identico. Nessuna copia necessaria.")
                return
            # Mostra diff sintetico
            old_lines = old.strip().splitlines()
            new_lines = new.strip().splitlines()
            diff_msg = f"File esistente: {dest_name}\n\n"
            diff_msg += f"Righe vecchie: {len(old_lines)}\n"
            diff_msg += f"Righe nuove: {len(new_lines)}\n\n"
            # Mostra prime differenze
            diffs = []
            for i, (o, n) in enumerate(zip(old_lines, new_lines)):
                if o != n:
                    diffs.append(f"  L{i+1}: {o.strip()[:40]} → {n.strip()[:40]}")
                    if len(diffs) >= 8:
                        diffs.append("  ... (altre differenze)")
                        break
            if not diffs and len(old_lines) != len(new_lines):
                diffs.append(f"  Differenza lunghezza: {len(old_lines)} → {len(new_lines)} righe")
            diff_msg += "Differenze:\n" + "\n".join(diffs) if diffs else "Solo differenze di lunghezza"
            diff_msg += "\n\nSovrascrivere?"
            if not messagebox.askyesno("Conferma sovrascrittura", diff_msg):
                return
        # Copia
        import shutil
        shutil.copy2(path, dest_path)
        messagebox.showinfo("Esportato", f"Layout copiato in PokerBotAgent:\n{dest_path}")

    # ============================================================
    # RUN
    # ============================================================

    def run(self):
        self.root.mainloop()


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    app = App()
    app.run()
