# main.py — orquestador (terminal)
from app.llm_service import route_query
from app.agent import dispatch


def ejecutar_consulta(texto_usuario: str):
    routed = route_query(texto_usuario)
    print("🧠 INTENT DETECTADO:", routed["intent"])
    print("📦 PARAMS:", routed["params"])
    result = dispatch(routed["intent"], routed["params"])
    print("\n=== RESULTADO ===")
    print(result)
    return result


if __name__ == "__main__":
    print("=== Asistente EduDB · Formas Normales ===")
    print("Ejemplos de consultas:")
    print("- ¿El esquema Pedido cumple 2FN?")
    print("- ¿En qué forma normal está el esquema Pedido?")
    print("- ¿Qué se requiere para cumplir 3FN?")
    print("- ¿Qué le falta al esquema Pedido para estar en 2FN?")
    while True:
        texto = input("\nTu consulta ('salir' para terminar): ")
        if texto.lower().startswith("salir"):
            break
        ejecutar_consulta(texto)
