import glfw
from OpenGL.GL import *
from OpenGL.GLU import *
import numpy as np
import sys
import socket
import pickle
import struct
import threading
from hand_3d_model import Hand3DModel

class Hand3DViewer:
    def __init__(self, width=1280, height=720):
        self.width = width
        self.height = height
        self.window = None
        
        # Camera settings
        self.camera_distance = 3.0
        self.camera_yaw = 0.0
        self.camera_pitch = 0.0
        self.mouse_last_x = 0
        self.mouse_last_y = 0
        self.mouse_dragging = False
        
        # Hand models (left and right)
        self.hands = [
            Hand3DModel(color=(1.0, 0.0, 0.0)),  # Red hand
            Hand3DModel(color=(0.0, 0.5, 1.0))   # Blue hand
        ]
        
        # Socket connection
        self.client_socket = None
        self.is_connected = False
        self.is_receiving = False
        self.server_ip = "127.0.0.1"
        self.server_port = 5555
        
        # Rendering mode
        self.wireframe_mode = False
        self.show_grid = True
        
        # FPS tracking
        self.frame_count = 0
        self.fps = 0
        self.last_fps_time = 0
        
    def init_glfw(self):
        """Initialize GLFW and create window"""
        if not glfw.init():
            sys.exit(1)
        
        # Create window
        self.window = glfw.create_window(self.width, self.height, "3D Hand Tracking Viewer", None, None)
        if not self.window:
            glfw.terminate()
            sys.exit(1)
        
        glfw.make_context_current(self.window)
        glfw.set_window_size_callback(self.window, self.on_resize)
        glfw.set_mouse_button_callback(self.window, self.on_mouse_button)
        glfw.set_cursor_pos_callback(self.window, self.on_mouse_move)
        glfw.set_scroll_callback(self.window, self.on_scroll)
        glfw.set_key_callback(self.window, self.on_key)
        
        # Disable VSync for maximum performance
        glfw.swap_interval(0)
        
    def init_opengl(self):
        """Initialize OpenGL settings"""
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_LIGHTING)
        glEnable(GL_LIGHT0)
        glEnable(GL_COLOR_MATERIAL)
        glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)
        
        # Enable backface culling for performance
        glEnable(GL_CULL_FACE)
        glCullFace(GL_BACK)
        
        # Smooth shading
        glShadeModel(GL_SMOOTH)
        
        # Set up lighting
        glLightfv(GL_LIGHT0, GL_POSITION, [2, 3, 2, 0])
        glLightfv(GL_LIGHT0, GL_AMBIENT, [0.3, 0.3, 0.3, 1])
        glLightfv(GL_LIGHT0, GL_DIFFUSE, [0.9, 0.9, 0.9, 1])
        glLightfv(GL_LIGHT0, GL_SPECULAR, [0.5, 0.5, 0.5, 1])
        
        # Add second light for better illumination
        glEnable(GL_LIGHT1)
        glLightfv(GL_LIGHT1, GL_POSITION, [-2, -1, 2, 0])
        glLightfv(GL_LIGHT1, GL_AMBIENT, [0.1, 0.1, 0.1, 1])
        glLightfv(GL_LIGHT1, GL_DIFFUSE, [0.4, 0.4, 0.4, 1])
        
        # Background color
        glClearColor(0.1, 0.1, 0.15, 1.0)
        
        # Set up perspective
        self.on_resize(self.window, self.width, self.height)
    
    def on_resize(self, window, width, height):
        """Handle window resize"""
        if height == 0:
            height = 1
        
        self.width = width
        self.height = height
        
        glViewport(0, 0, width, height)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(45, width / height, 0.1, 100.0)
        glMatrixMode(GL_MODELVIEW)
    
    def on_mouse_button(self, window, button, action, mods):
        """Handle mouse button events"""
        if button == glfw.MOUSE_BUTTON_LEFT:
            if action == glfw.PRESS:
                self.mouse_dragging = True
                self.mouse_last_x, self.mouse_last_y = glfw.get_cursor_pos(window)
            elif action == glfw.RELEASE:
                self.mouse_dragging = False
    
    def on_mouse_move(self, window, xpos, ypos):
        """Handle mouse movement for camera rotation"""
        if self.mouse_dragging:
            dx = xpos - self.mouse_last_x
            dy = ypos - self.mouse_last_y
            
            self.camera_yaw += dx * 0.5
            self.camera_pitch += dy * 0.5
            
            # Clamp pitch
            self.camera_pitch = max(-89, min(89, self.camera_pitch))
            
            self.mouse_last_x = xpos
            self.mouse_last_y = ypos
    
    def on_scroll(self, window, xoffset, yoffset):
        """Handle mouse scroll for zoom"""
        self.camera_distance -= yoffset * 0.2
        self.camera_distance = max(0.5, min(10.0, self.camera_distance))
    
    def on_key(self, window, key, scancode, action, mods):
        """Handle keyboard input"""
        if action == glfw.PRESS:
            if key == glfw.KEY_ESCAPE:
                glfw.set_window_should_close(window, True)
            elif key == glfw.KEY_W:
                self.wireframe_mode = not self.wireframe_mode
                print(f"Wireframe mode: {'ON' if self.wireframe_mode else 'OFF'}")
            elif key == glfw.KEY_G:
                self.show_grid = not self.show_grid
                print(f"Grid: {'ON' if self.show_grid else 'OFF'}")
            elif key == glfw.KEY_C:
                if not self.is_connected:
                    self.connect_to_server()
                else:
                    self.disconnect_from_server()
            elif key == glfw.KEY_R:
                # Reset camera
                self.camera_distance = 3.0
                self.camera_yaw = 0.0
                self.camera_pitch = 0.0
    
    def connect_to_server(self, ip=None, port=None):
        """Connect to hand tracking server"""
        if ip:
            self.server_ip = ip
        if port:
            self.server_port = port
        
        try:
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self.client_socket.connect((self.server_ip, self.server_port))
            
            self.is_connected = True
            self.is_receiving = True
            
            print(f"Connected to {self.server_ip}:{self.server_port}")
            
            # Start receiving thread
            threading.Thread(target=self.receive_data, daemon=True).start()
            
        except Exception as e:
            print(f"Connection failed: {e}")
            self.is_connected = False
    
    def disconnect_from_server(self):
        """Disconnect from server"""
        self.is_receiving = False
        self.is_connected = False
        
        if self.client_socket:
            try:
                self.client_socket.close()
            except:
                pass
        
        print("Disconnected from server")
    
    def receive_data(self):
        """Receive hand tracking data from server"""
        data = b""
        payload_size = struct.calcsize("Q")
        
        while self.is_receiving:
            try:
                # Retrieve message size
                while len(data) < payload_size:
                    packet = self.client_socket.recv(16384)
                    if not packet:
                        raise ConnectionError("Connection closed by server")
                    data += packet
                
                packed_msg_size = data[:payload_size]
                data = data[payload_size:]
                msg_size = struct.unpack("Q", packed_msg_size)[0]
                
                # Retrieve full message
                while len(data) < msg_size:
                    packet = self.client_socket.recv(16384)
                    if not packet:
                        raise ConnectionError("Connection closed by server")
                    data += packet
                
                frame_data = data[:msg_size]
                data = data[msg_size:]
                
                # Deserialize data
                received = pickle.loads(frame_data)
                landmarks = received['landmarks']
                
                # Update hand models
                for i, hand_data in enumerate(landmarks[:2]):  # Max 2 hands
                    if i < len(self.hands):
                        self.hands[i].update_landmarks(hand_data)
                
                # Clear unused hands
                for i in range(len(landmarks), len(self.hands)):
                    self.hands[i].update_landmarks(None)
                
            except Exception as e:
                if self.is_receiving:
                    print(f"Receive error: {e}")
                    self.disconnect_from_server()
                break
    
    def setup_camera(self):
        """Setup camera view"""
        glLoadIdentity()
        
        # Calculate camera position
        cam_x = self.camera_distance * np.sin(np.radians(self.camera_yaw)) * np.cos(np.radians(self.camera_pitch))
        cam_y = self.camera_distance * np.sin(np.radians(self.camera_pitch))
        cam_z = self.camera_distance * np.cos(np.radians(self.camera_yaw)) * np.cos(np.radians(self.camera_pitch))
        
        gluLookAt(cam_x, cam_y, cam_z,  # Camera position
                  0, 0, 0,               # Look at origin
                  0, 1, 0)               # Up vector
    
    def draw_grid(self):
        """Draw a reference grid"""
        if not self.show_grid:
            return
            
        glDisable(GL_LIGHTING)
        glColor3f(0.3, 0.3, 0.3)
        glBegin(GL_LINES)
        
        for i in range(-10, 11):
            # Grid lines along X
            glVertex3f(i * 0.2, 0, -2)
            glVertex3f(i * 0.2, 0, 2)
            # Grid lines along Z
            glVertex3f(-2, 0, i * 0.2)
            glVertex3f(2, 0, i * 0.2)
        
        glEnd()
        
        # Draw axes
        glBegin(GL_LINES)
        # X axis - Red
        glColor3f(1, 0, 0)
        glVertex3f(0, 0, 0)
        glVertex3f(1, 0, 0)
        # Y axis - Green
        glColor3f(0, 1, 0)
        glVertex3f(0, 0, 0)
        glVertex3f(0, 1, 0)
        # Z axis - Blue
        glColor3f(0, 0, 1)
        glVertex3f(0, 0, 0)
        glVertex3f(0, 0, 1)
        glEnd()
        
        glEnable(GL_LIGHTING)
    
    def render(self):
        """Main render loop"""
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        
        glMatrixMode(GL_MODELVIEW)
        self.setup_camera()
        
        # Draw grid
        self.draw_grid()
        
        # Draw hands
        for hand in self.hands:
            if self.wireframe_mode:
                hand.draw_wireframe()
            else:
                hand.draw()
        
        # Calculate and display FPS
        import time
        current_time = time.time()
        self.frame_count += 1
        
        if current_time - self.last_fps_time > 1.0:
            self.fps = self.frame_count
            self.frame_count = 0
            self.last_fps_time = current_time
            glfw.set_window_title(self.window, f"3D Hand Tracking Viewer - FPS: {self.fps}")
        
        glfw.swap_buffers(self.window)
    
    def run(self):
        """Main application loop"""
        self.init_glfw()
        self.init_opengl()
        
        print("=" * 60)
        print("3D Hand Tracking Viewer")
        print("=" * 60)
        print("Controls:")
        print("  - Left Mouse Drag: Rotate camera")
        print("  - Mouse Wheel: Zoom in/out")
        print("  - W: Toggle wireframe mode")
        print("  - G: Toggle grid")
        print("  - C: Connect/Disconnect from server")
        print("  - R: Reset camera")
        print("  - ESC: Exit")
        print("=" * 60)
        print(f"Server: {self.server_ip}:{self.server_port}")
        print("Press 'C' to connect or run with --connect flag")
        print("=" * 60)
        
        while not glfw.window_should_close(self.window):
            self.render()
            glfw.poll_events()
        
        self.disconnect_from_server()
        glfw.terminate()

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='3D Hand Tracking Viewer')
    parser.add_argument('--ip', type=str, default='127.0.0.1', help='Server IP address')
    parser.add_argument('--port', type=int, default=5555, help='Server port')
    parser.add_argument('--connect', action='store_true', help='Auto-connect on startup')
    parser.add_argument('--width', type=int, default=1280, help='Window width')
    parser.add_argument('--height', type=int, default=720, help='Window height')
    
    args = parser.parse_args()
    
    viewer = Hand3DViewer(width=args.width, height=args.height)
    viewer.server_ip = args.ip
    viewer.server_port = args.port
    
    if args.connect:
        viewer.connect_to_server()
    
    viewer.run()

if __name__ == "__main__":
    main()
