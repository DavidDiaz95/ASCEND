"""
main.py — Router de ASCEND
--------------------------------------------------------------------------------
Este archivo no contiene el chat del asistente (eso se movió a
pages/05_Asistente.py). Su único trabajo es:
  1. Inicializar la base de datos si no existe.
  2. Decidir qué páginas se ven en el sidebar según si hay sesión iniciada.

Las páginas de Rutinas, Nutrición, Dashboard y Asistente NO aparecen en el
menú si no hay usuario_id en session_state. Además, cada una de esas páginas
vuelve a checar esto por su cuenta (ver el bloque de guardia al inicio de
cada script) por si alguien intenta entrar directo por URL.
"""

import streamlit as st

from utils_db import init_db

init_db()

if "usuario_id" not in st.session_state:
    st.session_state["usuario_id"] = None
if "username" not in st.session_state:
    st.session_state["username"] = None

usuario_logueado = st.session_state["usuario_id"] is not None

# ---------------------------------------------------------------------------
# DEFINICIÓN DE PÁGINAS
# ---------------------------------------------------------------------------
pagina_bienvenida = st.Page(
    "pages/00_Bienvenida.py", title="Bienvenida", icon="🏠", default=not usuario_logueado
)
pagina_perfil = st.Page(
    "pages/01_Mi_Perfil.py", title="Mi Perfil", icon="📋"
)
pagina_rutinas = st.Page(
    "pages/02_Rutinas.py", title="Rutinas", icon="🏋️"
)
pagina_nutricion = st.Page(
    "pages/03_Nutricion.py", title="Nutrición", icon="🥗"
)
pagina_dashboard = st.Page(
    "pages/04_Dashboard.py", title="Mi Progreso", icon="📈"
)
pagina_asistente = st.Page(
    "pages/05_Asistente.py", title="Asistente ASCEND", icon="💬", default=usuario_logueado
)

# ---------------------------------------------------------------------------
# NAVEGACIÓN CONDICIONAL — esta es la pieza clave del bloqueo
# ---------------------------------------------------------------------------
if usuario_logueado:
    nav = st.navigation(
        {
            "": [pagina_bienvenida],
            "Tu cuenta": [pagina_perfil],
            "ASCEND": [pagina_rutinas, pagina_nutricion, pagina_dashboard, pagina_asistente],
        }
    )
else:
    nav = st.navigation(
        {
            "": [pagina_bienvenida],
            "Empieza aquí": [pagina_perfil],
        }
    )

nav.run()
