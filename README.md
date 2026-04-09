# 🤖 Asistente EduDB – Normalización y Formas Normales

Este proyecto fue desarrollado como trabajo integrador de la materia **Inteligencia Artificial (5° año)** de la carrera **Ingeniería en Sistemas de Información**.  
Combina un **grafo semántico en Neo4j**, reglas de **Formas Normales**, un **LLM** y una interfaz web para crear un asistente capaz de razonar sobre normalización de bases de datos.

La documentación técnica de este proyecto se encuentra disponible en el siguiente repositorio:
[Documentación técnica del proyecto](https://github.com/PauRodriguezz/EduDB_Documentacion_Tecnica)

---

## 🧠 ¿Qué hace este asistente?
El sistema ofrece **dos modos principales**:

### 🔹 1. Chat libre sobre formas normales

Permite hacer preguntas en lenguaje natural como:

- “¿El esquema *Pedido* cumple 2FN?”
- “¿En qué forma normal está el esquema Pedido?”
- “¿Qué se requiere para cumplir 3FN?”

El LLM interpreta la consulta, ejecuta búsquedas en Neo4j y devuelve explicaciones claras, basadas en el grafo.

### 🔹 2. Evaluación guiada de un nuevo esquema

El usuario puede ingresar:

- Nombre del esquema  
- Lista de atributos  
- Indicar cuáles son PK  
- Respuestas simples sobre dependencias **parciales** y **transitivas**

El sistema:

1. Crea el esquema y los atributos dentro del grafo (con sus `INSTANCE_OF` correspondientes).  
2. Evalúa **1FN / 2FN / 3FN** aplicando reglas teóricas reales.  
3. Crea relaciones **CUMPLE** o **NO_CUMPLE** con detalles.  
4. Devuelve una explicación didáctica del resultado.

Todo queda almacenado en Neo4j siguiendo el metamodelo de EduDB (FrameClass, Slot, Daemon, etc.).

---

## 📁 Estructura del proyecto
```text
.
├── app/
│   ├──__init__.py          # Convierte la carpeta en paquete importable
│   ├── app.py              # Servidor FastAPI + rutas HTTP + interfaz web
│   ├── agent.py            # Lógica del asistente + evaluación guiada + consultas al grafo
│   ├── llm_service.py      # Integración con Ollama + LangChain
│   ├── main.py             # CLI para interactuar por consola
│
├── neo4j/
│   └── setup.cypher        # Script para recrear el grafo completo desde cero
│
├── requirements.txt        # Dependencias del proyecto
├── .env                    # Credenciales Neo4j
└── README.md               # Este archivo :)
```

## ⚙️ Instalación y ejecución
📝 **Antes de empezar:**  
Asegurate de tener **Python 3.10+**, **Neo4j Aura / Desktop** y **Ollama** instalados.

### 1️⃣ Crear entorno virtual
**Windows (PowerShell)**
```bash
python -m venv .venv
.\.venv\Scripts\activate
```
**Windows (Git Bash)**
```bash
python -m venv .venv
source .venv/Scripts/activate
```
**Linux / Mac**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2️⃣ Instalar dependencias
```bash
pip install -r requirements.txt
```

### 3️⃣ Configurar el archivo .env
Creá un archivo .env en el root con:
```bash
# Neo4j
NEO4J_URI=neo4j+s://<tu-id>.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=<password>
NEO4J_DATABASE=neo4j

# LLM (Ollama local o remoto)
CLOUD_OLLAMA_URL=http://127.0.0.1:11434
LLM_MODEL=gpt-oss:120b-cloud
API_TOKEN=
```

### 4️⃣ Ejecutar el servidor
```bash
uvicorn app.app:app --reload
```

Abrir en el navegador:
```bash
http://127.0.0.1:8000
```
Si preferís hacer consultas desde la terminal, podés ejecutar el asistente en modo CLI con:
```bash
python -m app.main
```
Tené en cuenta que desde la consola solo se pueden hacer consultas sobre esquemas ya existentes en Neo4j.
La creación guiada de nuevos esquemas está disponible únicamente desde la interfaz web.

### 🧩 Recrear el grafo desde cero (Neo4j)
En el repo hay una carpeta /neo4j con el archivo:
```bash
setup.cypher
```
En ese archivo se encuentran los comandos necesarios para recrear el grafo que estamos utilizando en neo4j 
