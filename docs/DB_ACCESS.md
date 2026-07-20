# Acceso a base de datos — PROD

## Datos de conexión

| Campo | Valor |
|---|---|
| Puerto | `5432` |
| Base de datos | `powerfin_gas` |
| Usuario | `agent_llm` |
| Contraseña | `AgentLLM123` |
| Permisos | Lectura + Escritura |

### IPs del servidor

| IP | Vía | Cuándo usarla |
|---|---|---|
| `100.97.47.123` | Tailscale | **Principal** — siempre disponible, dentro o fuera de oficina |
| `192.168.1.25` | LAN local | Respaldo — solo desde la red de la oficina |

## Conectarse

```bash
# Principal (Tailscale — funciona desde cualquier lado)
PGPASSWORD=AgentLLM123 psql -h 100.97.47.123 -p 5432 -U agent_llm -d powerfin_gas

# Respaldo (LAN — solo desde la oficina)
PGPASSWORD=AgentLLM123 psql -h 192.168.1.25 -p 5432 -U agent_llm -d powerfin_gas
```

## Ejecutar un script SQL

```bash
PGPASSWORD=AgentLLM123 psql -h 100.97.47.123 -p 5432 -U agent_llm -d powerfin_gas -f script.sql
```

## Ejecutar una query directa

```bash
PGPASSWORD=AgentLLM123 psql -h 100.97.47.123 -p 5432 -U agent_llm -d powerfin_gas -c "SELECT * FROM shifts ORDER BY shift_id DESC LIMIT 5;"
```

## ⚠️ Precaución

Esta es la base de datos de **producción**. Cualquier INSERT/UPDATE/DELETE debe ser validado por el usuario antes de ejecutarse. Siempre usar `SELECT` primero para verificar los datos afectados.
