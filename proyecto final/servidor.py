import socket  # Modulo para crear conexiones de red (sockets TCP)
import threading  # Modulo para trabajar con hilos (varios clientes a la vez)
import hashlib  # Hashear contraseñas
import json
from datetime import datetime
import mysql.connector  # Base de datos
from mysql.connector import Error
import requests  # Para hacer peticiones http

# Configuración de red
HOST = "127.0.0.1"
PORT = 5000

# Configuración de la base de datos MySQL
DB_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "",  # contraseña de MySQL si corresponde
    "database": "tp_redes",
    "charset": "utf8mb4"
}

# Registro compartido de clientes autenticados: {usuario: {"socket": conn, "addr": addr, "rol": rol}}
clientes_conectados = {}
lock_clientes = threading.Lock()


#------------------------------------------------
# FUNCIONES BASE DE DATOS Y SEGURIDAD
#------------------------------------------------

def conexion_db():
    """Crea y retorna una nueva conexión a MySQL."""
    return mysql.connector.connect(**DB_CONFIG)


def hashear_password(password: str) -> str:
    """Genera el hash SHA-256 hexadecimal de una contraseña en texto plano."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def validar_credenciales(usuario: str, password: str):
    """Valida usuario y contraseña en MySQL. Retorna el rol ('admin'/'usuario') o None si falla."""
    conn_db = None
    cursor = None
    try:
        conn_db = conexion_db()
        cursor = conn_db.cursor()
        password_hash = hashear_password(password)

        query = "SELECT rol FROM usuarios WHERE usuario = %s AND password_hash = %s"
        cursor.execute(query, (usuario, password_hash))
        fila = cursor.fetchone()
        return fila[0] if fila else None
    except Error as e:
        print(f"[ERROR DB] Fallo al validar credenciales: {e}")
        return None
    finally:
        if cursor:
            cursor.close()
        if conn_db and conn_db.is_connected():
            conn_db.close()


def crear_usuario_bd(nuevo_usuario: str, nueva_password: str, rol: str = "usuario") -> str:
    """Inserta un nuevo usuario en MySQL con su contraseña hasheada en SHA-256."""
    conn_db = None
    cursor = None
    try:
        conn_db = conexion_db()
        cursor = conn_db.cursor()
        password_hash = hashear_password(nueva_password)

        query = "INSERT INTO usuarios (usuario, password_hash, rol) VALUES (%s, %s, %s)"
        cursor.execute(query, (nuevo_usuario, password_hash, rol))
        conn_db.commit()
        return f"[ADMIN] Usuario '{nuevo_usuario}' (rol: {rol}) creado correctamente."
    except Error as e:
        if e.errno == 1062:  # Código de MySQL para clave duplicada (UNIQUE)
            return f"[ADMIN] Error: El usuario '{nuevo_usuario}' ya existe."
        return f"Error al crear usuario en MySQL: {e}"
    finally:
        if cursor:
            cursor.close()
        if conn_db and conn_db.is_connected():
            conn_db.close()


#------------------------------------------------
# FUNCIONES DE API DE GITHUB Y PERSISTENCIA
#------------------------------------------------


#--------------------------------------------------------------
# Consultar y Guardar repositorios
#--------------------------------------------------------------

def consultar_y_guardar_repos(usuario_git: str) -> str:
    """Consulta los repositorios públicos en GitHub y los guarda en la tabla 'repositorios'."""
    url = f"https://api.github.com/users/{usuario_git}/repos"
    headers = {"User-Agent": "TP-Integrador-Redes-Python"}

    try:
        respuesta = requests.get(url, headers=headers, params={"per_page": 100}, timeout=10)
    except requests.RequestException as e:
        return f"Error de red al conectar con GitHub: {e}"

    if respuesta.status_code == 404:
        return f"El usuario de GitHub '{usuario_git}' no existe."
    if respuesta.status_code != 200:
        return f"Error de la API de GitHub (HTTP {respuesta.status_code})."

    repos = respuesta.json()
    if not repos:
        return f"El usuario '{usuario_git}' no tiene repositorios públicos."

    conn_db = None
    cursor = None
    try:
        conn_db = conexion_db()
        cursor = conn_db.cursor()

        query = """
            INSERT INTO repositorios
                (usuario_git, nombre_repo, descripcion, url_repo, lenguaje)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        registros = [
            (
                usuario_git,
                repo.get("name", ""),
                repo.get("description"),
                repo.get("html_url", ""),
                repo.get("language")
            )
            for repo in repos
        ]

        cursor.executemany(query, registros)
        conn_db.commit()

        detalle = "\n".join(
            f"  - {r['name']} ({r.get('language') or 'Sin lenguaje'}): {r['html_url']}"
            for r in repos[:15]
        )
        aviso_extra = f"\n  ... y {len(repos) - 15} más." if len(repos) > 15 else ""
        return (
            f"Se guardaron {len(repos)} repositorios de '{usuario_git}' en la base de datos:\n"
            f"{detalle}{aviso_extra}"
        )
    except Error as e:
        return f"Error al guardar repositorios en MySQL: {e}"
    finally:
        if cursor:
            cursor.close()
        if conn_db and conn_db.is_connected():
            conn_db.close()


#--------------------------------------------------------------
# Consultar y Guardar seguidores
#--------------------------------------------------------------

def consultar_y_guardar_followers(usuario_git: str) -> str:
    """Consulta los seguidores en GitHub y los guarda en la tabla 'followers'."""
    url = f"https://api.github.com/users/{usuario_git}/followers"
    headers = {"User-Agent": "TP-Integrador-Redes-Python"}

    try:
        respuesta = requests.get(url, headers=headers, params={"per_page": 100}, timeout=10)
    except requests.RequestException as e:
        return f"Error de red al conectar con GitHub: {e}"

    if respuesta.status_code == 404:
        return f"El usuario de GitHub '{usuario_git}' no existe."
    if respuesta.status_code != 200:
        return f"Error de la API de GitHub (HTTP {respuesta.status_code})."

    followers = respuesta.json()
    if not followers:
        return f"El usuario '{usuario_git}' no tiene followers públicos."

    conn_db = None
    cursor = None
    try:
        conn_db = conexion_db()
        cursor = conn_db.cursor()

        query = """
            INSERT INTO followers
                (usuario_git, follower_usuario, follower_url, tipo)
            VALUES (%s, %s, %s, %s)
        """
        registros = [
            (
                usuario_git,
                f.get("login", ""),
                f.get("html_url", ""),
                f.get("type", "User")
            )
            for f in followers
        ]

        cursor.executemany(query, registros)
        conn_db.commit()

        detalle = "\n".join(
            f"  - {f['login']} ({f['html_url']})"
            for f in followers[:15]
        )
        aviso_extra = f"\n  ... y {len(followers) - 15} más." if len(followers) > 15 else ""
        return (
            f"Se guardaron {len(followers)} followers de '{usuario_git}' en la base de datos:\n"
            f"{detalle}{aviso_extra}"
        )
    except Error as e:
        return f"Error al guardar followers en MySQL: {e}"
    finally:
        if cursor:
            cursor.close()
        if conn_db and conn_db.is_connected():
            conn_db.close()


#--------------------------------------------------------------
# Eliminar repos
#--------------------------------------------------------------

def eliminar_repositorios(criterio: str) -> str:
    """Elimina repositorios de la tabla 'repositorios' por usuario de GitHub o en su totalidad."""
    conn_db = None
    cursor = None
    try:
        conn_db = conexion_db()
        cursor = conn_db.cursor()

        if criterio.lower() in ("todo", "todos"):
            cursor.execute("DELETE FROM repositorios")
            cantidad = cursor.rowcount
            conn_db.commit()
            return f"[ADMIN] Se eliminaron todos los repositorios de la base de datos ({cantidad} registro/s)."
        else:
            cursor.execute("DELETE FROM repositorios WHERE usuario_git = %s", (criterio,))
            cantidad = cursor.rowcount
            conn_db.commit()

            if cantidad == 0:
                return f"[ADMIN] No se encontraron repositorios guardados para '{criterio}'."
            return f"[ADMIN] Se eliminaron {cantidad} repositorio/s de '{criterio}'."

    except Error as e:
        return f"Error al eliminar repositorios en MySQL: {e}"
    finally:
        if cursor:
            cursor.close()
        if conn_db and conn_db.is_connected():
            conn_db.close()


#------------------------------------------------
# PROTOCOLO DE RED Y MENSAJERÍA
#------------------------------------------------

def enviar_paquete(sock: socket.socket, payload: dict) -> bool:
    """Serializa un diccionario a JSON terminado en salto de línea y lo envía."""
    try:
        datos = (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")
        sock.sendall(datos)
        return True
    except OSError:
        return False


def difundir_a_todos(texto: str):
    """Envía un mensaje de texto a todos los clientes conectados actualmente."""
    with lock_clientes:
        destinatarios = [info["socket"] for info in clientes_conectados.values()]

    for sock in destinatarios:
        enviar_paquete(sock, {"tipo": "mensaje", "mensaje": texto})


def leer_lineas_json(sock: socket.socket):
    """Generador que reconstruye mensajes JSON completos delimitados por '\\n'."""
    buffer = ""
    while True:
        chunk = sock.recv(4096).decode("utf-8")
        if not chunk:
            break
        buffer += chunk
        while "\n" in buffer:
            linea, buffer = buffer.split("\n", 1)
            linea = linea.strip()
            if linea:
                yield json.loads(linea)


#------------------------------------------------
# PROCESAMIENTO DE COMANDOS Y CLIENTES
#------------------------------------------------

def procesar_comando(usuario: str, rol: str, texto_comando: str, conn: socket.socket) -> bool:
    """
    Procesa los comandos iniciados con '/'.
    Verifica el rol del usuario para comandos administrativos.
    Retorna False si el cliente solicitó desconectarse (/adios), True en caso contrario.
    """
    partes = texto_comando.strip().split(" ", 1)
    comando = partes[0].lower()
    argumento = partes[1].strip() if len(partes) > 1 else ""

    if comando == "/repos":
        if not argumento:
            enviar_paquete(conn, {"tipo": "mensaje", "mensaje": "Uso correcto: /repos <usuario_git>"})
            return True
        resultado = consultar_y_guardar_repos(argumento)
        enviar_paquete(conn, {"tipo": "mensaje", "mensaje": resultado})

    elif comando == "/followers":
        if not argumento:
            enviar_paquete(conn, {"tipo": "mensaje", "mensaje": "Uso correcto: /followers <usuario_git>"})
            return True
        resultado = consultar_y_guardar_followers(argumento)
        enviar_paquete(conn, {"tipo": "mensaje", "mensaje": resultado})

    elif comando == "/eliminar_repos":
        # Verificación de permisos mediante el rol almacenado en MySQL
        if rol != "admin":
            enviar_paquete(
                conn,
                {
                    "tipo": "mensaje",
                    "mensaje": "[ACCESO DENEGADO] Solo usuarios con rol 'admin' pueden eliminar repositorios."
                }
            )
            return True

        if not argumento:
            enviar_paquete(
                conn,
                {
                    "tipo": "mensaje",
                    "mensaje": "Uso correcto: /eliminar_repos <usuario_git> o /eliminar_repos todo"
                }
            )
            return True

        resultado = eliminar_repositorios(argumento)
        enviar_paquete(conn, {"tipo": "mensaje", "mensaje": resultado})

    elif comando == "/crear_usuario":
        # Verificación de permisos mediante el rol almacenado en MySQL
        if rol != "admin":
            enviar_paquete(
                conn,
                {
                    "tipo": "mensaje",
                    "mensaje": "[ACCESO DENEGADO] Solo usuarios con rol 'admin' pueden crear usuarios."
                }
            )
            return True

        datos_nuevo = argumento.split()
        if len(datos_nuevo) not in (2, 3):
            enviar_paquete(
                conn,
                {
                    "tipo": "mensaje",
                    "mensaje": "Uso correcto: /crear_usuario <usuario> <contraseña> [rol: usuario|admin]"
                }
            )
            return True

        nuevo_usr = datos_nuevo[0]
        nueva_pwd = datos_nuevo[1]
        nuevo_rol = datos_nuevo[2].lower() if len(datos_nuevo) == 3 else "usuario"

        if nuevo_rol not in ("usuario", "admin"):
            enviar_paquete(
                conn,
                {
                    "tipo": "mensaje",
                    "mensaje": "Rol inválido. Debe ser 'usuario' o 'admin'."
                }
            )
            return True

        resultado = crear_usuario_bd(nuevo_usr, nueva_pwd, nuevo_rol)
        enviar_paquete(conn, {"tipo": "mensaje", "mensaje": resultado})

    elif comando == "/hora":
        ahora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        enviar_paquete(conn, {"tipo": "mensaje", "mensaje": f"[Servidor] Hora actual: {ahora}"})

    elif comando == "/todos":
        if not argumento:
            enviar_paquete(conn, {"tipo": "mensaje", "mensaje": 'Uso correcto: /todos "mensaje"'})
            return True
        if (argumento.startswith('"') and argumento.endswith('"')) or (
            argumento.startswith("'") and argumento.endswith("'")
        ):
            argumento = argumento[1:-1]

        difundir_a_todos(f"[Todos - {usuario}]: {argumento}")

    elif comando == "/usuarios":
        with lock_clientes:
            lista_usuarios = [f"{usr} ({info['rol']})" for usr, info in clientes_conectados.items()]
        listado = ", ".join(lista_usuarios) if lista_usuarios else "Ninguno"
        enviar_paquete(
            conn,
            {
                "tipo": "mensaje",
                "mensaje": f"[Servidor] Usuarios conectados ({len(lista_usuarios)}): {listado}"
            }
        )

    elif comando == "/adios":
        enviar_paquete(
            conn,
            {
                "tipo": "desconexion",
                "mensaje": f"¡Hasta luego, {usuario}! Has cerrado sesión correctamente."
            }
        )
        return False

    else:
        comandos_disp = "/repos, /followers, /hora, /todos, /usuarios, /adios"
        if rol == "admin":
            comandos_disp += ", /eliminar_repos, /crear_usuario"

        enviar_paquete(
            conn,
            {
                "tipo": "mensaje",
                "mensaje": f"Comando '{comando}' no reconocido. Disponibles: {comandos_disp}"
            }
        )

    return True


def manejar_cliente(conn: socket.socket, addr):
    """Hilo dedicado a autenticar y atender a un cliente."""
    print(f"[+] Nueva conexión entrante desde {addr}")
    usuario_autenticado = None

    try:
        lector = leer_lineas_json(conn)

        # Recibir credenciales iniciales
        primer_paquete = next(lector, None)
        if not primer_paquete or primer_paquete.get("accion") != "login":
            enviar_paquete(conn, {"tipo": "auth", "ok": False, "mensaje": "Protocolo de inicio inválido."})
            return

        usuario = primer_paquete.get("usuario", "").strip()
        password = primer_paquete.get("password", "").strip()

        # Validar usuario y contraseña en la base de datos y obtener su rol
        rol = validar_credenciales(usuario, password) if (usuario and password) else None
        if not rol:
            print(f"[!] Autenticación fallida para '{usuario}' desde {addr}")
            enviar_paquete(
                conn,
                {
                    "tipo": "auth",
                    "ok": False,
                    "mensaje": "Error: Usuario o contraseña incorrectos. Cerrando sesión."
                }
            )
            return

        # Verificar que no tenga ya una sesión abierta
        with lock_clientes:
            if usuario in clientes_conectados:
                enviar_paquete(
                    conn,
                    {
                        "tipo": "auth",
                        "ok": False,
                        "mensaje": f"Error: El usuario '{usuario}' ya tiene una sesión activa."
                    }
                )
                return
            clientes_conectados[usuario] = {"socket": conn, "addr": addr, "rol": rol}
            usuario_autenticado = usuario

        print(f"[OK] Usuario '{usuario_autenticado}' (rol: {rol}) autenticado desde {addr}")

        mensaje_bienvenida = (
            f"¡Hola {usuario_autenticado}! (Rol: {rol})\n"
            "Comandos disponibles: /repos <usuario>, /followers <usuario>, "
            "/hora, /todos \"mensaje\", /usuarios, /adios"
        )
        if rol == "admin":
            mensaje_bienvenida += "\nComandos admin: /eliminar_repos <usuario|todo>, /crear_usuario <usuario> <clave> [rol]"

        enviar_paquete(
            conn,
            {
                "tipo": "auth",
                "ok": True,
                "mensaje": mensaje_bienvenida
            }
        )

        # Bucle principal de recepción de chat y comandos
        for paquete in lector:
            contenido = paquete.get("contenido", "").strip()
            if not contenido:
                continue

            if contenido.startswith("/"):
                print(f"[CMD - {usuario_autenticado} ({rol})]: {contenido}")
                continuar = procesar_comando(usuario_autenticado, rol, contenido, conn)
                if not continuar:
                    break
            else:
                print(f"[Chat - {usuario_autenticado}]: {contenido}")

    except (ConnectionResetError, BrokenPipeError, json.JSONDecodeError):
        pass
    except Exception as e:
        print(f"[ERROR] Excepción atendiendo a {addr}: {e}")
    finally:
        if usuario_autenticado:
            with lock_clientes:
                clientes_conectados.pop(usuario_autenticado, None)
            print(f"[-] Usuario '{usuario_autenticado}' desconectado ({addr}).")
        else:
            print(f"[-] Conexión cerrada sin autenticar ({addr}).")
        conn.close()


#-------------------------------------------------------------
# CONSOLA INTERACTIVA DEL SERVIDOR (CHAT SERVIDOR -> CLIENTE)
#-------------------------------------------------------------

def consola_servidor():
    """Permite al operador del servidor chatear con los clientes conectados."""
    print("\n--- Consola de Chat del Servidor ---")
    print("• Escribí un mensaje y presioná Enter para enviarlo a TODOS los clientes.")
    print("• Escribí '@usuario mensaje' para enviar un mensaje privado a un cliente.\n")

    while True:
        try:
            entrada = input().strip()
            if not entrada:
                continue

            if entrada.startswith("@"):
                partes = entrada[1:].split(None, 1)
                if len(partes) < 2 or not partes[1].strip():
                    print("[!] Uso correcto para privado: @usuario mensaje")
                    continue

                destinatario, mensaje = partes[0], partes[1].strip()
                sock_destino = None
                nombre_real = destinatario

                with lock_clientes:
                    for usr, info in clientes_conectados.items():
                        if usr.lower() == destinatario.lower():
                            sock_destino = info["socket"]
                            nombre_real = usr
                            break

                if sock_destino:
                    enviado = enviar_paquete(
                        sock_destino,
                        {"tipo": "mensaje", "mensaje": f"[Servidor (privado)]: {mensaje}"}
                    )
                    if enviado:
                        print(f"[Privado -> {nombre_real}]: {mensaje}")
                    else:
                        print(f"[ERROR] No se pudo entregar el mensaje a '{nombre_real}'.")
                else:
                    with lock_clientes:
                        conectados = ", ".join(clientes_conectados.keys()) or "ninguno"
                    print(f"[!] El usuario '{destinatario}' no está conectado. Activos: {conectados}")

            else:
                with lock_clientes:
                    cantidad = len(clientes_conectados)
                if cantidad == 0:
                    print("[!] No hay clientes conectados para recibir el mensaje.")
                else:
                    difundir_a_todos(f"[Servidor]: {entrada}")
                    print(f"[Difundido a {cantidad} cliente(s)]: {entrada}")
        except EOFError:
            break


#------------------------------------------------
# PUNTO DE ENTRADA DEL SERVIDOR
#------------------------------------------------

def iniciar_servidor():
    servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        servidor.bind((HOST, PORT))
        servidor.listen(10)
        print(f"[*] Servidor TCP concurrente escuchando en {HOST}:{PORT}...")

        hilo_consola = threading.Thread(target=consola_servidor, daemon=True)
        hilo_consola.start()

        while True:
            conn, addr = servidor.accept()
            hilo_cliente = threading.Thread(
                target=manejar_cliente,
                args=(conn, addr),
                daemon=True
            )
            hilo_cliente.start()

    except KeyboardInterrupt:
        print("\n[*] Deteniendo servidor por solicitud del operador...")
    finally:
        servidor.close()


if __name__ == "__main__":
    iniciar_servidor()