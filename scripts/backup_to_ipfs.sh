#!/bin/bash
# ARAFURA - Backup a IPFS
# Sube archivos críticos a IPFS para persistencia distribuida

echo "========================================"
echo "      ARAFURA - Backup a IPFS"
echo "========================================"
echo ""

# Verificar IPFS
if ! command -v ipfs &> /dev/null; then
    echo "[ERROR] IPFS no instalado"
    echo "Instala con: https://docs.ipfs.tech/install/"
    exit 1
fi

# Archivos críticos para backup
CRITICAL_FILES=(
    "MANIFIESTO_ARAFURA_v1.md"
    "arafura_identity.json"
    "core/agents/arafura.yaml"
    "core/agents/aether.yaml"
    "core/ethics/limits.yaml"
)

# Directorio base
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$BASE_DIR"

echo "[*] Directorio base: $BASE_DIR"
echo ""

# Subir cada archivo
for FILE in "${CRITICAL_FILES[@]}"; do
    if [ -f "$FILE" ]; then
        echo "[*] Subiendo: $FILE"
        HASH=$(ipfs add -q "$FILE")
        echo "    Hash: $HASH"
        echo "$FILE -> $HASH" >> backups/ipfs_hashes.log
    else
        echo "[!] No encontrado: $FILE"
    fi
done

# Subir directorio completo (opcional)
echo ""
read -p "¿Subir directorio completo a IPFS? (s/n): " UPLOAD_ALL
if [ "$UPLOAD_ALL" = "s" ]; then
    echo "[*] Subiendo directorio completo..."
    HASH=$(ipfs add -r -q . | tail -1)
    echo "    Hash raíz: $HASH"
    echo "ROOT -> $HASH" >> backups/ipfs_hashes.log
fi

echo ""
echo "========================================"
echo "    Backup completado"
echo "========================================"
echo ""
echo "Hashes guardados en: backups/ipfs_hashes.log"
echo ""
