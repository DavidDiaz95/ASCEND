"""
Almacenamiento de perfiles de usuario — VERSIÓN TEMPORAL (local, JSON)
--------------------------------------------------------------------------
IMPORTANTE: esto es solo para desarrollo local. Cuando despliegues a
Streamlit Community Cloud (remoto), el sistema de archivos NO es persistente
— estos datos se pueden perder en cualquier reinicio. Antes de desplegar,
reemplaza guardar_perfil()/cargar_perfiles() por las funciones equivalentes
conectadas a Supabase (o la base de datos que elijas), manteniendo la misma
firma de función para no tener que tocar el resto del código.
"""

import json
import uuid
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
RUTA_PERFILES = BASE_DIR / "Data" / "usuarios_temp.json"


def guardar_perfil(perfil: dict) -> str:
    """
    Guarda un perfil de usuario nuevo. Regresa el id único generado para ese
    usuario (lo vas a necesitar después para asociarle rutinas completadas,
    logs de XP, etc.)
    """
    RUTA_PERFILES.parent.mkdir(parents=True, exist_ok=True)

    if RUTA_PERFILES.exists():
        with open(RUTA_PERFILES, "r", encoding="utf-8") as f:
            perfiles = json.load(f)
    else:
        perfiles = []

    usuario_id = str(uuid.uuid4())
    perfil_completo = {
        "usuario_id": usuario_id,
        "creado_en": datetime.now().isoformat(),
        **perfil,
    }
    perfiles.append(perfil_completo)

    with open(RUTA_PERFILES, "w", encoding="utf-8") as f:
        json.dump(perfiles, f, ensure_ascii=False, indent=2)

    return usuario_id


def cargar_perfiles() -> list:
    """Regresa todos los perfiles guardados hasta ahora (lista de dicts)."""
    if not RUTA_PERFILES.exists():
        return []
    with open(RUTA_PERFILES, "r", encoding="utf-8") as f:
        return json.load(f)
