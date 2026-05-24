# tuberia.py
# ----------
# Abstraccion sencilla de tuberias nombradas para Linux y Windows.
#
# En Linux se usan FIFOs (os.mkfifo). Son half-duplex, por lo que cada
# servicio necesita dos tuberias: una para recibir peticiones y otra
# para enviar respuestas.
#
# En Windows se usan named pipes sobre \\.\pipe\nombre via pywin32.
# Por consistencia con el modelo half-duplex de Linux, tambien usamos
# dos tuberias (una para peticiones y otra para respuestas).
#
# Esta capa esconde las diferencias del sistema operativo al resto de
# la aplicacion: el codigo de los servicios y del cliente es el mismo
# en ambos sistemas.

import os
import sys

# Tamano maximo de mensaje (acordado en el protocolo, seccion 3.8.4)
MSG_MAX_LEN = 4096

ES_WINDOWS = sys.platform.startswith("win")


# ---------------------------------------------------------------
#  Implementacion para Linux (FIFOs POSIX)
# ---------------------------------------------------------------
if not ES_WINDOWS:

    def ruta_tuberia(nombre):
        """En Linux las tuberias son ficheros normales en /tmp."""
        if nombre.startswith("/"):
            return nombre
        return "/tmp/" + nombre

    def crear_tuberia(nombre):
        """Crea una tuberia nombrada (FIFO) si no existe."""
        ruta = ruta_tuberia(nombre)
        if not os.path.exists(ruta):
            os.mkfifo(ruta)
        return ruta

    def borrar_tuberia(nombre):
        """Elimina la tuberia del sistema de ficheros."""
        ruta = ruta_tuberia(nombre)
        try:
            os.remove(ruta)
        except OSError:
            pass

    class Tuberia:
        """
        Envuelve una FIFO de Linux.
        modo = "lectura"  -> se abre para leer peticiones
        modo = "escritura" -> se abre para enviar respuestas
        """

        def __init__(self, nombre, modo):
            self.nombre = nombre
            self.modo = modo
            self.ruta = ruta_tuberia(nombre)
            self.fichero = None

        def abrir(self):
            if self.modo == "lectura":
                self.fichero = open(self.ruta, "r", encoding="utf-8")
            else:
                self.fichero = open(self.ruta, "w", encoding="utf-8")

        def leer_linea(self):
            """Lee un mensaje (una linea terminada en \\n)."""
            linea = self.fichero.readline()
            if linea == "":
                return None
            return linea.rstrip("\n")

        def escribir_linea(self, texto):
            """Envia un mensaje (anade \\n al final)."""
            self.fichero.write(texto + "\n")
            self.fichero.flush()

        def cerrar(self):
            if self.fichero is not None:
                try:
                    self.fichero.close()
                except OSError:
                    pass
                self.fichero = None


# ---------------------------------------------------------------
#  Implementacion para Windows (Named Pipes con pywin32)
# ---------------------------------------------------------------
else:
    import win32pipe
    import win32file
    import pywintypes

    def ruta_tuberia(nombre):
        # En Windows las tuberias tienen el prefijo \\.\pipe\
        if nombre.startswith("\\\\"):
            return nombre
        return r"\\.\pipe" + "\\" + nombre

    def crear_tuberia(nombre):
        """En Windows la tuberia se crea al abrirla en modo lectura."""
        return ruta_tuberia(nombre)

    def borrar_tuberia(nombre):
        """En Windows el sistema cierra la tuberia al cerrar el handle."""
        return

    class Tuberia:
        """
        Envuelve una Named Pipe de Windows.
        modo = "lectura"  -> el servidor crea la tuberia y espera al cliente
        modo = "escritura" -> el cliente abre una tuberia ya existente
        """

        def __init__(self, nombre, modo):
            self.nombre = nombre
            self.modo = modo
            self.ruta = ruta_tuberia(nombre)
            self.handle = None
            self.buffer = ""

        def abrir(self):
            if self.modo == "lectura":
                # Creamos la tuberia y esperamos a que alguien se conecte.
                self.handle = win32pipe.CreateNamedPipe(
                    self.ruta,
                    win32pipe.PIPE_ACCESS_DUPLEX,
                    win32pipe.PIPE_TYPE_MESSAGE
                    | win32pipe.PIPE_READMODE_MESSAGE
                    | win32pipe.PIPE_WAIT,
                    1,
                    MSG_MAX_LEN,
                    MSG_MAX_LEN,
                    0,
                    None,
                )
                win32pipe.ConnectNamedPipe(self.handle, None)
            else:
                # Esperamos a que la tuberia exista y la abrimos.
                win32pipe.WaitNamedPipe(self.ruta, win32pipe.NMPWAIT_WAIT_FOREVER)
                self.handle = win32file.CreateFile(
                    self.ruta,
                    win32file.GENERIC_READ | win32file.GENERIC_WRITE,
                    0,
                    None,
                    win32file.OPEN_EXISTING,
                    0,
                    None,
                )

        def leer_linea(self):
            """Lee un mensaje hasta encontrar \\n."""
            while "\n" not in self.buffer:
                try:
                    hr, datos = win32file.ReadFile(self.handle, MSG_MAX_LEN)
                except pywintypes.error:
                    return None
                if not datos:
                    return None
                self.buffer += datos.decode("utf-8")
            pos = self.buffer.find("\n")
            linea = self.buffer[:pos]
            self.buffer = self.buffer[pos + 1 :]
            return linea

        def escribir_linea(self, texto):
            """Envia un mensaje terminado en \\n."""
            win32file.WriteFile(self.handle, (texto + "\n").encode("utf-8"))

        def cerrar(self):
            if self.handle is not None:
                try:
                    win32file.CloseHandle(self.handle)
                except pywintypes.error:
                    pass
                self.handle = None
