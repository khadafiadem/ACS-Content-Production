#!/usr/bin/env bash
# ACS Content Production - setup untuk Ubuntu 22.04/24.04 (Oracle Cloud Always Free)
# Jalankan sebagai root:  sudo bash setup_ubuntu.sh
#
# Hasil:
#   - Aplikasi terinstall di /opt/acs (user: acs)
#   - Venv Python, .env (isi kunci rahasia setelah skrip selesai)
#   - systemd service: acs-content  ->  aktif & auto-start

set -euo pipefail

APP_DIR="/opt/acs"
APP_USER="acs"
APP_PORT="${APP_PORT:-8000}"
REPO_URL="https://github.com/khadafiadem/ACS-Content-Production.git"

echo "==> [1/6] Install system packages"
apt-get update -y
DEBIAN_FRONTEND=noninteractive apt-get install -y \
    python3 python3-venv python3-pip git curl wget ffmpeg

echo "==> [2/6] Buat user & direktori"
id -u "$APP_USER" &>/dev/null || useradd -m -s /bin/bash "$APP_USER"
mkdir -p "$APP_DIR"
chown "$APP_USER":"$APP_USER" "$APP_DIR"

echo "==> [3/6] Clone repo"
if [ -d "$APP_DIR/.git" ]; then
    git -C "$APP_DIR" pull
else
    git clone "$REPO_URL" "$APP_DIR"
fi

echo "==> [4/6] Venv + install dependencies"
python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install --upgrade pip
"$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements.txt"
# ffmpeg dari apt dipakai (lebih stabil untuk video)
grep -q "^FFMPEG_PATH=" "$APP_DIR/.env" 2>/dev/null || \
    echo "FFMPEG_PATH=/usr/bin/ffmpeg" >> "$APP_DIR/.env" 2>/dev/null || true

echo "==> [5/6] Persiapan data & .env"
mkdir -p "$APP_DIR/data/audio" "$APP_DIR/data/videos" "$APP_DIR/data/backgrounds" "$APP_DIR/data/tokens"
chown -R "$APP_USER":"$APP_USER" "$APP_DIR/data"

if [ ! -f "$APP_DIR/.env" ]; then
    cp "$APP_DIR/.env.example" "$APP_DIR/.env"
    cat >> "$APP_DIR/.env" <<EOF

# === Deploy Oracle Cloud ===
APP_HOST=0.0.0.0
APP_PORT=$APP_PORT
SSL_ENABLED=false
FFMPEG_PATH=/usr/bin/ffmpeg
EOF
    echo "!! .env dibuat dari template - WAJIB diisi kunci rahasia lalu restart:"
    echo "   sudo nano $APP_DIR/.env  &&  sudo systemctl restart acs-content"
fi

echo "==> [6/6] Pasang systemd service"
cat > /etc/systemd/system/acs-content.service <<EOF
[Unit]
Description=ACS Content Production (FastAPI)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$APP_USER
Group=$APP_USER
WorkingDirectory=$APP_DIR
ExecStart=$APP_DIR/.venv/bin/python run.py
Restart=always
RestartSec=5
EOF

sed -i 's/reload=True/reload=False/' "$APP_DIR/run.py"

systemctl daemon-reload
systemctl enable acs-content
systemctl restart acs-content

# Buka port di iptables (Oracle default REJECT)
iptables -C INPUT -p tcp --dport "$APP_PORT" -j ACCEPT 2>/dev/null || \
    iptables -I INPUT -p tcp --dport "$APP_PORT" -j ACCEPT

echo ""
echo "================================================================"
echo "SELESAI. Service: acs-content"
echo "  Status:  sudo systemctl status acs-content"
echo "  Log:     sudo journalctl -u acs-content -f"
echo ""
echo "  JANGAN LUPA:"
echo "  1) Isi $APP_DIR/.env (GEMINI_API_KEY, PEXELS_API_KEY, dll)"
echo "  2) Buka port $APP_PORT di Oracle VCN -> Ingress Rules (TCP)"
echo "  3) Cek:  curl http://<PUBLIC_IP>:$APP_PORT/health"
echo "================================================================"