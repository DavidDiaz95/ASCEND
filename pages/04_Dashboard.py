import streamlit as st

from utils_db import (
    obtener_xp_total, obtener_historial_rutinas, obtener_perfil, obtener_clasificacion,
    obtener_historial_nutricion,
)
from utils_rutinas import calcular_ajuste_dificultad, calcular_tope_dificultad, obtener_techo_cluster

st.set_page_config(page_title="ASCEND — Mi Progreso", page_icon="📈")

if not st.session_state.get("usuario_id"):
    st.warning("Necesitas iniciar sesión para ver tu progreso.")
    if st.button("Ir a Mi Perfil"):
        st.switch_page("pages/01_Mi_Perfil.py")
    st.stop()

usuario_id = st.session_state["usuario_id"]

st.title("📈 Mi Progreso")

# [HIDDEN] Perfilador del Usuario — funcional, no decorativo. Se deja
# colapsado y sin explicación a propósito.
with st.expander("[HIDDEN] Perfilador del Usuario"):
    clasificacion = obtener_clasificacion(usuario_id)
    if clasificacion:
        st.write(f"**Cluster:** {clasificacion['nivel_cluster_nombre']} (id interno: {clasificacion['nivel_cluster']})")
        st.write(f"**Modelo usado:** {clasificacion.get('modelo_usado')}")
        st.json(clasificacion)
    else:
        st.warning("Este usuario todavía no tiene una clasificación guardada.")

    st.divider()
    historial_debug = obtener_historial_rutinas(usuario_id)
    n_facil = sum(1 for h in historial_debug if h.get("feedback_dificultad") == "facil")
    n_bien = sum(1 for h in historial_debug if h.get("feedback_dificultad") == "bien")
    n_dificil = sum(1 for h in historial_debug if h.get("feedback_dificultad") == "dificil")
    cluster_nombre = clasificacion["nivel_cluster_nombre"] if clasificacion else None
    st.write(f"**Feedback registrado:** fácil={n_facil} · bien={n_bien} · difícil={n_dificil}")
    st.write(f"**Ajuste de dificultad calculado:** {calcular_ajuste_dificultad(historial_debug):+.1f}")
    st.write(f"**Techo del cluster (con expansión):** {obtener_techo_cluster(cluster_nombre, historial_debug):.1f}")
    st.write(f"**Tope progresivo actual:** {calcular_tope_dificultad(cluster_nombre, historial_debug):.1f}")

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

st.divider()
st.subheader("Historial de nutrición")
historial_nutricion = obtener_historial_nutricion(usuario_id)
if historial_nutricion:
    calorias_registradas = [h["detalle"].get("calorias") for h in historial_nutricion if h["detalle"].get("calorias")]
    xp_nutricion_total = sum(h["xp_ganado"] for h in historial_nutricion)

    col_comidas, col_calorias, col_xp_nutricion = st.columns(3)
    with col_comidas:
        st.metric("Comidas registradas", len(historial_nutricion))
    with col_calorias:
        promedio_calorias = round(sum(calorias_registradas) / len(calorias_registradas)) if calorias_registradas else "—"
        st.metric("Calorías promedio/comida", promedio_calorias)
    with col_xp_nutricion:
        st.metric("XP ganado en nutrición", xp_nutricion_total)

    filas_tabla = [
        {
            "Fecha": h["registrado_en"], "Comida": h["detalle"].get("titulo", "—"),
            "Calorías": h["detalle"].get("calorias", "—"), "Proteína (g)": h["detalle"].get("proteina_g", "—"),
            "XP": h["xp_ganado"],
        }
        for h in historial_nutricion
    ]
    st.dataframe(filas_tabla, use_container_width=True)
else:
    st.caption("Todavía no registras ninguna comida — ve a Nutrición para buscar opciones.")

# ═══════════════════════════════════════════════════════════════════════════
# RESERVADO — EN DESARROLLO
# ═══════════════════════════════════════════════════════════════════════════
# Piezas que faltan (ver roadmap):
#   1. Gráfica de XP en el tiempo (Plotly, línea acumulada por semana,
#      separando rutinas vs. nutrición para ver de dónde viene el progreso).
#   2. Sistema de niveles: definir tabla xp_por_nivel y mostrar barra de
#      progreso hacia el siguiente nivel (esto es lo único visible al
#      usuario — nunca el nombre del clúster).
#   3. Preferencias/restricciones nutricionales del usuario (vegetariano,
#      alergias, meta calórica) — la "tabla de clientes" de dietas.
# ═══════════════════════════════════════════════════════════════════════════
st.info("🚧 Gráficas de progreso y sistema de niveles — próxima pieza a desarrollar.")
