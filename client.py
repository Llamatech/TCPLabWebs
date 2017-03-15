from socket import *


def receiveFile(socket,MSGLEN):
        chunks = []
        bytes_recd = 0
        while bytes_recd < MSGLEN:
            chunk = socket.recv(min(MSGLEN - bytes_recd, 2048))
            if chunk == b'':
                raise RuntimeError("socket connection broken")
            chunks.append(chunk)
            bytes_recd = bytes_recd + len(chunk)
            print('chunk #'+len(chunks))
            print('Size of chunk: %f'%len(chunk))
            print('Bytes received until now: %f'%bytes_recd)
        return b''.join(chunks)



if __name__=='__main__':
    serverName = '157.253.121.125'
    serverPort = 11000
    clientSocket = socket(AF_INET, SOCK_STREAM)
    clientSocket.connect((serverName,serverPort))
    #sentence = raw_input('Input lowercase sentence:')
    #clientSocket.send(sentence+"\n")

    nombre=str(clientSocket.recv(1024),"UTF-8")
    print(nombre)
    clientSocket.send(b"OK")

    tam=int(clientSocket.recv(1024))
    print(tam)
    clientSocket.send(b"OK")

    file = open(nombre, "wb")
    file.write(receiveFile(clientSocket,tam))
    file.close()


    clientSocket.close()


