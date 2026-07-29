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
  - score_llm: dificultad continua 0-100, ÚNICA fuente de dificultad que usa
    este módulo. `dificultad_final` (la etiqueta principiante/intermedio/
    experto del catálogo) se ignora por completo: viene de un modelo
    anterior entrenado con pocos datos (score ~0.3) y sesgaba las
    recomendaciones. Los "tiers" que se muestran al usuario (ver
    `clasificar_tier`) se recalculan aquí mismo a partir de score_llm.
"""

from pathlib import Path

import pandas as pd
import streamlit as st

BASE_DIR = Path(__file__).resolve().parent
RUTA_CATALOGO = BASE_DIR / "Assets" / "exercises_catalog_spanish_version.parquet"
RUTA_GIFS = BASE_DIR / "Assets" / "ejercicios_media" / "videos"

EQUIPO_OPCIONES = [
    "peso corporal", "mancuerna", "barra", "barra ez", "barra olímpica",
    "barra hexagonal", "polea", "máquina de palanca", "máquina smith",
    "máquina de trineo", "máquina hammer", "máquina skierg", "kettlebell",
    "banda de resistencia", "balón de estabilidad", "balón medicinal",
    "balón bosu", "cuerda", "rodillo", "rueda abdominal", "llanta",
    "con peso (lastrado)", "asistido", "bicicleta estática", "elíptica",
    "escaladora", "ergómetro de tren superior",
]

# Mismos 27 items de EQUIPO_OPCIONES, agrupados para mostrarse como grilla
# de checkboxes (más fácil de navegar que un multiselect de una sola lista
# larga). Cualquier equipo nuevo que agregues a EQUIPO_OPCIONES también
# debe agregarse aquí en la categoría que le corresponda.
CATEGORIAS_EQUIPO = {
    "🧍 Cuerpo libre": ["peso corporal", "banda de resistencia", "rueda abdominal", "cuerda", "rodillo", "llanta"],
    "🏋️ Pesas libres": ["mancuerna", "barra", "barra ez", "barra olímpica", "barra hexagonal", "kettlebell", "con peso (lastrado)"],
    "⚙️ Máquinas": ["polea", "máquina de palanca", "máquina smith", "máquina de trineo", "máquina hammer", "máquina skierg", "asistido"],
    "🚴 Cardio y estabilidad": ["bicicleta estática", "elíptica", "escaladora", "ergómetro de tren superior", "balón de estabilidad", "balón bosu", "balón medicinal"],
}

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


# Límites derivados directamente de la distribución real de score_llm en tu
# catálogo (no de la etiqueta dificultad_final, que ya no se usa). Se
# ubicaron en los saltos naturales de la escala: la mayoría de los valores
# caen en bloques discretos (5, 8, 12, 18, 22, 24, 28, 38, 42, 45, 48, 52,
# 58, 62, 68, 72, 74, 78, 88, 90) — 30 y 50 separan esos bloques en tres
# grupos con sentido práctico (fácil / moderado / exigente).
LIMITE_SUPERIOR_POR_TIER = {"principiante": 30, "intermedio": 50, "experto": 100}


import re


def formatear_nombre_ejercicio(nombre: str) -> str:
    """Nombre listo para mostrar: sin el sufijo '(male)'/'(female)' del
    catálogo original (viene de cómo se etiquetó la fuente, no aporta nada
    al usuario) y con la primera letra en mayúscula."""
    limpio = re.sub(r"\s*\((male|female)\)\s*", "", nombre, flags=re.IGNORECASE).strip()
    if not limpio:
        return limpio
    return limpio[0].upper() + limpio[1:]


def clasificar_tier(score_llm: float) -> str:
    """Etiqueta legible (solo para mostrarla al usuario) a partir del
    score_llm continuo — reemplaza por completo a dificultad_final."""
    if score_llm <= LIMITE_SUPERIOR_POR_TIER["principiante"]:
        return "principiante"
    if score_llm <= LIMITE_SUPERIOR_POR_TIER["intermedio"]:
        return "intermedio"
    return "experto"


def filtrar_ejercicios(
    equipo_disponible: list[str],
    zona_muscular: str | None = None,
    dificultad_max: str | None = None,
) -> pd.DataFrame:
    """
    Filtra el catálogo por el equipo que el usuario tiene disponible (join
    simple porque equipment es un valor por fila, no una lista), y
    opcionalmente por zona muscular y tope de dificultad.

    Siempre agrega las columnas `dificultad_continua` (= score_llm) y
    `nivel` (etiqueta legible derivada de esa misma columna) al resultado,
    para que cualquier consumidor (el explorador de catálogo, el generador
    de rutinas) tenga disponible la misma información de dificultad sin
    tener que recalcularla por su cuenta.
    """
    df = cargar_catalogo().copy()

    if not equipo_disponible:
        return df.iloc[0:0]  # sin equipo seleccionado = sin resultados

    df = df[df["equipment"].isin(equipo_disponible)]

    if zona_muscular and zona_muscular != "Todas":
        df = df[df["zona_muscular"] == zona_muscular]

    df["dificultad_continua"] = _obtener_dificultad_continua(df)
    df["nivel"] = df["dificultad_continua"].map(clasificar_tier)
    df["nombre_formateado"] = df["name"].map(formatear_nombre_ejercicio)

    if dificultad_max:
        tope = LIMITE_SUPERIOR_POR_TIER[dificultad_max]
        df = df[df["dificultad_continua"] <= tope]

    return df


# ═══════════════════════════════════════════════════════════════════════════
# GENERADOR DE RUTINAS — similitud coseno entre ejercicios y perfil ideal
# ═══════════════════════════════════════════════════════════════════════════
import hashlib
from collections import Counter
from datetime import datetime

import numpy as np

# Rango de dificultad tolerable por cluster — mismo criterio ya usado en el
# clasificador. Si el usuario todavía no tiene clasificación (tabla vacía,
# como es el caso ahora mismo), se usa el default conservador.
#
# IMPORTANTE — el cluster es SOLO la referencia inicial, nunca un techo
# permanente: rango[1] es el punto de partida que usa obtener_techo_cluster()
# para calcular el techo real, pero ese techo se EXPANDE sin límite fijo
# (hasta TOPE_DIFICULTAD_ABSOLUTO = 100) conforme el usuario acumula
# feedback "fácil". Un usuario que arranca en el cluster más bajo puede
# llegar exactamente a los mismos ejercicios de máxima dificultad que
# cualquier otro — el cluster nunca deja a nadie estancado. Verificado:
# con suficiente progreso real (rutinas completadas + feedback), el techo
# llega a 100/100 sin importar el cluster de origen.
RANGO_DIFICULTAD_POR_CLUSTER = {
    "Rendimiento Atlético Alto": (25, 75),
    "Contextura Ligera, Fuerza Limitada": (5, 50),
    "Contextura Ligera, Buena Eficiencia": (10, 60),
    "Composición Corporal Elevada": (5, 40),
}
RANGO_DEFAULT_SIN_CLASIFICACION = (10, 45)

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

SERIES_POR_OBJETIVO = {
    "Bajar de peso": (2, 3), "Ganar músculo": (3, 4), "Ganar fuerza": (4, 5),
    "Mejorar resistencia/cardio": (2, 3), "Salud general": (3, 3),
}


def _obtener_dificultad_continua(df: pd.DataFrame) -> pd.Series:
    """
    Dificultad continua 0-100 de cada ejercicio: directamente `score_llm`.

    ANTES esta función combinaba score_llm con la etiqueta dificultad_final
    (tomando el máximo de ambas). Se quitó esa mezcla por completo:
    dificultad_final salía de un modelo entrenado con muy pocos datos
    (score de validación ~0.3) y estaba sesgando qué tan difícil parecía
    cada ejercicio. score_llm es la señal limpia — se usa sola, sin mezclar
    con nada más. Esto además hace el cálculo más liviano: una sola
    columna, sin `.map()` ni `np.maximum()`.
    """
    return df["score_llm"]


ALPHA_ZONA_VS_DIFICULTAD = 0.55  # 1.0 = ignora dificultad, 0.0 = ignora zona muscular


def _calcular_scores(df: pd.DataFrame, pesos_zonas: dict, dificultad_ideal_norm: float) -> pd.Series:
    """
    Score por ejercicio = mezcla de (a) qué tan relevante es su zona para el
    objetivo/balance actual, y (b) qué tan CERCA está su dificultad del
    nivel objetivo — no qué tan ALTA. Esto reemplaza a la similitud coseno
    de una versión anterior que tenía un problema real: al meter "zona" y
    "dificultad" en el mismo vector, el producto punto de la similitud
    coseno crece con la dificultad sin límite (nunca penaliza pasarse), así
    que terminaba recomendando siempre el ejercicio más difícil disponible
    en cada zona, sin importar el nivel objetivo. Aquí la distancia
    absoluta SÍ castiga tanto pasarse como quedarse corto.
    """
    score_zona = df["zona_muscular"].map(pesos_zonas).fillna(0.0)
    d_norm = df["dificultad_continua"] / 100.0
    ajuste_dificultad = 1.0 - (d_norm - dificultad_ideal_norm).abs()
    return ALPHA_ZONA_VS_DIFICULTAD * score_zona + (1 - ALPHA_ZONA_VS_DIFICULTAD) * ajuste_dificultad



# ---------------------------------------------------------------------------
# BALANCEO DE ZONAS MUSCULARES — corrige el "ideal" de solo-objetivo con lo
# que el usuario REALMENTE ha entrenado. Sin esto, alguien con objetivo
# "Ganar fuerza" que ya hizo 5 rutinas de empuje/tracción seguiría recibiendo
# más empuje/tracción, aunque tenga el core totalmente abandonado.
# ---------------------------------------------------------------------------
PESO_BALANCE_ZONAS_DEFAULT = 0.35  # 0 = ignora el balance, 1 = ignora el objetivo


def _pesos_zonas_balanceados(
    objetivo: str, frecuencia_zonas: dict | None, peso_balance: float = PESO_BALANCE_ZONAS_DEFAULT
) -> dict:
    """
    Mezcla los pesos de zona del objetivo declarado con un "déficit de
    entrenamiento": zonas que el usuario ha trabajado menos de lo que le
    tocaría (en proporción pareja) reciben más peso; zonas sobre-trabajadas
    reciben menos. El objetivo sigue mandando (peso_balance bajo por
    default) — el balance es un empujón, no un reemplazo.
    """
    perfil = PERFILES_OBJETIVO.get(objetivo, PERFILES_OBJETIVO["Salud general"])
    pesos_objetivo = {z: perfil["zonas_ideal"].get(z, 0.0) for z in ZONAS_MUSCULARES}

    total_entrenado = sum((frecuencia_zonas or {}).values())
    if total_entrenado == 0:
        return pesos_objetivo  # sin historial todavía, no hay nada que balancear

    proporcion_justa = 1.0 / len(ZONAS_MUSCULARES)
    deficit = {
        z: max(0.0, proporcion_justa - (frecuencia_zonas.get(z, 0) / total_entrenado))
        for z in ZONAS_MUSCULARES
    }
    suma_deficit = sum(deficit.values())
    deficit_normalizado = (
        {z: v / suma_deficit for z, v in deficit.items()} if suma_deficit > 0
        else {z: proporcion_justa for z in ZONAS_MUSCULARES}
    )

    pesos_finales = {
        z: (1 - peso_balance) * pesos_objetivo[z] + peso_balance * deficit_normalizado[z]
        for z in ZONAS_MUSCULARES
    }
    suma_final = sum(pesos_finales.values())
    return {z: v / suma_final for z, v in pesos_finales.items()} if suma_final > 0 else pesos_objetivo


N_RUTINAS_CONFIANZA_TOTAL = 15

# ---------------------------------------------------------------------------
# TOPE DE DIFICULTAD PROGRESIVO — "asumir que son principiantes hasta que
# demuestren lo contrario". Nadie empieza viendo ejercicios de más de 70/100,
# sin importar lo que diga su cluster; el tope sube poco a poco según
# rutinas completadas REALES, no según una sola clasificación de día uno.
# ---------------------------------------------------------------------------
TOPE_DIFICULTAD_INICIAL = 50.0
INCREMENTO_TOPE_POR_RUTINA = 3.0
TOPE_DIFICULTAD_ABSOLUTO = 100.0


def calcular_tope_dificultad(nivel_cluster_nombre: str | None, historial: list[dict] | None) -> float:
    techo = obtener_techo_cluster(nivel_cluster_nombre, historial)
    n_completadas = calcular_metricas_historial(historial)["n_rutinas_completadas"]
    tope = TOPE_DIFICULTAD_INICIAL + INCREMENTO_TOPE_POR_RUTINA * n_completadas
    return min(max(tope, TOPE_DIFICULTAD_INICIAL), techo, TOPE_DIFICULTAD_ABSOLUTO)


# ---------------------------------------------------------------------------
# AJUSTE DE DIFICULTAD POR FEEDBACK — mismo proceso para ambos sentidos,
# inmediato por cada rutina (acumulado histórico, no agrupado):
#   +1 punto por cada rutina marcada "fácil".
#   -2 puntos por cada rutina marcada "difícil".
#   "bien" no mueve nada.
# La asimetría vive solo en la magnitud (subir de a poco, bajar más rápido),
# no en el mecanismo — los dos aplican de inmediato, uno por uno.
# ---------------------------------------------------------------------------
PUNTOS_POR_FACIL = 1.0
PUNTOS_POR_DIFICIL = 2.0


def calcular_ajuste_dificultad(historial: list[dict] | None) -> float:
    if not historial:
        return 0.0
    n_facil = sum(1 for h in historial if h.get("feedback_dificultad") == "facil")
    n_dificil = sum(1 for h in historial if h.get("feedback_dificultad") == "dificil")
    return (n_facil * PUNTOS_POR_FACIL) - (n_dificil * PUNTOS_POR_DIFICIL)


def obtener_techo_cluster(nivel_cluster_nombre: str | None, historial: list[dict] | None) -> float:
    """El límite superior 'real' a usar en vez de RANGO_DIFICULTAD_POR_CLUSTER[...][1]
    directo — el rango del cluster es el punto de partida, pero el ajuste
    por feedback (si es positivo) puede expandirlo más allá."""
    rango = RANGO_DIFICULTAD_POR_CLUSTER.get(nivel_cluster_nombre, RANGO_DEFAULT_SIN_CLASIFICACION)
    expansion = max(calcular_ajuste_dificultad(historial), 0.0)
    return min(rango[1] + expansion, TOPE_DIFICULTAD_ABSOLUTO)


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
    """Punto medio del rango del cluster, desplazado por el ajuste
    asimétrico de feedback (ver calcular_ajuste_dificultad). El techo
    superior YA NO es fijo — se expande cuando el ajuste es positivo."""
    rango = RANGO_DIFICULTAD_POR_CLUSTER.get(nivel_cluster_nombre, RANGO_DEFAULT_SIN_CLASIFICACION)
    techo = obtener_techo_cluster(nivel_cluster_nombre, historial)
    nivel_base_cluster = (rango[0] + rango[1]) / 2

    nivel_estimado = nivel_base_cluster + calcular_ajuste_dificultad(historial)

    nivel_estimado = max(rango[0], min(nivel_estimado, techo))  # tope 1: techo expandible del cluster
    return round(min(nivel_estimado, 100), 1)  # tope 2: regla dura absoluta


def _generar_variante(
    equipo_disponible: list[str],
    objetivo: str,
    nivel_cluster_nombre: str | None,
    historial: list[dict] | None = None,
    n_ejercicios: int = 8,
    desplazamiento_dificultad: float = 0.0,
    peso_balance: float = PESO_BALANCE_ZONAS_DEFAULT,
    frecuencia_zonas: dict | None = None,
    etiqueta: str = "Recomendada",
    excluir_ids: set | None = None,
    zonas_forzadas: dict | None = None,
) -> dict:
    """
    Núcleo del generador. `desplazamiento_dificultad` mueve el nivel
    dinámico hacia arriba/abajo (dentro del rango del cluster Y del tope
    progresivo) para producir variantes fácil/recomendada/reto SIN tener
    que reentrenar nada — es el mismo motor de similitud coseno, solo
    apuntando a un punto distinto de dificultad. `peso_balance` alto ignora
    casi todo el objetivo y prioriza llenar las zonas musculares que el
    usuario tiene descuidadas. `zonas_forzadas` (si se da) IGNORA el
    objetivo y el balance por completo — se usa para las rutinas "por
    grupo muscular" (día de empuje, de piernas, etc.), donde se quiere
    entrenar SOLO esa zona, no una mezcla.

    IMPORTANTE: el tope de dificultad (calcular_tope_dificultad) es un
    FILTRO DURO sobre los ejercicios candidatos — eso nunca se negocia.
    `excluir_ids` (rotación), en cambio, es una PENALIZACIÓN SUAVE al score,
    no un filtro: encontrar la dificultad correcta pesa más que variar los
    ejercicios. Si el ejercicio recién usado sigue siendo, por mucho, el
    que mejor encaja con el nivel objetivo, se puede repetir — la rotación
    solo desempata entre opciones parecidas.
    """
    df = cargar_catalogo()
    disponibles = df[df["equipment"].isin(equipo_disponible)].copy()
    if zonas_forzadas:
        disponibles = disponibles[disponibles["zona_muscular"].isin(zonas_forzadas.keys())]

    if disponibles.empty:
        return {"rutina_id": None, "etiqueta": etiqueta, "ejercicios": [],
                "dificultad_promedio_rutina": None, "similitud_promedio": 0.0,
                "aviso": "No hay ejercicios disponibles con ese equipo."}

    rango = RANGO_DIFICULTAD_POR_CLUSTER.get(nivel_cluster_nombre, RANGO_DEFAULT_SIN_CLASIFICACION)
    tope_dificultad = calcular_tope_dificultad(nivel_cluster_nombre, historial)

    disponibles["dificultad_continua"] = _obtener_dificultad_continua(disponibles)
    disponibles = disponibles[disponibles["dificultad_continua"] <= tope_dificultad]

    if disponibles.empty:
        return {"rutina_id": None, "etiqueta": etiqueta, "ejercicios": [],
                "dificultad_promedio_rutina": None, "similitud_promedio": 0.0,
                "aviso": "No hay ejercicios lo bastante accesibles todavía con ese equipo."}

    nivel_dinamico_base = estimar_nivel_dinamico(nivel_cluster_nombre, historial)
    # OJO: el límite superior aquí es tope_dificultad, NO rango[1] — rango[1]
    # es el techo SIN expandir; recortar contra él cancelaba el ajuste por
    # feedback en cuanto se aplicaba un desplazamiento_dificultad != 0.
    nivel_dinamico = max(rango[0], nivel_dinamico_base + desplazamiento_dificultad)
    nivel_dinamico = min(nivel_dinamico, tope_dificultad)

    pesos_zonas = zonas_forzadas if zonas_forzadas else _pesos_zonas_balanceados(objetivo, frecuencia_zonas, peso_balance)
    dificultad_ideal_norm = nivel_dinamico / 100.0

    disponibles = disponibles.assign(
        similitud=_calcular_scores(disponibles, pesos_zonas, dificultad_ideal_norm)
    )
    if excluir_ids:
        disponibles.loc[disponibles["id"].isin(excluir_ids), "similitud"] -= PENALIZACION_ROTACION
    disponibles = disponibles.sort_values("similitud", ascending=False)

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
    series_range = SERIES_POR_OBJETIVO.get(objetivo, (3, 3))
    rng = np.random.default_rng()

    ejercicios_final = []
    for ex in seleccionados:
        ejercicios_final.append({
            "id": ex["id"], "nombre": formatear_nombre_ejercicio(ex["name"]), "zona_muscular": ex["zona_muscular"],
            "equipment": ex["equipment"],
            "score_llm": ex["score_llm"], "nivel": clasificar_tier(ex["score_llm"]),
            "n_secondary": ex.get("n_secondary"), "dificultad_continua": round(float(ex["dificultad_continua"]), 1),
            "series": int(rng.integers(series_range[0], series_range[1] + 1)),
            "reps": int(rng.integers(reps_range[0], reps_range[1] + 1)),
            "gif_path": str(ruta_gif(pd.Series(ex))),
            "similitud": round(float(ex["similitud"]), 3),
        })

    dificultad_promedio = float(np.mean([ex["dificultad_continua"] for ex in ejercicios_final]))
    similitud_promedio = float(np.mean([ex["similitud"] for ex in ejercicios_final]))
    zonas_contadas = dict(Counter(ex["zona_muscular"] for ex in ejercicios_final))

    firma = (
        "-".join(sorted(ex["id"] for ex in seleccionados)) + objetivo + etiqueta
        + datetime.now().strftime("%Y%m%d%H%M%S%f")
    )
    rutina_id = hashlib.sha1(firma.encode()).hexdigest()[:12]

    return {
        "rutina_id": rutina_id,
        "etiqueta": etiqueta,
        "ejercicios": ejercicios_final,
        "zonas_contadas": zonas_contadas,
        "dificultad_promedio_rutina": round(dificultad_promedio, 1),
        "similitud_promedio": round(similitud_promedio, 3),
        "objetivo": objetivo,
        "nivel_dinamico_usado": round(nivel_dinamico, 1),
        "tope_dificultad_usado": round(tope_dificultad, 1),
        "rango_dificultad_cluster": rango,
        "clasificacion_disponible": nivel_cluster_nombre is not None,
    }


def generar_rutina(
    equipo_disponible: list[str],
    objetivo: str,
    nivel_cluster_nombre: str | None,
    historial: list[dict] | None = None,
    n_ejercicios: int = 8,
) -> dict:
    """Compatibilidad hacia atrás: una sola rutina 'recomendada', sin
    variantes ni balance de zonas explícito (usa el default). Para el menú
    completo usa generar_menu_rutinas()."""
    return _generar_variante(
        equipo_disponible, objetivo, nivel_cluster_nombre, historial, n_ejercicios=n_ejercicios,
    )


# ---------------------------------------------------------------------------
# MENÚ DE RUTINAS — muchas variantes listas para elegir, no una sola.
# Cubre una escalera de dificultad completa (no solo 3 escalones) más dos
# variantes temáticas (equilibrio muscular puro, y objetivo puro sin
# balance). El tope de dificultad progresivo (calcular_tope_dificultad)
# sigue aplicando sobre TODAS — si el usuario es nuevo, incluso "Reto alto"
# queda recortado a 70/100 automáticamente.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# ROTACIÓN DE EJERCICIOS — preferencia suave, NO un filtro duro. Es
# secundaria frente a encontrar la dificultad correcta: si el ejercicio
# recién usado sigue siendo, con mucho, el que mejor encaja con el nivel
# objetivo, se puede repetir. Se excluyen (con penalización, no filtro) los
# ejercicios de las últimas N_RUTINAS_EXCLUSION_ROTACION rutinas COMPLETADAS
# (por cantidad de rutinas, nunca por fecha/día).
# ---------------------------------------------------------------------------
N_RUTINAS_EXCLUSION_ROTACION = 2
PENALIZACION_ROTACION = 0.08  # pequeño castigo al score, no una eliminación


def obtener_ids_recientes(historial: list[dict] | None, n_rutinas: int = N_RUTINAS_EXCLUSION_ROTACION) -> set:
    """IDs de ejercicios principales usados en las últimas n_rutinas
    completadas (el historial ya viene ordenado del más reciente al más
    viejo). Se usan como `excluir_ids` para preferir variedad, sin que eso
    le gane nunca a encontrar la dificultad correcta."""
    ids = set()
    for h in (historial or [])[:n_rutinas]:
        ids.update(h.get("ejercicios_ids", []))
    return ids


POSICIONES_MENU = [
    # (etiqueta, posicion, peso_balance)
    # posicion en [-1, 1]: -1 = toca el piso del cluster exactamente,
    # 0 = el nivel dinámico actual (estimar_nivel_dinamico), +1 = toca el
    # techo actual exactamente (tope_dificultad, que ya incluye la
    # expansión por feedback). Al ser PROPORCIONAL a la distancia
    # disponible en cada extremo, ningún escalón puede "colapsarse" contra
    # otro cuando el techo sube — siempre se re-estira para cubrirlo.
    ("🟢 Día de campo (muy fácil)", -1.0, PESO_BALANCE_ZONAS_DEFAULT),
    ("🟢 Dia suave y controlado (fácil)", -0.6, PESO_BALANCE_ZONAS_DEFAULT),
    ("🟡 Dia de rutina (moderada)", -0.3, PESO_BALANCE_ZONAS_DEFAULT),
    ("🟡 Recomendada para ti (moderada)", 0.0, PESO_BALANCE_ZONAS_DEFAULT),
    ("🟠 Desafio Moderado (dificil)", 0.35, PESO_BALANCE_ZONAS_DEFAULT),
    ("🔴 Desafio Alto (brutal)", 0.7, PESO_BALANCE_ZONAS_DEFAULT),
    ("🔴 Desafio Brutal (brutal)", 1.0, PESO_BALANCE_ZONAS_DEFAULT),
    ("⚖️ Perfectamente Equilibrado (moderada)", 0.0, 0.85),
    ("🎯 Objetivo Puro (moderada)", 0.0, 0.05),
]


def generar_menu_rutinas(
    equipo_disponible: list[str],
    objetivo: str,
    nivel_cluster_nombre: str | None,
    historial: list[dict] | None = None,
    frecuencia_zonas: dict | None = None,
    n_ejercicios: int = 8,
) -> list[dict]:
    """
    Genera varias rutinas candidatas de una vez (toda una escalera de
    dificultad + variantes temáticas) usando el MISMO motor de similitud
    coseno con distintos parámetros, y las ordena por qué tan bien encajó
    cada una con su propio criterio (similitud_promedio) — así el orden es
    el "orden de recomendación" real, no un orden fijo. Excluye los
    ejercicios de tus últimas rutinas completadas (ver
    N_RUTINAS_EXCLUSION_ROTACION) para garantizar variedad real entre
    rutinas, no solo dentro de la misma rutina.

    La escalera de dificultad se calcula PROPORCIONAL al piso/techo
    disponibles en este momento (ver POSICIONES_MENU) — así "Reto alto"
    siempre toca el techo real y "Muy fácil" siempre toca el piso real,
    sin importar cuánto haya crecido el techo por feedback acumulado.
    """
    excluir_ids = obtener_ids_recientes(historial)

    rango = RANGO_DIFICULTAD_POR_CLUSTER.get(nivel_cluster_nombre, RANGO_DEFAULT_SIN_CLASIFICACION)
    nivel_base = estimar_nivel_dinamico(nivel_cluster_nombre, historial)
    techo = calcular_tope_dificultad(nivel_cluster_nombre, historial)
    piso = rango[0]

    variantes = []
    for etiqueta, posicion, peso_balance in POSICIONES_MENU:
        if posicion <= 0:
            desplazamiento = posicion * (nivel_base - piso)
        else:
            desplazamiento = posicion * (techo - nivel_base)

        variante = _generar_variante(
            equipo_disponible, objetivo, nivel_cluster_nombre, historial,
            n_ejercicios=n_ejercicios,
            desplazamiento_dificultad=desplazamiento,
            peso_balance=peso_balance,
            frecuencia_zonas=frecuencia_zonas,
            etiqueta=etiqueta,
            excluir_ids=excluir_ids,
        )
        if variante["ejercicios"]:
            variantes.append(variante)

    variantes.sort(key=lambda v: v["similitud_promedio"], reverse=True)
    return variantes


# ---------------------------------------------------------------------------
# RUTINAS POR GRUPO MUSCULAR ("split") — estructura de entrenamiento
# estándar (día de empuje / tracción / pierna / core / cardio), no un
# programa de ningún autor en particular. Se llena con TU catálogo, no con
# contenido bajado de internet.
# ---------------------------------------------------------------------------
DIAS_POR_GRUPO_MUSCULAR = {
    "Empuje superior": "💪 Empuje de Poder",
    "Tracción superior": "🎣 Tracción de Dragón",
    "Tren inferior": "🦵 Piernas de Fuego",
    "Core": "🔥 Core de Acero",
    "Cardio": "🏃 Cardio de Campeón",
}


def generar_rutina_por_grupo(
    equipo_disponible: list[str],
    zona: str,
    nivel_cluster_nombre: str | None,
    historial: list[dict] | None = None,
    n_ejercicios: int = 6,
) -> dict:
    """Una rutina enfocada 100% en una sola zona muscular — un 'día' de
    split, en vez de cuerpo completo."""
    etiqueta = DIAS_POR_GRUPO_MUSCULAR.get(zona, zona)
    return _generar_variante(
        equipo_disponible, objetivo="Salud general", nivel_cluster_nombre=nivel_cluster_nombre,
        historial=historial, n_ejercicios=n_ejercicios, etiqueta=etiqueta,
        zonas_forzadas={zona: 1.0}, excluir_ids=obtener_ids_recientes(historial),
    )


def generar_menu_por_grupos(
    equipo_disponible: list[str],
    nivel_cluster_nombre: str | None,
    historial: list[dict] | None = None,
    n_ejercicios: int = 6,
) -> list[dict]:
    """Una rutina por cada grupo muscular disponible con tu equipo actual —
    para armar tu propio split (ej. empuje lunes, tracción miércoles,
    pierna viernes) en vez de siempre cuerpo completo."""
    rutinas = []
    for zona in DIAS_POR_GRUPO_MUSCULAR:
        rutina = generar_rutina_por_grupo(equipo_disponible, zona, nivel_cluster_nombre, historial, n_ejercicios)
        if rutina["ejercicios"]:
            rutinas.append(rutina)
    return rutinas


def generar_calentamiento(
    equipo_disponible: list[str], zonas_objetivo: list[str], n_ejercicios: int = 5,
    tope_dificultad_calentamiento: float = 35.0,
) -> list[dict]:
    """
    Ejercicios GENUINAMENTE ligeros (score_llm bajo) de las mismas zonas
    que trabajará la rutina principal, para precalentar antes de exigir
    de verdad.
    """
    df = cargar_catalogo().copy()
    df["dificultad_continua"] = _obtener_dificultad_continua(df)

    candidatos = df[
        df["equipment"].isin(equipo_disponible)
        & df["zona_muscular"].isin(zonas_objetivo)
        & (df["dificultad_continua"] <= tope_dificultad_calentamiento)
    ]
    if candidatos.empty:
        candidatos = df[
            df["equipment"].isin(equipo_disponible)
            & (df["dificultad_continua"] <= tope_dificultad_calentamiento)
        ]
    if candidatos.empty:
        return []

    muestra = candidatos.sample(n=min(n_ejercicios, len(candidatos)))
    calentamiento = []
    for _, ex in muestra.iterrows():
        calentamiento.append({
            "id": ex["id"], "nombre": formatear_nombre_ejercicio(ex["name"]), "zona_muscular": ex["zona_muscular"],
            "equipment": ex["equipment"],
            "score_llm": ex["score_llm"], "nivel": clasificar_tier(ex["score_llm"]),
            "n_secondary": ex.get("n_secondary"), "dificultad_continua": round(float(ex["dificultad_continua"]), 1),
            "series": 2,
            "reps": 12, "gif_path": str(ruta_gif(ex)),
        })
    return calentamiento


def obtener_ejercicio_por_id(ejercicio_id: str) -> dict | None:
    """Reconstruye el dict completo de un ejercicio a partir de su id — lo
    usa la rutina personalizada, que solo guarda id + series + reps."""
    df = cargar_catalogo().copy()
    df["dificultad_continua"] = _obtener_dificultad_continua(df)
    fila = df[df["id"] == ejercicio_id]
    if fila.empty:
        return None
    ex = fila.iloc[0]
    return {
        "id": ex["id"], "nombre": formatear_nombre_ejercicio(ex["name"]), "zona_muscular": ex["zona_muscular"],
        "equipment": ex["equipment"],
        "score_llm": ex["score_llm"], "nivel": clasificar_tier(ex["score_llm"]),
        "n_secondary": ex.get("n_secondary"), "dificultad_continua": round(float(ex["dificultad_continua"]), 1),
        "gif_path": str(ruta_gif(ex)),
    }


def formatear_features_ejercicio(ejercicio: dict) -> str:
    """Texto corto con las características NUMÉRICAS del ejercicio — para
    poder verificar a simple vista que el catálogo está bien etiquetado.
    'nivel' se deriva de score_llm (ver clasificar_tier), no de la vieja
    dificultad_final."""
    partes = [f"Nivel: {ejercicio.get('nivel', '—')}"]
    if ejercicio.get("score_llm") is not None:
        partes.append(f"score {ejercicio['score_llm']}/100")
    if ejercicio.get("n_secondary") is not None:
        partes.append(f"{ejercicio['n_secondary']} músculo(s) secundario(s)")
    if ejercicio.get("similitud") is not None:
        partes.append(f"match {ejercicio['similitud']:.2f}")
    return " · ".join(partes)
