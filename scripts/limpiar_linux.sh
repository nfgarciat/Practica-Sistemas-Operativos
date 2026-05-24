#!/usr/bin/env bash
# Borra las tuberias nombradas y el contenido del aralmac.
# util para empezar las pruebas desde cero.

DIR_PROYECTO=$(dirname "$(dirname "$(realpath "$0")")")
DIR_ARALMAC="$DIR_PROYECTO/aralmac"

echo "Borrando tuberias /tmp/..."
rm -f /tmp/cli_pet /tmp/cli_pet_resp
rm -f /tmp/gf_pet  /tmp/gf_pet_resp
rm -f /tmp/gp_pet  /tmp/gp_pet_resp
rm -f /tmp/ej_pet  /tmp/ej_pet_resp

echo "Vaciando aralmac..."
rm -rf "$DIR_ARALMAC/ficheros"/* "$DIR_ARALMAC/programas"/*

echo "Listo."
