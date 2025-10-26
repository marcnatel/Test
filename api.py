# ascenseur.py
# Visualisation d'un contrôleur d'ascenseur (tkinter, sans dépendances externes)
# Logique : contrôle collectif (SCAN) — dessert dans le sens courant, puis inverse.

import tkinter as tk
from tkinter import ttk
import math
import random

# --------------------- Paramètres ---------------------
FLOORS = 10               # 0..9
SHAFT_HEIGHT = 600        # px
SHAFT_WIDTH = 220
CAR_WIDTH = 60
CAR_HEIGHT = 40
FLOOR_GAP = SHAFT_HEIGHT / (FLOORS - 1)
SPEED_FLOORS_PER_SEC = 0.9
DOOR_OPEN_TIME = 1000     # ms
TICK_MS = 30              # période animation

# --------------------- Modèle -------------------------
class ElevatorModel:
    def __init__(self, floors):
        self.floors = floors
        self.pos = 0.0                # position continue (0 = RDC)
        self.direction = 0            # -1 desc, +1 mont, 0 idle
        self.up_calls = set()         # appels palier UP
        self.down_calls = set()       # appels palier DOWN
        self.car_targets = set()      # sélections cabine
        self.door_open = False
        self.door_timer = 0           # ms restant portes ouvertes

    @property
    def current_floor_int(self):
        return int(round(self.pos))

    def has_any_request(self):
        return bool(self.up_calls or self.down_calls or self.car_targets)

    def requests_above(self, at):
        return {f for f in self.all_targets() if f > at}

    def requests_below(self, at):
        return {f for f in self.all_targets() if f < at}

    def all_targets(self):
        # Unifie tous les objectifs (cabine + paliers)
        return self.car_targets | self.up_calls | self.down_calls

    def should_stop_here(self, floor, going_dir):
        """Décide si on doit s'arrêter à 'floor' compte tenu du sens."""
        stop = False
        # En montée : on sert car_targets, up_calls et down_calls si on va inverser au sommet
        if going_dir >= 0:
            if floor in self.car_targets or floor in self.up_calls:
                stop = True
            # Si plus rien au-dessus, autoriser la prise des DOWN au passage (fin de montée)
            if not self.requests_above(floor) and floor in self.down_calls:
                stop = True
        # En descente : symétrique
        if going_dir <= 0:
            if floor in self.car_targets or floor in self.down_calls:
                stop = True
            if not self.requests_below(floor) and floor in self.up_calls:
                stop = True
        # À l’arrêt (idle) : on s’arrête si demandé
        if going_dir == 0:
            if floor in self.all_targets():
                stop = True
        return stop

    def commit_stop(self, floor):
        # On efface les demandes satisfaites au palier et en cabine
        if floor in self.car_targets:
            self.car_targets.discard(floor)
        # En pratique on efface les deux sens si on ouvre
        self.up_calls.discard(floor)
        self.down_calls.discard(floor)
        # Portes ouvertes
        self.door_open = True
        self.door_timer = DOOR_OPEN_TIME

    def choose_direction_if_idle(self):
        if self.direction != 0:
            return
        if not self.has_any_request():
            return
        # Choix du sens le plus "proche" (heuristique simple)
        up = self.requests_above(self.pos)
        down = self.requests_below(self.pos)
        if up and down:
            # Choisir le plus proche
            d_up = min(abs(f - self.pos) for f in up)
            d_dn = min(abs(f - self.pos) for f in down)
            self.direction = +1 if d_up <= d_dn else -1
        elif up:
            self.direction = +1
        elif down:
            self.direction = -1

    def maybe_reverse(self):
        # Inversion quand plus rien dans le sens courant
        if self.direction > 0 and not self.requests_above(math.floor(self.pos)):
            if self.has_any_request():
                self.direction = -1
            else:
                self.direction = 0
        elif self.direction < 0 and not self.requests_below(math.ceil(self.pos)):
            if self.has_any_request():
                self.direction = +1
            else:
                self.direction = 0

    def step(self, dt_ms):
        dt = dt_ms / 1000.0
        # Gestion portes
        if self.door_open:
            self.door_timer -= dt_ms
            if self.door_timer <= 0:
                self.door_open = False
            return

        # Si idle, choisir un sens si des demandes existent
        if self.direction == 0:
            self.choose_direction_if_idle()

        # Avance si on a une direction
        if self.direction != 0:
            delta = self.direction * SPEED_FLOORS_PER_SEC * dt
            self.pos += delta
            # Clamp aux bornes
            self.pos = max(0.0, min(self.pos, self.floors - 1))

            # Détection d'arrivée à un étage (snap si proche)
            nearest = round(self.pos)
            if abs(self.pos - nearest) < 0.02:
                self.pos = float(nearest)
                # Arrêt si demandé selon la logique
                if self.should_stop_here(int(nearest), self.direction):
                    self.commit_stop(int(nearest))
                    # Recalcule la direction après arrêt (peut inverser plus tard)
                    self.maybe_reverse()
                else:
                    # Si plus rien dans ce sens, on inverse
                    self.maybe_reverse()
        else:
            # Idle, si une demande au même étage, on ouvre
            f = int(round(self.pos))
            if f in self.all_targets():
                self.commit_stop(f)

# --------------------- Vue (tkinter) ---------------------
class ElevatorUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Ascenseur - Démonstrateur logique (SCAN)")
        self.resizable(False, False)

        self.model = ElevatorModel(FLOORS)

        self.canvas = tk.Canvas(self, width=SHAFT_WIDTH + 200, height=SHAFT_HEIGHT + 40, bg="white")
        self.canvas.grid(row=0, column=0, padx=10, pady=10, columnspan=2, sticky="n")

        # Panneau boutons palier
        self.panel = ttk.Frame(self)
        self.panel.grid(row=0, column=2, sticky="ns", padx=10, pady=10)
        ttk.Label(self.panel, text="Appels paliers").grid(row=0, column=0, columnspan=2, pady=(0,8))

        self.btn_up = {}
        self.btn_dn = {}
        for f in reversed(range(FLOORS)):
            r = (FLOORS - 1 - f) + 1
            ttk.Label(self.panel, text=f"Étage {f}").grid(row=r, column=0, sticky="w")
            frm = ttk.Frame(self.panel)
            frm.grid(row=r, column=1, sticky="e")
            if f < FLOORS - 1:
                b = ttk.Button(frm, text="Up", width=4, command=lambda k=f: self.add_up(k))
                b.grid(row=0, column=0, padx=2)
                self.btn_up[f] = b
            else:
                ttk.Label(frm, text="   ").grid(row=0, column=0)
            if f > 0:
                b = ttk.Button(frm, text="Down", width=6, command=lambda k=f: self.add_down(k))
                b.grid(row=0, column=1, padx=2)
                self.btn_dn[f] = b

        # Panneau cabine
        self.cabin = ttk.Frame(self)
        self.cabin.grid(row=0, column=3, sticky="ns", padx=10, pady=10)
        ttk.Label(self.cabin, text="Sélection cabine").grid(row=0, column=0, columnspan=3, pady=(0,8))
        self.cabin_buttons = {}
        for i, f in enumerate(reversed(range(FLOORS))):
            r = i // 3 + 1
            c = i % 3
            b = ttk.Button(self.cabin, text=str(f), width=4, command=lambda k=f: self.add_cabin(k))
            b.grid(row=r, column=c, padx=3, pady=3)
            self.cabin_buttons[f] = b

        # Statut
        self.status = tk.StringVar(value="Prêt.")
        ttk.Label(self, textvariable=self.status).grid(row=1, column=0, columnspan=4, sticky="we", padx=10, pady=(0,10))

        # dessin statique
        self.draw_static()
        self.after(TICK_MS, self.loop)

        # générateur (option) pour voir la logique tourner
        self.after(4000, self.random_seed_requests)

    # --- Actions ---
    def add_up(self, f):
        self.model.up_calls.add(f)
        self.status.set(f"Appel UP à l'étage {f}")
    def add_down(self, f):
        self.model.down_calls.add(f)
        self.status.set(f"Appel DOWN à l'étage {f}")
    def add_cabin(self, f):
        self.model.car_targets.add(f)
        self.status.set(f"Destination cabine {f}")

    # --- Animation principale ---
    def loop(self):
        self.model.step(TICK_MS)
        self.draw_dynamic()
        self.after(TICK_MS, self.loop)

    # --- Dessin ---
    def y_for_floor(self, f):
        # 0 en bas, SHAFT_HEIGHT en haut
        return (FLOORS - 1 - f) * FLOOR_GAP + 20

    def draw_static(self):
        self.canvas.delete("all")
        x0 = 40
        x1 = x0 + SHAFT_WIDTH
        # Gaine
        self.canvas.create_rectangle(x0, 20, x1, 20 + SHAFT_HEIGHT, outline="#333", width=2)
        # Étages
        for f in range(FLOORS):
            y = self.y_for_floor(f)
            self.canvas.create_line(x0, y, x1, y, fill="#ddd")
            self.canvas.create_text(x0 - 20, y, text=str(f), anchor="e")

    def draw_dynamic(self):
        # Efface éléments dynamiques
        self.canvas.delete("car")
        self.canvas.delete("tag")

        x0 = 40
        car_x = x0 + (SHAFT_WIDTH - CAR_WIDTH) / 2
        # Position cabine
        y = self.y_for_floor(self.model.pos)
        # Cabine
        outline = "#2a7" if not self.model.door_open else "#e67e22"
        self.canvas.create_rectangle(car_x, y - CAR_HEIGHT/2, car_x + CAR_WIDTH, y + CAR_HEIGHT/2,
                                     outline=outline, width=3, tags="car")

        # Portes (représentation simple : ouvertes = écartées)
        if self.model.door_open:
            gap = CAR_WIDTH // 2 - 6
        else:
            gap = 4
        # Deux panneaux
        self.canvas.create_rectangle(car_x, y - CAR_HEIGHT/2, car_x + CAR_WIDTH/2 - gap, y + CAR_HEIGHT/2,
                                     outline="#555", fill="#cfd8dc", tags="car")
        self.canvas.create_rectangle(car_x + CAR_WIDTH/2 + gap, y - CAR_HEIGHT/2, car_x + CAR_WIDTH, y + CAR_HEIGHT/2,
                                     outline="#555", fill="#cfd8dc", tags="car")

        # Affichage demandes (tags colorés)
        for f in self.model.up_calls:
            self.draw_tag(f, "UP", "#1e88e5")
        for f in self.model.down_calls:
            self.draw_tag(f, "DN", "#8e24aa", dx=+16)
        for f in self.model.car_targets:
            self.draw_tag(f, "CAR", "#f4511e", dx=-18)

        # Indicateur direction
        direc = {+1: "↑", -1: "↓", 0: "•"}[self.model.direction]
        msg = f"Pos: {self.model.pos:.2f}  Dir: {direc}  Portes: {'OUVERTES' if self.model.door_open else 'fermées'}"
        self.status.set(msg)

    def draw_tag(self, floor, text, color, dx=0):
        x = 40 + SHAFT_WIDTH + 25 + dx
        y = self.y_for_floor(floor)
        self.canvas.create_text(x, y, text=text, fill=color, font=("TkDefaultFont", 9, "bold"), tags="tag")

    # --- Générateur de démos (optionnel) ---
    def random_seed_requests(self):
        # Ajoute quelques demandes pour démarrer visuellement
        for _ in range(3):
            f1 = random.randint(0, FLOORS - 2)
            f2 = random.randint(f1 + 1, FLOORS - 1)
            self.model.up_calls.add(f1)
            self.model.car_targets.add(f2)
        # relance de temps en temps
        self.after(8000, self.random_more)

    def random_more(self):
        # Un peu d'aléatoire pour voir l'inversion de sens
        f = random.randint(0, FLOORS - 1)
        if random.random() < 0.5:
            if f < FLOORS - 1:
                self.model.up_calls.add(f)
        else:
            if f > 0:
                self.model.down_calls.add(f)
        if random.random() < 0.3:
            self.model.car_targets.add(random.randint(0, FLOORS - 1))
        self.after(6000, self.random_more)

# --------------------- Lancement ---------------------
if __name__ == "__main__":
    app = ElevatorUI()
    app.mainloop()
