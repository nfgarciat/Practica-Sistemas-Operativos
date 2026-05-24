"""
gesfich.py
----------
Servicio gestor de ficheros. Permite crear, leer, actualizar y borrar
ficheros que viven en la region aralmac.

Sinopsis:
    python gesfich.py -f <tub-peticiones> [-b <tub-respuestas>] -x <directorio>

Cada fichero recibe un identificador con formato f-XXXX y se guarda
fisicamente en el directorio aralmac/ficheros como un archivo con ese
mismo nombre.
"""

import argparse
import os
import shutil
import sys

# Permitir que este fichero se ejecute directamente: anadimos src al path.
DIR_SRC = os.path.dirname(os.path.abspath(__file__))
if DIR_SRC not in sys.path:
    sys.path.insert(0, DIR_SRC)

import protocolo
import tuberia


# Estados del servicio (seccion 3.4.2 del documento)
CORRIENDO = "Corriendo"
SUSPENDIDO = "Suspendido"
TERMINADO = "Terminado"


class ServicioGesfich:
    """Encapsula el estado y las operaciones del gestor de ficheros."""

    def __init__(self, directorio):
        self.directorio = directorio
        if not os.path.isdir(directorio):
            os.makedirs(directorio)
        self.estado = CORRIENDO
        self.contador = self._calcular_contador_inicial()

    # ---------------------------- utilidades ----------------------------

    def _calcular_contador_inicial(self):
        """Si ya existen ficheros f-XXXX se continua desde el mayor."""
        maximo = 0
        for nombre in os.listdir(self.directorio):
            if nombre.startswith("f-") and len(nombre) >= 6:
                try:
                    n = int(nombre[2:6])
                    if n > maximo:
                        maximo = n
                except ValueError:
                    pass
        return maximo

    def _nuevo_id(self):
        self.contador += 1
        return "f-{:04d}".format(self.contador)

    def _ruta(self, id_fichero):
        return os.path.join(self.directorio, id_fichero)

    # --------------------------- operaciones ----------------------------

    def crear(self):
        id_fichero = self._nuevo_id()
        try:
            open(self._ruta(id_fichero), "w").close()
        except OSError:
            return protocolo.respuesta_error("no se pudo crear el fichero")
        return protocolo.respuesta_ok({"id-fichero": id_fichero})

    def leer(self, id_fichero):
        # Sin id: listar todos los ficheros existentes.
        if id_fichero is None:
            try:
                lista = sorted(
                    n for n in os.listdir(self.directorio) if n.startswith("f-")
                )
            except OSError:
                return protocolo.respuesta_error("error al listar ficheros")
            return protocolo.respuesta_ok({"ficheros": lista})

        # Con id: devolver el contenido del fichero.
        ruta = self._ruta(id_fichero)
        if not os.path.isfile(ruta):
            return protocolo.respuesta_error("fichero no encontrado")
        try:
            with open(ruta, "r", encoding="utf-8", errors="replace") as f:
                contenido = f.read()
        except OSError:
            return protocolo.respuesta_error("fichero no encontrado")
        return protocolo.respuesta_ok({"contenido": contenido})

    def actualizar(self, id_fichero, ruta_origen):
        if not id_fichero or not ruta_origen:
            return protocolo.respuesta_error("faltan campos: id-fichero, ruta")
        ruta_destino = self._ruta(id_fichero)
        if not os.path.isfile(ruta_destino):
            return protocolo.respuesta_error("fichero no encontrado")
        if not os.path.isfile(ruta_origen):
            return protocolo.respuesta_error("no se pudo actualizar el fichero")
        try:
            shutil.copyfile(ruta_origen, ruta_destino)
        except OSError:
            return protocolo.respuesta_error("no se pudo actualizar el fichero")
        return protocolo.respuesta_ok()

    def borrar(self, id_fichero):
        ruta = self._ruta(id_fichero)
        if not os.path.isfile(ruta):
            return protocolo.respuesta_error("fichero no encontrado")
        try:
            os.remove(ruta)
        except OSError:
            return protocolo.respuesta_error("fichero no encontrado")
        return protocolo.respuesta_ok()

    # -------------------- transiciones de estado ------------------------

    def suspender(self):
        if self.estado != CORRIENDO:
            return protocolo.respuesta_error("transicion invalida")
        self.estado = SUSPENDIDO
        return protocolo.respuesta_ok()

    def reasumir(self):
        if self.estado != SUSPENDIDO:
            return protocolo.respuesta_error("transicion invalida")
        self.estado = CORRIENDO
        return protocolo.respuesta_ok()

    def terminar(self):
        self.estado = TERMINADO
        return protocolo.respuesta_ok()

    # ------------------------ enrutador interno -------------------------

    def atender(self, peticion):
        """Aplica la peticion y devuelve la respuesta correspondiente."""
        op = peticion.get("operacion", "")

        # Las operaciones de ciclo de vida funcionan en cualquier estado.
        if op == "Suspender":
            return self.suspender()
        if op == "Reasumir":
            return self.reasumir()
        if op == "Terminar":
            return self.terminar()

        # Si esta suspendido, las operaciones de datos se rechazan.
        if self.estado == SUSPENDIDO:
            return protocolo.respuesta_error("servicio suspendido")

        if op == "Crear":
            return self.crear()
        if op == "Leer":
            return self.leer(peticion.get("id-fichero"))
        if op == "Actualizar":
            return self.actualizar(
                peticion.get("id-fichero"), peticion.get("ruta")
            )
        if op == "Borrar":
            id_fichero = peticion.get("id-fichero")
            if not id_fichero:
                return protocolo.respuesta_error("fichero no encontrado")
            return self.borrar(id_fichero)

        return protocolo.respuesta_error("operacion desconocida")


# ------------------------------ main --------------------------------

def main():
    parser = argparse.ArgumentParser(description="Servicio gesfich")
    parser.add_argument("-f", required=True, help="Tuberia de peticiones")
    parser.add_argument("-b", help="Tuberia de respuestas (half-duplex)")
    parser.add_argument("-x", required=True, help="Directorio aralmac")
    args = parser.parse_args()

    servicio = ServicioGesfich(args.x)

    # Creamos las dos tuberias (modo half-duplex, valido para Linux y Windows).
    tub_peticiones_nombre = args.f
    tub_respuestas_nombre = args.b if args.b else args.f + "_resp"

    tuberia.crear_tuberia(tub_peticiones_nombre)
    tuberia.crear_tuberia(tub_respuestas_nombre)

    print("[gesfich] servicio iniciado, esperando peticiones...")

    while servicio.estado != TERMINADO:
        # Cada ciclo abrimos las tuberias, atendemos una peticion y cerramos.
        # Es la forma mas simple de soportar varios clientes secuencialmente.
        entrada = tuberia.Tuberia(tub_peticiones_nombre, "lectura")
        entrada.abrir()
        linea = entrada.leer_linea()
        entrada.cerrar()

        if linea is None:
            continue

        try:
            peticion = protocolo.decodificar(linea)
        except ValueError:
            respuesta = protocolo.respuesta_error("operacion desconocida")
        else:
            respuesta = servicio.atender(peticion)

        salida = tuberia.Tuberia(tub_respuestas_nombre, "escritura")
        salida.abrir()
        salida.escribir_linea(protocolo.codificar(respuesta))
        salida.cerrar()

    print("[gesfich] servicio terminado")
    tuberia.borrar_tuberia(tub_peticiones_nombre)
    tuberia.borrar_tuberia(tub_respuestas_nombre)


if __name__ == "__main__":
    main()
