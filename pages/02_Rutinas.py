import streamlit as st

from utils_db import obtener_equipo_usuario, guardar_equipo_usuario, obtener_perfil
from utils_rutinas import EQUIPO_OPCIONES, ZONAS_MUSCULARES, filtrar_ejercicios, ruta_gif

st.set_page_config(page_title="ASCEND — Rutinas", page_icon="🏋️")

if not st.session_state.get("usuario_id"):
    st.warning("Necesitas iniciar sesión para ver tus rutinas.")
    if st.button("Ir a Mi Perfil"):
        st.switch_page("pages/01_Mi_Perfil.py")
    st.stop()

usuario_id = st.session_state["usuario_id"]

st.title("🏋️ Rutinas")

# ---------------------------------------------------------------------------
# EQUIPO DISPONIBLE — independiente del perfil físico. Se guarda apenas
# cambia, así que si compras equipo nuevo lo actualizas aquí en cualquier
# momento sin tener que rehacer tus tests.
# ---------------------------------------------------------------------------
equipo_guardado = obtener_equipo_usuario(usuario_id)
primera_vez = not equipo_guardado
if not equipo_guardado:
    equipo_guardado = ["peso corporal"]  # default razonable la primera vez

with st.expander("🧰 Tu equipo disponible", expanded=primera_vez):
    st.caption("Selecciona todo lo que tengas acceso a usar. Puedes volver a actualizarlo cuando compres equipo nuevo.")
    equipo_seleccionado = st.multiselect(
        "Equipo disponible", options=EQUIPO_OPCIONES, default=equipo_guardado,
        label_visibility="collapsed",
    )
    if st.button("Guardar mi equipo", type="primary"):
        guardar_equipo_usuario(usuario_id, equipo_seleccionado)
        st.success("¡Equipo actualizado!")
        st.rerun()

equipo_activo = obtener_equipo_usuario(usuario_id) or ["peso corporal"]

st.divider()

# ---------------------------------------------------------------------------
# BROWSER DEL CATÁLOGO — filtrado por equipo disponible + zona muscular.
# ---------------------------------------------------------------------------
col_zona, col_dificultad = st.columns(2)
with col_zona:
    zona = st.selectbox("Zona muscular", ["Todas"] + ZONAS_MUSCULARES)
with col_dificultad:
    dificultad_max = st.selectbox("Dificultad máxima", ["principiante", "intermedio", "experto"], index=2)

ejercicios = filtrar_ejercicios(equipo_activo, zona_muscular=zona, dificultad_max=dificultad_max)

st.caption(f"{len(ejercicios)} ejercicios disponibles con tu equipo actual.")

if ejercicios.empty:
    st.info("No hay ejercicios que coincidan. Prueba agregando más equipo o subiendo la dificultad máxima.")
else:
    for _, ejercicio in ejercicios.head(20).iterrows():
        col_gif, col_info = st.columns([1, 2])
        with col_gif:
            ruta = ruta_gif(ejercicio)
            if ruta.exists():
                st.image(str(ruta), use_container_width=True)
            else:
                st.caption("📹 GIF pendiente")
        with col_info:
            st.markdown(f"**{ejercicio['name']}**")
            st.caption(
                f"{ejercicio['zona_muscular']} · {ejercicio['equipment']} · {ejercicio['dificultad_final']}"
            )
        st.divider()

    if len(ejercicios) > 20:
        st.caption(f"Mostrando 20 de {len(ejercicios)}. Afina los filtros para ver más específico.")

# ═══════════════════════════════════════════════════════════════════════════
# RESERVADO — EN DESARROLLO
# ═══════════════════════════════════════════════════════════════════════════
# Piezas que faltan (ver roadmap):
#   1. generar_rutina() en utils_rutinas.py — arma una rutina COMPLETA (no
#      solo lista ejercicios sueltos), usando objetivo + equipo + tope de
#      dificultad ligado al nivel_cluster oculto.
#   2. Botón "Marcar como completada" -> registrar_interaccion_rutina(...)
#      de utils_db.py, que ya está listo para recibir esto.
#   3. Mostrar XP acumulado con obtener_xp_total(usuario_id).
# ═══════════════════════════════════════════════════════════════════════════
st.info("🚧 Generador de rutina completa (no solo catálogo) — próxima pieza a desarrollar.")
