import os
from pathlib import Path

from dotenv import load_dotenv
import streamlit as st
from openai import OpenAI

BASE_DIR = Path(__file__).resolve().parent
RUTA_LOGOS = BASE_DIR / "Logos"

load_dotenv(BASE_DIR / ".env", override=True)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client_openai = OpenAI(api_key=OPENAI_API_KEY)
model_openai = "gpt-5.4-mini"

SYSTEM_PROMPT = """
Eres el asistente conversacional de ASCEND, una app de fitness y nutrición
para LATAM. Tu tono es motivador, cercano y nunca condescendiente.

Reglas importantes:
- Nunca le digas al usuario que está en un "nivel bajo" o uses etiquetas
  clínicas sobre su condición física — el progreso se comunica solo a través
  de su XP y rutinas completadas, nunca comparando su cuerpo contra otros.
- Ayuda a definir o ajustar el objetivo del usuario (bajar de peso, ganar
  fuerza, salud general, mejorar rendimiento) cuando lo pidan.
- Si preguntan algo médico serio (lesiones, dolor persistente, condiciones
  de salud), recomienda consultar a un profesional en vez de dar diagnóstico.
"""

# ---------------------------------------------------------------------------
# CONFIGURACIÓN DE PÁGINA — título de pestaña, ícono, layout
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="ASCEND",
    page_icon=str(RUTA_LOGOS / "ascend-icon.png"),
    layout="centered",
)

# ---------------------------------------------------------------------------
# ENCABEZADO CON LOGO — centrado usando columnas
# ---------------------------------------------------------------------------
col_izq, col_centro, col_der = st.columns([1, 2, 1])
with col_centro:
    st.image(str(RUTA_LOGOS / "ascend-logo-stacked.png"), use_container_width=True)

st.markdown("<p style='text-align: center; color: #141d16;'>Tu asistente de entrenamiento y nutrición</p>", unsafe_allow_html=True)
st.divider()

# ---------------------------------------------------------------------------
# CHAT
# ---------------------------------------------------------------------------
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "¡Hola! Soy tu asistente de ASCEND 💪 ¿En qué te ayudo hoy — dudas de tu rutina, tu alimentación, o quieres ajustar tu objetivo?"}
    ]

avatares = {
    "assistant": str(RUTA_LOGOS / "ascend-icon.png"),
    "user": None,  # usa el ícono por default de Streamlit para el usuario
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
