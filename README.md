# Ejecutor de lotes

**Curso:** Sistemas Operativos 
Universidad EAFIT  
**Integrantes:**
- Maria Clara Medina
- Franchesca Garcia Tabares

---

## Primera entrega

Esta primera entrega consiste en el diseño de la API del sistema. No se incluye implementación de código fuente.

El documento principal de la entrega se encuentra en:

[docs/Diseño.md](docs/Diseño.md)

---

## Descripción

El sistema simula un ejecutor de procesos por lotes inspirado en los sistemas de mainframe. Se registran programas y ficheros en un área de almacenamiento compartida, y luego se ejecutan tareas encadenando esos recursos:

```text
fichero_entrada → programa_1 → programa_2 → ... → fichero_salida
```

---

## Componentes principales

| Componente | Responsabilidad |
|---|---|
| `cliente` | Envía peticiones al sistema. Puede conectarse a `ctrllt` o directamente a los servicios. |
| `ctrllt` | Recibe peticiones y las redirige al servicio correspondiente (pasarela opcional). |
| `gesprog` | Gestiona los programas registrados. |
| `gesfich` | Gestiona los ficheros registrados. |
| `ejecutor` | Ejecuta procesos de lote de forma concurrente. |
| `aralmac` | Área de almacenamiento compartida, accedida mediante una biblioteca interna. |

---

## Comunicación

La comunicación entre procesos se realiza mediante tuberías nombradas con mensajes en formato JSON. El modelo varía según el sistema operativo:

- **Linux:** tuberías half-duplex (dos tuberías por conexión: una de entrada, una de respuesta compartida).
- **Windows 11:** tuberías full-duplex obligatorio (una sola tubería bidireccional por instancia).

---

## Estructura del repositorio

```text
.
└── docs/
    └── Diseño.md       ← Documento principal de la primera entrega
```

---

## Sistemas operativos considerados

El diseño contempla una futura implementación en Linux y Windows 11, manteniendo la misma API en ambos y cambiando únicamente la forma de manejar las tuberías nombradas.
