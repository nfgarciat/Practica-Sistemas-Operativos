#!/usr/bin/env bash
# Arranca los cuatro servicios del sistema en terminales independientes.
# Requiere xterm o gnome-terminal. Si no se dispone de terminal grafica,
# arranque cada servicio en una pestana distinta y al final el cliente.

DIR_PROYECTO=$(dirname "$(dirname "$(realpath "$0")")")
DIR_SRC="$DIR_PROYECTO/src"
DIR_ARALMAC="$DIR_PROYECTO/aralmac"

mkdir -p "$DIR_ARALMAC/ficheros" "$DIR_ARALMAC/programas"

# Limpiamos tuberias antiguas que puedan haber quedado.
rm -f /tmp/cli_pet /tmp/cli_pet_resp
rm -f /tmp/gf_pet  /tmp/gf_pet_resp
rm -f /tmp/gp_pet  /tmp/gp_pet_resp
rm -f /tmp/ej_pet  /tmp/ej_pet_resp

echo "Arrancando gesfich..."
python3 "$DIR_SRC/gesfich.py"  -f gf_pet -x "$DIR_ARALMAC/ficheros" &

echo "Arrancando gesprog..."
python3 "$DIR_SRC/gesprog.py"  -p gp_pet -x "$DIR_ARALMAC/programas" &

echo "Arrancando ejecutor..."
python3 "$DIR_SRC/ejecutor.py" -e ej_pet -x "$DIR_ARALMAC" &

sleep 1

echo "Arrancando ctrllt..."
python3 "$DIR_SRC/ctrllt.py" -c cli_pet \
                             -f gf_pet \
                             -p gp_pet \
                             -e ej_pet &

sleep 1
echo "Sistema arrancado. Ejecute 'python3 src/cliente.py -c cli_pet' en otra terminal."
echo "Para apagar todo, en el cliente escriba: apagar"
wait
