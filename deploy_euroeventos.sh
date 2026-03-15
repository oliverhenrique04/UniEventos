#!/usr/bin/env bash

set -euo pipefail

PROJECT_DIR="/var/www/euroeventos"
SERVICE_WORKER="euroeventos-worker"
SERVICE_APP="euroeventos"

echo "Iniciando atualização do projeto..."

if [ "$EUID" -ne 0 ]; then
  echo "Este script precisa ser executado com sudo."
  exit 1
fi

if [ ! -d "$PROJECT_DIR" ]; then
  echo "Erro: diretório $PROJECT_DIR não encontrado."
  exit 1
fi

cd "$PROJECT_DIR"

git pull
systemctl restart "$SERVICE_WORKER"
systemctl restart "$SERVICE_APP"

echo "Atualização concluída com sucesso."