#!/usr/bin/env bash
# Prueba casos de error y operaciones de suspension/reanudacion.
set -e

DIR_PROYECTO=$(cd "$(dirname "$0")/.." && pwd)
DIR_SRC="$DIR_PROYECTO/src"
DIR_ARALMAC="$DIR_PROYECTO/aralmac"

rm -f /tmp/cli_pet /tmp/cli_pet_resp
rm -f /tmp/gf_pet  /tmp/gf_pet_resp
rm -f /tmp/gp_pet  /tmp/gp_pet_resp
rm -f /tmp/ej_pet  /tmp/ej_pet_resp
rm -rf "$DIR_ARALMAC/ficheros"/* "$DIR_ARALMAC/programas"/*

python3 "$DIR_SRC/gesfich.py"  -f gf_pet -x "$DIR_ARALMAC/ficheros" &
python3 "$DIR_SRC/gesprog.py"  -p gp_pet -x "$DIR_ARALMAC/programas" &
python3 "$DIR_SRC/ejecutor.py" -e ej_pet -x "$DIR_ARALMAC" &
sleep 1
python3 "$DIR_SRC/ctrllt.py" -c cli_pet -f gf_pet -p gp_pet -e ej_pet &
sleep 1

PYTHONPATH="$DIR_SRC" python3 - <<PYEOF
import protocolo, tuberia

def pedir(pet):
    t = tuberia.Tuberia("cli_pet", "escritura")
    t.abrir()
    t.escribir_linea(protocolo.codificar(pet))
    t.cerrar()
    t = tuberia.Tuberia("cli_pet_resp", "lectura")
    t.abrir()
    linea = t.leer_linea()
    t.cerrar()
    return protocolo.decodificar(linea)

print("=== casos de error ===")
print("servicio inexistente:      ", pedir({"servicio":"xx","operacion":"X"}))
print("operacion ctrllt invalida: ", pedir({"servicio":"ctrllt","operacion":"Foo"}))
print("fichero inexistente:       ", pedir({"servicio":"gesfich","operacion":"Leer","id-fichero":"f-9999"}))
print("programa inexistente:      ", pedir({"servicio":"ejecutor","operacion":"Ejecutar","id-programa":"p-9999"}))
print("matar proceso inexistente: ", pedir({"servicio":"ejecutor","operacion":"Matar","id-ejecucion":"e-9999"}))
print("guardar sin ejecutable:    ", pedir({"servicio":"gesprog","operacion":"Guardar"}))

print("\n=== suspender / reasumir gesfich ===")
print("suspender:                 ", pedir({"servicio":"gesfich","operacion":"Suspender"}))
print("crear estando suspendido:  ", pedir({"servicio":"gesfich","operacion":"Crear"}))
print("reasumir:                  ", pedir({"servicio":"gesfich","operacion":"Reasumir"}))
print("crear ahora (debe ir ok):  ", pedir({"servicio":"gesfich","operacion":"Crear"}))
print("reasumir sin estar susp.:  ", pedir({"servicio":"gesfich","operacion":"Reasumir"}))

print("\n=== apagar todo ===")
print(pedir({"servicio":"ctrllt","operacion":"Terminar"}))
PYEOF

wait 2>/dev/null || true
echo "==== fin de prueba ===="
