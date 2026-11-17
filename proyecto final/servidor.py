import socket
import threading
import json
import hashlib
from datetime import datetime
import mysql.connector
from mysql.connector import Error
import requests

# Configuración de red
HOST = "127.0.0.1"
PORT = 5000

# Configuración de la base de datos MySQL
DB_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "",  # Colocar contraseña de MySQL si corresponde
    "database": "tp_redes_chat",
    "charset": "utf8mb4"
}

# Registro compartido de clientes autenticados: {usuario: {"socket": conn, "addr": addr}}
clientes_conectados = {}
lock_clientes = threading.Lock()


#------------------------------------------------
# FUNCIONES BASE DE DATOS Y SEGURIDAD
#------------------------------------------------

def obtener_conexion_db():
    """Crea y retorna una nueva conexión a MySQL."""
    return mysql.connector.connect(**DB_CONFIG)


def hashear_password(password: str) -> str:
    """Genera el hash SHA-256 hexadecimal de una contraseña en texto plano."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def validar_credenciales(usuario: str, password: str) -> bool:
    """Valida usuario y contraseña contra la tabla 'usuarios' usando consultas parametrizadas."""
    conn_db = None
    cursor = None
    try:
        conn_db = obtener_conexion_db()
        cursor = conn_db.cursor()
        password_hash = hashear_password(password)

        query = "SELECT id FROM usuarios WHERE usuario = %s AND password_hash = %s"
        cursor.execute(query, (usuario, password_hash))
        fila = cursor.fetchone()
        return fila is not None
    except Error as e:
        print(f"[ERROR DB] Fallo al validar credenciales: {e}")
        return False
    finally:
        if cursor:
            cursor.close()
        if conn_db and conn_db.is_connected():
            conn_db.close()


#------------------------------------------------
# FUNCIONES DE API DE GITHUB Y PERSISTENCIA
#------------------------------------------------

def consultar_y_guardar_repos(usuario_github: str) -> str:
    """Consulta los repositorios públicos en GitHub y los guarda en la tabla 'repositorios'."""
    url = f"https://api.github.com/users/{usuario_github}/repos"
    headers = {"User-Agent": "TP-Integrador-Redes-Python"}

    try:
        respuesta = requests.get(url, headers=headers, params={"per_page": 100}, timeout=10)
    except requests.RequestException as e:
        return f"Error de red al conectar con GitHub: {e}"

    if respuesta.status_code == 404:
        return f"El usuario de GitHub '{usuario_github}' no existe."
    if respuesta.status_code != 200:
        return f"Error de la API de GitHub (HTTP {respuesta.status_code})."

    repos = respuesta.json()
    if not repos:
        return f"El usuario '{usuario_github}' no tiene repositorios públicos."

    conn_db = None
    cursor = None
    try:
        conn_db = obtener_conexion_db()
        cursor = conn_db.cursor()

        query = """
            INSERT INTO repositorios
                (usuario_github, nombre_repo, descripcion, url_repo, lenguaje, estrellas)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        registros = [
            (
                usuario_github,
                repo.get("name", ""),
                repo.get("description"),
                repo.get("html_url", ""),
                repo.get("language"),
                repo.get("stargazers_count", 0)
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
            f"Se guardaron {len(repos)} repositorios de '{usuario_github}' en la base de datos:\n"
            f"{detalle}{aviso_extra}"
        )
    except Error as e:
        return f"Error al guardar repositorios en MySQL: {e}"
    finally:
        if cursor:
            cursor.close()
        if conn_db and conn_db.is_connected():
            conn_db.close()


def consultar_y_guardar_followers(usuario_github: str) -> str:
    """Consulta los seguidores en GitHub y los guarda en la tabla 'followers'."""
    url = f"https://api.github.com/users/{usuario_github}/followers"
    headers = {"User-Agent": "TP-Integrador-Redes-Python"}

    try:
        respuesta = requests.get(url, headers=headers, params={"per_page": 100}, timeout=10)
    except requests.RequestException as e:
        return f"Error de red al conectar con GitHub: {e}"

    if respuesta.status_code == 404:
        return f"El usuario de GitHub '{usuario_github}' no existe."
    if respuesta.status_code != 200:
        return f"Error de la API de GitHub (HTTP {respuesta.status_code})."

    followers = respuesta.json()
    if not followers:
        return f"El usuario '{usuario_github}' no tiene followers públicos."

    conn_db = None
    cursor = None
    try:
        conn_db = obtener_conexion_db()
        cursor = conn_db.cursor()

        query = """
            INSERT INTO followers
                (usuario_github, follower_usuario, follower_url, tipo)
            VALUES (%s, %s, %s, %s)
        """
        registros = [
            (
                usuario_github,
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
            f"Se guardaron {len(followers)} followers de '{usuario_github}' en la base de datos:\n"
            f"{detalle}{aviso_extra}"
        )
    except Error as e:
        return f"Error al guardar followers en MySQL: {e}"
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
# PROCESAMIENTO DE COMANDOS Y ATENCIÓN A CLIENTES
#------------------------------------------------

def procesar_comando(usuario: str, texto_comando: str, conn: socket.socket) -> bool:
    """
    Procesa los comandos iniciados con '/'.
    Retorna False si el cliente solicitó desconectarse (/adios), True en caso contrario.
    """
    partes = texto_comando.strip().split(" ", 1)
    comando = partes[0].lower()
    argumento = partes[1].strip() if len(partes) > 1 else ""

    if comando == "/repos":
        if not argumento:
            enviar_paquete(conn, {"tipo": "mensaje", "mensaje": "Uso correcto: /repos <usuario_github>"})
            return True
        resultado = consultar_y_guardar_repos(argumento)
        enviar_paquete(conn, {"tipo": "mensaje", "mensaje": resultado})

    elif comando == "/followers":
        if not argumento:
            enviar_paquete(conn, {"tipo": "mensaje", "mensaje": "Uso correcto: /followers <usuario_github>"})
            return True
        resultado = consultar_y_guardar_followers(argumento)
        enviar_paquete(conn, {"tipo": "mensaje", "mensaje": resultado})

    elif comando == "/hora":
        ahora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        enviar_paquete(conn, {"tipo": "mensaje", "mensaje": f"[Servidor] Hora actual: {ahora}"})

    elif comando == "/todos":
        if not argumento:
            enviar_paquete(conn, {"tipo": "mensaje", "mensaje": 'Uso correcto: /todos "mensaje"'})
            return True
        # Eliminar comillas envolventes si el usuario las escribió
        if (argumento.startswith('"') and argumento.endswith('"')) or (
            argumento.startswith("'") and argumento.endswith("'")
        ):
            argumento = argumento[1:-1]

        difundir_a_todos(f"[Todos - {usuario}]: {argumento}")

    elif comando == "/usuarios":
        with lock_clientes:
            lista_usuarios = list(clientes_conectados.keys())
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
        enviar_paquete(
            conn,
            {
                "tipo": "mensaje",
                "mensaje": (
                    f"Comando '{comando}' no reconocido. "
                    "Disponibles: /repos, /followers, /hora, /todos, /usuarios, /adios"
                )
            }
        )

    return True


def manejar_cliente(conn: socket.socket, addr):
    """Hilo dedicado a autenticar y atender a un cliente."""
    print(f"[+] Nueva conexión entrante desde {addr}")
    usuario_autenticado = None

    try:
        lector = leer_lineas_json(conn)

        # 1. Recibir credenciales iniciales
        primer_paquete = next(lector, None)
        if not primer_paquete or primer_paquete.get("accion") != "login":
            enviar_paquete(conn, {"tipo": "auth", "ok": False, "mensaje": "Protocolo de inicio inválido."})
            return

        usuario = primer_paquete.get("usuario", "").strip()
        password = primer_paquete.get("password", "").strip()

        # 2 y 3. Validar usuario y contraseña en la base de datos
        if not usuario or not password or not validar_credenciales(usuario, password):
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
            clientes_conectados[usuario] = {"socket": conn, "addr": addr}
            usuario_autenticado = usuario

        print(f"[OK] Usuario '{usuario_autenticado}' autenticado desde {addr}")
        enviar_paquete(
            conn,
            {
                "tipo": "auth",
                "ok": True,
                "mensaje": (
                    f"¡Bienvenido/a {usuario_autenticado}!\n"
                    "Comandos disponibles: /repos <usuario>, /followers <usuario>, "
                    "/hora, /todos \"mensaje\", /usuarios, /adios"
                )
            }
        )

        # 4 y 5. Bucle principal de recepción de chat y comandos
        for paquete in lector:
            contenido = paquete.get("contenido", "").strip()
            if not contenido:
                continue

            if contenido.startswith("/"):
                print(f"[CMD - {usuario_autenticado}]: {contenido}")
                continuar = procesar_comando(usuario_autenticado, contenido, conn)
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


# ==============================================================================
# CONSOLA INTERACTIVA DEL SERVIDOR (CHAT SERVIDOR -> CLIENTE)
# ==============================================================================

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

            if entrada.startswith("@") and " " in entrada:
                destinatario, mensaje = entrada[1:].split(" ", 1)
                with lock_clientes:
                    info = clientes_conectados.get(destinatario)

                if info:
                    enviado = enviar_paquete(
                        info["socket"],
                        {"tipo": "mensaje", "mensaje": f"[Servidor (privado)]: {mensaje}"}
                    )
                    if enviado:
                        print(f"[Enviado a {destinatario}]: {mensaje}")
                else:
                    print(f"[!] El usuario '{destinatario}' no está conectado.")
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


# ==============================================================================
# PUNTO DE ENTRADA DEL SERVIDOR
# ==============================================================================

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