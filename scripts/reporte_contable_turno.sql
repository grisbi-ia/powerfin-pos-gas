-- ═══════════════════════════════════════════════════════════════
-- reporte_contable_turno.sql
-- Reporte detallado para el contador — todos los despachos del turno.
--
-- Uso:
--   psql -h IP -U usuario -d powerfin_gas -f reporte_contable_turno.sql -v shift_id=28
-- ═══════════════════════════════════════════════════════════════

-- ── Encabezado del turno ─────────────────────────────────────
SELECT
    '═══ TURNO ' || s.shift_id || ' ═══'        AS encabezado,
    s.status                                      AS estado,
    u.name                                        AS cajero,
    to_char(s.opened_at, 'DD/MM/YYYY HH24:MI')   AS apertura,
    to_char(s.closed_at, 'DD/MM/YYYY HH24:MI')   AS cierre,
    s.accounting_date                             AS fecha_contable,
    s.opening_cash                                AS caja_inicial,
    s.surplus                                     AS sobrante,
    s.shortage                                    AS faltante
FROM shifts s
JOIN users u ON u.user_id = s.user_id
WHERE s.shift_id = :shift_id;


-- ── Resumen financiero ───────────────────────────────────────
SELECT
    COUNT(*)                                                             AS total_despachos,
    SUM(CASE WHEN d.status = 'COLLECTED'  THEN 1 ELSE 0 END)            AS cobrados,
    SUM(CASE WHEN d.status = 'COMPLETED' THEN 1 ELSE 0 END)             AS pendientes_cobro,
    SUM(CASE WHEN d.status = 'AUTHORIZED'  THEN 1 ELSE 0 END)           AS autorizados,
    SUM(CASE WHEN d.status = 'CANCELLED' THEN 1 ELSE 0 END)             AS cancelados,
    COALESCE(SUM(d.total), 0)                                           AS total_despachos_usd,
    COALESCE(SUM(CASE WHEN d.status = 'COLLECTED' THEN d.total END),0)  AS total_cobrado_usd,
    COALESCE(SUM(CASE WHEN d.status = 'CANCELLED' AND d.total = 0
                 AND d.preset_value ~ '^[0-9]+(\.[0-9]+)?$'
                 THEN CAST(d.preset_value AS numeric) END),0)           AS presets_cancelados_usd
FROM dispatches d
WHERE d.shift_id = :shift_id;


-- ── Ventas por forma de pago ─────────────────────────────────
SELECT
    pm.name                                      AS forma_pago,
    COUNT(DISTINCT d.dispatch_id)                AS despachos,
    SUM(dp.amount)                               AS total_usd
FROM dispatch_payments dp
JOIN payment_methods pm ON pm.payment_method_id = dp.payment_method_id
JOIN dispatches d       ON d.dispatch_id        = dp.dispatch_id
WHERE d.shift_id = :shift_id AND d.status = 'COLLECTED'
GROUP BY pm.name
ORDER BY total_usd DESC;


-- ── Movimientos de caja ──────────────────────────────────────
SELECT
    cm.type                                       AS tipo,
    cm.amount                                     AS monto,
    cm.observation                                AS observacion,
    cm.running_balance                            AS saldo_caja,
    cm.related_user_name                          AS usuario_relacionado,
    to_char(cm.created_at, 'DD/MM HH24:MI')       AS fecha_hora
FROM cash_movements cm
WHERE cm.shift_id = :shift_id
ORDER BY cm.created_at;


-- ── Despachos con diferencias (alertas) ──────────────────────
SELECT
    d.order_id                                    AS orden,
    d.status                                      AS estado,
    d.total                                       AS total_despacho,
    dd.total                                      AS total_detalle,
    dp.total_pagado                               AS total_cobrado,
    d.total - COALESCE(dd.total, 0)               AS diff_desp_det,
    d.total - COALESCE(dp.total_pagado, 0)        AS diff_desp_pago
FROM dispatches d
LEFT JOIN dispatch_details dd ON dd.dispatch_id = d.dispatch_id
LEFT JOIN LATERAL (
    SELECT SUM(dp2.amount) AS total_pagado
    FROM dispatch_payments dp2 WHERE dp2.dispatch_id = d.dispatch_id
) dp ON true
WHERE d.shift_id = :shift_id
  AND (
       d.total != COALESCE(dd.total, 0)
    OR d.total != COALESCE(dp.total_pagado, 0)
  )
ORDER BY d.created_at;
-- ═══════════════════════════════════════════════════════════════
-- DETALLE COMPLETO — Solo despachos oficiales (COLLECTED + COMPLETED)
-- ═══════════════════════════════════════════════════════════════
SELECT
    d.order_id                                                            AS orden,
    d.status                                                              AS estado,
    dt.name                                                               AS tipo,
    to_char(d.created_at,   'DD/MM HH24:MI')                              AS creado,
    to_char(d.completed_at, 'DD/MM HH24:MI')                              AS completado,
    ds.name                                                               AS dispensador,
    d.hose_id                                                             AS manguera,
    h.side                                                                AS lado,
    g.name                                                                AS producto,
    d.preset_value                                                        AS preset,
    d.preset_type                                                         AS tipo_preset,
    d.sequential_number                                                   AS secuencial,
    -- Cliente
    p.name                                                                AS cliente,
    p.id_type || ': ' || p.id_number                                      AS id_cliente,
    p.phone                                                               AS telefono,
    -- Vehículo
    v.plate                                                               AS placa,
    -- Totales dispatch
    d.subtotal                                                            AS subtotal_desp,
    d.tax_amount                                                          AS iva_desp,
    d.total                                                               AS total_desp,
    -- Totales detalle
    dd.quantity                                                           AS galones,
    dd.unit_price                                                         AS precio_galon,
    dd.subtotal                                                           AS subtotal_det,
    dd.tax_amount                                                         AS iva_det,
    dd.total                                                              AS total_det,
    -- Cobro
    COALESCE(dp.forma_pago, '—')                                          AS forma_pago,
    COALESCE(dp.referencias, '—')                                         AS ref_pago,
    COALESCE(dp.total_pagado, 0)                                          AS total_pagado,
    -- Diferencias
    CASE WHEN d.total != COALESCE(dd.total, 0)
         THEN '⚠ DET' END                                                  AS alerta_detalle,
    CASE WHEN d.total != COALESCE(dp.total_pagado, 0)
         THEN '⚠ PAGO' END                                                 AS alerta_pago,
    -- SRI
    d.sri_status                                                          AS sri,
    d.credit_status                                                       AS credito
FROM dispatches d
JOIN dispensers ds          ON ds.dispenser_id      = d.dispenser_id
LEFT JOIN hoses h           ON h.hose_id            = d.hose_id
LEFT JOIN grades g          ON g.code               = h.grade_id
LEFT JOIN dispatch_types dt ON dt.dispatch_type_id  = d.dispatch_type_id
LEFT JOIN persons p         ON p.person_id          = d.person_id
LEFT JOIN vehicles v        ON v.vehicle_id         = d.vehicle_id
LEFT JOIN dispatch_details dd ON dd.dispatch_id     = d.dispatch_id
LEFT JOIN LATERAL (
    SELECT
        STRING_AGG(pm.name, ' + ' ORDER BY pm.name)         AS forma_pago,
        STRING_AGG(COALESCE(dp2.reference_code, ''), ' | ') AS referencias,
        SUM(dp2.amount)                                     AS total_pagado
    FROM dispatch_payments dp2
    JOIN payment_methods pm ON pm.payment_method_id = dp2.payment_method_id
    WHERE dp2.dispatch_id = d.dispatch_id
) dp ON true
WHERE d.shift_id = :shift_id
  AND d.status IN ('COLLECTED', 'COMPLETED')
ORDER BY d.created_at;
