# Cloudflare Tunnel — Exponer Admin a internet

> **Objetivo**: Exponer Powerfin Admin a internet vía Cloudflare Tunnel sin exponer
> el POS ni abrir puertos en el firewall del servidor.

```
Última actualización: 2026-06-23
Dominio: neoguayas-paute.apx5.com
Túnel:  admin-neoguayas (UUID: 56028a77-e9ed-46f1-abbc-713ea49bb163)
```

---

## 1. Arquitectura

```
Internet                    Cloudflare Edge          Servidor Debian (neoguayas2)
───────                    ────────────────          ─────────────────────────────
Navegador                  cloudflared tunnel        Vite dev server
  │                        (QUIC/H2)                   │
  │  https://neoguayas-    ┌──────────┐               │ :5174
  ├── paute.apx5.com ─────┤ Cloudflare├───────────────┤ Admin (SPA)
  │                        └──────────┘               │
  │                         │                         │ :8080
  │                         │ WAF + DDoS              ├── Backend API
  │                         │                         │
  │                         │                         │ :5173
  │                         │                         ├── POS (NO expuesto)
  │                         │                         │ :8090
  │                         │                         └── FusionBridge (NO expuesto)
```

**El POS y FusionBridge NO se exponen** — solo el Admin. El túnel crea una
conexión saliente desde el servidor hacia Cloudflare, sin abrir puertos entrantes.

---

## 2. Requisitos previos

- [x] Cuenta Cloudflare con dominio configurado (`apx5.com`)
- [x] Admin funcionando en `localhost:5174`
- [x] Backend funcionando en `localhost:8080`
- [x] Servidor Debian 12 con acceso a internet

---

## 3. Instalación de cloudflared

```bash
# Descargar e instalar cloudflared
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb \
  -o /tmp/cloudflared.deb
sudo dpkg -i /tmp/cloudflared.deb

# Verificar
cloudflared --version
```

---

## 4. Autenticar y crear el túnel

```bash
# 4.1 Autenticar con cuenta Cloudflare
cloudflared tunnel login
# → Abre URL en navegador, inicia sesión, selecciona el dominio apx5.com
# → El certificado se guarda en ~/.cloudflared/cert.pem

# 4.2 Crear túnel
cloudflared tunnel create admin-neoguayas
# → Genera UUID y archivo .json en ~/.cloudflared/<UUID>.json

# 4.3 Anotar el UUID
cloudflared tunnel list
```

---

## 5. Configurar DNS en Cloudflare

En Cloudflare Dashboard → **DNS** → **Records** → **Add record**:

| Campo | Valor |
|-------|-------|
| Type | `CNAME` |
| Name | `neoguayas-paute` |
| Target | `56028a77-e9ed-46f1-abbc-713ea49bb163.cfargotunnel.com` |
| Proxy | ✅ Proxied (nube naranja) |
| TTL | Auto |

> Reemplaza el UUID por el valor real de `cloudflared tunnel list`.

---

## 6. Configurar archivo del túnel

```bash
sudo mkdir -p /etc/cloudflared

sudo tee /etc/cloudflared/config.yml << 'EOF'
tunnel: 56028a77-e9ed-46f1-abbc-713ea49bb163
credentials-file: /home/app/.cloudflared/56028a77-e9ed-46f1-abbc-713ea49bb163.json

ingress:
  - hostname: neoguayas-paute.apx5.com
    service: http://localhost:5174
  - service: http_status:404
EOF
```

> **Importante**: El `service` apunta directo a `localhost:5174` (Vite dev server del admin).
> No se necesita Nginx. El proxy `/api` ya lo maneja Vite internamente.

---

## 7. Instalar como servicio systemd

```bash
sudo cloudflared service install
sudo systemctl enable cloudflared
sudo systemctl start cloudflared
sudo systemctl status cloudflared
```

Verificar que aparezca `active (running)` y que los prechecks pasen:

```
✅ DNS Resolution
✅ UDP Connectivity (QUIC)
✅ TCP Connectivity (HTTP/2)
✅ Cloudflare API
```

---

## 8. Configurar allowedHosts en Vite

Sin esto, Vite rechaza peticiones con el dominio de Cloudflare.

### 8.1 Editar `vite.config.ts`

```bash
sudo nano /opt/powerfin/pos/admin/vite.config.ts
```

Agregar `allowedHosts` en el bloque `server`:

```ts
server: {
    allowedHosts: ['neoguayas-paute.apx5.com', 'localhost', '127.0.0.1', '192.168.1.25'],
    proxy: {
      '/api': 'http://localhost:8080'
    }
}
```

### 8.2 Reiniciar admin

```bash
sudo systemctl restart admin-frontend
```

---

## 9. Verificación

```bash
# 1. Túnel activo
sudo systemctl status cloudflared | grep -E "active|precheck"

# 2. Admin responde localmente
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:5174/
# → 200

# 3. Admin accesible desde internet (esperar ~30s propagación DNS)
curl -s -o /dev/null -w "%{http_code}\n" https://neoguayas-paute.apx5.com/
# → 200
```

Abrir en navegador: `https://neoguayas-paute.apx5.com/`

---

## 10. Troubleshooting

### Error 1016 — Origin DNS error

El registro CNAME no existe en Cloudflare DNS. Verificar paso 5.

### "Blocked request. This host is not allowed"

Falta `allowedHosts` en `vite.config.ts`. Ver paso 8.

### Página en blanco con error JS

Posibles causas:

1. **Caché del navegador**: Limpiar con Ctrl+Shift+R o probar en incógnito.
2. **Brave Shields**: Desactivar Shields (ícono 🦁 en barra de direcciones).
3. **Caché Vite corrupto**:
   ```bash
   sudo systemctl stop admin-frontend
   sudo rm -rf /opt/powerfin/pos/admin/node_modules/.vite
   sudo rm -rf /opt/powerfin/pos/admin/.svelte-kit
   sudo chown -R app:app /opt/powerfin/pos/admin
   sudo systemctl start admin-frontend
   ```

### Túnel no conecta

```bash
# Ver logs
sudo journalctl -u cloudflared -f

# Reiniciar
sudo systemctl restart cloudflared
```

---

## 11. Consideraciones de seguridad

| Capa | Protección |
|------|-----------|
| Cloudflare Edge | DDoS, WAF, SSL/TLS automático |
| Túnel cloudflared | Conexión saliente, sin puertos abiertos |
| Auth admin | JWT 4h, username + password, role-based |
| POS / FusionBridge | NO expuestos — solo accesibles por LAN |

### Rate limiting (pendiente)

Para proteger el endpoint de login contra fuerza bruta, opciones:

- **Backend**: slowapi + FastAPI (limitar intentos/min por IP)
- **Cloudflare WAF**: regla de rate limiting en dashboard
- **Nginx**: `limit_req_zone` si se instala Nginx en el futuro

---

## 12. Comandos rápidos

```bash
# Status de todo
powerfin-gas status

# Ver logs del túnel
sudo journalctl -u cloudflared -n 50

# Reiniciar túnel
sudo systemctl restart cloudflared

# Ver configuración activa
cat /etc/cloudflared/config.yml
cloudflared tunnel list
```
