from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from utils_db import (
    crear_usuario,
    verificar_login,
    guardar_perfil,
    obtener_perfil,
    guardar_clasificacion,
    obtener_clasificacion,
)

BASE_DIR = Path(__file__).resolve().parent.parent
RUTA_LOGOS = BASE_DIR / "Logos"
RUTA_EJERCICIOS_MEDIA = BASE_DIR / "Assets" / "ejercicios"

st.set_page_config(page_title="ASCEND — Mi Perfil", page_icon=str(RUTA_LOGOS / "ascend-icon.png"))

GIFS_TESTS = {
    "situps": RUTA_EJERCICIOS_MEDIA / "3679-6ZCiYWQ.gif",
    "salto": RUTA_EJERCICIOS_MEDIA / "salto-de-longitud.gif",
    "sit_and_reach": RUTA_EJERCICIOS_MEDIA / "sit-and-reach.gif",
}

if "usuario_id" not in st.session_state:
    st.session_state["usuario_id"] = None
if "username" not in st.session_state:
    st.session_state["username"] = None


# ═══════════════════════════════════════════════════════════════════════════
# BLOQUE 1 — LOGIN / CREAR CUENTA (solo se ve si NO hay sesión)
# ═══════════════════════════════════════════════════════════════════════════
def pantalla_auth() -> None:
    st.title("👋 Bienvenido a ASCEND")
    st.caption("Crea tu cuenta o inicia sesión para guardar tu progreso.")

    tab_login, tab_registro = st.tabs(["Iniciar sesión", "Crear cuenta"])

    with tab_login:
        with st.form("form_login"):
            username = st.text_input("Usuario", key="login_username")
            password = st.text_input("Contraseña", type="password", key="login_password")
            enviado = st.form_submit_button("Entrar", use_container_width=True, type="primary")

            if enviado:
                usuario_id = verificar_login(username, password)
                if usuario_id is None:
                    st.error("Usuario o contraseña incorrectos.")
                else:
                    st.session_state["usuario_id"] = usuario_id
                    st.session_state["username"] = username.strip().lower()
                    st.success("¡Sesión iniciada!")
                    st.rerun()

    with tab_registro:
        with st.form("form_registro"):
            username = st.text_input("Elige un usuario", key="registro_username")
            password = st.text_input("Elige una contraseña", type="password", key="registro_password")
            password_confirm = st.text_input("Confirma tu contraseña", type="password", key="registro_password_confirm")
            enviado = st.form_submit_button("Crear cuenta", use_container_width=True, type="primary")

            if enviado:
                if password != password_confirm:
                    st.error("Las contraseñas no coinciden.")
                else:
                    try:
                        usuario_id = crear_usuario(username, password)
                        st.session_state["usuario_id"] = usuario_id
                        st.session_state["username"] = username.strip().lower()
                        st.success("¡Cuenta creada! Ahora completa tus datos abajo.")
                        st.rerun()
                    except ValueError as e:
                        st.error(str(e))


if st.session_state["usuario_id"] is None:
    pantalla_auth()
    st.stop()  # nada de lo de abajo se ejecuta sin sesión


# ═══════════════════════════════════════════════════════════════════════════
# A partir de aquí: usuario_id existe. Header de cuenta + logout.
# ═══════════════════════════════════════════════════════════════════════════
col_titulo, col_logout = st.columns([4, 1])
with col_titulo:
    st.title("📋 Cuéntanos de ti")
    st.caption(f"Sesión de **{st.session_state['username']}** — estos datos no se comparten con nadie.")
with col_logout:
    st.write("")
    if st.button("Cerrar sesión", use_container_width=True):
        st.session_state["usuario_id"] = None
        st.session_state["username"] = None
        st.rerun()

usuario_id = st.session_state["usuario_id"]
perfil_existente = obtener_perfil(usuario_id)

if perfil_existente:
    st.info("Ya tienes un perfil guardado. Puedes actualizarlo si algo cambió.")


def mostrar_gif_o_placeholder(ruta_gif: Path, caption: str) -> None:
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
valor_default_reaccion = perfil_existente["reaction_time_sec"] if perfil_existente else 0.35
reaction_time_sec = st.number_input(
    "Tu resultado (segundos):", min_value=0.05, max_value=3.0,
    value=valor_default_reaccion, step=0.01, format="%.3f", key="reaction_time_input",
)

st.divider()

# ---------------------------------------------------------------------------
# 2. ABDOMINALES
# ---------------------------------------------------------------------------
st.subheader("2. Abdominales en 60 segundos")
col_gif, col_timer = st.columns([1, 1.3])
with col_gif:
    mostrar_gif_o_placeholder(GIFS_TESTS["situps"], "Sit-up con brazos cruzados")
with col_timer:
    st.write("Da clic y haz todas las que puedas mientras corre el cronómetro.")
    components.html(cronometro_html("trabajo", duracion_seg=60), height=150)

valor_default_situps = perfil_existente["cross_situp_count"] if perfil_existente else 20
cross_situp_count = st.number_input(
    "¿Cuántas hiciste?", min_value=0, max_value=100, value=valor_default_situps, step=1, key="situp_input",
)

st.divider()

# ---------------------------------------------------------------------------
# 3. SALTO DE LONGITUD
# ---------------------------------------------------------------------------
st.subheader("3. Salto de longitud sin carrera")
col_gif, col_timer = st.columns([1, 1.3])
with col_gif:
    mostrar_gif_o_placeholder(GIFS_TESTS["salto"], "Salto de longitud sin carrera")
with col_timer:
    st.write("Ponte de pie, prepárate, y salta hacia adelante lo más lejos que puedas. Mide la distancia con una cinta métrica.")
    components.html(cronometro_html("preparacion"), height=130)

valor_default_salto = int(perfil_existente["standing_long_jump_cm"]) if perfil_existente else 150
standing_long_jump_cm = st.number_input(
    "Distancia saltada (cm):", min_value=50, max_value=350, value=valor_default_salto, step=1, key="jump_input",
)

st.divider()

# ---------------------------------------------------------------------------
# 4. FLEXIBILIDAD (SIT AND REACH)
# ---------------------------------------------------------------------------
st.subheader("4. Flexibilidad (sit and reach)")
col_gif, col_timer = st.columns([1, 1.3])
with col_gif:
    mostrar_gif_o_placeholder(GIFS_TESTS["sit_and_reach"], "Sit and reach")
with col_timer:
    st.write("Siéntate con las piernas extendidas y estira los brazos hacia tus pies lo más que puedas.")
    components.html(cronometro_html("preparacion"), height=130)

valor_default_reach = int(perfil_existente["sit_and_reach_cm"]) if perfil_existente else 10
sit_and_reach_cm = st.number_input(
    "¿Cuánto rebasaste (+) o te faltó (-) para tocar tus pies? (cm):",
    min_value=-20, max_value=45, value=valor_default_reach, step=1, key="reach_input",
)

st.divider()

# ---------------------------------------------------------------------------
# 5. DATOS GENERALES + GUARDADO + CLASIFICACIÓN
# ---------------------------------------------------------------------------
st.subheader("5. Tus datos generales")

with st.form("formulario_perfil"):
    col1, col2 = st.columns(2)
    with col1:
        gender_default_idx = 0
        if perfil_existente:
            gender_default_idx = 0 if perfil_existente["gender_code"] == "F" else 1
        gender_label = st.selectbox("Sexo", ["Femenino", "Masculino"], index=gender_default_idx)
        age = st.number_input("Edad", min_value=18, max_value=90,
                               value=perfil_existente["age"] if perfil_existente else 25, step=1)
    with col2:
        height_cm = st.number_input("Estatura (cm)", min_value=140, max_value=210,
                                     value=int(perfil_existente["height_cm"]) if perfil_existente else 165, step=1)
        weight_kg = st.number_input("Peso (kg)", min_value=35.0, max_value=200.0,
                                     value=perfil_existente["weight_kg"] if perfil_existente else 65.0, step=0.5)

    waist_circumference_cm = st.number_input(
        "Circunferencia de cintura (cm)", min_value=50, max_value=150,
        value=int(perfil_existente["waist_circumference_cm"]) if perfil_existente else 80, step=1,
    )

    from utils_rutinas import OBJETIVOS

    objetivo_default_idx = 0
    if perfil_existente and perfil_existente.get("objetivo") in OBJETIVOS:
        objetivo_default_idx = OBJETIVOS.index(perfil_existente["objetivo"])
    objetivo = st.selectbox(
        "¿Cuál es tu objetivo principal?", OBJETIVOS, index=objetivo_default_idx,
        help="Uno solo — esto ajusta el enfoque de tus rutinas y tu plan de nutrición.",
    )

    enviado = st.form_submit_button("Guardar mi perfil", use_container_width=True, type="primary")

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
            "objetivo": objetivo,
        }

        guardar_perfil(usuario_id, perfil)
        st.session_state["perfil_usuario"] = perfil
        st.success("¡Perfil guardado!")

        # -----------------------------------------------------------------
        # CONEXIÓN CON EL CLASIFICADOR RESTRINGIDO (nivel_cluster oculto)
        # -----------------------------------------------------------------
        # TODO(David): renombra "5.5. pipeline_piloto_clasificacion.py" a
        # "pipeline_clasificacion.py" en la raíz del repo — con puntos y
        # espacios en el nombre, Python no puede importarlo como módulo.
        # Y copia clasificador_restringido_F.joblib / _M.joblib a Models/
        # junto a ese archivo (ya los tienes generados, según tu captura).
        try:
            from pipeline_clasificacion import clasificar_usuario

            resultado = clasificar_usuario(perfil)
            guardar_clasificacion(usuario_id, resultado)
            # Debug de servidor — NUNCA se muestra en la UI, solo en la
            # terminal donde corre `streamlit run`, para que puedas verificar
            # que el clasificador está asignando clusters razonables.
            print(
                f"[ASCEND][clasificacion] usuario={st.session_state['username']} "
                f"genero={resultado['gender_code']} "
                f"cluster={resultado['nivel_cluster']} "
                f"nombre='{resultado['nivel_cluster_nombre']}' "
                f"modelo={resultado.get('modelo_usado')} "
                f"probas={resultado.get('probabilidades')}"
            )
            # Nota: a propósito NO mostramos nivel_cluster_nombre aquí — es
            # dato interno. El usuario solo debe ver progreso vía XP.
            st.toast("Tu plan ya está personalizado con tus resultados 💪")
        except (ImportError, FileNotFoundError) as e:
            # RESERVADO: mientras no exista pipeline_clasificacion.py o los
            # .joblib no estén copiados al repo, el perfil se guarda igual
            # y la clasificación se hace en cuanto conectes esa pieza.
            st.info(
                "Tu perfil quedó guardado. La personalización automática por "
                "clúster se activará en cuanto conectemos el modelo (pendiente)."
            )
        except Exception as e:
            st.warning(f"Perfil guardado, pero hubo un problema al clasificar: {e}")
