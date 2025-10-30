"""
Lightweight Hand Tracking Server for Blender
Minimal memory usage - only sends landmark data
"""
import cv2
import mediapipe as mp
import socket
import pickle
import struct
import threading

class LightweightHandServer:
    def __init__(self):
        # MediaPipe (minimal config)
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=2,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
            model_complexity=0  # Fastest model
        )
        
        # Camera
        self.cap = None
        self.camera_index = 0
        self.is_running = False
        
        # Server
        self.server_socket = None
        self.server_running = False
        self.clients = []
        self.port = 5555
        
    def start_camera(self, camera_index=0):
        """Start camera capture"""
        self.camera_index = camera_index
        self.cap = cv2.VideoCapture(camera_index)
        
        # Optimize for speed
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.cap.set(cv2.CAP_PROP_FPS, 60)
        
        if self.cap.isOpened():
            self.is_running = True
            print(f"Camera {camera_index} started")
            return True
        return False
    
    def start_server(self):
        """Start socket server"""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self.server_socket.bind(('0.0.0.0', self.port))
            self.server_socket.listen(5)
            
            self.server_running = True
            print(f"Server listening on port {self.port}")
            
            # Accept clients in thread
            threading.Thread(target=self.accept_clients, daemon=True).start()
            return True
        except Exception as e:
            print(f"Server error: {e}")
            return False
    
    def accept_clients(self):
        """Accept client connections"""
        while self.server_running:
            try:
                self.server_socket.settimeout(1.0)
                client_socket, address = self.server_socket.accept()
                client_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                self.clients.append(client_socket)
                print(f"Client connected: {address}")
            except socket.timeout:
                continue
            except:
                break
    
    def process_frame(self):
        """Process single frame and send to clients"""
        ret, frame = self.cap.read()
        if not ret:
            return
        
        # Flip and convert
        frame = cv2.flip(frame, 1)
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Process hands
        results = self.hands.process(rgb_frame)
        
        # Extract only landmarks (minimal data)
        landmarks_list = []
        if results.multi_hand_landmarks:
            for hand_landmarks in results.multi_hand_landmarks:
                landmarks_data = []
                for landmark in hand_landmarks.landmark:
                    landmarks_data.append({
                        'x': landmark.x,
                        'y': landmark.y,
                        'z': landmark.z
                    })
                landmarks_list.append(landmarks_data)
        
        # Send to clients (landmarks only, no frame data)
        if self.clients:
            self.broadcast_landmarks(landmarks_list)
    
    def broadcast_landmarks(self, landmarks):
        """Send only landmarks (ultra-lightweight)"""
        try:
            # Pack only landmarks
            data = pickle.dumps({
                'landmarks': landmarks,
                'frame': b''  # Empty frame to save bandwidth
            })
            
            message = struct.pack("Q", len(data)) + data
            
            # Send to all clients
            disconnected = []
            for client in self.clients:
                try:
                    client.sendall(message)
                except:
                    disconnected.append(client)
            
            # Remove disconnected
            for client in disconnected:
                if client in self.clients:
                    self.clients.remove(client)
                try:
                    client.close()
                except:
                    pass
        except:
            pass
    
    def run(self):
        """Main loop"""
        import time
        
        print("=" * 60)
        print("LIGHTWEIGHT HAND TRACKING SERVER FOR BLENDER")
        print("=" * 60)
        print(f"Server: localhost:{self.port}")
        print("Optimized for minimal memory and instant response")
        print("Press Ctrl+C to stop")
        print("=" * 60)
        
        fps_counter = 0
        fps_time = time.time()
        
        try:
            while self.is_running:
                self.process_frame()
                
                # FPS counter
                fps_counter += 1
                if time.time() - fps_time > 1:
                    print(f"FPS: {fps_counter} | Clients: {len(self.clients)}")
                    fps_counter = 0
                    fps_time = time.time()
                
        except KeyboardInterrupt:
            print("\nStopping...")
        finally:
            self.stop()
    
    def stop(self):
        """Cleanup"""
        self.is_running = False
        self.server_running = False
        
        if self.cap:
            self.cap.release()
        
        if self.server_socket:
            self.server_socket.close()
        
        for client in self.clients:
            try:
                client.close()
            except:
                pass
        
        print("Server stopped")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Lightweight Hand Tracking Server for Blender')
    parser.add_argument('--camera', type=int, default=0, help='Camera index')
    parser.add_argument('--port', type=int, default=5555, help='Server port')
    
    args = parser.parse_args()
    
    server = LightweightHandServer()
    server.port = args.port
    
    if server.start_camera(args.camera):
        if server.start_server():
            server.run()
        else:
            print("Failed to start server")
    else:
        print("Failed to open camera")
