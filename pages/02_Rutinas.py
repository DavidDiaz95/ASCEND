from collections import Counter
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from utils_db import (
    obtener_equipo_usuario, guardar_equipo_usuario, obtener_perfil,
    obtener_clasificacion, registrar_interaccion_rutina, obtener_historial_rutinas,
    obtener_frecuencia_zonas_reciente, guardar_rutina_personalizada,
    obtener_rutina_personalizada,
)
from utils_rutinas import (
    EQUIPO_OPCIONES, ZONAS_MUSCULARES, OBJETIVOS,
    filtrar_ejercicios, ruta_gif, generar_menu_rutinas, generar_calentamiento,
    formatear_features_ejercicio, obtener_ejercicio_por_id,
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
    """Mismo patrón de cronómetro visual (JS puro) que ya usas en
    01_Mi_Perfil.py — el avance real de la rutina lo controla el botón de
    Streamlit de abajo, no este timer."""
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


def finalizar_rutina(feedback: str) -> None:
    """Guarda la interacción completa (XP, dificultad, n_ejercicios, zonas,
    objetivo Y el feedback del usuario) y limpia el estado de ejecución."""
    ejecucion = st.session_state["ejecucion"]
    secuencia = ejecucion["secuencia"]
    principales = [e for e in secuencia if e["tipo"] == "principal"]
    n_ejercicios = len(principales)
    zonas_json = dict(Counter(e["zona_muscular"] for e in principales))
    xp_ganado = int(ejecucion["dificultad_promedio_rutina"])

    registrar_interaccion_rutina(
        usuario_id, ejecucion["rutina_id"], xp_ganado,
        dificultad_promedio_rutina=ejecucion["dificultad_promedio_rutina"],
        n_ejercicios=n_ejercicios, zonas_json=zonas_json,
        objetivo=ejecucion["objetivo"], feedback_dificultad=feedback,
    )
    print(
        f"[ASCEND][rutina_completada] usuario={st.session_state.get('username')} "
        f"rutina={ejecucion['rutina_id']} etiqueta={ejecucion['etiqueta']} "
        f"n_ejercicios={n_ejercicios} zonas={zonas_json} xp={xp_ganado} feedback={feedback}"
    )
    st.session_state["rutina_completada_xp"] = xp_ganado
    del st.session_state["ejecucion"]
    st.session_state.pop("menu_rutinas_clave", None)  # se regenera con el nuevo historial/feedback
    st.rerun()


# ═══════════════════════════════════════════════════════════════════════════
# SI HAY UNA RUTINA EN EJECUCIÓN — pantalla de enfoque, se oculta el resto.
# ═══════════════════════════════════════════════════════════════════════════
if st.session_state.get("ejecucion"):
    ejecucion = st.session_state["ejecucion"]
    secuencia = ejecucion["secuencia"]
    indice = ejecucion["indice"]
    fase = ejecucion["fase"]

    if fase == "feedback":
        st.subheader("🏁 ¡Rutina terminada!")
        st.write("¿Cómo se sintió la dificultad? Esto ajusta tus próximas recomendaciones.")
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("😌 Fácil", use_container_width=True):
                finalizar_rutina("facil")
        with col2:
            if st.button("🙂 Bien", use_container_width=True, type="primary"):
                finalizar_rutina("bien")
        with col3:
            if st.button("😖 Difícil", use_container_width=True):
                finalizar_rutina("dificil")
        st.stop()

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
        st.write(f"**{ejercicio_actual.get('series', '—')} series × {ejercicio_actual['reps']} repeticiones**")
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
        with col2:
            if es_ultimo:
                if st.button("🏁 Terminar rutina", type="primary", use_container_width=True):
                    st.session_state["ejecucion"]["fase"] = "feedback"
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

    st.stop()


# ═══════════════════════════════════════════════════════════════════════════
# SIN RUTINA EN EJECUCIÓN
# ═══════════════════════════════════════════════════════════════════════════
if "rutina_completada_xp" in st.session_state:
    st.success(f"¡Rutina completada! +{st.session_state.pop('rutina_completada_xp')} XP 🎉")

# ---------------------------------------------------------------------------
# EQUIPO DISPONIBLE
# ---------------------------------------------------------------------------
equipo_guardado = obtener_equipo_usuario(usuario_id)
primera_vez_equipo = not equipo_guardado
if not equipo_guardado:
    equipo_guardado = ["peso corporal"]

with st.expander("🧰 Tu equipo disponible", expanded=primera_vez_equipo):
    st.caption("Selecciona todo lo que tengas acceso a usar. Puedes volver a actualizarlo cuando compres equipo nuevo.")
    equipo_seleccionado = st.multiselect(
        "Equipo disponible", options=EQUIPO_OPCIONES, default=equipo_guardado,
        label_visibility="collapsed",
    )
    if st.button("Guardar mi equipo", type="primary"):
        guardar_equipo_usuario(usuario_id, equipo_seleccionado)
        st.session_state.pop("menu_rutinas_clave", None)
        st.success("¡Equipo actualizado!")
        st.rerun()

equipo_activo = obtener_equipo_usuario(usuario_id) or ["peso corporal"]

st.divider()

# ---------------------------------------------------------------------------
# MENÚ DE RUTINAS RECOMENDADAS
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

    # Señal pedida explícitamente: ver en consola (o abajo, en el
    # Dashboard) qué cluster se está usando de verdad para recomendar.
    print(f"tu cluster es {nivel_cluster_nombre}")
    print(
        f"[ASCEND][generar_menu] usuario={st.session_state.get('username')} "
        f"objetivo={objetivo_seleccionado} equipo={equipo_activo} "
        f"n_rutinas_historial={len(historial)} frecuencia_zonas={frecuencia_zonas}"
    )

    if nivel_cluster_nombre is None:
        st.caption(
            "ℹ️ Todavía no tienes una clasificación de nivel — se usó un rango de dificultad estándar. "
            "Completa el test en Mi Perfil para rutinas más ajustadas a ti."
        )
    else:
        st.caption(f"🔎 Recomendando según tu cluster: **{nivel_cluster_nombre}** (ver también consola/servidor)")

    st.session_state["menu_rutinas"] = generar_menu_rutinas(
        equipo_activo, objetivo_seleccionado, nivel_cluster_nombre,
        historial=historial, frecuencia_zonas=frecuencia_zonas, n_ejercicios=8,
    )
    st.session_state["menu_rutinas_clave"] = clave_menu_actual

if st.button("🔄 Actualizar recomendaciones"):
    st.session_state.pop("menu_rutinas_clave", None)
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
                    f"(tope actual: {rutina['tope_dificultad_usado']}/100) · match {rutina['similitud_promedio']:.2f}"
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
# RUTINA PERSONALIZADA — UNA sola por usuario (crear = editar la misma).
# ---------------------------------------------------------------------------
with st.expander("🛠️ Tu rutina personalizada"):
    st.caption(
        "Arma tu propia rutina eligiendo ejercicios del catálogo. Solo puedes tener UNA — "
        "si guardas de nuevo, reemplaza a la anterior (así no se acumulan mil rutinas)."
    )

    rutina_actual = obtener_rutina_personalizada(usuario_id)
    catalogo_filtrado = filtrar_ejercicios(equipo_activo)
    opciones_ejercicios = [f"{row.id} — {row.name}" for row in catalogo_filtrado.itertuples()]

    ids_previos = {ex["id"] for ex in rutina_actual["ejercicios"]} if rutina_actual else set()
    defaults_previos = [op for op in opciones_ejercicios if op.split(" — ")[0] in ids_previos]

    nombre_rutina = st.text_input(
        "Nombre de tu rutina", value=rutina_actual["nombre"] if rutina_actual else "Mi rutina"
    )
    seleccion = st.multiselect(
        "Ejercicios (según tu equipo disponible)", options=opciones_ejercicios, default=defaults_previos,
    )

    series_reps_previos = {
        ex["id"]: (ex.get("series", 3), ex.get("reps", 12)) for ex in (rutina_actual["ejercicios"] if rutina_actual else [])
    }

    ejercicios_configurados = []
    for opcion in seleccion:
        ejercicio_id = opcion.split(" — ")[0]
        series_default, reps_default = series_reps_previos.get(ejercicio_id, (3, 12))
        col_nombre, col_series, col_reps = st.columns([2, 1, 1])
        with col_nombre:
            st.write(opcion.split(" — ", 1)[1])
        with col_series:
            series_val = st.number_input("Series", min_value=1, max_value=10, value=series_default, key=f"series_{ejercicio_id}")
        with col_reps:
            reps_val = st.number_input("Reps", min_value=1, max_value=50, value=reps_default, key=f"reps_{ejercicio_id}")
        ejercicios_configurados.append({"id": ejercicio_id, "series": int(series_val), "reps": int(reps_val)})

    col_guardar, col_empezar = st.columns(2)
    with col_guardar:
        if st.button("💾 Guardar mi rutina", use_container_width=True, disabled=not ejercicios_configurados):
            guardar_rutina_personalizada(usuario_id, nombre_rutina, ejercicios_configurados)
            st.success("¡Rutina personalizada guardada!")
            st.rerun()
    with col_empezar:
        if rutina_actual and st.button("▶️ Empezar mi rutina", use_container_width=True, type="primary"):
            principales = []
            for ex_guardado in rutina_actual["ejercicios"]:
                completo = obtener_ejercicio_por_id(ex_guardado["id"])
                if completo:
                    completo["series"] = ex_guardado.get("series", 3)
                    completo["reps"] = ex_guardado.get("reps", 12)
                    principales.append(completo)

            zonas_de_la_rutina = list({ex["zona_muscular"] for ex in principales})
            calentamiento = generar_calentamiento(equipo_activo, zonas_de_la_rutina)
            dificultad_promedio = (
                sum(ex["dificultad_continua"] for ex in principales) / len(principales) if principales else 0.0
            )

            import hashlib as _hashlib
            from datetime import datetime as _datetime
            rutina_id = _hashlib.sha1(
                (usuario_id + "personalizada" + _datetime.now().isoformat()).encode()
            ).hexdigest()[:12]

            st.session_state["ejecucion"] = {
                "rutina_id": rutina_id,
                "etiqueta": "🛠️ Personalizada",
                "objetivo": objetivo_seleccionado,
                "dificultad_promedio_rutina": round(dificultad_promedio, 1),
                "secuencia": (
                    [{"tipo": "calentamiento", **ex} for ex in calentamiento]
                    + [{"tipo": "principal", **ex} for ex in principales]
                ),
                "indice": 0,
                "fase": "ejercicio",
            }
            st.rerun()

st.divider()

# ---------------------------------------------------------------------------
# BROWSER DEL CATÁLOGO — exploración libre, con features numéricas.
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
# zonas_json / dificultad_promedio_rutina / feedback a través del tiempo en
# 04_Dashboard.py — todos los datos ya se están guardando en cada
# "Terminar rutina", solo falta graficarlos.
# ═══════════════════════════════════════════════════════════════════════════
