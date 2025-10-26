# api.py
# Version web (FastAPI) du simulateur d'ascenseur

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import threading
import time

app = FastAPI(title="Ascenseur virtuel", description="Simulation d'un ascenseur via API web.")

# ----------------- Modèle de données -----------------
class Call(BaseModel):
    floor: int

# ----------------- État de l'ascenseur -----------------
class Elevator:
    def __init__(self, floors=10):
        self.total_floors = floors
        self.current_floor = 0
        self.direction = "up"     # up, down, idle
        self.doors = "closed"
        self.requests = set()
        self.lock = threading.Lock()

    def step(self):
        """Fait avancer l'ascenseur d'un étage ou ouvre les portes s'il doit s'arrêter."""
        with self.lock:
            if not self.requests:
                self.direction = "idle"
                self.doors = "closed"
                return

            # Si porte ouverte, on la referme après un petit délai
            if self.doors == "open":
                self.doors = "closed"
                return

            target = min(self.requests) if self.direction == "down" else max(self.requests)

            # Si déjà au bon étage → ouvrir portes et retirer demande
            if self.current_floor == target:
                self.doors = "open"
                self.requests.discard(target)
                if not self.requests:
                    self.direction = "idle"
                return

            # Sinon, on avance d'un étage dans la direction actuelle
            if self.direction == "up":
                self.current_floor += 1
                if self.current_floor >= self.total_floors - 1:
                    self.direction = "down"
            elif self.direction == "down":
                self.current_floor -= 1
                if self.current_floor <= 0:
                    self.direction = "up"

    def call(self, floor: int):
        with self.lock:
            if floor < 0 or floor >= self.total_floors:
                raise ValueError("Étage invalide.")
            self.requests.add(floor)
            if self.direction == "idle":
                self.direction = "up" if floor > self.current_floor else "down"

    def status(self):
        with self.lock:
            return {
                "current_floor": self.current_floor,
                "direction": self.direction,
                "doors": self.doors,
                "pending_calls": sorted(list(self.requests)),
            }

elevator = Elevator(floors=10)

# ----------------- Boucle en arrière-plan -----------------
def loop():
    while True:
        elevator.step()
        time.sleep(1.5)

threading.Thread(target=loop, daemon=True).start()

# ----------------- Routes FastAPI -----------------
@app.get("/")
def root():
    return {"message": "Ascenseur virtuel en ligne"}

@app.get("/status")
def get_status():
    return elevator.status()

@app.post("/call")
def make_call(call: Call):
    try:
        elevator.call(call.floor)
        return {"message": f"Appel enregistré à l'étage {call.floor}"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
