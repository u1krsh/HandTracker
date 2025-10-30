"""
Quick connection test - Run this on the OTHER laptop
"""
import socket

SERVER_IP = "10.48.231.133"  # Change this to your server IP
SERVER_PORT = 5555

print("=" * 60)
print("CONNECTION TEST")
print("=" * 60)
print(f"Attempting to connect to {SERVER_IP}:{SERVER_PORT}")
print()

try:
    test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    test_socket.settimeout(5)
    test_socket.connect((SERVER_IP, SERVER_PORT))
    print("✓ CONNECTION SUCCESSFUL!")
    print("The other laptop CAN connect to the server.")
    print()
    print("If client_viewer.py still shows only 1 client,")
    print("make sure you're using the correct IP in the app.")
    test_socket.close()
except socket.timeout:
    print("✗ CONNECTION TIMEOUT")
    print("Server is not responding. Check:")
    print("1. Server is running (python blender_server.py)")
    print("2. Both devices on same WiFi network")
    print("3. Firewall is not blocking port 5555")
except ConnectionRefusedError:
    print("✗ CONNECTION REFUSED")
    print("Server is not accepting connections. Check:")
    print("1. Server is running on the other laptop")
    print("2. Port 5555 is not blocked by firewall")
except Exception as e:
    print(f"✗ CONNECTION FAILED: {e}")
    print("Check network settings")

print("=" * 60)
input("Press Enter to exit...")
