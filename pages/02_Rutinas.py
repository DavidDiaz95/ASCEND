from collections import Counter
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from utils_db import (
    obtener_equipo_usuario, guardar_equipo_usuario, obtener_perfil,
    obtener_clasificacion, registrar_interaccion_rutina, obtener_historial_rutinas,
    obtener_frecuencia_zonas_reciente,
)
from utils_rutinas import (
    EQUIPO_OPCIONES, ZONAS_MUSCULARES, OBJETIVOS,
    filtrar_ejercicios, ruta_gif, generar_menu_rutinas, generar_calentamiento,
    formatear_features_ejercicio,
)

st.set_page_config(page_title="ASCEND — Rutinas", page_icon="🏋️")

if not st.session_state.get("usuario_id"):
    st.warning("Necesitas iniciar sesión para ver tus rutinas.")
    if st.button("Ir a Mi Perfil"):
        st.switch_page("pages/01_Mi_Perfil.py")
    st.stop()

usuario_id = st.session_state["usuario_id"]

st.title("🏋️ Rutinas")


def descanso_html(duracion_seg: int = 60) -> str:
    """Mismo patrón de cronómetro visual (JS puro, sin comunicación de vuelta
    a Python) que ya usas en 01_Mi_Perfil.py — el avance real de la rutina
    lo controla el botón de Streamlit de abajo, no este timer."""
    return f"""
    <div style="font-family: sans-serif; text-align: center;">
      <div id="caja" style="width: 100%; height: 90px; background-color: #006a20;
                             color: white; display: flex; align-items: center;
                             justify-content: center; border-radius: 10px;
                             font-size: 20px;">
        Descansando... {duracion_seg}s
      </div>
    </div>
    <script>
      const caja = document.getElementById("caja");
      let segundosRestantes = {duracion_seg};
      const intervalo = setInterval(() => {{
        segundosRestantes--;
        if (segundosRestantes > 0) {{
          caja.innerText = "Descansando... " + segundosRestantes + "s";
        }} else {{
          clearInterval(intervalo);
          caja.style.backgroundColor = "#cc3333";
          caja.innerText = "¡Listo! Da clic en 'Continuar' abajo 👇";
        }}
      }}, 1000);
    </script>
    """


# ═══════════════════════════════════════════════════════════════════════════
# SI HAY UNA RUTINA EN EJECUCIÓN — se muestra SOLO eso (pantalla de enfoque),
# se oculta el resto para no distraer a media rutina.
# ═══════════════════════════════════════════════════════════════════════════
if st.session_state.get("ejecucion"):
    ejecucion = st.session_state["ejecucion"]
    secuencia = ejecucion["secuencia"]
    indice = ejecucion["indice"]
    fase = ejecucion["fase"]
    ejercicio_actual = secuencia[indice]
    es_ultimo = indice == len(secuencia) - 1

    st.subheader(f"{ejecucion['etiqueta']} — en progreso")
    st.progress((indice + 1) / len(secuencia))
    etiqueta_tipo = "🔥 Calentamiento" if ejercicio_actual["tipo"] == "calentamiento" else "💪 Ejercicio principal"
    st.caption(f"{etiqueta_tipo} — {indice + 1} de {len(secuencia)}")

    col_gif, col_info = st.columns([1, 1.3])
    with col_gif:
        ruta = Path(ejercicio_actual["gif_path"])
        if ruta.exists():
            st.image(str(ruta), use_container_width=True)
        else:
            st.caption("📹 GIF pendiente")
    with col_info:
        st.markdown(f"### {ejercicio_actual['nombre']}")
        st.write(f"**{ejercicio_actual['reps']} repeticiones**")
        st.caption(f"{ejercicio_actual['zona_muscular']} · {ejercicio_actual['equipment']}")
        st.caption(formatear_features_ejercicio(ejercicio_actual))

    st.divider()

    if fase == "ejercicio":
        col1, col2 = st.columns(2)
        with col1:
            if not es_ultimo:
                if st.button("😌 Descansar 60s", use_container_width=True):
                    st.session_state["ejecucion"]["fase"] = "descanso"
                    st.rerun()
            else:
                st.write("")
        with col2:
            if es_ultimo:
                if st.button("🏁 Terminar rutina", type="primary", use_container_width=True):
                    principales = [e for e in secuencia if e["tipo"] == "principal"]
                    n_ejercicios = len(principales)
                    zonas_json = dict(Counter(e["zona_muscular"] for e in principales))
                    xp_ganado = int(ejecucion["dificultad_promedio_rutina"])

                    registrar_interaccion_rutina(
                        usuario_id, ejecucion["rutina_id"], xp_ganado,
                        dificultad_promedio_rutina=ejecucion["dificultad_promedio_rutina"],
                        n_ejercicios=n_ejercicios, zonas_json=zonas_json,
                        objetivo=ejecucion["objetivo"],
                    )
                    print(
                        f"[ASCEND][rutina_completada] usuario={st.session_state.get('username')} "
                        f"rutina={ejecucion['rutina_id']} etiqueta={ejecucion['etiqueta']} "
                        f"n_ejercicios={n_ejercicios} zonas={zonas_json} xp={xp_ganado}"
                    )
                    st.session_state["rutina_completada_xp"] = xp_ganado
                    del st.session_state["ejecucion"]
                    st.session_state.pop("menu_rutinas", None)  # se regenera con el nuevo historial
                    st.rerun()
            else:
                if st.button("⏭️ Saltar descanso, siguiente", use_container_width=True):
                    st.session_state["ejecucion"]["indice"] += 1
                    st.rerun()

    elif fase == "descanso":
        components.html(descanso_html(60), height=110)
        if st.button("▶️ Ya descansé, continuar", type="primary", use_container_width=True):
            st.session_state["ejecucion"]["indice"] += 1
            st.session_state["ejecucion"]["fase"] = "ejercicio"
            st.rerun()

    st.divider()
    if st.button("❌ Cancelar rutina (no se guarda)"):
        del st.session_state["ejecucion"]
        st.rerun()

    st.stop()  # nada del menú se muestra mientras hay una rutina activa


# ═══════════════════════════════════════════════════════════════════════════
# SIN RUTINA EN EJECUCIÓN — mensaje de la última completada (si aplica)
# ═══════════════════════════════════════════════════════════════════════════
if "rutina_completada_xp" in st.session_state:
    st.success(f"¡Rutina completada! +{st.session_state.pop('rutina_completada_xp')} XP 🎉")

# ---------------------------------------------------------------------------
# EQUIPO DISPONIBLE — independiente del perfil físico. Se guarda apenas
# cambia, así que si compras equipo nuevo lo actualizas aquí en cualquier
# momento sin tener que rehacer tus tests.
# ---------------------------------------------------------------------------
equipo_guardado = obtener_equipo_usuario(usuario_id)
primera_vez_equipo = not equipo_guardado
if not equipo_guardado:
    equipo_guardado = ["peso corporal"]  # default razonable la primera vez

with st.expander("🧰 Tu equipo disponible", expanded=primera_vez_equipo):
    st.caption("Selecciona todo lo que tengas acceso a usar. Puedes volver a actualizarlo cuando compres equipo nuevo.")
    equipo_seleccionado = st.multiselect(
        "Equipo disponible", options=EQUIPO_OPCIONES, default=equipo_guardado,
        label_visibility="collapsed",
    )
    if st.button("Guardar mi equipo", type="primary"):
        guardar_equipo_usuario(usuario_id, equipo_seleccionado)
        st.session_state.pop("menu_rutinas", None)  # el equipo cambió, hay que regenerar
        st.success("¡Equipo actualizado!")
        st.rerun()

equipo_activo = obtener_equipo_usuario(usuario_id) or ["peso corporal"]

st.divider()

# ---------------------------------------------------------------------------
# MENÚ DE RUTINAS RECOMENDADAS — se genera solo (sin que el usuario tenga
# que pedirlo), y se regenera automáticamente si cambia equipo u objetivo.
# ---------------------------------------------------------------------------
st.subheader("✨ Tus rutinas recomendadas")

perfil = obtener_perfil(usuario_id) or {}
objetivo_guardado = perfil.get("objetivo") or OBJETIVOS[-1]

objetivo_seleccionado = st.selectbox(
    "¿Cuál es tu objetivo hoy?", OBJETIVOS,
    index=OBJETIVOS.index(objetivo_guardado) if objetivo_guardado in OBJETIVOS else len(OBJETIVOS) - 1,
)

clave_menu_actual = (tuple(sorted(equipo_activo)), objetivo_seleccionado)

if st.session_state.get("menu_rutinas_clave") != clave_menu_actual:
    clasificacion = obtener_clasificacion(usuario_id)
    nivel_cluster_nombre = clasificacion["nivel_cluster_nombre"] if clasificacion else None
    historial = obtener_historial_rutinas(usuario_id)
    frecuencia_zonas = obtener_frecuencia_zonas_reciente(usuario_id)

    # Debug de servidor — para verificar en la terminal qué cluster/zonas
    # está usando el motor al armar las recomendaciones.
    print(
        f"[ASCEND][generar_menu] usuario={st.session_state.get('username')} "
        f"cluster={nivel_cluster_nombre} objetivo={objetivo_seleccionado} "
        f"equipo={equipo_activo} frecuencia_zonas={frecuencia_zonas}"
    )

    if nivel_cluster_nombre is None:
        st.caption(
            "ℹ️ Todavía no tienes una clasificación de nivel — se usó un rango de dificultad estándar. "
            "Completa el test en Mi Perfil para rutinas más ajustadas a ti."
        )

    st.session_state["menu_rutinas"] = generar_menu_rutinas(
        equipo_activo, objetivo_seleccionado, nivel_cluster_nombre,
        historial=historial, frecuencia_zonas=frecuencia_zonas, n_ejercicios=7,
    )
    st.session_state["menu_rutinas_clave"] = clave_menu_actual

if st.button("🔄 Actualizar recomendaciones"):
    st.session_state.pop("menu_rutinas_clave", None)  # fuerza regenerar aunque nada cambió
    st.rerun()

menu_rutinas = st.session_state.get("menu_rutinas", [])

if not menu_rutinas:
    st.info("No se encontraron rutinas con tu equipo actual. Agrega más equipo arriba.")
else:
    for rutina in menu_rutinas:
        with st.container(border=True):
            col_titulo, col_boton = st.columns([2.5, 1])
            with col_titulo:
                st.markdown(f"**{rutina['etiqueta']}**")
                zonas_resumen = ", ".join(f"{z} ({n})" for z, n in rutina["zonas_contadas"].items())
                st.caption(
                    f"{len(rutina['ejercicios'])} ejercicios · dificultad {rutina['dificultad_promedio_rutina']}/100 "
                    f"· match {rutina['similitud_promedio']:.2f}"
                )
                st.caption(f"Zonas: {zonas_resumen}")
            with col_boton:
                if st.button("▶️ Empezar", key=f"empezar_{rutina['rutina_id']}", use_container_width=True):
                    calentamiento = generar_calentamiento(equipo_activo, list(rutina["zonas_contadas"].keys()))
                    secuencia = (
                        [{"tipo": "calentamiento", **ex} for ex in calentamiento]
                        + [{"tipo": "principal", **ex} for ex in rutina["ejercicios"]]
                    )
                    st.session_state["ejecucion"] = {
                        "rutina_id": rutina["rutina_id"],
                        "etiqueta": rutina["etiqueta"],
                        "objetivo": rutina["objetivo"],
                        "dificultad_promedio_rutina": rutina["dificultad_promedio_rutina"],
                        "secuencia": secuencia,
                        "indice": 0,
                        "fase": "ejercicio",
                    }
                    st.rerun()

st.divider()

# ---------------------------------------------------------------------------
# BROWSER DEL CATÁLOGO — exploración libre, separada del generador. Muestra
# las características numéricas de cada ejercicio para poder auditar a
# simple vista que el catálogo está bien etiquetado.
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
                st.caption(f"{ejercicio['zona_muscular']} · {ejercicio['equipment']}")
                st.caption(formatear_features_ejercicio(ejercicio.to_dict()))
            st.divider()

        if len(ejercicios) > 20:
            st.caption(f"Mostrando 20 de {len(ejercicios)}. Afina los filtros para ver más específico.")

# ═══════════════════════════════════════════════════════════════════════════
# RESERVADO — EN DESARROLLO
# ═══════════════════════════════════════════════════════════════════════════
# Pendiente: mostrar XP acumulado (obtener_xp_total) y la evolución de
# zonas_json / dificultad_promedio_rutina a través del tiempo en
# 04_Dashboard.py — todos los datos ya se están guardando en cada
# "Terminar rutina", solo falta graficarlos.
# ═══════════════════════════════════════════════════════════════════════════
