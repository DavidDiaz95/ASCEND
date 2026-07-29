import streamlit as st

from utils_db import (
    obtener_xp_total, registrar_interaccion_nutricion, obtener_historial_nutricion,
    obtener_perfil, obtener_comidas_de_hoy,
)
from utils_nutricion import (
    identificar_ingredientes_de_foto, traducir_ingredientes_a_ingles, traducir_ingredientes_a_espanol,
    buscar_opciones_comida, buscar_comidas_por_objetivo, calcular_objetivo_nutricional,
    obtener_instrucciones_preparacion, obtener_ingredientes_de_receta,
    XP_POR_COMIDA_CONFIRMADA, ErrorNutricion,
)

st.set_page_config(page_title="ASCEND — Nutrición", page_icon="🥗")

if not st.session_state.get("usuario_id"):
    st.warning("Necesitas iniciar sesión para ver tu plan de nutrición.")
    if st.button("Ir a Mi Perfil"):
        st.switch_page("pages/01_Mi_Perfil.py")
    st.stop()

usuario_id = st.session_state["usuario_id"]

VERDE_PRIMARIO = "#006a20"
TEXTO_OSCURO = "#141d16"


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


def elegir_opcion(opcion: dict) -> None:
    """Traduce ingredientes usados/faltantes a español ANTES de pasar a la
    pantalla de confirmación — más legible para nuestro público. Si la
    opción viene de 'recomendadas para tu objetivo' (no del refri), no trae
    usados/faltantes — en ese caso se busca la lista de ingredientes
    NECESARIOS por default, para que la pantalla nunca se quede vacía de
    esa información. Limpia también cualquier instrucción de una comida
    elegida previamente."""
    opcion = dict(opcion)
    with st.spinner("Preparando el detalle..."):
        if opcion.get("ingredientes_usados") or opcion.get("ingredientes_faltantes"):
            opcion["ingredientes_usados"] = traducir_ingredientes_a_espanol(opcion.get("ingredientes_usados", []))
            opcion["ingredientes_faltantes"] = traducir_ingredientes_a_espanol(opcion.get("ingredientes_faltantes", []))
        else:
            try:
                necesarios = obtener_ingredientes_de_receta(opcion["id"])
                opcion["ingredientes_necesarios"] = traducir_ingredientes_a_espanol(necesarios)
            except ErrorNutricion as e:
                st.error(str(e))
                opcion["ingredientes_necesarios"] = []
    st.session_state["comida_seleccionada"] = opcion
    st.session_state.pop("instrucciones_actual", None)
    st.rerun()


def mostrar_tarjeta_opcion(opcion: dict, key_prefix: str) -> None:
    """Tarjeta reutilizable — la usan tanto 'disponibles' como 'recomendadas
    para tu objetivo', para que se vean y se comporten igual."""
    with st.container(border=True):
        col_img, col_info = st.columns([1, 2])
        with col_img:
            if opcion.get("imagen_url"):
                st.image(opcion["imagen_url"], use_container_width=True)
        with col_info:
            st.markdown(f"**{opcion['titulo']}**")
            st.caption(
                f"{opcion['calorias'] or '—'} kcal · {opcion['proteina_g'] or '—'} g proteína · "
                f"{opcion['grasa_g'] or '—'} g grasa · {opcion['carbohidratos_g'] or '—'} g carbs"
            )
            if opcion.get("ingredientes_faltantes"):
                st.caption(f"🛒 Te faltaría: {', '.join(opcion['ingredientes_faltantes'])}")
            elif opcion.get("ingredientes_usados"):
                st.caption("✅ Tienes todo lo que necesitas")
        if st.button("Elegir", key=f"{key_prefix}_{opcion['id']}", use_container_width=True, type="primary"):
            elegir_opcion(opcion)


st.markdown(f"<h1 style='color: {TEXTO_OSCURO};'>🥗 Nutrición</h1>", unsafe_allow_html=True)

if "comida_registrada_xp" in st.session_state:
    st.success(f"¡Comida registrada! +{st.session_state.pop('comida_registrada_xp')} XP 🎉")


# ═══════════════════════════════════════════════════════════════════════════
# SI HAY UNA COMIDA ELEGIDA PENDIENTE DE CONFIRMAR — pantalla de enfoque.
# ═══════════════════════════════════════════════════════════════════════════
if st.session_state.get("comida_seleccionada"):
    comida = st.session_state["comida_seleccionada"]

    encabezado_seccion("🍽️ ¿Vas a preparar esta comida?")

    col_img, col_info = st.columns([1, 1.4])
    with col_img:
        if comida.get("imagen_url"):
            st.image(comida["imagen_url"], use_container_width=True)
    with col_info:
        st.markdown(f"### {comida['titulo']}")
        st.write(f"**{comida['calorias'] or '—'} kcal** por porción")
        st.caption(
            f"Proteína: {comida['proteina_g'] or '—'} g · "
            f"Grasa: {comida['grasa_g'] or '—'} g · "
            f"Carbohidratos: {comida['carbohidratos_g'] or '—'} g"
        )
        if comida.get("listo_en_minutos"):
            st.caption(f"⏱️ Listo en ~{comida['listo_en_minutos']} min · {comida.get('porciones', '—')} porciones")
        if comida.get("ingredientes_usados"):
            st.caption(f"✅ Usa: {', '.join(comida['ingredientes_usados'])}")
        if comida.get("ingredientes_faltantes"):
            st.caption(f"🛒 Te faltaría: {', '.join(comida['ingredientes_faltantes'])}")
        if comida.get("ingredientes_necesarios"):
            st.caption(f"🧾 Ingredientes necesarios: {', '.join(comida['ingredientes_necesarios'])}")

    st.divider()

    # --- Instrucciones DENTRO de la app, ya no un link externo ---
    if st.button("👨‍🍳 Ver cómo prepararla", use_container_width=True):
        with st.spinner("Buscando la preparación..."):
            try:
                st.session_state["instrucciones_actual"] = obtener_instrucciones_preparacion(comida["id"], comida["titulo"])
            except ErrorNutricion as e:
                st.error(str(e))

    instrucciones = st.session_state.get("instrucciones_actual")
    if instrucciones:
        if instrucciones["es_generada_por_ia"]:
            st.caption("⚠️ No encontramos la receta original — esta es una sugerencia general basada en el título.")
        st.markdown(instrucciones["texto"])

    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ Sí, la voy a preparar", type="primary", use_container_width=True):
            registrar_interaccion_nutricion(
                usuario_id, "comida_confirmada",
                {
                    "receta_id": comida["id"], "titulo": comida["titulo"],
                    "calorias": comida["calorias"], "proteina_g": comida["proteina_g"],
                    "grasa_g": comida["grasa_g"], "carbohidratos_g": comida["carbohidratos_g"],
                    "ingredientes_usados": comida.get("ingredientes_usados", []),
                },
                xp_ganado=XP_POR_COMIDA_CONFIRMADA,
            )
            print(
                f"[ASCEND][comida_confirmada] usuario={st.session_state.get('username')} "
                f"receta={comida['titulo']} calorias={comida['calorias']} xp={XP_POR_COMIDA_CONFIRMADA}"
            )
            st.session_state["comida_registrada_xp"] = XP_POR_COMIDA_CONFIRMADA
            del st.session_state["comida_seleccionada"]
            st.session_state.pop("instrucciones_actual", None)
            st.rerun()
    with col2:
        if st.button("⬅️ Elegir otra opción", use_container_width=True):
            del st.session_state["comida_seleccionada"]
            st.session_state.pop("instrucciones_actual", None)
            st.rerun()

    st.stop()


# ═══════════════════════════════════════════════════════════════════════════
# 1. PANEL DE METAS DIARIAS + BARRA DE PROGRESO — arriba de todo.
# ═══════════════════════════════════════════════════════════════════════════
encabezado_seccion("🎯 Tu meta diaria")

perfil = obtener_perfil(usuario_id)
if not perfil:
    st.warning("Completa tus datos en **Mi Perfil** para calcular tu meta diaria personalizada.")
    metas = None
else:
    metas = calcular_objetivo_nutricional(perfil)
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Calorías/día", metas["calorias"])
    col2.metric("Proteína", f"{metas['proteina_g']} g")
    col3.metric("Grasa", f"{metas['grasa_g']} g")
    col4.metric("Carbohidratos", f"{metas['carbohidratos_g']} g")
    st.caption(
        f"Estimado para tu objetivo actual (**{metas['objetivo_usado']}**) con Mifflin-St Jeor y factor de actividad moderado."
    )

    comidas_hoy = obtener_comidas_de_hoy(usuario_id)
    calorias_hoy = sum(c.get("calorias") or 0 for c in comidas_hoy)
    proteina_hoy = sum(c.get("proteina_g") or 0 for c in comidas_hoy)
    grasa_hoy = sum(c.get("grasa_g") or 0 for c in comidas_hoy)
    carbs_hoy = sum(c.get("carbohidratos_g") or 0 for c in comidas_hoy)

    progreso_calorias = min(calorias_hoy / metas["calorias"], 1.0) if metas["calorias"] else 0.0
    progreso_proteina = min(proteina_hoy / metas["proteina_g"], 1.0) if metas["proteina_g"] else 0.0
    progreso_grasa = min(grasa_hoy / metas["grasa_g"], 1.0) if metas["grasa_g"] else 0.0
    progreso_carbs = min(carbs_hoy / metas["carbohidratos_g"], 1.0) if metas["carbohidratos_g"] else 0.0

    st.caption(f"Progreso de hoy — {len(comidas_hoy)} comida(s) registrada(s):")
    col_prog1, col_prog2 = st.columns(2)
    with col_prog1:
        st.progress(progreso_calorias, text=f"🔥 Calorías: {round(calorias_hoy)}/{metas['calorias']} kcal")
        st.progress(progreso_grasa, text=f"🥑 Grasa: {round(grasa_hoy)}/{metas['grasa_g']} g")
    with col_prog2:
        st.progress(progreso_proteina, text=f"🍗 Proteína: {round(proteina_hoy)}/{metas['proteina_g']} g")
        st.progress(progreso_carbs, text=f"🍞 Carbohidratos: {round(carbs_hoy)}/{metas['carbohidratos_g']} g")
    st.caption("Solo indicativo — no es una meta estricta.")

st.divider()

# ═══════════════════════════════════════════════════════════════════════════
# 2. CAPTURA DE INGREDIENTES — foto o texto, compartida arriba de las dos
# columnas de resultados.
# ═══════════════════════════════════════════════════════════════════════════
encabezado_seccion("📷 ¿Qué tienes disponible?")

modo = st.radio(
    "¿Cómo quieres darnos tus ingredientes?",
    ["📷 Foto de mi refrigerador/despensa", "✍️ Escribirlos yo mismo"],
    label_visibility="collapsed",
)

ingredientes_para_buscar = None

if modo.startswith("📷"):
    foto = st.file_uploader("Sube una foto", type=["jpg", "jpeg", "png"])
    if foto is not None:
        st.image(foto, caption="Tu foto", use_container_width=True)
        if st.button("🔎 Identificar ingredientes", type="primary"):
            with st.spinner("Viendo qué tienes disponible..."):
                try:
                    st.session_state["ingredientes_detectados"] = identificar_ingredientes_de_foto(foto.getvalue())
                except ErrorNutricion as e:
                    st.error(str(e))

    ingredientes_detectados = st.session_state.get("ingredientes_detectados")
    if ingredientes_detectados:
        st.success(f"Detecté: {', '.join(ingredientes_detectados)}")
        ingredientes_para_buscar = st.multiselect(
            "Ajusta la lista si algo quedó mal",
            options=ingredientes_detectados, default=ingredientes_detectados,
        )
else:
    texto_ingredientes = st.text_input(
        "Escribe tus ingredientes separados por coma, en el idioma que quieras",
        placeholder="arroz, pechuga de pollo, jitomate",
    )
    if texto_ingredientes:
        ingredientes_para_buscar = [i.strip() for i in texto_ingredientes.split(",") if i.strip()]

st.divider()

# ═══════════════════════════════════════════════════════════════════════════
# 3. DOS COLUMNAS: disponibles (izquierda) | recomendadas por objetivo (derecha)
# ═══════════════════════════════════════════════════════════════════════════
col_izq, col_der = st.columns(2)

with col_izq:
    encabezado_seccion("🍳 Con lo que tienes disponible")

    if ingredientes_para_buscar:
        if st.button("Buscar opciones de comida", type="primary", use_container_width=True, key="btn_buscar_disponibles"):
            with st.spinner("Traduciendo y buscando recetas con esto..."):
                try:
                    ingredientes_en_ingles = traducir_ingredientes_a_ingles(ingredientes_para_buscar)
                    print(f"[ASCEND][nutricion] traducción: {ingredientes_para_buscar} -> {ingredientes_en_ingles}")
                    st.session_state["opciones_disponibles"] = buscar_opciones_comida(ingredientes_en_ingles, n_opciones=3)
                except ErrorNutricion as e:
                    st.error(str(e))
                    st.session_state["opciones_disponibles"] = []
    else:
        st.caption("Dinos qué tienes arriba para buscar aquí.")

    opciones_disponibles = st.session_state.get("opciones_disponibles", [])
    if opciones_disponibles:
        st.caption(f"{len(opciones_disponibles)} opciones — de la que menos te falta a la que más.")
        for opcion in opciones_disponibles:
            mostrar_tarjeta_opcion(opcion, key_prefix="disponible")
    elif "opciones_disponibles" in st.session_state:
        st.info("No encontré nada ni siquiera cercano — prueba agregando uno o dos ingredientes más.")

with col_der:
    encabezado_seccion("✨ Recomendadas para tu objetivo", color=TEXTO_OSCURO)

    if metas is None:
        st.caption("Completa tu perfil arriba para desbloquear esta sección.")
    else:
        if st.button("🔄 Buscar recomendaciones", use_container_width=True, key="btn_buscar_objetivo"):
            with st.spinner("Buscando comidas balanceadas para ti..."):
                try:
                    st.session_state["opciones_objetivo"] = buscar_comidas_por_objetivo(metas, n_opciones=3)
                except ErrorNutricion as e:
                    st.error(str(e))
                    st.session_state["opciones_objetivo"] = []

        opciones_objetivo = st.session_state.get("opciones_objetivo", [])
        if opciones_objetivo:
            for opcion in opciones_objetivo:
                mostrar_tarjeta_opcion(opcion, key_prefix="objetivo")
        elif "opciones_objetivo" in st.session_state:
            st.info("No encontré recomendaciones esta vez — intenta de nuevo en un momento.")

st.divider()

# ---------------------------------------------------------------------------
# TU HISTORIAL DE COMIDAS
# ---------------------------------------------------------------------------
encabezado_seccion("📋 Tus comidas registradas", color=TEXTO_OSCURO)
historial_nutricion = obtener_historial_nutricion(usuario_id)
if historial_nutricion:
    filas_tabla = [
        {
            "Fecha": h["registrado_en"], "Comida": h["detalle"].get("titulo", "—"),
            "Calorías": h["detalle"].get("calorias", "—"), "Proteína (g)": h["detalle"].get("proteina_g", "—"),
            "XP ganado": h["xp_ganado"],
        }
        for h in historial_nutricion
    ]
    st.dataframe(filas_tabla, use_container_width=True)
else:
    st.caption("Todavía no registras ninguna comida — ¡busca opciones arriba!")

# ═══════════════════════════════════════════════════════════════════════════
# RESERVADO — EN DESARROLLO
# ═══════════════════════════════════════════════════════════════════════════
# Pendiente (ver roadmap):
#   1. Preferencias/restricciones del usuario (vegetariano, alergias) — la
#      "tabla de clientes" de dietas, para filtrar ambos buscadores.
#   2. Factor de actividad real (hoy es un supuesto fijo de 1.45) — podría
#      calcularse de cuántas rutinas completa el usuario por semana.
#   3. Más gráficas en el Dashboard (calorías/macros en el tiempo).
# ═══════════════════════════════════════════════════════════════════════════
