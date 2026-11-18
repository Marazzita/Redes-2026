import socket
import threading
import json
import sys

HOST = "127.0.0.1"
PORT = 5000

sesion_activa = True


def enviar_paquete(sock: socket.socket, payload: dict):
    """Codifica un diccionario como JSON terminado en '\\n' y lo envía al servidor."""
    datos = (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")
    sock.sendall(datos)


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


def escuchar_servidor(sock: socket.socket):
    """Hilo secundario encargado de recibir e imprimir mensajes del servidor en tiempo real."""
    global sesion_activa
    try:
        for paquete in leer_lineas_json(sock):
            tipo = paquete.get("tipo")
            mensaje = paquete.get("mensaje", "")

            print(f"\r{mensaje}\n> ", end="", flush=True)

            if tipo == "desconexion":
                sesion_activa = False
                break
    except (OSError, json.JSONDecodeError):
        pass
    finally:
        if sesion_activa:
            print("\n[!] Se perdió la conexión con el servidor.")
            sesion_activa = False


def iniciar_cliente():
    global sesion_activa
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        sock.connect((HOST, PORT))
        print(f"Conectado al servidor en {HOST}:{PORT}")

        # solicitar y enviar credenciales al conectarse
        print("\n=== INICIO DE SESIÓN ===")
        usuario = input("Usuario: ").strip()
        password = input("Contraseña: ").strip()

        enviar_paquete(
            sock,
            {
                "accion": "login",
                "usuario": usuario,
                "password": password
            }
        )

        # esperar resultado de autenticación del servidor
        lector = leer_lineas_json(sock)
        respuesta_auth = next(lector, None)

        if not respuesta_auth:
            print("[!] El servidor cerró la conexión sin responder.")
            return

        print(f"\n{respuesta_auth.get('mensaje')}")

        if not respuesta_auth.get("ok"):
            return

        # iniciar hilo de escucha y bucle de envío de chat/comandos
        hilo_receptor = threading.Thread(
            target=escuchar_servidor,
            args=(sock,),
            daemon=True
        )
        hilo_receptor.start()

        print("\n--- Chat iniciado (escribí un mensaje, '@usuario mensaje' para privado o un comando con '/') ---")
        while sesion_activa:
            texto = input("> ")
            if not sesion_activa:
                break

            texto_limpio = texto.strip()
            if not texto_limpio:
                continue

            enviar_paquete(sock, {"accion": "mensaje", "contenido": texto_limpio})

            if texto_limpio.lower() == "/adios":
                hilo_receptor.join(timeout=2)
                break

    except ConnectionRefusedError:
        print("[!] No se pudo conectar: asegurate de que el servidor esté ejecutándose.")
    except (KeyboardInterrupt, EOFError):
        if sesion_activa:
            try:
                enviar_paquete(sock, {"accion": "mensaje", "contenido": "/adios"})
            except OSError:
                pass
    finally:
        sesion_activa = False
        sock.close()
        print("\nConexión finalizada.")
        sys.exit(0)


if __name__ == "__main__":
    iniciar_cliente()