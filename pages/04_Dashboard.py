import plotly.graph_objects as go
import streamlit as st

from utils_db import (
    obtener_xp_total, obtener_historial_rutinas, obtener_perfil, obtener_clasificacion,
    obtener_historial_nutricion,
)
from utils_rutinas import calcular_ajuste_dificultad, calcular_tope_dificultad, obtener_techo_cluster
from utils_dashboard import (
    calcular_serie_xp_acumulado, calcular_balance_muscular, calcular_distribucion_objetivos,
    calcular_balance_nutricional, obtener_ejercicio_favorito, calcular_evolucion_dificultad,
)

st.set_page_config(page_title="ASCEND — Mi Progreso", page_icon="📈", layout="wide")

if not st.session_state.get("usuario_id"):
    st.warning("Necesitas iniciar sesión para ver tu progreso.")
    if st.button("Ir a Mi Perfil"):
        st.switch_page("pages/01_Mi_Perfil.py")
    st.stop()

usuario_id = st.session_state["usuario_id"]

# ---------------------------------------------------------------------------
# COLORES DE MARCA (mismos que Rutinas/Nutrición)
# ---------------------------------------------------------------------------
VERDE_PRIMARIO = "#006a20"
VERDE_CLARO = "#3ea85c"
NARANJA = "#e0862a"
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


def grafico_radar(categorias: list[str], valores: list[float], color: str, titulo: str, valor_max: float | None = None):
    cats_cerrado = categorias + [categorias[0]]
    vals_cerrado = valores + [valores[0]]
    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=vals_cerrado, theta=cats_cerrado, fill="toself",
        line=dict(color=color, width=2), fillcolor=color.replace(")", ", 0.35)").replace("rgb", "rgba"),
        name=titulo,
    ))
    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, valor_max] if valor_max else None)),
        showlegend=False, title=dict(text=titulo, x=0.5, font=dict(color=TEXTO_OSCURO, size=15)),
        margin=dict(l=40, r=40, t=50, b=20), height=340,
    )
    return fig


st.markdown(f"<h1 style='color: {TEXTO_OSCURO};'>📈 Mi Progreso</h1>", unsafe_allow_html=True)

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

# ---------------------------------------------------------------------------
# CARGA DE DATOS — una sola vez, se reutiliza en todas las gráficas de abajo
# ---------------------------------------------------------------------------
historial_rutinas = obtener_historial_rutinas(usuario_id, limite=200)
historial_nutricion = obtener_historial_nutricion(usuario_id, limite=200)
perfil = obtener_perfil(usuario_id)

col_xp, col_perfil = st.columns(2)
with col_xp:
    st.metric("XP acumulado", obtener_xp_total(usuario_id))
with col_perfil:
    st.metric("Última actualización de perfil", perfil["actualizado_en"] if perfil else "Sin registrar aún")

st.divider()

# ═══════════════════════════════════════════════════════════════════════════
# 1. XP ACUMULADO — área apilada, rutinas vs. nutrición
# ═══════════════════════════════════════════════════════════════════════════
encabezado_seccion("📊 XP acumulado — de dónde viene tu progreso")

serie_xp = calcular_serie_xp_acumulado(historial_rutinas, historial_nutricion)
if len(serie_xp) >= 1 and (serie_xp["xp_rutinas_acumulado"].iloc[-1] > 0 or serie_xp["xp_nutricion_acumulado"].iloc[-1] > 0):
    fig_xp = go.Figure()
    fig_xp.add_trace(go.Scatter(
        x=serie_xp["fecha"], y=serie_xp["xp_rutinas_acumulado"], mode="lines", name="Rutinas",
        line=dict(color=VERDE_PRIMARIO, width=2.5), fill="tozeroy",
        fillcolor="rgba(0, 106, 32, 0.35)", stackgroup="xp",
    ))
    fig_xp.add_trace(go.Scatter(
        x=serie_xp["fecha"], y=serie_xp["xp_nutricion_acumulado"], mode="lines", name="Nutrición",
        line=dict(color=NARANJA, width=2.5), fill="tonexty",
        fillcolor="rgba(224, 134, 42, 0.35)", stackgroup="xp",
    ))
    fig_xp.update_layout(
        height=340, margin=dict(l=40, r=20, t=20, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        yaxis_title="XP acumulado", xaxis_title=None,
        plot_bgcolor="white", paper_bgcolor="white",
        font=dict(color=TEXTO_OSCURO),
    )
    st.plotly_chart(fig_xp, use_container_width=True)
else:
    st.info("Completa rutinas o confirma comidas para ver aquí tu progreso de XP en el tiempo.")

st.divider()

# ═══════════════════════════════════════════════════════════════════════════
# 2. BALANCE MUSCULAR (radar) | TIPOS DE RUTINA MÁS ENTRENADOS (radar)
# ═══════════════════════════════════════════════════════════════════════════
col_radar1, col_radar2 = st.columns(2)

with col_radar1:
    balance_muscular = calcular_balance_muscular(historial_rutinas)
    if any(balance_muscular.values()):
        fig = grafico_radar(
            list(balance_muscular.keys()), list(balance_muscular.values()),
            color="rgb(0, 106, 32)", titulo="💪 Balance muscular",
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Completa rutinas para ver aquí qué zonas musculares entrenas más.")

with col_radar2:
    distribucion_objetivos = calcular_distribucion_objetivos(historial_rutinas)
    if any(distribucion_objetivos.values()):
        # Nombres cortos para que quepan bien en el radar
        etiquetas_cortas = {
            "Bajar de peso": "Bajar peso", "Ganar músculo": "Ganar músculo", "Ganar fuerza": "Ganar fuerza",
            "Mejorar resistencia/cardio": "Resistencia", "Salud general": "Salud general",
        }
        categorias = [etiquetas_cortas[k] for k in distribucion_objetivos]
        fig = grafico_radar(
            categorias, list(distribucion_objetivos.values()),
            color="rgb(62, 168, 92)", titulo="🎯 Tipos de rutina más entrenados",
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Completa rutinas para ver qué objetivos entrenas más seguido.")

st.divider()

# ═══════════════════════════════════════════════════════════════════════════
# 3. EVOLUCIÓN DE LA DIFICULTAD | BALANCE NUTRICIONAL (radar)
# ═══════════════════════════════════════════════════════════════════════════
col_evol, col_nutri = st.columns(2)

with col_evol:
    encabezado_seccion("📈 Evolución de la dificultad", color=TEXTO_OSCURO)
    evolucion = calcular_evolucion_dificultad(historial_rutinas)
    if not evolucion.empty:
        fig_evol = go.Figure()
        fig_evol.add_trace(go.Scatter(
            x=evolucion["indice"], y=evolucion["dificultad"], mode="lines+markers",
            line=dict(color=VERDE_PRIMARIO, width=2.5), marker=dict(size=7, color=VERDE_PRIMARIO),
            fill="tozeroy", fillcolor="rgba(0, 106, 32, 0.15)",
        ))
        fig_evol.update_layout(
            height=340, margin=dict(l=40, r=20, t=10, b=40),
            xaxis_title="Rutina completada #", yaxis_title="Dificultad promedio",
            plot_bgcolor="white", paper_bgcolor="white", font=dict(color=TEXTO_OSCURO),
        )
        st.plotly_chart(fig_evol, use_container_width=True)
    else:
        st.info("Completa rutinas para ver aquí cómo va subiendo tu dificultad.")

with col_nutri:
    balance_nutricional = calcular_balance_nutricional(historial_nutricion, perfil)
    if balance_nutricional:
        fig = grafico_radar(
            list(balance_nutricional.keys()), list(balance_nutricional.values()),
            color="rgb(224, 134, 42)", titulo="🥗 Balance nutricional (% de tu meta)", valor_max=150,
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Confirma comidas (con tu perfil completo) para ver tu balance nutricional aquí.")

st.divider()

# ═══════════════════════════════════════════════════════════════════════════
# 4. EJERCICIO FAVORITO
# ═══════════════════════════════════════════════════════════════════════════
encabezado_seccion("⭐ Tu ejercicio favorito", color=TEXTO_OSCURO)
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
        st.caption("Todavía no completas ninguna rutina.")

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
        st.caption("Todavía no registras ninguna comida.")

# ═══════════════════════════════════════════════════════════════════════════
# RESERVADO — EN DESARROLLO
# ═══════════════════════════════════════════════════════════════════════════
# Pendiente (ver roadmap):
#   1. Sistema de niveles visible (barra de progreso al siguiente nivel).
#   2. Preferencias/restricciones nutricionales del usuario — la "tabla de
#      clientes" de dietas.
# ═══════════════════════════════════════════════════════════════════════════
