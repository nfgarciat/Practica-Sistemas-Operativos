"""
gesprog.py
----------
Servicio gestor de programas. Guarda los metadatos (ejecutable,
argumentos y variables de entorno) de los programas que despues
podran ser lanzados por el ejecutor.

Sinopsis:
    python gesprog.py -p <tub-peticiones> [-c <tub-respuestas>] -x <directorio>

Los metadatos de cada programa se guardan en un fichero JSON con
nombre p-XXXX dentro del directorio aralmac/programas.
"""

import argparse
import json
import os
import shutil
import sys

ES_WINDOWS = sys.platform.startswith("win")

DIR_SRC = os.path.dirname(os.path.abspath(__file__))
if DIR_SRC not in sys.path:
    sys.path.insert(0, DIR_SRC)

import protocolo
import tuberia


CORRIENDO = "Corriendo"
SUSPENDIDO = "Suspendido"
TERMINADO = "Terminado"


class ServicioGesprog:
    """Estado y operaciones del gestor de programas."""

    def __init__(self, directorio):
        self.directorio = directorio
        if not os.path.isdir(directorio):
            os.makedirs(directorio)
        self.estado = CORRIENDO
        self.contador = self._calcular_contador_inicial()

    # ---------------------------- utilidades ----------------------------

    def _calcular_contador_inicial(self):
        maximo = 0
        for nombre in os.listdir(self.directorio):
            if nombre.startswith("p-") and len(nombre) >= 6:
                try:
                    n = int(nombre[2:6])
                    if n > maximo:
                        maximo = n
                except ValueError:
                    pass
        return maximo

    def _nuevo_id(self):
        self.contador += 1
        return "p-{:04d}".format(self.contador)

    def _ruta(self, id_programa):
        return os.path.join(self.directorio, id_programa + ".json")

    # --------------------------- operaciones ----------------------------

    def guardar(self, ejecutable, args, env):
        if not ejecutable:
            return protocolo.respuesta_error("falta campo: ejecutable")
        if not os.path.isfile(ejecutable):
            return protocolo.respuesta_error("no se pudo guardar el programa")
        id_programa = self._nuevo_id()

        # Copiamos el ejecutable dentro de aralmac (enunciado sec. 3.5.3).
        # Se guarda como p-XXXX_bin para no colisionar con p-XXXX.json.
        ruta_copia = os.path.join(self.directorio, id_programa + "_bin")
        try:
            shutil.copy2(ejecutable, ruta_copia)
            # En Linux nos aseguramos de que la copia sea ejecutable.
            if not ES_WINDOWS:
                modo = os.stat(ruta_copia).st_mode
                os.chmod(ruta_copia, modo | 0o111)
        except OSError:
            return protocolo.respuesta_error("no se pudo guardar el programa")

        datos = {
            "id-programa": id_programa,
            "nombre": os.path.basename(ejecutable),
            "ejecutable": ruta_copia,          # el ejecutor usa esta ruta
            "ejecutable-original": ejecutable,  # referencia informativa
            "args": args or [],
            "env": env or [],
        }
        try:
            with open(self._ruta(id_programa), "w", encoding="utf-8") as f:
                json.dump(datos, f, ensure_ascii=False)
        except OSError:
            # Si falla guardar el JSON limpiamos la copia binaria
            try:
                os.remove(ruta_copia)
            except OSError:
                pass
            return protocolo.respuesta_error("no se pudo guardar el programa")
        return protocolo.respuesta_ok({"id-programa": id_programa})

    def leer(self, id_programa):
        # Sin id: listar todos los identificadores
        if id_programa is None:
            try:
                lista = sorted(
                    n[:-5]
                    for n in os.listdir(self.directorio)
                    if n.startswith("p-") and n.endswith(".json")
                )
            except OSError:
                return protocolo.respuesta_error("error al listar programas")
            return protocolo.respuesta_ok({"programas": lista})

        # Con id: devolver el objeto de metadatos
        ruta = self._ruta(id_programa)
        if not os.path.isfile(ruta):
            return protocolo.respuesta_error("programa no encontrado")
        try:
            with open(ruta, "r", encoding="utf-8") as f:
                datos = json.load(f)
        except (OSError, ValueError):
            return protocolo.respuesta_error("programa no encontrado")

        # La respuesta solo expone los campos del objeto programa.
        programa = {
            "id-programa": datos.get("id-programa", id_programa),
            "nombre": datos.get("nombre", ""),
            "args": datos.get("args", []),
            "env": datos.get("env", []),
        }
        return protocolo.respuesta_ok({"programa": programa})

    def actualizar(self, id_programa, ruta_nueva):
        if not id_programa or not ruta_nueva:
            return protocolo.respuesta_error("faltan campos: id-programa, ruta")
        ruta = self._ruta(id_programa)
        if not os.path.isfile(ruta):
            return protocolo.respuesta_error("programa no encontrado")
        try:
            with open(ruta, "r", encoding="utf-8") as f:
                datos = json.load(f)
            datos["ejecutable"] = ruta_nueva
            datos["nombre"] = os.path.basename(ruta_nueva)
            with open(ruta, "w", encoding="utf-8") as f:
                json.dump(datos, f, ensure_ascii=False)
        except (OSError, ValueError):
            return protocolo.respuesta_error("no se pudo actualizar el programa")
        return protocolo.respuesta_ok()

    def borrar(self, id_programa):
        ruta = self._ruta(id_programa)
        if not os.path.isfile(ruta):
            return protocolo.respuesta_error("programa no encontrado")
        try:
            os.remove(ruta)
            # Borramos también la copia del ejecutable si existe.
            ruta_bin = os.path.join(self.directorio, id_programa + "_bin")
            if os.path.isfile(ruta_bin):
                os.remove(ruta_bin)
        except OSError:
            return protocolo.respuesta_error("programa no encontrado")
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
        op = peticion.get("operacion", "")

        if op == "Suspender":
            return self.suspender()
        if op == "Reasumir":
            return self.reasumir()
        if op == "Terminar":
            return self.terminar()

        # Segun la maquina de estados, Leer se permite incluso suspendido.
        if op == "Leer":
            return self.leer(peticion.get("id-programa"))

        if self.estado == SUSPENDIDO:
            return protocolo.respuesta_error("servicio suspendido")

        if op == "Guardar":
            return self.guardar(
                peticion.get("ejecutable"),
                peticion.get("args"),
                peticion.get("env"),
            )
        if op == "Actualizar":
            return self.actualizar(
                peticion.get("id-programa"), peticion.get("ruta")
            )
        if op == "Borrar":
            id_programa = peticion.get("id-programa")
            if not id_programa:
                return protocolo.respuesta_error("programa no encontrado")
            return self.borrar(id_programa)

        return protocolo.respuesta_error("operacion desconocida")


# ------------------------------ main --------------------------------

def main():
    parser = argparse.ArgumentParser(description="Servicio gesprog")
    parser.add_argument("-p", required=True, help="Tuberia de peticiones")
    parser.add_argument("-c", help="Tuberia de respuestas (half-duplex)")
    parser.add_argument("-x", required=True, help="Directorio aralmac")
    args = parser.parse_args()

    servicio = ServicioGesprog(args.x)

    tub_peticiones_nombre = args.p
    tub_respuestas_nombre = args.c if args.c else args.p + "_resp"

    tuberia.crear_tuberia(tub_peticiones_nombre)
    tuberia.crear_tuberia(tub_respuestas_nombre)

    print("[gesprog] servicio iniciado, esperando peticiones...")

    while servicio.estado != TERMINADO:
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

    print("[gesprog] servicio terminado")
    tuberia.borrar_tuberia(tub_peticiones_nombre)
    tuberia.borrar_tuberia(tub_respuestas_nombre)


if __name__ == "__main__":
    main()
