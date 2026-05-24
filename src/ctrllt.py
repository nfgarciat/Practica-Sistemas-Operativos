"""
ctrllt.py
---------
Controlador de lotes. Es el unico punto de entrada para los clientes.
Cada peticion que llega lleva un campo "servicio" que indica a quien
debe reenviarse: gesfich, gesprog o ejecutor. La respuesta del
servicio se devuelve al cliente sin modificarla.

La unica operacion propia de ctrllt es "Terminar", que apaga todo el
sistema (envia Terminar a gesfich y gesprog, Parar al ejecutor y se
detiene a si mismo).

Sinopsis:
    python ctrllt.py -c <tub-cliente-pet> [-a <tub-cliente-resp>] \\
                     -f <tub-gesfich-pet> [-b <tub-gesfich-resp>]  \\
                     -p <tub-gesprog-pet> [-q <tub-gesprog-resp>]  \\
                     -e <tub-ejec-pet>    [-d <tub-ejec-resp>]
"""

import argparse
import os
import sys

DIR_SRC = os.path.dirname(os.path.abspath(__file__))
if DIR_SRC not in sys.path:
    sys.path.insert(0, DIR_SRC)

import protocolo
import tuberia


CORRIENDO = "Corriendo"
TERMINADO = "Terminado"


def enviar_a_servicio(tub_envio_nombre, tub_resp_nombre, peticion):
    """
    Envia la peticion a un servicio y devuelve la respuesta.
    Si hay un fallo de comunicacion, devuelve un error generico.
    """
    try:
        salida = tuberia.Tuberia(tub_envio_nombre, "escritura")
        salida.abrir()
        salida.escribir_linea(protocolo.codificar(peticion))
        salida.cerrar()
    except (OSError, IOError):
        return protocolo.respuesta_error("error enviando solicitud al servicio")

    try:
        entrada = tuberia.Tuberia(tub_resp_nombre, "lectura")
        entrada.abrir()
        linea = entrada.leer_linea()
        entrada.cerrar()
    except (OSError, IOError):
        return protocolo.respuesta_error("error leyendo respuesta del servicio")

    if linea is None:
        return protocolo.respuesta_error("error leyendo respuesta del servicio")

    try:
        return protocolo.decodificar(linea)
    except ValueError:
        return protocolo.respuesta_error("error leyendo respuesta del servicio")


def main():
    parser = argparse.ArgumentParser(description="Controlador ctrllt")
    parser.add_argument("-c", required=True, help="Tuberia peticiones cliente")
    parser.add_argument("-a", help="Tuberia respuestas cliente (half-duplex)")
    parser.add_argument("-f", required=True, help="Tuberia peticiones gesfich")
    parser.add_argument("-b", help="Tuberia respuestas gesfich")
    parser.add_argument("-p", required=True, help="Tuberia peticiones gesprog")
    parser.add_argument("-q", help="Tuberia respuestas gesprog")
    parser.add_argument("-e", required=True, help="Tuberia peticiones ejecutor")
    parser.add_argument("-d", help="Tuberia respuestas ejecutor")
    args = parser.parse_args()

    # Resolvemos los nombres de las tuberias de respuesta (por defecto
    # se usa el nombre de la de peticiones con el sufijo "_resp").
    tub_cli_pet = args.c
    tub_cli_resp = args.a if args.a else args.c + "_resp"
    tub_gesfich_pet = args.f
    tub_gesfich_resp = args.b if args.b else args.f + "_resp"
    tub_gesprog_pet = args.p
    tub_gesprog_resp = args.q if args.q else args.p + "_resp"
    tub_ejecutor_pet = args.e
    tub_ejecutor_resp = args.d if args.d else args.e + "_resp"

    # Las tuberias hacia el cliente las crea ctrllt (seccion 3.3).
    tuberia.crear_tuberia(tub_cli_pet)
    tuberia.crear_tuberia(tub_cli_resp)

    # Las tuberias de los servicios ya deben existir (las crea cada servicio
    # al arrancar). Si no existen, esperamos a que aparezcan, lo unico que
    # tiene que asegurar el operador es que ctrllt arranque despues.

    estado = CORRIENDO
    print("[ctrllt] controlador iniciado, esperando peticiones...")

    while estado != TERMINADO:
        # 1) Leer una peticion del cliente.
        entrada = tuberia.Tuberia(tub_cli_pet, "lectura")
        entrada.abrir()
        linea = entrada.leer_linea()
        entrada.cerrar()

        if linea is None:
            continue

        try:
            peticion = protocolo.decodificar(linea)
        except ValueError:
            respuesta = protocolo.respuesta_error("servicio desconocido")
            _responder_cliente(tub_cli_resp, respuesta)
            continue

        servicio = peticion.get("servicio", "")

        # 2) Enrutar segun el servicio destino.
        if servicio == "ctrllt":
            respuesta, terminar = manejar_ctrllt(
                peticion,
                tub_gesfich_pet, tub_gesfich_resp,
                tub_gesprog_pet, tub_gesprog_resp,
                tub_ejecutor_pet, tub_ejecutor_resp,
            )
            if terminar:
                estado = TERMINADO
        elif servicio == "gesfich":
            respuesta = enviar_a_servicio(tub_gesfich_pet, tub_gesfich_resp, peticion)
        elif servicio == "gesprog":
            respuesta = enviar_a_servicio(tub_gesprog_pet, tub_gesprog_resp, peticion)
        elif servicio == "ejecutor":
            respuesta = enviar_a_servicio(tub_ejecutor_pet, tub_ejecutor_resp, peticion)
        else:
            respuesta = protocolo.respuesta_error("servicio desconocido")

        # 3) Devolver la respuesta al cliente sin modificarla.
        _responder_cliente(tub_cli_resp, respuesta)

    print("[ctrllt] controlador terminado")
    tuberia.borrar_tuberia(tub_cli_pet)
    tuberia.borrar_tuberia(tub_cli_resp)


def _responder_cliente(tub_cli_resp, respuesta):
    salida = tuberia.Tuberia(tub_cli_resp, "escritura")
    salida.abrir()
    salida.escribir_linea(protocolo.codificar(respuesta))
    salida.cerrar()


def manejar_ctrllt(peticion,
                   tub_gesfich_pet, tub_gesfich_resp,
                   tub_gesprog_pet, tub_gesprog_resp,
                   tub_ejecutor_pet, tub_ejecutor_resp):
    """
    Atiende las operaciones propias del controlador.
    Devuelve (respuesta, debe_terminar).
    """
    op = peticion.get("operacion", "")
    if op != "Terminar":
        return protocolo.respuesta_error("operacion ctrllt desconocida"), False

    # Propagamos Terminar a gesfich y gesprog, y Parar al ejecutor.
    enviar_a_servicio(
        tub_gesfich_pet, tub_gesfich_resp,
        {"servicio": "gesfich", "operacion": "Terminar"},
    )
    enviar_a_servicio(
        tub_gesprog_pet, tub_gesprog_resp,
        {"servicio": "gesprog", "operacion": "Terminar"},
    )
    enviar_a_servicio(
        tub_ejecutor_pet, tub_ejecutor_resp,
        {"servicio": "ejecutor", "operacion": "Parar"},
    )
    return protocolo.respuesta_ok(), True


if __name__ == "__main__":
    main()
