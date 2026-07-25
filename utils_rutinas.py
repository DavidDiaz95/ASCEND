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
# GENERADOR DE RUTINAS — similitud coseno entre ejercicios y perfil ideal
# ═══════════════════════════════════════════════════════════════════════════
import hashlib
from datetime import datetime

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

# Dificultad continua aproximada por tier — se usa SOLO si el catálogo no
# trae una columna continua (score_llm). Si sí la trae, esa tiene prioridad
# porque es más precisa que el punto medio del tier.
DIFICULTAD_CONTINUA_POR_TIER = {"principiante": 25, "intermedio": 55, "experto": 85}

# Rango de dificultad tolerable por cluster — mismo criterio ya usado en el
# clasificador. Si el usuario todavía no tiene clasificación (tabla vacía,
# como es el caso ahora mismo), se usa el default conservador.
RANGO_DIFICULTAD_POR_CLUSTER = {
    "Rendimiento Atlético Alto": (35, 90),
    "Contextura Ligera, Fuerza Limitada": (15, 65),
    "Contextura Ligera, Buena Eficiencia": (20, 75),
    "Composición Corporal Elevada": (10, 55),
}
RANGO_DEFAULT_SIN_CLASIFICACION = (20, 60)

# Perfil de zonas "ideal" por objetivo — cuánto debería pesar cada zona en la
# rutina, y en qué punto de su rango de dificultad debería ubicarse (0=bajo
# del rango, 1=alto del rango). Decisión de producto, no validada estadísticamente.
PERFILES_OBJETIVO = {
    "Bajar de peso": {
        "zonas_ideal": {"Cardio": 0.35, "Core": 0.20, "Tren inferior": 0.20,
                         "Empuje superior": 0.125, "Tracción superior": 0.125},
        "posicion_en_rango": 0.35,
    },
    "Ganar músculo": {
        "zonas_ideal": {"Empuje superior": 0.3, "Tracción superior": 0.3, "Tren inferior": 0.3,
                         "Core": 0.1},
        "posicion_en_rango": 0.55,
    },
    "Ganar fuerza": {
        "zonas_ideal": {"Empuje superior": 0.3, "Tracción superior": 0.3, "Tren inferior": 0.3,
                         "Core": 0.05, "Cardio": 0.05},
        "posicion_en_rango": 0.8,
    },
    "Mejorar resistencia/cardio": {
        "zonas_ideal": {"Cardio": 0.4, "Tren inferior": 0.25, "Core": 0.2,
                         "Empuje superior": 0.075, "Tracción superior": 0.075},
        "posicion_en_rango": 0.45,
    },
    "Salud general": {
        "zonas_ideal": {"Empuje superior": 0.2, "Tracción superior": 0.2, "Tren inferior": 0.2,
                         "Core": 0.2, "Cardio": 0.2},
        "posicion_en_rango": 0.5,
    },
}

REPS_RANGE_POR_OBJETIVO = {
    "Bajar de peso": (15, 20), "Ganar músculo": (10, 12), "Ganar fuerza": (5, 8),
    "Mejorar resistencia/cardio": (15, 25), "Salud general": (10, 15),
}


def _obtener_dificultad_continua(df: pd.DataFrame) -> pd.Series:
    """score_llm si existe en el catálogo (más preciso); si no, se aproxima
    con el punto medio del tier de dificultad_final."""
    if "score_llm" in df.columns:
        return df["score_llm"]
    return df["dificultad_final"].map(DIFICULTAD_CONTINUA_POR_TIER)


def _vectorizar_ejercicios(df: pd.DataFrame) -> np.ndarray:
    """Vector por ejercicio: one-hot de zona muscular + dificultad normalizada 0-1."""
    zonas_onehot = pd.get_dummies(df["zona_muscular"]).reindex(columns=ZONAS_MUSCULARES, fill_value=0)
    dificultad_norm = (_obtener_dificultad_continua(df) / 100.0).values.reshape(-1, 1)
    return np.hstack([zonas_onehot.values, dificultad_norm])


def _vector_ideal(objetivo: str, rango_dificultad: tuple) -> np.ndarray:
    perfil = PERFILES_OBJETIVO.get(objetivo, PERFILES_OBJETIVO["Salud general"])
    zonas_ideal = np.array([perfil["zonas_ideal"].get(z, 0.0) for z in ZONAS_MUSCULARES])
    lo, hi = rango_dificultad
    dificultad_ideal_norm = (lo + (hi - lo) * perfil["posicion_en_rango"]) / 100.0
    return np.concatenate([zonas_ideal, [dificultad_ideal_norm]])


N_RUTINAS_CONFIANZA_TOTAL = 15
PESO_EMPUJE_PROGRESION = 0.2


def calcular_metricas_historial(historial: list[dict] | None) -> dict:
    """historial: lo que regresa utils_db.obtener_historial_rutinas(). Con
    historial vacío/None, las métricas de dificultad son None (no 0 — 0
    significaría 'ya demostró que solo aguanta cosas facilísimas')."""
    if not historial:
        return {"dificultad_promedio_completada": None, "dificultad_maxima_completada": None, "n_rutinas_completadas": 0}

    # Filtra registros viejos que pudieran no tener dificultad guardada
    # (rutinas completadas ANTES de esta migración) — se ignoran, no rompen el cálculo.
    dificultades = [h["dificultad_promedio_rutina"] for h in historial if h.get("dificultad_promedio_rutina") is not None]
    if not dificultades:
        return {"dificultad_promedio_completada": None, "dificultad_maxima_completada": None, "n_rutinas_completadas": 0}

    return {
        "dificultad_promedio_completada": float(np.mean(dificultades)),
        "dificultad_maxima_completada": float(np.max(dificultades)),
        "n_rutinas_completadas": len(dificultades),
    }


def estimar_nivel_dinamico(nivel_cluster_nombre: str | None, historial: list[dict] | None) -> float:
    """Punto medio del rango del cluster si no hay historial; se va
    desplazando hacia el desempeño real conforme se acumulan rutinas
    completadas, con un pequeño empuje de progresión hacia arriba. Doble
    tope: nunca sale del rango del cluster, nunca pasa de 100."""
    rango = RANGO_DIFICULTAD_POR_CLUSTER.get(nivel_cluster_nombre, RANGO_DEFAULT_SIN_CLASIFICACION)
    nivel_base_cluster = (rango[0] + rango[1]) / 2

    metricas = calcular_metricas_historial(historial)
    n_completadas = metricas["n_rutinas_completadas"]

    if n_completadas == 0:
        nivel_estimado = nivel_base_cluster
    else:
        peso_historial = min(n_completadas / N_RUTINAS_CONFIANZA_TOTAL, 1.0)
        dificultad_promedio = metricas["dificultad_promedio_completada"]
        dificultad_maxima = metricas["dificultad_maxima_completada"]

        nivel_base_o_demostrado = (1 - peso_historial) * nivel_base_cluster + peso_historial * dificultad_promedio
        empuje_progresion = PESO_EMPUJE_PROGRESION * (dificultad_maxima - dificultad_promedio)
        nivel_estimado = nivel_base_o_demostrado + empuje_progresion

    nivel_estimado = max(rango[0], min(nivel_estimado, rango[1]))  # tope 1: rango del cluster
    return round(min(nivel_estimado, 100), 1)  # tope 2: regla dura absoluta


def generar_rutina(
    equipo_disponible: list[str],
    objetivo: str,
    nivel_cluster_nombre: str | None,
    historial: list[dict] | None = None,
    n_ejercicios: int = 7,
) -> dict:
    """
    Arma UNA rutina completa por similitud coseno entre cada ejercicio
    disponible y un vector "ideal" derivado del objetivo del usuario y su
    NIVEL DINÁMICO — que empieza en el punto medio del rango de su cluster
    y se ajusta con su historial real de rutinas completadas (pásale
    utils_db.obtener_historial_rutinas(usuario_id); None o [] para un
    usuario nuevo sin historial).

    Regla de negocio explícita: no se permiten dos ejercicios de la MISMA
    zona muscular consecutivos en la rutina final.
    """
    df = cargar_catalogo()
    disponibles = df[df["equipment"].isin(equipo_disponible)].copy()

    if disponibles.empty:
        return {"rutina_id": None, "ejercicios": [], "dificultad_promedio_rutina": None,
                "aviso": "No hay ejercicios disponibles con ese equipo."}

    rango = RANGO_DIFICULTAD_POR_CLUSTER.get(nivel_cluster_nombre, RANGO_DEFAULT_SIN_CLASIFICACION)
    nivel_dinamico = estimar_nivel_dinamico(nivel_cluster_nombre, historial)

    # El vector ideal ahora usa el NIVEL DINÁMICO en vez del punto medio fijo
    # del cluster — se calcula qué tan arriba/abajo del rango cae ese nivel,
    # y se usa esa misma posición relativa para ubicar la dificultad ideal.
    posicion_en_rango = (nivel_dinamico - rango[0]) / (rango[1] - rango[0]) if rango[1] != rango[0] else 0.5
    perfil_objetivo = dict(PERFILES_OBJETIVO.get(objetivo, PERFILES_OBJETIVO["Salud general"]))
    perfil_objetivo["posicion_en_rango"] = posicion_en_rango  # sobreescribe el default estático del objetivo

    vectores = _vectorizar_ejercicios(disponibles)
    zonas_ideal = np.array([perfil_objetivo["zonas_ideal"].get(z, 0.0) for z in ZONAS_MUSCULARES])
    dificultad_ideal_norm = nivel_dinamico / 100.0
    ideal = np.concatenate([zonas_ideal, [dificultad_ideal_norm]]).reshape(1, -1)

    similitudes = cosine_similarity(vectores, ideal).flatten()
    disponibles = disponibles.assign(similitud=similitudes).sort_values("similitud", ascending=False)

    seleccionados = []
    zona_anterior = None
    candidatos_restantes = disponibles.to_dict("records")

    while len(seleccionados) < n_ejercicios and candidatos_restantes:
        for i, candidato in enumerate(candidatos_restantes):
            if candidato["zona_muscular"] != zona_anterior:
                seleccionados.append(candidato)
                zona_anterior = candidato["zona_muscular"]
                candidatos_restantes.pop(i)
                break
        else:
            seleccionados.append(candidatos_restantes.pop(0))
            zona_anterior = seleccionados[-1]["zona_muscular"]

    reps_range = REPS_RANGE_POR_OBJETIVO.get(objetivo, (10, 15))
    rng = np.random.default_rng()

    ejercicios_final = []
    for ex in seleccionados:
        ejercicios_final.append({
            "id": ex["id"], "nombre": ex["name"], "zona_muscular": ex["zona_muscular"],
            "equipment": ex["equipment"], "dificultad_final": ex["dificultad_final"],
            "reps": int(rng.integers(reps_range[0], reps_range[1] + 1)),
            "gif_path": str(ruta_gif(pd.Series(ex))),
        })

    dificultad_promedio = float(_obtener_dificultad_continua(pd.DataFrame(seleccionados)).mean())

    firma = "-".join(sorted(ex["id"] for ex in seleccionados)) + objetivo + datetime.now().strftime("%Y%m%d%H%M%S")
    rutina_id = hashlib.sha1(firma.encode()).hexdigest()[:12]

    return {
        "rutina_id": rutina_id,
        "ejercicios": ejercicios_final,
        "dificultad_promedio_rutina": round(dificultad_promedio, 1),
        "objetivo": objetivo,
        "nivel_dinamico_usado": nivel_dinamico,
        "rango_dificultad_cluster": rango,
        "clasificacion_disponible": nivel_cluster_nombre is not None,
    }
