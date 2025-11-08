from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import threading
import time
import json
import os

app = FastAPI(title="Project Timers")

# ---- 🔒 CORS configuration ----
origins = [
    "https://strategix.ch",
    "https://www.strategix.ch",
    "https://chatelain.li",
    "https://www.chatelain.li",
    "http://localhost:8000",  # pour tests locaux
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- Données et stockage ----------
STATE_FILE = "timers_state.json"
LOCK = threading.Lock()

class ProjectTimer(BaseModel):
    name: str
    total_seconds: float = 0.0
    running: bool = False
    start_time: float | None = None

def load_state() -> dict[int, ProjectTimer]:
    if not os.path.exists(STATE_FILE):
        return {i: ProjectTimer(name=f"Projet {i}") for i in range(1, 11)}
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        raw = json.load(f)
    timers = {int(k): ProjectTimer(**v) for k, v in raw.items()}
    return timers

def save_state(timers: dict[int, ProjectTimer]):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump({str(i): t.dict() for i, t in timers.items()}, f, ensure_ascii=False, indent=2)

TIMERS = load_state()

def get_effective_seconds(t: ProjectTimer) -> float:
    if t.running and t.start_time is not None:
        return t.total_seconds + (time.time() - t.start_time)
    return t.total_seconds

# ---------- API ----------
class ToggleRequest(BaseModel):
    running: bool

@app.get("/", response_class=HTMLResponse)
def index():
    # ... (HTML identique à la version précédente)
    return HTMLResponse("<h2>Interface disponible via /status et /toggle</h2>")

@app.get("/status")
def get_status():
    with LOCK:
        now = time.time()
        projects = {
            str(i): {
                "name": t.name,
                "total_seconds": get_effective_seconds(t),
                "running": t.running,
                "start_time": (now if t.running else None),
            }
            for i, t in TIMERS.items()
        }
        # Mise à jour continue si nécessaire
        for t in TIMERS.values():
            if t.running and t.start_time is not None:
                t.total_seconds += now - t.start_time
                t.start_time = now
        save_state(TIMERS)
    return {"server_time": now, "projects": projects}

@app.post("/toggle/{project_id}")
def toggle_timer(project_id: int, req: ToggleRequest):
    if project_id not in TIMERS:
        raise HTTPException(status_code=404, detail="Projet inexistant")
    with LOCK:
        t = TIMERS[project_id]
        now = time.time()
        if not req.running and t.running:
            if t.start_time:
                t.total_seconds += now - t.start_time
            t.start_time = None
            t.running = False
        elif req.running and not t.running:
            t.start_time = now
            t.running = True
        save_state(TIMERS)
        return {
            "name": t.name,
            "total_seconds": get_effective_seconds(t),
            "running": t.running,
            "start_time": t.start_time,
        }

