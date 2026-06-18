-- ═══════════════════════════════════════════════════════════════
-- consulta_despachos_turno.sql
-- Muestra despachos de un turno con persona, vehículo, usuario,
-- totales (dispatches, details, payments) y forma de pago.
--
-- Uso: reemplazar :shift_id por el número de turno deseado.
-- Ejemplo: \set shift_id 28
-- ═══════════════════════════════════════════════════════════════

\set shift_id 28

-- ── Encabezado: datos del turno ────────────────────────────
SELECT
    '═══ TURNO ' || s.shift_id || ' ═══' AS encabezado,
    s.status                                          AS estado_turno,
    to_char(s.opened_at, 'DD/MM/YYYY HH24:MI')        AS apertura,
    to_char(s.closed_at, 'DD/MM/YYYY HH24:MI')        AS cierre,
    u.name                                            AS cajero,
    s.accounting_date                                 AS fecha_contable,
    s.opening_cash                                    AS caja_inicial,
    s.closing_cash                                    AS caja_final,
    COALESCE(s.surplus, 0)                            AS sobrante,
    COALESCE(s.shortage, 0)                           AS faltante
FROM shifts s
JOIN users u ON u.user_id = s.user_id
WHERE s.shift_id = :shift_id;

-- ── Resumen financiero del turno ───────────────────────────
SELECT
    COUNT(*)                                                           AS total_despachos,
    SUM(CASE WHEN d.status = 'COLLECTED' THEN 1 ELSE 0 END)           AS cobrados,
    SUM(CASE WHEN d.status = 'COMPLETED' THEN 1 ELSE 0 END)           AS completados_sin_cobrar,
    SUM(CASE WHEN d.status = 'AUTHORIZED' THEN 1 ELSE 0 END)          AS autorizados,
    SUM(CASE WHEN d.status = 'CANCELLED' THEN 1 ELSE 0 END)           AS cancelados,
    COALESCE(SUM(d.total), 0)                                         AS total_despachos_usd,
    COALESCE(SUM(CASE WHEN d.status = 'COLLECTED' THEN d.total ELSE 0 END), 0) AS total_cobrado_usd
FROM dispatches d
WHERE d.shift_id = :shift_id;

-- ── Detalle de cada despacho ────────────────────────────────
SELECT
    d.dispatch_id,
    d.order_id,
    d.status,
    dt.name                                                              AS tipo,
    to_char(d.created_at, 'DD/MM HH24:MI')                               AS creado,
    to_char(d.completed_at, 'DD/MM HH24:MI')                             AS completado,
    -- Dispensador / manguera
    ds.name                                                              AS dispensador,
    d.hose_id                                                            AS manguera_id,
    h.side                                                               AS lado,
    d.grade_id                                                           AS producto,
    d.preset_value                                                       AS preset,
    -- Secuencial / factura
    d.sequential_number                                                  AS secuencial,
    -- Persona (cliente)
    p.name                                                               AS cliente,
    p.id_type || ': ' || p.id_number                                     AS id_cliente,
    p.phone                                                              AS telefono,
    -- Vehículo
    v.plate                                                              AS placa,
    -- Usuario que autorizó
    au.name                                                              AS autorizado_por,
    -- Totales — tabla dispatches
    d.subtotal                                                           AS subtotal_disp,
    d.tax_amount                                                         AS iva_disp,
    d.total                                                              AS total_disp,
    -- Totales — tabla dispatch_details
    dd.subtotal                                                          AS subtotal_det,
    dd.tax_amount                                                        AS iva_det,
    dd.total                                                             AS total_det,
    dd.quantity                                                          AS cantidad,
    dd.unit_price                                                        AS precio_unitario,
    -- Totales — tabla dispatch_payments (suma por despacho)
    COALESCE(dp.total_pagado, 0)                                         AS total_pagado,
    dp.forma_pago,
    -- SRI
    d.sri_status,
    -- Diferencia: dispatch vs detail vs payment
    d.total - COALESCE(dd.total, 0)                                      AS diff_disp_vs_det,
    d.total - COALESCE(dp.total_pagado, 0)                               AS diff_disp_vs_pago
FROM dispatches d
JOIN dispensers ds          ON ds.dispenser_id = d.dispenser_id
LEFT JOIN hoses h           ON h.hose_id = d.hose_id
LEFT JOIN dispatch_types dt ON dt.dispatch_type_id = d.dispatch_type_id
LEFT JOIN persons p         ON p.person_id = d.person_id
LEFT JOIN vehicles v        ON v.vehicle_id = d.vehicle_id
LEFT JOIN users au          ON au.user_id = d.authorized_by_user_id
LEFT JOIN dispatch_details dd ON dd.dispatch_id = d.dispatch_id
LEFT JOIN LATERAL (
    SELECT
        SUM(dp2.amount)                                 AS total_pagado,
        STRING_AGG(DISTINCT pm.name, ', ')             AS forma_pago
    FROM dispatch_payments dp2
    JOIN payment_methods pm ON pm.payment_method_id = dp2.payment_method_id
    WHERE dp2.dispatch_id = d.dispatch_id
) dp ON true
WHERE d.shift_id = :shift_id
ORDER BY d.created_at DESC;

-- ── Totales por forma de pago ───────────────────────────────
SELECT
    pm.name                                                              AS forma_pago,
    COUNT(DISTINCT dp.dispatch_id)                                       AS despachos,
    SUM(dp.amount)                                                       AS total_usd
FROM dispatch_payments dp
JOIN payment_methods pm ON pm.payment_method_id = dp.payment_method_id
JOIN dispatches d ON d.dispatch_id = dp.dispatch_id
WHERE d.shift_id = :shift_id
GROUP BY pm.name
ORDER BY total_usd DESC;
