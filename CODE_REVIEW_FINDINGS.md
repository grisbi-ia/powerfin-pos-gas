# CODE_REVIEW_FINDINGS.md — Revisión de código por módulo (2026-08-04)

Revisión generada con 4 subagentes en paralelo (uno por módulo: `pos_backend`,
`fusion-bridge`, `pos/`, `admin/`), buscando bugs, deuda técnica, condiciones
de carrera y violaciones a las reglas de `AGENTS.md` (no silent fallbacks,
no business logic en componentes Svelte, paginación obligatoria en admin, etc).

Marcar `[x]` a medida que se revisa/resuelve cada punto. Añadir nota debajo
de cada ítem con la decisión tomada (fix / descartado / diferido + por qué).

---

## 🔴 Alta prioridad

- [ ] **1. `fusion-bridge` — posible doble conexión TCP concurrente**
  `FusionTcpClient.java:65-68,146-152`
  Ante un error de socket, `exceptionHandler` y `closeHandler` disparan cada
  uno `onDisconnected()` por separado, agendando dos `reconnectWithBackoff()`
  independientes (`vertx.setTimer`). Pueden abrirse **dos conexiones TCP
  simultáneas** a la Synergy, cada una reenviando `sendSubscriptions()` /
  `REQ_PUMP_STATUS` — viola la regla de "conexión única" y puede causar
  eventos `EVT_PUMP_NEW_TRANSACTION` duplicados (doble `completeDispatch`,
  doble impresión). Candidato a explicar incidentes tipo MINERA PIRINCAY.
  Falta guarda `if (reconnecting) return;` o desregistrar handlers antes de
  cerrar el socket.

- [ ] **2. `pos_backend` — secuencial fiscal se pierde en silencio**
  `app/api/dispatches.py:184-188`
  Si `consume_sequential` falla, el despacho se crea sin secuencial y el
  error se traga con `except Exception: pass`. Mismo patrón que causó los
  "53 secuenciales quemados" documentados en `NEXT_SESSION.md`.

- [ ] **3. `pos_backend` — facturación SRI en background sin logging de errores**
  `app/api/dispatches.py:64-67`
  `_key49_background` traga cualquier excepción sin loggear nada. Si
  `emitir_factura` falla por un bug real (no solo timeout SRI), el despacho
  queda `sri_status=PENDING` para siempre, sin rastro para auditar.

- [ ] **4. `pos_backend` — token/credenciales hardcodeadas**
  `app/services/identity_service.py:9-10`
  URL del servicio de identidad y JWT Bearer token completo (Sercobaco/SRI)
  en texto plano en el código fuente, persistente en el historial de git.
  Ya pendiente "mover a system_config" en `NEXT_SESSION.md` — rotar el
  token también, no solo moverlo.

- [ ] **5. `pos_backend` — lógica de rollback/reactivación duplicada**
  `app/api/dispatches.py:381-499` (`complete_dispatch`) vs. `502-625`
  (`complete_dispatch_by_pump`)
  El parche de reactivación CANCELLED→COMPLETED y corrección de totales en
  $0 está copiado casi línea por línea en ambos endpoints. Extraer a un
  helper compartido (`_reactivate_or_correct(...)`) para no tener que
  recordar aplicar el mismo fix dos veces.

- [ ] **6. `pos/` — `SaleWizard.svelte` (1186 líneas) con lógica de negocio dentro del componente**
  Viola la regla explícita de AGENTS.md ("NO business logic en componentes
  Svelte — usar `$lib/api/` y stores"). Incluye cálculo de cupos de crédito
  (`checkPublicContract`, 191-230), rollback de dispatch (`handleAuthorize`,
  407-458) y armado de payload de impresión (`doPrint`, 492-565). No
  testeable de forma aislada; no hay tests unitarios de esta lógica.

- [ ] **7. `pos/` — fallos silenciosos en operaciones financieras**
  `checkPublicContract` (229), `saveEditCustomer` (402: `catch { /* silently fail */ }`),
  `applyBillingChange` (621) — todos con catch vacíos o comentarios que
  admiten el silenciamiento. Contradice la regla #6 de AGENTS.md. Escenario
  concreto: si el backend de crédito está caído un instante, el despachador
  cobra en efectivo una venta que debía ser a crédito, sin aviso.

- [ ] **8. `admin/` — sin gating de permisos en la UI + permisividad en backend**
  Frontend: ningún componente usa `isAdmin`/`permissions` fuera de
  `auth.ts` — SUPERVISOR (debería ser solo lectura+export) ve los mismos
  botones de crear/editar/eliminar que ADMIN; el 403 solo aparece al hacer
  clic.
  Backend: `pos_backend/app/api/admin/deps.py:53-54` — `require_permission`
  concede acceso total si `role.permissions_json` está vacío/None. **Acción
  previa recomendada: verificar en la BD real si `permissions_json` está
  poblado** antes de decidir el fix (puede que hoy SUPERVISOR = ADMIN en la
  práctica).

---

## 🟡 Media prioridad

- [ ] **9. `fusion-bridge` — cero tests para el código más crítico**
  `FusionTcpClient`, `FusionEventHandler`, `DispenserStatusCache`,
  `RecoveryService`, `DispatchResource`, `ThermalPrinter` sin cobertura.
  Justo las partes con más historial de bugs reales (race condition del
  despacho fantasma $539.63, PAY_IN perdido).

- [ ] **10. `fusion-bridge` — `payment_method_id=1` hardcodeado**
  `FusionEventHandler.java:183`
  Contradice la lección aprendida documentada en `NEXT_SESSION.md`
  ("payment_method codes cambian entre entornos — no hardcodear"), y hay un
  incidente manual (#6623) causado por `payment_method_id=0`.

- [ ] **11. `pos_backend` — `cancel_dispatch` sin advisory lock**
  `app/api/dispatches.py:1030-1065`
  A diferencia de `create_dispatch` (línea 90), no usa
  `pg_advisory_xact_lock`. Posible TOCTOU si dos requests concurrentes
  cancelan/completan el mismo `order_id`.

- [ ] **12. `pos_backend` — queries N+1-ish en endpoints de polling**
  `get_active_dispatches` (`dispatches.py:1124-1245`, 6 queries batched
  adicionales) y `_build_receipt_data` (826-867, ~8 queries secuenciales en
  el hot path de cobro). Candidato a `selectinload`/`joinedload`.

- [ ] **13. `fusion-bridge` — JSON construido a mano con `String.format`**
  `FusionEventHandler.java:181-186,233-236`
  Riesgo bajo (campos numéricos) pero frágil; usar Jackson en vez de
  concatenación manual.

- [ ] **14. `pos/` — duplicación de armado de ticket**
  `doPrint()` en `SaleWizard.svelte` (492-556): dos formatos de payload
  mantenidos en paralelo (branch DB-persisted vs. branch legacy fallback).
  Riesgo de que diverjan silenciosamente ante un cambio de campo SRI.

- [ ] **15. `pos/` — reactive statement con side-effect**
  `SaleWizard.svelte:131-141` — `$: if (mode === 'collect') {...}` mezcla
  asignación de estado con llamada async dentro de bloque reactivo; se
  re-ejecuta ante cualquier cambio de dependencia rastreada. Mover a
  `onMount`/watcher explícito.

- [ ] **16. `admin/` — `NEXT_SESSION.md` desactualizado (actualizar doc, no código)**
  Los 13 módulos CRUD marcados como pendientes en Fase 12/13 (Roles,
  Products, Grades, Price-lists, Dispensers/hoses, Emission-points,
  company-info, system-config, Payment-methods) **ya están implementados**
  completos, backend y frontend. Actualizar `NEXT_SESSION.md`/`AGENTS.md`
  para no replanificar trabajo ya hecho.

- [ ] **17. `admin/` — listados no filtran por `is_active` por defecto**
  `products.py` y patrón repetido en grades/dispensers/price_lists: no
  excluyen soft-deleted por defecto ni ofrecen parámetro
  `include_inactive`. Puede ser intencional — confirmar y documentar.

---

## 🟢 Baja prioridad

- [ ] **18. `pos_backend` — falta test para `identity_service.py`**
  Única integración con servicio externo (Sercobaco/SRI) fuera de Key49,
  sin cobertura. Parsing con `or` en cascada frágil (`_parse_ced_data`,
  `_parse_ruc_data`).

- [ ] **19. `pos_backend` — try/except externo redundante**
  `dispatches.py:713-718` — envuelve `asyncio.create_task(...)` en
  try/except, pero la falla real ocurre dentro de `_key49_background` (que
  ya tiene su propio catch, ver #3). Código muerto que oculta bugs de
  programación si `create_task` cambia de comportamiento.

- [ ] **20. `fusion-bridge` — `ThermalPrinter` sin retry**
  A diferencia del patrón de 3 reintentos en `completeDispatchOnBackend`,
  un fallo transitorio de red hacia la impresora no reintenta. Confirmar si
  es intencional.

- [ ] **21. `fusion-bridge` — parsing de buffer TCP potencialmente O(n²)**
  `FusionTcpClient.onDataReceived` (125-144) usa `content.substring()`
  repetido dentro del while. Irrelevante al volumen actual, pero evitable
  con índice en vez de recortar el string.

- [ ] **22. `pos/` — cobertura de tests floja**
  ~520 líneas de test vs. ~5582 líneas de código fuente; `SaleWizard.svelte`
  (el componente más crítico) sin tests directos.

- [ ] **23. `pos/` — nomenclatura confusa (`confirmingPayment`)**
  Se usa como estado de modal de confirmación, no como "enviando cobro" — el
  texto del botón nunca coincide con el request real en curso. No es bug
  funcional, pero confunde a quien mantenga el código.

- [ ] **24. `pos/` — mutación directa de objeto anidado sin reasignación**
  `saveEditCustomer` (386-400) muta `billingCustomer.name = ...` en vez de
  reasignar `billingCustomer = {...}`. Funciona hoy por reactividad indirecta,
  pero es frágil ante refactors.

- [ ] **25. `admin/` — endpoints sin paginación (bajo riesgo)**
  `system_config.py` y `company.py` no paginan — contradice la regla
  literal de AGENTS.md, pero son key-value/singleton de tamaño acotado.

- [ ] **26. `admin/` — guard de auth con async IIFE innecesaria**
  `admin/src/routes/(admin)/+layout.svelte:9-14` — `$effect` envuelve una
  IIFE async sin `await` real adentro. Deuda de estilo, sin bug funcional.

---

## Notas generales

- No se hicieron cambios de código en esta revisión — solo diagnóstico.
- Los hallazgos de `pos_backend` #13 (paginación en `app/api/admin/*.py`) no
  se verificaron por límite de alcance del subagente correspondiente — ver
  ítem #25 arriba, que sí lo cubre parcialmente desde el lado de `admin/`.
- Cobertura de tests para los módulos admin nuevos no se ejecutó
  (`pytest` no corrido durante la revisión).
