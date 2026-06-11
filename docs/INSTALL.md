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
apt install -y curl wget git ufw nginx certbot python3-certbot-nginx rsync netcat-openbsd
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
mkdir -p /opt/powerfin/pos/backend /opt/powerfin/pos/fusion-bridge /var/lib/powerfin/pos
chown -R app:app /opt/powerfin/pos /var/lib/powerfin/pos

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

# Directorio de datos (ya creado en sección 4)
chmod 755 /var/lib/powerfin/pos
```

### Compilar (en máquina de desarrollo)

```bash
cd fusion-bridge
./mvnw package -DskipTests
# Copiar al VPS:
scp -r target/quarkus-app/* root@VPS:/opt/powerfin/pos/fusion-bridge/
```

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
Environment="POWERFIN_API_KEY="
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

## 6. Powerfin POS (SvelteKit — estáticos)

```bash
# Node.js 22 (desde NodeSource para Debian 13)
curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
apt install -y nodejs

# Directorio web
mkdir -p /var/www/pos
chown -R root:www-data /var/www/pos
```

### Compilar (en máquina de desarrollo)

```bash
cd pos
npm install
npm run build
# Copiar al VPS:
rsync -av --delete build/ root@VPS:/var/www/pos/
```

---

## 7. Nginx

```bash
cat > /etc/nginx/sites-available/powerfin-pos << 'EOF'
server {
    listen 443 ssl;
    server_name pos.gasolinera.com;

    ssl_certificate     /etc/letsencrypt/live/pos.gasolinera.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/pos.gasolinera.com/privkey.pem;

    # Powerfin POS — estáticos
    location / {
        root /var/www/pos;
        try_files $uri $uri/ /index.html;
    }

    # POS Backend API
    location /api/pos/ {
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

# SSL
certbot --nginx -d pos.gasolinera.com
```

---

## 8. Firewall

```bash
apt install -y ufw
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow 80/tcp
ufw allow 443/tcp
ufw enable
```

---

## 9. Base de datos — schema y datos iniciales

### Crear tablas (desde el backend)

```bash
cd /opt/powerfin/pos/backend
source venv/bin/activate
python3 -c "
from app.database import engine, Base
import asyncio
async def init():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
asyncio.run(init())
"
```

### Seed — system_config

```bash
psql -h localhost -U postgres -d powerfin_gas << 'SQL'
INSERT INTO system_config (key, value, description) VALUES
  ('accounting_branch_code', '001', 'Código de sucursal contable'),
  ('default_currency', 'USD', 'Moneda por defecto'),
  ('invoice_footer_message', 'Gracias por su compra', 'Mensaje pie de factura'),
  ('printer_policy', 'ASK', 'ALWAYS, ASK, or NEVER'),
  ('max_cash_in_hand', '300.00', 'Límite máximo de efectivo en bolsillo (USD)'),
  ('cash_printer_ip', '192.168.1.21', 'IP de impresora para comprobantes de caja'),
  ('cash_printer_port', '9100', 'Puerto de impresora para comprobantes de caja'),
  ('key49_api_key', '', 'Key49 API key (k49_...)'),
  ('key49_base_url', 'https://key49.apx5.com/v1', 'Key49 API base URL'),
  ('key49_enabled', 'false', 'Enable automatic SRI invoicing via Key49')
ON CONFLICT (key) DO NOTHING;
SQL
```

### Seed — company_info

```bash
psql -h localhost -U postgres -d powerfin_gas << 'SQL'
INSERT INTO company_info (ruc, name, commercial_name, address, phone, email,
  city, province, country, fiscal_regime, sri_environment, emission_type, is_active)
VALUES (
  '1103875439001', 'PATRICIO VALAREZO', 'NEOGAS',
  'Av. Principal 123, Cuenca', '072345678', 'info@neogas.com',
  'PAUTE', 'AZUAY', 'ECUADOR',
  'OBLIGADO A LLEVAR CONTABILIDAD', 1, 1, true
)
ON CONFLICT DO NOTHING;
SQL
```

### Seed — impresoras (dispensers)

```bash
psql -h localhost -U postgres -d powerfin_gas << 'SQL'
UPDATE dispensers SET printer_ip = '192.168.1.21', printer_port = 9100;
SQL
```

---

## 10. Verificación final

```bash
# Health checks
curl -s http://localhost:8080/health
curl -s http://localhost:8090/health
curl -s https://pos.gasolinera.com

# Servicios
systemctl status pos-backend
systemctl status fusion-bridge
systemctl status nginx
systemctl status postgresql

# Logs
journalctl -u pos-backend -f
journalctl -u fusion-bridge -f
```

---

## 11. Comandos útiles

```bash
# Reiniciar todo
systemctl restart pos-backend fusion-bridge nginx

# Logs en vivo
journalctl -u pos-backend -u fusion-bridge -f

# Conectividad con dispensador Wayne
echo -n "00012|5|2||ECHO||||^" | nc -v 192.168.1.20 3011

# Conectividad con impresora
nc -zv 192.168.1.21 9100

# Backup de BD
pg_dump -U postgres powerfin_gas > backup_$(date +%Y%m%d).sql
```

---

## 12. Estructura de directorios

```
/opt/powerfin/pos/
├── backend/                  # Python FastAPI
│   ├── venv/
│   ├── .env
│   └── app/
└── fusion-bridge/            # Java Quarkus
    └── quarkus-app/

/var/lib/powerfin/pos/        # Datos persistentes
├── pending_sales.json
└── receipt-template.txt

/var/www/pos/                 # POS estáticos (SvelteKit)
├── index.html
└── _app/

/etc/systemd/system/
├── pos-backend.service
└── fusion-bridge.service

/etc/nginx/sites-available/
└── powerfin-pos
```
