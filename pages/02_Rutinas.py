import streamlit as st

st.set_page_config(page_title="ASCEND — Rutinas", page_icon="🏋️")

# ---------------------------------------------------------------------------
# GUARDIA — defensa en profundidad. main.py ya oculta esta página del
# sidebar sin sesión, pero si alguien entra por URL directa, la bloqueamos
# aquí también.
# ---------------------------------------------------------------------------
if not st.session_state.get("usuario_id"):
    st.warning("Necesitas iniciar sesión para ver tus rutinas.")
    if st.button("Ir a Mi Perfil"):
        st.switch_page("pages/01_Mi_Perfil.py")
    st.stop()

st.title("🏋️ Rutinas")
st.caption("Aquí vivirán tus rutinas asignadas según tu nivel de XP y tu clúster oculto.")

# ═══════════════════════════════════════════════════════════════════════════
# RESERVADO — EN DESARROLLO
# ═══════════════════════════════════════════════════════════════════════════
# Piezas que faltan (ver roadmap):
#   1. Catálogo de rutinas (por ahora puede ser un dict/JSON estático en
#      Assets/rutinas.json: id, nombre, dificultad, grupo muscular, xp_base).
#   2. Selección de rutina según nivel_cluster (obtener_clasificacion) sin
#      exponerlo — solo usarlo para decidir dificultad sugerida.
#   3. Botón "Marcar como completada" -> registrar_interaccion_rutina(...)
#      de utils_db.py, que ya está listo para recibir esto.
#   4. Mostrar XP acumulado con obtener_xp_total(usuario_id).
# ═══════════════════════════════════════════════════════════════════════════
st.info("🚧 Sección en construcción — próxima pieza a desarrollar.")
