#!/bin/bash
set -e

INSTALL_DIR="/opt/package-remover"

echo "Instalacija Package Remover-a..."

if [ "$EUID" -eq 0 ]; then
    echo "Ne pokreći kao root. Bićeš pitan za sudo šifru."
    exit 1
fi

sudo mkdir -p "$INSTALL_DIR"
sudo cp "$(dirname "$0")/package-remover.py" "$INSTALL_DIR/"
sudo chmod +x "$INSTALL_DIR/package-remover.py"

DESKTOP_DIR="$HOME/.local/share/applications"
mkdir -p "$DESKTOP_DIR"
cp "$(dirname "$0")/package-remover.desktop" "$DESKTOP_DIR/"
sed -i "s|Exec=python3 /opt/package-remover/package-remover.py|Exec=python3 $INSTALL_DIR/package-remover.py|" "$DESKTOP_DIR/package-remover.desktop"

update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true

echo "✅ Instalacija završena!"
echo "Pokreni program iz menija: 'Package Remover'"
echo "Ili iz terminala: python3 $INSTALL_DIR/package-remover.py"
