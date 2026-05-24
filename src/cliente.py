"""
cliente.py
----------
Cliente interactivo para el sistema de ejecucion de lotes.
Se conecta unicamente a ctrllt enviando peticiones JSON y mostrando
las respuestas que devuelve el servidor.

Sinopsis:
    python cliente.py -c <tub-peticiones> [-a <tub-respuestas>]

Comandos disponibles en la consola interactiva:
    --- gesfich ---
    fich-crear
    fich-leer [id]
    fich-actualizar <id> <ruta>
    fich-borrar <id>
    fich-suspender / fich-reasumir / fich-terminar

    --- gesprog ---
    prog-guardar <ejecutable> [arg1 arg2 ...]
    prog-leer [id]
    prog-actualizar <id> <ruta>
    prog-borrar <id>
    prog-suspender / prog-reasumir / prog-terminar

    --- ejecutor ---
    ejec-lanzar <id-programa> [stdin=id] [stdout=id] [stderr=id]
    ejec-estado [id-ejecucion]
    ejec-matar <id-ejecucion>
    ejec-suspender / ejec-reasumir / ejec-parar

    --- general ---
    apagar          (envia Terminar a ctrllt: apaga todo el sistema)
    salir           (sale del cliente sin tocar el servidor)
    ayuda
"""

import argparse
import os
import sys

DIR_SRC = os.path.dirname(os.path.abspath(__file__))
if DIR_SRC not in sys.path:
    sys.path.insert(0, DIR_SRC)

import protocolo
import tuberia


# -------------- comunicacion con ctrllt -----------------

def enviar(tub_pet_nombre, tub_resp_nombre, peticion):
    """Envia una peticion a ctrllt y devuelve la respuesta como dict."""
    salida = tuberia.Tuberia(tub_pet_nombre, "escritura")
    salida.abrir()
    salida.escribir_linea(protocolo.codificar(peticion))
    salida.cerrar()

    entrada = tuberia.Tuberia(tub_resp_nombre, "lectura")
    entrada.abrir()
    linea = entrada.leer_linea()
    entrada.cerrar()

    if linea is None:
        return {"estado": "error", "mensaje": "sin respuesta"}
    try:
        return protocolo.decodificar(linea)
    except ValueError:
        return {"estado": "error", "mensaje": "respuesta invalida"}


# ----------------- traduccion de comandos ----------------

def construir_peticion(comando, partes):
    """A partir de un comando interactivo construye la peticion JSON."""
    # ---------- gesfich ----------
    if comando == "fich-crear":
        return {"servicio": "gesfich", "operacion": "Crear"}
    if comando == "fich-leer":
        pet = {"servicio": "gesfich", "operacion": "Leer"}
        if partes:
            pet["id-fichero"] = partes[0]
        return pet
    if comando == "fich-actualizar" and len(partes) >= 2:
        return {
            "servicio": "gesfich",
            "operacion": "Actualizar",
            "id-fichero": partes[0],
            "ruta": partes[1],
        }
    if comando == "fich-borrar" and partes:
        return {
            "servicio": "gesfich",
            "operacion": "Borrar",
            "id-fichero": partes[0],
        }
    if comando == "fich-suspender":
        return {"servicio": "gesfich", "operacion": "Suspender"}
    if comando == "fich-reasumir":
        return {"servicio": "gesfich", "operacion": "Reasumir"}
    if comando == "fich-terminar":
        return {"servicio": "gesfich", "operacion": "Terminar"}

    # ---------- gesprog ----------
    if comando == "prog-guardar" and partes:
        return {
            "servicio": "gesprog",
            "operacion": "Guardar",
            "ejecutable": partes[0],
            "args": partes[1:],
            "env": [],
        }
    if comando == "prog-leer":
        pet = {"servicio": "gesprog", "operacion": "Leer"}
        if partes:
            pet["id-programa"] = partes[0]
        return pet
    if comando == "prog-actualizar" and len(partes) >= 2:
        return {
            "servicio": "gesprog",
            "operacion": "Actualizar",
            "id-programa": partes[0],
            "ruta": partes[1],
        }
    if comando == "prog-borrar" and partes:
        return {
            "servicio": "gesprog",
            "operacion": "Borrar",
            "id-programa": partes[0],
        }
    if comando == "prog-suspender":
        return {"servicio": "gesprog", "operacion": "Suspender"}
    if comando == "prog-reasumir":
        return {"servicio": "gesprog", "operacion": "Reasumir"}
    if comando == "prog-terminar":
        return {"servicio": "gesprog", "operacion": "Terminar"}

    # ---------- ejecutor ----------
    if comando == "ejec-lanzar" and partes:
        pet = {
            "servicio": "ejecutor",
            "operacion": "Ejecutar",
            "id-programa": partes[0],
        }
        for extra in partes[1:]:
            if "=" in extra:
                clave, valor = extra.split("=", 1)
                if clave in ("stdin", "stdout", "stderr"):
                    pet[clave] = valor
        return pet
    if comando == "ejec-estado":
        pet = {"servicio": "ejecutor", "operacion": "Estado"}
        if partes:
            pet["id-ejecucion"] = partes[0]
        return pet
    if comando == "ejec-matar" and partes:
        return {
            "servicio": "ejecutor",
            "operacion": "Matar",
            "id-ejecucion": partes[0],
        }
    if comando == "ejec-suspender":
        return {"servicio": "ejecutor", "operacion": "Suspender"}
    if comando == "ejec-reasumir":
        return {"servicio": "ejecutor", "operacion": "Reasumir"}
    if comando == "ejec-parar":
        return {"servicio": "ejecutor", "operacion": "Parar"}

    # ---------- ctrllt ----------
    if comando == "apagar":
        return {"servicio": "ctrllt", "operacion": "Terminar"}

    return None


AYUDA = """\
Comandos disponibles:
  fich-crear
  fich-leer [id]
  fich-actualizar <id> <ruta>
  fich-borrar <id>
  fich-suspender | fich-reasumir | fich-terminar

  prog-guardar <ejecutable> [arg ...]
  prog-leer [id]
  prog-actualizar <id> <ruta>
  prog-borrar <id>
  prog-suspender | prog-reasumir | prog-terminar

  ejec-lanzar <id-prog> [stdin=fid] [stdout=fid] [stderr=fid]
  ejec-estado [id-ejec]
  ejec-matar <id-ejec>
  ejec-suspender | ejec-reasumir | ejec-parar

  apagar    -> apaga todo el sistema (ctrllt Terminar)
  ayuda     -> muestra esta ayuda
  salir     -> cierra el cliente
"""


# ----------------------------- main ---------------------------------

def main():
    parser = argparse.ArgumentParser(description="Cliente ctrllt")
    parser.add_argument("-c", required=True, help="Tuberia para enviar peticiones")
    parser.add_argument("-a", help="Tuberia para recibir respuestas (half-duplex)")
    args = parser.parse_args()

    tub_pet = args.c
    tub_resp = args.a if args.a else args.c + "_resp"

    print("Cliente ejecutor de lotes. Escriba 'ayuda' para ver comandos.")

    while True:
        try:
            linea = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not linea:
            continue

        partes = linea.split()
        comando = partes[0]
        argumentos = partes[1:]

        if comando == "salir":
            break
        if comando == "ayuda":
            print(AYUDA)
            continue

        peticion = construir_peticion(comando, argumentos)
        if peticion is None:
            print("Comando desconocido o argumentos insuficientes. 'ayuda' para ver lista.")
            continue

        respuesta = enviar(tub_pet, tub_resp, peticion)
        print(protocolo.codificar(respuesta))

        # Si acabamos de apagar el sistema, no tiene sentido seguir conectados.
        if comando == "apagar" and respuesta.get("estado") == "ok":
            break


if __name__ == "__main__":
    main()
