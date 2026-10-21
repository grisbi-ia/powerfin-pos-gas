# Análisis de precios y propuesta comercial
## Powerfin ERP + Powerfin POS GAS

**Documento interno — no enviar al cliente.**
Versión 4.1 · Fecha: 2026-10-20

> v4.0 reemplaza los “planes” por **cuatro rubros explícitos**: instalación,
> precio del sistema, soporte mensual y actualizaciones mayores. El cliente sabe
> qué paga una vez, qué paga cada mes y qué se cotiza aparte. Ver §3 y §4.
>
> v4.1 documenta **cómo se fijó cada precio** (§5), agrega la columna *Costo a
> 5 años* para comparar las modalidades en el mismo horizonte (§4.2) y corrige la
> cifra de payback del anexo (§10): no es 0,05% de merma, son 0,09% para pagar en
> 12 meses.

---

## 1. Resumen ejecutivo

La oferta queda con **cuatro rubros** y una sola decisión de pago: contado o
financiado.

| # | Rubro | Tipo | Valor (tramo mediano) |
|---|---|---|---|
| 1 | Instalación, implementación y capacitación | Una vez | **$1.200** |
| 2 | Precio del sistema (ERP + POS + Admin) | Una vez o financiado | **$7.500** |
| 3 | Soporte mensual y actualizaciones menores | Mensual | **$175/mes** |
| 4 | Actualizaciones mayores | Cuando se pacten | **20% del sistema ($1.500)** por versión |

- **Contado:** $8.875 el día 0 (instalación + sistema + primer soporte) y
  $175/mes. Costo a 5 años: **$19.200**.
- **Financiado:** 20% del sistema al inicio ($1.500) y el saldo a 12% anual.
  - 24 meses: $3.157 el día 0 y **$457/mes**; total $13.679.
  - 36 meses: $3.074 el día 0 y **$374/mes**; total $16.174.
  - 48 meses: $3.033 el día 0 y **$333/mes**; total $18.684.
- **Comparación al mismo horizonte (5 años):** contado **$19.200** < 24 meses
  $19.979 < 36 meses $20.374 < 48 meses $20.784. Financiar cuesta exactamente el
  interés ($779 / $1.174 / $1.584) y nunca menos que el contado.
- **Equivalente mensual del contado a 5 años:** $320/mes, dentro del rango de
  mercado de software para gasolineras ($150–$500/estación/mes).

Dos riesgos que hay que mirar antes de firmar:

1. **Financiar con 20% de inicial exige capital de trabajo.** El día 0 entran
   $3.157 y la entrega cuesta ~$4.500: el punto de equilibrio llega entre el
   mes 3 y el mes 5 según el plazo. Si no hay caja para eso, subir el inicial
   a 30–40%.
2. **Key49 incluido sin tope.** Incluir hasta 3.000 facturas/mes y facturar el
   excedente al costo. Ver §7.4.

---

## 2. Qué estamos vendiendo

### 2.1 Powerfin ERP (según documentación oficial)

| Bloque | Módulos |
|---|---|
| Gestión financiera | Contabilidad General, Cuentas por Cobrar, Cuentas por Pagar, Control Bancario, Activos Fijos, Presupuesto Financiero, Control Presupuestal, Caja Chica, Flujo de Caja |
| Comercial | Ventas, Facturación electrónica, Listas de precios, Sucursales, CRM, Ecommerce, Documentos electrónicos |
| Compras y operación | Compras, Inventario/Almacenes, Logística, Producción, Taller y órdenes de trabajo |
| Personas | Nómina y roles de pago, Recursos Humanos |
| Analítica | Reportería, Indicadores, Business Intelligence, Alertas y notificaciones |
| Financiero extendido | Préstamos, Inversiones, Originación de cartera, Confirming y Factoring |
| Plataforma | Servicios Web REST (API-KEY + JWT), Movilidad, Multimoneda, Multilingüe, Parametrización |

Datos duros: Java 8+, PostgreSQL 9.6+, cualquier SO con Java, cualquier servidor
de aplicaciones con Servlets 3.1+, solo navegador. Implantado en 26 empresas a
nivel nacional e internacional.

### 2.2 Powerfin POS GAS (verificado en este repositorio)

| Bloque | Capacidad real |
|---|---|
| Pista | Estado de surtidores en tiempo real (SSE), autorización, preset por monto/volumen/lleno, stop, clear, destrabe de surtidor `PAUSED` (comando `REAUTH`; botón en UI pendiente) |
| Venta | Búsqueda por cédula/RUC/placa/nombre, validación de cédula (módulo 10), registro y actualización de cliente, vehículos internos predefinidos con balanceo |
| Precios | Listas con prioridad vehículo > persona > default |
| Cobro | Efectivo, tarjeta, transferencia, Yalobox, crédito con cupo. Pago mixto existe en el API (`payments[]`); la UI de pista hoy envía un solo medio |
| Crédito | Contratos, cupo disponible, liquidación, sector público con facturación en lote |
| Fiscal | Factura electrónica SRI vía Key49, clave de 49 dígitos, reintentos automáticos, regeneración al cruzar medianoche, monitor y reconciliación |
| Impresión | ESC/POS por socket TCP directo a impresora de isla, plantilla configurable, reimpresión con fecha original |
| Caja | Apertura/cierre de turno, cuadre, transferencias, depósitos a caja fuerte, medidores mecánicos |
| Administración | Dashboard, reportes, export PDF/Excel, CRUD de 11 módulos, roles y permisos, monitor SRI |
| Resiliencia | Recuperación de despachos, limpieza de huérfanos, sin fallbacks silenciosos |
| Pruebas | 696 pruebas automatizadas (548 backend + 71 FusionBridge + 77 POS) |

### 2.3 Lo que NO incluye

- Tanques / telemedición ATG / detección de fugas
- Tienda de conveniencia (inventario de tienda, básculas, escáner)
- Control de flotas con tarjetas RFID
- Certificado digital y firma electrónica del contribuyente
- Hardware: dispensadores, controlador, impresoras, servidor, red, UPS
- Nómina ecuatoriana con cálculo de IESS si no se configura el módulo

---

## 3. De dónde venimos y por qué cambió el modelo

### 3.1 v1.0 — anticipo grande, plan dominado

| Plan | Inicial | Mensual | Total 24 m |
|---|---:|---:|---:|
| Estándar | $7.500 | $250 | $13.500 |
| Entrada baja | $4.500 | $350 | $12.900 |
| Sin inversión | $0 | $550 | $13.200 |

**Problema:** el plan de $7.500 pagaba más al inicio y, en flujo acumulado,
gastaba más que los otros hasta el **mes 25** (vs. Sin inversión) y el **mes 30**
(vs. Entrada baja). Estaba dominado en el horizonte de decisión.

### 3.2 v2.0 — se eliminó el anticipo (error)

La v2.0 bajó la instalación a $300 y dejó el pago inicial en $850/$650/$550.
A 24 meses el total no cambió:

```
$7.500 + 24 × $250 = $13.500  =  $300 + 24 × $550
```

Lo único que cambió fue **cuándo se cobra**: $6.650 que entraban el día 0
pasaron a los meses 1–24. Con $850 el día 0 no se cubre ni la implementación
(~$4.500). La v2.0 optimizó **cerrar la venta**, no **cobrar caja**.

### 3.3 v3.0 — el anticipo vuelve, pero mezclado con el soporte

La v3 agregó un “anticipo de $7.500” con descuentos sobre el total. Funcionaba
para la caja, pero seguía mezclando dos rubros distintos:

- el **precio del sistema**, que se paga una vez; y
- el **soporte mensual**, que se paga todos los meses.

Al meter ambos en una sola cuota, “Total lista” y “Anticipo” no se entendían sin
explicar la fórmula. Además, el soporte implícito cambiaba con el plazo:
$237,50/mes en 24 m, $141,67 en 36 m y $93,75 en 48 m. Eso hacía que el plan de
48 m vendiera soporte por debajo del costo.

### 3.4 v4.0 — cuatro rubros explícitos

La regla es simple: **cada cosa que se cobra tiene su propia línea y su propio
precio**.

1. Instalación: una vez.
2. Sistema: una vez, o financiado.
3. Soporte: mensual, siempre el mismo valor.
4. Actualizaciones mayores: una vez, cuando se pacten.

El plazo ya no cambia el precio del soporte ni el del sistema: solo decide en
cuántas cuotas se paga el sistema. Eso es lo que el cliente entiende.

---

## 4. Estructura vigente (v4)

### 4.1 Los cuatro rubros

| # | Rubro | Tipo | Valor (mediana) | Qué cubre |
|---|---|---|---:|---|
| 1 | Instalación, implementación y capacitación | Único | $1.200 | Levantamiento, configuración, migración, capacitación, go-live |
| 2 | Precio del sistema | Único o financiado | $7.500 | Licencia de ERP Powerfin + POS GAS + Admin |
| 3 | Soporte mensual y actualizaciones menores | Mensual | $175 | Hosting, respaldos, monitoreo, Key49 hasta 3.000 facturas/mes, soporte, parches y cambios regulatorios |
| 4 | Actualizaciones mayores | Único, opcional | 20% del sistema ($1.500) | Versión mayor cada 3–4 años o módulos nuevos, cotizados por proyecto |

**Regla de oro:** los cambios regulatorios del SRI **no** son rubro 4; están
incluidos en el soporte. Si no, el cliente queda expuesto a multas y nosotros a
una discusión comercial.

### 4.2 Formas de pago

**Contado**

| Concepto | Valor |
|---|---:|
| Rubro 1 | $1.200 |
| Rubro 2 | $7.500 |
| Primer mes de soporte | $175 |
| **Pago inicial** | **$8.875** |
| Cuota mensual | $175 |
| Costo a 5 años | $19.200 |

**Financiado** — 20% del sistema al inicio y el saldo a 12% anual:

| Plazo | Inicial del sistema | Saldo financiado | Cuota de licencia | + Soporte | Cuota total | Pago inicial* | Total en el plazo | Costo a 5 años** | Interés |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 24 m | $1.500 | $6.000 | $282 | $175 | **$457** | $3.157 | $13.679 | $19.979 | $779 |
| 36 m | $1.500 | $6.000 | $199 | $175 | **$374** | $3.074 | $16.174 | $20.374 | $1.174 |
| 48 m | $1.500 | $6.000 | $158 | $175 | **$333** | $3.033 | $18.684 | $20.784 | $1.584 |

\* Pago inicial = instalación ($1.200) + 20% del sistema ($1.500) + primera cuota.
\*\* Costo a 5 años = total del plazo + los meses de soporte que faltan para 60.
Es la **única columna comparable entre filas**: al mismo horizonte el contado
($19.200) siempre gana. El “total en el plazo” es más bajo solo porque el plazo
es más corto, no porque la modalidad sea más barata.

### 4.3 Escalado por tamaño

| Tramo | Pistolas | Factor | Instalación | Sistema | Soporte/mes | Actualización mayor |
|---|---:|---:|---:|---:|---:|---:|
| Pequeña | 1–4 | 0,85× | $1.020 | $6.375 | $149 | $1.275 |
| Mediana | 5–8 | 1,00× | $1.200 | $7.500 | $175 | $1.500 |
| Grande | 9–16 | 1,30× | $1.560 | $9.750 | $228 | $1.950 |
| Extra grande | 17–24 | 1,60× | $1.920 | $12.000 | $280 | $2.400 |
| Red | 25+ | A cotizar | — | — | — | — |

### 4.4 Redes multi-estación

La licencia baja por volumen; la instalación y el soporte se cobran por estación.

| Estación | Factor de licencia |
|---|---:|
| 1.ª | 100% |
| 2.ª y 3.ª | 60% |
| 4.ª a 6.ª | 50% |
| 7.ª en adelante | 40% |

Ejemplo: 3 estaciones medianas → licencia de $7.500 × (1 + 0,6 + 0,6) =
**$16.500** (en vez de $22.500). Instalación: $3.600. Soporte: $525/mes.

### 4.5 Actualizaciones mayores (rubro 4)

| Concepto | Precio | Cuándo |
|---|---:|---|
| Versión mayor del sistema | **20% de la licencia** ($1.500 en la mediana) | Cada 3–4 años, opcional |
| Módulo nuevo (tienda, flotas, telemedición) | $2.000–$6.000 | Por proyecto |
| Cambio regulatorio (SRI, comprobantes) | Incluido en el soporte | Cuando ocurra |

### 4.6 Add-ons

| Servicio | Precio |
|---|---:|
| Capacitación adicional | $480 por 8 horas |
| Visita en sitio | $120 + viáticos |
| Isla de impresión adicional | $15/mes |
| Desarrollo a medida | $45–$60/hora |
| Migración histórica (>50.000 registros) | Cotización |

---

## 5. Cómo se fijó el precio (método)

El esquema no es “costo + margen” ni “precio de la competencia”. Cada rubro se
ancló a una referencia distinta y después el conjunto se validó con caja y
margen. Este es el método, en el orden en que se aplicó.

### 5.1 Una ancla por rubro

| Rubro | Cómo se fijó | Ancla / fórmula | Resultado |
|---|---|---|---|
| 1 · Instalación | Precio de servicio, por estación | Implementación vertical estándar = 15–30% de la licencia | $1.200 = 16% de $7.500 |
| 2 · Sistema | Precio de activo, por valor | 4,3% del margen bruto anual del cliente + comparables | $7.500 |
| 3 · Soporte | Precio recurrente, por estación/mes | Mantenimiento ERP 18–22% anual + hosting + Key49 | $112,50 + $35 + $30 = $177,50 → $175 |
| 4 · Actualización mayor | Precio opcional, por versión | Práctica de mercado (cada 3–4 años) | 20% de la licencia = $1.500 |

Regla: **ningún rubro subsidia a otro**. El soporte no paga la licencia y la
instalación no paga el soporte.

### 5.2 Rubro 2 — el número que manda (valor, no costo)

| Ancla | Cálculo | Resultado |
|---|---|---:|
| Margen bruto anual de una estación mediana | 120.000 gal/mes × $0,12 × 12 | $172.800 |
| Licencia / margen anual | $7.500 ÷ $172.800 | **4,3%** |
| SAP B1 para 3–5 usuarios | $1.400–2.700 × 4 | $5.600–10.800 |
| POS de pista internacional | Referencia de mercado | $10.000–20.000+ |

$7.500 queda **por debajo** de un POS de pista, **dentro** del rango de un ERP
para 3–5 usuarios y en **4,3%** del margen anual que ayuda a controlar. Es el
ancla más defendible en una reunión: no se compara contra otro software, se
compara contra el margen que administra.

### 5.3 Rubro 3 — se construyó de abajo hacia arriba

| Componente | Cálculo | Valor |
|---|---|---:|
| Mantenimiento de software (18% anual de la licencia) | $7.500 × 18% ÷ 12 | $112,50 |
| Hosting, respaldos y monitoreo | Estimado | $35,00 |
| Key49 hasta 3.000 facturas | Estimado | $30,00 |
| **Suma** | | **$177,50** |
| **Precio de lista** | Redondeo comercial a la baja | **$175** |

Como proporción de la licencia, $175/mes equivale a **28% anual**, por encima del
estándar de 18–22%: se justifica porque incluye hosting y Key49, que un contrato
de mantenimiento puro no cubre. Margen estimado: **43%** sobre un costo de
~$100/mes (ver §7.3).

### 5.4 Rubro 1 — por qué $1.200 y no $300

En v2 la instalación estaba en $300 (4% de la licencia), **por debajo** del
estándar de 15–30%, y señalizaba bajo valor. Se fijó en **$1.200 = 16%**, en el
borde bajo del rango.

> **Ojo con el argumento:** los $1.200 **no** cubren por sí solos la entrega
> (~$4.500). Lo que cubre la entrega es el **día 0 completo** (instalación +
> licencia + primer soporte = $8.875, que deja +$4.375 netos). El ancla de la
> instalación es el 15–30%, no el costo de entrega.

### 5.5 Cómo se validó el conjunto

| Prueba | Cálculo | Resultado |
|---|---|---:|
| Equivalente mensual del contado | $19.200 ÷ 60 | $320/mes (rango SaaS $150–500) |
| Margen bruto a 5 años | $19.200 − $6.000 soporte − $4.500 entrega | ~$8.700 (**45%**) |
| Caja el día 0 (contado) | $8.875 − $4.500 | **+$4.375** |
| Caja el día 0 (financiado 48 m) | $3.033 vs ~$4.500 | equilibrio en el mes 5 |
| Payback del contado | $8.875 ÷ $1.490/mes | ~6 meses (ver §10) |

Prueba de coherencia entre modalidades: **a 5 años el contado siempre es el más
barato** ($19.200 vs $19.979 / $20.374 / $20.784). Si una tabla mostrara lo
contrario, estaría comparando horizontes distintos (ver §4.2).

### 5.6 Qué es dato y qué es supuesto

| Dato verificable | Supuesto pendiente de validar |
|---|---|
| Toda la aritmética (cuotas, día 0, totales, márgenes) | Tarifa real de Key49 y costo del excedente |
| Precio de lista y descuentos por red | Costo de entrega “~$4.500” |
| Comparables de mercado (con fuente en §6) | Costo de soporte “~$100/mes” |
| Equivalente $320/mes a 5 años | Margen por galón $0,12 y volumen 120.000 gal/mes |

Los cuatro supuestos de la segunda columna están en los *Pendientes antes de
enviar* (§9). Ninguno cambia la estructura de rubros: cambian el margen.

---

## 6. Benchmark de mercado

> Los proveedores ecuatorianos de software para gasolineras (Menatics, Gasintec,
> Solintece, Zencillo) **no publican precios**; cotizan caso por caso. Los rangos
> de abajo son referencias internacionales y del catálogo propio.

| Referencia | Rango | Fuente |
|---|---|---|
| SaaS para gasolinera (México, 2026) | **$150–$500+ USD/estación/mes** | Swirvle |
| SAP Business One cloud | $40–$110 USD/usuario/mes | HCO |
| SAP B1 licencia perpetua | $1.400–$2.700 USD/usuario | HCO |
| Mantenimiento anual ERP | **18–22% de la licencia** | Ramo |
| Implementación ERP (empresarial) | 100–200% de la licencia | Houseblend |
| Implementación vertical estándar | 15–30% de la licencia | Práctica de mercado |
| POS de pista tipo Gilbarco/Verifone | $10.000–$20.000+ por sitio | Petrosoft 2025 |
| ERP Powerfin (catálogo propio) | $10–$120 + IVA/módulo/mes | Planes GRISBI |

**Lectura:** nuestro contado equivale a **$320/mes a 5 años**, en el cuartil
medio-bajo del SaaS de gasolineras. La ventaja no es solo el precio: es que un
solo proveedor entrega contabilidad, pista, SRI y la integración con Wayne.

### 6.1 Por qué $7.500 por el sistema

| Ancla | Cálculo | Resultado |
|---|---|---:|
| Margen bruto de la estación | 120.000 gal × $0,12 | $14.400/mes |
| Margen bruto anual | $14.400 × 12 | $172.800 |
| Licencia / margen anual | $7.500 ÷ $172.800 | **4,3%** |
| SAP B1 para 3–5 usuarios | $1.400–$2.700 × 4 | $5.600–$10.800 |
| POS de pista internacional | Referencia | $10.000–$20.000+ |

$7.500 es menos que un POS de pista internacional, está en el rango de un ERP
para 3–5 usuarios y equivale a **4,3% de un año** del margen que ayuda a
controlar.

### 6.2 Por qué $175/mes de soporte

El estándar de mantenimiento ERP es 18–22% de la licencia al año:

| Componente | Cálculo | Valor |
|---|---|---:|
| Mantenimiento de software (18%) | $7.500 × 18% ÷ 12 | $112,50 |
| Hosting, respaldos y monitoreo | Estimado | $35,00 |
| Key49 hasta 3.000 facturas | Estimado | $30,00 |
| **Total** | | **$177,50** |

$175 queda en el punto medio, con ~43% de margen sobre el costo estimado de
$100/mes.

---

## 7. Economía de la propuesta

### 7.1 Caja y margen (estación mediana, contado)

| Concepto | Valor |
|---|---:|
| Ingreso el día 0 | $8.875 |
| Costo de entrega | ~$4.500 |
| **Caja neta el día 0** | **+$4.375** |
| Ingreso a 5 años | $19.200 |
| Costo de soporte a 5 años | ~$6.000 |
| Costo de entrega | ~$4.500 |
| **Margen bruto a 5 años** | **~$8.700 (45%)** |

El día 0 cubre la implementación y deja caja. Ese es el argumento para no
regalar la licencia ni financiarla sin inicial.

### 7.2 Financiación: qué cuesta y qué exige

| Plazo | Interés total | Caja el día 0 | Punto de equilibrio de la entrega* |
|---|---:|---:|---:|
| 24 m | $779 | $3.157 | Mes 3 |
| 36 m | $1.174 | $3.074 | Mes 4 |
| 48 m | $1.584 | $3.033 | Mes 5 |

\* Día 0 + cuotas acumuladas contra el costo de entrega de ~$4.500.

El 12% anual cubre el costo de capital y el riesgo. Si el inicial baja a 10%, el
punto de equilibrio se corre al mes 5; si sube a 30%, baja al mes 2. **No
financiar con menos de 20% de inicial.**

### 7.3 El soporte como negocio recurrente

| Estación | Soporte/mes | Costo estimado | Margen | Margen % |
|---|---:|---:|---:|---:|
| Pequeña | $149 | $85 | $64 | 43% |
| Mediana | $175 | $100 | $75 | 43% |
| Grande | $228 | $130 | $98 | 43% |
| Extra grande | $280 | $160 | $120 | 43% |

El soporte debe ser rentable por sí solo. Si se usa para subsidiar la licencia,
se repite el error de v2/v3.

### 7.4 Key49 incluido: el riesgo silencioso

Key49 cobra por documento emitido. El costo unitario es bajo, pero escala con
el volumen:

| Facturas/mes | Costo estimado Key49* | % de una cuota de $175 |
|---|---:|---:|
| 1.000 | $10–$30 | 6%–17% |
| 3.000 | $30–$90 | 17%–51% |
| 6.000 | $60–$180 | 34%–103% |

\* Rango referencial; confirmar la tarifa vigente del proveedor.

**Recomendación:** incluir hasta 3.000 facturas/mes y facturar el excedente al
costo. Sin tope, una estación de alto volumen puede consumir el margen completo
del soporte.

Antes de firmar el primer contrato hay que verificar:

1. La tarifa real por factura del tenant de Key49.
2. Si el costo es por documento emitido o por documento autorizado.
3. Si las notas de crédito también se cobran.

---

## 8. Riesgos comerciales y cláusulas

| # | Riesgo | Mitigación |
|---|---|---|
| 1 | Cliente se va antes del plazo | Penalidad = saldo del sistema + cuotas restantes |
| 2 | Key49 sin tope consume el margen | Tope de 3.000 facturas/mes + excedente al costo |
| 3 | Financiar con poco inicial | Mínimo 20% del sistema; ideal 30% |
| 4 | Hardware mal dimensionado genera soporte infinito | Acta de inventario; red y hardware son responsabilidad del cliente |
| 5 | Alcance creep | Todo cambio fuera de alcance va por horas, con aprobación escrita |
| 6 | Inflación y alza de hosting | Indexación anual (IPC Ecuador) con aviso de 30 días |
| 7 | SLA 95% prometido a una gasolinera 24/7 | El SLA actual no cubre madrugada; definir guardia o aceptar la exclusión |
| 8 | Migración de datos sucia | El cliente certifica los datos migrados |
| 9 | Actualización mayor no presupuestada | Rubro 4 separado; aviso con 90 días y cotización aprobada |
| 10 | Dependencia de un proveedor fiscal | Documentar el procedimiento de reenvío y contingencia |

**Cláusulas mínimas del contrato:**

- Vigencia igual al plazo del plan, renovación automática
- Pago mensual adelantado, día 1
- Licencia: pago único o financiado con 20% de inicial; el saldo no genera
  propiedad hasta su cancelación
- Soporte: incluye hosting, respaldos, Key49 hasta 3.000 facturas/mes,
  actualizaciones menores y cambios regulatorios
- Actualizaciones mayores y módulos nuevos: cotización y aprobación escrita
- Indexación anual
- Confidencialidad y propiedad de los datos (los datos son del cliente)
- Nivel de servicio y exclusiones (SLA vigente)
- Terminación y entrega de datos en CSV/SQL
- Uso de marca del cliente solo con autorización escrita

---

## 9. Decisiones tomadas (2026-10-20)

| # | Punto | Decisión |
|---|---|---|
| 1 | Estructura | **Cuatro rubros explícitos** (instalación, sistema, soporte, actualizaciones mayores) |
| 2 | Instalación | **$1.200** (tramo mediano) |
| 3 | Sistema | **$7.500** (tramo mediano) |
| 4 | Soporte | **$175/mes** (tramo mediano) |
| 5 | Actualización mayor | **20% del sistema** ($1.500) por versión, opcional |
| 6 | Financiación | **20% de inicial + 12% anual** a 24/36/48 meses |
| 7 | Redes | Licencia: 2.ª–3.ª al 60%, 4.ª–6.ª al 50%, 7.ª+ al 40% |
| 8 | Key49 | Incluido hasta **3.000 facturas/mes**; excedente al costo |
| 9 | Plazo mínimo | **24 meses** |
| 10 | Datos legales | RUC 0190411826001 · Carlos Vintimilla 130 y Luis Moreno Mora, Cuenca · Patricio Valarezo, Gerente · validez 30 días |
| 11 | Referencias | **NeoGas y NeoGuayas** |
| 12 | Soporte | L-V 8 h, sábados y domingos 4 h; movilización 1–2 h |

### Pendientes antes de enviar

- [ ] **Confirmar la tarifa de Key49** y validar el tope de 3.000 facturas.
- [ ] **Actualizar el PDF del SLA**: hoy dice lunes a viernes 8:30–17:30 y no
      menciona fines de semana ni movilización.
- [ ] **Definir la cobertura de movilización**: "Cuenca y zona de influencia";
      confirmar el radio en km.
- [ ] **Verificar el costo real de soporte** por estación/mes antes de firmar.
- [ ] **Confirmar que NeoGas y NeoGuayas autorizan** el uso de su nombre y logo.
- [ ] **Validar los supuestos de §5.6** antes de firmar: costo de entrega, costo
      real de soporte, tarifa de Key49 y margen por galón.

---

## 10. Anexo — Cálculo de valor

Supuestos conservadores para una estación mediana:

| Variable | Valor |
|---|---:|
| Volumen mensual | 120.000 galones |
| Margen bruto por galón | $0,12 |
| Margen bruto mensual | $14.400 |
| Costo equivalente del sistema (contado, 5 años) | $320/mes (2,2% del margen) |
| Costo del sistema en el año 1 | $10.800 (6,3% del margen anual) |

| Palanca | Cálculo | Ahorro mensual |
|---|---|---:|
| Merma detectada al 0,3% | 360 gal × $3,00 | $1.080 |
| Tiempo de cuadre (2 h/día) | 60 h × $4,00 | $240 |
| Facturas recuperadas | 1 factura/semana × $20 | $80 |
| Despachos huérfanos evitados | 2/mes × $45 | $90 |
| **Total** | | **$1.490** |

**Payback del contado:** $8.875 ÷ $1.490 ≈ **6 meses**.

La frase “se paga solo con 0,05% de merma” **no se sostiene con estos mismos
números**: 0,05% de 120.000 galones son 60 galones ($180/mes) que, sumados a las
otras palancas ($410), dan $590/mes → **15 meses**. La sensibilidad real es:

| Merma detectada (% del volumen) | Galones/mes | Ahorro por merma | Ahorro total | Payback |
|---|---:|---:|---:|---:|
| 0,05% | 60 | $180 | $590 | ~15 meses |
| 0,09% | 110 | $330 | $740 | ~12 meses |
| 0,15% | 180 | $540 | $950 | ~9 meses |
| 0,30% (supuesto del anexo) | 360 | $1.080 | $1.490 | ~6 meses |

**Cifra para usar en reunión:** con **0,09% del volumen en merma** (≈110
galones/mes) el sistema se paga en **12 meses**; al supuesto pleno de 0,3%, en 6.
Ese es el argumento de cierre, no el precio.

---

## 11. Archivos

| Archivo | Uso |
|---|---|
| `ANALISIS_PRECIOS.md` | Este documento (interno) |
| `brochure.html` / `brochure.pdf` | Brochure comercial (12 páginas A4) |
| `cotizador.html` | Calculadora **parametrizable** (v5): 4 rubros, financiación, tramos, red y conceptos; exporta/importa JSON |
| `README.md` | Guía de la carpeta comercial |
