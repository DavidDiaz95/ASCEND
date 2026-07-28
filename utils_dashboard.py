"""
utils_dashboard.py — Agregación de datos para "Mi Progreso"
--------------------------------------------------------------------------------
Este módulo NO calcula nada nuevo del motor de recomendación — solo toma lo
que ya se guarda en interacciones_rutinas / interacciones_nutricion y lo
convierte en series/resúmenes listos para graficar. Mantiene 04_Dashboard.py
enfocado en la presentación (Plotly + Streamlit), no en la lógica de datos.
"""

from collections import Counter
from datetime import datetime

import pandas as pd

from utils_rutinas import ZONAS_MUSCULARES, OBJETIVOS, obtener_ejercicio_por_id
from utils_nutricion import calcular_objetivo_nutricional


# ---------------------------------------------------------------------------
# 1. XP ACUMULADO POR FUENTE (rutinas vs. nutrición) — para el área apilada
# ---------------------------------------------------------------------------
def calcular_serie_xp_acumulado(historial_rutinas: list[dict], historial_nutricion: list[dict]) -> pd.DataFrame:
    """
    Regresa un DataFrame con una fila por fecha (orden cronológico) y las
    columnas xp_rutinas_acumulado / xp_nutricion_acumulado — listo para un
    área apilada que muestre de dónde viene el progreso.
    """
    eventos = []
    for h in historial_rutinas:
        fecha = h["completado_en"][:10]  # 'YYYY-MM-DD HH:MM:SS' -> solo la fecha
        eventos.append({"fecha": fecha, "fuente": "rutinas", "xp": h["xp_ganado"] or 0})
    for h in historial_nutricion:
        fecha = h["registrado_en"][:10]
        eventos.append({"fecha": fecha, "fuente": "nutricion", "xp": h["xp_ganado"] or 0})

    if not eventos:
        return pd.DataFrame(columns=["fecha", "xp_rutinas_acumulado", "xp_nutricion_acumulado"])

    df = pd.DataFrame(eventos)
    diario = df.groupby(["fecha", "fuente"])["xp"].sum().unstack(fill_value=0)
    diario = diario.reindex(columns=["rutinas", "nutricion"], fill_value=0).sort_index()

    resultado = pd.DataFrame({
        "fecha": diario.index,
        "xp_rutinas_acumulado": diario["rutinas"].cumsum(),
        "xp_nutricion_acumulado": diario["nutricion"].cumsum(),
    }).reset_index(drop=True)
    return resultado


# ---------------------------------------------------------------------------
# 2. BALANCE MUSCULAR — para el radar de zonas entrenadas
# ---------------------------------------------------------------------------
def calcular_balance_muscular(historial_rutinas: list[dict]) -> dict:
    """Suma zonas_json de todas las rutinas completadas — cuántos
    ejercicios de cada zona ha hecho el usuario en total."""
    conteo = Counter({zona: 0 for zona in ZONAS_MUSCULARES})
    for h in historial_rutinas:
        conteo.update(h.get("zonas_json", {}))
    return dict(conteo)


# ---------------------------------------------------------------------------
# 3. TIPOS DE RUTINA (objetivo) MÁS ENTRENADOS
# ---------------------------------------------------------------------------
def calcular_distribucion_objetivos(historial_rutinas: list[dict]) -> dict:
    conteo = Counter({objetivo: 0 for objetivo in OBJETIVOS})
    for h in historial_rutinas:
        objetivo = h.get("objetivo")
        if objetivo in conteo:
            conteo[objetivo] += 1
    return dict(conteo)


# ---------------------------------------------------------------------------
# 4. BALANCE NUTRICIONAL — promedio por comida vs. meta por comida (%)
# ---------------------------------------------------------------------------
def calcular_balance_nutricional(historial_nutricion: list[dict], perfil: dict | None) -> dict | None:
    """Regresa, para calorías/proteína/grasa/carbohidratos, qué porcentaje
    representa el promedio real por comida contra la meta por comida
    (dividiendo la meta diaria entre 3). 100% = comiendo justo la meta."""
    if not historial_nutricion or not perfil:
        return None

    calorias = [h["detalle"].get("calorias") for h in historial_nutricion if h["detalle"].get("calorias")]
    proteina = [h["detalle"].get("proteina_g") for h in historial_nutricion if h["detalle"].get("proteina_g")]
    grasa = [h["detalle"].get("grasa_g") for h in historial_nutricion if h["detalle"].get("grasa_g")]
    carbs = [h["detalle"].get("carbohidratos_g") for h in historial_nutricion if h["detalle"].get("carbohidratos_g")]

    if not calorias:
        return None

    metas = calcular_objetivo_nutricional(perfil)
    meta_por_comida = {
        "Calorías": metas["calorias"] / 3, "Proteína": metas["proteina_g"] / 3,
        "Grasa": metas["grasa_g"] / 3, "Carbohidratos": metas["carbohidratos_g"] / 3,
    }
    promedio_real = {
        "Calorías": sum(calorias) / len(calorias) if calorias else 0,
        "Proteína": sum(proteina) / len(proteina) if proteina else 0,
        "Grasa": sum(grasa) / len(grasa) if grasa else 0,
        "Carbohidratos": sum(carbs) / len(carbs) if carbs else 0,
    }
    return {
        clave: round((promedio_real[clave] / meta_por_comida[clave]) * 100) if meta_por_comida[clave] else 0
        for clave in meta_por_comida
    }


# ---------------------------------------------------------------------------
# 5. EJERCICIO FAVORITO — el más repetido; empate -> mayor dificultad;
# empate otra vez -> orden alfabético.
# ---------------------------------------------------------------------------
def obtener_ejercicio_favorito(historial_rutinas: list[dict]) -> dict | None:
    conteo_ids = Counter()
    for h in historial_rutinas:
        conteo_ids.update(h.get("ejercicios_ids", []))

    if not conteo_ids:
        return None

    maximo = max(conteo_ids.values())
    candidatos_ids = [eid for eid, n in conteo_ids.items() if n == maximo]

    candidatos = []
    for eid in candidatos_ids:
        info = obtener_ejercicio_por_id(eid)
        if info:
            candidatos.append({
                "id": eid, "nombre": info["nombre"], "dificultad": info["dificultad_continua"],
                "veces": maximo,
            })

    if not candidatos:
        return None

    # Desempate: mayor dificultad primero, luego orden alfabético del nombre.
    candidatos.sort(key=lambda c: (-c["dificultad"], c["nombre"]))
    return candidatos[0]


# ---------------------------------------------------------------------------
# 6. EVOLUCIÓN DE LA DIFICULTAD — una fila por rutina completada, en orden
# cronológico (el historial viene más-reciente-primero; aquí se invierte).
# ---------------------------------------------------------------------------
def calcular_evolucion_dificultad(historial_rutinas: list[dict]) -> pd.DataFrame:
    filas = [
        {"indice": i + 1, "fecha": h["completado_en"], "dificultad": h["dificultad_promedio_rutina"]}
        for i, h in enumerate(reversed(historial_rutinas))
        if h.get("dificultad_promedio_rutina") is not None
    ]
    return pd.DataFrame(filas)
