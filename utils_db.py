"""
utils_db.py — Capa de persistencia de ASCEND
--------------------------------------------------------------------------------
Reemplaza/extiende a utils_storage.py. Usa SQLite (un solo archivo, sin
servidor, incluido en la stdlib de Python) para que los datos sobrevivan
entre sesiones y entre reinicios de la app.

Tablas:
    usuarios              -> auth (username, password hasheado)
    perfiles               -> último perfil físico/antropométrico reportado
    clasificaciones        -> resultado OCULTO del clasificador restringido
    interacciones_rutinas  -> historial de rutinas completadas + XP ganado
    interacciones_nutricion -> historial de registros de nutrición

IMPORTANTE (arquitectura ya decidida en el proyecto):
    nivel_cluster / nivel_cluster_nombre son de uso INTERNO. Nunca se
    muestran tal cual al usuario final. Lo que el usuario ve es el sistema
    de XP/niveles, que se calcula aparte a partir de interacciones_rutinas.
"""

import hashlib
import os
import sqlite3
import uuid
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "ascend.db"

PBKDF2_ITERATIONS = 100_000


# ---------------------------------------------------------------------------
# CONEXIÓN E INICIALIZACIÓN
# ---------------------------------------------------------------------------
def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db() -> None:
    """Crea las tablas si no existen. Llamar una vez al arrancar main.py."""
    with get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS usuarios (
                usuario_id      TEXT PRIMARY KEY,
                username        TEXT UNIQUE NOT NULL,
                password_hash   TEXT NOT NULL,
                salt            TEXT NOT NULL,
                creado_en       TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS perfiles (
                usuario_id              TEXT PRIMARY KEY,
                gender_code             TEXT NOT NULL,
                age                     INTEGER NOT NULL,
                height_cm               REAL NOT NULL,
                weight_kg               REAL NOT NULL,
                waist_circumference_cm  REAL NOT NULL,
                sit_and_reach_cm        REAL NOT NULL,
                cross_situp_count       INTEGER NOT NULL,
                standing_long_jump_cm   REAL NOT NULL,
                reaction_time_sec       REAL NOT NULL,
                actualizado_en          TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (usuario_id) REFERENCES usuarios(usuario_id)
            );

            CREATE TABLE IF NOT EXISTS equipo_usuario (
                usuario_id      TEXT PRIMARY KEY,
                equipo_json     TEXT NOT NULL,
                actualizado_en  TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (usuario_id) REFERENCES usuarios(usuario_id)
            );

            CREATE TABLE IF NOT EXISTS clasificaciones (
                usuario_id           TEXT PRIMARY KEY,
                gender_code          TEXT NOT NULL,
                nivel_cluster        INTEGER NOT NULL,
                nivel_cluster_nombre TEXT NOT NULL,
                modelo_usado         TEXT,
                probabilidades_json  TEXT,
                actualizado_en       TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (usuario_id) REFERENCES usuarios(usuario_id)
            );

            CREATE TABLE IF NOT EXISTS interacciones_rutinas (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id    TEXT NOT NULL,
                rutina_id     TEXT NOT NULL,
                xp_ganado     INTEGER NOT NULL DEFAULT 0,
                completado_en TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (usuario_id) REFERENCES usuarios(usuario_id)
            );

            CREATE TABLE IF NOT EXISTS interacciones_nutricion (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id    TEXT NOT NULL,
                tipo          TEXT NOT NULL,
                detalle_json  TEXT,
                registrado_en TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (usuario_id) REFERENCES usuarios(usuario_id)
            );
            """
        )
        _migrar_columnas_faltantes(conn)


def _migrar_columnas_faltantes(conn: sqlite3.Connection) -> None:
    """Agrega columnas nuevas a tablas que ya existían en instalaciones
    previas de ascend.db, sin perder los datos que ya tenías guardados.
    Cada vez que agregues un campo nuevo a una tabla existente, se declara
    aquí en vez de romper el CREATE TABLE IF NOT EXISTS de arriba."""
    columnas_perfiles = {
        fila["name"] for fila in conn.execute("PRAGMA table_info(perfiles)").fetchall()
    }
    if "objetivo" not in columnas_perfiles:
        conn.execute("ALTER TABLE perfiles ADD COLUMN objetivo TEXT")

    columnas_interacciones = {
        fila["name"] for fila in conn.execute("PRAGMA table_info(interacciones_rutinas)").fetchall()
    }
    if "dificultad_promedio_rutina" not in columnas_interacciones:
        # Necesaria para el "nivel dinámico": sin esto, el historial solo
        # trae XP, no dificultad, y no se puede calcular hacia dónde va
        # progresando el usuario en términos de exigencia real.
        conn.execute("ALTER TABLE interacciones_rutinas ADD COLUMN dificultad_promedio_rutina REAL")
    if "n_ejercicios" not in columnas_interacciones:
        conn.execute("ALTER TABLE interacciones_rutinas ADD COLUMN n_ejercicios INTEGER")
    if "zonas_json" not in columnas_interacciones:
        # dict zona_muscular -> cuántos ejercicios de esa zona trajo la
        # rutina. Es la pieza que le falta al dashboard y al balanceador
        # de zonas musculares del recomendador.
        conn.execute("ALTER TABLE interacciones_rutinas ADD COLUMN zonas_json TEXT")
    if "objetivo" not in columnas_interacciones:
        conn.execute("ALTER TABLE interacciones_rutinas ADD COLUMN objetivo TEXT")


# ---------------------------------------------------------------------------
# AUTH — hashing de contraseña
# ---------------------------------------------------------------------------
def _hashear_password(password: str, salt: bytes | None = None) -> tuple[str, str]:
    if salt is None:
        salt = os.urandom(16)
    hash_bytes = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS
    )
    return hash_bytes.hex(), salt.hex()


def crear_usuario(username: str, password: str) -> str:
    """Crea una cuenta nueva. Regresa el usuario_id. Lanza ValueError si el
    username ya existe (esto es lo que distingue 'crear cuenta' de 'login')."""
    username = username.strip().lower()
    if not username or not password:
        raise ValueError("Usuario y contraseña no pueden estar vacíos.")
    if len(password) < 6:
        raise ValueError("La contraseña debe tener al menos 6 caracteres.")

    password_hash, salt = _hashear_password(password)
    usuario_id = str(uuid.uuid4())

    with get_connection() as conn:
        existe = conn.execute(
            "SELECT 1 FROM usuarios WHERE username = ?", (username,)
        ).fetchone()
        if existe:
            raise ValueError("Ese nombre de usuario ya existe. Intenta iniciar sesión.")
        conn.execute(
            "INSERT INTO usuarios (usuario_id, username, password_hash, salt) VALUES (?, ?, ?, ?)",
            (usuario_id, username, password_hash, salt),
        )
    return usuario_id


def verificar_login(username: str, password: str) -> str | None:
    """Regresa el usuario_id si username/password son correctos, si no None."""
    username = username.strip().lower()
    with get_connection() as conn:
        fila = conn.execute(
            "SELECT usuario_id, password_hash, salt FROM usuarios WHERE username = ?",
            (username,),
        ).fetchone()
        if fila is None:
            return None
        hash_calculado, _ = _hashear_password(password, bytes.fromhex(fila["salt"]))
        if hash_calculado == fila["password_hash"]:
            return fila["usuario_id"]
        return None


# ---------------------------------------------------------------------------
# PERFIL FÍSICO / ANTROPOMÉTRICO
# ---------------------------------------------------------------------------
def guardar_perfil(usuario_id: str, perfil: dict) -> None:
    """Upsert del perfil físico más reciente del usuario."""
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO perfiles (
                usuario_id, gender_code, age, height_cm, weight_kg,
                waist_circumference_cm, sit_and_reach_cm, cross_situp_count,
                standing_long_jump_cm, reaction_time_sec, objetivo, actualizado_en
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(usuario_id) DO UPDATE SET
                gender_code = excluded.gender_code,
                age = excluded.age,
                height_cm = excluded.height_cm,
                weight_kg = excluded.weight_kg,
                waist_circumference_cm = excluded.waist_circumference_cm,
                sit_and_reach_cm = excluded.sit_and_reach_cm,
                cross_situp_count = excluded.cross_situp_count,
                standing_long_jump_cm = excluded.standing_long_jump_cm,
                reaction_time_sec = excluded.reaction_time_sec,
                objetivo = excluded.objetivo,
                actualizado_en = datetime('now')
            """,
            (
                usuario_id,
                perfil["gender_code"],
                perfil["age"],
                perfil["height_cm"],
                perfil["weight_kg"],
                perfil["waist_circumference_cm"],
                perfil["sit_and_reach_cm"],
                perfil["cross_situp_count"],
                perfil["standing_long_jump_cm"],
                perfil["reaction_time_sec"],
                perfil.get("objetivo"),
            ),
        )


def obtener_perfil(usuario_id: str) -> dict | None:
    with get_connection() as conn:
        fila = conn.execute(
            "SELECT * FROM perfiles WHERE usuario_id = ?", (usuario_id,)
        ).fetchone()
        return dict(fila) if fila else None


# ---------------------------------------------------------------------------
# CLASIFICACIÓN OCULTA (salida de clasificar_usuario())
# ---------------------------------------------------------------------------
def guardar_clasificacion(usuario_id: str, resultado: dict) -> None:
    import json

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO clasificaciones (
                usuario_id, gender_code, nivel_cluster, nivel_cluster_nombre,
                modelo_usado, probabilidades_json, actualizado_en
            ) VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(usuario_id) DO UPDATE SET
                gender_code = excluded.gender_code,
                nivel_cluster = excluded.nivel_cluster,
                nivel_cluster_nombre = excluded.nivel_cluster_nombre,
                modelo_usado = excluded.modelo_usado,
                probabilidades_json = excluded.probabilidades_json,
                actualizado_en = datetime('now')
            """,
            (
                usuario_id,
                resultado["gender_code"],
                resultado["nivel_cluster"],
                resultado["nivel_cluster_nombre"],
                resultado.get("modelo_usado"),
                json.dumps(resultado.get("probabilidades", {})),
            ),
        )


def obtener_clasificacion(usuario_id: str) -> dict | None:
    with get_connection() as conn:
        fila = conn.execute(
            "SELECT * FROM clasificaciones WHERE usuario_id = ?", (usuario_id,)
        ).fetchone()
        return dict(fila) if fila else None


# ---------------------------------------------------------------------------
# INTERACCIONES — rutinas y nutrición (alimentan el XP visible y el dashboard)
# ---------------------------------------------------------------------------
def registrar_interaccion_rutina(
    usuario_id: str, rutina_id: str, xp_ganado: int,
    dificultad_promedio_rutina: float | None = None,
    n_ejercicios: int | None = None,
    zonas_json: dict | None = None,
    objetivo: str | None = None,
) -> None:
    import json

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO interacciones_rutinas
                (usuario_id, rutina_id, xp_ganado, dificultad_promedio_rutina,
                 n_ejercicios, zonas_json, objetivo)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                usuario_id, rutina_id, xp_ganado, dificultad_promedio_rutina,
                n_ejercicios, json.dumps(zonas_json) if zonas_json is not None else None,
                objetivo,
            ),
        )


def registrar_interaccion_nutricion(usuario_id: str, tipo: str, detalle: dict) -> None:
    import json

    with get_connection() as conn:
        conn.execute(
            "INSERT INTO interacciones_nutricion (usuario_id, tipo, detalle_json) VALUES (?, ?, ?)",
            (usuario_id, tipo, json.dumps(detalle)),
        )


def obtener_xp_total(usuario_id: str) -> int:
    with get_connection() as conn:
        fila = conn.execute(
            "SELECT COALESCE(SUM(xp_ganado), 0) AS xp FROM interacciones_rutinas WHERE usuario_id = ?",
            (usuario_id,),
        ).fetchone()
        return int(fila["xp"])


# ---------------------------------------------------------------------------
# EQUIPO DISPONIBLE — independiente del perfil físico, se actualiza cuando
# el usuario quiera (ej. compró una barra nueva) sin rehacer los tests.
# ---------------------------------------------------------------------------
def guardar_equipo_usuario(usuario_id: str, lista_equipo: list[str]) -> None:
    import json

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO equipo_usuario (usuario_id, equipo_json, actualizado_en)
            VALUES (?, ?, datetime('now'))
            ON CONFLICT(usuario_id) DO UPDATE SET
                equipo_json = excluded.equipo_json,
                actualizado_en = datetime('now')
            """,
            (usuario_id, json.dumps(lista_equipo)),
        )


def obtener_equipo_usuario(usuario_id: str) -> list[str]:
    import json

    with get_connection() as conn:
        fila = conn.execute(
            "SELECT equipo_json FROM equipo_usuario WHERE usuario_id = ?", (usuario_id,)
        ).fetchone()
        return json.loads(fila["equipo_json"]) if fila else []


def obtener_historial_rutinas(usuario_id: str, limite: int = 20) -> list[dict]:
    import json

    with get_connection() as conn:
        filas = conn.execute(
            """
            SELECT rutina_id, xp_ganado, dificultad_promedio_rutina, n_ejercicios,
                   zonas_json, objetivo, completado_en
            FROM interacciones_rutinas
            WHERE usuario_id = ? ORDER BY completado_en DESC LIMIT ?
            """,
            (usuario_id, limite),
        ).fetchall()
        historial = [dict(f) for f in filas]
        for h in historial:
            h["zonas_json"] = json.loads(h["zonas_json"]) if h.get("zonas_json") else {}
        return historial


def obtener_frecuencia_zonas_reciente(usuario_id: str, dias: int = 21) -> dict:
    """Cuántos ejercicios de cada zona muscular hizo el usuario en los
    últimos `dias` días. Es la entrada del balanceador de zonas del
    recomendador — sin esto, el motor solo sigue el objetivo declarado y
    puede sobre-entrenar la misma zona una y otra vez."""
    import json
    from collections import Counter

    with get_connection() as conn:
        filas = conn.execute(
            """
            SELECT zonas_json FROM interacciones_rutinas
            WHERE usuario_id = ? AND zonas_json IS NOT NULL
              AND datetime(completado_en) >= datetime('now', ?)
            """,
            (usuario_id, f"-{dias} days"),
        ).fetchall()

    frecuencia = Counter()
    for fila in filas:
        frecuencia.update(json.loads(fila["zonas_json"]))
    return dict(frecuencia)
