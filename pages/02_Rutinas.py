import streamlit as st

from utils_db import (
    obtener_equipo_usuario, guardar_equipo_usuario, obtener_perfil,
    obtener_clasificacion, registrar_interaccion_rutina, obtener_historial_rutinas,
)
from utils_rutinas import EQUIPO_OPCIONES, ZONAS_MUSCULARES, OBJETIVOS, filtrar_ejercicios, ruta_gif, generar_rutina

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
# GENERADOR DE RUTINA — la pieza que antes estaba "reservada"
# ---------------------------------------------------------------------------
st.subheader("✨ Genera tu rutina de hoy")

perfil = obtener_perfil(usuario_id) or {}
objetivo_guardado = perfil.get("objetivo", OBJETIVOS[-1])  # "Salud general" como default

objetivo_seleccionado = st.selectbox(
    "¿Cuál es tu objetivo hoy?", OBJETIVOS,
    index=OBJETIVOS.index(objetivo_guardado) if objetivo_guardado in OBJETIVOS else len(OBJETIVOS) - 1,
)

if st.button("🎲 Generar mi rutina", type="primary", use_container_width=True):
    clasificacion = obtener_clasificacion(usuario_id)
    nivel_cluster_nombre = clasificacion["nivel_cluster_nombre"] if clasificacion else None
    historial = obtener_historial_rutinas(usuario_id)

    if nivel_cluster_nombre is None:
        st.caption("ℹ️ Todavía no tienes una clasificación de nivel — se usó un rango de dificultad estándar. "
                   "Completa el test en Mi Perfil para rutinas más ajustadas a ti.")

    rutina = generar_rutina(equipo_activo, objetivo_seleccionado, nivel_cluster_nombre,
                             historial=historial, n_ejercicios=7)
    st.session_state["rutina_actual"] = rutina

if "rutina_actual" in st.session_state:
    rutina = st.session_state["rutina_actual"]

    if not rutina["ejercicios"]:
        st.warning(rutina.get("aviso", "No se pudo generar una rutina con ese equipo."))
    else:
        st.caption(
            f"Rutina generada — dificultad promedio: {rutina['dificultad_promedio_rutina']}/100 "
            f"(nivel dinámico usado: {rutina['nivel_dinamico_usado']}/100)"
        )

        for ejercicio in rutina["ejercicios"]:
            col_gif, col_info = st.columns([1, 2])
            with col_gif:
                from pathlib import Path
                ruta = Path(ejercicio["gif_path"])
                if ruta.exists():
                    st.image(str(ruta), use_container_width=True)
                else:
                    st.caption("📹 GIF pendiente")
            with col_info:
                st.markdown(f"**{ejercicio['nombre']}**")
                st.caption(f"{ejercicio['zona_muscular']} · {ejercicio['equipment']} · {ejercicio['dificultad_final']}")
                st.write(f"{ejercicio['reps']} repeticiones")
            st.divider()

        if st.button("✅ Marcar rutina como completada", type="primary", use_container_width=True):
            xp_ganado = int(rutina["dificultad_promedio_rutina"])  # XP proporcional a la dificultad, criterio simple inicial
            registrar_interaccion_rutina(
                usuario_id, rutina["rutina_id"], xp_ganado,
                dificultad_promedio_rutina=rutina["dificultad_promedio_rutina"],
            )
            st.success(f"¡Rutina completada! +{xp_ganado} XP 🎉")
            del st.session_state["rutina_actual"]
            st.rerun()

st.divider()

# ---------------------------------------------------------------------------
# BROWSER DEL CATÁLOGO — filtrado por equipo disponible + zona muscular.
# Se conserva como herramienta de exploración aparte del generador.
# ---------------------------------------------------------------------------
with st.expander("🔍 Explorar catálogo completo de ejercicios"):
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
# Pendiente: mostrar XP acumulado con obtener_xp_total(usuario_id) en algún
# lado visible de esta página (o en 04_Dashboard.py). El nivel dinámico ya
# está conectado (usa obtener_historial_rutinas + calcular_metricas_historial
# + estimar_nivel_dinamico en utils_rutinas.py).
# ═══════════════════════════════════════════════════════════════════════════
