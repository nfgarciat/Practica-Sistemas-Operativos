#!/usr/bin/env bash
# Script de prueba: arranca los 4 servicios y simula un cliente.
set -e

DIR_PROYECTO=$(cd "$(dirname "$0")/.." && pwd)
DIR_SRC="$DIR_PROYECTO/src"
DIR_ARALMAC="$DIR_PROYECTO/aralmac"

rm -f /tmp/cli_pet /tmp/cli_pet_resp
rm -f /tmp/gf_pet  /tmp/gf_pet_resp
rm -f /tmp/gp_pet  /tmp/gp_pet_resp
rm -f /tmp/ej_pet  /tmp/ej_pet_resp
rm -rf "$DIR_ARALMAC/ficheros"/* "$DIR_ARALMAC/programas"/*

echo "==== arrancando servicios ===="
python3 "$DIR_SRC/gesfich.py"  -f gf_pet -x "$DIR_ARALMAC/ficheros" &
PID_GF=$!
python3 "$DIR_SRC/gesprog.py"  -p gp_pet -x "$DIR_ARALMAC/programas" &
PID_GP=$!
python3 "$DIR_SRC/ejecutor.py" -e ej_pet -x "$DIR_ARALMAC" &
PID_EJ=$!
sleep 1
python3 "$DIR_SRC/ctrllt.py" -c cli_pet -f gf_pet -p gp_pet -e ej_pet &
PID_CT=$!
sleep 1

echo "==== enviando peticiones ===="
PYTHONPATH="$DIR_SRC" python3 - <<PYEOF
import sys, time
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

print(">> Crear fichero entrada")
r1 = pedir({"servicio":"gesfich","operacion":"Crear"})
print(r1)
fid_in = r1["id-fichero"]

print(">> Actualizar entrada con contenido")
with open("/tmp/entrada_test.txt","w") as f:
    f.write("hola mundo desde el lote\n")
print(pedir({"servicio":"gesfich","operacion":"Actualizar","id-fichero":fid_in,"ruta":"/tmp/entrada_test.txt"}))

print(">> Crear fichero salida")
r2 = pedir({"servicio":"gesfich","operacion":"Crear"})
print(r2)
fid_out = r2["id-fichero"]

print(">> Listar ficheros")
print(pedir({"servicio":"gesfich","operacion":"Leer"}))

print(">> Leer contenido entrada")
print(pedir({"servicio":"gesfich","operacion":"Leer","id-fichero":fid_in}))

print(">> Guardar programa 'cat'")
r3 = pedir({"servicio":"gesprog","operacion":"Guardar","ejecutable":"/bin/cat","args":[],"env":[]})
print(r3)
pid = r3["id-programa"]

print(">> Listar programas")
print(pedir({"servicio":"gesprog","operacion":"Leer"}))

print(">> Leer programa por id")
print(pedir({"servicio":"gesprog","operacion":"Leer","id-programa":pid}))

print(">> Ejecutar cat (stdin=entrada, stdout=salida)")
r4 = pedir({"servicio":"ejecutor","operacion":"Ejecutar","id-programa":pid,"stdin":fid_in,"stdout":fid_out})
print(r4)
eid = r4["id-ejecucion"]

time.sleep(0.5)

print(">> Estado del proceso")
print(pedir({"servicio":"ejecutor","operacion":"Estado","id-ejecucion":eid}))

print(">> Listar todos los procesos")
print(pedir({"servicio":"ejecutor","operacion":"Estado"}))

print(">> Leer fichero salida (debe tener el contenido de entrada)")
print(pedir({"servicio":"gesfich","operacion":"Leer","id-fichero":fid_out}))

print(">> Borrar fichero entrada")
print(pedir({"servicio":"gesfich","operacion":"Borrar","id-fichero":fid_in}))

print(">> Borrar programa")
print(pedir({"servicio":"gesprog","operacion":"Borrar","id-programa":pid}))

print(">> Apagar el sistema")
print(pedir({"servicio":"ctrllt","operacion":"Terminar"}))
PYEOF

sleep 1
wait $PID_CT 2>/dev/null || true
wait $PID_GF 2>/dev/null || true
wait $PID_GP 2>/dev/null || true
wait $PID_EJ 2>/dev/null || true
rm -f /tmp/entrada_test.txt
echo "==== prueba completada ===="
