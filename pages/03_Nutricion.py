import streamlit as st

st.set_page_config(page_title="ASCEND — Nutrición", page_icon="🥗")

if not st.session_state.get("usuario_id"):
    st.warning("Necesitas iniciar sesión para ver tu plan de nutrición.")
    if st.button("Ir a Mi Perfil"):
        st.switch_page("pages/01_Mi_Perfil.py")
    st.stop()

st.title("🥗 Nutrición")
st.caption("Aquí vivirá tu plan de alimentación y el registro de tus comidas.")

# ═══════════════════════════════════════════════════════════════════════════
# RESERVADO — EN DESARROLLO
# ═══════════════════════════════════════════════════════════════════════════
# Piezas que faltan (ver roadmap):
#   1. Definir objetivo nutricional (bajar de peso / mantener / ganar masa)
#      — puede ir ligado al "objetivo del usuario" que ya maneja el asistente.
#   2. Calculadora de requerimiento calórico básico (Mifflin-St Jeor con los
#      datos que ya tenemos en perfiles: peso, estatura, edad, sexo).
#   3. Registro de comidas -> registrar_interaccion_nutricion(usuario_id,
#      tipo, detalle) de utils_db.py, ya está listo para recibir esto.
#   4. Historial/resumen semanal en el Dashboard.
# ═══════════════════════════════════════════════════════════════════════════
st.info("🚧 Sección en construcción — próxima pieza a desarrollar.")
