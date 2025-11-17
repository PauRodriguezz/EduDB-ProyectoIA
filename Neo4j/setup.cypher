// =======================================
// PASO 1 — CONSTRAINTS (esquema base)
// =======================================
CREATE CONSTRAINT frameclass_name IF NOT EXISTS
FOR (c:FrameClass) REQUIRE c.name IS UNIQUE;

CREATE CONSTRAINT slot_name_per_frame IF NOT EXISTS
FOR (s:Slot) REQUIRE (s.name, s.frame) IS UNIQUE;

CREATE CONSTRAINT daemon_name IF NOT EXISTS
FOR (d:Daemon) REQUIRE d.name IS UNIQUE;

// =======================================
// PASO 2 — METAMODELO (sin APOC)
// =======================================
// ---- FrameClass ----
UNWIND [
  'EVALUAR_FORMA_NORMAL',
  '1FN','2FN','3FN',
  'CRITERIO_1FN','CRITERIO_2FN','CRITERIO_3FN',
  'ESQUEMA','ATRIBUTO','DEPENDENCIA_FUNCIONAL'
] AS fc
MERGE (:FrameClass {name: fc});

// ---- Relaciones entre Frames ----
MATCH (fn1:FrameClass {name:'1FN'}),(fn2:FrameClass {name:'2FN'}),(fn3:FrameClass {name:'3FN'}),
      (c1:FrameClass {name:'CRITERIO_1FN'}),(c2:FrameClass {name:'CRITERIO_2FN'}),(c3:FrameClass {name:'CRITERIO_3FN'})
MERGE (fn1)-[:REQUIERE]->(c1)
MERGE (fn2)-[:REQUIERE]->(c2)
MERGE (fn3)-[:REQUIERE]->(c3)
MERGE (fn2)-[:DEPENDE_DE]->(fn1)
MERGE (fn3)-[:DEPENDE_DE]->(fn2);

MATCH (eval:FrameClass {name:'EVALUAR_FORMA_NORMAL'}),
      (esq:FrameClass {name:'ESQUEMA'})
MERGE (eval)-[:EVALUA]->(esq);

// ---- Slots ----
UNWIND [
  // EVALUAR_FORMA_NORMAL
  {frame:'EVALUAR_FORMA_NORMAL', name:'forma_normal', tipo:'enum(1FN,2FN,3FN)', es_lista:false},

  // CRITERIOS
  {frame:'CRITERIO_1FN', name:'sin_atributos_multivaluados', tipo:'boolean', es_lista:false},
  {frame:'CRITERIO_1FN', name:'atributos_multivaluados', tipo:'string', es_lista:true},

  {frame:'CRITERIO_2FN', name:'pk_compuesta', tipo:'boolean', es_lista:false},
  {frame:'CRITERIO_2FN', name:'sin_dependencias_parciales', tipo:'boolean', es_lista:false},
  {frame:'CRITERIO_2FN', name:'dependencias_parciales', tipo:'ref(DF)', es_lista:true},

  {frame:'CRITERIO_3FN', name:'sin_dependencias_transitivas', tipo:'boolean', es_lista:false},
  {frame:'CRITERIO_3FN', name:'dependencias_transitivas', tipo:'ref(DF)', es_lista:true},

  // Dominio básico
  {frame:'ESQUEMA', name:'name', tipo:'string', es_lista:false},
  {frame:'ATRIBUTO', name:'name', tipo:'string', es_lista:false},
  {frame:'ATRIBUTO', name:'es_pk', tipo:'boolean', es_lista:false},
  {frame:'DEPENDENCIA_FUNCIONAL', name:'tipo', tipo:'enum(Plena,Parcial,Transitiva)', es_lista:false}
] AS s
MERGE (sl:Slot {name:s.name})
SET sl.frame = s.frame, sl.tipo = s.tipo, sl.es_lista = s.es_lista;

// ---- Daemons ----
UNWIND [
  {name:'if-needed_1FN', trigger:'if-needed', target:'1FN'},
  {name:'if-needed_2FN', trigger:'if-needed', target:'2FN'},
  {name:'if-needed_3FN', trigger:'if-needed', target:'3FN'},
  {name:'if-added_DF_classifier', trigger:'if-added', target:'DEPENDENCIA_FUNCIONAL'}
] AS d
MERGE (dm:Daemon {name:d.name})
SET dm.trigger = d.trigger, dm.target = d.target;

// ---- Enlaces Frame ↔ Daemon ----
MATCH (fn1:FrameClass {name:'1FN'}),(fn2:FrameClass {name:'2FN'}),(fn3:FrameClass {name:'3FN'}),
      (df:FrameClass {name:'DEPENDENCIA_FUNCIONAL'}),
      (d1:Daemon {name:'if-needed_1FN'}),(d2:Daemon {name:'if-needed_2FN'}),(d3:Daemon {name:'if-needed_3FN'}),
      (dc:Daemon {name:'if-added_DF_classifier'})
MERGE (fn1)-[:TRIGGERS]->(d1)
MERGE (fn2)-[:TRIGGERS]->(d2)
MERGE (fn3)-[:TRIGGERS]->(d3)
MERGE (df)-[:TRIGGERS]->(dc);

// ---- Conexiones generales ----
MATCH (f:FrameClass),(s:Slot)
WHERE s.frame = f.name
MERGE (f)-[:HAS_SLOT]->(s);

MATCH (f:FrameClass)-[:TRIGGERS]->(d:Daemon)
MERGE (f)-[:HAS_DAEMON]->(d);

// ---- Parche de relaciones del metamodelo (clase ↔ clase) ----
// ESQUEMA con ATRIBUTO y DEPENDENCIA_FUNCIONAL
MATCH (es:FrameClass {name:'ESQUEMA'}),
      (at:FrameClass {name:'ATRIBUTO'}),
      (df:FrameClass {name:'DEPENDENCIA_FUNCIONAL'})
MERGE (es)-[:TIENE]->(at)
MERGE (es)-[:DEFINE]->(df)
MERGE (df)-[:DESDE]->(at)
MERGE (df)-[:HASTA]->(at);

// EVALUAR_FORMA_NORMAL determina el tipo de FN (1FN/2FN/3FN)
MATCH (eval:FrameClass {name:'EVALUAR_FORMA_NORMAL'}),
      (fn1:FrameClass {name:'1FN'}),
      (fn2:FrameClass {name:'2FN'}),
      (fn3:FrameClass {name:'3FN'})
MERGE (eval)-[:DETERMINA]->(fn1)
MERGE (eval)-[:DETERMINA]->(fn2)
MERGE (eval)-[:DETERMINA]->(fn3);

// ============================
// PASO 3 — INSTANCIACIÓN 
// ============================

// --- 1) Esquema + INSTANCE_OF
MERGE (es:Esquema {name:'Pedido'})
WITH es
MATCH (fc_es:FrameClass {name:'ESQUEMA'})
MERGE (es)-[:INSTANCE_OF]->(fc_es);

// --- 2) Atributos + enlaces TIENE + INSTANCE_OF
UNWIND [
  {name:'IDProducto',      es_pk:true},
  {name:'IDPedido',        es_pk:true},
  {name:'NroPedido',       es_pk:false},
  {name:'NombreProducto',  es_pk:false},
  {name:'Cantidad',        es_pk:false}
] AS a
MERGE (att:Atributo {name:a.name, esquema:'Pedido'})
SET   att.es_pk = a.es_pk
MERGE (es)-[:TIENE]->(att)
WITH att
MATCH (fc_at:FrameClass {name:'ATRIBUTO'})
MERGE (att)-[:INSTANCE_OF]->(fc_at);

// (Refuerzo idempotente: asegurar que TODOS los atributos del esquema estén enlazados por TIENE)
MATCH (es2:Esquema {name:'Pedido'})
MATCH (a2:Atributo {esquema:'Pedido'})
MERGE (es2)-[:TIENE]->(a2);

// --- 3) Dependencias Funcionales (DF como RELACIÓN entre atributos del mismo esquema)
MATCH (idProd:Atributo {name:'IDProducto',     esquema:'Pedido'}),
      (idPed :Atributo {name:'IDPedido',       esquema:'Pedido'}),
      (nro   :Atributo {name:'NroPedido',      esquema:'Pedido'}),
      (nom   :Atributo {name:'NombreProducto', esquema:'Pedido'}),
      (cant  :Atributo {name:'Cantidad',       esquema:'Pedido'})

// (IDProducto, IDPedido) → Cantidad  (Plena)  → representado con dos arcos
MERGE (idProd)-[:DF {tipo:'Plena'}]->(cant)
MERGE (idPed) -[:DF {tipo:'Plena'}]->(cant)

// IDProducto → NombreProducto  (Parcial)
MERGE (idProd)-[:DF {tipo:'Parcial'}]->(nom)

// IDPedido → NroPedido  (Parcial)
MERGE (idPed)-[:DF {tipo:'Parcial'}]->(nro);

// --- 4) Instancia de evaluación (con slot forma_normal y el enlace EVALUA)
MERGE (ev:EVALUAR_FORMA_NORMAL {id:'EV_Pedido_2FN'})
SET   ev.forma_normal = '2FN',
      ev.esquema_objetivo = 'Pedido'
WITH ev
MATCH (es:Esquema {name: ev.esquema_objetivo})
MERGE (ev)-[:EVALUA]->(es)

// Tipado de la instancia de evaluación
WITH ev
MATCH (fc_eval:FrameClass {name:'EVALUAR_FORMA_NORMAL'})
MERGE (ev)-[:INSTANCE_OF]->(fc_eval);

// ============================
// PASO 4 — Consultas para caso 1
// ============================
// Parte 1
// Setea hechos en la evaluación indicada por id (ajustá $evId si usaste otro)
WITH 'EV_Pedido_2FN' AS evId
MATCH (ev:EVALUAR_FORMA_NORMAL {id:evId})
MATCH (es:Esquema {name: ev.esquema_objetivo})

// pk_compuesta + multivaluados (si usás a.multivaluado=true en algún dato)
MATCH (a:Atributo {esquema: es.name})
WITH ev, es, collect(a) AS attrs
WITH ev, es,
reduce(k=0, x IN attrs | k + CASE WHEN coalesce(x.es_pk,false) THEN 1 ELSE 0 END) AS cant_pk,
[x IN attrs WHERE coalesce(x.multivaluado,false)=true | x.name] AS multival

// conteo DF parciales y transitivas del mismo esquema
MATCH (:Atributo {esquema: es.name})-[df:DF]->(:Atributo {esquema: es.name})
WITH ev, es, cant_pk, multival,
sum(CASE WHEN df.tipo='Parcial' THEN 1 ELSE 0 END) AS n_parciales,
sum(CASE WHEN df.tipo='Transitiva' THEN 1 ELSE 0 END) AS n_transitivas
SET ev.pk_compuesta = cant_pk > 1,
ev.sin_atributos_multivaluados = size(multival)=0,
ev.atributos_multivaluados = multival,
ev.cant_df_parciales = n_parciales,
ev.cant_df_transitivas = n_transitivas;

// parte 2
// Evaluar 1FN/2FN/3FN y crear CUMPLE / NO_CUMPLE (Neo4j 5.x)
WITH 'EV_Pedido_2FN' AS evId
MATCH (ev:EVALUAR_FORMA_NORMAL {id:evId})
MATCH (es:Esquema {name: ev.esquema_objetivo})
MATCH (fn1:FrameClass {name:'1FN'}),(fn2:FrameClass {name:'2FN'}),(fn3:FrameClass {name:'3FN'})

// limpiar resultados anteriores
OPTIONAL MATCH (es)-[old:CUMPLE|NO_CUMPLE]->(f:FrameClass)
WHERE f.name IN ['1FN','2FN','3FN']
DELETE old

// flags de cumplimiento
WITH ev, es, fn1, fn2, fn3,
(ev.sin_atributos_multivaluados) AS ok1,
(ev.sin_atributos_multivaluados AND ev.pk_compuesta AND ev.cant_df_parciales=0) AS ok2,
(ev.sin_atributos_multivaluados AND ev.pk_compuesta AND ev.cant_df_parciales=0 AND ev.cant_df_transitivas=0) AS ok3

// ----- 1FN -----
FOREACH (_ IN CASE WHEN ok1 THEN [1] ELSE [] END |
MERGE (es)-[r1:CUMPLE]->(fn1)
SET r1.multival = 0,
r1.pk_compuesta = ev.pk_compuesta,
r1.parciales = ev.cant_df_parciales,
r1.transitivas = ev.cant_df_transitivas
)
FOREACH (_ IN CASE WHEN NOT ok1 THEN [1] ELSE [] END |
MERGE (es)-[r1:NO_CUMPLE]->(fn1)
SET r1.motivo = 'Atributos multivaluados',
r1.atributos = coalesce(ev.atributos_multivaluados, [])
)

// ----- 2FN (requiere 1FN) -----
WITH ev, es, fn1, fn2, fn3, ok1, ok2, ok3,
[x IN [
CASE WHEN NOT ev.sin_atributos_multivaluados THEN 'No cumple 1FN' END,
CASE WHEN NOT ev.pk_compuesta THEN 'PK no compuesta' END,
CASE WHEN ev.cant_df_parciales>0 THEN 'Tiene dependencias parciales' END
] WHERE x IS NOT NULL] AS motivos2

FOREACH (_ IN CASE WHEN ok2 THEN [1] ELSE [] END |
MERGE (es)-[r2:CUMPLE]->(fn2)
SET r2.pk_compuesta = true,
r2.parciales = 0
)
FOREACH (_ IN CASE WHEN NOT ok2 THEN [1] ELSE [] END |
MERGE (es)-[r2:NO_CUMPLE]->(fn2)
SET r2.motivos = motivos2,
r2.parciales = ev.cant_df_parciales
);