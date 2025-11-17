# llm_service.py — LangChain (LCEL) + router de intención para EduDB
import os
from typing import Dict, Any, Literal, Optional
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain_community.llms import Ollama

load_dotenv()

# ⚙️ Variables del entorno
OLLAMA_BASE = os.getenv("CLOUD_OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("LLM_MODEL", "gpt-oss:120b-cloud")
API_TOKEN = os.getenv("API_TOKEN", "")
TEMPERATURE = 0.2  # baja temperatura para respuestas más precisas

# ================================
# Modelo del LLM (Ollama local/remoto)
# ================================
llm = Ollama(
    model=OLLAMA_MODEL,
    base_url=OLLAMA_BASE,
    temperature=TEMPERATURE,
)

# ================================
# Esquemas Pydantic (intents EduDB)
# ================================

class EstadoFNParams(BaseModel):
    """
    Para preguntas tipo:
    - "¿Pedido cumple 2FN?"
    - "¿en qué forma normal está el esquema Pedido?"
    - "qué formas normales cumple Pedido"
    """
    esquema: Optional[str] = None       # nombre del esquema: "Pedido", "Cliente_Direccion", etc.
    forma_normal: Optional[str] = None  # "1FN", "2FN", "3FN" (normalizable)


class RequisitosFNParams(BaseModel):
    """
    Para preguntas tipo:
    - "qué se requiere para cumplir 2FN"
    - "qué condiciones tiene que cumplir un esquema para estar en 3FN"
    - "qué le falta a Pedido para cumplir 2FN" (luego en el agent cruzamos con el grafo)
    """
    esquema: Optional[str] = None
    forma_normal: Optional[str] = None


class Route(BaseModel):
    intent: Literal[
        "estado_fn",       # saber si cumple/no cumple, o qué FN tiene un esquema
        "requisitos_fn",   # saber qué se requiere para cumplir una FN
        "desconocido",
    ] = "desconocido"
    params: Dict[str, Any] = Field(default_factory=dict)


parser = PydanticOutputParser(pydantic_object=Route)

# ================================
# Prompt de routing de intención
# ================================

template = """
Sos un router de intención para un asistente de normalización de bases de datos (EduDB).
Tu trabajo es LEER la consulta del usuario y devolver SOLO un JSON que respete
el siguiente esquema:
{format_instructions}

Contexto:
- El dominio es diseño de bases de datos relacionales y formas normales (1FN, 2FN, 3FN).
- Los esquemas tienen nombres como "Pedido", "Cliente_Direccion", etc.
- El grafo sabe si un esquema CUMPLE o NO_CUMPLE una FN, y también puede usarse
  para explicar qué le falta para cumplirla.

Intents válidos:

1) "estado_fn"
   Usalo cuando el usuario pregunte por el ESTADO de un esquema respecto a alguna forma normal,
   o quiera saber qué formas normales cumple.
   Ejemplos:
   - "¿Pedido cumple 2FN?"
   - "en qué forma normal está el esquema Pedido"
   - "qué formas normales cumple Pedido"
   - "Pedido está en 1FN, 2FN o 3FN?"
   Params:
     - esquema (str, opcional): nombre del esquema si se menciona ("Pedido", "Cliente_Direccion"...).
     - forma_normal (str, opcional): forma normal si se menciona explícitamente ("1FN", "2FN", "3FN").

2) "requisitos_fn"
   Usalo cuando el usuario pregunte por los REQUISITOS o condiciones de una forma normal,
   o qué haría falta para cumplirla.
   Ejemplos:
   - "qué se requiere para cumplir 2FN"
   - "qué condiciones tiene que cumplir un esquema para estar en 3FN"
   - "qué le falta a Pedido para estar en 3FN"
   - "explicame qué pide la 1FN"
   Params:
     - forma_normal (str, opcional): la FN de la que se habla ("1FN", "2FN", "3FN") si aparece.
     - esquema (str, opcional): nombre del esquema si se menciona ("Pedido", etc.).

Reglas:
- No inventes campos. Si no se menciona una forma normal o un esquema, dejalos en null.
- Extraé los nombres de esquemas y formas normales tal como aparezcan en el texto,
  pero normalizá la forma normal (1fn → 1FN, "primera forma normal" → 1FN, etc.).
- Si la pregunta no encaja claramente en ninguno de los dos intents, usá intent="desconocido".
- La salida DEBE ser SOLO el JSON, sin explicaciones ni texto adicional.

Usuario: {text}
Salida:
"""

prompt = PromptTemplate(
    template=template,
    input_variables=["text"],
    partial_variables={"format_instructions": parser.get_format_instructions()},
)

# Cadena LCEL: prompt -> llm -> parser
chain = prompt | llm | parser

# ================================
# Normalizaciones útiles
# ================================

_FN_MAP = {
    "1fn": "1FN",
    "1nf": "1FN",
    "primeraformanormal": "1FN",
    "primeraforma": "1FN",

    "2fn": "2FN",
    "2nf": "2FN",
    "segundaformanormal": "2FN",
    "segundaforma": "2FN",

    "3fn": "3FN",
    "3nf": "3FN",
    "terceraformanormal": "3FN",
    "terceraforma": "3FN",
}

def _clean_str(x: Optional[str]) -> Optional[str]:
    if x is None:
        return None
    s = str(x).strip()
    return s or None

def _norm_forma_normal(x: Optional[str]) -> Optional[str]:
    if not x:
        return None
    t = str(x).lower().replace(" ", "")
    return _FN_MAP.get(t, x.strip())

# ================================
# Función pública: route_query
# ================================

def route_query(text: str) -> Dict[str, Any]:
    """
    Recibe el texto del usuario y devuelve algo como:
      { "intent": "estado_fn", "params": {"esquema": "Pedido", "forma_normal": "2FN"} }
      { "intent": "requisitos_fn", "params": {"forma_normal": "3FN"} }
      { "intent": "desconocido", "params": {} }
    """
    try:
        routed: Route = chain.invoke({"text": text})

        if routed.intent == "estado_fn":
            ef = EstadoFNParams(**routed.params)
            clean = {
                "esquema": _clean_str(ef.esquema),
                "forma_normal": _norm_forma_normal(ef.forma_normal),
            }
            return {"intent": "estado_fn", "params": clean}

        if routed.intent == "requisitos_fn":
            rf = RequisitosFNParams(**routed.params)
            clean = {
                "esquema": _clean_str(rf.esquema),
                "forma_normal": _norm_forma_normal(rf.forma_normal),
            }
            return {"intent": "requisitos_fn", "params": clean}

        # Fallback
        return {"intent": "desconocido", "params": {}}

    except Exception as e:
        # Falla segura
        return {"intent": "desconocido", "params": {"error": str(e)}}
