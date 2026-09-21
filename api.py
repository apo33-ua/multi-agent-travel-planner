"""FastAPI wrapper que expone el orquestador como API HTTP para el frontend."""
from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from supervisor_viajes import run_supervisor_structured

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%H:%M:%S")

app = FastAPI(title="Orquestador de Viajes - API", version="1.0.0")

# CORS abierto para desarrollo local. En produccion conviene restringir a la URL del frontend.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class PlanRequest(BaseModel):
    ciudad: str = Field(..., min_length=1, description="Ciudad destino del viaje")
    contexto_viaje: str = Field(default="", description="Descripcion libre del proposito del viaje")
    objetivo_usuario: str = Field(default="", description="Objetivo especifico del usuario")
    fecha_inicio: str = Field(default="", description="Fecha de inicio en formato YYYY-MM-DD")
    fecha_fin: str = Field(default="", description="Fecha de fin en formato YYYY-MM-DD")
    origen_iata: str = Field(default="MAD", description="Codigo IATA del aeropuerto de origen")
    destino_iata: str = Field(default="", description="Codigo IATA del aeropuerto de destino (opcional)")
    presupuesto_total_eur: float = Field(default=0, ge=0, description="Presupuesto maximo en euros")
    adultos: int = Field(default=2, ge=1, description="Numero de viajeros adultos")


@app.get("/")
def root() -> dict[str, str]:
    return {"status": "ok", "service": "orquestador-viajes", "docs": "/docs"}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "healthy"}


@app.post("/plan")
def generar_plan(request: PlanRequest) -> dict[str, Any]:
    """Lanza el grafo del supervisor con los parametros recibidos y devuelve el plan."""
    try:
        result = run_supervisor_structured(
            ciudad=request.ciudad,
            contexto_viaje=request.contexto_viaje,
            objetivo_usuario=request.objetivo_usuario,
            fecha_inicio=request.fecha_inicio,
            fecha_fin=request.fecha_fin,
            origen_iata=request.origen_iata,
            destino_iata=request.destino_iata,
            presupuesto_total_eur=request.presupuesto_total_eur,
            adultos=request.adultos,
        )
        return result
    except Exception as exc:
        logging.exception("Error generando el plan")
        raise HTTPException(status_code=500, detail=str(exc))
