# app/agent.py — Neo4j tools + dispatcher para EduDB (formas normales)
import os
import unicodedata
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv
from neo4j import GraphDatabase

# ==========================
# Utilidades de texto
# ==========================

def _norm_text(s: Optional[str]) -> Optional[str]:
    if s is None:
        return None
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(ch for ch in s if not unicodedata.combining(ch))  # saca tildes
    s = s.strip()
    return s or None

# ==========================
# Config Neo4j
# ==========================

load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")

driver = GraphDatabase.driver(
    NEO4J_URI,
    auth=(NEO4J_USERNAME, NEO4J_PASSWORD),
)

def _run_cypher(query: str, params: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
    params = params or {}
    with driver.session(database=NEO4J_DATABASE) as session:
        result = session.run(query, params)
        return [r.data() for r in result]

# ==========================
# Reglas teóricas (hard-code)
# ==========================

REQUISITOS_FN: Dict[str, str] = {
    "1FN": (
        "1FN exige que todas las celdas de la tabla sean atómicas: "
        "no debe haber grupos repetitivos ni atributos multivaluados. "
        "Cada atributo debe contener un único valor por fila."
    ),
    "2FN": (
        "2FN exige que el esquema cumpla 1FN y que no existan dependencias "
        "parciales: ningún atributo no clave puede depender solo de una parte "
        "propia de una clave primaria compuesta."
    ),
    "3FN": (
        "3FN exige que el esquema cumpla 2FN y que no existan dependencias "
        "transitivas: ningún atributo no clave puede depender de otro atributo "
        "no clave a través de una cadena de dependencias."
    ),
}

def _norm_fn(fn: Optional[str]) -> Optional[str]:
    if not fn:
        return None
    s = str(fn).upper().strip()
    if s == "1NF":
        return "1FN"
    if s == "2NF":
        return "2FN"
    if s == "3NF":
        return "3FN"
    return s

# ==========================
# Tools Neo4j existentes
# ==========================

def tool_estado_fn(esquema: str, forma_normal: Optional[str] = None) -> Dict[str, Any]:
    """Devuelve el estado de un esquema respecto a una o varias formas normales.

    Si forma_normal está dada → devuelve una sola fila (o SIN_EVALUAR).
    Si forma_normal es None → devuelve lista para 1FN, 2FN, 3FN (si existen).
    """
    esquema = _norm_text(esquema)
    if not esquema:
        return {
            "ok": False,
            "error": "Falta el nombre del esquema.",
        }

    if forma_normal:
        fn = _norm_fn(forma_normal)
        q = """
        MATCH (es:Esquema {name:$esquema})
        OPTIONAL MATCH (es)-[c:CUMPLE]->(fn1:FrameClass {name:$fn})
        OPTIONAL MATCH (es)-[nc:NO_CUMPLE]->(fn2:FrameClass {name:$fn})
        RETURN es.name AS esquema,
               coalesce(fn1.name, fn2.name, $fn) AS forma_normal,
               CASE
                 WHEN c IS NOT NULL THEN 'CUMPLE'
                 WHEN nc IS NOT NULL THEN 'NO_CUMPLE'
                 ELSE 'SIN_EVALUAR'
               END AS estado,
               properties(c)  AS datos_cumple,
               properties(nc) AS datos_no_cumple
        """
        rows = _run_cypher(q, {"esquema": esquema, "fn": fn})
        if not rows:
            return {
                "ok": False,
                "error": f"No se encontró el esquema '{esquema}' en el grafo.",
            }
        row = rows[0]
        return {
            "ok": True,
            "esquema": row.get("esquema"),
            "forma_normal": row.get("forma_normal"),
            "estado": row.get("estado"),
            "datos_cumple": row.get("datos_cumple"),
            "datos_no_cumple": row.get("datos_no_cumple"),
        }

    # Sin forma_normal → devolvemos estado para las FNs conocidas
    q = """
    MATCH (es:Esquema {name:$esquema})
    OPTIONAL MATCH (es)-[rel:CUMPLE|NO_CUMPLE]->(fn:FrameClass)
    WHERE fn.name IN ['1FN','2FN','3FN']
    RETURN es.name AS esquema,
           fn.name AS forma_normal,
           type(rel) AS tipo_rel,
           CASE
             WHEN rel IS NULL THEN 'SIN_EVALUAR'
             WHEN type(rel) = 'CUMPLE' THEN 'CUMPLE'
             WHEN type(rel) = 'NO_CUMPLE' THEN 'NO_CUMPLE'
             ELSE 'SIN_EVALUAR'
           END AS estado,
           properties(rel) AS detalles
    ORDER BY fn.name
    """
    rows = _run_cypher(q, {"esquema": esquema})
    if not rows:
        return {
            "ok": False,
            "error": f"No se encontró el esquema '{esquema}' en el grafo.",
        }
    return {
        "ok": True,
        "esquema": esquema,
        "resultados": rows,
    }


def tool_requisitos_fn(forma_normal: str, esquema: Optional[str] = None) -> Dict[str, Any]:
    """Devuelve los requisitos teóricos de una FN y, si se da un esquema,
    cruza con el grafo para decir qué le falta o cómo está hoy.
    """
    fn = _norm_fn(forma_normal)
    desc = REQUISITOS_FN.get(fn, f"No tengo requisitos hard-codeados para {fn}.")
    esquema = _norm_text(esquema) if esquema else None

    info_estado: Optional[Dict[str, Any]] = None
    problemas: List[str] = []

    if esquema:
        estado = tool_estado_fn(esquema, fn)
        if estado.get("ok"):
            info_estado = {
                "esquema": estado.get("esquema"),
                "forma_normal": estado.get("forma_normal"),
                "estado": estado.get("estado"),
            }
            if estado.get("estado") == "NO_CUMPLE":
                detalles = estado.get("datos_no_cumple") or {}
                if "motivo" in detalles:
                    problemas.append(detalles.get("motivo"))
                if "motivos" in detalles and isinstance(detalles.get("motivos"), list):
                    problemas.extend(m for m in detalles.get("motivos") if m)
                if "parciales" in detalles:
                    problemas.append(f"Cantidad de DF parciales: {detalles.get('parciales')}")
                if "transitivas" in detalles:
                    problemas.append(f"Cantidad de DF transitivas: {detalles.get('transitivas')}")
                if "atributos" in detalles and isinstance(detalles.get("atributos"), list):
                    attrs = detalles.get("atributos")
                    if attrs:
                        problemas.append("Atributos problemáticos: " + ", ".join(attrs))

    return {
        "ok": True,
        "forma_normal": fn,
        "requisitos": desc,
        "esquema": esquema,
        "estado_actual": info_estado,
        "problemas_detectados": problemas or None,
    }

# ==========================
# flujo de Evaluación guiada de un esquema
# ==========================

def _coerce_int(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default

def crear_esquema_guiado_y_evaluar(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Crea un Esquema + Atributos + instancia de EVALUAR_FORMA_NORMAL
    a partir de un cuestionario guiado, y evalúa 1FN / 2FN / 3FN
    usando la misma lógica teórica, pero ejecutando varias consultas
    simples en lugar de un Cypher gigante.
    """
    nombre = _norm_text(payload.get("nombre_esquema"))
    if not nombre:
        return {"ok": False, "error": "Falta el nombre del esquema."}

    # -------- atributos --------
    atributos_payload = payload.get("atributos") or []
    atributos: List[Dict[str, Any]] = []
    for a in atributos_payload:
        nom = _norm_text(a.get("nombre"))
        if not nom:
            continue
        es_pk = bool(a.get("es_pk", False))
        atributos.append({"nombre": nom, "es_pk": es_pk})

    if not atributos:
        return {"ok": False, "error": "Debes indicar al menos un atributo para el esquema."}

    # -------- flags automáticos + guiados --------

    # 1FN — asumimos SIEMPRE que NO hay multivaluados
    tiene_multivaluados = False
    atributos_multivaluados = []   # no se usa más

    # 2FN — PK compuesta detectada automáticamente
    pk_es_compuesta = sum(1 for a in atributos if a.get("es_pk")) > 1

    # Dependencias parciales (PREGUNTA 3)
    tiene_parciales = bool(payload.get("tiene_parciales", False))
    cant_df_parciales = _coerce_int(payload.get("cant_df_parciales"))
    if tiene_parciales and cant_df_parciales <= 0:
        cant_df_parciales = 1
    if not tiene_parciales:
        cant_df_parciales = 0

    # Dependencias transitivas (PREGUNTA 4)
    tiene_transitivas = bool(payload.get("tiene_transitivas", False))
    cant_df_transitivas = _coerce_int(payload.get("cant_df_transitivas"))
    if tiene_transitivas and cant_df_transitivas <= 0:
        cant_df_transitivas = 1
    if not tiene_transitivas:
        cant_df_transitivas = 0

    # 1FN flag final
    sin_multival = True


    # -------- id de evaluación --------
    safe_name = nombre.replace(" ", "_")
    ev_id = f"EV_{safe_name}_GUIADO"

    # ================================
    # 1) Crear Esquema + Atributos + EV
    # ================================
    query_setup = """
    // Crear esquema (o reutilizar si ya existe)
    MERGE (es:Esquema {name:$esquema})
    WITH es, $atributos AS attrs

    // Borrar atributos viejos que ya no están en la lista nueva
    OPTIONAL MATCH (es)-[:TIENE]->(att_viejo:Atributo {esquema: es.name})
    WHERE NOT att_viejo.name IN [a IN attrs | a.nombre]
    OPTIONAL MATCH (att_viejo)-[r_viejo]-()
    DELETE r_viejo, att_viejo

    // Asegurar INSTANCE_OF del esquema
    WITH es, attrs
    MATCH (fc_es:FrameClass {name:'ESQUEMA'})
    MERGE (es)-[:INSTANCE_OF]->(fc_es)

    // Crear/actualizar atributos actuales, TIENE e INSTANCE_OF
    WITH es, attrs
    UNWIND attrs AS a
    MERGE (att:Atributo {name:a.nombre, esquema: es.name})
    SET att.es_pk = coalesce(a.es_pk, false)
    MERGE (es)-[:TIENE]->(att)
    WITH es
    MATCH (att2:Atributo {esquema: es.name})
    MATCH (fc_at:FrameClass {name:'ATRIBUTO'})
    MERGE (att2)-[:INSTANCE_OF]->(fc_at)

    // Crear instancia de evaluación (EV)
    WITH es
    MERGE (ev:EVALUAR_FORMA_NORMAL {id:$evId})
    SET ev.forma_normal = '3FN',
        ev.esquema_objetivo = es.name,
        ev.sin_atributos_multivaluados = $sin_multival,
        ev.atributos_multivaluados = $attrs_multival,
        ev.pk_compuesta = $pk_compuesta,
        ev.cant_df_parciales = $cant_parciales,
        ev.cant_df_transitivas = $cant_transitivas
    MERGE (ev)-[:EVALUA]->(es)
    WITH es, ev
    MATCH (fc_eval:FrameClass {name:'EVALUAR_FORMA_NORMAL'})
    MERGE (ev)-[:INSTANCE_OF]->(fc_eval)

    // Limpiar evaluaciones anteriores para 1FN/2FN/3FN
    WITH es
    OPTIONAL MATCH (es)-[old:CUMPLE|NO_CUMPLE]->(f:FrameClass)
    WHERE f.name IN ['1FN','2FN','3FN']
    DELETE old

    RETURN es.name AS esquema
    """
    params_setup = {
        "esquema": nombre,
        "atributos": atributos,
        "evId": ev_id,
        "sin_multival": sin_multival,
        "attrs_multival": atributos_multivaluados,
        "pk_compuesta": pk_es_compuesta,
        "cant_parciales": cant_df_parciales,
        "cant_transitivas": cant_df_transitivas,
    }

    _run_cypher(query_setup, params_setup)

    # ================================
    # 2) Calcular flags en Python
    # ================================
    ok1 = sin_multival

    # Regla correcta para 2FN:
    # - Si la PK NO es compuesta -> si cumple 1FN, entonces cumple 2FN
    # - Si la PK es compuesta -> además tiene que no tener DF parciales
    if pk_es_compuesta:
        ok2 = ok1 and (cant_df_parciales == 0)
    else:
        ok2 = ok1

    # 3FN requiere que 2FN se cumpla + sin transitivas
    ok3 = ok2 and (cant_df_transitivas == 0)

    # Motivos para 2FN si NO cumple
    motivos2: List[str] = []
    if not ok1:
        motivos2.append("No cumple 1FN")
    # Solo tiene sentido hablar de parciales si la PK es compuesta
    if pk_es_compuesta and cant_df_parciales > 0:
        motivos2.append("Tiene dependencias parciales")


    # ================================
    # 3) Escribir relaciones CUMPLE / NO_CUMPLE
    # ================================

    # ----- 1FN -----
    if ok1:
        query_1fn = """
        MATCH (es:Esquema {name:$esquema}),
              (fn:FrameClass {name:'1FN'}),
              (ev:EVALUAR_FORMA_NORMAL {id:$evId})
        MERGE (es)-[r:CUMPLE]->(fn)
        SET r.multival = 0,
            r.pk_compuesta = ev.pk_compuesta,
            r.parciales = ev.cant_df_parciales,
            r.transitivas = ev.cant_df_transitivas
        """
    else:
        query_1fn = """
        MATCH (es:Esquema {name:$esquema}),
              (fn:FrameClass {name:'1FN'}),
              (ev:EVALUAR_FORMA_NORMAL {id:$evId})
        MERGE (es)-[r:NO_CUMPLE]->(fn)
        SET r.motivo = 'Atributos multivaluados',
            r.atributos = coalesce(ev.atributos_multivaluados, [])
        """
    _run_cypher(query_1fn, {"esquema": nombre, "evId": ev_id})

    # ----- 2FN -----
    # Borrar cualquier relación vieja de 2FN (por las dudas que haya quedado algo de otra evaluación)
    _run_cypher("""
    MATCH (es:Esquema {name:$esquema})-[r:CUMPLE|NO_CUMPLE]->(fn:FrameClass {name:'2FN'})
    DELETE r
    """, {"esquema": nombre})

    if ok2:
        query_2fn = """
        MATCH (es:Esquema {name:$esquema}),
              (fn:FrameClass {name:'2FN'}),
              (ev:EVALUAR_FORMA_NORMAL {id:$evId})
        MERGE (es)-[r:CUMPLE]->(fn)
        SET r.pk_compuesta = ev.pk_compuesta,
            r.parciales = 0
        """
        _run_cypher(query_2fn, {"esquema": nombre, "evId": ev_id})
    else:
        query_2fn = """
        MATCH (es:Esquema {name:$esquema}),
              (fn:FrameClass {name:'2FN'}),
              (ev:EVALUAR_FORMA_NORMAL {id:$evId})
        MERGE (es)-[r:NO_CUMPLE]->(fn)
        SET r.motivos = $motivos2,
            r.parciales = ev.cant_df_parciales
        """
        _run_cypher(query_2fn, {
            "esquema": nombre,
            "evId": ev_id,
            "motivos2": motivos2,
        })

    # ----- 3FN -----
    if ok3:
        query_3fn = """
        MATCH (es:Esquema {name:$esquema}),
              (fn:FrameClass {name:'3FN'}),
              (ev:EVALUAR_FORMA_NORMAL {id:$evId})
        MERGE (es)-[r:CUMPLE]->(fn)
        SET r.transitivas = 0
        """
        _run_cypher(query_3fn, {"esquema": nombre, "evId": ev_id})
    else:
        query_3fn = """
        MATCH (es:Esquema {name:$esquema}),
              (fn:FrameClass {name:'3FN'}),
              (ev:EVALUAR_FORMA_NORMAL {id:$evId})
        MERGE (es)-[r:NO_CUMPLE]->(fn)
        SET r.motivo = 'Tiene dependencias transitivas',
            r.transitivas = ev.cant_df_transitivas
        """
        _run_cypher(query_3fn, {"esquema": nombre, "evId": ev_id})

    # ================================
    # 4) Resumen + consulta del estado usando la tool existente
    # ================================
    resumen = {
        "esquema": nombre,
        "cumple_1fn": ok1,
        "cumple_2fn": ok2,
        "cumple_3fn": ok3,
    }

    estado = tool_estado_fn(nombre)

    return {
        "ok": True,
        "esquema": nombre,
        "ev_id": ev_id,
        "evaluacion_resumen": resumen,
        "estado_detallado": estado,
    }


# ==========================
# Dispatcher (para intents del LLM)
# ==========================

def dispatch(intent: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Recibe el intent del router y llama a la tool adecuada."""
    intent = intent or ""
    intent = intent.strip()

    if intent == "estado_fn":
        esquema = params.get("esquema")
        forma_normal = params.get("forma_normal")
        if not esquema:
            return {"ok": False, "error": "Debes indicar un esquema para consultar su estado de FN."}
        data = tool_estado_fn(esquema=esquema, forma_normal=forma_normal)
        data["intent"] = intent
        return data

    if intent == "requisitos_fn":
        forma_normal = params.get("forma_normal")
        esquema = params.get("esquema")
        if not forma_normal:
            return {"ok": False, "error": "Debes indicar una forma normal (1FN, 2FN, 3FN) para ver sus requisitos."}
        data = tool_requisitos_fn(forma_normal=forma_normal, esquema=esquema)
        data["intent"] = intent
        return data

    # Intent desconocido
    return {
        "ok": False,
        "error": f"Intent no soportado: {intent}",
    }
