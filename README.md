# Ejecutor de Lotes — Práctica VII

Sistemas Operativos — Universidad EAFIT
Asignatura ST0257
Segunda y tercera entrega.

## Resumen

Sistema que simula la ejecución por lotes propia de un sistema operativo
de mainframe. Está compuesto por cinco procesos que se comunican
únicamente mediante tuberías nombradas e intercambian mensajes JSON:

| Proceso  | Rol |
|---|---|
| `cliente`  | Interfaz interactiva del usuario. |
| `ctrllt`   | Pasarela: enruta las peticiones a los servicios y devuelve las respuestas. |
| `gesfich`  | CRUD de ficheros sobre la región **aralmac**. |
| `gesprog`  | CRUD de programas: copia el ejecutable en `aralmac/programas/` y guarda sus metadatos (argumentos, variables de entorno). |
| `ejecutor` | Lanza, controla y mata procesos de lotes. |

El proyecto está escrito en **Python 3** y funciona tanto en **Linux**
como en **Windows 11**. El detalle del diseño está en
[`docs/Diseño.md`](docs/Diseño.md).

## Requisitos

- Python 3.8 o superior.
- En Windows, instalar `pywin32`:
  ```powershell
  pip install pywin32
  ```

## Cómo ejecutar

### En Linux

```bash
# Arrancar los cuatro servicios (se queda en primer plano)
bash scripts/arrancar_linux.sh

# En otra terminal, lanzar el cliente
python3 src/cliente.py -c cli_pet
```

Una vez en el cliente, escriba `ayuda` para ver los comandos
disponibles. Para apagar todo el sistema escriba `apagar`.

Para borrar tuberías y contenido del aralmac y empezar limpio:

```bash
bash scripts/limpiar_linux.sh
```

### En Windows 11

```powershell
# Arrancar los servicios (abre cuatro ventanas)
powershell -ExecutionPolicy Bypass -File scripts\arrancar_windows.ps1

# En otra terminal:
python src\cliente.py -c cli_pet
```

## Estructura del repositorio

```
ejecutor-lotes/
├── docs/Diseño.md            <- documento de diseño (entregable)
├── src/                      <- código fuente
├── aralmac/                  <- repositorio de ficheros y programas
├── scripts/                  <- scripts de arranque y pruebas
└── README.md
```

## Pruebas

En Linux hay dos scripts que verifican el flujo completo y los casos
de error:

```bash
bash scripts/test_linux.sh     # caso feliz: crear, ejecutar, leer salida
bash scripts/test_errores.sh   # errores y suspender/reasumir
```

## Autores

Práctica realizada en pareja (entrega para Linux y Windows 11).
