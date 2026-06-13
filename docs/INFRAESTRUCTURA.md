# Infraestructura y Seguridad

## Stack del servidor en GASOLINERA

```
Hardware recomendado:
  CPU:   Intel Core i5 o superior
  RAM:   16 GB mínimo
  Disco: SSD 256 GB
  UPS:   OBLIGATORIO (protege PowerFin y FusionBridge ante cortes)
  OS:    Debian 12 (Bookworm) — instalación directa, sin Docker

Procesos corriendo como servicios systemd:
  ├── postgresql        → BD de PowerFin (ya instalado)
  ├── powerfin          → ERP Java 8 (ya instalado)
  ├── fusion-bridge     → nuevo — Java 21, puerto 8090
  └── nginx             → nuevo — sirve Powerfin POS + proxy inverso
```

---

## Por qué instalación directa (sin Docker)

```
FusionBridge necesita acceso TCP directo a la red local (192.168.1.20:3011).
Con Docker bridge network esto requiere configuración extra de routing.
Con instalación directa, FusionBridge usa la LAN del servidor sin fricción.

Además, PowerFin ya funciona con instalación directa.
Mantener el mismo modelo simplifica la operación y el mantenimiento.
```

---

## Topología de red

```
RED LOCAL GASOLINERA (192.168.1.0/24)

Servidor          192.168.1.10   (IP fija)
Wayne Synergy     192.168.1.20   (IP fija)
Impresora Isla 1  192.168.1.31   (IP fija)
Impresora Isla 2  192.168.1.32   (IP fija — si aplica)
Gateway/Router    192.168.1.1

Celulares/Tablets despachadores → IP dinámica via DHCP
  Acceden via HTTPS: https://pos.gasolinera.com
  Nginx resuelve internamente a los servicios locales
```

---

## Instalación inicial en Debian 12

### Paso 1 — Java 21 con SDKMAN

```bash
# SDKMAN permite tener múltiples versiones de Java sin conflictos
# PowerFin usa Java 8, FusionBridge usa Java 21 — coexisten sin problema

curl -s "https://get.sdkman.io" | bash
source ~/.sdkman/bin/sdkman-init.sh

sdk install java 21.0.3-tem

# Verificar
java -version
# openjdk version "21.0.3" 2024-04-16
```

### Paso 2 — Node.js 20 (solo para build del Powerfin POS)

```bash
# Solo para compilar el frontend — no corre en producción
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs
```

### Paso 3 — Nginx

```bash
sudo apt-get install -y nginx
sudo systemctl enable nginx
sudo systemctl start nginx
```

### Paso 4 — SSL con Certbot

```bash
sudo apt-get install -y certbot python3-certbot-nginx
sudo certbot --nginx -d pos.gasolinera.com
# Certbot renueva automáticamente — no requiere intervención manual
```

### Paso 5 — Usuario y directorios del sistema

```bash
# Usuario sin shell para correr FusionBridge
sudo useradd -r -s /bin/false powerfin-pos
sudo mkdir -p /opt/powerfin/pos/fusion-bridge
sudo chown powerfin-pos:powerfin-pos /opt/powerfin/pos/fusion-bridge

# Directorio para Powerfin POS estáticos
sudo mkdir -p /var/www/pos
sudo chown $USER:www-data /var/www/pos
sudo chmod 755 /var/www/pos
```

---

## Configuración de Nginx

```nginx
# /etc/nginx/sites-available/powerfin-pos

server {
    listen 443 ssl;
    server_name pos.gasolinera.com;

    ssl_certificate     /etc/letsencrypt/live/pos.gasolinera.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/pos.gasolinera.com/privkey.pem;

    # Powerfin POS — archivos estáticos SvelteKit
    location / {
        root /var/www/pos;
        try_files $uri $uri/ /index.html;
        add_header Cache-Control "public, max-age=3600";
    }

    # FusionBridge — REST y SSE
    location /bridge/ {
        proxy_pass          http://localhost:8090/;
        proxy_http_version  1.1;
        proxy_set_header    Host $host;
        proxy_set_header    X-Real-IP $remote_addr;

        # Crítico para SSE — sin buffering
        proxy_set_header    Connection '';
        proxy_buffering     off;
        proxy_cache         off;
        proxy_read_timeout  3600s;
        chunked_transfer_encoding on;
    }

    # PowerFin API — proxy inverso
    location /api/ {
        proxy_pass          http://localhost:8080/api/;
        proxy_http_version  1.1;
        proxy_set_header    Host $host;
        proxy_set_header    X-Real-IP $remote_addr;
        proxy_read_timeout  30s;
    }
}

# Redirigir HTTP → HTTPS
server {
    listen 80;
    server_name pos.gasolinera.com;
    return 301 https://$host$request_uri;
}
```

```bash
# Activar la configuración
sudo ln -s /etc/nginx/sites-available/powerfin-pos /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

---

## Servicio systemd para FusionBridge

```ini
# /etc/systemd/system/fusion-bridge.service

[Unit]
Description=PowerFin FusionBridge — Wayne Synergy TCP Bridge
After=network.target
Wants=network.target

[Service]
Type=simple
User=powerfin-pos
WorkingDirectory=/opt/powerfin/pos/fusion-bridge

ExecStart=/usr/bin/java \
    -Xms64m -Xmx256m \
    -jar quarkus-run.jar

# Reiniciar automáticamente si falla
Restart=always
RestartSec=10
StartLimitIntervalSec=60
StartLimitBurst=5

# Variables de entorno de conexión
Environment="FUSION_IP=192.168.1.20"
Environment="FUSION_PORT=3011"
Environment="POWERFIN_URL=http://localhost:8080"

# Impresión
Environment="PRINTER_POLICY=ASK"

StandardOutput=journal
StandardError=journal
SyslogIdentifier=fusion-bridge

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable fusion-bridge
sudo systemctl start fusion-bridge
sudo systemctl status fusion-bridge
```

---

## Script de deploy

```bash
#!/bin/bash
# deploy.sh — actualización del sistema Powerfin POS
# Uso: ./deploy.sh [fusion-bridge|pos|all]

set -e

COMPONENT=${1:-all}
PROJECT_DIR="/home/patricio/powerfin-pos"

deploy_fusion_bridge() {
    echo ""
    echo "=== Actualizando FusionBridge ==="
    cd "$PROJECT_DIR/fusion-bridge"

    echo "→ Ejecutando tests..."
    ./mvnw test

    echo "→ Compilando..."
    ./mvnw package -DskipTests

    echo "→ Deteniendo servicio..."
    sudo systemctl stop fusion-bridge

    echo "→ Copiando binarios..."
    sudo cp -r target/quarkus-app/* /opt/powerfin/pos/fusion-bridge/

    echo "→ Iniciando servicio..."
    sudo systemctl start fusion-bridge

    sleep 3
    if sudo systemctl is-active --quiet fusion-bridge; then
        echo "✅ FusionBridge activo"
    else
        echo "❌ Error al iniciar FusionBridge"
        sudo journalctl -u fusion-bridge -n 20
        exit 1
    fi
}

deploy_pos() {
    echo ""
    echo "=== Actualizando Powerfin POS ==="
    cd "$PROJECT_DIR/pos"

    echo "→ Ejecutando tests..."
    npm run test:ci

    echo "→ Verificando tipos TypeScript..."
    npm run check

    echo "→ Compilando..."
    npm run build

    echo "→ Desplegando estáticos..."
    sudo rsync -av --delete build/ /var/www/pos/

    echo "→ Recargando Nginx..."
    sudo systemctl reload nginx

    echo "✅ Powerfin POS desplegado"
}

case $COMPONENT in
    fusion-bridge) deploy_fusion_bridge ;;
    pos)      deploy_pos ;;
    all)
        deploy_fusion_bridge
        deploy_pos
        echo ""
        echo "=== Deploy completado ✅ ==="
        ;;
    *)
        echo "Uso: ./deploy.sh [fusion-bridge|pos|all]"
        exit 1
        ;;
esac
```

```bash
chmod +x deploy.sh
```

---

## Comandos de operación diaria

```bash
# ── FusionBridge ──────────────────────────────────────
sudo systemctl status fusion-bridge      # estado
sudo journalctl -u fusion-bridge -f      # logs en tiempo real
sudo journalctl -u fusion-bridge -n 50   # últimas 50 líneas
sudo systemctl restart fusion-bridge     # reiniciar

# ── Nginx ─────────────────────────────────────────────
sudo nginx -t                            # verificar config
sudo systemctl reload nginx              # recargar sin cortar conexiones
sudo tail -f /var/log/nginx/error.log    # logs de errores

# ── Verificaciones de conectividad ────────────────────
echo -n "00012|5|2||ECHO||||^" | nc -v 192.168.1.20 3011   # test Synergy
nc -zv 192.168.1.31 9100 && echo "Impresora isla 1 OK"     # test impresora

# ── Health check ──────────────────────────────────────
curl -s http://localhost:8090/health | python3 -m json.tool
```

---

## Seguridad

### Autenticación

```
Despachador → Powerfin POS:    JWT (usuario + PIN, 8 horas)
FusionBridge → PowerFin:   Header X-Bridge-Key (API key de sistema)
FusionBridge → Synergy:    TCP directo LAN (sin cifrado — red privada)
FusionBridge → Impresoras: TCP socket LAN puerto 9100
```

### Firewall con ufw

```bash
sudo apt-get install -y ufw
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
# Puertos 8080 (PowerFin) y 8090 (FusionBridge) NO expuestos
# Solo accesibles via Nginx en localhost
sudo ufw enable
```

---

## Resiliencia

```
Si FusionBridge cae:
  systemd reinicia en 10 segundos (Restart=always)
  Al reconectar, RecoveryService recupera ventas perdidas
  Powerfin POS reconecta SSE automáticamente (nativo del browser)

Si el servidor se reinicia:
  Todos los servicios tienen systemctl enable
  Arrancan automáticamente en orden correcto (After= en .service)

Si se va la energía:
  UPS mantiene el servidor durante el corte
  Al volver: todos los servicios arrancan solos
  El Synergy también debe tener su propio UPS
```
