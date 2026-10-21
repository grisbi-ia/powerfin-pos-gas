# Material comercial — Powerfin ERP + POS GAS

Carpeta con los entregables de la propuesta comercial.

| Archivo | Qué es | Para quién |
|---|---|---|
| `ANALISIS_PRECIOS.md` | Análisis interno: estructura de precios, benchmark, márgenes, riesgos y decisiones | **Interno** — no enviar |
| `brochure.html` | Fuente editable del brochure (12 páginas A4) | Interno / diseño |
| `brochure.pdf` | Brochure listo para enviar | Cliente |
| `cotizador.html` | Calculadora **parametrizable**: 4 rubros, financiación, tramos, red y conceptos adicionales | Interno / reunión con cliente |
| `hoja-reunion.html` / `hoja-reunion.pdf` | Resumen de **1 página A4**: 4 rubros, 4 modalidades con costo a 5 años, tramos, servicios y contacto | Cliente / reunión |
| `GUION_REUNION.md` / `GUION_REUNION.pdf` | Guión completo de la reunión (45 min): recorrido, **bloque de precios**, objeciones y resguardos | **Interno** — no enviar |
| `guion-bolsillo.html` / `guion-bolsillo.pdf` | **Una carilla A4** con los 5 pasos del precio, las 6 objeciones, los números y el cierre | **Interno** — para tener en la mano |
| `build-guion.py` / `guion-print.css` | Script y estilo para regenerar el PDF del guión desde el Markdown | Interno |
| `assets/` | Logos GRISBI, NeoGas y NeoGuayas | — |
| `assets/admin/` | Capturas del Admin (`admin_dashboard.png` es la usada en la p.7) | Interno |

## Regenerar la hoja de reunión

```bash
cd comercial
weasyprint hoja-reunion.html hoja-reunion.pdf
pdfinfo hoja-reunion.pdf | grep Pages   # debe decir 1
```

Es el resumen que se lleva impreso: cuatro rubros, las cuatro modalidades con
costo a 5 años, tramos por pistolas, servicios opcionales, qué incluye y el
contacto. **Tiene que caber en una sola página**: si se agrega contenido y salen
dos, recortar texto antes de imprimir. El contacto y la vigencia salen del
brochure (p.12); no hay datos del cliente impresos, se llenan a mano.

## Guión de la reunión

`GUION_REUNION.md` es la fuente (se edita ahí). Orden: apertura con preguntas
(5'), recorrido del brochure (10'), **precios (15')**, objeciones (10') y cierre
(5'). Incluye las frases textuales, las cifras de bolsillo y los resguardos para
SLA, Key49 y movilización. No se envía al cliente.

```bash
cd comercial
python3 build-guion.py                    # GUION_REUNION.md → GUION_REUNION.pdf
weasyprint guion-bolsillo.html guion-bolsillo.pdf   # carilla de bolsillo
pdfinfo GUION_REUNION.pdf | grep Pages    # hoy: 5
pdfinfo guion-bolsillo.pdf | grep Pages   # debe decir 1
```

`build-guion.py` usa pandoc para convertir el Markdown e inyecta `guion-print.css`
(encabezado, tipografía, tablas y casillas ☐). La **versión de bolsillo** es un
HTML aparte, de una sola página: no duplicar contenido ahí sin quitarlo del
guión completo.

## Regenerar el PDF

```bash
cd comercial
weasyprint brochure.html brochure.pdf
```

El PDF sale en A4, 12 páginas. Verificar:

```bash
pdfinfo brochure.pdf | grep Pages   # debe decir 12
```

**Diseño optimizado para impresión (2026-10-21):** la portada, la página 12 y
las bandas de énfasis usan fondo blanco o gris muy claro con acento rojo. No hay
fondos negros a página completa: se puede imprimir en láser sin agotar el
tóner. Si se cambia el diseño, verificar que no vuelvan los fondos oscuros y
que las páginas sigan siendo 12.

## Abrir el cotizador

```bash
xdg-open comercial/cotizador.html
```

Archivo autónomo (HTML + JS, sin servidor ni dependencias). **Imprimir / PDF**
usa el diálogo del navegador; **Copiar resumen** deja el texto listo para
WhatsApp o correo.

### Qué se puede cambiar (v5 · parametrizable)

Los valores por defecto son exactamente la lista v4.1, así que al abrirlo la
cotización sale idéntica al brochure. En **Parámetros de cálculo** se edita:

| Bloque | Variables |
|---|---|
| Rubros de lista | Instalación, sistema, soporte mensual, % de actualización mayor |
| Financiación | % inicial, tasa anual, plazos disponibles (meses) |
| Redes e islas | Islas incluidas por estación, costo de isla adicional |
| Tramos por pistolas | Nombre, límite y factor de cada tramo (se pueden añadir o borrar) |
| Descuento por red | Desde/hasta estación y factor de licencia |
| Conceptos adicionales | Catálogo con nombre, precio y tipo (único o mensual) |

Cada cambio recalcula al instante el desglose, la comparación de las cuatro
modalidades y el “cálculo paso a paso” (interno, no se imprime).

### Seguridad de los cambios

- **Persistencia:** los parámetros y la cotización se guardan en el navegador
  (`localStorage`). Al reabrir el archivo sigue donde quedó.
- **Exportar / Importar JSON:** un archivo por prospecto, para archivar o pasar
  la cotización a otra máquina. El JSON incluye parámetros + datos del cliente.
- **Restablecer lista v4.1:** vuelve a los valores oficiales.
- **Aviso visible:** si algún parámetro difiere de la lista, aparece
  “parámetros modificados” en el resumen y en el texto copiado.
- **Sin fallbacks silenciosos:** con un dato inválido (por ejemplo soporte
  vacío) no calcula: muestra la lista de errores y deja los importes en “—”.

> Si un cambio de parámetros se adopta como precio oficial, hay que reflejarlo en
> `ANALISIS_PRECIOS.md`, `brochure.html` (p.10), el PDF y este README.

## Modelo de precios vigente (v4.1, 2026-10-20)

### Los cuatro rubros (tramo mediano)

| # | Rubro | Tipo | Valor |
|---|---|---|---:|
| 1 | Instalación, implementación y capacitación | Único | $1.200 |
| 2 | Precio del sistema (ERP + POS + Admin) | Único o financiado | $7.500 |
| 3 | Soporte mensual y actualizaciones menores | Mensual | $175 |
| 4 | Actualizaciones mayores | Único, opcional | 20% del sistema ($1.500) |

### Contado

| Concepto | Valor |
|---|---:|
| Instalación | $1.200 |
| Sistema | $7.500 |
| Primer mes de soporte | $175 |
| **Pago inicial** | **$8.875** |
| Cuota mensual | $175 |
| Costo a 5 años | $19.200 |

### Financiado (20% del sistema + 12% anual)

| Plazo | Pago inicial | Cuota mensual | Total en el plazo | Costo a 5 años | Interés |
|---|---:|---:|---:|---:|---:|
| 24 meses | $3.157 | $457 | $13.679 | $19.979 | $779 |
| 36 meses | $3.074 | $374 | $16.174 | $20.374 | $1.174 |
| 48 meses | $3.033 | $333 | $18.684 | $20.784 | $1.584 |

**Costo a 5 años** lleva cada modalidad a 60 meses de soporte y es la única
columna comparable entre filas: el contado ($19.200) siempre es el más barato.
El “total en el plazo” es menor solo porque el plazo es más corto.

### Escalado por pistolas

| Tramo | Pistolas | Factor | Instalación | Sistema | Soporte/mes |
|---|---|---:|---:|---:|---:|
| Pequeña | 1–4 | 0,85× | $1.020 | $6.375 | $149 |
| Mediana | 5–8 | 1,00× | $1.200 | $7.500 | $175 |
| Grande | 9–16 | 1,30× | $1.560 | $9.750 | $228 |
| Extra grande | 17–24 | 1,60× | $1.920 | $12.000 | $280 |
| Red | 25+ | A cotizar | — | — | — |

### Redes multi-estación

La licencia baja por volumen; instalación y soporte se cobran por estación.

| Estación | Licencia |
|---|---:|
| 1.ª | 100% |
| 2.ª y 3.ª | 60% |
| 4.ª a 6.ª | 50% |
| 7.ª en adelante | 40% |

### Reglas adicionales

| Concepto | Regla |
|---|---|
| Actualización mayor | 20% del sistema por versión, opcional |
| Módulo nuevo | $2.000–$6.000 por proyecto |
| Cambio regulatorio SRI | Incluido en el soporte |
| Key49 | Incluido hasta 3.000 facturas/mes; excedente al costo |
| Capacitación adicional | $480 por 8 horas |
| Visita en sitio | $120 + viáticos |
| Isla adicional | $15/mes |

### Método (cómo se fijó cada rubro)

Cada rubro tiene su propia ancla; ninguno subsidia a otro. Detalle en
`ANALISIS_PRECIOS.md` §5.

| Rubro | Ancla | Resultado |
|---|---|---|
| Instalación | Implementación vertical estándar = 15–30% de la licencia | $1.200 = 16% de $7.500 |
| Sistema | 4,3% del margen bruto anual del cliente + comparables SAP B1 / POS de pista | $7.500 |
| Soporte | Mantenimiento ERP 18–22% anual + hosting + Key49 | $112,50 + $35 + $30 = $177,50 → **$175** |
| Actualización mayor | Práctica de mercado, cada 3–4 años | 20% de la licencia = $1.500 |

Validación del conjunto: $320/mes equivalentes a 5 años, margen bruto ~45% y
caja neta de +$4.375 el día 0 del contado.

### Jerarquía de la oferta

1. **Contado:** caja inmediata y menor costo total.
2. **Financiado con 20% de inicial:** accesible, con interés del 12% anual.
3. **Nunca** financiar sin inicial: el día 0 debe cubrir la instalación y parte
   del sistema.

> Ver `ANALISIS_PRECIOS.md` §4 (estructura), §6 (benchmark) y §7 (márgenes y caja).

## Estado al 2026-10-20

### Listo

- [x] Brochure A4 de 12 páginas, con portada, problema, arquitectura,
      módulos ERP, flujo del despachador, capacidades POS, Admin, hardware,
      SLA, planes, implementación y cierre.
- [x] Estructura de precios v4: cuatro rubros explícitos (instalación $1.200,
      sistema $7.500, soporte $175/mes, actualización mayor 20% del sistema).
- [x] Escalado por pistolas y descuento de licencia por red.
- [x] Cotizador HTML con las cuatro formas de pago (contado y financiado 24/36/48).
- [x] Análisis interno con benchmark, márgenes, caja y justificación de cada rubro.
- [x] Datos legales y referencias (NeoGas, NeoGuayas) en el brochure.
- [x] Logos de clientes limpios en `assets/`.

### Correcciones 2026-10-21 — guión en PDF y versión de bolsillo

- [x] **`GUION_REUNION.pdf`** (5 páginas A4) generado desde el Markdown con
      `build-guion.py` (pandoc + weasyprint) y `guion-print.css`: tablas, casillas
      ☐, encabezado rojo, pie con “uso interno” y numeración.
- [x] **`guion-bolsillo.pdf`** (1 página A4): los 5 pasos del precio con las
      frases textuales, las 6 objeciones, la tabla de números, el cierre, lo que
      no se dice y los resguardos (SLA, Key49, plazos).

### Correcciones 2026-10-21 — brochure en tono claro para impresión

- [x] **Portada sin fondo negro:** pasó del degradado oscuro a blanco con barra
      roja superior, panel gris muy claro para los 4 puntos y banda gris para
      las cifras. Consumo de tinta de la página: **97% → 3,8%** de píxeles
      oscuros.
- [x] **Página 12 sin tarjeta negra:** el bloque de contacto ahora es gris muy
      claro con borde superior rojo (**24,9% → 1,9%**).
- [x] **9 bandas de énfasis** convertidas de fondo negro a gris claro con regla
      roja izquierda (ej. p.2: **7,3% → 1,3%**).
- [x] **PDF regenerado:** 12 páginas, p.1/p.2/p.10/p.12 verificadas visualmente.

### Correcciones 2026-10-20 — v5 (cotizador parametrizable)

- [x] **Panel “Parámetros de cálculo”** con todos los valores editables: rubros,
      % inicial, tasa, plazos, islas, tramos por pistolas, descuento de red y
      catálogo de conceptos adicionales (añadir/borrar filas).
- [x] **Persistencia en `localStorage`** + **Exportar/Importar JSON** por
      prospecto + **Restablecer lista v4.1**.
- [x] **Aviso “parámetros modificados”** en el resumen y en el texto copiado,
      para no enviar una cotización alterada creyendo que es la oficial.
- [x] **Validación visible:** no calcula con parámetros inválidos; muestra los
      errores y deja los importes en “—”.
- [x] **Comparación de las 4 modalidades** en una tabla y **“cálculo paso a
      paso”** (interno, oculto al imprimir).
- [x] **Datos del cliente** (nombre, fecha, referencia) que salen impresos; la
      fecha usa la zona local (no UTC).
- [x] **Sin dependencias:** sigue siendo un HTML autónomo.

### Correcciones 2026-10-20 — v4.1 (método y horizonte)

- [x] **Método documentado:** nueva **§5** del análisis con el ancla de cada
      rubro (instalación 15–30% de la licencia, sistema 4,3% del margen anual,
      soporte 18–22% + hosting + Key49) y la separación dato/supuesto.
- [x] **Tabla de pago a horizonte equiparable:** nueva columna **Costo a 5 años**
      en brochure p.10, análisis §4.2, cotizador y este README. Antes la fila
      “Contado” mostraba 5 años ($19.200) y las financiadas solo su plazo, lo
      que hacía parecer más barato financiar.
- [x] **Payback corregido:** “0,05% de merma” daba 15 meses, no 6. La cifra
      correcta para pagar en 12 meses es **0,09% del volumen** (~110 gal/mes);
      con el supuesto pleno de 0,3% son 6 meses.
- [x] **Cotizador:** agrega “Costo a 5 años (comparación)”, cambia “costo
      promedio del contrato” por **costo promedio a 5 años / mes** ($320 contado
      vs $333/$340/$346 financiado) y muestra el tope de Key49, las 2 islas
      incluidas por estación y el costo de la isla adicional.
- [x] **Precisión de capacidades (§2.2):** “pago mixto” se marca como disponible
      en el API (la UI de pista envía un solo medio) y el destrabe `PAUSED` como
      comando `REAUTH` con botón en UI pendiente.
- [x] **“5 países” → “26 empresas”** en el análisis, alineado con el brochure.
- [x] **PDF regenerado:** 12 páginas A4, página 10 verificada sin desbordes.

### Correcciones 2026-10-20 — v4 (cuatro rubros)

- [x] **Se eliminaron “Total lista” y “Anticipo”.** La página 10 ahora muestra
      los cuatro rubros por separado: instalación $1.200, sistema $7.500,
      soporte $175/mes y actualización mayor 20% del sistema.
- [x] **Instalación subió de $300 a $1.200:** $300 era 4% de la licencia, por
      debajo del estándar de implementación (15–30%); $1.200 = 16%. No cubre por
      sí sola la entrega (~$4.500): la cubre el día 0 completo.
- [x] **Financiación:** 20% del sistema al inicio + saldo a 12% anual.
      Contado: $8.875 el día 0 y $175/mes. Financiado 24/36/48: $457/$374/$333
      por mes, con totales de $13.679/$16.174/$18.684.
- [x] **Redes:** licencia con descuento por volumen (2.ª–3.ª al 60%,
      4.ª–6.ª al 50%, 7.ª+ al 40%); instalación y soporte por estación.
- [x] **Actualizaciones mayores:** 20% del sistema por versión, opcionales;
      los cambios regulatorios del SRI quedan dentro del soporte.
- [x] **Cotizador reescrito** para calcular los 4 rubros y la financiación.
- [x] **ANALISIS v4.0** con benchmark de mercado, márgenes, caja y payback.
- [x] **PDF regenerado:** 12 páginas A4 (verificado).

### Correcciones 2026-10-20 — v3 (superada por v4)

- [x] **Se restauró el anticipo de $7.500** como modalidad principal. La v2 lo
      había eliminado y el primer pago quedó en $850, que no cubre la
      implementación.
- [x] **Descuento por anticipo:** −10% en 24/36 meses y **−5% en 48** (el plan
      de 48 m no tiene margen para un descuento mayor).
- [x] **Descuento por contado:** −15% en 24/36 meses y **−8% en 48**.
- [x] **Pago anual:** bajó de 2 meses gratis a **1 mes gratis** para que no
      compita con el contado (16,7% > 15% rompía la jerarquía).
- [x] **Brochure p.10:** se agregó la tabla del anticipo y se reemplazó el
      “pago inicial” de las tarjetas por “con anticipo $7.500”.
- [x] **Cotizador:** nueva forma de pago **Anticipo $7.500**, filas de anticipo
      y saldo financiado, y descuentos por plazo (15/15/8 y 10/10/5).
- [x] **ANALISIS v3.0:** nueva §3 (por qué se había bajado el pago inicial y
      cuánto costó diferir la caja), §4 con las tres modalidades y §6 (numeración
      de entonces) con la justificación numérica de cada descuento.
- [x] **PDF regenerado:** 12 páginas A4 (verificado).

### Correcciones 2026-10-19

- [x] **Cotizador, 25+ pistolas:** ya no aplica 1,60× ni muestra un monto;
      ahora muestra **"A cotizar"** en cuota, contrato y desglose, coherente con
      la tabla del brochure.
- [x] **Cotizador, etiqueta del pago inicial:** cuando se marcan servicios
      opcionales dice "Pago inicial" (no "Instalación"), porque incluye
      capacitación y visita.
- [x] **Brochure p.10:** el descuento por red ahora dice "hasta 20%" en vez de
      una mención sin cifras.
- [x] **ANALISIS:** se corrigió el "tope de 1,60×" → 25+ se cotiza a medida.
- [x] **Conteo de pruebas:** **696** (548 backend + 71 FusionBridge + 77 POS),
      actualizado en brochure, ANALISIS y AGENTS.md.
- [x] **PDF regenerado:** 12 páginas A4, sin desbordes (verificado visualmente).
- [x] **Página 4:** el texto de posicionamiento del ERP ahora dice "implantado
      en 26 empresas a nivel nacional e internacional" (antes "cinco países").
- [x] **Página 7 (Admin):** se incorporó una captura real del Dashboard
      (`assets/admin/admin_dashboard.png`) en lugar de la tabla "Reportes que ya
      vienen incluidos" (esa información ya estaba en la tarjeta *Reportes*).
      Se retiró además la banda final, que repetía el mensaje de la primera.
      La captura va centrada con pie de foto y tiene redactado el nombre del
      usuario; se conserva "GASOLINERA XXX".
- [x] **Página 7: versión móvil.** Se añadió `admin_dashboard_movil.png` junto
      a la de escritorio (ambas a 78 mm de alto, misma línea de base, ~280 ppi)
      para comunicar que el Admin se usa igual desde computador y desde celular.
      También se redactó el nombre del usuario en la captura móvil.
- [x] **Página 12:** "Powerfin se implanta hoy en 26 empresas a nivel nacional e
      internacional" (antes "cinco países"), alineado con la página 4.
- [x] **Página 10: pago inicial explícito.** Cada plan muestra ahora
      **Pago inicial** = instalación ($300) + primera cuota: $850 / $650 / $550.
      Se eliminó la frase "Sin desembolso inicial relevante", que contradecía
      el cobro de la instalación. El intro aclara que a mayor plazo baja la
      cuota y también el pago inicial.
- [x] **Cotizador alineado:** nueva fila **Pago inicial** (cargos únicos +
      primera cuota; con pago anual equivale a 10 meses, con pago total al
      contrato con 10% de descuento). "Pago único inicial" pasó a llamarse
      "Cargos únicos" para no confundirlo con el desembolso real.
- [x] **README y ANALISIS:** columna **Pago inicial** en las tablas de planes.

### Pendiente de decidir

- [x] **Validar el esquema de precios.** Adoptado en v4: cuatro rubros con
      instalación $1.200, sistema $7.500, soporte $175/mes y actualización mayor
      al 20% del sistema.
- [ ] **Tope de Key49.** Hoy figura "incluido hasta 3.000 facturas/mes";
      confirmar la tarifa real y el costo del excedente.
- [ ] **Actualizar el PDF del SLA.** El SLA vigente (L-V 8:30–17:30, sin fines
      de semana ni movilización) no coincide con lo que promete el brochure.
- [ ] **Radio de movilización.** El brochure dice "Cuenca y zona de
      influencia". Confirmar el radio en km o el criterio.
- [ ] **Autorización de NeoGas y NeoGuayas** para usar nombre y logo.
- [ ] **Costo real de soporte** por estación/mes, para validar el margen del
      43% estimado en el análisis.

### Próxima sesión (orden sugerido)

1. Revisar el PDF completo (p. 1–9, 11–12) y anotar cambios de texto; la p. 10
   ya está verificada con la columna “Costo a 5 años”.
2. Resolver los seis pendientes de arriba y validar los supuestos del método
   (`ANALISIS_PRECIOS.md` §5.6).
3. Probar el cotizador con 2–3 prospectos reales (pistolas y estaciones).
4. Si hay que enviar a un cliente específico, personalizar la página 12.

## Checklist de envío

1. Regenerar el PDF y confirmar 12 páginas (`pdfinfo brochure.pdf | grep Pages`).
2. Revisar que la página 12 tenga el contacto correcto del destinatario.
3. Abrir el PDF y verificar que ningún texto quede cortado al pie de página.
4. Adjuntar el cotizador lleno con el número de pistolas del prospecto.
5. Guardar una copia del PDF enviado con la fecha en el nombre.
