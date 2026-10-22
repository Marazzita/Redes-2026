import socket
import threading
import sys

# funcion del hilo que escucha al servidor
def recibir(sock):
    while True:
        try:
            # decode siempre para recibir
            data = sock.recv(1024).decode('utf-8')
            if not data:
                break
            print(data, end='') # end='' para no duplicar los saltos de linea
        except:
            print("\nSe cortó la conexión.")
            break

# conexion del cliente
cliente = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
cliente.connect(('127.0.0.1', 5555))

# arranco el hilo para recibir mensajes al mismo tiempo que escribo
hilo = threading.Thread(target=recibir, args=(cliente,))
hilo.start()

# ciclo principal para escribi
while True:
    texto = input()
    
    # encode siempre para mandar
    cliente.send(texto.encode('utf-8'))
    
    # cuando /adios termina el programa
    if texto.strip() == '/adios':
        break

cliente.close()
sys.exit()