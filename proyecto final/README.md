# TP Integrador - Programación sobre Redes 

Aplicación Cliente-Servidor concurrente desarrollada en **Python** utilizando **sockets TCP**, multihilos (`threading`), persistencia en **MySQL** y consumo de la **API REST pública de GitHub**.

El sistema permite autenticar múltiples clientes simultáneos contra una base de datos con contraseñas encriptadas en **SHA-256**, mantener un chat bidireccional en tiempo real entre clientes y servidor, y ejecutar comandos especiales con `/`.

---

## Estructura del Repositorio

```text
├── base_datos.sql     # Script SQL para crear la base de datos 'tp_redes', tablas y usuarios de prueba
├── servidor.py        # Servidor TCP concurrente, validación en MySQL, consola de chat y comandos
├── cliente.py         # Cliente TCP interactivo con hilo de escucha en tiempo real
├── requirements.txt   # Dependencias externas de Python necesarias para ejecutar el proyecto
└── README.md          # Documentación general, instalación y guía de comandos
```

---

## Características Técnicas

* **Concurrencia segura:** El servidor atiende a cada cliente en un hilo independiente (`threading.Thread`) y protege el registro compartido de usuarios conectados mediante un cerrojo (`threading.Lock`) para evitar condiciones de carrera.
* **Protocolo de comunicación estructurado:** Todos los mensajes entre cliente y servidor viajan serializados en **JSON** y delimitados por salto de línea (`\n`), evitando problemas de fragmentación o pegado de paquetes en el flujo TCP.
* **Seguridad en autenticación:** Las contraseñas se almacenan como hash hexadecimal **SHA-256** (`hashlib.sha256` en Python / `SHA2(..., 256)` en MySQL) y se verifican mediante consultas SQL parametrizadas (`%s`) para prevenir inyección SQL.
* **Integración con GitHub:** Los comandos `/repos` y `/followers` consultan la API de GitHub (`api.github.com`) mediante `requests` y almacenan los resultados en MySQL en lote (`executemany`).

---

## Requisitos Previos

* **Python 3.8** o superior.
* **MySQL** o **MariaDB** activo en el puerto `3306` (por ejemplo, mediante XAMPP, WAMP o servicio local).
* Conexión a Internet (necesaria para las consultas a `api.github.com`).

---

## Instalación y Configuración

1. **Clonar o descargar el repositorio** y ubicarse en la carpeta del proyecto:
   ```bash
   cd nombre-del-repositorio
   ```

2. **(Opcional) Crear y activar un entorno virtual:**
   ```bash
   python -m venv venv
   # En Windows:
   venv\Scripts\activate
   # En Linux / macOS:
   source venv/bin/activate
   ```

3. **Instalar las dependencias de Python:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Crear e inicializar la base de datos MySQL:**
   * Iniciá el servicio de MySQL.
   * Importá el archivo `base_datos.sql` desde phpMyAdmin o ejecutalo desde la terminal:
     ```bash
     mysql -u root < base_datos.sql
     ```

5. **Verificar credenciales de MySQL en `servidor.py`:**
   Si tu servidor MySQL utiliza contraseña o un puerto distinto al `3306`, edita el diccionario `DB_CONFIG` al inicio de `servidor.py`:
   ```python
   DB_CONFIG = {
       "host": "localhost",
       "port": 3306,
       "user": "root",
       "password": "",
       "database": "tp_redes",
       "charset": "utf8mb4"
   }
   ```

---

## Ejecución

### 1. Iniciar el Servidor
En una terminal, ejecutá:
```bash
python servidor.py
```
El servidor quedará escuchando conexiones en `127.0.0.1:5000` y habilitará su consola interactiva para enviar mensajes.

### 2. Iniciar uno o más Clientes
En otra(s) terminal(es), ejecutá:
```bash
python cliente.py
```
Al conectarse, el cliente solicitará **Usuario** y **Contraseña**. Si las credenciales son incorrectas o el usuario ya tiene una sesión activa, el servidor informará el error y cerrará la conexión.

### Usuarios de Prueba Precargados
El script `base_datos.sql` incluye los siguientes usuarios listos para iniciar sesión:

| Usuario | Contraseña |
| :--- | :--- |
| `admin` | `admin123` |
| `oriana` | `1234` |
| `alumno1` | `redes2026` |
| `alumno2` | `clave456` |

---

## Guía de Uso y Comandos

### Comandos del Cliente (precedidos por `/`)

Una vez autenticado, el cliente puede escribir texto libre para chatear con el servidor o ejecutar cualquiera de los siguientes comandos:

| Comando | Descripción | Ejemplo de uso |
| :--- | :--- | :--- |
| `/repos <usuario>` | Consulta los repositorios públicos de `<usuario>` en GitHub y los guarda en la tabla `repositorios` de MySQL. | `/repos octocat` |
| `/followers <usuario>` | Consulta los seguidores de `<usuario>` en GitHub y los guarda en la tabla `followers` de MySQL. | `/followers torvalds` |
| `/hora` | Solicita y muestra la fecha y hora actual del servidor. | `/hora` |
| `/todos "mensaje"` | Difunde un mensaje global a todos los clientes conectados en ese momento. | `/todos "Hola a todos"` |
| `/usuarios` | Devuelve la cantidad y la lista de todos los usuarios conectados actualmente. | `/usuarios` |
| `/adios` | Envía un mensaje de despedida, cierra la sesión en el servidor y desconecta al cliente. | `/adios` |

### Chat desde la Consola del Servidor

Mientras el servidor está en ejecución, el operador puede enviar mensajes directamente desde su consola:

* **Mensaje global (a todos los clientes conectados):**
  Escribí cualquier texto y presioná `Enter`.
  ```text
  Hola a todos, el servidor entrará en mantenimiento en 10 minutos.
  ```
* **Mensaje privado (a un cliente específico):**
  Escribí `@usuario` seguido del mensaje.
  ```text
  @oriana Tu consulta de repositorios se procesó correctamente.
  ```