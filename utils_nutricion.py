"""
utils_nutricion.py — Motor de recomendación de comidas de ASCEND
--------------------------------------------------------------------------------
Conecta dos piezas:
  1. Visión (gpt-5.4-mini, el mismo modelo que ya usa el asistente) — identifica
     ingredientes a partir de una foto del refrigerador/despensa.
  2. Spoonacular (API de recetas y nutrición) — busca recetas que usen esos
     ingredientes y trae calorías/macros reales.

Por qué Spoonacular en inglés: su catálogo de recetas e ingredientes SOLO
funciona en inglés (confirmado en su documentación) — por eso
`identificar_ingredientes_de_foto` le pide a la IA los nombres en inglés,
aunque el resto de ASCEND esté en español. Los nombres que ve el usuario en
pantalla sí vienen ya traducidos/mostrados en español donde aplica.

IMPORTANTE (arquitectura): esta capa NUNCA registra nada en la base de
datos por sí sola — solo busca y arma opciones. El registro (con XP) lo
hace la página, y solo después de que el usuario CONFIRMA que va a preparar
esa comida. Buscar opciones no cuesta XP; confirmarla sí.
"""

import base64
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv
from openai import OpenAI

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env", override=True)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SPOONACULAR_API_KEY = os.getenv("SPOONACULAR_API_KEY")
SPOONACULAR_BASE_URL = "https://api.spoonacular.com"

MODELO_VISION = "gpt-5.4-mini"  # mismo modelo que 05_Asistente.py

# ---------------------------------------------------------------------------
# XP — a propósito más generoso que una rutina promedio, para incentivar que
# el usuario adopte esta parte nueva de la app. El XP de rutina es
# proporcional a su dificultad (normalmente 10-70); una comida confirmada da
# un XP fijo por encima de ese rango.
# ---------------------------------------------------------------------------
XP_POR_COMIDA_CONFIRMADA = 60


class ErrorNutricion(Exception):
    """Error controlado (cuota agotada, red caída, respuesta rara del LLM)
    para que la página pueda mostrar un mensaje amigable en vez de tronar."""


# ---------------------------------------------------------------------------
# TRADUCCIÓN DE INGREDIENTES ESCRITOS A MANO — el bug real: cuando el
# usuario escribe "arroz" en vez de subir una foto, nunca pasaba por
# ningún paso de traducción, y Spoonacular (inglés únicamente) no
# reconocía nada -> 0 resultados siempre, sin importar qué tan cerca
# estuviera el ingrediente real.
# ---------------------------------------------------------------------------
def traducir_ingredientes_a_ingles(ingredientes: list[str]) -> list[str]:
    """Traduce una lista de ingredientes (en el idioma que sea) a nombres
    genéricos en inglés que Spoonacular pueda reconocer. Si el texto ya
    viene en inglés, lo normaliza igual (minúsculas, sin ruido)."""
    if not ingredientes:
        return []
    if not OPENAI_API_KEY:
        raise ErrorNutricion("No hay OPENAI_API_KEY configurada en .env")

    client = OpenAI(api_key=OPENAI_API_KEY)
    prompt = (
        "Translate/normalize this list of food ingredients (they may be in "
        "Spanish, English, or mixed) into simple, generic ingredient names "
        "in English that a recipe database would recognize (e.g. 'arroz' -> "
        "'rice', 'jitomate' -> 'tomato', 'pechuga de pollo' -> 'chicken "
        f"breast'). Ingredients: {ingredientes}. Respond with ONLY a JSON "
        "array of strings, same order, same length, no extra text, no "
        "markdown fences."
    )
    try:
        respuesta = client.chat.completions.create(
            model=MODELO_VISION,
            messages=[{"role": "user", "content": prompt}],
            max_completion_tokens=300,
        )
        texto = respuesta.choices[0].message.content.strip()
    except Exception as e:
        raise ErrorNutricion(f"No se pudo traducir la lista de ingredientes: {e}")

    texto_limpio = texto.replace("```json", "").replace("```", "").strip()
    try:
        traducidos = json.loads(texto_limpio)
    except json.JSONDecodeError:
        # Si la traducción falla, seguimos con el texto original en vez de
        # tronar — más vale intentar la búsqueda tal cual que no buscar nada.
        print(f"[ASCEND][nutricion][WARN] no se pudo parsear traducción, uso original: {texto[:200]}")
        return [i.strip().lower() for i in ingredientes]

    if not isinstance(traducidos, list) or len(traducidos) != len(ingredientes):
        print(f"[ASCEND][nutricion][WARN] traducción con forma rara, uso original: {traducidos}")
        return [i.strip().lower() for i in ingredientes]

    return [str(i).strip().lower() for i in traducidos]


def traducir_ingredientes_a_espanol(ingredientes: list[str]) -> list[str]:
    """Dirección inversa — Spoonacular regresa 'usedIngredients'/
    'missedIngredients' en inglés; esto los traduce para mostrarlos en la
    pantalla de confirmación, más legible para nuestro público. Si algo
    sale mal, se regresan tal cual (mejor mostrar inglés que tronar)."""
    if not ingredientes:
        return []
    if not OPENAI_API_KEY:
        return ingredientes

    client = OpenAI(api_key=OPENAI_API_KEY)
    prompt = (
        f"Translate this list of food ingredient names to natural Spanish "
        f"(Latin American, simple everyday words): {ingredientes}. Respond "
        "with ONLY a JSON array of strings, same order, same length, no "
        "extra text, no markdown fences."
    )
    try:
        respuesta = client.chat.completions.create(
            model=MODELO_VISION,
            messages=[{"role": "user", "content": prompt}],
            max_completion_tokens=300,
        )
        texto_limpio = respuesta.choices[0].message.content.strip().replace("```json", "").replace("```", "").strip()
        traducidos = json.loads(texto_limpio)
        if isinstance(traducidos, list) and len(traducidos) == len(ingredientes):
            return [str(i).strip() for i in traducidos]
    except Exception as e:
        print(f"[ASCEND][nutricion][WARN] no se pudo traducir a español: {e}")

    return ingredientes


# ---------------------------------------------------------------------------
# PASO 1 — FOTO DEL REFRIGERADOR -> LISTA DE INGREDIENTES (en inglés)
# ---------------------------------------------------------------------------
def identificar_ingredientes_de_foto(imagen_bytes: bytes) -> list[str]:
    """
    Manda la foto a gpt-5.4-mini (visión) y regresa una lista simple de
    ingredientes EN INGLÉS (requisito de Spoonacular). Si el usuario quiere
    ver los nombres en español, se traducen solo para mostrarlos en
    pantalla — la búsqueda en Spoonacular siempre usa esta lista en inglés.
    """
    if not OPENAI_API_KEY:
        raise ErrorNutricion("No hay OPENAI_API_KEY configurada en .env")

    client = OpenAI(api_key=OPENAI_API_KEY)
    imagen_b64 = base64.b64encode(imagen_bytes).decode("utf-8")

    prompt = (
        "Look at this photo of a fridge or pantry. List every distinct food "
        "ingredient you can actually identify. Respond with ONLY a JSON array "
        "of simple, generic ingredient names in English (e.g. [\"egg\", \"milk\", "
        "\"tomato\", \"chicken breast\"]) — no brand names, no extra text, no "
        "markdown fences, just the JSON array. If you cannot identify any food "
        "ingredients, respond with []."
    )

    try:
        respuesta = client.chat.completions.create(
            model=MODELO_VISION,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{imagen_b64}"}},
                    ],
                }
            ],
            max_completion_tokens=500,
        )
        texto = respuesta.choices[0].message.content.strip()
    except Exception as e:
        raise ErrorNutricion(f"No se pudo analizar la imagen: {e}")

    texto_limpio = texto.replace("```json", "").replace("```", "").strip()
    try:
        ingredientes = json.loads(texto_limpio)
    except json.JSONDecodeError:
        raise ErrorNutricion(f"La IA no regresó una lista válida: {texto[:200]}")

    if not isinstance(ingredientes, list):
        raise ErrorNutricion("La IA no regresó una lista de ingredientes.")

    return [str(i).strip().lower() for i in ingredientes if str(i).strip()]


# ---------------------------------------------------------------------------
# PASO 2 — INGREDIENTES -> OPCIONES DE RECETA CON NUTRICIÓN (Spoonacular)
# ---------------------------------------------------------------------------
def _extraer_nutrientes(info_receta: dict) -> dict:
    """Spoonacular regresa los nutrientes como una lista [{'name':.., 'amount':..,
    'unit':..}, ...] — esto la convierte en un dict directo con lo que nos
    interesa mostrar."""
    nutrientes_buscados = {
        "Calories": "calorias", "Protein": "proteina_g",
        "Fat": "grasa_g", "Carbohydrates": "carbohidratos_g",
    }
    resultado = {v: None for v in nutrientes_buscados.values()}
    for nutriente in info_receta.get("nutrition", {}).get("nutrients", []):
        if nutriente.get("name") in nutrientes_buscados:
            resultado[nutrientes_buscados[nutriente["name"]]] = round(nutriente.get("amount", 0), 1)
    return resultado


def buscar_opciones_comida(ingredientes: list[str], n_opciones: int = 3) -> list[dict]:
    """
    Busca recetas que aprovechen los ingredientes dados y regresa
    `n_opciones` con su información nutricional ya calculada. Usa 2
    llamadas a Spoonacular en total (findByIngredients + informationBulk en
    una sola petición) para cuidar la cuota del plan gratis (50 puntos/día).

    Pide más candidatos de los que se muestran (N_CANDIDATOS_A_PEDIR) y usa
    ranking=2 (Spoonacular minimiza ingredientes faltantes) — así, aunque
    no haya un match perfecto, siempre se regresa lo MÁS CERCANO posible a
    lo que el usuario tiene disponible, en vez de nada.
    """
    if not SPOONACULAR_API_KEY:
        raise ErrorNutricion("No hay SPOONACULAR_API_KEY configurada en .env")
    if not ingredientes:
        return []

    n_candidatos_a_pedir = max(n_opciones, 10)
    print(f"[ASCEND][nutricion][request] findByIngredients ingredientes={ingredientes} number={n_candidatos_a_pedir}")

    try:
        resp_busqueda = requests.get(
            f"{SPOONACULAR_BASE_URL}/recipes/findByIngredients",
            params={
                "ingredients": ",".join(ingredientes),
                "number": n_candidatos_a_pedir,
                "ranking": 2,  # minimiza ingredientes faltantes -> el más cercano queda primero
                "ignorePantry": "true",
                "apiKey": SPOONACULAR_API_KEY,
            },
            timeout=15,
        )
    except requests.RequestException as e:
        raise ErrorNutricion(f"No se pudo conectar con Spoonacular: {e}")

    print(f"[ASCEND][nutricion][response] findByIngredients status={resp_busqueda.status_code}")

    if resp_busqueda.status_code == 402:
        raise ErrorNutricion("Se acabó la cuota gratuita de Spoonacular por hoy (50 puntos/día). Intenta mañana.")
    if not resp_busqueda.ok:
        raise ErrorNutricion(f"Spoonacular respondió con error {resp_busqueda.status_code}: {resp_busqueda.text[:200]}")

    candidatos = resp_busqueda.json()
    print(f"[ASCEND][nutricion][response] {len(candidatos)} candidatos encontrados")
    if not candidatos:
        return []

    candidatos = candidatos[:n_opciones]  # nos quedamos con los más cercanos para no gastar cuota de más
    ids = ",".join(str(c["id"]) for c in candidatos)
    try:
        resp_info = requests.get(
            f"{SPOONACULAR_BASE_URL}/recipes/informationBulk",
            params={"ids": ids, "includeNutrition": "true", "apiKey": SPOONACULAR_API_KEY},
            timeout=15,
        )
    except requests.RequestException as e:
        raise ErrorNutricion(f"No se pudo conectar con Spoonacular: {e}")

    print(f"[ASCEND][nutricion][response] informationBulk status={resp_info.status_code}")

    if not resp_info.ok:
        raise ErrorNutricion(f"Spoonacular respondió con error {resp_info.status_code}: {resp_info.text[:200]}")

    info_por_id = {r["id"]: r for r in resp_info.json()}

    opciones = []
    for candidato in candidatos:
        info = info_por_id.get(candidato["id"])
        if not info:
            continue
        nutrientes = _extraer_nutrientes(info)
        opciones.append({
            "id": candidato["id"],
            "titulo": candidato["title"],
            "imagen_url": candidato.get("image"),
            "ingredientes_usados": [ing["name"] for ing in candidato.get("usedIngredients", [])],
            "ingredientes_faltantes": [ing["name"] for ing in candidato.get("missedIngredients", [])],
            "calorias": nutrientes["calorias"],
            "proteina_g": nutrientes["proteina_g"],
            "grasa_g": nutrientes["grasa_g"],
            "carbohidratos_g": nutrientes["carbohidratos_g"],
            "listo_en_minutos": info.get("readyInMinutes"),
            "porciones": info.get("servings"),
            "url_receta": info.get("sourceUrl") or f"https://spoonacular.com/recipes/{candidato['title'].replace(' ', '-')}-{candidato['id']}",
        })

    print(f"[ASCEND][nutricion][resultado] {len(opciones)} opciones finales armadas")
    return opciones


# ---------------------------------------------------------------------------
# PANEL DE METAS DIARIAS — Mifflin-St Jeor (BMR) + factor de actividad +
# ajuste según objetivo. Es una ESTIMACIÓN general, no un plan clínico
# ---------------------------------------------------------------------------
FACTOR_ACTIVIDAD_BAJO = 1.2
FACTOR_ACTIVIDAD_MODERADO = 1.45
FACTOR_ACTIVIDAD_ALTO = 1.725
NOMBRE_FACTOR_ACTIVIDAD = {
    FACTOR_ACTIVIDAD_BAJO: "baja", FACTOR_ACTIVIDAD_MODERADO: "moderada", FACTOR_ACTIVIDAD_ALTO: "alta",
}


def _determinar_factor_actividad(historial_rutinas: list[dict] | None) -> float:
    """Puente rutinas -> dieta: sin datos de calorías por ejercicio, se usa
    la cantidad de rutinas completadas hoy/ayer (en UTC, mismo criterio que
    SQLite) como proxy de actividad física real."""
    if not historial_rutinas:
        return FACTOR_ACTIVIDAD_BAJO
    hoy = datetime.now(timezone.utc).date()
    ayer = hoy - timedelta(days=1)
    contador = sum(
        1 for h in historial_rutinas
        if datetime.strptime(h["completado_en"][:19], "%Y-%m-%d %H:%M:%S").date() in (hoy, ayer)
    )
    if contador > 2:
        return FACTOR_ACTIVIDAD_ALTO
    if contador >= 1:
        return FACTOR_ACTIVIDAD_MODERADO
    return FACTOR_ACTIVIDAD_BAJO

AJUSTE_CALORICO_POR_OBJETIVO = {
    "Bajar de peso": -500, "Ganar músculo": +300, "Ganar fuerza": +200,
    "Mejorar resistencia/cardio": 0, "Salud general": 0,
}
PROTEINA_G_POR_KG_POR_OBJETIVO = {
    # Más alta durante déficit (preservar músculo) y en ganancia muscular;
    # valores dentro de los rangos que maneja la literatura deportiva.
    "Bajar de peso": 1.8, "Ganar músculo": 2.0, "Ganar fuerza": 1.8,
    "Mejorar resistencia/cardio": 1.4, "Salud general": 1.4,
}
PISO_CALORICO_SEGURIDAD = 1200  # nunca recomendar menos que esto, no es saludable


def calcular_objetivo_nutricional(perfil: dict, historial_rutinas: list[dict] | None = None) -> dict:
    """
    A partir del perfil físico (peso, estatura, edad, sexo) y el objetivo
    declarado, calcula: calorías objetivo, proteína, grasa y carbohidratos
    en gramos. Usa Mifflin-St Jeor para el metabolismo basal, con el factor
    de actividad determinado por las rutinas completadas hoy/ayer.
    """
    peso = perfil["weight_kg"]
    altura = perfil["height_cm"]
    edad = perfil["age"]
    sexo = perfil["gender_code"]
    objetivo = perfil.get("objetivo") or "Salud general"

    if sexo == "M":
        bmr = 10 * peso + 6.25 * altura - 5 * edad + 5
    else:
        bmr = 10 * peso + 6.25 * altura - 5 * edad - 161

    factor_actividad = _determinar_factor_actividad(historial_rutinas)
    tdee = bmr * factor_actividad
    calorias_objetivo = max(tdee + AJUSTE_CALORICO_POR_OBJETIVO.get(objetivo, 0), PISO_CALORICO_SEGURIDAD)

    proteina_g = round(peso * PROTEINA_G_POR_KG_POR_OBJETIVO.get(objetivo, 1.6))
    proteina_kcal = proteina_g * 4
    grasa_kcal = calorias_objetivo * 0.27  # 27% de calorías totales, punto medio razonable
    grasa_g = round(grasa_kcal / 9)
    carbohidratos_kcal = max(calorias_objetivo - proteina_kcal - grasa_kcal, 0)
    carbohidratos_g = round(carbohidratos_kcal / 4)

    return {
        "calorias": round(calorias_objetivo), "proteina_g": proteina_g,
        "factor_actividad": factor_actividad, "nombre_actividad": NOMBRE_FACTOR_ACTIVIDAD[factor_actividad],
        "grasa_g": grasa_g, "carbohidratos_g": carbohidratos_g,
        "bmr": round(bmr), "tdee": round(tdee), "objetivo_usado": objetivo,
    }


# ---------------------------------------------------------------------------
# SEGUNDO BUSCADOR — "otras comidas recomendadas para tu objetivo",
# independiente de lo que haya en el refrigerador. Usa complexSearch con
# rangos de calorías/proteína por comida (dividiendo la meta diaria entre
# N_COMIDAS_POR_DIA), y `addRecipeNutrition=true` para traer la nutrición
# en la MISMA llamada (más barato en cuota que buscar + informationBulk).
# ---------------------------------------------------------------------------
N_COMIDAS_POR_DIA = 3


def buscar_comidas_por_objetivo(objetivo_nutricional: dict, n_opciones: int = 3) -> list[dict]:
    if not SPOONACULAR_API_KEY:
        raise ErrorNutricion("No hay SPOONACULAR_API_KEY configurada en .env")

    calorias_por_comida = objetivo_nutricional["calorias"] / N_COMIDAS_POR_DIA
    proteina_por_comida = objetivo_nutricional["proteina_g"] / N_COMIDAS_POR_DIA

    params = {
        "minCalories": round(calorias_por_comida * 0.6),
        "maxCalories": round(calorias_por_comida * 1.3),
        "minProtein": round(proteina_por_comida * 0.6),
        "addRecipeNutrition": "true",
        "number": n_opciones,
        "sort": "random",
        "apiKey": SPOONACULAR_API_KEY,
    }
    print(f"[ASCEND][nutricion][request] complexSearch params={ {k:v for k,v in params.items() if k!='apiKey'} }")

    try:
        resp = requests.get(f"{SPOONACULAR_BASE_URL}/recipes/complexSearch", params=params, timeout=15)
    except requests.RequestException as e:
        raise ErrorNutricion(f"No se pudo conectar con Spoonacular: {e}")

    print(f"[ASCEND][nutricion][response] complexSearch status={resp.status_code}")

    if resp.status_code == 402:
        raise ErrorNutricion("Se acabó la cuota gratuita de Spoonacular por hoy (50 puntos/día). Intenta mañana.")
    if not resp.ok:
        raise ErrorNutricion(f"Spoonacular respondió con error {resp.status_code}: {resp.text[:200]}")

    resultados = resp.json().get("results", [])
    print(f"[ASCEND][nutricion][response] {len(resultados)} comidas recomendadas por objetivo")

    opciones = []
    for r in resultados:
        nutrientes = _extraer_nutrientes(r)
        opciones.append({
            "id": r["id"], "titulo": r["title"], "imagen_url": r.get("image"),
            "ingredientes_usados": [], "ingredientes_faltantes": [],  # no aplica, no viene del refri
            "calorias": nutrientes["calorias"], "proteina_g": nutrientes["proteina_g"],
            "grasa_g": nutrientes["grasa_g"], "carbohidratos_g": nutrientes["carbohidratos_g"],
            "listo_en_minutos": r.get("readyInMinutes"), "porciones": r.get("servings"),
            "url_receta": r.get("sourceUrl") or f"https://spoonacular.com/recipes/{r['title'].replace(' ', '-')}-{r['id']}",
        })
    return opciones


# ---------------------------------------------------------------------------
# INGREDIENTES NECESARIOS 
# missedIngredients. Esta función
# trae la lista completa de ingredientes de la receta (una sola llamada) para
# mostrarla al elegir, aunque no venga del buscador por disponibilidad.
# ---------------------------------------------------------------------------
def obtener_ingredientes_de_receta(receta_id: int) -> list[str]:
    if not SPOONACULAR_API_KEY:
        raise ErrorNutricion("No hay SPOONACULAR_API_KEY configurada en .env")

    print(f"[ASCEND][nutricion][request] recipe information id={receta_id} (para ingredientes)")
    try:
        resp = requests.get(
            f"{SPOONACULAR_BASE_URL}/recipes/{receta_id}/information",
            params={"apiKey": SPOONACULAR_API_KEY},
            timeout=15,
        )
    except requests.RequestException as e:
        raise ErrorNutricion(f"No se pudo conectar con Spoonacular: {e}")

    print(f"[ASCEND][nutricion][response] recipe information status={resp.status_code}")
    if resp.status_code == 402:
        raise ErrorNutricion("Se acabó la cuota gratuita de Spoonacular por hoy (50 puntos/día). Intenta mañana.")
    if not resp.ok:
        raise ErrorNutricion(f"Spoonacular respondió con error {resp.status_code}: {resp.text[:200]}")

    data = resp.json()
    return [ing["name"] for ing in data.get("extendedIngredients", []) if ing.get("name")]


# ---------------------------------------------------------------------------
# INSTRUCCIONES DE PREPARACIÓN — DENTRO de la app, no un link externo.
# Usa las instrucciones REALES de Spoonacular (una sola llamada, barata en
# cuota) y solo las traduce/formatea con el LLM — no inventa una receta
# nueva. Si Spoonacular no tiene instrucciones para esa receta en particular
# (pasa con algunas), el LLM sí propone una preparación razonable, pero se
# marca claramente para no hacerla pasar por la receta original.
# ---------------------------------------------------------------------------
def obtener_instrucciones_preparacion(receta_id: int, titulo: str) -> dict:
    """Regresa {'texto': str, 'es_generada_por_ia': bool}."""
    if not SPOONACULAR_API_KEY:
        raise ErrorNutricion("No hay SPOONACULAR_API_KEY configurada en .env")

    print(f"[ASCEND][nutricion][request] recipe information id={receta_id} (para instrucciones)")
    try:
        resp = requests.get(
            f"{SPOONACULAR_BASE_URL}/recipes/{receta_id}/information",
            params={"apiKey": SPOONACULAR_API_KEY},
            timeout=15,
        )
    except requests.RequestException as e:
        raise ErrorNutricion(f"No se pudo conectar con Spoonacular: {e}")

    print(f"[ASCEND][nutricion][response] recipe information status={resp.status_code}")
    if resp.status_code == 402:
        raise ErrorNutricion("Se acabó la cuota gratuita de Spoonacular por hoy (50 puntos/día). Intenta mañana.")
    if not resp.ok:
        raise ErrorNutricion(f"Spoonacular respondió con error {resp.status_code}: {resp.text[:200]}")

    data = resp.json()
    pasos_analizados = data.get("analyzedInstructions", [])
    if pasos_analizados and pasos_analizados[0].get("steps"):
        pasos_ingles = "\n".join(f"{p['number']}. {p['step']}" for p in pasos_analizados[0]["steps"])
    else:
        pasos_ingles = (data.get("instructions") or "").strip()

    if not OPENAI_API_KEY:
        raise ErrorNutricion("No hay OPENAI_API_KEY configurada en .env")
    client = OpenAI(api_key=OPENAI_API_KEY)

    if pasos_ingles:
        prompt = (
            f"Translate and format these cooking instructions into clear, "
            f"numbered steps in natural Spanish (Latin American audience). "
            f"Keep all steps, don't invent or remove any. Recipe: '{titulo}'.\n\n"
            f"Instructions:\n{pasos_ingles}"
        )
        es_generada_por_ia = False
    else:
        # Spoonacular no tenía instrucciones para esta receta en particular.
        prompt = (
            f"No encontramos instrucciones oficiales para la receta '{titulo}'. "
            f"Propón una preparación simple y razonable, en pasos numerados, "
            f"en español, para alguien cocinando en casa."
        )
        es_generada_por_ia = True

    try:
        respuesta = client.chat.completions.create(
            model=MODELO_VISION,
            messages=[{"role": "user", "content": prompt}],
            max_completion_tokens=700,
        )
        texto = respuesta.choices[0].message.content.strip()
    except Exception as e:
        raise ErrorNutricion(f"No se pudieron generar las instrucciones: {e}")

    return {"texto": texto, "es_generada_por_ia": es_generada_por_ia}
