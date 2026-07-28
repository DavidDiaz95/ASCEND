import os
from pathlib import Path

from dotenv import load_dotenv
import streamlit as st
from openai import OpenAI

from prompts import construir_system_prompt
from utils_db import obtener_perfil, obtener_xp_total

BASE_DIR = Path(__file__).resolve().parent.parent
RUTA_LOGOS = BASE_DIR / "Logos"

st.set_page_config(page_title="ASCEND — Asistente", page_icon=str(RUTA_LOGOS / "ascend-icon.png"))

# ---------------------------------------------------------------------------
# GUARDIA — mismo patrón que las demás páginas bloqueadas.
# ---------------------------------------------------------------------------
if not st.session_state.get("usuario_id"):
    st.warning("Necesitas iniciar sesión para hablar con el asistente de ASCEND.")
    if st.button("Ir a Mi Perfil"):
        st.switch_page("pages/01_Mi_Perfil.py")
    st.stop()

load_dotenv(BASE_DIR / ".env", override=True)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client_openai = OpenAI(api_key=OPENAI_API_KEY)
model_openai = "gpt-5.4-mini"

# El system prompt ya no es un string fijo — se arma con el objetivo y el
# XP real del usuario (ver prompts.py). nivel_cluster NUNCA se pasa aquí:
# la sección de seguridad de construir_system_prompt() ya cubre qué hacer
# si preguntan por su clasificación.
usuario_id = st.session_state["usuario_id"]
perfil_usuario = obtener_perfil(usuario_id) or {}
SYSTEM_PROMPT = construir_system_prompt(
    nombre_usuario=st.session_state.get("username"),
    objetivo=perfil_usuario.get("objetivo"),
    xp_total=obtener_xp_total(usuario_id),
)

col_izq, col_centro, col_der = st.columns([1, 2, 1])
with col_centro:
    st.image(str(RUTA_LOGOS / "ascend-logo-stacked.png"), use_container_width=True)

st.markdown("<p style='text-align: center; color: #141d16;'>Tu asistente de entrenamiento y nutrición</p>", unsafe_allow_html=True)
st.divider()

if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "¡Hola! Soy tu asistente de ASCEND 💪 ¿En qué te ayudo hoy — dudas de tu rutina, tu alimentación, o quieres ajustar tu objetivo?"}
    ]

avatares = {
    "assistant": str(RUTA_LOGOS / "ascend-icon.png"),
    "user": None,
}

for msg in st.session_state.messages:
    st.chat_message(msg["role"], avatar=avatares.get(msg["role"])).write(msg["content"])

if prompt := st.chat_input("Escribe tu mensaje aquí..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.chat_message("user").write(prompt)

    conversation = [{"role": "system", "content": SYSTEM_PROMPT}]
    conversation.extend(
        {"role": m["role"], "content": m["content"]} for m in st.session_state.messages
    )

    with st.chat_message("assistant", avatar=avatares["assistant"]):
        stream = client_openai.chat.completions.create(
            model=model_openai,
            messages=conversation,
            stream=True,
        )
        response = st.write_stream(stream)

    st.session_state.messages.append({"role": "assistant", "content": response})
