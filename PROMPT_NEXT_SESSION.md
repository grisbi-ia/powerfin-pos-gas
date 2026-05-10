# PROMPT_NEXT_SESSION — Powerfin POS

## Dónde nos quedamos

**Último tag:** `v0.3.0` — Fase 4: flujo de venta completo con mocks.

**Cambios sin commitear (deben versionarse al iniciar):**
- SSE usa broadcast a múltiples listeners (fix para que `/fueling` reciba eventos)
- Forma de pago reubicada: se selecciona **después del despacho** en `/confirmation`
- Métodos de pago ahora son configurables desde PowerFin (`payment_methods` en AppConfig)
- Campo `requires_reference` en métodos de pago: si es `true`, muestra input para código de transacción
- Métodos agregados al mock: DeUna, JepFast, Sipy, Tarjeta (todos con `requires_reference: true`)

## Lo próximo a implementar

### Registrar nuevo cliente + vehículo (desde el POS)

En `/new-dispatch`, al buscar clientes, agregar un botón "Nuevo cliente" que abra un formulario con:
- Tipo de ID (CED/RUC)
- Número de identificación
- Nombre
- Placa del vehículo
- Email, teléfono (opcionales)

El endpoint es `POST /api/pos/customers` (definido en `docs/API_CONTRACT.md`). El mock debe simular el registro y devolver el cliente creado con su `price_list`.

### Mejoras al CustomerSearch

- Si no hay resultados, mostrar botón "Registrar nuevo cliente"
- Al registrar, insertar automáticamente el cliente en la búsqueda

## Para iniciar la sesión

```bash
cd /home/pvalarezo/grisbiapps/powerfin_pos_gas
git status          # ver cambios sin commitear
git log --oneline -5

# POS
cd pos
export PATH=$HOME/.n/bin:$PATH
npm run dev         # iniciar servidor de desarrollo

# Tests
npm run check       # TypeScript (0 errores)
npm run test        # Vitest (31 tests)
```

## Estado de tests

- FusionBridge: 35 tests (./mvnw test)
- Powerfin POS: 31 tests (npm run test)
- Total: 66 tests pasando

## Datos de prueba (mock)

- Login: `carlos` / PIN `1234`
- Cliente VIP: "Juan Carlos Pérez", cédula `0912345678`, placa `ABC-1234`
- Cliente estándar: "Transportes Andinos S.A.", RUC `1790012345001`

## RAMAS — trabajar en develop

```bash
git checkout develop
```

## No olvidar

- Documentación en español, código en inglés
- Commits en inglés: feat(pos): / fix(pos): / test(pos):
- Versionar solo después de que todos los tests pasen
- Actualizar ROADMAP.md y AGENTS.md al completar
