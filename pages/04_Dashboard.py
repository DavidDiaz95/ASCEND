import plotly.graph_objects as go
import streamlit as st

from utils_db import (
    obtener_historial_rutinas, obtener_perfil, obtener_clasificacion, obtener_historial_nutricion,
)
from utils_rutinas import calcular_ajuste_dificultad, calcular_tope_dificultad, obtener_techo_cluster
from utils_dashboard import (
    OPCIONES_RANGO, filtrar_por_rango, granularidad_por_rango,
    calcular_serie_xp_acumulado, calcular_balance_muscular, calcular_distribucion_objetivos,
    calcular_balance_nutricional, obtener_ejercicio_favorito, calcular_evolucion_dificultad,
    calcular_minutos_entrenados, calcular_racha_actual, calcular_kpis,
)

st.set_page_config(page_title="ASCEND — Mi Progreso", page_icon="📈", layout="wide")

if not st.session_state.get("usuario_id"):
    st.warning("Necesitas iniciar sesión para ver tu progreso.")
    if st.button("Ir a Mi Perfil"):
        st.switch_page("pages/01_Mi_Perfil.py")
    st.stop()

usuario_id = st.session_state["usuario_id"]

# ---------------------------------------------------------------------------
# PALETA REAL DE ASCEND (colores oficiales)
# del MISMO matiz (150°) para series secundarias.
# ---------------------------------------------------------------------------
VERDE_PRIMARIO = "#006a20"   # oklch(0.45 0.15 150) — oficial
VERDE_MEDIO = "#20a04e"      # derivado, mismo matiz, L=0.62 — series secundarias
VERDE_SUAVE = "#8ec899"      # derivado, mismo matiz, L=0.78 — acentos terciarios
VERDE_CLARO = "#d8efdc"      # oklch(0.93 0.035 150) — oficial, para rellenos
CASI_NEGRO = "#141d16"       # oklch(0.22 0.02 150) — oficial, texto
FONDO = "#f2f6f3"            # oklch(0.97 0.006 150) — oficial, fondo de gráficas
GRIS_VERDE = "#c7d1c9"       # derivado, mismo matiz, L=0.85 — rejillas/ejes

FUENTE = dict(family="sans-serif", color=CASI_NEGRO)


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


def _layout_base(fig: go.Figure, **kwargs) -> go.Figure:
    kwargs.setdefault("margin", dict(l=40, r=30, t=40, b=40))
    fig.update_layout(plot_bgcolor=FONDO, paper_bgcolor=FONDO, font=FUENTE, **kwargs)
    return fig


def grafico_radar(categorias: list[str], valores: list[float], color_linea: str, color_relleno: str,
                   titulo: str, valor_max: float | None = None, altura: int = 340):
    # Etiquetas en negritas y más grandes — antes casi no se veían.
    categorias_negritas = [f"<b>{c}</b>" for c in categorias]
    cats_cerrado = categorias_negritas + [categorias_negritas[0]]
    vals_cerrado = valores + [valores[0]]

    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=vals_cerrado, theta=cats_cerrado, fill="toself",
        line=dict(color=color_linea, width=2.5), fillcolor=color_relleno,
        marker=dict(size=6, color=color_linea),
    ))
    fig.update_layout(
        polar=dict(
            bgcolor=FONDO,
            radialaxis=dict(
                visible=True, showticklabels=False,  # se quita el "eje" de números, se ve feo
                range=[0, valor_max] if valor_max else None,
                gridcolor=GRIS_VERDE, linecolor=GRIS_VERDE,
            ),
            angularaxis=dict(
                gridcolor=GRIS_VERDE, linecolor=GRIS_VERDE,
                tickfont=dict(color=CASI_NEGRO, size=14),
            ),
        ),
        showlegend=False,
        title=dict(text=titulo, x=0.5, xanchor="center", font=dict(color=CASI_NEGRO, size=19)),
        height=altura,
    )
    return _layout_base(fig, margin=dict(l=30, r=30, t=60, b=20))


st.markdown(f"<h1 style='color: {CASI_NEGRO};'>📈 Mi Progreso</h1>", unsafe_allow_html=True)

# [HIDDEN] Perfilador del Usuario — funcional, no decorativo. Se deja
# colapsado y sin explicación a propósito.
with st.expander("[HIDDEN] Perfilador del Usuario (Visible solo para desarrollo y evaluación)"):
    clasificacion = obtener_clasificacion(usuario_id)
    if clasificacion:
        st.write(f"**Cluster:** {clasificacion['nivel_cluster_nombre']} (id interno: {clasificacion['nivel_cluster']})")
        st.write(f"**Modelo usado:** {clasificacion.get('modelo_usado')}")
        st.json(clasificacion)
    else:
        st.warning("Este usuario todavía no tiene una clasificación guardada.")

    st.divider()
    historial_debug = obtener_historial_rutinas(usuario_id, limite=1000)
    n_facil = sum(1 for h in historial_debug if h.get("feedback_dificultad") == "facil")
    n_bien = sum(1 for h in historial_debug if h.get("feedback_dificultad") == "bien")
    n_dificil = sum(1 for h in historial_debug if h.get("feedback_dificultad") == "dificil")
    cluster_nombre = clasificacion["nivel_cluster_nombre"] if clasificacion else None
    st.write(f"**Feedback registrado:** fácil={n_facil} · bien={n_bien} · difícil={n_dificil}")
    st.write(f"**Ajuste de dificultad calculado:** {calcular_ajuste_dificultad(historial_debug):+.1f}")
    st.write(f"**Techo del cluster (con expansión):** {obtener_techo_cluster(cluster_nombre, historial_debug):.1f}")
    st.write(f"**Tope progresivo actual:** {calcular_tope_dificultad(cluster_nombre, historial_debug):.1f}")

# ---------------------------------------------------------------------------
# CARGA DE DATOS COMPLETA (sin filtrar) — se usa para la racha (que siempre
# ve el histórico completo) y como base para filtrar por el rango elegido.
# ---------------------------------------------------------------------------
historial_rutinas_completo = obtener_historial_rutinas(usuario_id, limite=1000)
historial_nutricion_completo = obtener_historial_nutricion(usuario_id, limite=1000)
perfil = obtener_perfil(usuario_id)
racha_actual = calcular_racha_actual(historial_rutinas_completo, historial_nutricion_completo)

# ═══════════════════════════════════════════════════════════════════════════
# ESTADÍSTICAS HISTÓRICAS + SELECTOR DE RANGO — al inicio, como un tablero.
# ═══════════════════════════════════════════════════════════════════════════
encabezado_seccion("📊 Estadísticas")

rango_seleccionado = st.radio(
    "Rango a mostrar", OPCIONES_RANGO, index=0, horizontal=True, label_visibility="collapsed",
)
granularidad = granularidad_por_rango(rango_seleccionado)

historial_rutinas = filtrar_por_rango(historial_rutinas_completo, "completado_en", rango_seleccionado)
historial_nutricion = filtrar_por_rango(historial_nutricion_completo, "registrado_en", rango_seleccionado)

kpis = calcular_kpis(historial_rutinas, historial_nutricion, racha_actual)

col1, col2, col3, col4, col5, col6 = st.columns(6)
col1.metric("XP en el periodo", kpis["xp_total"])
col2.metric("Rutinas completadas", kpis["n_rutinas"])
col3.metric("Comidas registradas", kpis["n_comidas"])
col4.metric("Minutos entrenados", kpis["minutos_totales"])
col5.metric("Dificultad promedio", kpis["dificultad_promedio"] if kpis["dificultad_promedio"] is not None else "—")
col6.metric("🔥 Racha actual", f"{kpis['racha_actual']} día(s)")

st.divider()

# ═══════════════════════════════════════════════════════════════════════════
# FILA 1 (1:1) — XP acumulado | Evolución de la dificultad (por día/mes)
# ═══════════════════════════════════════════════════════════════════════════
col_xp_area, col_evol = st.columns([1, 1])
etiqueta_periodo = "Día" if granularidad == "dia" else "Mes"

with col_xp_area:
    encabezado_seccion("📊 XP acumulado — de dónde viene tu progreso")
    serie_xp = calcular_serie_xp_acumulado(historial_rutinas, historial_nutricion, granularidad)
    if len(serie_xp) >= 1 and (serie_xp["xp_rutinas_acumulado"].iloc[-1] > 0 or serie_xp["xp_nutricion_acumulado"].iloc[-1] > 0):
        fig_xp = go.Figure()
        fig_xp.add_trace(go.Scatter(
            x=serie_xp["periodo"], y=serie_xp["xp_rutinas_acumulado"], mode="lines", name="Rutinas",
            line=dict(color=VERDE_PRIMARIO, width=2.5, shape="spline"), fill="tozeroy",
            fillcolor="rgba(0, 106, 32, 0.35)", stackgroup="xp",
        ))
        fig_xp.add_trace(go.Scatter(
            x=serie_xp["periodo"], y=serie_xp["xp_nutricion_acumulado"], mode="lines", name="Nutrición",
            line=dict(color=VERDE_MEDIO, width=2.5, shape="spline"), fill="tonexty",
            fillcolor="rgba(32, 160, 78, 0.35)", stackgroup="xp",
        ))
        fig_xp.update_xaxes(gridcolor=GRIS_VERDE, linecolor=GRIS_VERDE, title=etiqueta_periodo, type="category")
        fig_xp.update_yaxes(gridcolor=GRIS_VERDE, linecolor=GRIS_VERDE, title="XP acumulado")
        _layout_base(
            fig_xp, height=300,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        st.plotly_chart(fig_xp, use_container_width=True)
    else:
        st.info("Completa rutinas o confirma comidas para ver aquí tu progreso de XP en el tiempo.")

with col_evol:
    encabezado_seccion("📈 Evolución de la dificultad", color=CASI_NEGRO)
    evolucion = calcular_evolucion_dificultad(historial_rutinas, granularidad)
    if not evolucion.empty:
        fig_evol = go.Figure()
        fig_evol.add_trace(go.Scatter(
            x=evolucion["periodo"], y=evolucion["dificultad"], mode="lines+markers",
            line=dict(color=VERDE_PRIMARIO, width=2.5, shape="spline"),
            marker=dict(size=8, color=VERDE_PRIMARIO, line=dict(color="white", width=1)),
            fill="tozeroy", fillcolor="rgba(0, 106, 32, 0.15)",
        ))
        fig_evol.update_xaxes(gridcolor=GRIS_VERDE, linecolor=GRIS_VERDE, title=etiqueta_periodo, type="category")
        fig_evol.update_yaxes(gridcolor=GRIS_VERDE, linecolor=GRIS_VERDE, title="Dificultad promedio")
        _layout_base(fig_evol, height=300)
        st.plotly_chart(fig_evol, use_container_width=True)
    else:
        st.info("Completa rutinas para ver aquí cómo va subiendo tu dificultad.")

st.divider()

# ═══════════════════════════════════════════════════════════════════════════
# FILA 2 (2:1) — Balance muscular (grande, izquierda) | Tipos de rutina +
# Balance nutricional apilados (derecha, cada uno la mitad de alto)
# ═══════════════════════════════════════════════════════════════════════════
col_muscular, col_derecha = st.columns([2, 1])

with col_muscular:
    balance_muscular = calcular_balance_muscular(historial_rutinas)
    if any(balance_muscular.values()):
        fig = grafico_radar(
            list(balance_muscular.keys()), list(balance_muscular.values()),
            color_linea=VERDE_PRIMARIO, color_relleno="rgba(0, 106, 32, 0.35)",
            titulo="💪 Balance muscular", altura=480,
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Completa rutinas para ver aquí qué zonas musculares entrenas más.")

with col_derecha:
    distribucion_objetivos = calcular_distribucion_objetivos(historial_rutinas)
    if any(distribucion_objetivos.values()):
        etiquetas_cortas = {
            "Bajar de peso": "Bajar peso", "Ganar músculo": "Ganar músculo", "Ganar fuerza": "Ganar fuerza",
            "Mejorar resistencia/cardio": "Resistencia", "Salud general": "Salud general",
        }
        categorias = [etiquetas_cortas[k] for k in distribucion_objetivos]
        fig = grafico_radar(
            categorias, list(distribucion_objetivos.values()),
            color_linea=VERDE_MEDIO, color_relleno="rgba(32, 160, 78, 0.35)",
            titulo="🎯 Tipos de rutina", altura=240,
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Completa rutinas para ver qué objetivos entrenas más seguido.")

    balance_nutricional = calcular_balance_nutricional(historial_nutricion, perfil)
    if balance_nutricional:
        fig = grafico_radar(
            list(balance_nutricional.keys()), list(balance_nutricional.values()),
            color_linea=VERDE_SUAVE, color_relleno="rgba(142, 200, 153, 0.45)",
            titulo="🥗 Balance nutricional (%)", valor_max=150, altura=240,
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Confirma comidas (con tu perfil completo) para ver tu balance nutricional aquí.")

st.divider()

# ═══════════════════════════════════════════════════════════════════════════
# FILA 3 — Minutos entrenados por día/mes
# ═══════════════════════════════════════════════════════════════════════════
encabezado_seccion(f"⏱️ Minutos entrenados por {etiqueta_periodo.lower()}", color=CASI_NEGRO)
minutos_periodo = calcular_minutos_entrenados(historial_rutinas, granularidad)
if not minutos_periodo.empty:
    fig_minutos = go.Figure()
    fig_minutos.add_trace(go.Scatter(
        x=minutos_periodo["periodo"], y=minutos_periodo["minutos"], mode="lines+markers",
        line=dict(color=VERDE_PRIMARIO, width=2.5, shape="spline"),
        marker=dict(size=8, color=VERDE_PRIMARIO, line=dict(color="white", width=1)),
        fill="tozeroy", fillcolor="rgba(0, 106, 32, 0.15)",
    ))
    fig_minutos.update_xaxes(gridcolor=GRIS_VERDE, linecolor=GRIS_VERDE, title=etiqueta_periodo, type="category")
    fig_minutos.update_yaxes(gridcolor=GRIS_VERDE, linecolor=GRIS_VERDE, title="Minutos entrenados")
    _layout_base(fig_minutos, height=260, showlegend=False)
    st.plotly_chart(fig_minutos, use_container_width=True)
else:
    st.info(f"Completa rutinas para ver aquí cuántos minutos entrenas por {etiqueta_periodo.lower()}.")

st.divider()

# ═══════════════════════════════════════════════════════════════════════════
# EJERCICIO FAVORITO
# ═══════════════════════════════════════════════════════════════════════════
encabezado_seccion("⭐ Tu ejercicio favorito", color=CASI_NEGRO)
favorito = obtener_ejercicio_favorito(historial_rutinas)
if favorito:
    col_fav1, col_fav2, col_fav3 = st.columns(3)
    col_fav1.metric("Ejercicio", favorito["nombre"])
    col_fav2.metric("Veces realizado", favorito["veces"])
    col_fav3.metric("Dificultad", f"{favorito['dificultad']:.0f}/100")
else:
    st.caption("Completa rutinas para descubrir cuál es tu ejercicio favorito.")

st.divider()

# ---------------------------------------------------------------------------
# HISTORIAL DETALLADO (tablas) — colapsado por default, para no saturar
# ---------------------------------------------------------------------------
with st.expander("📋 Ver historial detallado de rutinas y nutrición"):
    st.subheader("Rutinas")
    if historial_rutinas:
        st.dataframe(historial_rutinas, use_container_width=True)
    else:
        st.caption("Todavía no completas ninguna rutina en este rango.")

    st.subheader("Nutrición")
    if historial_nutricion:
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
        st.caption("Todavía no registras ninguna comida en este rango.")


