"""
ejecutor.py
-----------
Servicio que ejecuta procesos de lotes. Recibe un id-programa
(registrado por gesprog) y opcionalmente ids de ficheros (registrados
por gesfich) que se usaran como stdin, stdout y stderr.

Sinopsis:
    python ejecutor.py -e <tub-peticiones> [-d <tub-respuestas>] -x <directorio>

El parametro -x es la ruta de la region aralmac, que en nuestra
implementacion es un directorio raiz que contiene:
    aralmac/ficheros   -> ficheros gestionados por gesfich
    aralmac/programas  -> programas registrados por gesprog
"""

import argparse
import json
import os
import signal
import subprocess
import sys

DIR_SRC = os.path.dirname(os.path.abspath(__file__))
if DIR_SRC not in sys.path:
    sys.path.insert(0, DIR_SRC)

import protocolo
import tuberia


# Estados internos del servicio (seccion 3.6.2)
EJECUTAR = "Ejecutar"     # estado normal
SUSPENDIDOS = "Suspendidos"
PARAR = "Parar"
TERMINADO = "Terminado"

# Estados de cada proceso (seccion 3.11.2)
P_EJECUTANDO = "Ejecutando"
P_SUSPENDIDO = "Suspendido"
P_TERMINADO = "Terminado"

ES_WINDOWS = sys.platform.startswith("win")


class ServicioEjecutor:
    """Estado y operaciones del ejecutor de procesos de lotes."""

    def __init__(self, dir_aralmac):
        self.dir_aralmac = dir_aralmac
        self.dir_ficheros = os.path.join(dir_aralmac, "ficheros")
        self.dir_programas = os.path.join(dir_aralmac, "programas")
        self.estado = EJECUTAR
        self.contador = 0
        # Cada proceso se guarda como dict con: popen, id-programa, estado,
        # codigo-salida, ficheros abiertos (para cerrarlos al terminar).
        self.procesos = {}

    # ---------------------------- utilidades ----------------------------

    def _nuevo_id(self):
        self.contador += 1
        return "e-{:04d}".format(self.contador)

    def _cargar_programa(self, id_programa):
        ruta = os.path.join(self.dir_programas, id_programa + ".json")
        if not os.path.isfile(ruta):
            return None
        try:
            with open(ruta, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return None

    def _abrir_fichero_io(self, id_fichero, modo):
        """Abre un fichero gestionado por gesfich para usarlo como E/S."""
        if not id_fichero:
            return None
        ruta = os.path.join(self.dir_ficheros, id_fichero)
        if not os.path.isfile(ruta):
            return None
        return open(ruta, modo)

    def _refrescar_estados(self):
        """Actualiza el estado de los procesos que ya hayan terminado."""
        for info in self.procesos.values():
            if info["estado"] in (P_EJECUTANDO, P_SUSPENDIDO):
                ret = info["popen"].poll()
                if ret is not None:
                    info["estado"] = P_TERMINADO
                    info["codigo-salida"] = ret
                    self._cerrar_descriptores(info)

    @staticmethod
    def _cerrar_descriptores(info):
        for clave in ("f_stdin", "f_stdout", "f_stderr"):
            f = info.get(clave)
            if f is not None:
                try:
                    f.close()
                except OSError:
                    pass
                info[clave] = None

    # --------------------------- operaciones ----------------------------

    def ejecutar(self, peticion):
        id_programa = peticion.get("id-programa")
        if not id_programa:
            return protocolo.respuesta_error("falta campo: id-programa")
        programa = self._cargar_programa(id_programa)
        if programa is None:
            return protocolo.respuesta_error("no se pudo ejecutar el programa")

        # Abrimos las redirecciones de E/S si se han indicado.
        f_in = self._abrir_fichero_io(peticion.get("stdin"), "r")
        f_out = self._abrir_fichero_io(peticion.get("stdout"), "w")
        f_err = self._abrir_fichero_io(peticion.get("stderr"), "w")

        comando = [programa["ejecutable"]] + list(programa.get("args", []))
        entorno = os.environ.copy()
        for asignacion in programa.get("env", []):
            if "=" in asignacion:
                clave, valor = asignacion.split("=", 1)
                entorno[clave] = valor

        try:
            popen = subprocess.Popen(
                comando,
                stdin=f_in,
                stdout=f_out,
                stderr=f_err,
                env=entorno,
            )
        except (OSError, ValueError):
            for f in (f_in, f_out, f_err):
                if f is not None:
                    f.close()
            return protocolo.respuesta_error("no se pudo ejecutar el programa")

        id_ejecucion = self._nuevo_id()
        self.procesos[id_ejecucion] = {
            "popen": popen,
            "id-programa": id_programa,
            "estado": P_EJECUTANDO,
            "codigo-salida": None,
            "f_stdin": f_in,
            "f_stdout": f_out,
            "f_stderr": f_err,
        }
        return protocolo.respuesta_ok({"id-ejecucion": id_ejecucion})

    def estado_proceso(self, id_ejecucion):
        self._refrescar_estados()

        # Sin id: listar todos los procesos.
        if id_ejecucion is None:
            lista = []
            for ide, info in self.procesos.items():
                item = {
                    "id-ejecucion": ide,
                    "id-programa": info["id-programa"],
                    "proceso-estado": info["estado"],
                }
                if info["estado"] == P_TERMINADO:
                    item["codigo-salida"] = info["codigo-salida"]
                lista.append(item)
            return protocolo.respuesta_ok({"procesos": lista})

        # Con id: devolver el estado del proceso indicado.
        info = self.procesos.get(id_ejecucion)
        if info is None:
            return protocolo.respuesta_error("proceso no encontrado")
        respuesta = {
            "id-ejecucion": id_ejecucion,
            "id-programa": info["id-programa"],
            "proceso-estado": info["estado"],
        }
        if info["estado"] == P_TERMINADO:
            respuesta["codigo-salida"] = info["codigo-salida"]
        return protocolo.respuesta_ok(respuesta)

    def matar(self, id_ejecucion):
        if not id_ejecucion:
            return protocolo.respuesta_error("falta campo: id-ejecucion")
        info = self.procesos.get(id_ejecucion)
        if info is None or info["estado"] == P_TERMINADO:
            return protocolo.respuesta_error("proceso no encontrado o ya terminado")
        try:
            info["popen"].kill()
            info["popen"].wait(timeout=2)
        except (OSError, subprocess.TimeoutExpired):
            pass
        info["estado"] = P_TERMINADO
        info["codigo-salida"] = info["popen"].returncode
        self._cerrar_descriptores(info)
        return protocolo.respuesta_ok()

    # -------------------- transiciones de estado ------------------------

    def suspender_todos(self):
        """Pasa al estado Suspendidos y suspende cada proceso activo."""
        if self.estado != EJECUTAR:
            return protocolo.respuesta_error("transicion invalida")
        for info in self.procesos.values():
            if info["estado"] == P_EJECUTANDO:
                if not ES_WINDOWS:
                    try:
                        info["popen"].send_signal(signal.SIGSTOP)
                        info["estado"] = P_SUSPENDIDO
                    except OSError:
                        pass
                else:
                    # Windows no tiene SIGSTOP; marcamos el estado logicamente.
                    info["estado"] = P_SUSPENDIDO
        self.estado = SUSPENDIDOS
        return protocolo.respuesta_ok()

    def reasumir_todos(self):
        if self.estado != SUSPENDIDOS:
            return protocolo.respuesta_error("transicion invalida")
        for info in self.procesos.values():
            if info["estado"] == P_SUSPENDIDO:
                if not ES_WINDOWS:
                    try:
                        info["popen"].send_signal(signal.SIGCONT)
                    except OSError:
                        pass
                info["estado"] = P_EJECUTANDO
        self.estado = EJECUTAR
        return protocolo.respuesta_ok()

    def parar(self):
        """No acepta nuevas ejecuciones. Termina cuando no haya procesos vivos."""
        self.estado = PARAR
        self._refrescar_estados()
        # Si ya no hay procesos activos, pasamos a Terminado directamente.
        if not self._hay_procesos_activos():
            self.estado = TERMINADO
        return protocolo.respuesta_ok()

    def _hay_procesos_activos(self):
        for info in self.procesos.values():
            if info["estado"] in (P_EJECUTANDO, P_SUSPENDIDO):
                return True
        return False

    # ------------------------ enrutador interno -------------------------

    def atender(self, peticion):
        op = peticion.get("operacion", "")

        if op == "Suspender":
            return self.suspender_todos()
        if op == "Reasumir":
            return self.reasumir_todos()
        if op == "Parar":
            return self.parar()
        if op == "Estado":
            return self.estado_proceso(peticion.get("id-ejecucion"))
        if op == "Matar":
            return self.matar(peticion.get("id-ejecucion"))

        if self.estado == PARAR:
            return protocolo.respuesta_error("servicio parando")
        if self.estado == SUSPENDIDOS:
            return protocolo.respuesta_error("servicio suspendido")

        if op == "Ejecutar":
            return self.ejecutar(peticion)

        return protocolo.respuesta_error("operacion desconocida")


# ------------------------------ main --------------------------------

def main():
    parser = argparse.ArgumentParser(description="Servicio ejecutor")
    parser.add_argument("-e", required=True, help="Tuberia de peticiones")
    parser.add_argument("-d", help="Tuberia de respuestas (half-duplex)")
    parser.add_argument("-x", required=True, help="Directorio aralmac")
    args = parser.parse_args()

    servicio = ServicioEjecutor(args.x)

    tub_peticiones_nombre = args.e
    tub_respuestas_nombre = args.d if args.d else args.e + "_resp"

    tuberia.crear_tuberia(tub_peticiones_nombre)
    tuberia.crear_tuberia(tub_respuestas_nombre)

    print("[ejecutor] servicio iniciado, esperando peticiones...")

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

        # Si estamos en Parar y ya no quedan procesos vivos, terminamos.
        if servicio.estado == PARAR:
            servicio._refrescar_estados()
            if not servicio._hay_procesos_activos():
                servicio.estado = TERMINADO

    print("[ejecutor] servicio terminado")
    tuberia.borrar_tuberia(tub_peticiones_nombre)
    tuberia.borrar_tuberia(tub_respuestas_nombre)


if __name__ == "__main__":
    main()
