# api.py
# Simulation d'ascenseur "headless" (compatible Render) exposée via FastAPI
# - Endpoints: /, /ping, /status (GET), /call (POST)
# - CORS autorisé pour vos domaines WordPress (chatelain.li, strategix.ch)

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import threading
import time

# --------- Configuration ---------
TOTAL_FLOORS = 10          # nombre d'étages (0..9)
STEP_PERIOD_SEC = 1.5      # "tick" de la simulation

ALLOWED_ORIGINS = [
    "https://chatelain.li",
    "https://www.chatelain.li",
    "https://strategix.ch",
    "https://www.strategix.ch",
]

# --------- App FastAPI + CORS ---------
app = FastAPI(
    title="Ascenseur virtuel",
    description="Simulation d'un ascenseur via API web (compat. Render).",
    version="1.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    allow_credentials=False,
)

# --------- Modèles d'E/S ---------
class Call(BaseModel):
    floor: int = Field(ge=0, lt=TOTAL_FLOORS, description="Étage demandé")

class Status(BaseModel):
    current_floor: int
    direction: str
    doors: str
    pending_calls: list[int]

# --------- Logique d'ascenseur ---------
class Elevator:
    def __init__(self, floors: int):
        self.total_floors = floors
        self.current_floor = 0
        self.direction = "idle"   # "up" | "down" | "idle"
        self.doors = "closed"     # "open" | "closed"
        self.requests: set[int] = set()
        self.lock = threading.Lock()

    def _next_target(self) -> int | None:
        if not self.requests:
            return None
        return (max(self.requests) if self.direction == "up"
                else min(self.requests) if self.direction == "down"
                else min(self.requests, key=lambda f: abs(f - self.current_floor)))

    def step(self):
        with self.lock:
            if not self.requests:
                self.direction = "idle"
                self.doors = "closed"
                return

            if self.doors == "open":
                self.doors = "closed"
                return

            target = self._next_target()
            if target is None:
                self.direction = "idle"
                return

            if self.current_floor == target:
                self.doors = "open"
                self.requests.discard(target)
                if not self.requests:
                    self.direction = "idle"
                else:
                    nearest = min(self.requests, key=lambda f: abs(f - self.current_floor))
                    self.direction = "up" if nearest > self.current_floor else "down"
                return

            if target > self.current_floor:
                self.current_floor += 1
                self.direction = "up"
                if self.current_floor >= self.total_floors - 1 and max(self.requests) <= self.current_floor:
                    self.direction = "down"
            elif target < self.current_floor:
                self.current_floor -= 1
                self.direction = "down"
                if self.current_floor <= 0 and min(self.requests) >= self.current_floor:
                    self.direction = "up"

    def call(self, floor: int):
        if floor < 0 or floor >= self.total_floors:
            raise ValueError("Étage invalide.")
        with self.lock:
            self.requests.add(floor)
            if self.direction == "idle":
                self.direction = "up" if floor > self.current_floor else "down" if floor < self.current_floor else "idle"
                if self.current_floor == floor:
                    self.doors = "open"

    def status(self) -> Status:
        with self.lock:
            return Status(
                current_floor=self.current_floor,
                direction=self.direction,
                doors=self.doors,
                pending_calls=sorted(self.requests),
            )

# --------- Thread de simulation ---------
elevator = Elevator(floors=TOTAL_FLOORS)

def _loop():
    while True:
        try:
            elevator.step()
        except Exception:
            pass
        time.sleep(STEP_PERIOD_SEC)

threading.Thread(target=_loop, daemon=True).start()

# --------- Routes ---------
@app.get("/", tags=["health"])
def root():
    return {"message": "Ascenseur virtuel en ligne", "floors": TOTAL_FLOORS}

@app.get("/ping", tags=["health"])
def ping():
    return {"ok": True}

@app.get("/status", response_model=Status, tags=["elevator"])
def get_status():
    return elevator.status()

@app.post("/call", tags=["elevator"])
def make_call(call: Call):
    try:
        elevator.call(call.floor)
        return {"message": f"Appel enregistré à l'étage {call.floor}"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
