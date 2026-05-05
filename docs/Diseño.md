
# Diseño de la API
# Maria Clara Medina y Franchesca Garcia Tabares

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
| `cliente` | Envía solicitudes al sistema. No se implementa en esta entrega. |
| `ctrllt` | Recibe peticiones y las redirige al servicio correcto. |
| `gesprog` | Administra programas registrados. |
| `gesfich` | Administra ficheros registrados. |
| `ejecutor` | Ejecuta y controla procesos de lote. |
| `aralmac` | Área donde se almacenan programas, ficheros e información del sistema. |

Flujo general:

```text
cliente -> ctrllt -> gesprog
                 -> gesfich
                 -> ejecutor
```

`ctrllt` actúa como pasarela. Recibe una petición JSON, revisa el servicio solicitado y la envía al componente correspondiente.

---

## 3. Comunicación y sistemas operativos

Los procesos se comunicarán mediante tuberías nombradas. Cada mensaje enviado por una tubería será un JSON.

El diseño contempla dos casos:

- `full-duplex`: una tubería permite enviar y recibir.
- `half-duplex`: se usan dos tuberías, una para petición y otra para respuesta.

Ejemplo:

```text
cliente ---- petición ----> ctrllt
cliente <--- respuesta ---- ctrllt
```

La API será la misma en Linux y Windows 11. Lo que cambia es la implementación de las tuberías.

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

---

### 3.1 Manejo de múltiples clientes y tuberías

El sistema puede recibir peticiones de varios clientes. Como las tuberías funcionan como un canal compartido, los mensajes se atienden de forma secuencial según van llegando al buffer de la tubería.

Para diferenciar las solicitudes y respuestas se usan dos campos:

- `id_peticion`: identifica una petición específica.
- `id_cliente`: identifica al cliente que envió la petición.

De esta forma, aunque varios clientes estén usando la misma tubería, cada cliente puede reconocer cuáles respuestas le corresponden.

No se propone crear una tubería diferente para cada cliente, porque eso haría más complejo el manejo de nombres de tuberías. La propuesta es mantener una tubería de comunicación por servicio y usar los identificadores dentro del JSON.

En una implementación futura, el control o los servicios podrían usar lectura no bloqueante, `select`, `poll` o hilos para revisar las tuberías sin quedarse bloqueados esperando una sola respuesta.

---

### 3.2 Responsabilidad de creación y orden de arranque

Cada servicio será responsable de crear las tuberías que usa para recibir peticiones. Por ejemplo:

- `gesprog` crea sus tuberías de comunicación.
- `gesfich` crea sus tuberías de comunicación.
- `ejecutor` crea sus tuberías de comunicación.
- `ctrllt` se conecta a las tuberías de los servicios para redirigir las solicitudes.

El orden recomendado de arranque es desde los procesos más internos hacia afuera:

```text
1. aralmac o estructura de almacenamiento
2. gesprog, gesfich y ejecutor
3. ctrllt
4. cliente
```
---

## 4. Estructura base de los mensajes

Todas las peticiones tendrán una estructura común en formato JSON. Cada mensaje incluye un identificador de petición y un identificador de cliente para poder relacionar la respuesta con quien hizo la solicitud.

```json
{
    "id_peticion": "req-0001",
    "id_cliente": "cli-0001",
    "servicio": "nombre_servicio",
    "operacion": "nombre_operacion",
    "datos": {}
}
```

Respuesta exitosa:

```json
{
    "id_peticion": "req-0001",
    "id_cliente": "cli-0001",
    "estado": "ok",
    "mensaje": "Operación realizada correctamente",
    "datos": {}
}
```

Respuesta con error:

```json
{
    "id_peticion": "req-0001",
    "id_cliente": "cli-0001",
    "estado": "error",
    "mensaje": "Descripción del error",
    "codigo": "CODIGO_ERROR"
}
```

---

## 5. Servicios de la API

En esta sección se definen los servicios principales y las operaciones que acepta cada uno. Para no repetir demasiado, primero se muestran las operaciones en tablas y luego algunos ejemplos JSON de las peticiones más importantes.

---

### 5.1 gesprog

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
| `registrar_programa` | `{ "ejecutable": "/usr/bin/wc", "argumentos": ["-l"], "ambiente": { "LANG": "es_CO.UTF-8" }, "descripcion": "Cuenta líneas" }` | Retorna `id_programa`. |
| `leer_programa` | `{ "id_programa": "p-0001" }` | Retorna los datos del programa. Si no se envía `id_programa`, lista todos los programas registrados. |
| `listar_programas` | `{}` | Lista todos los programas registrados. |
| `actualizar_programa` | `{ "id_programa": "p-0001", "ejecutable": "/usr/bin/wc", "argumentos": ["-w"], "ambiente": {}, "descripcion": "Cuenta palabras" }` | Actualiza el programa. |
| `borrar_programa` | `{ "id_programa": "p-0001" }` | Borra el programa. |
| `suspender_servicio` | `{}` | Cambia el servicio a suspendido. |
| `reasumir_servicio` | `{}` | Cambia el servicio a corriendo. |
| `terminar_servicio` | `{}` | Cambia el servicio a terminado. |

#### Máquina de estados de gesprog

```
  [Inicio] --> [Corriendo] <--> [Suspendido]
                    |
                    v
              [Terminado]
```

Transiciones:

| Desde | Evento | Hacia |
|---|---|---|
| Inicio | arranque | Corriendo |
| Corriendo | `suspender_servicio` | Suspendido |
| Suspendido | `reasumir_servicio` | Corriendo |
| Corriendo | `terminar_servicio` | Terminado |
| Suspendido | `terminar_servicio` | Terminado |

En estado **Corriendo** se aceptan: `registrar_programa`, `leer_programa`, `listar_programas`, `actualizar_programa`, `borrar_programa`. En estado **Suspendido** solo se acepta `leer_programa`. En estado **Terminado** no se acepta ninguna operación.

#### Ejemplos JSON

Registrar programa:

```json
{
    "id_peticion": "req-0001",
    "id_cliente": "cli-0001",
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
    "id_cliente": "cli-0001",
    "estado": "ok",
    "mensaje": "Programa registrado correctamente",
    "datos": {
        "id_programa": "p-0001"
    }
}
```

Leer programa (con identificador):

```json
{
    "id_peticion": "req-0002",
    "id_cliente": "cli-0001",
    "servicio": "gesprog",
    "operacion": "leer_programa",
    "datos": {
        "id_programa": "p-0001"
    }
}
```

Respuesta:

```json
{
    "id_peticion": "req-0002",
    "id_cliente": "cli-0001",
    "estado": "ok",
    "mensaje": "Programa encontrado",
    "datos": {
        "id_programa": "p-0001",
        "ejecutable": "/usr/bin/wc",
        "argumentos": ["-l"],
        "ambiente": {
            "LANG": "es_CO.UTF-8"
        },
        "descripcion": "Cuenta la cantidad de líneas del fichero de entrada",
        "estado_programa": "activo"
    }
}
```

Leer programa (sin identificador — equivale a listar todos):

```json
{
    "id_peticion": "req-0002b",
    "id_cliente": "cli-0001",
    "servicio": "gesprog",
    "operacion": "leer_programa",
    "datos": {}
}
```

Respuesta:

```json
{
    "id_peticion": "req-0002b",
    "id_cliente": "cli-0001",
    "estado": "ok",
    "mensaje": "Listado de programas registrados",
    "datos": {
        "programas": [
            {
                "id_programa": "p-0001",
                "ejecutable": "/usr/bin/wc",
                "descripcion": "Cuenta la cantidad de líneas del fichero de entrada",
                "estado_programa": "activo"
            }
        ]
    }
}
```

Borrar programa:

```json
{
    "id_peticion": "req-0003",
    "id_cliente": "cli-0001",
    "servicio": "gesprog",
    "operacion": "borrar_programa",
    "datos": {
        "id_programa": "p-0001"
    }
}
```

Respuesta:

```json
{
    "id_peticion": "req-0003",
    "id_cliente": "cli-0001",
    "estado": "ok",
    "mensaje": "Programa borrado correctamente",
    "datos": {
        "id_programa": "p-0001"
    }
}
```

---

### 5.2 gesfich

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
| `crear_fichero` | `{ "contenido_base64": "dW5vCmRvcwp0cmVzCg==" }` o `{}` | Retorna `id_fichero`. Por defecto crea el fichero vacío; el campo contenido_base64 es opcional. |
| `leer_fichero` | `{ "id_fichero": "f-0001" }` | Retorna el contenido del fichero. Si no se envía `id_fichero`, lista todos los ficheros registrados. |
| `listar_ficheros` | `{}` | Lista los ficheros registrados. |
| `actualizar_fichero` | `{ "id_fichero": "f-0001", "ruta_fichero": "./datos/nuevo.txt" }` | Reemplaza el contenido almacenado en `aralmac` por el contenido del fichero externo indicado. |
| `borrar_fichero` | `{ "id_fichero": "f-0001" }` | Borra el fichero. |
| `suspender_servicio` | `{}` | Cambia el servicio a suspendido. |
| `reasumir_servicio` | `{}` | Cambia el servicio a corriendo. |
| `terminar_servicio` | `{}` | Cambia el servicio a terminado. |

#### Máquina de estados de gesfich

```
  [Inicio] --> [Corriendo] <--> [Suspendido]
                    |
                    v
              [Terminado]
```

Transiciones:

| Desde | Evento | Hacia |
|---|---|---|
| Inicio | arranque | Corriendo |
| Corriendo | `suspender_servicio` | Suspendido |
| Suspendido | `reasumir_servicio` | Corriendo |
| Corriendo | `terminar_servicio` | Terminado |
| Suspendido | `terminar_servicio` | Terminado |

En estado **Corriendo** se aceptan todas las operaciones. En estado **Suspendido** solo se acepta `leer_fichero`. En estado **Terminado** no se acepta ninguna operación.

#### Ejemplos JSON

Crear fichero:

```json
{
    "id_peticion": "req-0003",
    "id_cliente": "cli-0001",
    "servicio": "gesfich",
    "operacion": "crear_fichero",
    "datos": {
        "nombre": "entrada.txt",
        "contenido_base64": "dW5vCmRvcwp0cmVzCg=="
    }
}
```

Respuesta:

```json
{
    "id_peticion": "req-0003",
    "id_cliente": "cli-0001",
    "estado": "ok",
    "mensaje": "Fichero creado correctamente",
    "datos": {
        "id_fichero": "f-0001"
    }
}
```

Leer fichero (con identificador):

```json
{
    "id_peticion": "req-0004",
    "id_cliente": "cli-0001",
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
    "id_cliente": "cli-0001",
    "estado": "ok",
    "mensaje": "Fichero encontrado",
    "datos": {
        "id_fichero": "f-0001",
        "nombre": "entrada.txt",
        "contenido_base64": "dW5vCmRvcwp0cmVzCg=="
    }
}
```

Leer fichero (sin identificador — equivale a listar todos):

```json
{
    "id_peticion": "req-0005b",
    "id_cliente": "cli-0001",
    "servicio": "gesfich",
    "operacion": "leer_fichero",
    "datos": {}
}
```

Respuesta:

```json
{
    "id_peticion": "req-0005b",
    "id_cliente": "cli-0001",
    "estado": "ok",
    "mensaje": "Listado de ficheros registrados",
    "datos": {
        "ficheros": [
            {
                "id_fichero": "f-0001",
                "estado_fichero": "activo"
            },
            {
                "id_fichero": "f-0002",
                "estado_fichero": "activo"
            }
        ]
    }
}
```

Actualizar fichero:

```json
{
    "id_peticion": "req-0006",
    "id_cliente": "cli-0001",
    "servicio": "gesfich",
    "operacion": "actualizar_fichero",
    "datos": {
        "id_fichero": "f-0001",
        "ruta_fichero": "./datos/entrada_actualizada.txt"
    }
}
```

Respuesta:

```json
{
    "id_peticion": "req-0006",
    "id_cliente": "cli-0001",
    "estado": "ok",
    "mensaje": "Fichero actualizado correctamente",
    "datos": {
        "id_fichero": "f-0001"
    }
}
```

Borrar fichero:

```json
{
    "id_peticion": "req-0007",
    "id_cliente": "cli-0001",
    "servicio": "gesfich",
    "operacion": "borrar_fichero",
    "datos": {
        "id_fichero": "f-0001"
    }
}
```

Respuesta:

```json
{
    "id_peticion": "req-0007",
    "id_cliente": "cli-0001",
    "estado": "ok",
    "mensaje": "Fichero borrado correctamente",
    "datos": {
        "id_fichero": "f-0001"
    }
}
```

---

### 5.3 ejecutor

`ejecutor` administra los procesos de lote. Cada lote se identifica con el formato:

```text
l-XXXX
```

Ejemplo:

```text
l-0001
```

Un lote recibe un fichero de entrada, un fichero de salida y una lista ordenada de programas.

Ejemplo conceptual:

```text
f-0001 -> p-0001 -> p-0002 -> f-0002
```

| Operación | Datos esperados | Respuesta principal |
|---|---|---|
| `ejecutar_lote` | `{ "entrada": "f-0001", "salida": "f-0002", "programas": ["p-0001", "p-0002"] }` | Retorna `id_lote` y estado inicial. |
| `estado_lote` | `{ "id_lote": "l-0001" }` | Retorna el estado del lote. Si no se envía `id_lote`, lista todos los lotes. |
| `listar_lotes` | `{}` | Lista todos los procesos de lote. |
| `matar_lote` | `{ "id_lote": "l-0001" }` | Termina forzosamente un lote en ejecución. |
| `suspender_servicio` | `{}` | Cambia el ejecutor a suspendido. |
| `reasumir_servicio` | `{}` | Cambia el ejecutor a corriendo. |
| `parar_ejecutor` | `{}` | Detiene el ejecutor. |

#### Máquina de estados del ejecutor

```
  [Inicio] --> [Corriendo] <--> [Suspendido]
                    |
                    v
                [Parar] --> [Terminado]
```

Transiciones:

| Desde | Evento | Hacia |
|---|---|---|
| Inicio | arranque | Corriendo |
| Corriendo | `suspender_servicio` | Suspendido |
| Suspendido | `reasumir_servicio` | Corriendo |
| Corriendo | `parar_ejecutor` (procesos = 0) | Parar → Terminado |
| Corriendo | `parar_ejecutor` (procesos > 0) | espera a que terminen → Terminado |

En estado **Corriendo** se aceptan: `ejecutar_lote`, `estado_lote`, `listar_lotes`, `matar_lote`. En estado **Suspendido** solo se aceptan: `estado_lote`, `listar_lotes`. En estado **Parar** o **Terminado** no se acepta ninguna operación nueva.

#### Máquina de estados de un lote individual

```
[pendiente] --> [corriendo] --> [terminado]
                    |
                    +--> [fallido]
                    |
                    +--> [matado]
```

| Estado | Descripción |
|---|---|
| `pendiente` | El lote fue recibido pero aún no comenzó a ejecutarse. |
| `corriendo` | El lote está en ejecución. |
| `terminado` | El lote finalizó correctamente. |
| `fallido` | El lote terminó con error. |
| `matado` | El lote fue detenido forzosamente con `matar_lote`. |

#### Ejemplos JSON

Ejecutar lote:

```json
{
    "id_peticion": "req-0008",
    "id_cliente": "cli-0001",
    "servicio": "ejecutor",
    "operacion": "ejecutar_lote",
    "datos": {
        "entrada": "f-0001",
        "salida": "f-0002",
        "programas": ["p-0001", "p-0002"]
    }
}
```

Respuesta exitosa:

```json
{
    "id_peticion": "req-0008",
    "id_cliente": "cli-0001",
    "estado": "ok",
    "mensaje": "Proceso de lote iniciado correctamente",
    "datos": {
        "id_lote": "l-0001",
        "estado_lote": "corriendo"
    }
}
```

Respuesta de error (fichero o programa no existe):

```json
{
    "id_peticion": "req-0008",
    "id_cliente": "cli-0001",
    "estado": "error",
    "mensaje": "El fichero de entrada no existe",
    "codigo": "FICHERO_NO_EXISTE"
}
```

```json
{
    "id_peticion": "req-0008",
    "id_cliente": "cli-0001",
    "estado": "error",
    "mensaje": "Uno o más programas de la lista no existen",
    "codigo": "REFERENCIA_INVALIDA"
}
```

Consultar estado de un lote:

```json
{
    "id_peticion": "req-0009",
    "id_cliente": "cli-0001",
    "servicio": "ejecutor",
    "operacion": "estado_lote",
    "datos": {
        "id_lote": "l-0001"
    }
}
```

Respuesta:

```json
{
    "id_peticion": "req-0009",
    "id_cliente": "cli-0001",
    "estado": "ok",
    "mensaje": "Estado del lote consultado correctamente",
    "datos": {
        "id_lote": "l-0001",
        "estado_lote": "corriendo",
        "entrada": "f-0001",
        "salida": "f-0002",
        "programas": ["p-0001", "p-0002"]
    }
}
```

Consultar estado sin identificador (equivale a listar todos):

```json
{
    "id_peticion": "req-0009b",
    "id_cliente": "cli-0001",
    "servicio": "ejecutor",
    "operacion": "estado_lote",
    "datos": {}
}
```

Matar lote:

```json
{
    "id_peticion": "req-0010",
    "id_cliente": "cli-0001",
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
    "id_peticion": "req-0010",
    "id_cliente": "cli-0001",
    "estado": "ok",
    "mensaje": "Proceso de lote terminado forzosamente",
    "datos": {
        "id_lote": "l-0001",
        "estado_lote": "matado"
    }
}
```

Listar todos los lotes:

```json
{
    "id_peticion": "req-0011",
    "id_cliente": "cli-0001",
    "servicio": "ejecutor",
    "operacion": "listar_lotes",
    "datos": {}
}
```

Respuesta:

```json
{
    "id_peticion": "req-0011",
    "id_cliente": "cli-0001",
    "estado": "ok",
    "mensaje": "Listado de procesos de lote",
    "datos": {
        "procesos": [
            {
                "id_lote": "l-0001",
                "estado_lote": "terminado"
            },
            {
                "id_lote": "l-0002",
                "estado_lote": "matado"
            }
        ]
    }
}
```

---

## 6. Estados, control y errores

Estados de servicios:

```text
iniciado, corriendo, suspendido, terminado
```

Estados de programas y ficheros:

```text
activo, inactivo, borrado
```

Estados de lotes:

```text
pendiente, corriendo, terminado, fallido, matado
```

Operaciones de control:

| Operación | Descripción |
|---|---|
| `suspender_servicio` | Suspende temporalmente un servicio. |
| `reasumir_servicio` | Reactiva un servicio suspendido. |
| `terminar_servicio` | Termina un servicio (gesprog / gesfich). |
| `parar_ejecutor` | Detiene el ejecutor esperando a que los lotes activos finalicen. |

Errores principales:

| Código | Significado |
|---|---|
| `SERVICIO_INVALIDO` | El servicio no existe. |
| `OPERACION_INVALIDA` | La operación no existe para ese servicio. |
| `JSON_INVALIDO` | El mensaje no tiene formato JSON válido. |
| `DATOS_INCOMPLETOS` | Faltan campos obligatorios. |
| `PROGRAMA_NO_EXISTE` | El programa solicitado no existe. |
| `FICHERO_NO_EXISTE` | El fichero solicitado no existe. |
| `LOTE_NO_EXISTE` | El lote solicitado no existe. |
| `EJECUTABLE_INVALIDO` | El ejecutable no existe o no es válido. |
| `REFERENCIA_INVALIDA` | Algún identificador enviado no existe. |
| `LISTA_PROGRAMAS_VACIA` | No se enviaron programas para ejecutar. |
| `LOTE_NO_ACTIVO` | Se intentó matar un lote que ya terminó o fue matado. |
| `SERVICIO_SUSPENDIDO` | La operación no está permitida mientras el servicio está suspendido. |
| `ERROR_INTERNO` | Error inesperado del servicio. |

Ejemplo de error por servicio suspendido:

```json
{
    "id_peticion": "req-0012",
    "id_cliente": "cli-0001",
    "estado": "error",
    "mensaje": "El servicio está suspendido y no puede procesar esta operación",
    "codigo": "SERVICIO_SUSPENDIDO"
}
```

---

## 7. Decisiones de diseño

Para esta entrega se toman estas decisiones:

1. Todos los mensajes serán JSON.
2. Las peticiones tendrán un `id_peticion`.
3. Las respuestas conservarán el mismo `id_peticion`.
4. Los programas usarán identificadores `p-XXXX`.
5. Los ficheros usarán identificadores `f-XXXX`.
6. Los lotes usarán identificadores `l-XXXX`.
7. `ctrllt` funcionará como pasarela.
8. `aralmac` no se fija todavía; después puede implementarse con archivos, base de datos o memoria.
9. La API será igual para Linux y Windows 11.
10. `ejecutar_lote` recibirá identificadores registrados, no rutas directas.
11. `crear_fichero` acepta un campo `contenido_base64` opcional. Si no se envía, el fichero se crea vacío.
12. `leer_programa`, `leer_fichero` y `estado_lote` tienen comportamiento dual: con identificador retornan el recurso específico; sin identificador listan todos los recursos del tipo correspondiente.
13. Cada mensaje incluirá `id_cliente` para facilitar la identificación de respuestas cuando existan varios clientes usando la misma tubería.
14. Cada servicio será responsable de crear sus propias tuberías de comunicación.
15. El orden recomendado de arranque será: almacenamiento, servicios, control y cliente.
16. El contenido de los ficheros viajará dentro del JSON usando Base64 mediante el campo `contenido_base64`.
17. En estado suspendido, las operaciones principales no se encolan; se rechazan con un error `SERVICIO_SUSPENDIDO`, excepto las operaciones permitidas para consultar o reactivar el servicio.

---

## 8. Primera entrega

Esta primera entrega incluye únicamente el diseño de la API. No incluye implementación de código.

El documento define:

- Componentes del sistema.
- Comunicación por tuberías nombradas.
- Diseño para Linux y Windows 11.
- Formato de mensajes JSON.
- Operaciones de `gesprog`, `gesfich` y `ejecutor`.
- Máquinas de estados de cada servicio y de los lotes individuales.
- Estados, errores y operaciones de control.

Con esto queda definido el contrato de comunicación entre los procesos. La implementación futura podrá hacerse en Linux y Windows 11 manteniendo la misma API y cambiando solo la forma de manejar las tuberías nombradas.
