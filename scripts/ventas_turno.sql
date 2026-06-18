-- ═══════════════════════════════════════════════════════════════
-- ventas_turno.sql — Ventas cobradas de un turno con cliente,
-- vehículo, forma de pago y referencia.
--
-- Uso: \set shift_id 28   o   psql -v shift_id=28 -f script.sql
-- ═══════════════════════════════════════════════════════════════

\set shift_id 28

-- ── Encabezado ────────────────────────────────────────────
SELECT '═══ TURNO ' || s.shift_id || ' ═══' AS encabezado,
       u.name AS cajero,
       s.status,
       to_char(s.opened_at, 'DD/MM/YYYY HH24:MI') AS apertura,
       to_char(s.closed_at, 'DD/MM/YYYY HH24:MI') AS cierre,
       s.opening_cash AS caja_inicial,
       s.surplus AS sobrante,
       s.shortage AS faltante
FROM shifts s
JOIN users u ON u.user_id = s.user_id
WHERE s.shift_id = :shift_id;

-- ── Totales ────────────────────────────────────────────────
SELECT COUNT(*)                    AS despachos_cobrados,
       SUM(d.total)                AS total_usd,
       SUM(d.tax_amount)           AS total_iva,
       SUM(d.subtotal)             AS total_sin_iva
FROM dispatches d
WHERE d.shift_id = :shift_id AND d.status = 'COLLECTED';

-- ── Detalle ────────────────────────────────────────────────
SELECT
    d.order_id                                 AS orden,
    d.sequential_number                        AS factura,
    to_char(d.created_at, 'DD/MM HH24:MI')     AS creado,
    ds.name                                    AS dispensador,
    d.hose_id                                  AS manguera,
    d.grade_id                                 AS producto,
    d.preset_value || ' (' || COALESCE(d.preset_type,'MONEY') || ')' AS preset,
    p.name                                     AS cliente,
    p.id_type || ': ' || p.id_number           AS id_cliente,
    p.phone                                    AS telefono,
    v.plate                                    AS placa,
    dd.quantity                                AS cantidad,
    dd.unit_price                              AS precio_unitario,
    d.subtotal                                 AS subtotal,
    d.tax_amount                               AS iva,
    d.total                                    AS total,
    pm.name                                    AS forma_pago,
    dp.reference_code                          AS referencia,
    au.name                                    AS despachador,
    d.sri_status                               AS sri
FROM dispatches d
JOIN dispensers ds          ON ds.dispenser_id = d.dispenser_id
LEFT JOIN persons p         ON p.person_id = d.person_id
LEFT JOIN vehicles v        ON v.vehicle_id = d.vehicle_id
LEFT JOIN dispatch_details dd ON dd.dispatch_id = d.dispatch_id
LEFT JOIN dispatch_payments dp ON dp.dispatch_id = d.dispatch_id
LEFT JOIN payment_methods pm ON pm.payment_method_id = dp.payment_method_id
LEFT JOIN users au          ON au.user_id = d.authorized_by_user_id
WHERE d.shift_id = :shift_id AND d.status = 'COLLECTED'
ORDER BY d.created_at;

-- ── Totales por forma de pago ─────────────────────────────
SELECT
    pm.name                                    AS forma_pago,
    COUNT(DISTINCT d.dispatch_id)              AS despachos,
    SUM(dp.amount)                             AS total_usd
FROM dispatches d
JOIN dispatch_payments dp ON dp.dispatch_id = d.dispatch_id
JOIN payment_methods pm ON pm.payment_method_id = dp.payment_method_id
WHERE d.shift_id = :shift_id AND d.status = 'COLLECTED'
GROUP BY pm.name
ORDER BY total_usd DESC;

-- ── Resumen por producto ──────────────────────────────────
SELECT
    d.grade_id                                 AS producto,
    COUNT(*)                                   AS despachos,
    SUM(dd.quantity)                           AS galones,
    SUM(d.total)                               AS total_usd
FROM dispatches d
LEFT JOIN dispatch_details dd ON dd.dispatch_id = d.dispatch_id
WHERE d.shift_id = :shift_id AND d.status = 'COLLECTED'
GROUP BY d.grade_id
ORDER BY total_usd DESC;
