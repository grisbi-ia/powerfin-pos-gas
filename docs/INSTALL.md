# Guía de Instalación — Powerfin POS

> Debian 13 (Trixie) · Instalación directa · Sin Docker · Usuario root

---

## 1. Requisitos del VPS

```
CPU:    2+ cores
RAM:    4 GB mínimo (8 GB recomendado)
Disco:  40 GB SSD
OS:     Debian 13 (Trixie)
Red:    IP fija en LAN de la gasolinera (ej: 192.168.1.10)
```

---

## 2. Sistema base

```bash
apt update && apt upgrade -y

# Zona horaria Ecuador
timedatectl set-timezone America/Guayaquil

# Herramientas básicas
apt install -y curl wget git ufw rsync netcat-openbsd htop
```

---

## 3. PostgreSQL 16

```bash
apt install -y postgresql postgresql-client

# Configurar contraseña
su - postgres -c "psql -c \"ALTER USER postgres PASSWORD 'clave-segura-postgres';\""

# Crear bases de datos
su - postgres -c "createdb powerfin_gas"
su - postgres -c "createdb powerfin_gas_test"

# Zona horaria Ecuador
su - postgres -c "psql -c \"ALTER SYSTEM SET timezone = 'America/Guayaquil';\""
systemctl restart postgresql

# Verificar
psql -h localhost -U postgres -d powerfin_gas -c "SHOW timezone;"
# Debe mostrar: America/Guayaquil
```

---

## 4. POS Backend (Python / FastAPI)

```bash
apt install -y python3 python3-pip python3-venv python3-dev build-essential libpq-dev

# Usuario único para todos los servicios (si no existe)
id app &>/dev/null || useradd -r -m -s /bin/bash app
mkdir -p /opt/powerfin/pos/backend /opt/powerfin/pos/fusion-bridge /opt/powerfin/pos/pos
chown -R app:app /opt/powerfin/pos

# Copiar código del backend (desde repo)
cd /opt/powerfin/pos/backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Archivo .env
cat > .env << 'EOF'
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_NAME=powerfin_gas
DATABASE_USER=postgres
DATABASE_PASSWORD=clave-segura-postgres
JWT_SECRET=cambiar-por-clave-larga-y-aleatoria
JWT_EXPIRE_MINUTES=480
DEBUG=false
CORS_ORIGINS=https://pos.gasolinera.com
EOF

# Probar manualmente
source venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8080
# Ctrl+C para detener
```

### Servicio systemd

```bash
cat > /etc/systemd/system/pos-backend.service << 'EOF'
[Unit]
Description=Powerfin POS Backend — FastAPI
After=network.target postgresql.service
Wants=postgresql.service

[Service]
Type=simple
User=app
WorkingDirectory=/opt/powerfin/pos/backend
ExecStart=/opt/powerfin/pos/backend/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8080
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable pos-backend
systemctl start pos-backend
```

---

## 5. FusionBridge (Java 21 / Quarkus)

```bash
# Java 21
apt install -y openjdk-21-jdk-headless

# Verificar
java -version
# openjdk version "21.0.x"
```

### Compilar y desplegar (en máquina de desarrollo)

El VPS solo necesita el JAR compilado, no el código fuente ni Maven.

```bash
# En tu máquina de desarrollo
cd fusion-bridge
./mvnw package -DskipTests

# Copiar SOLO el JAR y dependencias al VPS
scp -r target/quarkus-app/* root@192.168.1.10:/opt/powerfin/pos/fusion-bridge/

# En el VPS
systemctl restart fusion-bridge
```

> **Importante:** No usar `rsync` del código fuente completo al VPS.
>
> Solo se necesita `target/quarkus-app/` (el JAR compilado).

### Servicio systemd

```bash
cat > /etc/systemd/system/fusion-bridge.service << 'EOF'
[Unit]
Description=Powerfin FusionBridge — Wayne Synergy TCP Bridge
After=network.target

[Service]
Type=simple
User=app
WorkingDirectory=/opt/powerfin/pos/fusion-bridge

ExecStart=/usr/bin/java \
    -Xms64m -Xmx256m \
    -jar quarkus-run.jar

Restart=always
RestartSec=10

Environment="FUSION_IP=192.168.1.20"
Environment="FUSION_PORT=3011"
Environment="POWERFIN_URL=http://localhost:8080"
Environment="PRINTER_POLICY=ASK"

StandardOutput=journal
StandardError=journal
SyslogIdentifier=fusion-bridge

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable fusion-bridge
systemctl start fusion-bridge
```

---

## 6. Powerfin POS (SvelteKit — desarrollo local)

El POS corre en modo desarrollo (`npm run dev`) directamente en el servidor.

Los dispositivos en la LAN acceden vía `http://<IP-DEL-SERVIDOR>:5173`.

```bash
# Node.js 22 (desde NodeSource para Debian 13)
curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
apt install -y nodejs

cd /opt/powerfin/pos/pos
npm install

# El servicio systemd arranca con --host 0.0.0.0 para aceptar
# conexiones desde cualquier IP de la LAN.
cat > /etc/systemd/system/pos-frontend.service << 'EOF'
[Unit]
Description=Powerfin POS Frontend
After=network.target

[Service]
Type=simple
User=app
WorkingDirectory=/opt/powerfin/pos/pos
ExecStart=/usr/bin/npm run dev -- --host 0.0.0.0 --port 5173
Restart=always
RestartSec=5

StandardOutput=journal
StandardError=journal
SyslogIdentifier=pos-frontend

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable pos-frontend
systemctl start pos-frontend
```

---

## 6b. Powerfin Admin (SvelteKit — desarrollo local)

El Admin corre en modo desarrollo (`npm run dev`) en el puerto 5174.

```bash
cd /opt/powerfin/pos/admin
npm install

cat > /etc/systemd/system/admin-frontend.service << 'EOF'
[Unit]
Description=Powerfin Admin Frontend
After=network.target

[Service]
Type=simple
User=app
WorkingDirectory=/opt/powerfin/pos/admin
ExecStart=/usr/bin/npm run dev -- --host 0.0.0.0 --port 5174
Restart=always
RestartSec=5

StandardOutput=journal
StandardError=journal
SyslogIdentifier=admin-frontend

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable admin-frontend
systemctl start admin-frontend
```

---

## 7. Archivos de configuración

Antes de arrancar los servicios, completar los siguientes archivos.

### POS Backend — `/opt/powerfin/pos/backend/.env`

```bash
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_NAME=powerfin_gas
DATABASE_USER=postgres
DATABASE_PASSWORD=<CONTRASEÑA-DE-POSTGRES>
JWT_SECRET=<GENERAR-CLAVE-LARGA-Y-ALEATORIA>
JWT_EXPIRE_MINUTES=480
```

> Generar JWT_SECRET: `openssl rand -hex 32`

### POS Backend — `/opt/powerfin/pos/backend/app/config.py`

Verificar que `database_password` y `jwt_secret` estén vacíos o

sobreescritos por el `.env`. No dejar valores por defecto en código.

### POS Frontend — `/opt/powerfin/pos/pos/.env`

```bash
VITE_USE_MOCKS_POWERFIN=false
VITE_USE_MOCKS_BRIDGE=false
```

### FusionBridge — systemd service

Las variables de entorno se configuran en el archivo de servicio

(`/etc/systemd/system/fusion-bridge.service`):

```ini
Environment="FUSION_IP=192.168.1.20"    # IP del Wayne Synergy
Environment="FUSION_PORT=3011"           # Puerto TCP del Wayne
Environment="POWERFIN_URL=http://localhost:8080"
Environment="PRINTER_POLICY=ASK"        # ALWAYS | ASK | NEVER
```

### FusionBridge — `/opt/powerfin/pos/fusion-bridge/src/main/resources/application.properties`

Las propiedades vienen dentro del JAR compilado. Las variables de entorno

del systemd service las sobreescriben automáticamente. No se crea ningún

archivo de configuración en el VPS.

```properties
# Estos son los defaults dentro del JAR:
fusion.ip=${FUSION_IP}
fusion.port=${FUSION_PORT}
powerfin.url=${POWERFIN_URL}
printer.policy=${PRINTER_POLICY:ASK}
```

---

## 8. Firewall — acceso restringido a la LAN

El POS, backend y FusionBridge solo deben ser accesibles desde

la red local de la gasolinera. Nada desde el exterior.

```bash
apt install -y ufw

# Política por defecto: denegar todo lo entrante
ufw default deny incoming
ufw default allow outgoing

# SSH — permitido desde cualquier IP (incluye Tailscale 100.x.y.z)
# Tailscale ya provee cifrado y autenticación, no se necesita filtrar por IP.
ufw allow 22

# POS Frontend (:5173) — solo LAN
ufw allow from 192.168.1.0/24 to any port 5173

# Admin Frontend (:5174) — solo LAN
ufw allow from 192.168.1.0/24 to any port 5174

# POS Backend (:8080) — solo LAN
ufw allow from 192.168.1.0/24 to any port 8080

# FusionBridge (:8090) — solo LAN
ufw allow from 192.168.1.0/24 to any port 8090

# Activar
ufw enable

# Verificar
ufw status verbose
```

**Nota:** Si se requiere acceso solo desde IPs específicas de los

dispositivos de despachadores (más seguro que toda la subnet):

```bash
# Reemplazar las reglas de subnet por IPs individuales:
ufw allow from 192.168.1.31 to any port 5173
ufw allow from 192.168.1.32 to any port 5173
ufw deny 5173   # bloquea a cualquier otra IP
```

---

## 9. Base de datos — schema y datos iniciales

### 9.1 Ejecutar migraciones Alembic (crea todas las tablas)

```bash
cd /opt/powerfin/pos/backend
source venv/bin/activate
alembic upgrade head
```

Esto crea las 26 tablas con todas las columnas acumuladas:

`preset_value`, `sri_code`, `sort_order`, `allow_container_sale`, etc.

### 9.2 Cargar datos semilla (seed_data.py)

El script `seed_data.py` inserta TODOS los datos de referencia necesarios:

```bash
cd /opt/powerfin/pos/backend
source venv/bin/activate
python seed_data.py
```

**Lo que inserta:**


| Tabla                | Contenido                                                            |
| -------------------- | -------------------------------------------------------------------- |
| `system_config`      | 3 configs base (branch_code, currency, invoice_footer)               |
| `company_info`       | NEOGAS S.A. (ajustar RUC/datos antes de producción)                  |
| `roles`              | ADMIN, SUPERVISOR, DISPATCHER                                        |
| `users`              | admin, carlos, maria, pedro (PIN: 1234)                              |
| `tax_types`          | IVA_12, IVA_0, ICE                                                   |
| `product_categories` | FUEL, OIL, ADDITIVE, AMBIENTAL                                       |
| `products`           | DIESEL, SUPER, ECO_PAIS, ACEITE_20W50, ADITIVO_MOTOR, AMBIENTAL_PINO |
| `grades`             | DIESEL, SUPER, ECO_PAIS                                              |
| `price_lists`        | STANDARD, VIP, EMPLOYEE, FAMILY                                      |
| `price_list_items`   | Precios por lista y producto                                         |
| `persons`            | 3 personas (1 CED + 2 RUC)                                           |
| `vehicles`           | 3 vehículos (ABC1234, XYZ5678, XYZ5679)                              |
| `payment_methods`    | 8 métodos con sri_code (EFECTIVO=01, TARJETA=19, resto=20)           |
| `emission_points`    | 001-001, FACTURA, secuencial desde 1                                 |
| `dispensers`         | 4 surtidores (SURT-01 a SURT-04) con printer_ip                      |
| `hoses`              | 10 mangueras (8 lados A/B × 4 dispensers, 2 bi-producto)             |
| `dispatch_types`     | SALE, CREDIT, CALIBRATION, TEST                                      |
| `credit_contracts`   | CT-2026-001 (INDEFINIDO, $5,000 cupo, Transportes Andinos)           |


### 9.3 Ajustar datos para producción

Después de seed_data.py, ajustar los datos reales del cliente:

```bash
psql -h localhost -U postgres -d powerfin_gas << 'SQL'
-- Datos reales de la empresa
UPDATE company_info SET
  ruc = '<RUC-REAL>',
  name = '<RAZON-SOCIAL>',
  commercial_name = '<NOMBRE-COMERCIAL>',
  address = '<DIRECCION>',
  phone = '<TELEFONO>',
  email = '<EMAIL>',
  city = '<CIUDAD>',
  province = '<PROVINCIA>',
  sri_environment = 2   -- 1=PRUEBAS, 2=PRODUCCION
WHERE company_id = 1;

-- Configuraciones adicionales
INSERT INTO system_config (key, value, description) VALUES
  ('printer_policy', 'ASK', 'ALWAYS, ASK, or NEVER'),
  ('max_cash_in_hand', '300.00', 'Límite máximo de efectivo en bolsillo (USD)'),
  ('cash_printer_ip', '192.168.1.21', 'IP de impresora para comprobantes de caja'),
  ('cash_printer_port', '9100', 'Puerto de impresora para comprobantes de caja'),
  ('key49_api_key', '', 'Key49 API key (k49_...)'),
  ('key49_base_url', 'https://key49.apx5.com/v1', 'Key49 API base URL'),
  ('key49_enabled', 'false', 'Enable automatic SRI invoicing via Key49')
ON CONFLICT (key) DO NOTHING;

-- IPs de impresoras (ajustar a las reales)
UPDATE dispensers SET printer_ip = '192.168.1.21', printer_port = 9100;
SQL
```

### 9.4 Verificar

```bash
cd /opt/powerfin/pos/backend
source venv/bin/activate
pytest
```

---

## 10. Verificación final

```bash
# Health checks
curl -s http://localhost:8080/health
curl -s http://localhost:8090/health
curl -s http://localhost:5173
curl -s http://localhost:5174

# Servicios
systemctl status pos-backend
systemctl status fusion-bridge
systemctl status pos-frontend
systemctl status admin-frontend
systemctl status postgresql

# Logs
journalctl -u pos-backend -f
journalctl -u fusion-bridge -f
```

---

## 11. Comandos útiles

```bash
# Reiniciar todo
systemctl restart pos-backend fusion-bridge pos-frontend admin-frontend

# Logs en vivo
journalctl -u pos-backend -u fusion-bridge -u pos-frontend -u admin-frontend -f

# Conectividad con dispensador Wayne
echo -n "00012|5|2||ECHO||||^" | nc -v 192.168.1.20 3011

# Conectividad con impresora
nc -zv 192.168.1.21 9100

# Backup de BD
pg_dump -U postgres powerfin_gas > backup_$(date +%Y%m%d).sql
```

### Desplegar actualizaciones

**FusionBridge** (compilar en dev, copiar JAR al VPS):

```bash
cd fusion-bridge && ./mvnw package -DskipTests
scp -r target/quarkus-app/* app@192.168.1.25:/opt/powerfin/pos/fusion-bridge/
ssh app@192.168.1.25 sudo systemctl restart fusion-bridge
```

**POS Backend** (solo código Python, se reinicia solo con systemd):

```bash
rsync -av pos_backend/app/ app@192.168.1.25:/opt/powerfin/pos/backend/app/
ssh app@192.168.1.25 sudo systemctl restart pos-backend
```

**POS Frontend** (SvelteKit, modo dev):

```bash
rsync -av pos/src/ app@192.168.1.25:/opt/powerfin/pos/pos/src/
ssh app@192.168.1.25 sudo systemctl restart pos-frontend
```

**Admin Frontend** (SvelteKit, modo dev):

```bash
./scripts/deploy-to-server.sh admin
ssh app@192.168.1.25 "cd /opt/powerfin/pos/admin && npm install && powerfin-gas deploy-admin"
```

---

## 12. Estructura de directorios

```
/opt/powerfin/pos/
├── backend/                  # Python FastAPI
│   ├── venv/
│   ├── .env
│   └── app/
├── fusion-bridge/            # Java Quarkus
│   └── quarkus-app/
├── pos/                      # SvelteKit Frontend (POS)
│   └── src/
├── admin/                    # SvelteKit Frontend (Admin)
│   ├── node_modules/
│   └── src/

/etc/systemd/system/
├── pos-backend.service
├── fusion-bridge.service
├── pos-frontend.service
└── admin-frontend.service
```

---

## 13. Nginx + HTTPS — PWA instalable en fullscreen

Sin HTTPS, el POS se abre como bookmark (con barra de URL).

Con HTTPS, Chrome/iOS permiten instalar la PWA como app nativa:

ícono en el home, fullscreen, sin barra del navegador.

Como es una red local sin dominio público, usamos un **certificado**

**auto-firmado** (gratuito, 365 días de validez).

### Instalar Nginx

```bash
apt install -y nginx
mkdir -p /etc/nginx/ssl
```

### Generar certificado auto-firmado

```bash
# Ajustar 192.168.1.10 a la IP real del servidor
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout /etc/nginx/ssl/pos-key.pem \
  -out /etc/nginx/ssl/pos-cert.pem \
  -subj "/CN=192.168.1.10"

chmod 600 /etc/nginx/ssl/pos-key.pem
chmod 644 /etc/nginx/ssl/pos-cert.pem
```

### Configurar Nginx como proxy inverso

Nginx recibe HTTPS en :443 y enruta al POS (:5173), Admin (:5174), backend (:8080)

y FusionBridge (:8090). Todo pasa por un solo puerto.

```bash
cat > /etc/nginx/sites-available/powerfin-pos << 'EOF'
server {
    listen 443 ssl;
    ssl_certificate     /etc/nginx/ssl/pos-cert.pem;
    ssl_certificate_key /etc/nginx/ssl/pos-key.pem;

    # IP whitelist — solo LAN de la gasolinera
    allow 192.168.1.0/24;
    deny all;

    # POS Frontend (SvelteKit dev server con HMR y SSE)
    location / {
        proxy_pass http://127.0.0.1:5173;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 3600s;
    }
}
EOF

ln -sf /etc/nginx/sites-available/powerfin-pos /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl enable nginx
systemctl reload nginx
```

### Actualizar firewall

Con Nginx, todo el tráfico entra por :443. Cerrar los puertos directos:

```bash
ufw delete allow from 192.168.1.0/24 to any port 5173
ufw delete allow from 192.168.1.0/24 to any port 5174
ufw delete allow from 192.168.1.0/24 to any port 8080
ufw delete allow from 192.168.1.0/24 to any port 8090
ufw allow from 192.168.1.0/24 to any port 443
```

> **Tailscale:** SSH está abierto para cualquier IP (`ufw allow 22`),
>
> lo que cubre tanto la LAN (`192.168.1.x`) como Tailscale (`100.x.y.z`).
>
> El resto de puertos (5173, 8080, 8090, 443) siguen restringidos a la LAN.

### Instalar la PWA en el celular/tablet

```
1. Abrir https://192.168.1.10 en Chrome
2. Chrome advierte "Conexión no segura" → "Avanzado" → "Continuar a 192.168.1.10"
   (solo la primera vez — certificado auto-firmado)
3. Aparece banner: "Instalar Powerfin GAS"  ← automático
   o tocar ⋮ → "Agregar a pantalla de inicio"
4. Ícono en el home → abre FULLSCREEN, sin barra de navegador ✅
```

> En **iPhone/Safari:** Abrir `https://192.168.1.10` → ⬆ Compartir →
>
> "Agregar a la pantalla de inicio".

**Nota:** Si no necesitás PWA fullscreen, podés usar el acceso directo

sin Nginx vía `http://192.168.1.10:5173` (modo desarrollo).

---

## Opcional: Nginx + Let's Encrypt (dominio real)

Si se requiere HTTPS, un nombre de dominio amigable, o servir el POS

como archivos estáticos compilados en vez de `npm run dev`, instalar

Nginx como proxy inverso:

```bash
apt install -y nginx certbot python3-certbot-nginx
```

### POS compilado (estáticos)

```bash
# En máquina de desarrollo
cd pos
npm install
npm run build
rsync -av --delete build/ root@VPS:/var/www/pos/

# En el VPS
mkdir -p /var/www/pos
chown -R root:www-data /var/www/pos
```

### Configuración Nginx

```bash
cat > /etc/nginx/sites-available/powerfin-pos << 'EOF'
server {
    listen 443 ssl;
    server_name pos.gasolinera.com;

    ssl_certificate     /etc/letsencrypt/live/pos.gasolinera.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/pos.gasolinera.com/privkey.pem;

    # IP whitelist — solo dispositivos de la LAN
    allow 192.168.1.0/24;
    deny all;

    # Powerfin POS — estáticos
    location / {
        root /var/www/pos;
        try_files $uri $uri/ /index.html;
    }

    # Admin Frontend — proxy al dev server
    location /admin {
        proxy_pass http://127.0.0.1:5174;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # POS Backend API (POS + Admin)
    location /api/ {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 30s;
    }

    # FusionBridge — REST + SSE
    location /bridge/ {
        proxy_pass http://127.0.0.1:8090/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header Connection '';
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 3600s;
        chunked_transfer_encoding on;
    }
}

server {
    listen 80;
    server_name pos.gasolinera.com;
    return 301 https://$host$request_uri;
}
EOF

ln -sf /etc/nginx/sites-available/powerfin-pos /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl enable nginx
systemctl reload nginx

# SSL con Let's Encrypt (requiere dominio público y DNS apuntando al servidor)
certbot --nginx -d pos.gasolinera.com
```

Con Nginx, el acceso cambia a:

```
https://pos.gasolinera.com    ← nombre de dominio local
```

**Nota:** Con Nginx activo, cerrar los puertos directos en ufw y solo

dejar 443:

```bash
ufw delete allow from 192.168.1.0/24 to any port 5173
ufw delete allow from 192.168.1.0/24 to any port 5174
ufw delete allow from 192.168.1.0/24 to any port 8080
ufw delete allow from 192.168.1.0/24 to any port 8090
ufw allow from 192.168.1.0/24 to any port 443
```

