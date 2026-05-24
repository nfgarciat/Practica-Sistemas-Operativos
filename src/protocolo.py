"""
protocolo.py
------------
Funciones auxiliares para codificar y decodificar los mensajes JSON
que viajan por las tuberias nombradas.

Todos los mensajes son objetos JSON en una sola linea (sin saltos
internos) terminados con '\\n' en la tuberia. La capa de tuberia ya
se encarga del '\\n', aqui solo trabajamos con la cadena JSON.
"""

import json


def codificar(objeto):
    """Convierte un diccionario Python en una cadena JSON compacta."""
    return json.dumps(objeto, ensure_ascii=False)


def decodificar(cadena):
    """Convierte la cadena JSON recibida en un diccionario."""
    return json.loads(cadena)


def respuesta_ok(extra=None):
    """Construye una respuesta correcta. extra es un dict opcional."""
    resp = {"estado": "ok"}
    if extra:
        resp.update(extra)
    return resp


def respuesta_error(mensaje):
    """Construye una respuesta de error con el texto indicado."""
    return {"estado": "error", "mensaje": mensaje}
