import time
from collections import Counter
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from utils_db import (
    obtener_equipo_usuario, guardar_equipo_usuario, obtener_perfil,
    obtener_clasificacion, registrar_interaccion_rutina, obtener_historial_rutinas,
    obtener_frecuencia_zonas_reciente, guardar_rutina_personalizada,
    obtener_rutinas_personalizadas, eliminar_rutina_personalizada,
    MAX_RUTINAS_PERSONALIZADAS,
)
from utils_rutinas import (
    EQUIPO_OPCIONES, CATEGORIAS_EQUIPO, ZONAS_MUSCULARES, OBJETIVOS,
    filtrar_ejercicios, ruta_gif, generar_menu_rutinas, generar_calentamiento,
    formatear_features_ejercicio, obtener_ejercicio_por_id, generar_menu_por_grupos,
    formatear_nombre_ejercicio, calcular_ajuste_dificultad,
)

st.set_page_config(page_title="ASCEND — Rutinas", page_icon="🏋️")

if not st.session_state.get("usuario_id"):
    st.warning("Necesitas iniciar sesión para ver tus rutinas.")
    if st.button("Ir a Mi Perfil"):
        st.switch_page("pages/01_Mi_Perfil.py")
    st.stop()

usuario_id = st.session_state["usuario_id"]

# ---------------------------------------------------------------------------
# COLORES DE MARCA (mismos que el resto de la app)
# ---------------------------------------------------------------------------
VERDE_PRIMARIO = "#006a20"
VERDE_CLARO = "#d8efdc"
TEXTO_OSCURO = "#141d16"
ROJO_ALERTA = "#cc3333"


def encabezado_seccion(texto: str, color: str = VERDE_PRIMARIO) -> None:
    st.markdown(
        f"""
        <div style="background-color: {color}; color: white; padding: 10px 16px;
                    border-radius: 8px; font-weight: 600; font-size: 18px; margin-bottom: 12px;">
            {texto}
        </div>
        """,
        unsafe_allow_html=True,
    )


st.markdown(
    f"<h1 style='color: {TEXTO_OSCURO};'>🏋️ Rutinas</h1>", unsafe_allow_html=True,
)


def descanso_html(duracion_seg: int = 60) -> str:
    """Cronómetro visual + campana (tono sintetizado con Web Audio API, sin
    archivo de audio) cuando termina el descanso."""
    return f"""
    <div style="font-family: sans-serif; text-align: center;">
      <div id="caja" style="width: 100%; height: 90px; background-color: {VERDE_PRIMARIO};
                             color: white; display: flex; align-items: center;
                             justify-content: center; border-radius: 10px;
                             font-size: 20px;">
        Descansando... {duracion_seg}s
      </div>
    </div>
    <script>
      const caja = document.getElementById("caja");
      let segundosRestantes = {duracion_seg};

      function reproducirCampana() {{
        try {{
          const ctx = new (window.AudioContext || window.webkitAudioContext)();
          [880, 1320].forEach((freq, i) => {{
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.type = "sine";
            osc.frequency.value = freq;
            gain.gain.setValueAtTime(i === 0 ? 0.35 : 0.15, ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 1.4);
            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.start();
            osc.stop(ctx.currentTime + 1.4);
          }});
        }} catch (e) {{ /* navegador sin soporte de audio: se ignora */ }}
      }}

      const intervalo = setInterval(() => {{
        segundosRestantes--;
        if (segundosRestantes > 0) {{
          caja.innerText = "Descansando... " + segundosRestantes + "s";
        }} else {{
          clearInterval(intervalo);
          caja.style.backgroundColor = "{ROJO_ALERTA}";
          caja.innerText = "¡Listo! Da clic en 'Continuar' abajo 👇";
          reproducirCampana();
        }}
      }}, 1000);
    </script>
    """


def iniciar_ejecucion(rutina: dict, equipo_activo: list[str]) -> None:
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
        "serie_actual": 1,
        "fase": "ejercicio",
        "hora_inicio": time.time(),
    }
    st.rerun()


def avanzar_a_siguiente_ejercicio() -> None:
    """Pasa al siguiente ejercicio (o a la pantalla de feedback si era el
    último), reiniciando el contador de series."""
    ejecucion = st.session_state["ejecucion"]
    if ejecucion["indice"] == len(ejecucion["secuencia"]) - 1:
        ejecucion["fase"] = "feedback"
    else:
        ejecucion["indice"] += 1
        ejecucion["serie_actual"] = 1
        ejecucion["fase"] = "ejercicio"


def finalizar_rutina(feedback: str) -> None:
    """Guarda la interacción completa (XP, dificultad, n_ejercicios, zonas,
    objetivo, feedback, duración real Y los ids exactos de ejercicios —
    esto último es lo que le permite al generador rotar de verdad la
    próxima vez) y limpia el estado de ejecución."""
    ejecucion = st.session_state["ejecucion"]
    secuencia = ejecucion["secuencia"]
    principales = [e for e in secuencia if e["tipo"] == "principal"]
    n_ejercicios = len(principales)
    zonas_json = dict(Counter(e["zona_muscular"] for e in principales))
    ejercicios_ids = [e["id"] for e in principales]
    xp_ganado = int(ejecucion["dificultad_promedio_rutina"])
    duracion_segundos = int(time.time() - ejecucion.get("hora_inicio", time.time()))

    registrar_interaccion_rutina(
        usuario_id, ejecucion["rutina_id"], xp_ganado,
        dificultad_promedio_rutina=ejecucion["dificultad_promedio_rutina"],
        n_ejercicios=n_ejercicios, zonas_json=zonas_json,
        objetivo=ejecucion["objetivo"], feedback_dificultad=feedback,
        duracion_segundos=duracion_segundos, ejercicios_ids=ejercicios_ids,
    )
    print(
        f"[ASCEND][rutina_completada] usuario={st.session_state.get('username')} "
        f"rutina={ejecucion['rutina_id']} etiqueta={ejecucion['etiqueta']} "
        f"n_ejercicios={n_ejercicios} zonas={zonas_json} xp={xp_ganado} "
        f"feedback={feedback} duracion_seg={duracion_segundos}"
    )
    st.session_state["rutina_completada_xp"] = xp_ganado
    del st.session_state["ejecucion"]
    st.session_state.pop("menu_rutinas_clave", None)
    st.session_state.pop("menu_grupos_clave", None)
    st.rerun()


# ═══════════════════════════════════════════════════════════════════════════
# RUTINA EN EJECUCIÓN — pantalla de enfoque, oculta todo lo demás.
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
    series_totales = ejercicio_actual.get("series", 1)
    serie_actual = ejecucion["serie_actual"]

    encabezado_seccion(f"{ejecucion['etiqueta']} — en progreso")
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
        st.write(f"**Serie {serie_actual} de {series_totales} · {ejercicio_actual['reps']} repeticiones**")
        st.caption(f"{ejercicio_actual['zona_muscular']} · {ejercicio_actual['equipment']}")
        st.caption(formatear_features_ejercicio(ejercicio_actual))

    st.divider()

    if fase == "ejercicio":
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("😌 Descansar 60s", use_container_width=True):
                st.session_state["ejecucion"]["fase"] = "descanso"
                st.rerun()
        with col2:
            if st.button("⏭️ Siguiente", use_container_width=True):
                avanzar_a_siguiente_ejercicio()
                st.rerun()
        with col3:
            if st.button(f"✅ Serie {serie_actual}/{series_totales}", use_container_width=True, type="primary"):
                if serie_actual >= series_totales:
                    avanzar_a_siguiente_ejercicio()
                else:
                    st.session_state["ejecucion"]["serie_actual"] += 1
                st.rerun()

    elif fase == "descanso":
        components.html(descanso_html(60), height=110)
        if st.button("▶️ Ya descansé, continuar", type="primary", use_container_width=True):
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
# FILTROS Y OBJETIVO DE HOY (arriba, aplica a todo lo de abajo)
# ---------------------------------------------------------------------------
encabezado_seccion("🎯 Filtros y objetivo de hoy")

col_equipo, col_objetivo = st.columns([1.4, 1])

with col_equipo:
    equipo_guardado = obtener_equipo_usuario(usuario_id)
    primera_vez_equipo = not equipo_guardado
    if not equipo_guardado:
        equipo_guardado = ["peso corporal"]

    with st.expander("🧰 Tu equipo disponible", expanded=primera_vez_equipo):
        st.caption("Marca todo lo que tengas acceso a usar.")
        equipo_seleccionado = []
        for categoria, items in CATEGORIAS_EQUIPO.items():
            st.markdown(f"**{categoria}**")
            columnas_equipo = st.columns(3)
            for i, item in enumerate(items):
                with columnas_equipo[i % 3]:
                    marcado = st.checkbox(
                        item.capitalize(), value=item in equipo_guardado, key=f"equipo_chk_{item}",
                    )
                    if marcado:
                        equipo_seleccionado.append(item)

        if st.button("Guardar mi equipo", type="primary"):
            guardar_equipo_usuario(usuario_id, equipo_seleccionado)
            st.session_state.pop("menu_rutinas_clave", None)
            st.session_state.pop("menu_grupos_clave", None)
            st.success("¡Equipo actualizado!")
            st.rerun()

equipo_activo = obtener_equipo_usuario(usuario_id) or ["peso corporal"]

with col_objetivo:
    perfil = obtener_perfil(usuario_id) or {}
    objetivo_guardado = perfil.get("objetivo") or OBJETIVOS[-1]
    objetivo_seleccionado = st.selectbox(
        "¿Cuál es tu objetivo hoy?", OBJETIVOS,
        index=OBJETIVOS.index(objetivo_guardado) if objetivo_guardado in OBJETIVOS else len(OBJETIVOS) - 1,
    )

st.divider()

# ---------------------------------------------------------------------------
# GENERAR MENÚS (recomendadas + por grupo) — una sola vez por combinación
# de equipo/objetivo, se regenera solo si algo cambia.
# ---------------------------------------------------------------------------
clave_menu_actual = (tuple(sorted(equipo_activo)), objetivo_seleccionado)

if st.session_state.get("menu_rutinas_clave") != clave_menu_actual:
    clasificacion = obtener_clasificacion(usuario_id)
    nivel_cluster_nombre = clasificacion["nivel_cluster_nombre"] if clasificacion else None
    historial = obtener_historial_rutinas(usuario_id, limite=1000)
    frecuencia_zonas = obtener_frecuencia_zonas_reciente(usuario_id)

    print(f"tu cluster es {nivel_cluster_nombre}")
    n_facil = sum(1 for h in historial if h.get("feedback_dificultad") == "facil")
    n_dificil = sum(1 for h in historial if h.get("feedback_dificultad") == "dificil")
    n_bien = sum(1 for h in historial if h.get("feedback_dificultad") == "bien")
    print(
        f"[ASCEND][diagnostico_dificultad] usuario={st.session_state.get('username')} "
        f"n_rutinas_en_historial={len(historial)} facil={n_facil} bien={n_bien} dificil={n_dificil} "
        f"ajuste_calculado={calcular_ajuste_dificultad(historial)}"
    )

    st.session_state["menu_rutinas"] = generar_menu_rutinas(
        equipo_activo, objetivo_seleccionado, nivel_cluster_nombre,
        historial=historial, frecuencia_zonas=frecuencia_zonas, n_ejercicios=8,
    )
    st.session_state["menu_rutinas_clave"] = clave_menu_actual

if st.session_state.get("menu_grupos_clave") != tuple(sorted(equipo_activo)):
    clasificacion = obtener_clasificacion(usuario_id)
    nivel_cluster_nombre = clasificacion["nivel_cluster_nombre"] if clasificacion else None
    historial = obtener_historial_rutinas(usuario_id, limite=1000)
    st.session_state["menu_grupos"] = generar_menu_por_grupos(equipo_activo, nivel_cluster_nombre, historial=historial)
    st.session_state["menu_grupos_clave"] = tuple(sorted(equipo_activo))

menu_rutinas = st.session_state.get("menu_rutinas", [])
menu_grupos = st.session_state.get("menu_grupos", [])

# ---------------------------------------------------------------------------
# DOS COLUMNAS: recomendadas (izquierda) | por grupo muscular (derecha)
# ---------------------------------------------------------------------------
col_izq, col_der = st.columns(2)

with col_izq:
    encabezado_seccion("✨ Recomendadas para ti", color=VERDE_PRIMARIO)
    if st.button("🔄 Actualizar", key="btn_actualizar_recomendadas"):
        st.session_state.pop("menu_rutinas_clave", None)
        st.rerun()

    if not menu_rutinas:
        st.info("No se encontraron rutinas con tu equipo actual.")
    else:
        for rutina in menu_rutinas:
            with st.container(border=True):
                st.markdown(f"**{rutina['etiqueta']}**")
                zonas_resumen = ", ".join(f"{z} ({n})" for z, n in rutina["zonas_contadas"].items())
                st.caption(
                    f"{len(rutina['ejercicios'])} ejercicios · dificultad {rutina['dificultad_promedio_rutina']}/100 "
                    f"· objetivo interno {rutina['nivel_dinamico_usado']}/100"
                )
                st.caption(f"Zonas: {zonas_resumen}")
                if st.button("▶️ Empezar", key=f"empezar_{rutina['rutina_id']}", use_container_width=True):
                    iniciar_ejecucion(rutina, equipo_activo)

with col_der:
    encabezado_seccion("💪 Por grupo muscular", color=TEXTO_OSCURO)
    st.caption("Un día enfocado en una sola zona (split).")

    if not menu_grupos:
        st.info("No se encontraron rutinas por grupo con tu equipo actual.")
    else:
        for rutina in menu_grupos:
            with st.container(border=True):
                st.markdown(f"**{rutina['etiqueta']}**")
                st.caption(
                    f"{len(rutina['ejercicios'])} ejercicios · dificultad {rutina['dificultad_promedio_rutina']}/100 "
                    f"· objetivo interno {rutina['nivel_dinamico_usado']}/100"
                )
                if st.button("▶️ Empezar", key=f"empezar_grupo_{rutina['rutina_id']}", use_container_width=True):
                    iniciar_ejecucion(rutina, equipo_activo)

st.divider()

# ---------------------------------------------------------------------------
# RUTINAS PERSONALIZADAS — hasta 3, cada una con su propio slot.
# ---------------------------------------------------------------------------
encabezado_seccion("🛠️ Tus rutinas personalizadas", color=VERDE_PRIMARIO)

rutinas_guardadas = {r["slot"]: r for r in obtener_rutinas_personalizadas(usuario_id)}
catalogo_filtrado = filtrar_ejercicios(equipo_activo)
opciones_ejercicios = [f"{row.id} — {row.nombre_formateado}" for row in catalogo_filtrado.itertuples()]

tabs_slots = st.tabs([f"Rutina {slot}" for slot in range(1, MAX_RUTINAS_PERSONALIZADAS + 1)])

for slot, tab in zip(range(1, MAX_RUTINAS_PERSONALIZADAS + 1), tabs_slots):
    with tab:
        rutina_actual = rutinas_guardadas.get(slot)

        ids_previos = {ex["id"] for ex in rutina_actual["ejercicios"]} if rutina_actual else set()
        defaults_previos = [op for op in opciones_ejercicios if op.split(" — ")[0] in ids_previos]
        series_reps_previos = {
            ex["id"]: (ex.get("series", 3), ex.get("reps", 12))
            for ex in (rutina_actual["ejercicios"] if rutina_actual else [])
        }

        nombre_rutina = st.text_input(
            "Nombre", value=rutina_actual["nombre"] if rutina_actual else f"Mi rutina {slot}",
            key=f"nombre_slot_{slot}",
        )
        seleccion = st.multiselect(
            "Ejercicios", options=opciones_ejercicios, default=defaults_previos, key=f"seleccion_slot_{slot}",
        )

        ejercicios_configurados = []
        for opcion in seleccion:
            ejercicio_id = opcion.split(" — ")[0]
            series_default, reps_default = series_reps_previos.get(ejercicio_id, (3, 12))
            col_nombre, col_series, col_reps = st.columns([2, 1, 1])
            with col_nombre:
                st.write(opcion.split(" — ", 1)[1])
            with col_series:
                series_val = st.number_input(
                    "Series", min_value=1, max_value=10, value=series_default, key=f"series_{slot}_{ejercicio_id}"
                )
            with col_reps:
                reps_val = st.number_input(
                    "Reps", min_value=1, max_value=50, value=reps_default, key=f"reps_{slot}_{ejercicio_id}"
                )
            ejercicios_configurados.append({"id": ejercicio_id, "series": int(series_val), "reps": int(reps_val)})

        col_guardar, col_empezar, col_borrar = st.columns(3)
        with col_guardar:
            if st.button("💾 Guardar", key=f"guardar_slot_{slot}", use_container_width=True,
                         disabled=not ejercicios_configurados):
                guardar_rutina_personalizada(usuario_id, slot, nombre_rutina, ejercicios_configurados)
                st.success("¡Guardada!")
                st.rerun()
        with col_empezar:
            if rutina_actual and st.button("▶️ Empezar", key=f"empezar_slot_{slot}", use_container_width=True, type="primary"):
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
                    (usuario_id + f"personalizada{slot}" + _datetime.now().isoformat()).encode()
                ).hexdigest()[:12]

                st.session_state["ejecucion"] = {
                    "rutina_id": rutina_id,
                    "etiqueta": f"🛠️ {rutina_actual['nombre']}",
                    "objetivo": objetivo_seleccionado,
                    "dificultad_promedio_rutina": round(dificultad_promedio, 1),
                    "secuencia": (
                        [{"tipo": "calentamiento", **ex} for ex in calentamiento]
                        + [{"tipo": "principal", **ex} for ex in principales]
                    ),
                    "indice": 0,
                    "serie_actual": 1,
                    "fase": "ejercicio",
                    "hora_inicio": time.time(),
                }
                st.rerun()
        with col_borrar:
            if rutina_actual and st.button("🗑️ Borrar", key=f"borrar_slot_{slot}", use_container_width=True):
                eliminar_rutina_personalizada(usuario_id, slot)
                st.rerun()

st.divider()

# ---------------------------------------------------------------------------
# EXPLORAR CATÁLOGO COMPLETO
# ---------------------------------------------------------------------------
encabezado_seccion("🔍 Explorar catálogo de ejercicios", color=TEXTO_OSCURO)

with st.expander("Ver catálogo filtrable", expanded=False):
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
        LIMITE_MOSTRADO = 40
        for _, ejercicio in ejercicios.head(LIMITE_MOSTRADO).iterrows():
            col_gif, col_info = st.columns([1, 2])
            with col_gif:
                ruta = ruta_gif(ejercicio)
                if ruta.exists():
                    st.image(str(ruta), use_container_width=True)
                else:
                    st.caption("📹 GIF pendiente")
            with col_info:
                st.markdown(f"**{ejercicio['nombre_formateado']}**")
                st.caption(f"{ejercicio['zona_muscular']} · {ejercicio['equipment']}")
                st.caption(formatear_features_ejercicio(ejercicio.to_dict()))
            st.divider()

        if len(ejercicios) > LIMITE_MOSTRADO:
            st.caption(f"Mostrando {LIMITE_MOSTRADO} de {len(ejercicios)}. Afina los filtros para ver más específico.")
