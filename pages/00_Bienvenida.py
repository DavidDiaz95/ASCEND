from pathlib import Path

import streamlit as st

BASE_DIR = Path(__file__).resolve().parent.parent
RUTA_LOGOS = BASE_DIR / "Logos"

st.set_page_config(page_title="ASCEND", page_icon=str(RUTA_LOGOS / "ascend-icon.png"))

col_izq, col_centro, col_der = st.columns([1, 2, 1])
with col_centro:
    st.image(str(RUTA_LOGOS / "ascend-logo-stacked.png"), use_container_width=True)

st.markdown(
    "<h3 style='text-align: center; color: #141d16;'>Cada recomendación basada en tu realidad.</h3>",
    unsafe_allow_html=True,
)
st.markdown(
    """
    <p style='text-align: center; color: #3a3a3a; font-size: 16px;'>
    ASCEND utiliza inteligencia y datos para ayudarte a entrenar y alimentarte
    mejor. Cada recomendación se adapta a tu nivel, hábitos, objetivos y
    recursos disponibles, para que avances de forma sostenible y medible.
    </p>
    """,
    unsafe_allow_html=True,
)

st.divider()

col1, col2, col3 = st.columns([1, 1, 1])
with col2:
    if st.session_state.get("usuario_id"):
        if st.button("Ir a mi cuenta →", use_container_width=True, type="primary"):
            st.switch_page("pages/01_Mi_Perfil.py")
    else:
        if st.button("Comenzar →", use_container_width=True, type="primary"):
            st.switch_page("pages/01_Mi_Perfil.py")

st.divider()

