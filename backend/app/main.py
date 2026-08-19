from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import agents, chat, city, events, ml, perception, simulation, world

app = FastAPI(
    title="智哨先锋 API",
    description="城市行为智能推演 Agent。所有人员、关系、轨迹与风险事件均为 Synthetic Data。",
    version="0.1.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for route in (city.router, agents.router, events.router, world.router, simulation.router, chat.router, perception.router, ml.router):
    app.include_router(route, prefix="/api")


@app.get("/")
def root():
    return {"name": "智哨先锋", "status": "ready", "synthetic_data": True, "docs": "/docs"}


@app.get("/health")
def health():
    return {"status": "ok"}

