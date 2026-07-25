"""
utils_rutinas.py — Acceso al catálogo de ejercicios
--------------------------------------------------------------------------------
El catálogo NO es un dataset que se "descarga": es contenido curado que ya
armaste (exercises_catalog_spanish_version.parquet — 1324 ejercicios, 24
columnas). Este módulo solo lo carga, lo cachea, y lo filtra por equipo
disponible / zona muscular / dificultad para alimentar al generador de
rutinas y a la página 02_Rutinas.py.

Estructura confirmada del parquet (revisada directo con pandas):
  - Un ejercicio = una fila. `equipment` es UN equipo por fila (no listas).
  - id: string de 4 dígitos con ceros a la izquierda (ej. "0001").
  - media_id: string corto que arma el nombre del gif junto con id:
        Assets/ejercicios_media/videos/{id}-{media_id}.gif
  - zona_muscular: una de 7 categorías agregadas (Core, Tren inferior, etc.)
  - dificultad_final: 'principiante' | 'intermedio' | 'experto'
"""

from pathlib import Path

import pandas as pd
import streamlit as st

BASE_DIR = Path(__file__).resolve().parent
RUTA_CATALOGO = BASE_DIR / "Assets" / "exercises_catalog_spanish_version.parquet"
RUTA_GIFS = BASE_DIR / "Assets" / "ejercicios_media" / "videos"

# Mismo orden en que David los reportó — se usa tal cual en el multiselect
# de equipo para que el usuario no tenga que adivinar nombres.
EQUIPO_OPCIONES = [
    "peso corporal", "mancuerna", "barra", "barra ez", "barra olímpica",
    "barra hexagonal", "polea", "máquina de palanca", "máquina smith",
    "máquina de trineo", "máquina hammer", "máquina skierg", "kettlebell",
    "banda de resistencia", "balón de estabilidad", "balón medicinal",
    "balón bosu", "cuerda", "rodillo", "rueda abdominal", "llanta",
    "con peso (lastrado)", "asistido", "bicicleta estática", "elíptica",
    "escaladora", "ergómetro de tren superior",
]

ZONAS_MUSCULARES = [
    "Core", "Tren inferior", "Tracción superior", "Empuje superior",
    "Cardio", "Accesorio (antebrazo)", "Accesorio (cuello)",
]

ORDEN_DIFICULTAD = {"principiante": 0, "intermedio": 1, "experto": 2}

OBJETIVOS = [
    "Bajar de peso",
    "Ganar músculo",
    "Ganar fuerza",
    "Mejorar resistencia/cardio",
    "Salud general",
]


@st.cache_data
def cargar_catalogo() -> pd.DataFrame:
    """Carga el parquet una sola vez por sesión de servidor (cacheado)."""
    return pd.read_parquet(RUTA_CATALOGO)


def ruta_gif(fila: pd.Series) -> Path:
    return RUTA_GIFS / f"{fila['id']}-{fila['media_id']}.gif"


def filtrar_ejercicios(
    equipo_disponible: list[str],
    zona_muscular: str | None = None,
    dificultad_max: str | None = None,
) -> pd.DataFrame:
    """
    Filtra el catálogo por el equipo que el usuario tiene disponible (join
    simple porque equipment es un valor por fila, no una lista), y
    opcionalmente por zona muscular y tope de dificultad.
    """
    df = cargar_catalogo()

    if not equipo_disponible:
        return df.iloc[0:0]  # sin equipo seleccionado = sin resultados

    df = df[df["equipment"].isin(equipo_disponible)]

    if zona_muscular and zona_muscular != "Todas":
        df = df[df["zona_muscular"] == zona_muscular]

    if dificultad_max:
        tope = ORDEN_DIFICULTAD[dificultad_max]
        df = df[df["dificultad_final"].map(ORDEN_DIFICULTAD) <= tope]

    return df


# ═══════════════════════════════════════════════════════════════════════════
# RESERVADO — EN DESARROLLO
# ═══════════════════════════════════════════════════════════════════════════
# generar_rutina(usuario_id, duracion_min, enfoque) -> list[ejercicios]
#   Pendiente: el generador real de rutinas completas (no solo el browser
#   de ejercicios individuales). Debe combinar:
#     - equipo_disponible (utils_db.obtener_equipo_usuario)
#     - objetivo (utils_db.obtener_perfil -> "objetivo")
#     - nivel_cluster oculto (utils_db.obtener_clasificacion) SOLO para
#       tope de dificultad, nunca para mostrarlo
#     - cobertura de zonas musculares (no repetir la misma zona 2x seguidas)
# ═══════════════════════════════════════════════════════════════════════════
