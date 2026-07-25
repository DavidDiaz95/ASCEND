from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from utils_storage import guardar_perfil

BASE_DIR = Path(__file__).resolve().parent.parent
RUTA_LOGOS = BASE_DIR / "Logos"
RUTA_EJERCICIOS_MEDIA = BASE_DIR / "Assets" / "ejercicios"

st.set_page_config(page_title="ASCEND — Mi Perfil", page_icon=str(RUTA_LOGOS / "ascend-icon.png"))

# ═══════════════════════════════════════════════════════════════════════════
# ⭐ ÚNICO LUGAR QUE NECESITAS EDITAR PARA AGREGAR LOS 3 GIFS ⭐
# Cuando tengas cada archivo, ponlo dentro de Assets/ejercicios/ y solo
# cambia el nombre de archivo aquí abajo (no toques nada más del código).
# Si el archivo no existe todavía, se muestra un placeholder automáticamente,
# del mismo tamaño, para que el layout no salte cuando lo agregues.
# ═══════════════════════════════════════════════════════════════════════════
GIFS_TESTS = {
    "situps": RUTA_EJERCICIOS_MEDIA / "3679-6ZCiYWQ.gif",
    "salto": RUTA_EJERCICIOS_MEDIA / "salto-de-longitud.gif",
    "sit_and_reach": RUTA_EJERCICIOS_MEDIA / "sit-and-reach.gif",
}
# ═══════════════════════════════════════════════════════════════════════════

st.title("📋 Cuéntanos de ti")
st.caption("Estos datos nos ayudan a armar rutinas y planes a tu medida — nada de esto se comparte con nadie.")


def mostrar_gif_o_placeholder(ruta_gif: Path, caption: str) -> None:
    """Muestra el GIF si ya existe el archivo; si no, reserva el espacio
    visualmente con un placeholder del mismo tamaño."""
    if ruta_gif.exists():
        st.image(str(ruta_gif), caption=caption, use_container_width=True)
    else:
        st.markdown(
            f"""
            <div style="width: 100%; aspect-ratio: 1 / 1; background-color: #d8efdc;
                        border: 2px dashed #006a20; border-radius: 10px;
                        display: flex; align-items: center; justify-content: center;
                        text-align: center; color: #006a20; font-family: sans-serif;
                        padding: 10px;">
                📹<br>GIF pendiente<br><small>{caption}</small>
            </div>
            """,
            unsafe_allow_html=True,
        )


# ---------------------------------------------------------------------------
# CRONÓMETRO REUTILIZABLE (HTML/JS) — dos modos
# ---------------------------------------------------------------------------
def cronometro_html(modo: str, duracion_seg: int = 60) -> str:
    if modo == "preparacion":
        return """
        <div style="font-family: sans-serif; text-align: center;">
          <div id="caja" style="width: 100%; height: 100px; background-color: #006a20;
                                 color: white; display: flex; align-items: center;
                                 justify-content: center; border-radius: 10px; cursor: pointer;
                                 font-size: 22px;">
            Da clic para iniciar la cuenta regresiva
          </div>
        </div>
        <script>
          const caja = document.getElementById("caja");
          caja.addEventListener("click", () => {
            const pasos = ["3...", "2...", "1...", "¡YA! Realiza el movimiento"];
            let i = 0;
            caja.style.pointerEvents = "none";
            const intervalo = setInterval(() => {
              caja.innerText = pasos[i];
              i++;
              if (i >= pasos.length) {
                clearInterval(intervalo);
                setTimeout(() => {
                  caja.innerText = "Da clic para repetir";
                  caja.style.pointerEvents = "auto";
                }, 1500);
              }
            }, 700);
          });
        </script>
        """
    elif modo == "trabajo":
        return f"""
        <div style="font-family: sans-serif; text-align: center;">
          <div id="caja" style="width: 100%; height: 100px; background-color: #006a20;
                                 color: white; display: flex; align-items: center;
                                 justify-content: center; border-radius: 10px; cursor: pointer;
                                 font-size: 22px;">
            Da clic para empezar ({duracion_seg}s)
          </div>
        </div>
        <script>
          const caja = document.getElementById("caja");
          let segundosRestantes = {duracion_seg};
          let intervalo = null;
          caja.addEventListener("click", () => {{
            if (intervalo !== null) return;
            caja.style.pointerEvents = "none";
            intervalo = setInterval(() => {{
              segundosRestantes--;
              caja.innerText = segundosRestantes + " segundos restantes";
              if (segundosRestantes <= 0) {{
                clearInterval(intervalo);
                caja.style.backgroundColor = "#cc3333";
                caja.innerText = "¡ALTO! Escribe cuántas hiciste abajo 👇";
              }}
            }}, 1000);
          }});
        </script>
        """


# ---------------------------------------------------------------------------
# 1. TIEMPO DE REACCIÓN
# ---------------------------------------------------------------------------
st.subheader("1. Tiempo de reacción")
st.write("Da clic, espera a que el cuadro cambie a verde, y da clic lo más rápido que puedas.")

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
    "Tu resultado (segundos):", min_value=0.05, max_value=3.0, value=0.35, step=0.01, format="%.3f",
    key="reaction_time_input",
)

st.divider()

# ---------------------------------------------------------------------------
# 2. ABDOMINALES — GIF + cronómetro de trabajo (60s)
# ---------------------------------------------------------------------------
st.subheader("2. Abdominales en 60 segundos")

col_gif, col_timer = st.columns([1, 1.3])
with col_gif:
    mostrar_gif_o_placeholder(GIFS_TESTS["situps"], "Sit-up con brazos cruzados")
with col_timer:
    st.write("Da clic y haz todas las que puedas mientras corre el cronómetro.")
    components.html(cronometro_html("trabajo", duracion_seg=60), height=150)

cross_situp_count = st.number_input(
    "¿Cuántas hiciste?", min_value=0, max_value=100, value=20, step=1, key="situp_input",
)

st.divider()

# ---------------------------------------------------------------------------
# 3. SALTO DE LONGITUD — GIF + cuenta regresiva de preparación
# ---------------------------------------------------------------------------
st.subheader("3. Salto de longitud sin carrera")

col_gif, col_timer = st.columns([1, 1.3])
with col_gif:
    mostrar_gif_o_placeholder(GIFS_TESTS["salto"], "Salto de longitud sin carrera")
with col_timer:
    st.write("Ponte de pie, prepárate, y salta hacia adelante lo más lejos que puedas. Mide la distancia con una cinta métrica.")
    components.html(cronometro_html("preparacion"), height=130)

standing_long_jump_cm = st.number_input(
    "Distancia saltada (cm):", min_value=50, max_value=350, value=150, step=1, key="jump_input",
)

st.divider()

# ---------------------------------------------------------------------------
# 4. FLEXIBILIDAD (SIT AND REACH) — GIF + cuenta regresiva de preparación
# ---------------------------------------------------------------------------
st.subheader("4. Flexibilidad (sit and reach)")

col_gif, col_timer = st.columns([1, 1.3])
with col_gif:
    mostrar_gif_o_placeholder(GIFS_TESTS["sit_and_reach"], "Sit and reach")
with col_timer:
    st.write("Siéntate con las piernas extendidas y estira los brazos hacia tus pies lo más que puedas.")
    components.html(cronometro_html("preparacion"), height=130)

sit_and_reach_cm = st.number_input(
    "¿Cuánto rebasaste (+) o te faltó (-) para tocar tus pies? (cm):",
    min_value=-20, max_value=45, value=10, step=1, key="reach_input",
)

st.divider()

# ---------------------------------------------------------------------------
# 5. RESTO DE LOS DATOS + GUARDADO
# ---------------------------------------------------------------------------
st.subheader("5. Tus datos generales")

with st.form("formulario_perfil"):
    col1, col2 = st.columns(2)
    with col1:
        gender_label = st.selectbox("Sexo", ["Femenino", "Masculino"])
        age = st.number_input("Edad", min_value=18, max_value=90, value=25, step=1)
    with col2:
        height_cm = st.number_input("Estatura (cm)", min_value=140, max_value=210, value=165, step=1)
        weight_kg = st.number_input("Peso (kg)", min_value=35.0, max_value=200.0, value=65.0, step=0.5)

    waist_circumference_cm = st.number_input("Circunferencia de cintura (cm)", min_value=50, max_value=150, value=80, step=1)

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

        # TODO: conectar clasificar_usuario() del pipeline piloto una vez que
        # copies Models/clasificador_restringido_F.joblib y _M.joblib a este repo.
