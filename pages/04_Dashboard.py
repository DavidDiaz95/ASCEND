import streamlit as st

from utils_db import obtener_xp_total, obtener_historial_rutinas, obtener_perfil

st.set_page_config(page_title="ASCEND — Mi Progreso", page_icon="📈")

if not st.session_state.get("usuario_id"):
    st.warning("Necesitas iniciar sesión para ver tu progreso.")
    if st.button("Ir a Mi Perfil"):
        st.switch_page("pages/01_Mi_Perfil.py")
    st.stop()

usuario_id = st.session_state["usuario_id"]

st.title("📈 Mi Progreso")

col_xp, col_perfil = st.columns(2)
with col_xp:
    xp_total = obtener_xp_total(usuario_id)
    st.metric("XP acumulado", xp_total)
with col_perfil:
    perfil = obtener_perfil(usuario_id)
    if perfil:
        st.metric("Última actualización de perfil", perfil["actualizado_en"])
    else:
        st.metric("Perfil físico", "Sin registrar aún")

st.divider()
st.subheader("Historial de rutinas")
historial = obtener_historial_rutinas(usuario_id)
if historial:
    st.dataframe(historial, use_container_width=True)
else:
    st.caption("Todavía no completas ninguna rutina — ¡anímate a hacer la primera!")

# ═══════════════════════════════════════════════════════════════════════════
# RESERVADO — EN DESARROLLO
# ═══════════════════════════════════════════════════════════════════════════
# Piezas que faltan (ver roadmap):
#   1. Gráfica de XP en el tiempo (Plotly, línea acumulada por semana).
#   2. Sistema de niveles: definir tabla xp_por_nivel y mostrar barra de
#      progreso hacia el siguiente nivel (esto es lo único visible al
#      usuario — nunca el nombre del clúster).
#   3. Resumen de nutrición una vez que exista 03_Nutricion.py funcional.
# ═══════════════════════════════════════════════════════════════════════════
st.info("🚧 Gráficas de progreso y sistema de niveles — próxima pieza a desarrollar.")
