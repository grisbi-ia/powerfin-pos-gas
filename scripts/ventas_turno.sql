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
-- dispatch_count: todos los despachos NO cancelados (coincide con backend)
-- montos: solo COLLECTED (único status que tiene cobro real)
SELECT
    (SELECT COUNT(*) FROM dispatches
     WHERE shift_id = :shift_id AND status != 'CANCELLED') AS total_despachos,
    (SELECT COUNT(*) FROM dispatches
     WHERE shift_id = :shift_id AND status = 'COLLECTED')  AS despachos_cobrados,
    (SELECT COUNT(*) FROM dispatches
     WHERE shift_id = :shift_id AND status = 'CANCELLED')  AS despachos_cancelados,
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

-- ═══════════════════════════════════════════════════════════════
-- CIERRE DE TURNO — Cuadre de caja
-- Calcula cuánto efectivo debe tener el cajero al cerrar turno.
-- ═══════════════════════════════════════════════════════════════
--
-- Fórmula (coincide con _compute_shift_summary en shifts.py):
--   efectivo_esperado = caja_inicial
--                     + ventas_en_efectivo (COLLECTED + payment_method_id=1)
--                     + income (INCOME + TRANSFER_IN agrupados)
--                     - expense
--                     - deposit
--                     - transfer_out
--                     - safe_drop
--
--   diferencia = efectivo_declarado - efectivo_esperado

WITH
shift_base AS (
    SELECT shift_id, opening_cash, closing_cash, surplus, shortage, status
    FROM shifts
    WHERE shift_id = :shift_id
),
cash_sales AS (
    -- Ventas cobradas en EFECTIVO (payment_method_id = 1, igual que el backend)
    SELECT COALESCE(SUM(dp.amount), 0) AS total_cash
    FROM dispatches d
    JOIN dispatch_payments dp ON dp.dispatch_id = d.dispatch_id
    WHERE d.shift_id = :shift_id
      AND d.status = 'COLLECTED'
      AND dp.payment_method_id = 1
),
cash_movements AS (
    -- Agrupa movimientos de caja por tipo (coincide con _compute_shift_summary)
    -- INCOME + TRANSFER_IN se suman en un solo rubro "income" como hace el backend
    SELECT
        COALESCE(SUM(CASE WHEN type IN ('INCOME', 'TRANSFER_IN') THEN amount ELSE 0 END), 0) AS total_income,
        COALESCE(SUM(CASE WHEN type = 'EXPENSE'       THEN amount ELSE 0 END), 0) AS total_expense,
        COALESCE(SUM(CASE WHEN type = 'SAFE_DROP'     THEN amount ELSE 0 END), 0) AS total_safe_drop,
        COALESCE(SUM(CASE WHEN type = 'TRANSFER_OUT'  THEN amount ELSE 0 END), 0) AS total_transfer_out,
        COALESCE(SUM(CASE WHEN type = 'DEPOSIT'       THEN amount ELSE 0 END), 0) AS total_deposit
    FROM cash_movements
    WHERE shift_id = :shift_id
)

-- ── Cuadre de caja (fórmula exacta del backend) ───────────
SELECT
    '💰 CUADRE DE CAJA'                       AS concepto,
    sb.opening_cash                           AS caja_inicial,
    cs.total_cash                             AS ventas_efectivo,
    cm.total_income                           AS income_transfer_in,
    cm.total_expense                          AS gastos_salidas,
    cm.total_deposit                          AS depositos_bancarios,
    cm.total_transfer_out                     AS enviado_transferencias,
    cm.total_safe_drop                        AS envios_caja_fuerte,
    -- Efectivo que DEBERÍA haber en caja (fórmula del backend)
    (sb.opening_cash
      + cs.total_cash
      + cm.total_income
      - cm.total_expense
      - cm.total_deposit
      - cm.total_transfer_out
      - cm.total_safe_drop)                   AS efectivo_esperado,
    -- Efectivo declarado por el cajero al cerrar
    sb.closing_cash                           AS efectivo_declarado,
    -- Diferencia: positivo = sobra, negativo = falta
    (sb.closing_cash - (
        sb.opening_cash
        + cs.total_cash
        + cm.total_income
        - cm.total_expense
        - cm.total_deposit
        - cm.total_transfer_out
        - cm.total_safe_drop
    ))                                        AS diferencia,
    CASE
        WHEN sb.closing_cash - (
            sb.opening_cash
            + cs.total_cash
            + cm.total_income
            - cm.total_expense
            - cm.total_deposit
            - cm.total_transfer_out
            - cm.total_safe_drop
        ) > 0 THEN 'SOBRANTE ↑'
        WHEN sb.closing_cash - (
            sb.opening_cash
            + cs.total_cash
            + cm.total_income
            - cm.total_expense
            - cm.total_deposit
            - cm.total_transfer_out
            - cm.total_safe_drop
        ) < 0 THEN 'FALTANTE ↓'
        ELSE 'CUADRADO ✓'
    END                                       AS estado
FROM shift_base sb
CROSS JOIN cash_sales cs
CROSS JOIN cash_movements cm;

-- ── Desglose de movimientos de caja ────────────────────────
SELECT
    cm.movement_id                            AS id,
    cm.type                                   AS tipo,
    cm.amount                                 AS monto,
    cm.running_balance                        AS balance_tras_movimiento,
    cm.observation                            AS observacion,
    to_char(cm.created_at, 'DD/MM HH24:MI')   AS fecha_hora
FROM cash_movements cm
WHERE cm.shift_id = :shift_id
ORDER BY cm.created_at;

-- ── Desglose de transferencias entre cajeros ───────────────
SELECT
    t.transfer_id                             AS id,
    'TRANSFER_OUT'                            AS tipo,
    t.amount                                  AS monto,
    t.to_user_name                            AS destinatario,
    t.observation                             AS observacion,
    to_char(t.created_at, 'DD/MM HH24:MI')    AS fecha_hora
FROM transfers t
WHERE t.from_shift_id = :shift_id
ORDER BY t.created_at;

-- ── Totales que NO son efectivo (referencia, payment_method_id != 1) ──
SELECT
    pm.name                                   AS forma_pago,
    COUNT(DISTINCT d.dispatch_id)             AS despachos,
    SUM(dp.amount)                            AS total_usd
FROM dispatches d
JOIN dispatch_payments dp ON dp.dispatch_id = d.dispatch_id
JOIN payment_methods pm ON pm.payment_method_id = dp.payment_method_id
WHERE d.shift_id = :shift_id
  AND d.status = 'COLLECTED'
  AND dp.payment_method_id != 1
GROUP BY pm.name
ORDER BY total_usd DESC;
