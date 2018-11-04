import struct
import pickle


def send_msg(sock, msg):
    """Send message via socket"""
    # Prefix each message with a 4-byte length (network byte order)
    msg = pickle.dumps(msg)
    msg = struct.pack('>I', len(msg)) + msg
    sock.sendall(msg)


def recv_msg(sock):
    """Receive message via socket"""
    # Read message length and unpack it into an integer
    raw_msglen = _recvall(sock, 4)
    if not raw_msglen:
        return None
    msglen = struct.unpack('>I', raw_msglen)[0]
    # Read the message data
    msg = _recvall(sock, msglen)
    return pickle.loads(msg)


def _recvall(sock, n):
    """Helper function"""
    # Helper function to recv n bytes or return None if EOF is hit
    data = b''
    while len(data) < n:
        packet = sock.recv(n - len(data))
        if not packet:
            return None
        data += packet
    return data
