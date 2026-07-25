"""
Pipeline piloto — clasificación de un usuario nuevo (clasificador restringido)
--------------------------------------------------------------------------------
Este script es la base que se adaptará a Streamlit más adelante. Recibe SOLO
las variables que un usuario real puede auto-reportar/auto-medir, reconstruye
las variables de laboratorio necesarias (igual que en el notebook de
entrenamiento) y devuelve el nivel_cluster oculto predicho.

Recordatorio de arquitectura: nivel_cluster NUNCA se muestra tal cual al
usuario final — se usa solo en backend para ajustar dificultad de rutinas.
Lo que el usuario ve es el sistema de XP visible, completamente separado.
"""

import joblib
import pandas as pd
from pathlib import Path

# ---------------------------------------------------------------------------
# CONFIGURACIÓN
# ---------------------------------------------------------------------------
# BASE_DIR: carpeta donde vive ESTE archivo, sin importar desde dónde lo
# ejecutes. Esto evita el problema clásico de que "../Models/..." se resuelva
# distinto según tu directorio de trabajo actual (cwd) en vez de según dónde
# está guardado el script.
BASE_DIR = Path(__file__).resolve().parent

MODEL_PATHS = {
    "F": BASE_DIR / "Models" / "clasificador_restringido_F.joblib",
    "M": BASE_DIR / "Models" / "clasificador_restringido_M.joblib",
}

NOMBRES_CLUSTER = {
    "F": {
        0: "Rendimiento Atlético Alto",
        1: "Contextura Ligera, Fuerza Limitada",
        2: "Composición Corporal Elevada",
    },
    "M": {
        0: "Composición Corporal Elevada",
        1: "Contextura Ligera, Buena Eficiencia",
        2: "Rendimiento Atlético Alto",
    },
}

CAMPOS_REQUERIDOS = [
    "age", "height_cm", "weight_kg", "waist_circumference_cm",
    "sit_and_reach_cm", "cross_situp_count", "standing_long_jump_cm",
    "reaction_time_sec", "gender_code",
]

# Cache simple en memoria — evita releer el .joblib del disco en cada llamada.
# En Streamlit esto se reemplaza por @st.cache_resource sobre esta misma función.
_modelos_cache = {}


def _cargar_modelo(genero: str) -> dict:
    if genero not in _modelos_cache:
        ruta = MODEL_PATHS[genero]
        if not ruta.exists():
            raise FileNotFoundError(
                f"No se encontró el modelo en: {ruta.resolve()}\n"
                f"Verifica que la carpeta Models/ exista junto a la carpeta de este script, "
                f"y que el notebook de entrenamiento ya haya guardado el .joblib ahí."
            )
        _modelos_cache[genero] = joblib.load(ruta)
    return _modelos_cache[genero]


def _reconstruir_features(datos_usuario: dict, bundle: dict) -> pd.DataFrame:
    """
    Recalcula EXACTAMENTE las mismas variables derivadas y reconstruidas que se
    usaron al entrenar (secciones 3, 4 y 5 del notebook de entrenamiento).
    Si algún día cambias el feature engineering allá, debes actualizar aquí
    también — ambos lados tienen que coincidir siempre.
    """
    df_input = pd.DataFrame([datos_usuario])

    # --- derivadas simples ---
    df_input["bmi_calc"] = df_input["weight_kg"] / (df_input["height_cm"] / 100) ** 2
    df_input["waist_to_height_ratio"] = df_input["waist_circumference_cm"] / df_input["height_cm"]
    df_input["relative_power"] = df_input["standing_long_jump_cm"] / df_input["weight_kg"]
    df_input["situps_por_edad"] = df_input["cross_situp_count"] / df_input["age"]
    df_input["salto_por_altura"] = df_input["standing_long_jump_cm"] / df_input["height_cm"]
    df_input["edad_x_imc"] = df_input["age"] * df_input["bmi_calc"]

    # --- % grasa corporal estimado (fórmula de Deurenberg, 1991) ---
    sexo_num = 1 if datos_usuario["gender_code"] == "M" else 0
    df_input["body_fat_pct_estimado"] = (
        1.20 * df_input["bmi_calc"] + 0.23 * df_input["age"] - 10.8 * sexo_num - 5.4
    )

    # --- reconstrucción de agarre y VO2max con los regresores auxiliares guardados ---
    predictores_reconstruccion = bundle["predictores_reconstruccion"]
    df_input["grip_strength_avg_kg_reconstruido"] = bundle["reconstructor_grip"].predict(
        df_input[predictores_reconstruccion]
    )
    df_input["vo2max_estimate_reconstruido"] = bundle["reconstructor_vo2"].predict(
        df_input[predictores_reconstruccion]
    )

    return df_input[bundle["features"]]


def clasificar_usuario(datos_usuario: dict) -> dict:
    """
    Punto de entrada único del pipeline — esta es la función que Streamlit
    va a llamar directamente cuando el usuario llene el formulario.

    Parameters
    ----------
    datos_usuario : dict
        Debe traer exactamente las llaves de CAMPOS_REQUERIDOS.
        gender_code debe ser "F" o "M".

    Returns
    -------
    dict con nivel_cluster (int, uso interno), nivel_cluster_nombre (str, uso
    interno también — NO mostrar directo al usuario final), modelo_usado, y
    probabilidades por clase si el modelo las soporta.
    """
    faltantes = [c for c in CAMPOS_REQUERIDOS if c not in datos_usuario]
    if faltantes:
        raise ValueError(f"Faltan campos en datos_usuario: {faltantes}")

    genero = datos_usuario["gender_code"]
    if genero not in ("F", "M"):
        raise ValueError(f"gender_code debe ser 'F' o 'M', recibido: {genero!r}")

    bundle = _cargar_modelo(genero)
    X_input = _reconstruir_features(datos_usuario, bundle)

    modelo = bundle["modelo"]
    cluster_predicho = int(modelo.predict(X_input)[0])
    nombre_cluster = NOMBRES_CLUSTER[genero][cluster_predicho]

    resultado = {
        "gender_code": genero,
        "nivel_cluster": cluster_predicho,
        "nivel_cluster_nombre": nombre_cluster,
        "modelo_usado": bundle["nombre_modelo"],
    }

    if hasattr(modelo, "predict_proba"):
        proba = modelo.predict_proba(X_input)[0]
        resultado["probabilidades"] = {
            NOMBRES_CLUSTER[genero][i]: round(float(p), 3) for i, p in enumerate(proba)
        }

    return resultado


# ---------------------------------------------------------------------------
# PRUEBA PILOTO — simula usuarios distintos para verificar que el pipeline corre
# de principio a fin sin errores, antes de conectarlo a Streamlit.
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    usuarios_prueba = [
        {  # mujer joven, buen desempeño físico esperado
            "age": 28, "height_cm": 165, "weight_kg": 58, "waist_circumference_cm": 70,
            "sit_and_reach_cm": 18, "cross_situp_count": 30, "standing_long_jump_cm": 160,
            "reaction_time_sec": 0.35, "gender_code": "F",
        },
        {  # hombre de mayor edad, peso/cintura altos
            "age": 45, "height_cm": 170, "weight_kg": 90, "waist_circumference_cm": 100,
            "sit_and_reach_cm": 8, "cross_situp_count": 15, "standing_long_jump_cm": 140,
            "reaction_time_sec": 0.45, "gender_code": "M",
        },
        {  # hombre joven, buen desempeño esperado
            "age": 22, "height_cm": 178, "weight_kg": 72, "waist_circumference_cm": 80,
            "sit_and_reach_cm": 12, "cross_situp_count": 45, "standing_long_jump_cm": 230,
            "reaction_time_sec": 0.32, "gender_code": "M",
        },
    ]

    for i, usuario in enumerate(usuarios_prueba, start=1):
        print(f"\n--- Usuario de prueba {i} ({usuario['gender_code']}) ---")
        resultado = clasificar_usuario(usuario)
        for k, v in resultado.items():
            print(f"  {k}: {v}")