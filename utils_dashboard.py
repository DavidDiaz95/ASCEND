"""
utils_dashboard.py — Agregación de datos para "Mi Progreso"
--------------------------------------------------------------------------------
Este módulo NO calcula nada nuevo del motor de recomendación — solo toma lo
que ya se guarda en interacciones_rutinas / interacciones_nutricion y lo
convierte en series/resúmenes listos para graficar. Mantiene 04_Dashboard.py
enfocado en la presentación (Plotly + Streamlit), no en la lógica de datos.
"""

from collections import Counter

import pandas as pd

from utils_rutinas import ZONAS_MUSCULARES, OBJETIVOS, obtener_ejercicio_por_id
from utils_nutricion import calcular_objetivo_nutricional

# ---------------------------------------------------------------------------
# RANGO TEMPORAL — mismo selector para todo el dashboard (estilo Power BI):
# filtra qué datos se usan, y decide la granularidad de agrupación de las
# gráficas de línea/barras (día para rangos cortos, mes para rangos largos).
# ---------------------------------------------------------------------------
OPCIONES_RANGO = ["Última semana", "Último mes", "Último año", "Histórico completo"]
DIAS_POR_RANGO = {"Última semana": 7, "Último mes": 30, "Último año": 365, "Histórico completo": None}


def filtrar_por_rango(historial: list[dict], campo_fecha: str, rango: str) -> list[dict]:
    dias = DIAS_POR_RANGO.get(rango)
    if dias is None:
        return historial
    limite = pd.Timestamp.now() - pd.Timedelta(days=dias)
    return [h for h in historial if pd.to_datetime(h[campo_fecha]) >= limite]


def granularidad_por_rango(rango: str) -> str:
    """'dia' para rangos cortos (se puede leer un punto por día); 'mes'
    para rangos largos (un año de puntos diarios sería ilegible)."""
    return "dia" if rango in ("Última semana", "Último mes") else "mes"


# ---------------------------------------------------------------------------
# 1. XP ACUMULADO POR FUENTE (rutinas vs. nutrición) — para el área apilada
# ---------------------------------------------------------------------------
def calcular_serie_xp_acumulado(historial_rutinas: list[dict], historial_nutricion: list[dict],
                                 granularidad: str = "dia") -> pd.DataFrame:
    """
    Regresa un DataFrame con una fila por periodo (día o mes, orden
    cronológico) y las columnas xp_rutinas_acumulado / xp_nutricion_acumulado
    — listo para un área apilada que muestre de dónde viene el progreso.
    """
    largo = 10 if granularidad == "dia" else 7  # 'YYYY-MM-DD' vs 'YYYY-MM'

    eventos = []
    for h in historial_rutinas:
        eventos.append({"periodo": h["completado_en"][:largo], "fuente": "rutinas", "xp": h["xp_ganado"] or 0})
    for h in historial_nutricion:
        eventos.append({"periodo": h["registrado_en"][:largo], "fuente": "nutricion", "xp": h["xp_ganado"] or 0})

    if not eventos:
        return pd.DataFrame(columns=["periodo", "xp_rutinas_acumulado", "xp_nutricion_acumulado"])

    df = pd.DataFrame(eventos)
    agrupado = df.groupby(["periodo", "fuente"])["xp"].sum().unstack(fill_value=0)
    agrupado = agrupado.reindex(columns=["rutinas", "nutricion"], fill_value=0).sort_index()

    resultado = pd.DataFrame({
        "periodo": agrupado.index,
        "xp_rutinas_acumulado": agrupado["rutinas"].cumsum(),
        "xp_nutricion_acumulado": agrupado["nutricion"].cumsum(),
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

    candidatos.sort(key=lambda c: (-c["dificultad"], c["nombre"]))
    return candidatos[0]


# ---------------------------------------------------------------------------
# 6. EVOLUCIÓN DE LA DIFICULTAD — promedio por día/mes (no por rutina
# individual), para que el eje sea de tiempo real, consistente con las
# demás gráficas.
# ---------------------------------------------------------------------------
def calcular_evolucion_dificultad(historial_rutinas: list[dict], granularidad: str = "dia") -> pd.DataFrame:
    largo = 10 if granularidad == "dia" else 7
    filas = [
        {"periodo": h["completado_en"][:largo], "dificultad": h["dificultad_promedio_rutina"]}
        for h in historial_rutinas if h.get("dificultad_promedio_rutina") is not None
    ]
    if not filas:
        return pd.DataFrame(columns=["periodo", "dificultad"])
    df = pd.DataFrame(filas)
    return df.groupby("periodo")["dificultad"].mean().reset_index().sort_values("periodo")


# ---------------------------------------------------------------------------
# 7. MINUTOS ENTRENADOS POR DÍA/MES — dato que ya se guarda (duracion_segundos)
# desde hace varias iteraciones, pero nunca se había mostrado en ningún lado.
# ---------------------------------------------------------------------------
def calcular_minutos_entrenados(historial_rutinas: list[dict], granularidad: str = "dia") -> pd.DataFrame:
    largo = 10 if granularidad == "dia" else 7
    filas = [
        {"periodo": h["completado_en"][:largo], "minutos": h["duracion_segundos"] / 60}
        for h in historial_rutinas if h.get("duracion_segundos")
    ]
    if not filas:
        return pd.DataFrame(columns=["periodo", "minutos"])
    df = pd.DataFrame(filas)
    return df.groupby("periodo")["minutos"].sum().reset_index().sort_values("periodo")


# ---------------------------------------------------------------------------
# 8. RACHA ACTUAL — días consecutivos con actividad (rutina o comida),
# SIEMPRE calculada sobre el histórico completo (una racha no depende del
# rango que estés viendo en pantalla). Si hoy todavía no hay actividad, se
# cuenta desde ayer — para no romper la racha solo porque el día no ha
# terminado.
# ---------------------------------------------------------------------------
def calcular_racha_actual(historial_rutinas_completo: list[dict], historial_nutricion_completo: list[dict]) -> int:
    fechas = set()
    for h in historial_rutinas_completo:
        fechas.add(pd.to_datetime(h["completado_en"]).date())
    for h in historial_nutricion_completo:
        fechas.add(pd.to_datetime(h["registrado_en"]).date())

    if not fechas:
        return 0

    hoy = pd.Timestamp.now().date()
    cursor = hoy if hoy in fechas else hoy - pd.Timedelta(days=1)
    if cursor not in fechas:
        return 0

    racha = 0
    while cursor in fechas:
        racha += 1
        cursor = cursor - pd.Timedelta(days=1)
    return racha


# ---------------------------------------------------------------------------
# 9. KPIs — resumen para las tarjetas del inicio del dashboard. Responden al
# rango seleccionado (excepto la racha, ver función 8).
# ---------------------------------------------------------------------------
def calcular_kpis(historial_rutinas: list[dict], historial_nutricion: list[dict], racha_actual: int) -> dict:
    xp_total = sum(h["xp_ganado"] or 0 for h in historial_rutinas) + sum(h["xp_ganado"] or 0 for h in historial_nutricion)
    minutos_totales = round(sum((h.get("duracion_segundos") or 0) for h in historial_rutinas) / 60)
    dificultades = [h["dificultad_promedio_rutina"] for h in historial_rutinas if h.get("dificultad_promedio_rutina") is not None]

    return {
        "xp_total": xp_total,
        "n_rutinas": len(historial_rutinas),
        "n_comidas": len(historial_nutricion),
        "minutos_totales": minutos_totales,
        "dificultad_promedio": round(sum(dificultades) / len(dificultades), 1) if dificultades else None,
        "racha_actual": racha_actual,
    }
