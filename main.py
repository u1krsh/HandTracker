import tkinter as tk
from tkinter import ttk
import cv2
from PIL import Image, ImageTk
import mediapipe as mp
import threading
import socket
import pickle
import struct

class HandTrackingApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Hand Tracking App")
        self.root.geometry("900x700")
        
        # Initialize MediaPipe
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=2,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        self.mp_drawing = mp.solutions.drawing_utils
        self.mp_drawing_styles = mp.solutions.drawing_styles
        
        # Camera and streaming variables
        self.cap = None
        self.current_camera = 0
        self.is_running = False
        self.frame = None
        self.hand_landmarks_list = []
        
        # Socket server variables
        self.server_socket = None
        self.server_running = False
        self.clients = []
        self.server_port = 5555
        
        # Create UI
        self.create_ui()
        
    def create_ui(self):
        # Top control panel
        control_frame = tk.Frame(self.root, bg="#2c3e50", padx=10, pady=10)
        control_frame.pack(fill=tk.X)
        
        # Camera selection
        tk.Label(control_frame, text="Camera:", bg="#2c3e50", fg="white", font=("Arial", 10)).pack(side=tk.LEFT, padx=5)
        
        self.camera_var = tk.StringVar()
        self.camera_combo = ttk.Combobox(control_frame, textvariable=self.camera_var, width=15, state="readonly")
        self.camera_combo.pack(side=tk.LEFT, padx=5)
        self.populate_cameras()
        self.camera_combo.bind("<<ComboboxSelected>>", self.change_camera)
        
        # Start/Stop button
        self.start_button = tk.Button(control_frame, text="Start Camera", command=self.toggle_camera, 
                                       bg="#27ae60", fg="white", font=("Arial", 10, "bold"), padx=20)
        self.start_button.pack(side=tk.LEFT, padx=10)
        
        # Server control
        self.server_button = tk.Button(control_frame, text="Start Server", command=self.toggle_server,
                                        bg="#3498db", fg="white", font=("Arial", 10, "bold"), padx=20)
        self.server_button.pack(side=tk.LEFT, padx=10)
        
        # Server status
        self.server_status_label = tk.Label(control_frame, text="Server: OFF", bg="#2c3e50", 
                                            fg="#e74c3c", font=("Arial", 10, "bold"))
        self.server_status_label.pack(side=tk.LEFT, padx=10)
        
        # Info panel
        info_frame = tk.Frame(self.root, bg="#34495e", padx=10, pady=5)
        info_frame.pack(fill=tk.X)
        
        self.info_label = tk.Label(info_frame, text="Ready to start", bg="#34495e", 
                                   fg="white", font=("Arial", 9))
        self.info_label.pack(side=tk.LEFT)
        
        self.ip_label = tk.Label(info_frame, text=f"IP: {self.get_local_ip()}", bg="#34495e",
                                fg="#f39c12", font=("Arial", 9, "bold"))
        self.ip_label.pack(side=tk.RIGHT)
        
        # Video display
        self.video_frame = tk.Frame(self.root, bg="black")
        self.video_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.canvas = tk.Canvas(self.video_frame, bg="black", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas_image = None  # Store canvas image reference
        
        # Bottom stats panel
        stats_frame = tk.Frame(self.root, bg="#2c3e50", padx=10, pady=5)
        stats_frame.pack(fill=tk.X)
        
        self.stats_label = tk.Label(stats_frame, text="FPS: 0 | Hands Detected: 0 | Clients: 0", 
                                    bg="#2c3e50", fg="white", font=("Arial", 9))
        self.stats_label.pack()
        
    def populate_cameras(self):
        """Detect available cameras"""
        cameras = []
        for i in range(5):  # Check first 5 camera indices
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                cameras.append(f"Camera {i}")
                cap.release()
        
        if cameras:
            self.camera_combo['values'] = cameras
            self.camera_combo.current(0)
        else:
            self.camera_combo['values'] = ["No cameras found"]
            self.camera_combo.current(0)
    
    def change_camera(self, event=None):
        """Change the active camera"""
        if self.is_running:
            camera_str = self.camera_var.get()
            if "Camera" in camera_str:
                new_camera = int(camera_str.split()[-1])
                if new_camera != self.current_camera:
                    self.current_camera = new_camera
                    if self.cap:
                        self.cap.release()
                    self.cap = cv2.VideoCapture(self.current_camera)
                    self.info_label.config(text=f"Switched to {camera_str}")
    
    def toggle_camera(self):
        """Start or stop the camera"""
        if not self.is_running:
            camera_str = self.camera_var.get()
            if "Camera" in camera_str:
                self.current_camera = int(camera_str.split()[-1])
                self.cap = cv2.VideoCapture(self.current_camera)
                
                if self.cap.isOpened():
                    self.is_running = True
                    self.start_button.config(text="Stop Camera", bg="#e74c3c")
                    self.info_label.config(text="Camera running")
                    threading.Thread(target=self.update_frame, daemon=True).start()
                else:
                    self.info_label.config(text="Failed to open camera")
        else:
            self.is_running = False
            self.start_button.config(text="Start Camera", bg="#27ae60")
            self.info_label.config(text="Camera stopped")
            if self.cap:
                self.cap.release()
    
    def update_frame(self):
        """Main loop to capture and process frames"""
        import time
        fps_counter = 0
        fps_time = time.time()
        fps = 0
        
        while self.is_running:
            ret, frame = self.cap.read()
            if not ret:
                continue
            
            # Flip frame horizontally for mirror effect
            frame = cv2.flip(frame, 1)
            
            # Convert BGR to RGB for MediaPipe
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Process hand tracking
            results = self.hands.process(rgb_frame)
            
            # Draw hand landmarks
            self.hand_landmarks_list = []
            hands_detected = 0
            
            if results.multi_hand_landmarks:
                hands_detected = len(results.multi_hand_landmarks)
                for hand_landmarks in results.multi_hand_landmarks:
                    # Draw the hand skeleton in red
                    self.mp_drawing.draw_landmarks(
                        frame,
                        hand_landmarks,
                        self.mp_hands.HAND_CONNECTIONS,
                        self.mp_drawing.DrawingSpec(color=(0, 0, 255), thickness=2, circle_radius=3),  # Red landmarks
                        self.mp_drawing.DrawingSpec(color=(0, 0, 255), thickness=2)  # Red connections
                    )
                    
                    # Store landmarks for socket transmission
                    landmarks_data = []
                    for landmark in hand_landmarks.landmark:
                        landmarks_data.append({
                            'x': landmark.x,
                            'y': landmark.y,
                            'z': landmark.z
                        })
                    self.hand_landmarks_list.append(landmarks_data)
            
            # Store processed frame
            self.frame = frame.copy()
            
            # Send to clients if server is running
            if self.server_running and self.clients:
                self.broadcast_frame(frame, self.hand_landmarks_list)
            
            # Display frame
            self.display_frame(frame)
            
            # Calculate FPS
            fps_counter += 1
            if time.time() - fps_time > 1:
                fps = fps_counter
                fps_counter = 0
                fps_time = time.time()
                
            # Update stats
            self.stats_label.config(text=f"FPS: {fps} | Hands Detected: {hands_detected} | Clients: {len(self.clients)}")
    
    def display_frame(self, frame):
        """Display frame on canvas"""
        # Resize frame to fit canvas
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        
        if canvas_width > 1 and canvas_height > 1:
            # Calculate aspect ratio
            frame_height, frame_width = frame.shape[:2]
            aspect_ratio = frame_width / frame_height
            
            if canvas_width / canvas_height > aspect_ratio:
                new_height = canvas_height
                new_width = int(new_height * aspect_ratio)
            else:
                new_width = canvas_width
                new_height = int(new_width / aspect_ratio)
            
            frame = cv2.resize(frame, (new_width, new_height), interpolation=cv2.INTER_LINEAR)
        
        # Convert to PhotoImage
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(frame_rgb)
        photo = ImageTk.PhotoImage(image=img)
        
        # Update canvas without clearing (prevents flicker)
        if self.canvas_image is None:
            self.canvas_image = self.canvas.create_image(
                canvas_width // 2, canvas_height // 2, 
                image=photo, anchor=tk.CENTER
            )
        else:
            self.canvas.itemconfig(self.canvas_image, image=photo)
            self.canvas.coords(self.canvas_image, canvas_width // 2, canvas_height // 2)
        
        self.canvas.image = photo  # Keep a reference
    
    def toggle_server(self):
        """Start or stop the socket server"""
        if not self.server_running:
            self.server_running = True
            self.server_button.config(text="Stop Server", bg="#e74c3c")
            self.server_status_label.config(text=f"Server: ON (Port {self.server_port})", fg="#27ae60")
            threading.Thread(target=self.run_server, daemon=True).start()
        else:
            self.server_running = False
            self.server_button.config(text="Start Server", bg="#3498db")
            self.server_status_label.config(text="Server: OFF", fg="#e74c3c")
            if self.server_socket:
                self.server_socket.close()
            self.clients = []
    
    def run_server(self):
        """Run the socket server"""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)  # Disable Nagle's algorithm
            self.server_socket.bind(('0.0.0.0', self.server_port))
            self.server_socket.listen(5)
            
            self.info_label.config(text=f"Server listening on {self.get_local_ip()}:{self.server_port}")
            
            while self.server_running:
                try:
                    self.server_socket.settimeout(1.0)
                    client_socket, address = self.server_socket.accept()
                    client_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)  # Disable Nagle's for client too
                    self.clients.append(client_socket)
                    print(f"Client connected: {address}")
                    threading.Thread(target=self.handle_client, args=(client_socket,), daemon=True).start()
                except socket.timeout:
                    continue
                except Exception as e:
                    if self.server_running:
                        print(f"Server error: {e}")
                    break
        except Exception as e:
            self.info_label.config(text=f"Server error: {e}")
            self.server_running = False
            self.server_button.config(text="Start Server", bg="#3498db")
            self.server_status_label.config(text="Server: OFF", fg="#e74c3c")
    
    def handle_client(self, client_socket):
        """Handle individual client connection"""
        try:
            while self.server_running and client_socket in self.clients:
                pass  # Client handling is done in broadcast_frame
        except:
            pass
        finally:
            if client_socket in self.clients:
                self.clients.remove(client_socket)
            try:
                client_socket.close()
            except:
                pass
    
    def broadcast_frame(self, frame, landmarks):
        """Send frame and landmarks to all connected clients"""
        try:
            # Resize frame before encoding to reduce bandwidth
            height, width = frame.shape[:2]
            max_width = 640  # Reduce resolution for faster transmission
            if width > max_width:
                scale = max_width / width
                new_width = max_width
                new_height = int(height * scale)
                frame = cv2.resize(frame, (new_width, new_height), interpolation=cv2.INTER_LINEAR)
            
            # Encode frame as JPEG with lower quality for speed
            _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 60])
            data = pickle.dumps({
                'frame': buffer,
                'landmarks': landmarks
            })
            
            # Send to all clients
            message = struct.pack("Q", len(data)) + data
            
            disconnected_clients = []
            for client in self.clients:
                try:
                    client.sendall(message)
                except:
                    disconnected_clients.append(client)
            
            # Remove disconnected clients
            for client in disconnected_clients:
                if client in self.clients:
                    self.clients.remove(client)
                try:
                    client.close()
                except:
                    pass
        except Exception as e:
            print(f"Broadcast error: {e}")
    
    def get_local_ip(self):
        """Get local IP address"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"
    
    def on_closing(self):
        """Cleanup on application close"""
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
        
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = HandTrackingApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()
