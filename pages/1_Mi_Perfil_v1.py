from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from utils_storage import guardar_perfil

BASE_DIR = Path(__file__).resolve().parent.parent
RUTA_LOGOS = BASE_DIR / "Logos"

st.set_page_config(page_title="ASCEND — Mi Perfil", page_icon=str(RUTA_LOGOS / "ascend-icon.png"))

st.title("📋 Cuéntanos de ti")
st.caption("Estos datos nos ayudan a armar rutinas y planes a tu medida — nada de esto se comparte con nadie.")

# ---------------------------------------------------------------------------
# MINI-TEST DE TIEMPO DE REACCIÓN
# ---------------------------------------------------------------------------
# Streamlit no puede medir milisegundos de un clic directamente en Python —
# por eso este bloque es HTML/JS embebido, que sí mide el tiempo real. El
# resultado se muestra en pantalla y el usuario lo transcribe abajo, en un
# campo normal de Streamlit — evita tener que construir un componente
# bidireccional completo (que requeriría un build de React/npm aparte).
st.subheader("1. Prueba de tiempo de reacción")
st.write("Da clic en el botón, espera a que el cuadro cambie a verde, y da clic lo más rápido que puedas.")

components.html(
    """
    <div style="font-family: sans-serif; text-align: center;">
      <div id="caja" style="width: 100%; height: 120px; background-color: #cc3333;
                             color: white; display: flex; align-items: center;
                             justify-content: center; border-radius: 10px; cursor: pointer;
                             font-size: 18px;">
        Da clic para empezar
      </div>
      <p id="resultado" style="font-size: 20px; font-weight: bold; margin-top: 10px;"></p>
    </div>

    <script>
      const caja = document.getElementById("caja");
      const resultado = document.getElementById("resultado");
      let estado = "espera_inicio";
      let horaInicio = 0;
      let timeoutId = null;

      caja.addEventListener("click", () => {
        if (estado === "espera_inicio") {
          estado = "contando";
          caja.style.backgroundColor = "#cc3333";
          caja.innerText = "Espera el verde...";
          resultado.innerText = "";
          const demora = 1000 + Math.random() * 2500;
          timeoutId = setTimeout(() => {
            caja.style.backgroundColor = "#2e8b3d";
            caja.innerText = "¡YA! Da clic";
            horaInicio = performance.now();
            estado = "listo";
          }, demora);

        } else if (estado === "contando") {
          clearTimeout(timeoutId);
          estado = "espera_inicio";
          caja.style.backgroundColor = "#cc3333";
          caja.innerText = "Muy pronto — da clic para reintentar";

        } else if (estado === "listo") {
          const tiempoMs = performance.now() - horaInicio;
          const tiempoSeg = (tiempoMs / 1000).toFixed(3);
          resultado.innerText = "Tu tiempo: " + tiempoSeg + " segundos — cópialo abajo 👇";
          estado = "espera_inicio";
          caja.style.backgroundColor = "#cc3333";
          caja.innerText = "Da clic para intentar de nuevo";
        }
      });
    </script>
    """,
    height=220,
)

reaction_time_sec = st.number_input(
    "Escribe aquí el resultado que te salió arriba (en segundos):",
    min_value=0.05, max_value=3.0, value=0.35, step=0.01, format="%.3f",
)

st.divider()

# ---------------------------------------------------------------------------
# FORMULARIO DE DATOS
# ---------------------------------------------------------------------------
st.subheader("2. Tus datos")

with st.form("formulario_perfil"):
    col1, col2 = st.columns(2)
    with col1:
        gender_label = st.selectbox("Sexo", ["Femenino", "Masculino"])
        age = st.number_input("Edad", min_value=18, max_value=90, value=25, step=1)
        height_cm = st.number_input("Estatura (cm)", min_value=140, max_value=210, value=165, step=1)
        weight_kg = st.number_input("Peso (kg)", min_value=35.0, max_value=200.0, value=65.0, step=0.5)
        waist_circumference_cm = st.number_input("Circunferencia de cintura (cm)", min_value=50, max_value=150, value=80, step=1)

    with col2:
        sit_and_reach_cm = st.number_input(
            "Flexibilidad — sit and reach (cm)", min_value=-20, max_value=45, value=10, step=1,
            help="Siéntate con piernas extendidas y estira los brazos hacia tus pies lo más que puedas; mide cuánto rebasas (positivo) o te falta (negativo) para tocar la punta de tus pies.",
        )
        cross_situp_count = st.number_input(
            "Abdominales en 60 segundos (repeticiones)", min_value=0, max_value=100, value=20, step=1,
        )
        standing_long_jump_cm = st.number_input(
            "Salto de longitud sin carrera (cm)", min_value=50, max_value=350, value=150, step=1,
            help="Desde parado, salta hacia adelante lo más lejos que puedas y mide la distancia.",
        )

    enviado = st.form_submit_button("Guardar mi perfil", use_container_width=True)

    if enviado:
        gender_code = "F" if gender_label == "Femenino" else "M"

        perfil = {
            "gender_code": gender_code,
            "age": age,
            "height_cm": height_cm,
            "weight_kg": weight_kg,
            "waist_circumference_cm": waist_circumference_cm,
            "sit_and_reach_cm": sit_and_reach_cm,
            "cross_situp_count": cross_situp_count,
            "standing_long_jump_cm": standing_long_jump_cm,
            "reaction_time_sec": reaction_time_sec,
        }

        usuario_id = guardar_perfil(perfil)
        st.session_state["usuario_id"] = usuario_id
        st.session_state["perfil_usuario"] = perfil

        st.success(f"¡Listo! Tu perfil quedó guardado (ID: {usuario_id[:8]}...)")
        st.json(perfil)

        # TODO: una vez que copies Models/clasificador_restringido_F.joblib y
        # _M.joblib a este repo, aquí es donde se llama a clasificar_usuario()
        # del pipeline piloto para obtener el nivel_cluster oculto — todavía
        # no está conectado porque esos archivos no viven en este repo aún.
