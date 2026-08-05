# ASCEND 🛡️

**Fitness y nutrición gamificados, adaptados a ti — no a un promedio.**

Sistema inteligente de generación de rutinas fitness y alimentación nutritiva,
construido con ciencia de datos real: un perfilador físico entrenado sobre
430,666 registros del programa nacional de aptitud física de Corea del Sur
(KSPO), un motor de recomendación sobre un catálogo de 1,324 ejercicios con
dificultad continua calificada por LLM, y un módulo de nutrición con visión
por computadora.

🚀 **App en vivo:** https://ascend-mejora-t.streamlit.app

📊 **Repo de desarrollo** (notebooks, datos, entrenamiento de modelos):
https://github.com/DavidDiaz95/Desarrollo-de-ASCEND

---

## ¿Qué hace ASCEND?

| Módulo | Qué hace |
|---|---|
| 🧬 **Perfilador físico** | Con solo 8 datos auto-medibles (edad, altura, peso, cintura, flexibilidad, abdominales, salto, tiempo de reacción), un clasificador aproxima el perfil de condición física que un GMM descubrió sobre datos de laboratorio. La clasificación **nunca se muestra al usuario** — solo calibra la dificultad inicial. |
| 🏋️ **Motor de rutinas** | Genera rutinas desde un catálogo de 1,324 ejercicios reales (con GIFs), balanceando zonas musculares según el objetivo declarado y el historial real de entrenamiento. La dificultad se ajusta dinámicamente con el feedback del usuario (fácil / bien / difícil). |
| 🥗 **Motor de nutrición** | Toma una foto del refrigerador, identifica los ingredientes con visión por computadora, y sugiere recetas reales (vía Spoonacular) alineadas a la meta calórica del usuario (Mifflin-St Jeor). |
| 🎮 **Gamificación** | XP por rutinas completadas (más difícil = más XP) y comidas confirmadas, niveles, rachas de constancia y un tablero de progreso con radar muscular. |
| 🤖 **Asistente** | Chat con contexto real del usuario (objetivo, XP, racha, equipo disponible) y guardrails contra prompt injection. |

## Arquitectura

```
ASCEND/
├── main.py                      # Punto de entrada (página de bienvenida + login)
├── pages/                       # Páginas de la app multi-page de Streamlit
│   ├── 01_Mi_Perfil.py          #   Perfil físico → clasificación interna
│   ├── 02_Rutinas.py            #   Menú de rutinas + ejecución + feedback
│   ├── 03_Nutricion.py          #   Foto del refri → visión → recetas + XP
│   ├── 04_Dashboard.py          #   XP, racha, radar muscular, progreso
│   └── 05_Asistente.py          #   Chat con contexto del usuario
│
├── utils_db.py                  # Persistencia SQLite (usuarios, perfil, interacciones)
├── utils_rutinas.py             # Catálogo, score de ejercicios, generación de rutinas
├── utils_nutricion.py           # Visión, traducción, Spoonacular, metas nutricionales
├── utils_dashboard.py           # Agregaciones para el tablero de progreso
├── pipeline_clasificacion.py    # Clasificador restringido (feature engineering + predicción)
├── prompts.py                   # System prompt modular del asistente (con guardrails)
│
├── Models/                      # Modelos entrenados (.joblib): clasificador + GMM
├── Assets/                      # Catálogo de ejercicios (parquet) y recursos
├── Logos/                       # Identidad visual de ASCEND
├── ascend.db                    # Base SQLite
│
├── pyproject.toml / uv.lock     # Dependencias gestionadas con uv
└── requirements.txt             # Dependencias para Streamlit Community Cloud
```

**Flujo de datos:** el usuario completa su perfil → `pipeline_clasificacion.py`
reconstruye las variables de laboratorio (fórmula de Deurenberg + regresores
auxiliares) y predice el clúster → `utils_rutinas.py` usa ese clúster solo
como punto de partida del rango de dificultad → cada rutina completada y cada
feedback ajustan el nivel objetivo → todo persiste en SQLite vía `utils_db.py`.

## Ciencia de datos detrás

- **Segmentación no supervisada**: Gaussian Mixture Models separados por sexo
  (k=3), entrenados sobre 18 variables en percentiles con PCA, validados con
  split train/test (silhouette, Davies-Bouldin, Calinski-Harabasz).
- **Clasificador restringido**: regresión logística (F1-macro 0.78–0.81)
  elegida sobre Random Forest/MLP por mejor generalización y menor peso del
  artefacto — clave para los límites de memoria de Streamlit Community Cloud.
- **Dificultad continua vía LLM**: los 1,324 ejercicios calificados 1–100 con
  una rúbrica explícita (complejidad técnica, riesgo, fuerza requerida),
  tras detectar un sesgo unidireccional en la etiqueta categórica original.
- **Motor de score**: `0.55·relevancia_zona + 0.45·(1 − |dificultad − objetivo|)`
  — la similitud coseno se descartó con evidencia empírica (saturaba la
  dificultad entregada sin importar lo solicitado).

El detalle completo (EDA, metodología, métricas y decisiones documentadas)
está en el [repo de desarrollo](https://github.com/DavidDiaz95/Desarrollo-de-ASCEND)
y su documento final.

## Correr localmente

### Con `uv` (recomendado)

```bash
git clone https://github.com/DavidDiaz95/ASCEND.git
cd ASCEND
uv sync
uv run streamlit run main.py
```

### Con pip

```bash
git clone https://github.com/DavidDiaz95/ASCEND.git
cd ASCEND
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
streamlit run main.py
```

### Llaves de API

La app usa OpenAI (visión y asistente) y Spoonacular (recetas y nutrición).
Crea `.streamlit/secrets.toml` (no se versiona) con:

```toml
OPENAI_API_KEY = "sk-..."
SPOONACULAR_API_KEY = "..."
```

En producción, las llaves viven en los *secrets* de la configuración avanzada
de Streamlit Community Cloud — nunca en el repositorio.

> **Nota sobre Spoonacular:** el plan gratuito tiene cuota de 50 puntos/día.
> La app maneja el error de cuota agotada con un mensaje amigable en vez de
> tronar.

## Despliegue

Desplegado en **Streamlit Community Cloud** apuntando a `main.py`. Los
artefactos de modelo (`Models/*.joblib`) están deliberadamente aligerados
(regresión logística + reconstructores compactos) para operar dentro de los
límites de memoria del plan gratuito.

## Fuentes de datos

- **KSPO** — Korea Sports Promotion Foundation, programa 국민체력100
  ([Big Data Culture Portal](https://www.bigdata-culture.kr/bigdata/user/data_market/detail.do?id=ace0aea7-5eee-48b9-b616-637365d665c1))
- **Catálogo de ejercicios** — [hasaneyldrm/exercises-dataset](https://github.com/hasaneyldrm/exercises-dataset)
  (1,324 ejercicios con GIFs) + [yuhonas/free-exercise-db](https://github.com/yuhonas/free-exercise-db)
  (dificultad de referencia)
- **Recetas y nutrición** — [Spoonacular API](https://spoonacular.com/food-api)

## Autor

**David Díaz Sánchez** — Trabajo final del Diplomado en Ciencia de Datos,
FES Acatlán (UNAM), Generación 33.
