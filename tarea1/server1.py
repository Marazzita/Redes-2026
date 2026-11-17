import socket
import threading

# lista para guardar las IP de los que se conectan
lista_clientes = []

def atender_cliente(conn, addr):
    print("Se conectó:", addr)
    
    while True:
        try:
            # decode siempre para recibir 
            recibido = conn.recv(1024).decode('utf-8')
            if not recibido:
                break
            
            # strip para limpiar el enter y espacios vacíos
            mensaje = recibido.strip()
            
            # startswith("/") este es el que conviene para los comandos
            if mensaje.startswith('/'):
                
                if mensaje == '/adios':
                    # cuando /adios termina el programa y se elimina al cliente de la lista
                    break
                    
                elif mensaje == '/users':
                    usuarios = "Usuarios conectados:\n"
                    for c in lista_clientes:
                        usuarios += str(c) + "\n"
                    
                    # encode siempre para mandar
                    conn.send(usuarios.encode('utf-8'))
                else:
                    conn.send("Comando no existe\n".encode('utf-8'))
            
            else:
                # si no es comando echo normal
                echo = "Echo: " + mensaje + "\n"
                conn.send(echo.encode('utf-8')) # encode siempre para mandar
                
        except:
            # si hay un error (ej. se cerró de golpe), salimos del ciclo
            break
            
    # salimos del while, eliminamos al cliente de la lista
    if addr in lista_clientes:
        lista_clientes.remove(addr)
    
    print("Se desconectó:", addr)
    conn.close()

# configuracion basica del servidor
servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
servidor.bind(('127.0.0.1', 5555))
servidor.listen()

print("Servidor prendido y esperando conexiones...")

# bucle principal para aceptar clientes nuevos
while True:
    conn, addr = servidor.accept()
    lista_clientes.append(addr) # agrego el cliente a la lista
    
    # hilo para que no se trabe y pueda aceptar varios a la vez
    hilo = threading.Thread(target=atender_cliente, args=(conn, addr))
    hilo.start()