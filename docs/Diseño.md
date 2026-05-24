# Diseño — Ejecutor de lotes

## 1. Introducción

Este documento describe el diseño y la implementación del sistema
*ejecutor de lotes* propuesto en la práctica. El sistema simula, a
escala pequeña, el modelo de ejecución por lotes de los sistemas
operativos de tipo *mainframe*: el cliente registra programas y
ficheros en un repositorio común (la región **aralmac**) y
posteriormente lanza procesos de lotes referenciándolos por su
identificador.

El proyecto está implementado en **Python 3** y funciona tanto en
**Linux** como en **Windows 11**. La portabilidad se consigue gracias a
una pequeña capa de abstracción de tuberías nombradas
(`src/tuberia.py`) que oculta las diferencias de cada sistema
operativo.

## 2. Componentes del sistema

```
        +---------+      tuberia       +---------+
        | cliente | <----------------> | ctrllt  |
        +---------+                    +----+----+
                                            |
                       +--------------------+--------------------+
                       |                    |                    |
                  +----v----+          +----v----+          +----v----+
                  | gesfich |          | gesprog |          | ejecutor|
                  +---------+          +---------+          +---------+
                       |                    |                    |
                       +----------+---------+----------+---------+
                                  |                    |
                              aralmac/ficheros   aralmac/programas
```

| Componente | Fichero | Función |
|---|---|---|
| `cliente`  | `src/cliente.py`  | Consola interactiva. Envía peticiones a `ctrllt`. |
| `ctrllt`   | `src/ctrllt.py`   | Controlador / pasarela. Único punto de entrada para los clientes. |
| `gesfich`  | `src/gesfich.py`  | Gestor de ficheros (CRUD sobre `aralmac/ficheros`). |
| `gesprog`  | `src/gesprog.py`  | Gestor de programas (CRUD sobre `aralmac/programas`). |
| `ejecutor` | `src/ejecutor.py` | Ejecuta procesos de lotes leyendo programas y ficheros del aralmac. |
| `tuberia`  | `src/tuberia.py`  | Capa portable de tuberías nombradas (Linux + Windows). |
| `protocolo`| `src/protocolo.py`| Codificación y decodificación de mensajes JSON. |

## 3. Comunicación entre procesos

### 3.1 Tuberías nombradas

El documento permite trabajar con tuberías *full-duplex* o
*half-duplex*. Para mantener un único modelo en ambos sistemas
operativos hemos optado por el modelo **half-duplex** en los dos
casos. Esto significa que cada servicio dispone de **dos** tuberías
nombradas:

- Una para **recibir peticiones**.
- Otra para **enviar respuestas**.

La capa `tuberia.py` ofrece la misma API en ambos sistemas:

```python
tub = tuberia.Tuberia("mi_tuberia", "lectura")  # o "escritura"
tub.abrir()
linea = tub.leer_linea()
tub.escribir_linea(texto)
tub.cerrar()
```

| Sistema  | Implementación |
|---|---|
| Linux    | `os.mkfifo()` sobre `/tmp/<nombre>`.|
| Windows  | `win32pipe.CreateNamedPipe()` sobre `\\.\pipe\<nombre>` (requiere `pywin32`). |

### 3.2 Formato de los mensajes

Los mensajes son objetos **JSON** en una sola línea, terminados con
`\n`. El tamaño máximo de un mensaje es **4096 bytes** (constante
`MSG_MAX_LEN` definida en `tuberia.py`).

Todas las peticiones siguen este envoltorio:

```json
{"servicio": "<svc>", "operacion": "<op>", ...campos adicionales...}
```

Todas las respuestas tienen un campo `estado` con valor `"ok"` o
`"error"`. En caso de error se incluye un campo `mensaje`.

## 4. Servicios

A continuación se describen las operaciones admitidas por cada
servicio. La lista completa de campos y de mensajes de error
coincide con la del enunciado y se reproduce en los comentarios del
código fuente.

### 4.1 `gesfich` — Gestor de ficheros

| Operación | Campos petición | Respuesta correcta |
|---|---|---|
| `Crear` | — | `{"estado":"ok","id-fichero":"f-XXXX"}` |
| `Leer` (por id) | `id-fichero` | `{"estado":"ok","contenido":"..."}` |
| `Leer` (listar) | — | `{"estado":"ok","ficheros":["f-0001",...]}` |
| `Actualizar` | `id-fichero`, `ruta` | `{"estado":"ok"}` |
| `Borrar` | `id-fichero` | `{"estado":"ok"}` |
| `Suspender` / `Reasumir` / `Terminar` | — | `{"estado":"ok"}` |

Los ficheros se guardan físicamente en `aralmac/ficheros/f-XXXX`.

### 4.2 `gesprog` — Gestor de programas

| Operación | Campos petición | Respuesta correcta |
|---|---|---|
| `Guardar` | `ejecutable`, `args`, `env` | `{"estado":"ok","id-programa":"p-XXXX"}` |
| `Leer` (por id) | `id-programa` | `{"estado":"ok","programa":{...}}` |
| `Leer` (listar) | — | `{"estado":"ok","programas":["p-0001",...]}` |
| `Actualizar` | `id-programa`, `ruta` | `{"estado":"ok"}` |
| `Borrar` | `id-programa` | `{"estado":"ok"}` |
| `Suspender` / `Reasumir` / `Terminar` | — | `{"estado":"ok"}` |

Al ejecutar `Guardar`, el servicio **copia el binario** dentro de
`aralmac/programas/` con el nombre `p-XXXX_bin` y, en Linux, fuerza
el bit de ejecución (`chmod +x`). Los metadatos se persisten en
`aralmac/programas/p-XXXX.json`; el campo `ejecutable` de ese JSON
apunta a la copia interna, no a la ruta original. `Borrar` elimina
tanto el JSON como el binario copiado. El objeto `programa` devuelto
por `Leer` expone los campos `id-programa`, `nombre`, `args` y `env`.

### 4.3 `ejecutor` — Ejecutor de procesos

| Operación | Campos petición | Respuesta correcta |
|---|---|---|
| `Ejecutar` | `id-programa`, `stdin?`, `stdout?`, `stderr?` | `{"estado":"ok","id-ejecucion":"e-XXXX"}` |
| `Estado` (por id) | `id-ejecucion` | objeto con `proceso-estado` y, si terminó, `codigo-salida` |
| `Estado` (listar) | — | `{"estado":"ok","procesos":[...]}` |
| `Matar` | `id-ejecucion` | `{"estado":"ok"}` |
| `Suspender` / `Reasumir` / `Parar` | — | `{"estado":"ok"}` |

Los campos `stdin`, `stdout` y `stderr` son **identificadores de
fichero** (formato `f-XXXX`) que previamente deben haber sido
registrados con `gesfich`. Internamente el ejecutor abre estos
ficheros y los conecta a la entrada/salida del proceso lanzado con
`subprocess.Popen`.

Los estados posibles de un proceso son `Ejecutando`, `Suspendido` y
`Terminado`.

### 4.4 `ctrllt` — Controlador

`ctrllt` actúa únicamente como **pasarela**: lee la petición del
cliente, mira el campo `servicio`, la reenvía al servicio adecuado y
devuelve la respuesta al cliente sin modificarla.

La única operación propia del controlador es `Terminar`. Cuando se
recibe, `ctrllt`:

1. Envía `{"servicio":"gesfich","operacion":"Terminar"}` a `gesfich`.
2. Envía `{"servicio":"gesprog","operacion":"Terminar"}` a `gesprog`.
3. Envía `{"servicio":"ejecutor","operacion":"Parar"}` al ejecutor.
4. Responde `{"estado":"ok"}` al cliente y se detiene.

## 5. Máquinas de estados

Cada servicio implementa la máquina de estados descrita en el
enunciado:

- **gesfich** y **gesprog**: `Inicio → Corriendo ↔ Suspendido →
  Terminado`. Las operaciones de datos sólo se aceptan en
  `Corriendo` (en `gesprog` la operación `Leer` también se permite
  en `Suspendido`, tal como muestra la figura del enunciado).
- **ejecutor**: `Inicio → Ejecutar ↔ Suspendidos → Parar →
  Terminado`. En `Parar` el servicio no acepta nuevas ejecuciones y
  termina automáticamente cuando todos los procesos hijos han
  finalizado.

Cuando una operación de transición no es posible desde el estado
actual se devuelve el error `"transicion invalida"`.

## 6. Soporte de Linux y Windows 11

La portabilidad se concentra en dos puntos:

1. **`src/tuberia.py`** detecta el sistema operativo con
   `sys.platform` y elige la implementación adecuada:
   - En Linux usa FIFOs (`os.mkfifo`, `open`).
   - En Windows usa Named Pipes (`win32pipe`, `win32file`).
   El resto del proyecto sólo conoce la clase `Tuberia` y las
   funciones `crear_tuberia` / `borrar_tuberia`.
2. **`src/ejecutor.py`** usa `subprocess.Popen` (multiplataforma).
   Sólo la operación `Suspender` necesita una diferencia: en Linux
   se envían las señales `SIGSTOP` y `SIGCONT` a los procesos hijos;
   en Windows, que no dispone de esas señales, la suspensión se
   gestiona de forma lógica (los procesos quedan marcados como
   `Suspendido`).

### Dependencias

| Sistema | Requisitos |
|---|---|
| Linux   | Python 3.8 o superior. No requiere paquetes externos. |
| Windows | Python 3.8 o superior, `pywin32` (`pip install pywin32`). |

## 7. Ejecución

### 7.1 Linux

```bash
# Cada uno de los siguientes comandos se lanza en una terminal distinta.

python3 src/gesfich.py  -f gf_pet -x aralmac/ficheros
python3 src/gesprog.py  -p gp_pet -x aralmac/programas
python3 src/ejecutor.py -e ej_pet -x aralmac
python3 src/ctrllt.py   -c cli_pet -f gf_pet -p gp_pet -e ej_pet
python3 src/cliente.py  -c cli_pet
```

### 7.2 Windows 11 (PowerShell)

```powershell
python src\gesfich.py  -f gf_pet -x aralmac\ficheros
python src\gesprog.py  -p gp_pet -x aralmac\programas
python src\ejecutor.py -e ej_pet -x aralmac
python src\ctrllt.py   -c cli_pet -f gf_pet -p gp_pet -e ej_pet
python src\cliente.py  -c cli_pet
```

Existen también scripts de arranque en `scripts/`:

- `arrancar_linux.sh`
- `arrancar_windows.ps1`

> **Nota sobre el flag `-c` del controlador**: el enunciado usa `-c`
> dos veces en la sinopsis de `ctrllt` (una para la tubería de
> peticiones del cliente y otra para la tubería de respuestas de
> `gesprog`). Para evitar la colisión, en la implementación hemos
> renombrado el segundo `-c` como `-q` (`q` de *gesproQ*).
> Funcionalmente es equivalente: ambos parámetros son opcionales y
> sólo se usan en el modo half-duplex.

### 7.3 Comandos del cliente

Una sesión típica:

```
> fich-crear
{"estado":"ok","id-fichero":"f-0001"}
> fich-actualizar f-0001 /tmp/entrada.txt
{"estado":"ok"}
> fich-crear
{"estado":"ok","id-fichero":"f-0002"}
> prog-guardar /bin/cat
{"estado":"ok","id-programa":"p-0001"}
> ejec-lanzar p-0001 stdin=f-0001 stdout=f-0002
{"estado":"ok","id-ejecucion":"e-0001"}
> ejec-estado e-0001
{"estado":"ok","id-ejecucion":"e-0001","id-programa":"p-0001","proceso-estado":"Terminado","codigo-salida":0}
> fich-leer f-0002
{"estado":"ok","contenido":"...contenido de la entrada..."}
> apagar
{"estado":"ok"}
```

## 8. Estructura del repositorio

```
ejecutor-lotes/
├── docs/
│   └── Diseño.md           <- este documento
├── src/
│   ├── tuberia.py          <- capa portable de tuberias
│   ├── protocolo.py        <- helpers de mensajes JSON
│   ├── cliente.py
│   ├── ctrllt.py
│   ├── gesfich.py
│   ├── gesprog.py
│   └── ejecutor.py
├── aralmac/
│   ├── ficheros/           <- ficheros gestionados por gesfich
│   └── programas/          <- gesprog guarda aquí p-XXXX.json (metadatos)
│                              y p-XXXX_bin (copia del ejecutable)
├── scripts/
│   ├── arrancar_linux.sh
│   ├── arrancar_windows.ps1
│   ├── limpiar_linux.sh
│   ├── test_linux.sh
│   └── test_errores.sh
└── README.md
```

## 9. Decisiones de diseño

- **Un mensaje, una conexión**: cada operación abre, escribe/lee y
  cierra la tubería. Esto sacrifica un poco de rendimiento pero
  simplifica enormemente el control de flujo y permite que varios
  clientes hablen con `ctrllt` sin conflictos.
- **Aralmac como directorios**: en lugar de una base de datos, el
  almacenamiento es un par de directorios. Esto se ajusta a la
  observación del enunciado de que `<info-aralmac>` puede ser "la
  ruta de un directorio".
- **Copia del ejecutable en aralmac**: `gesprog` copia el binario
  registrado dentro de `aralmac/programas/p-XXXX_bin`, tal como
  indica el enunciado (§3.5.3). El ejecutor usa siempre esa copia
  interna, lo que permite que el original sea movido o borrado sin
  afectar las ejecuciones futuras. `Borrar` elimina ambos archivos
  (JSON + copia binaria) para no dejar residuos.
- **Identificadores secuenciales**: al arrancar cada servicio
  consulta los ficheros existentes para continuar la numeración
  desde el mayor valor presente, evitando colisiones tras reinicios.
- **Errores con los mensajes literales del enunciado**: todos los
  textos de error usados (`"fichero no encontrado"`,
  `"transicion invalida"`, etc.) son los que aparecen en la sección
  3 del documento de práctica.
