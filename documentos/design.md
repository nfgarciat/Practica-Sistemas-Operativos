# Diseño de la API
# Maria Clara Medina y Franchesca Garcia Tabares

## Tabla de contenidos

1. [Propósito del proyecto](#1-propósito-del-proyecto)
2. [Componentes propuestos](#2-componentes-propuestos)
3. [Comunicación y sistemas operativos](#3-comunicación-y-sistemas-operativos)
4. [Arranque de los componentes](#4-arranque-de-los-componentes)
5. [Estructura base de los mensajes](#5-estructura-base-de-los-mensajes)
6. [Servicios de la API](#6-servicios-de-la-api)
7. [Estados, control y errores](#7-estados-control-y-errores)
8. [Flujo de ejemplo completo](#8-flujo-de-ejemplo-completo)
9. [Decisiones de diseño](#9-decisiones-de-diseño)
10. [Primera entrega](#10-primera-entrega)

---

## 1. Propósito del proyecto

Este documento presenta el diseño de la API para la primera entrega del proyecto.

En esta entrega no se implementa código. El objetivo es definir los servicios del sistema, sus operaciones, los argumentos que reciben y las respuestas que deben retornar en formato JSON.

El sistema permite registrar programas y ficheros para luego ejecutar procesos de lote. Un proceso de lote usa un fichero de entrada, ejecuta uno o varios programas en orden y guarda el resultado en un fichero de salida.

La comunicación entre procesos se realizará mediante tuberías nombradas. Como nuestro trabajo es en parejas, el diseño contempla una futura implementación en Linux y Windows 11.

---

## 2. Componentes propuestos

El sistema se divide en los siguientes componentes:

| Componente | Responsabilidad |
|---|---|
| `cliente` | Envía solicitudes al sistema. Puede comunicarse con `ctrllt` o directamente con los servicios. No se implementa en esta entrega. |
| `ctrllt` | Recibe peticiones y las redirige al servicio correcto. Solo hace enrutamiento. |
| `gesprog` | Administra programas registrados. |
| `gesfich` | Administra ficheros registrados. |
| `ejecutor` | Ejecuta y controla procesos de lote de forma concurrente. |
| `aralmac` | Área donde se almacenan programas, ficheros e información del sistema. Se accede mediante una biblioteca interna compartida. |

Flujo general:

```text
cliente -> ctrllt -> gesprog
                 -> gesfich
                 -> ejecutor

cliente -> gesprog   (conexión directa)
cliente -> gesfich   (conexión directa)
cliente -> ejecutor  (conexión directa)
```

`ctrllt` actúa como pasarela opcional. Recibe una petición JSON, revisa el servicio solicitado y la envía al componente correspondiente. El cliente también puede conectarse directamente a cualquiera de los servicios sin pasar por `ctrllt`.

---

## 3. Comunicación y sistemas operativos

Los procesos se comunicarán mediante tuberías nombradas. Cada mensaje enviado por una tubería será un JSON.

### 3.1 Modelo de tuberías por sistema operativo

El modelo de comunicación depende del sistema operativo:

- **Linux**: se usan dos tuberías por servicio, una para petición y otra para respuesta (half-duplex). La tubería de respuesta es única por servicio y es compartida: todos los clientes que se comuniquen con un mismo servicio leen sus respuestas de esa misma tubería de retorno. Las respuestas se identifican mediante el campo `id_peticion`.

- **Windows 11**: se usa una sola tubería por instancia de conexión en modo **full-duplex** (obligatorio). Windows no soporta el modelo half-duplex de manera confiable con tuberías nombradas, por lo que en esta plataforma cada cliente abre una instancia de tubería full-duplex con el servicio correspondiente.

Ejemplo (Linux, half-duplex):

```text
cliente ---- petición ----> ctrllt  (tubería de entrada)
cliente <--- respuesta ---- ctrllt  (tubería de respuesta única)
```

Ejemplo (Windows 11, full-duplex):

```text
cliente <---> ctrllt  (una sola tubería, bidireccional por instancia)
```

### 3.2 Nombres de tuberías

En Linux se podrían usar nombres como:

```text
/tmp/lotes_ctrllt
/tmp/lotes_gesprog
/tmp/lotes_gesfich
/tmp/lotes_ejecutor
```

En Windows 11 se podrían usar nombres como:

```text
\\.\pipe\lotes_ctrllt
\\.\pipe\lotes_gesprog
\\.\pipe\lotes_gesfich
\\.\pipe\lotes_ejecutor
```

### 3.3 Script de limpieza

Antes de iniciar el sistema se debe ejecutar un script de limpieza que elimine las tuberías nombradas huérfanas y el estado persistente previo. Esto garantiza que el sistema arranque en un estado conocido.

En Linux, el script debe eliminar los ficheros de tubería que hayan quedado del proceso anterior:

```bash
rm -f /tmp/lotes_ctrllt
rm -f /tmp/lotes_gesprog
rm -f /tmp/lotes_gesfich
rm -f /tmp/lotes_ejecutor
```

En Windows 11 las tuberías son gestionadas por el sistema operativo y se limpian automáticamente al terminar el proceso. No obstante, el script debe verificar que no haya instancias previas activas antes de arrancar.

El script de limpieza debe ejecutarse siempre antes de lanzar cualquier componente del sistema. Si se desea también limpiar los datos persistentes (programas, ficheros y lotes registrados en `aralmac`), esto debe hacerse explícitamente mediante una operación de administración o eliminando los datos directamente.

---

## 4. Arranque de los componentes

Cada componente se inicia como un proceso independiente y recibe por línea de comandos las tuberías que debe usar y la configuración de `aralmac`. Los parámetros opcionales solo aplican en sistemas half-duplex (Linux).

**ctrllt**
```
ctrllt -c <tuberia-cliente-entrada> [-r <tuberia-cliente-respuesta>]
       -g <tuberia-gesprog>         [-rg <tuberia-gesprog-respuesta>]
       -f <tuberia-gesfich>         [-rf <tuberia-gesfich-respuesta>]
       -e <tuberia-ejecutor>        [-re <tuberia-ejecutor-respuesta>]
```

**gesprog**
```
gesprog -g <tuberia-entrada> [-r <tuberia-respuesta>] -x <info-aralmac>
```

**gesfich**
```
gesfich -f <tuberia-entrada> [-r <tuberia-respuesta>] -x <info-aralmac>
```

**ejecutor**
```
ejecutor -e <tuberia-entrada> [-r <tuberia-respuesta>] -x <info-aralmac>
```

| Parámetro | Descripción |
|---|---|
| `-c / -g / -f / -e` | Tubería de entrada de peticiones del componente. En full-duplex también recibe respuestas. |
| `-r / -rg / -rf / -re` | Tubería de respuesta (solo en half-duplex, Linux). |
| `-x <info-aralmac>` | Ruta o parámetros de conexión al área de almacenamiento compartida. |

En Windows 11 los parámetros `-r` no se usan; cada componente gestiona el canal bidireccional sobre la misma tubería full-duplex.

---

## 5. Estructura base de los mensajes

Todas las peticiones tendrán esta estructura:

```json
{
    "id_peticion": "req-0001",
    "servicio": "nombre_servicio",
    "operacion": "nombre_operacion",
    "datos": {},
    "timestamp": "2026-05-07T19:00:00Z"
}
```

El campo `timestamp` sigue el formato ISO 8601. Sirve para correlacionar eventos en logs y depurar problemas de orden de mensajes.

Respuesta exitosa:

```json
{
    "id_peticion": "req-0001",
    "estado": "ok",
    "mensaje": "Operación realizada correctamente",
    "datos": {},
    "timestamp": "2026-05-07T19:00:01Z"
}
```

Respuesta con error:

```json
{
    "id_peticion": "req-0001",
    "estado": "error",
    "mensaje": "Descripción del error",
    "codigo": "CODIGO_ERROR",
    "detalles": {},
    "timestamp": "2026-05-07T19:00:01Z"
}
```

El campo `detalles` en las respuestas de error es un objeto opcional que proporciona contexto adicional sobre el fallo, como el identificador que no se encontró o el campo que faltó. Ejemplo:

```json
{
    "id_peticion": "req-0005",
    "estado": "error",
    "mensaje": "El fichero solicitado no existe",
    "codigo": "FICHERO_NO_EXISTE",
    "detalles": {
        "id_fichero": "f-9999"
    },
    "timestamp": "2026-05-07T19:00:01Z"
}
```

---

## 6. Servicios de la API

En esta sección se definen los servicios principales y las operaciones que acepta cada uno. Para no repetir demasiado, primero se muestran las operaciones en tablas y luego algunos ejemplos JSON de las peticiones más importantes.

---

### 6.1 gesprog

`gesprog` administra los programas registrados en `aralmac`. Cada programa se identifica con el formato:

```text
p-XXXX
```

Ejemplo:

```text
p-0001
```

Un programa almacena ejecutable, argumentos, variables de ambiente, descripción y estado.

| Operación | Datos esperados | Respuesta principal |
|---|---|---|
| `registrar_programa` | `{ "ejecutable": "/usr/bin/wc", "argumentos": ["-l"], "ambiente": { "LANG": "es_CO.UTF-8" }, "descripcion": "Cuenta líneas" }` | Retorna id_programa. |
| `leer_programa` | `{ "id_programa": "p-0001" }` | Consulta un programa. |
| `listar_programas` | `{}` | Lista los programas registrados. |
| `actualizar_programa` | `{ "id_programa": "p-0001", "ejecutable": "/usr/bin/wc", "argumentos": ["-w"], "ambiente": {}, "descripcion": "Cuenta palabras" }` | Actualiza el programa. |
| `borrar_programa` | `{ "id_programa": "p-0001" }` | Borra el programa. |
| `suspender_servicio` | `{}` | Cambia el servicio a suspendido. |
| `reasumir_servicio` | `{}` | Cambia el servicio a corriendo. |
| `terminar_servicio` | `{}` | Cambia el servicio a terminado. |

Ejemplo para registrar programa:

```json
{
    "id_peticion": "req-0001",
    "servicio": "gesprog",
    "operacion": "registrar_programa",
    "datos": {
        "ejecutable": "/usr/bin/wc",
        "argumentos": ["-l"],
        "ambiente": {
            "LANG": "es_CO.UTF-8"
        },
        "descripcion": "Cuenta la cantidad de líneas del fichero de entrada"
    }
}
```

Respuesta:

```json
{
    "id_peticion": "req-0001",
    "estado": "ok",
    "mensaje": "Programa registrado correctamente",
    "datos": {
        "id_programa": "p-0001"
    }
}
```

Ejemplo para leer programa:

```json
{
    "id_peticion": "req-0002",
    "servicio": "gesprog",
    "operacion": "leer_programa",
    "datos": {
        "id_programa": "p-0001"
    }
}
```

---

### 6.2 gesfich

`gesfich` administra los ficheros registrados en `aralmac`. Cada fichero se identifica con el formato:

```text
f-XXXX
```

Ejemplo:

```text
f-0001
```

| Operación | Datos esperados | Respuesta principal |
|---|---|---|
| `crear_fichero` | `{ "contenido": "texto inicial" }` o `{ "contenido": "" }` | Retorna id_fichero. |
| `leer_fichero` | `{ "id_fichero": "f-0001" }` | Lee un fichero específico o lista los ficheros si no recibe identificador. |
| `listar_ficheros` | `{}` | Lista los ficheros registrados. |
| `actualizar_fichero` | `{ "id_fichero": "f-0001", "ruta_fichero": "./datos/nuevo.txt" }` | Reemplaza el contenido usando la ruta de un fichero externo. |
| `borrar_fichero` | `{ "id_fichero": "f-0001" }` | Borra el fichero. Falla con `FICHERO_EN_USO` si hay un lote activo usándolo. |
| `suspender_servicio` | `{}` | Cambia el servicio a suspendido. |
| `reasumir_servicio` | `{}` | Cambia el servicio a corriendo. |
| `terminar_servicio` | `{}` | Cambia el servicio a terminado. |

Ejemplo para crear fichero:

```json
{
    "id_peticion": "req-0003",
    "servicio": "gesfich",
    "operacion": "crear_fichero",
    "datos": {
        "contenido": "3\n1\n2\n"
    }
}
```

Respuesta:

```json
{
    "id_peticion": "req-0003",
    "estado": "ok",
    "mensaje": "Fichero creado correctamente",
    "datos": {
        "id_fichero": "f-0001"
    }
}
```

Ejemplo para leer un fichero:

```json
{
    "id_peticion": "req-0004",
    "servicio": "gesfich",
    "operacion": "leer_fichero",
    "datos": {
        "id_fichero": "f-0001"
    }
}
```

Respuesta:

```json
{
    "id_peticion": "req-0004",
    "estado": "ok",
    "mensaje": "Fichero encontrado",
    "datos": {
        "id_fichero": "f-0001",
        "contenido": "3\n1\n2\n"
    }
}
```

Si `leer_fichero` no recibe `id_fichero`, se interpreta como una consulta general de los ficheros registrados.

Ejemplo para actualizar:

```json
{
    "id_peticion": "req-0005",
    "servicio": "gesfich",
    "operacion": "actualizar_fichero",
    "datos": {
        "id_fichero": "f-0001",
        "ruta_fichero": "./datos/entrada_actualizada.txt"
    }
}
```

En esta operación, actualizar significa reemplazar el contenido almacenado en `aralmac` por el contenido del fichero indicado en `ruta_fichero`.

Ejemplo para borrar:

```json
{
    "id_peticion": "req-0006",
    "servicio": "gesfich",
    "operacion": "borrar_fichero",
    "datos": {
        "id_fichero": "f-0001"
    }
}
```

---

### 6.3 ejecutor

`ejecutor` administra los procesos de lote. Cada lote se identifica con el formato:

```text
l-XXXX
```

Ejemplo:

```text
l-0001
```

Un lote requiere obligatoriamente un fichero de entrada, un fichero de salida y una lista ordenada de al menos un programa. El formato de ejecución es:

```text
fichero_entrada -> programa_1 -> programa_2 -> ... -> fichero_salida
```

Ambos ficheros (entrada y salida) son **obligatorios**. Si falta cualquiera de los dos, la operación retorna error `FICHERO_REQUERIDO`.

#### Concurrencia

El ejecutor puede gestionar múltiples procesos de lote simultáneamente. Cada lote se ejecuta en su propio hilo de ejecución. Cuando el ejecutor está en estado `suspendido`, los lotes ya en ejecución continúan corriendo hasta terminar, pero no se aceptan nuevas solicitudes de ejecución.

#### Acceso a aralmac

El ejecutor no se comunica con `gesprog` ni con `gesfich` a través de sus tuberías para validar o leer recursos. En su lugar, utiliza directamente una biblioteca interna de acceso a `aralmac` que expone una API para consultar programas y ficheros. Esta biblioteca es compartida entre los componentes que necesitan acceder al almacenamiento.

#### Naturaleza asíncrona de ejecutar_lote

La operación `ejecutar_lote` no es bloqueante. El ejecutor valida que los identificadores de programas y ficheros existan, crea el proceso de lote y retorna inmediatamente el `id_lote` con estado `corriendo`. El lote se ejecuta en segundo plano. Cuando el lote termina (por cualquier causa), el ejecutor actualiza su estado en `aralmac`. El cliente puede consultar el estado mediante `estado_lote`.

| Operación | Datos esperados | Respuesta principal |
|---|---|---|
| `ejecutar_lote` | `{ "entrada": "f-0001", "salida": "f-0002", "programas": ["p-0001", "p-0002"] }` | Retorna id_lote. Ambos ficheros son obligatorios. |
| `estado_lote` | `{ "id_lote": "l-0001" }` | Consulta el estado de un lote o lista todos si no recibe identificador. |
| `listar_lotes` | `{}` | Lista los procesos de lote. |
| `matar_lote` | `{ "id_lote": "l-0001" }` | Termina forzosamente un lote e indica que fue terminado por causa externa. |
| `suspender_servicio` | `{}` | Cambia el ejecutor a suspendido. Los lotes activos continúan; no se aceptan nuevos. |
| `reasumir_servicio` | `{}` | Cambia el ejecutor a corriendo. |
| `parar_ejecutor` | `{}` | Detiene el ejecutor. |

Ejemplo para ejecutar:

```json
{
    "id_peticion": "req-0007",
    "servicio": "ejecutor",
    "operacion": "ejecutar_lote",
    "datos": {
        "entrada": "f-0001",
        "salida": "f-0002",
        "programas": ["p-0001", "p-0002"]
    }
}
```

Respuesta (inmediata, el lote corre en segundo plano):

```json
{
    "id_peticion": "req-0007",
    "estado": "ok",
    "mensaje": "Proceso de lote iniciado correctamente",
    "datos": {
        "id_lote": "l-0001",
        "estado_lote": "corriendo"
    },
    "timestamp": "2026-05-07T19:00:00Z"
}
```

Cuando el lote termina, el ejecutor envía una notificación al cliente usando el mismo `id_peticion` original:

```json
{
    "id_peticion": "req-0007",
    "estado": "ok",
    "mensaje": "Proceso de lote finalizado",
    "datos": {
        "id_lote": "l-0001",
        "estado_lote": "terminado",
        "causa": null
    },
    "timestamp": "2026-05-07T19:00:45Z"
}
```

Si el lote terminó por error, la notificación lleva `estado_lote: "fallido"` y `causa: "error_ejecucion"`. Si fue matado, lleva `estado_lote: "matado"` y `causa: "terminado_externamente"`.

Ejemplo para consultar estado:

```json
{
    "id_peticion": "req-0008",
    "servicio": "ejecutor",
    "operacion": "estado_lote",
    "datos": {
        "id_lote": "l-0001"
    }
}
```

Respuesta cuando el lote terminó normalmente:

```json
{
    "id_peticion": "req-0008",
    "estado": "ok",
    "mensaje": "Estado del lote consultado correctamente",
    "datos": {
        "id_lote": "l-0001",
        "estado_lote": "terminado",
        "causa": null
    }
}
```

Si `estado_lote` no recibe `id_lote`, se interpreta como una consulta general equivalente a listar los procesos de lote.

Ejemplo para matar un lote:

```json
{
    "id_peticion": "req-0009",
    "servicio": "ejecutor",
    "operacion": "matar_lote",
    "datos": {
        "id_lote": "l-0001"
    }
}
```

Respuesta:

```json
{
    "id_peticion": "req-0009",
    "estado": "ok",
    "mensaje": "Proceso de lote terminado por causa externa",
    "datos": {
        "id_lote": "l-0001",
        "estado_lote": "matado",
        "causa": "terminado_externamente"
    }
}
```

Cuando se consulta el estado de un lote matado, la respuesta también incluye el campo `causa`:

```json
{
    "id_peticion": "req-0010",
    "estado": "ok",
    "mensaje": "Estado del lote consultado correctamente",
    "datos": {
        "id_lote": "l-0001",
        "estado_lote": "matado",
        "causa": "terminado_externamente"
    }
}
```

Ejemplo para listar:

```json
{
    "id_peticion": "req-0011",
    "servicio": "ejecutor",
    "operacion": "listar_lotes",
    "datos": {}
}
```

Respuesta:

```json
{
    "id_peticion": "req-0011",
    "estado": "ok",
    "mensaje": "Listado de procesos de lote",
    "datos": {
        "procesos": [
            {
                "id_lote": "l-0001",
                "estado_lote": "corriendo",
                "causa": null
            },
            {
                "id_lote": "l-0002",
                "estado_lote": "matado",
                "causa": "terminado_externamente"
            }
        ]
    }
}
```

---

## 7. Estados, control y errores

### 7.1 Máquinas de estado

**gesprog y gesfich**

```
iniciado ──► corriendo ──► suspendido
                │               │
                │    reasumir ◄─┘
                │
                ▼
            terminado
```

| Estado | Descripción |
|---|---|
| `iniciado` | El servicio arrancó pero aún no aceptó ninguna petición. |
| `corriendo` | Procesando peticiones normalmente. |
| `suspendido` | No acepta peticiones nuevas. Las peticiones recibidas se rechazan con `SERVICIO_SUSPENDIDO`. |
| `terminado` | El servicio finalizó su ejecución. |

**ctrllt**

```
iniciado ──► corriendo ──► terminando ──► terminado
```

| Estado | Descripción |
|---|---|
| `iniciado` | Arrancó, aún no enruta peticiones. |
| `corriendo` | Enrutando peticiones entre cliente y servicios. |
| `terminando` | Recibió `terminar_servicio`. Está enviando la señal de cierre a los servicios hijos y esperando que confirmen su fin. No acepta peticiones nuevas. |
| `terminado` | Todos los servicios hijos terminaron. `ctrllt` se apaga. |

**ejecutor**

```
iniciado ──► corriendo ──► suspendido
                │               │
                │    reasumir ◄─┘
                │
                ▼
            parando ──► terminado
```

| Estado | Descripción |
|---|---|
| `iniciado` | Arrancó, listo para recibir lotes. |
| `corriendo` | Aceptando y ejecutando lotes simultáneamente. |
| `suspendido` | No acepta lotes nuevos. Los lotes en ejecución continúan hasta terminar. |
| `parando` | Recibió `parar_ejecutor`. No acepta lotes nuevos. Espera que los lotes activos terminen antes de apagarse (cierre ordenado). |
| `terminado` | Todos los lotes activos terminaron. El ejecutor se apaga. |

La diferencia entre `suspendido` y `parando` es que `suspendido` es reversible (se puede reasumir), mientras que `parando` es el inicio del apagado definitivo.

**Estados de programas y ficheros:**

```text
activo, inactivo, borrado
```

**Estados de lotes:**

```text
pendiente, corriendo, terminado, fallido, matado
```

El campo `causa` en la respuesta de estado de un lote puede tomar los siguientes valores:

| Valor | Significado |
|---|---|
| `null` | El lote no ha terminado o terminó normalmente. |
| `"terminado_externamente"` | El lote fue matado mediante `matar_lote`. |
| `"error_ejecucion"` | El lote falló durante la ejecución de un programa. |

**Operaciones de control disponibles:**

| Operación | Aplica a | Descripción |
|---|---|---|
| `suspender_servicio` | gesprog, gesfich, ejecutor | Suspende el servicio temporalmente. |
| `reasumir_servicio` | gesprog, gesfich, ejecutor | Reactiva un servicio suspendido. |
| `terminar_servicio` | gesprog, gesfich, ctrllt | Termina el servicio definitivamente. |
| `parar_ejecutor` | ejecutor | Inicia el cierre ordenado del ejecutor. |

---

### 7.2 Apagado en cadena desde ctrllt

Cuando `ctrllt` recibe la operación `terminar_servicio` dirigida a sí mismo, antes de apagarse debe detener cada uno de los servicios según su máquina de estados:

1. Envía `suspender_servicio` a `gesprog`, `gesfich` y `ejecutor` para que dejen de aceptar nuevas peticiones.
2. Espera a que los lotes en ejecución del `ejecutor` terminen (o los mata si se requiere un apagado forzado).
3. Envía `terminar_servicio` a `gesprog` y `gesfich`.
4. Envía `parar_ejecutor` al `ejecutor`.
5. Se apaga a sí mismo.

Los datos persistentes (programas, ficheros y lotes registrados) se conservan entre ejecuciones en `aralmac`. Para eliminarlos es necesario ejecutar el script de limpieza con la opción de borrado de datos, o eliminarlos manualmente.

Errores principales:

| Código | Significado |
|---|---|
| `SERVICIO_INVALIDO` | El servicio no existe. |
| `OPERACION_INVALIDA` | La operación no existe para ese servicio. |
| `JSON_INVALIDO` | El mensaje no tiene formato JSON válido. |
| `DATOS_INCOMPLETOS` | Faltan campos obligatorios. |
| `PROGRAMA_NO_EXISTE` | El programa solicitado no existe. |
| `FICHERO_NO_EXISTE` | El fichero solicitado no existe. |
| `FICHERO_REQUERIDO` | Falta el fichero de entrada o de salida en `ejecutar_lote`. |
| `FICHERO_EN_USO` | Se intentó borrar un fichero que está siendo usado por un lote activo. |
| `LOTE_NO_EXISTE` | El lote solicitado no existe. |
| `EJECUTABLE_INVALIDO` | El ejecutable no existe o no es válido. |
| `REFERENCIA_INVALIDA` | Algún identificador enviado no existe. |
| `LISTA_PROGRAMAS_VACIA` | No se enviaron programas para ejecutar. |
| `SERVICIO_SUSPENDIDO` | El servicio está suspendido y no acepta nuevas peticiones. |
| `ERROR_INTERNO` | Error inesperado del servicio. |

---

## 8. Flujo de ejemplo completo

Este flujo muestra el ciclo completo de vida: registrar un programa, registrar los ficheros, ejecutar el lote y leer el resultado.

**Paso 1 — Registrar el programa**

```json
{
    "id_peticion": "req-0001",
    "servicio": "gesprog",
    "operacion": "registrar_programa",
    "datos": {
        "ejecutable": "/usr/bin/sort",
        "argumentos": ["-n"],
        "ambiente": {},
        "descripcion": "Ordena líneas numéricamente"
    },
    "timestamp": "2026-05-07T19:00:00Z"
}
```

Respuesta:

```json
{
    "id_peticion": "req-0001",
    "estado": "ok",
    "mensaje": "Programa registrado correctamente",
    "datos": { "id_programa": "p-0001" },
    "timestamp": "2026-05-07T19:00:00Z"
}
```

**Paso 2 — Crear el fichero de entrada con contenido**

```json
{
    "id_peticion": "req-0002",
    "servicio": "gesfich",
    "operacion": "crear_fichero",
    "datos": { "contenido": "3\n1\n2\n" },
    "timestamp": "2026-05-07T19:00:01Z"
}
```

Respuesta:

```json
{
    "id_peticion": "req-0002",
    "estado": "ok",
    "mensaje": "Fichero creado correctamente",
    "datos": { "id_fichero": "f-0001" },
    "timestamp": "2026-05-07T19:00:01Z"
}
```

**Paso 3 — Crear el fichero de salida vacío**

```json
{
    "id_peticion": "req-0003",
    "servicio": "gesfich",
    "operacion": "crear_fichero",
    "datos": { "contenido": "" },
    "timestamp": "2026-05-07T19:00:02Z"
}
```

Respuesta: `{ "id_fichero": "f-0002" }`

**Paso 4 — Ejecutar el lote**

```json
{
    "id_peticion": "req-0004",
    "servicio": "ejecutor",
    "operacion": "ejecutar_lote",
    "datos": {
        "entrada": "f-0001",
        "salida": "f-0002",
        "programas": ["p-0001"]
    },
    "timestamp": "2026-05-07T19:00:03Z"
}
```

Respuesta inmediata:

```json
{
    "id_peticion": "req-0004",
    "estado": "ok",
    "mensaje": "Proceso de lote iniciado correctamente",
    "datos": { "id_lote": "l-0001", "estado_lote": "corriendo" },
    "timestamp": "2026-05-07T19:00:03Z"
}
```

Notificación cuando termina (misma `id_peticion`):

```json
{
    "id_peticion": "req-0004",
    "estado": "ok",
    "mensaje": "Proceso de lote finalizado",
    "datos": { "id_lote": "l-0001", "estado_lote": "terminado", "causa": null },
    "timestamp": "2026-05-07T19:00:04Z"
}
```

**Paso 5 — Leer el fichero de salida**

```json
{
    "id_peticion": "req-0005",
    "servicio": "gesfich",
    "operacion": "leer_fichero",
    "datos": { "id_fichero": "f-0002" },
    "timestamp": "2026-05-07T19:00:05Z"
}
```

Respuesta:

```json
{
    "id_peticion": "req-0005",
    "estado": "ok",
    "mensaje": "Fichero encontrado",
    "datos": { "id_fichero": "f-0002", "contenido": "1\n2\n3\n" },
    "timestamp": "2026-05-07T19:00:05Z"
}
```

---

## 9. Decisiones de diseño

Para esta entrega se toman estas decisiones:

1. Todos los mensajes serán JSON.
2. Las peticiones tendrán un `id_peticion`.
3. Las respuestas conservarán el mismo `id_peticion`.
4. Los programas usarán identificadores `p-XXXX`.
5. Los ficheros usarán identificadores `f-XXXX`.
6. Los lotes usarán identificadores `l-XXXX`.
7. `ctrllt` funcionará como pasarela opcional; el cliente puede conectarse directamente a los servicios.
8. `aralmac` no se fija todavía; después puede implementarse con archivos, base de datos o memoria. El acceso se realiza mediante una biblioteca interna compartida, no a través de las tuberías de los servicios.
9. En Linux se usa el modelo half-duplex con una tubería de respuesta única por servicio. En Windows 11 se usa obligatoriamente el modelo full-duplex.
10. `ejecutar_lote` recibirá identificadores registrados, no rutas directas. La operación es no bloqueante: retorna el `id_lote` inmediatamente y el lote corre en segundo plano.
11. El ejecutor puede gestionar múltiples lotes de forma simultánea, cada uno en su propio hilo.
12. `matar_lote` establece el estado del lote en `matado` e incluye el campo `causa: "terminado_externamente"` en las respuestas de estado posteriores.
13. Ambos ficheros (entrada y salida) son obligatorios en `ejecutar_lote`.
14. Antes de iniciar el sistema se debe ejecutar el script de limpieza para eliminar tuberías huérfanas.
15. Los datos persisten entre ejecuciones. Para borrarlos es necesario hacerlo explícitamente.
16. Intentar borrar un fichero que está en uso por un lote activo retorna error `FICHERO_EN_USO`.

---

## 10. Primera entrega

Esta primera entrega incluye únicamente el diseño de la API. No incluye implementación de código.

El documento define:

- Componentes del sistema y sus responsabilidades.
- Parámetros de arranque por línea de comandos de cada componente.
- Comunicación por tuberías nombradas con modelo half-duplex en Linux y full-duplex obligatorio en Windows 11.
- Procedimiento de limpieza antes de arrancar el sistema.
- Formato de mensajes JSON con `id_peticion`, `timestamp` y campo `detalles` en errores.
- Operaciones completas de `gesprog`, `gesfich` y `ejecutor`.
- Comportamiento asíncrono de `ejecutar_lote` con respuesta inmediata y notificación de fin.
- Soporte de múltiples lotes simultáneos en el ejecutor.
- Campo `causa` en el estado de los lotes para indicar terminación normal, externa o por error.
- Máquinas de estado de todos los componentes, incluyendo estados `terminando` en `ctrllt` y `parando` en el ejecutor.
- Procedimiento de apagado en cadena desde `ctrllt`.
- Flujo de ejemplo completo end-to-end.
- Códigos de error con campo `detalles` para facilitar el diagnóstico.

Con esto dejamos definido el contrato de comunicación entre los procesos. La implementación futura podrá hacerse en Linux y Windows 11 manteniendo la misma API y cambiando solo la forma de manejar las tuberías nombradas.
