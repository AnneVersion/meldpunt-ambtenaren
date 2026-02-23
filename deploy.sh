#!/bin/bash
# ==============================================
# Meldpunt Ambtenaren — Debian VPS Deploy Script
# ==============================================
#
# Dit script installeert alles op een schone Debian VPS:
#   - PostgreSQL
#   - Python 3 + venv
#   - Nginx
#   - Flask applicatie als systemd service
#   - (Optioneel) Let's Encrypt SSL
#
# Gebruik:
#   sudo bash deploy.sh --domain meldpunt.example.nl --admin-pass 'jouw_wachtwoord'
#
# Of interactief:
#   sudo bash deploy.sh
#

set -e

# ============ CONFIGURATIE ============
APP_DIR="/opt/meldpunt"
APP_USER="meldpunt"
DB_NAME="meldpunt"
DB_USER="meldpunt"
DB_PASS="$(openssl rand -hex 16)"
SECRET_KEY="$(openssl rand -hex 32)"
DOMAIN=""
ADMIN_USER="admin"
ADMIN_PASS=""

# Parse argumenten
while [[ $# -gt 0 ]]; do
    case $1 in
        --domain) DOMAIN="$2"; shift 2 ;;
        --admin-pass) ADMIN_PASS="$2"; shift 2 ;;
        --admin-user) ADMIN_USER="$2"; shift 2 ;;
        --db-pass) DB_PASS="$2"; shift 2 ;;
        *) echo "Onbekend argument: $1"; exit 1 ;;
    esac
done

# Interactieve vragen als niet meegegeven
if [ -z "$DOMAIN" ]; then
    read -p "Domeinnaam (of IP-adres): " DOMAIN
fi
if [ -z "$ADMIN_PASS" ]; then
    read -s -p "Admin wachtwoord: " ADMIN_PASS
    echo
fi

echo "================================================"
echo "  Meldpunt Ambtenaren — Installatie"
echo "================================================"
echo "  Domein:     $DOMAIN"
echo "  App dir:    $APP_DIR"
echo "  DB:         $DB_NAME"
echo "  Admin user: $ADMIN_USER"
echo "================================================"
echo ""

# ============ 1. SYSTEEM UPDATEN ============
echo "[1/8] Systeem updaten..."
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip postgresql postgresql-contrib nginx certbot python3-certbot-nginx curl > /dev/null

# ============ 2. SYSTEEMGEBRUIKER AANMAKEN ============
echo "[2/8] Systeemgebruiker '$APP_USER' aanmaken..."
if ! id -u "$APP_USER" > /dev/null 2>&1; then
    useradd --system --shell /bin/false --home "$APP_DIR" "$APP_USER"
fi

# ============ 3. POSTGRESQL DATABASE ============
echo "[3/8] PostgreSQL database aanmaken..."
sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='$DB_USER'" | grep -q 1 || \
    sudo -u postgres psql -c "CREATE USER $DB_USER WITH PASSWORD '$DB_PASS';"
sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'" | grep -q 1 || \
    sudo -u postgres createdb -O "$DB_USER" "$DB_NAME"
echo "  Database '$DB_NAME' klaar"

# ============ 4. APPLICATIE INSTALLEREN ============
echo "[4/8] Applicatie installeren in $APP_DIR..."
mkdir -p "$APP_DIR"/{backend,frontend}

# Kopieer bestanden (gaat ervan uit dat deploy.sh vanuit project root draait)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cp "$SCRIPT_DIR/index.html" "$APP_DIR/frontend/"
cp -r "$SCRIPT_DIR/backend/"* "$APP_DIR/backend/"

# Python virtual environment
cd "$APP_DIR/backend"
python3 -m venv venv
source venv/bin/activate
pip install --quiet -r requirements.txt
deactivate

# Environment bestand
cat > "$APP_DIR/.env" << ENVEOF
MELDPUNT_SECRET_KEY=$SECRET_KEY
MELDPUNT_DB_HOST=localhost
MELDPUNT_DB_PORT=5432
MELDPUNT_DB_NAME=$DB_NAME
MELDPUNT_DB_USER=$DB_USER
MELDPUNT_DB_PASS=$DB_PASS
MELDPUNT_ADMIN_USER=$ADMIN_USER
MELDPUNT_ADMIN_PASS=$ADMIN_PASS
MELDPUNT_HTTPS=false
DATABASE_URL=postgresql://$DB_USER:$DB_PASS@localhost:5432/$DB_NAME
ENVEOF
chmod 600 "$APP_DIR/.env"

# Eigenaar zetten
chown -R "$APP_USER:$APP_USER" "$APP_DIR"

echo "  Applicatie geinstalleerd"

# ============ 5. DATABASE MIGRATIE ============
echo "[5/8] Database migratie uitvoeren..."
cd "$APP_DIR/backend"
sudo -u "$APP_USER" bash -c "
    set -a; source $APP_DIR/.env; set +a;
    cd $APP_DIR/backend;
    venv/bin/python migrate.py
"
echo "  Database gemigreerd"

# ============ 6. SYSTEMD SERVICE ============
echo "[6/8] Systemd service aanmaken..."
cat > /etc/systemd/system/meldpunt.service << SVCEOF
[Unit]
Description=Meldpunt Ambtenaren Flask API
After=network.target postgresql.service

[Service]
Type=simple
User=$APP_USER
Group=$APP_USER
WorkingDirectory=$APP_DIR/backend
EnvironmentFile=$APP_DIR/.env
ExecStart=$APP_DIR/backend/venv/bin/gunicorn \
    --bind 127.0.0.1:5000 \
    --workers 3 \
    --timeout 30 \
    --access-logfile /var/log/meldpunt_access.log \
    --error-logfile /var/log/meldpunt_error.log \
    app:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SVCEOF

systemctl daemon-reload
systemctl enable meldpunt
systemctl start meldpunt
echo "  Service 'meldpunt' draait"

# ============ 7. NGINX CONFIGURATIE ============
echo "[7/8] Nginx configureren..."
# Vervang _DOMAIN_ in het config template
sed "s/_DOMAIN_/$DOMAIN/g" "$SCRIPT_DIR/nginx/meldpunt.conf" > /etc/nginx/sites-available/meldpunt.conf

# Activeer de site
ln -sf /etc/nginx/sites-available/meldpunt.conf /etc/nginx/sites-enabled/meldpunt.conf
rm -f /etc/nginx/sites-enabled/default

# Test config
nginx -t
systemctl reload nginx
echo "  Nginx geconfigureerd voor $DOMAIN"

# ============ 8. SSL (OPTIONEEL) ============
echo "[8/8] SSL certificaat..."
if [[ "$DOMAIN" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "  OVERGESLAGEN — Let's Encrypt werkt niet met IP-adressen"
    echo "  Koppel een domeinnaam en run: certbot --nginx -d $DOMAIN"
else
    echo "  Certbot uitvoeren voor $DOMAIN..."
    certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --register-unsafely-without-email --redirect || \
        echo "  WAARSCHUWING: Certbot mislukt — handmatig uitvoeren: certbot --nginx -d $DOMAIN"
fi

# ============ KLAAR ============
echo ""
echo "================================================"
echo "  INSTALLATIE VOLTOOID!"
echo "================================================"
echo ""
echo "  Website:    http://$DOMAIN"
echo "  Admin:      http://$DOMAIN/#/admin"
echo "  API:        http://$DOMAIN/api/meldingen"
echo ""
echo "  Admin login:"
echo "    Gebruiker: $ADMIN_USER"
echo "    Wachtwoord: (wat je hebt ingevoerd)"
echo ""
echo "  Database:"
echo "    Host:      localhost"
echo "    Database:  $DB_NAME"
echo "    User:      $DB_USER"
echo "    Wachtwoord: $DB_PASS"
echo ""
echo "  Configuratie:  $APP_DIR/.env"
echo "  Logs:          journalctl -u meldpunt -f"
echo "  Herstart:      systemctl restart meldpunt"
echo ""
echo "  BEWAAR DEZE GEGEVENS!"
echo "================================================"
