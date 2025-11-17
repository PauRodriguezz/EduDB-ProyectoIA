# app/app.py — FastAPI + UI para EduDB (chat + evaluación guiada)
import os
from typing import Any, Dict
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

from app.llm_service import route_query
from app.agent import dispatch, crear_esquema_guiado_y_evaluar

app = FastAPI(title="Asistente EduDB · Formas Normales")

INDEX_HTML = """
<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8" />
  <title>Asistente EduDB · Formas Normales</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="min-h-screen bg-slate-100">
  <div class="max-w-5xl mx-auto py-10 px-4 space-y-8">
      <div class="container mx-auto max-w-4xl bg-white p-6 rounded-xl shadow-lg">

        <!-- ENCABEZADO -->
        <div class="w-full py-6 mb-6 text-center" style="background-color: #f0f4ff;">
          <h1 class="text-2xl font-bold text-gray-800 mb-2">
            Asistente EduDB · Formas Normales
          </h1>
          <div class="flex justify-center mt-2">
            <img 
              src="https://cdn-icons-png.flaticon.com/512/6008/6008363.png"
              alt="robot"
              class="w-24 h-24"
            />
          </div>
        </div>
    <!-- ======================================== -->
    <!-- Sección Funcionamiento con ícono         -->
    <!-- ======================================== -->
    <div class="mt-6 mb-4 flex items-start space-x-3">

      <!-- Icono -->
      <img 
        src="https://cdn-icons-png.flaticon.com/128/1076/1076337.png" 
        alt="info"
        class="w-6 h-6 mt-1"
      />

      <!-- Texto -->
      <div>
        <h3 class="text-lg font-semibold text-slate-700">
          Funcionamiento:
        </h3>

        <p class="mt-1 text-slate-600 text-sm max-w-2xl leading-relaxed">
          Tenés dos modos:
          <span class="font-semibold">Chat</span> para hacer preguntas libres sobre formas normales en general o sobre esquemas ya creados,
          y <span class="font-semibold">Evaluación guiada</span> para cargar un esquema nuevo y que el sistema lo evalúe.
        </p>
      </div>
    </div>


    <div class="space-y-6">
    <!-- Panel de Chat -->
    <main class="bg-white rounded-xl shadow p-4 md:p-6 space-y-4 border border-slate-300">
        <h2 class="text-lg font-semibold text-slate-900">Chat sobre formas normales</h2>
        <p class="text-xs text-slate-600">
          Ejemplos:
          <span class="block">
            – ¿El esquema <strong>Pedido</strong> cumple 2FN?
          </span>
          <span class="block">
            – ¿En qué forma normal está el esquema <strong>Pedido</strong>?
          </span>
          <span class="block">
            – ¿Qué se requiere para cumplir 3FN?
          </span>
        </p>
        <form id="query-form" class="flex flex-col gap-3">
          <label class="text-sm font-medium text-slate-700" for="query">
            Consulta
          </label>
          <textarea
            id="query"
            name="query"
            rows="3"
            class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
            placeholder="Ej: ¿El esquema Pedido cumple 2FN?"
            required
          ></textarea>
          <div class="flex items-center gap-3 mt-2">
            <button
              id="submit-btn"
              type="submit"
              class="inline-flex items-center justify-center rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-60 disabled:cursor-not-allowed"
            >
              Consultar
            </button>
            <span id="status" class="text-xs text-slate-500"></span>
          </div>
        </form>

        <section id="output" class="mt-4 space-y-3"></section>
      </main>

       <!-- Panel Evaluación guiada -->
      <section class="bg-white rounded-xl shadow p-4 md:p-6 space-y-4 border border-slate-300">
        <h2 class="text-lg font-semibold text-slate-900">Evaluación guiada de un esquema</h2>
        <p class="text-xs text-slate-600">
          Ingresá el esquema y respondé algunas preguntas sencillas.
          El sistema creará la instancia en Neo4j respetando el metamodelo y evaluará 1FN / 2FN / 3FN.
        </p>

        <form id="guided-form" class="flex flex-col gap-3">
          <div>
            <label for="g-esquema" class="text-sm font-medium text-slate-700">
              Nombre del esquema
            </label>
            <input
              id="g-esquema"
              name="g-esquema"
              type="text"
              class="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
              placeholder="Ej: Pedido2"
              required
            />
          </div>

          <div>
            <label for="g-atributos" class="text-sm font-medium text-slate-700">
              Atributos (uno por línea, marcá las PK con <span class="font-mono">(pk)</span>)
            </label>
            <textarea
              id="g-atributos"
              name="g-atributos"
              rows="4"
              class="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
              placeholder="Ej:
IDProducto (pk)
IDPedido (pk)
NombreProducto
Cantidad"
              required
            ></textarea>
            <p class="mt-1 text-[11px] text-slate-500">
              Ejemplo: <span class="font-mono">IDProducto (pk)</span>, <span class="font-mono">IDPedido (pk)</span>, etc.
            </p>
          </div>

          <div class="border-t border-slate-200 pt-4 space-y-4">
            <p class="text-sm font-semibold text-slate-800">Preguntas sobre dependencias</p>

            <!-- Bloque 1: Dependencias parciales -->
            <div class="p-3 rounded-lg border border-slate-200 bg-slate-50 space-y-2">
              <p class="text-xs text-slate-700">
                1) Si tu clave principal está formada por MÁS de una columna (PK compuesta):<br />
                ¿existe alguna columna NO clave que dependa solo de una parte de la PK,
                y no de toda la combinación?
              </p>
              <div class="flex flex-col gap-1 text-xs mt-1">
                <label class="inline-flex items-center gap-1">
                  <input type="radio" name="g-parciales" value="no" checked />
                  <span>No, todas necesitan toda la PK</span>
                </label>
                <label class="inline-flex items-center gap-1">
                  <input type="radio" name="g-parciales" value="si" />
                  <span>Sí, hay casos así</span>
                </label>
              </div>
              <input
                id="g-parciales-cant"
                type="number"
                min="0"
                class="mt-2 w-full rounded-lg border border-slate-200 px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500"
                placeholder="¿Cuántas dependencias parciales (aprox.)? (opcional)"
              />
            </div>

            <!-- Bloque 2: Dependencias transitivas -->
            <div class="p-3 rounded-lg border border-slate-200 bg-slate-50 space-y-2">
              <p class="text-xs text-slate-700">
                2) ¿Hay columnas NO clave que se puedan calcular a partir de OTRA columna NO clave
                (por ejemplo, <span class="font-mono">NombreProvincia</span> a partir de <span class="font-mono">CodigoProvincia</span>)?
              </p>
              <div class="flex flex-col gap-1 text-xs mt-1">
                <label class="inline-flex items-center gap-1">
                  <input type="radio" name="g-transitivas" value="no" checked />
                  <span>No, las columnas no clave dependen solo de la clave</span>
                </label>
                <label class="inline-flex items-center gap-1">
                  <input type="radio" name="g-transitivas" value="si" />
                  <span>Sí, hay relaciones así</span>
                </label>
              </div>
              <input
                id="g-transitivas-cant"
                type="number"
                min="0"
                class="mt-2 w-full rounded-lg border border-slate-200 px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500"
                placeholder="¿Cuántas dependencias transitivas (aprox.)? (opcional)"
              />
            </div>
          </div>

          <div class="flex items-center gap-3 mt-2">
            <button
              id="g-submit-btn"
              type="submit"
              class="inline-flex items-center justify-center rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-60 disabled:cursor-not-allowed"
            >
              Crear esquema y evaluar
            </button>
            <span id="g-status" class="text-xs text-slate-500"></span>
          </div>
        </form>

        <section id="guided-output" class="mt-3 space-y-3"></section>
      </section>
    </div>
  </div>

  <script>
    // Utilidad para tarjetas
    function card(inner) {
      return `
        <div class="border border-slate-200 rounded-lg p-3 bg-slate-50 text-sm text-slate-800">
          ${inner}
        </div>
      `;
    }

    // =======================
    // Lado Chat
    // =======================
    const form = document.getElementById('query-form');
    const textarea = document.getElementById('query');
    const btn = document.getElementById('submit-btn');
    const out = document.getElementById('output');
    const statusEl = document.getElementById('status');

    function renderEstadoFN(data) {
      if (!data.ok) {
        out.innerHTML = card(`<div class="text-red-600">Error: ${data.error ?? 'Consulta inválida.'}</div>`);
        return;
      }

      if (data.forma_normal && data.estado) {
        const esquema = data.esquema ?? '-';
        const fn = data.forma_normal ?? '-';
        const estado = data.estado ?? 'SIN_EVALUAR';

        let detallesHtml = '';
        if (data.datos_cumple) {
          detallesHtml += `<p class="mt-1 text-xs text-emerald-700">Detalles CUMPLE: <code>${JSON.stringify(data.datos_cumple)}</code></p>`;
        }
        if (data.datos_no_cumple) {
          detallesHtml += `<p class="mt-1 text-xs text-red-700">Detalles NO_CUMPLE: <code>${JSON.stringify(data.datos_no_cumple)}</code></p>`;
        }

        out.innerHTML = card(`
          <div>
            <p><span class="font-semibold">Esquema:</span> ${esquema}</p>
            <p><span class="font-semibold">Forma normal:</span> ${fn}</p>
            <p class="mt-1">
              <span class="font-semibold">Estado:</span>
              <span class="${
                estado === 'CUMPLE'
                  ? 'text-emerald-700'
                  : estado === 'NO_CUMPLE'
                  ? 'text-red-700'
                  : 'text-slate-700'
              }">${estado}</span>
            </p>
            ${detallesHtml}
          </div>
        `);
        return;
      }

      if (Array.isArray(data.resultados)) {
        if (data.resultados.length === 0) {
          out.innerHTML = card(`<div class="text-slate-600">No hay evaluaciones registradas para este esquema.</div>`);
          return;
        }

        const rowsHtml = data.resultados.map(r => {
          const fn = r.forma_normal ?? '-';
          const estado = r.estado ?? 'SIN_EVALUAR';
          const detalles = r.detalles ? `<code class="text-xs">${JSON.stringify(r.detalles)}</code>` : '';

          let estadoClass = 'text-slate-700';
          if (estado === 'CUMPLE') estadoClass = 'text-emerald-700';
          if (estado === 'NO_CUMPLE') estadoClass = 'text-red-700';

          return `
            <div class="border border-slate-200 rounded-md px-3 py-2 bg-white">
              <p><span class="font-semibold">Forma normal:</span> ${fn}</p>
              <p class="mt-1"><span class="font-semibold">Estado:</span> <span class="${estadoClass}">${estado}</span></p>
              ${detalles ? `<p class="mt-1">${detalles}</p>` : ''}
            </div>
          `;
        }).join('');

        out.innerHTML = card(`
          <div>
            <p class="mb-2">
              <span class="font-semibold">Esquema:</span> ${data.esquema ?? '-'}
            </p>
            <div class="space-y-2">${rowsHtml}</div>
          </div>
        `);
        return;
      }

      out.innerHTML = card(`<div class="text-slate-600">No se encontró información de formas normales para este esquema.</div>`);
    }

    function renderRequisitosFN(data) {
      if (!data.ok) {
        out.innerHTML = card(`<div class="text-red-600">Error: ${data.error ?? 'Consulta inválida.'}</div>`);
        return;
      }

      const fn = data.forma_normal ?? '-';
      const esquema = data.esquema ?? null;
      const requisitos = data.requisitos ?? '';
      const estado = data.estado_actual ?? null;
      const problemas = data.problemas_detectados ?? null;

      let html = `
        <p><span class="font-semibold">Forma normal:</span> ${fn}</p>
        <p class="mt-2 text-slate-700">${requisitos}</p>
      `;

      if (esquema) {
        html += `
          <hr class="my-3 border-slate-200" />
          <p class="font-semibold">Aplicado al esquema: ${esquema}</p>
        `;
        if (estado) {
          const est = estado.estado ?? 'SIN_EVALUAR';
          let estadoClass = 'text-slate-700';
          if (est === 'CUMPLE') estadoClass = 'text-emerald-700';
          if (est === 'NO_CUMPLE') estadoClass = 'text-red-700';
          html += `
            <p class="mt-1">
              <span class="font-semibold">Estado actual:</span>
              <span class="${estadoClass}">${est}</span>
            </p>
          `;
        }
        if (Array.isArray(problemas) && problemas.length > 0) {
          const items = problemas.map(p => `<li>${p}</li>`).join('');
          html += `
            <p class="mt-2 text-sm font-semibold text-slate-700">Problemas detectados:</p>
            <ul class="mt-1 text-sm text-slate-700 list-disc list-inside">${items}</ul>
          `;
        }
      }

      out.innerHTML = card(html);
    }

    function renderDesconocido(data) {
      out.innerHTML = card(`
        <div class="text-slate-700">
          <p>No pude clasificar tu consulta en un tipo soportado.</p>
          <p class="mt-1 text-xs text-slate-500">
            Probá algo como: "¿El esquema Pedido cumple 2FN?" o "¿Qué se requiere para cumplir 3FN?".
          </p>
        </div>
      `);
    }

    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const text = textarea.value.trim();
      if (!text) return;

      btn.disabled = true;
      statusEl.textContent = "Consultando...";
      out.innerHTML = "";

      try {
        const res = await fetch("/api/query", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ query: text })
        });

        const data = await res.json();

        if (!res.ok) {
          out.innerHTML = card(`<div class="text-red-600">Error: ${data.error ?? 'Ocurrió un error en el servidor.'}</div>`);
          return;
        }

        const intent = data.intent ?? "desconocido";

        if (intent === "estado_fn") {
          renderEstadoFN(data);
        } else if (intent === "requisitos_fn") {
          renderRequisitosFN(data);
        } else {
          renderDesconocido(data);
        }
      } catch (err) {
        out.innerHTML = card(`<div class="text-red-600">Error de red o servidor.</div>`);
      } finally {
        btn.disabled = false;
        statusEl.textContent = "";
      }
    });

    // =======================
    // Lado Evaluación guiada
    // =======================
    const gForm = document.getElementById('guided-form');
    const gEsquema = document.getElementById('g-esquema');
    const gAtributos = document.getElementById('g-atributos');
    const gParcialesCant = document.getElementById('g-parciales-cant');
    const gTransitivasCant = document.getElementById('g-transitivas-cant');
    const gBtn = document.getElementById('g-submit-btn');
    const gStatus = document.getElementById('g-status');
    const gOut = document.getElementById('guided-output');

    function getRadioValue(name) {
      const els = document.querySelectorAll(`input[name="${name}"]`);
      for (const el of els) {
        if (el.checked) return el.value;
      }
      return null;
    }

    function parseAtributos(text) {
      const lines = text.split(/\\r?\\n/);
      const attrs = [];
      for (let line of lines) {
        line = line.trim();
        if (!line) continue;
        const isPk = line.toLowerCase().includes("(pk");
        let nombre = line.replace(/\\(pk\\)/ig, "").trim();
        if (!nombre) continue;
        attrs.push({ nombre, es_pk: isPk });
      }
      return attrs;
    }

    function renderGuiadoResultado(data) {
      if (!data.ok) {
        gOut.innerHTML = card(`<div class="text-red-600">Error: ${data.error ?? 'Error al evaluar el esquema.'}</div>`);
        return;
      }

      const esquema = data.esquema ?? '-';
      const resumen = data.evaluacion_resumen ?? null;
      const estadoDet = data.estado_detallado ?? null;

      let html = `
        <p><span class="font-semibold">Esquema creado:</span> ${esquema}</p>
      `;

      if (resumen) {
        const c1 = resumen.cumple_1fn ? "CUMPLE" : "NO CUMPLE";
        const c2 = resumen.cumple_2fn ? "CUMPLE" : "NO CUMPLE";
        const c3 = resumen.cumple_3fn ? "CUMPLE" : "NO CUMPLE";
        html += `
          <div class="mt-2 text-sm">
            <p><span class="font-semibold">1FN:</span> ${c1}</p>
            <p><span class="font-semibold">2FN:</span> ${c2}</p>
            <p><span class="font-semibold">3FN:</span> ${c3}</p>
          </div>
        `;
      }

      if (estadoDet && estadoDet.ok && Array.isArray(estadoDet.resultados)) {
        const rows = estadoDet.resultados.map(r => {
          const fn = r.forma_normal ?? '-';
          const est = r.estado ?? 'SIN_EVALUAR';
          const detalles = r.detalles ? `<code class="text-[11px]">${JSON.stringify(r.detalles)}</code>` : '';
          let estClass = 'text-slate-700';
          if (est === 'CUMPLE') estClass = 'text-emerald-700';
          if (est === 'NO_CUMPLE') estClass = 'text-red-700';
          return `
            <div class="border border-slate-200 rounded-md px-3 py-2 bg-white">
              <p><span class="font-semibold">Forma normal:</span> ${fn}</p>
              <p class="mt-1"><span class="font-semibold">Estado:</span> <span class="${estClass}">${est}</span></p>
              ${detalles ? `<p class="mt-1">${detalles}</p>` : ''}
            </div>
          `;
        }).join('');

        html += `
          <hr class="my-3 border-slate-200" />
          <p class="text-sm font-semibold text-slate-800">Detalle en Neo4j (CUMPLE / NO_CUMPLE):</p>
          <div class="mt-2 space-y-2">${rows}</div>
        `;
      }

      gOut.innerHTML = card(html);
    }

    gForm.addEventListener('submit', async (e) => {
      e.preventDefault();

      const nombre = gEsquema.value.trim();
      const attrsText = gAtributos.value.trim();
      if (!nombre || !attrsText) return;

      const atributos = parseAtributos(attrsText);
      if (!atributos.length) {
        gOut.innerHTML = card('<div class="text-red-600 text-sm">Debes ingresar al menos un atributo válido.</div>');
        return;
      }

      // Multivaluados: lo tomamos siempre como NO por defecto
      const tieneMultival = false;
      const multivalList = "";

      // PK compuesta: la deducimos a partir de cuántos atributos están marcados como PK
      const pkComp = atributos.filter(a => a.es_pk).length > 1;

      // Preguntas 1 y 2 (parciales y transitivas)
      const parcVal = getRadioValue("g-parciales");
      const tieneParciales = parcVal === "si";
      const parcCant = gParcialesCant.value;

      const transVal = getRadioValue("g-transitivas");
      const tieneTransitivas = transVal === "si";
      const transCant = gTransitivasCant.value;

      const payload = {
        nombre_esquema: nombre,
        atributos: atributos,
        tiene_multivaluados: tieneMultival,
        atributos_multivaluados: multivalList,
        pk_es_compuesta: pkComp,
        tiene_parciales: tieneParciales,
        cant_df_parciales: parcCant || null,
        tiene_transitivas: tieneTransitivas,
        cant_df_transitivas: transCant || null
      };

      gBtn.disabled = true;
      gStatus.textContent = "Creando esquema y evaluando...";
      gOut.innerHTML = "";

      try {
        const res = await fetch("/api/guiado/evaluar-esquema", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });

        const data = await res.json();

        if (!res.ok) {
          gOut.innerHTML = card(`<div class="text-red-600">Error: ${data.error ?? 'Error en el servidor.'}</div>`);
          return;
        }

        renderGuiadoResultado(data);
      } catch (err) {
        gOut.innerHTML = card(`<div class="text-red-600">Error de red o servidor.</div>`);
      } finally {
        gBtn.disabled = false;
        gStatus.textContent = "";
      }
    });

  </script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return HTMLResponse(INDEX_HTML)


@app.post("/api/query")
async def api_query(payload: Dict[str, Any]) -> JSONResponse:
    text = payload.get("query")
    if not text or not isinstance(text, str):
        return JSONResponse({"error": "Falta 'query'."}, status_code=400)

    routed = route_query(text)
    intent = routed.get("intent")
    params = routed.get("params", {})

    result = dispatch(intent, params)
    result["intent"] = intent
    return JSONResponse(result)

@app.post("/api/guiado/evaluar-esquema")
async def api_guiado_evaluar(payload: Dict[str, Any]) -> JSONResponse:
    """
    Endpoint para el flujo guiado: crea un esquema + evaluación
    a partir de un cuestionario, y devuelve un resumen.
    """
    result = crear_esquema_guiado_y_evaluar(payload)
    status = 200 if result.get("ok") else 400
    return JSONResponse(result, status_code=status)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=int(os.getenv("PORT", "8000")))
