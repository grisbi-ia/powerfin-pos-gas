# Powerfin POS — Documentación Técnica

## Visión general

Sistema de punto de venta para estaciones de servicio de combustible.

Compuesto por dos nuevos desarrollos que trabajan junto al ERP PowerFin existente.

---

## Los tres actores

```
┌──────────────────────────────────────────────────────────┐
│              SERVIDOR DEBIAN 12 — GASOLINERA                 │
│                     192.168.1.10                         │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │              PowerFin ERP (existente)            │   │
│  │              OpenXava / Java 8 — :8080           │   │
│  │  ✅ Clientes y vehículos    ✅ Facturación SRI   │   │
│  │  ✅ Listas de precios       ✅ Contabilidad       │   │
│  │  ✅ Ventas y cobros         ✅ Turnos operativos  │   │
│  └──────────────────────┬───────────────────────────┘   │
│                         │ REST API /api/pos/*            │
│            ┌────────────┴────────────┐                   │
│            │                         │                   │
│  ┌─────────▼──────────┐  ┌──────────▼─────────────┐    │
│  │   FusionBridge     │  │    PowerFin POS    │    │
│  │  Quarkus/Java 21   │  │  SvelteKit — estáticos  │    │
│  │  :8090             │  │  servidos por Nginx      │    │
│  │                    │  │                          │    │
│  │  ✅ TCP con Fusion  │  │  ✅ Interfaz touch       │    │
│  │  ✅ ESC/POS         │  │  ✅ Gestión de turnos   │    │
│  │  ✅ SSE → Powerfin POS  │  │  ✅ Búsqueda clientes   │    │
│  │  ✅ Cola pendientes │  │  ✅ Nueva venta          │    │
│  └─────────┬──────────┘  │  ✅ Estado surtidores   │    │
│            │              │  ✅ Ticket impreso       │    │
│            │              └────────────────────────┘    │
│            │ TCP :3011                                    │
│  ┌─────────▼──────────┐                                  │
│  │   Wayne Synergy    │  192.168.1.20                   │
│  └─────────┬──────────┘                                  │
│            │ Serial COM1                                  │
│  ┌─────────▼──────────┐                                  │
│  │   Dispensadores    │                                  │
│  └────────────────────┘                                  │
│                                                          │
│  Impresoras de red:                                      │
│  Isla 1: 192.168.1.31:9100                              │
│  Isla 2: 192.168.1.32:9100                              │
└──────────────────────────────────────────────────────────┘
              │ HTTPS (Nginx + Certbot)
              ▼
   Celulares / Tablets despachadores
   PWA instalada en pantalla de inicio
```

---

## Principio de diseño

```
PowerFin es el cerebro — datos y lógica de negocio.
FusionBridge es el puente — hardware + impresión.
Powerfin POS son las manos — interfaz del despachador.

Ninguno duplica la responsabilidad del otro.
```

---

## Archivos de documentación

| Archivo                | Contenido                                            |
| ---------------------- | ---------------------------------------------------- |
| `README.md`            | Este archivo — visión general                        |
| `FUSION_BRIDGE.md`     | Arquitectura y código del FusionBridge               |
| `POWERFIN_POS.md`      | Arquitectura y código del Powerfin POS               |
| `API_CONTRACT.md`      | Contrato completo entre los tres sistemas            |
| `FUSION_PROTOCOL.md`   | Protocolo TCP Wayne Fusion (datos reales GASOLINERA) |
| `FLUJOS_OPERATIVOS.md` | Flujos del despachador con mockups                   |
| `INFRAESTRUCTURA.md`   | Debian, systemd, Nginx, deploy                       |
| `ROADMAP.md`           | Plan de desarrollo fase por fase                     |

---

## Convenciones

```
Documentación:    español
Código fuente:    inglés (Java, Svelte, SQL, variables, métodos, comentarios)
Chat con AGENTS:  español
```

---

## Datos técnicos validados (pruebas reales con GASOLINERA)

```
Wayne Synergy:   192.168.1.20:3011
Firmware:        Rel-5.19.1 (Windows, Hardware V2)
Protocolo:       Fusion Native Protocol (texto, separado por pipes)
Keep-alive:      ECHO cada 120s, timeout 360s
Configuración:   NEOPAUTE — Ecuador, USD, litros, modo AUTOMATIC
                 1 surtidor, 2 pistolas, SUPER $9.999/litro
```
