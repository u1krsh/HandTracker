import tkinter as tk
from tkinter import messagebox
import socket
import pickle
import struct
import cv2
import numpy as np
from PIL import Image, ImageTk
import threading

class ClientViewer:
    def __init__(self, root):
        self.root = root
        self.root.title("Hand Tracking Client Viewer")
        self.root.geometry("800x650")
        
        self.client_socket = None
        self.is_connected = False
        self.is_receiving = False
        
        self.create_ui()
        
    def create_ui(self):
        # Connection panel
        conn_frame = tk.Frame(self.root, bg="#2c3e50", padx=10, pady=10)
        conn_frame.pack(fill=tk.X)
        
        tk.Label(conn_frame, text="Server IP:", bg="#2c3e50", fg="white", 
                font=("Arial", 10)).pack(side=tk.LEFT, padx=5)
        
        self.ip_entry = tk.Entry(conn_frame, width=20, font=("Arial", 10))
        self.ip_entry.insert(0, "192.168.1.100")  # Default IP
        self.ip_entry.pack(side=tk.LEFT, padx=5)
        
        tk.Label(conn_frame, text="Port:", bg="#2c3e50", fg="white", 
                font=("Arial", 10)).pack(side=tk.LEFT, padx=5)
        
        self.port_entry = tk.Entry(conn_frame, width=8, font=("Arial", 10))
        self.port_entry.insert(0, "5555")
        self.port_entry.pack(side=tk.LEFT, padx=5)
        
        self.connect_button = tk.Button(conn_frame, text="Connect", command=self.toggle_connection,
                                        bg="#27ae60", fg="white", font=("Arial", 10, "bold"), padx=20)
        self.connect_button.pack(side=tk.LEFT, padx=10)
        
        self.status_label = tk.Label(conn_frame, text="Disconnected", bg="#2c3e50",
                                     fg="#e74c3c", font=("Arial", 10, "bold"))
        self.status_label.pack(side=tk.LEFT, padx=10)
        
        # Info panel
        info_frame = tk.Frame(self.root, bg="#34495e", padx=10, pady=5)
        info_frame.pack(fill=tk.X)
        
        self.info_label = tk.Label(info_frame, text="Enter server IP and click Connect", 
                                   bg="#34495e", fg="white", font=("Arial", 9))
        self.info_label.pack()
        
        # Video display
        self.video_frame = tk.Frame(self.root, bg="black")
        self.video_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.canvas = tk.Canvas(self.video_frame, bg="black", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas_image = None  # Store canvas image reference
        
        # Stats panel
        stats_frame = tk.Frame(self.root, bg="#2c3e50", padx=10, pady=5)
        stats_frame.pack(fill=tk.X)
        
        self.stats_label = tk.Label(stats_frame, text="FPS: 0 | Hands: 0", 
                                    bg="#2c3e50", fg="white", font=("Arial", 9))
        self.stats_label.pack()
        
    def toggle_connection(self):
        """Connect or disconnect from server"""
        if not self.is_connected:
            server_ip = self.ip_entry.get().strip()
            server_port = self.port_entry.get().strip()
            
            if not server_ip or not server_port:
                messagebox.showerror("Error", "Please enter server IP and port")
                return
            
            try:
                port = int(server_port)
                self.connect_to_server(server_ip, port)
            except ValueError:
                messagebox.showerror("Error", "Invalid port number")
        else:
            self.disconnect_from_server()
    
    def connect_to_server(self, ip, port):
        """Connect to the hand tracking server"""
        try:
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)  # Disable Nagle's algorithm for lower latency
            self.client_socket.connect((ip, port))
            
            self.is_connected = True
            self.is_receiving = True
            
            self.connect_button.config(text="Disconnect", bg="#e74c3c")
            self.status_label.config(text=f"Connected to {ip}:{port}", fg="#27ae60")
            self.info_label.config(text="Receiving hand tracking data...")
            
            # Start receiving thread
            threading.Thread(target=self.receive_data, daemon=True).start()
            
        except Exception as e:
            messagebox.showerror("Connection Error", f"Failed to connect: {str(e)}")
            self.info_label.config(text=f"Connection failed: {str(e)}")
    
    def disconnect_from_server(self):
        """Disconnect from server"""
        self.is_receiving = False
        self.is_connected = False
        
        if self.client_socket:
            try:
                self.client_socket.close()
            except:
                pass
        
        self.connect_button.config(text="Connect", bg="#27ae60")
        self.status_label.config(text="Disconnected", fg="#e74c3c")
        self.info_label.config(text="Disconnected from server")
        
        # Clear canvas
        if self.canvas_image:
            self.canvas.delete(self.canvas_image)
            self.canvas_image = None
    
    def receive_data(self):
        """Receive and display frames from server"""
        import time
        fps_counter = 0
        fps_time = time.time()
        fps = 0
        
        data = b""
        payload_size = struct.calcsize("Q")
        
        while self.is_receiving:
            try:
                # Retrieve message size
                while len(data) < payload_size:
                    packet = self.client_socket.recv(16384)  # Increased buffer size
                    if not packet:
                        raise ConnectionError("Connection closed by server")
                    data += packet
                
                packed_msg_size = data[:payload_size]
                data = data[payload_size:]
                msg_size = struct.unpack("Q", packed_msg_size)[0]
                
                # Retrieve full message with larger buffer
                while len(data) < msg_size:
                    packet = self.client_socket.recv(16384)  # Increased buffer size
                    if not packet:
                        raise ConnectionError("Connection closed by server")
                    data += packet
                
                frame_data = data[:msg_size]
                data = data[msg_size:]
                
                # Deserialize data
                received = pickle.loads(frame_data)
                frame_buffer = received['frame']
                landmarks = received['landmarks']
                
                # Decode frame
                frame = cv2.imdecode(np.frombuffer(frame_buffer, dtype=np.uint8), cv2.IMREAD_COLOR)
                
                # Display frame (use after to avoid blocking)
                hands_count = len(landmarks) if landmarks else 0
                self.root.after(0, self.display_frame, frame, hands_count)
                
                # Calculate FPS
                fps_counter += 1
                if time.time() - fps_time > 1:
                    fps = fps_counter
                    fps_counter = 0
                    fps_time = time.time()
                    
                    # Update stats
                    self.root.after(0, self.update_stats, fps, hands_count)
                
            except Exception as e:
                if self.is_receiving:
                    print(f"Receive error: {e}")
                    self.info_label.config(text=f"Connection lost: {str(e)}")
                    self.root.after(0, self.disconnect_from_server)
                break
    
    
    def update_stats(self, fps, hands_count):
        """Update statistics label"""
        self.stats_label.config(text=f"FPS: {fps} | Hands: {hands_count}")
    
    def display_frame(self, frame, hands_count=0):
        """Display received frame on canvas"""
        if not self.is_receiving:
            return
            
        try:
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
                
                # Use faster interpolation
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
        except Exception as e:
            print(f"Display error: {e}")
    
    def on_closing(self):
        """Cleanup on application close"""
        self.is_receiving = False
        self.is_connected = False
        
        if self.client_socket:
            try:
                self.client_socket.close()
            except:
                pass
        
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = ClientViewer(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()
