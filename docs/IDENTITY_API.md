# API de Consulta de Personas — Sercobaco / SRI

## Propósito

Servicio externo de consulta de datos de personas naturales (cédula) y jurídicas (RUC)
para el registro automático de clientes en el POS Backend. Evita la digitación manual
de nombres, direcciones y otros datos.

---

## Endpoints

### 1. Consulta por Cédula (Sercobaco)

```
GET http://131.161.221.131:2356/v1/info/ALL/sercobaco/{cedula}
Authorization: Bearer {token}
```

**Ejemplo:** `GET /v1/info/ALL/sercobaco/1103875439`

**Respuesta (campos relevantes):**

```json
{
  "httpStatus": "OK",
  "successful": true,
  "personId": "1103875439",
  "brokerId": "sercobaco",
  "data": {
    "d_datos": {
      "d_cedula": "1103875439",
      "d_nombre": "VALAREZO OREJUELA PATRICIO DANIEL",
      "d_fecnac": "31/1/1981",
      "d_sexo": "MASCULINO",
      "d_domicilio": "LOJA/LOJA/VALLE",
      "d_estadocivil": "CASADO-A",
      "d_profesion": "ESTUDIANTE",
      "d_nacionalidad": "ECUATORIANA"
    },
    "d_emails": [
      {
        "email": "patriciovalarezo@gmail.com||andreinachaguayczs5@gmail.com"
      }
    ],
    "d_telefonos": [
      {
        "telefono": "0993832368||072587794"
      }
    ]
  }
}
```

**Mapeo a campos del POS:**

| Campo API | Campo POS | Extractor |
|---|---|---|
| `data.d_datos.d_nombre` | `name` | directo |
| `data.d_datos.d_cedula` | `id_number` | directo |
| `data.d_datos.d_domicilio` | `address` | directo |
| `data.d_emails[0].email` | `email` | split por `\|\|`, tomar el primero |
| `data.d_telefonos[0].telefono` | `phone` | split por `\|\|`, tomar el primero |
| `id_type` siempre | `"CED"` | — |

### 2. Consulta por RUC (SRI)

```
GET http://131.161.221.131:2356/v1/info/ALL/sri/{ruc}
Authorization: Bearer {token}
```

**Ejemplo:** `GET /v1/info/ALL/sri/0190411826001`

**Respuesta (campos relevantes):**

```json
{
  "httpStatus": "OK",
  "successful": true,
  "personId": "0190411826001",
  "brokerId": "sri",
  "data": {
    "ruc": "0190411826001",
    "contribuyente": {
      "numeroRuc": "0190411826001",
      "razonSocial": "INGENIERIA DE SISTEMAS GRISBI CIA. LTDA.",
      "estadoContribuyenteRuc": "ACTIVO",
      "tipoContribuyente": "SOCIEDAD",
      "regimen": "GENERAL",
      "obligadoLlevarContabilidad": "SI",
      "agenteRetencion": "SI",
      "contribuyenteEspecial": "NO"
    },
    "establecimientos": [
      {
        "nombreFantasiaComercial": null,
        "tipoEstablecimiento": "MAT",
        "direccionCompleta": "AZUAY / CUENCA / TOTORACOCHA / GUAGRAHUMA 20 Y AV. GUAPONDELIG",
        "estado": "ABIERTO",
        "numeroEstablecimiento": "001",
        "matriz": "SI"
      }
    ]
  }
}
```

**Mapeo a campos del POS:**

| Campo API | Campo POS |
|---|---|
| `data.contribuyente.razonSocial` | `name` |
| `data.contribuyente.numeroRuc` | `id_number` |
| `data.establecimientos[0].direccionCompleta` | `address` |
| `data.contribuyente.tipoContribuyente` | (no se almacena) |
| `id_type` siempre | `"RUC"` |

---

## Reglas de extracción

| Campo | Regla |
|---|---|
| **Nombre** | CED: `d_datos.d_nombre`. RUC: `contribuyente.razonSocial` |
| **Dirección** | CED: `d_datos.d_domicilio`. RUC: primer establecimiento (`establecimientos[0].direccionCompleta`) |
| **Email** | CED: `d_emails[0].email`, split por `\|\|`, tomar el primero. RUC: no disponible |
| **Teléfono** | CED: `d_telefonos[0].telefono`, split por `\|\|`, tomar el primero. RUC: no disponible |

---

## Credenciales

```
URL base:  http://131.161.221.131:2356
Token JWT: eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJnYXMiLCJ1c2VySWQiOjUsImVtYWlsIjoiZ2FzQGRhdGFnby5jb20iLCJmdWxsTmFtZSI6IlBvd2VyZmluIFBPUyBHQVMgSW50ZWdyYXRpb24iLCJyb2xlcyI6WyJBUElfQ0xJRU5UIl0sImlhdCI6MTc4MDQyODI3OSwiZXhwIjoxODExOTY0Mjc5fQ.fYSb--was6n089W-CCZUzY2vSL7qYKt1VUq_eiaYLtA

Expiracion: 2027-06-01 (approx 1 año)
```

## Tiempos de respuesta

| Endpoint | Tiempo |
|---|---|
| Sercobaco (cédula) | ~565ms (cache) |
| SRI (RUC) | ~2800ms (consulta en vivo) |

---

## Pruebas realizadas

| Fecha | Tipo | ID | Resultado |
|---|---|---|---|
| 2026-06-02 | CED | 1103875439 | ✅ OK — VALAREZO OREJUELA PATRICIO DANIEL |
| 2026-06-02 | RUC | 0190411826001 | ✅ OK — INGENIERIA DE SISTEMAS GRISBI CIA. LTDA. |

---

## Fecha: 2026-06-02 | Versión: 1.0
