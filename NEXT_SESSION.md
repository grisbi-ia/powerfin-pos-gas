# NEXT_SESSION.md — Powerfin POS

## Estado actual (2026-07-13) — v0.34.0

### ✅ Logros de la sesión

#### Despachos a crédito — sector público + contratos ✅
- `PENDING_BULK_INVOICE` credit_status para contratos NO_INDEFINIDO
- Factura global / liquidación para sector público
- Migraciones: plate 15 chars, PENDING_BULK_INVOICE constraint
- Admin: módulo contracts (listado + liquidación)

#### Cleanup automático de despachos huérfanos ✅
- Servicio `dispatch_cleanup.py`: cada 60s cancela AUTHORIZED + $0.00 con >900s
- `ORPHAN_AGE_SECONDS = 900` (15 min) — seguro para camiones grandes
- Endpoints: `GET /orphans`, `POST /cleanup-orphans`
- 5 tests dedicados, 0 regresiones en test suite completa

#### Ticket de crédito con firma ✅
- `contractCode` en receipt data (backend → FusionBridge)
- Bloque condicional `{#credit}` en template ESC/POS
- Línea de firma: RECIBI CONFORME / FIRMA / CEDULA

#### Bugfixes en producción
- `powerfin-gas`: fix permisos `chown` antes de cada build
- `deploy-to-server.sh`: IP actualizada a Cloudflare Tunnel

#### Intervenciones manuales en BD (producción)
- #6447: COMPLETED $10.00 → CANCELLED (turno cerrado, nunca cobrado)
- #6512: AUTHORIZED $0.00 → CANCELLED (pistola levantada sin autorizar)
- #6517: AUTHORIZED $0.00 → restaurado COMPLETED $102.28 (cancelado por error durante carga)
- #6573: AUTHORIZED $0.00 → restaurado COMPLETED $57.00 (cancelado por cleanup service)

### 🆕 Próximas tareas

```
☐ 1. Admin — sección "Despachos con problemas"
   · Listar despachos en estados anómalos (AUTHORIZED $0.00, COMPLETED sin cobrar)
   · Botones de acción: Cancelar huérfano, Restaurar, Forzar completado
   · Solo ADMIN/SUPERVISOR — evitar intervención SQL manual

☐ 2. Admin — modificar precios de Lista de Precios
   · Pantalla price-lists/[id]: editar unit_price inline en la tabla de items

☐ 3. Precios programados — cambio automático a las 00:00 horas
   · Tabla: scheduled_price_changes
   · Backend: scheduler que aplique cambios pendientes al iniciar el día
   · Admin: CRUD para programar cambios de precio futuros

☐ 4. Pago mixto (efectivo + tarjeta)
☐ 5. identity_service.py — mover URL y token a system_config
☐ 6. Roles/permisos — enforcement real en POS endpoints
☐ 7. Flujo de crédito en el POS — selector en SaleWizard
☐ 8. Nginx rate limiting login
☐ 9. Prueba E2E completa (admin → POS)
```

---

## Configuración del sitio

| Dato | Valor |
|------|-------|
| Estación | NEOGAS |
| Surtidores | 4: 1 SUPER-ECO, 2 ECO, 3 DIESEL, 4 DIESEL |
| Puntos emisión | 001-001 a 001-004 |
| Formas de pago | EFECTIVO, TARJETA, CREDITO DIRECTO, YALOBOX |
| ATO Wayne | 180s (próximo cambio a 300s) |
| Cleanup huérfanos | 900s (15 min) |
| Cliente requerido | Sí (cédula o RUC obligatorio) |
| Firmware Wayne | Rel-5.19.1 |

## Base de datos

| Dato | Valor |
|------|-------|
| Host | 192.168.1.25:5432 |
| Database | powerfin_gas |
| User (lectura) | agent_llm / AgentLLM123 |
| User (admin) | postgres / Post20Gres17 |

## Deploy a producción

```bash
# Desde desarrollo
./scripts/deploy-to-server.sh backend|frontend|admin|fusion|all

# En el servidor
ssh app@100.97.47.123
powerfin-gas pending
powerfin-gas deploy-all
powerfin-gas status
```

## Lecciones aprendidas

- **NUNCA cancelar AUTHORIZED $0.00 sin verificar si el surtidor está cargando.** 
  Despachos FULL/VOLUME grandes pueden tomar 5-12 minutos con $0.00 hasta que el
  Wayne manda el completado.
- **El cleanup service ahora espera 15 minutos** — suficiente para el camión más grande.
- **El deploy del frontend/admin no afecta el flujo de despacho** — backend y FusionBridge
  son independientes.
