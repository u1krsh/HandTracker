"""
Blender Hand Tracking - Real-time hand control in Blender
Install: Run this script inside Blender's Scripting workspace
"""

import bpy
import socket
import pickle
import struct
import threading
import mathutils
from mathutils import Vector, Euler
import time

# MediaPipe hand landmark indices
WRIST = 0
THUMB_CMC = 1
THUMB_MCP = 2
THUMB_IP = 3
THUMB_TIP = 4
INDEX_FINGER_MCP = 5
INDEX_FINGER_PIP = 6
INDEX_FINGER_DIP = 7
INDEX_FINGER_TIP = 8
MIDDLE_FINGER_MCP = 9
MIDDLE_FINGER_PIP = 10
MIDDLE_FINGER_DIP = 11
MIDDLE_FINGER_TIP = 12
RING_FINGER_MCP = 13
RING_FINGER_PIP = 14
RING_FINGER_DIP = 15
RING_FINGER_TIP = 16
PINKY_MCP = 17
PINKY_PIP = 18
PINKY_DIP = 19
PINKY_TIP = 20

class BlenderHandTracker:
    def __init__(self):
        self.server_ip = "127.0.0.1"
        self.server_port = 5555
        self.client_socket = None
        self.is_connected = False
        self.is_receiving = False
        self.running = True
        
        # Hand data (minimal memory)
        self.hand_data = [None, None]  # Max 2 hands
        
        # Blender objects
        self.hand_objects = []
        
        # Setup scene
        self.setup_scene()
        
    def setup_scene(self):
        """Setup Blender scene with hand empties"""
        # Clear existing hand objects
        bpy.ops.object.select_all(action='DESELECT')
        for obj in bpy.data.objects:
            if obj.name.startswith("Hand_"):
                obj.select_set(True)
        bpy.ops.object.delete()
        
        # Create two hand rigs (minimal memory footprint)
        for hand_idx in range(2):
            hand_name = f"Hand_{hand_idx}"
            empties = {}
            
            # Create empty for each landmark
            for i in range(21):
                empty = bpy.data.objects.new(f"{hand_name}_L{i}", None)
                empty.empty_display_size = 0.02
                empty.empty_display_type = 'SPHERE'
                bpy.context.collection.objects.link(empty)
                empties[i] = empty
            
            # Create bones (curves for visual feedback)
            self.create_hand_bones(hand_name, empties, hand_idx)
            self.hand_objects.append(empties)
        
        # Set up camera
        if not bpy.data.objects.get("Camera"):
            bpy.ops.object.camera_add(location=(0, -3, 1))
        camera = bpy.data.objects.get("Camera")
        camera.rotation_euler = (1.3, 0, 0)
        bpy.context.scene.camera = camera
        
        # Optimize viewport
        for area in bpy.context.screen.areas:
            if area.type == 'VIEW_3D':
                for space in area.spaces:
                    if space.type == 'VIEW_3D':
                        space.shading.type = 'SOLID'
                        space.overlay.show_floor = False
                        space.overlay.show_axis_x = False
                        space.overlay.show_axis_y = False
        
        print("Scene setup complete")
    
    def create_hand_bones(self, hand_name, empties, hand_idx):
        """Create visual bones between landmarks"""
        connections = [
            (0, 1), (1, 2), (2, 3), (3, 4),  # Thumb
            (0, 5), (5, 6), (6, 7), (7, 8),  # Index
            (0, 9), (9, 10), (10, 11), (11, 12),  # Middle
            (0, 13), (13, 14), (14, 15), (15, 16),  # Ring
            (0, 17), (17, 18), (18, 19), (19, 20),  # Pinky
            (5, 9), (9, 13), (13, 17),  # Palm
        ]
        
        # Create curve for bones
        curve_data = bpy.data.curves.new(f"{hand_name}_Bones", type='CURVE')
        curve_data.dimensions = '3D'
        curve_data.bevel_depth = 0.005
        curve_data.bevel_resolution = 2
        
        # Set color
        if hand_idx == 0:
            mat = bpy.data.materials.new(name=f"{hand_name}_Mat")
            mat.diffuse_color = (1, 0, 0, 1)  # Red
        else:
            mat = bpy.data.materials.new(name=f"{hand_name}_Mat")
            mat.diffuse_color = (0, 0.5, 1, 1)  # Blue
        
        curve_obj = bpy.data.objects.new(f"{hand_name}_Bones", curve_data)
        bpy.context.collection.objects.link(curve_obj)
        curve_obj.data.materials.append(mat)
    
    def connect_to_server(self):
        """Connect to hand tracking server"""
        try:
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self.client_socket.settimeout(0.1)  # Non-blocking with timeout
            self.client_socket.connect((self.server_ip, self.server_port))
            
            self.is_connected = True
            self.is_receiving = True
            
            print(f"Connected to {self.server_ip}:{self.server_port}")
            
            # Start receiving in thread
            thread = threading.Thread(target=self.receive_data, daemon=True)
            thread.start()
            
            return True
            
        except Exception as e:
            print(f"Connection failed: {e}")
            return False
    
    def receive_data(self):
        """Receive hand data (optimized for low latency)"""
        data = b""
        payload_size = struct.calcsize("Q")
        
        while self.is_receiving and self.running:
            try:
                # Retrieve message size
                while len(data) < payload_size:
                    packet = self.client_socket.recv(16384)
                    if not packet:
                        raise ConnectionError("Connection closed")
                    data += packet
                
                packed_msg_size = data[:payload_size]
                data = data[payload_size:]
                msg_size = struct.unpack("Q", packed_msg_size)[0]
                
                # Retrieve full message
                while len(data) < msg_size:
                    packet = self.client_socket.recv(16384)
                    if not packet:
                        raise ConnectionError("Connection closed")
                    data += packet
                
                frame_data = data[:msg_size]
                data = data[msg_size:]
                
                # Deserialize (only landmarks, skip frame for memory)
                received = pickle.loads(frame_data)
                landmarks = received.get('landmarks', [])
                
                # Update hand data (minimal memory)
                for i in range(min(2, len(landmarks))):
                    self.hand_data[i] = landmarks[i]
                
                # Clear unused hands
                for i in range(len(landmarks), 2):
                    self.hand_data[i] = None
                
                # Clear frame data immediately to free memory
                del received
                del frame_data
                
            except socket.timeout:
                continue
            except Exception as e:
                if self.is_receiving:
                    print(f"Receive error: {e}")
                    self.disconnect()
                break
    
    def disconnect(self):
        """Disconnect from server"""
        self.is_receiving = False
        self.is_connected = False
        
        if self.client_socket:
            try:
                self.client_socket.close()
            except:
                pass
        
        print("Disconnected")
    
    def update_hand(self, hand_idx, landmarks_data):
        """Update hand positions in Blender (instant translation)"""
        if not landmarks_data or hand_idx >= len(self.hand_objects):
            return
        
        empties = self.hand_objects[hand_idx]
        hand_name = f"Hand_{hand_idx}"
        
        # Update empties positions (fast)
        for i, lm in enumerate(landmarks_data):
            if i in empties:
                # Convert coordinates (centered, scaled)
                x = (lm['x'] - 0.5) * 2
                y = -(lm['y'] - 0.5) * 2
                z = -lm['z'] * 2
                
                empties[i].location = (x * 0.5 + hand_idx * 1.0, z * 0.5, y * 0.5)
        
        # Update bone curves (fast)
        self.update_bone_curves(hand_name, empties)
    
    def update_bone_curves(self, hand_name, empties):
        """Update curve geometry for bones"""
        curve_obj = bpy.data.objects.get(f"{hand_name}_Bones")
        if not curve_obj:
            return
        
        curve_data = curve_obj.data
        curve_data.splines.clear()
        
        connections = [
            (0, 1), (1, 2), (2, 3), (3, 4),
            (0, 5), (5, 6), (6, 7), (7, 8),
            (0, 9), (9, 10), (10, 11), (11, 12),
            (0, 13), (13, 14), (14, 15), (15, 16),
            (0, 17), (17, 18), (18, 19), (19, 20),
            (5, 9), (9, 13), (13, 17),
        ]
        
        for start_idx, end_idx in connections:
            if start_idx in empties and end_idx in empties:
                spline = curve_data.splines.new('POLY')
                spline.points.add(1)
                spline.points[0].co = (*empties[start_idx].location, 1)
                spline.points[1].co = (*empties[end_idx].location, 1)
    
    def update(self):
        """Main update loop (call this repeatedly)"""
        if not self.is_connected:
            return False
        
        # Update both hands
        for i in range(2):
            if self.hand_data[i]:
                self.update_hand(i, self.hand_data[i])
        
        return True
    
    def stop(self):
        """Cleanup"""
        self.running = False
        self.disconnect()

# Global tracker instance
_tracker = None

def start_tracking(ip="127.0.0.1", port=5555):
    """Start hand tracking"""
    global _tracker
    
    if _tracker:
        _tracker.stop()
    
    _tracker = BlenderHandTracker()
    _tracker.server_ip = ip
    _tracker.server_port = port
    
    if _tracker.connect_to_server():
        print("Hand tracking started!")
        print("Run: bpy.app.timers.register(update_hands)")
        return _tracker
    else:
        print("Failed to connect")
        return None

def update_hands():
    """Timer callback for updating hands"""
    global _tracker
    
    if _tracker and _tracker.update():
        return 0.001  # Update every 1ms for instant response
    else:
        return None  # Stop timer

def stop_tracking():
    """Stop hand tracking"""
    global _tracker
    
    if _tracker:
        _tracker.stop()
        _tracker = None
        bpy.app.timers.unregister(update_hands)
        print("Hand tracking stopped")

# Auto-start if running in Blender
if __name__ == "__main__":
    # Start tracking
    tracker = start_tracking()
    
    if tracker:
        # Register timer for instant updates
        if bpy.app.timers.is_registered(update_hands):
            bpy.app.timers.unregister(update_hands)
        bpy.app.timers.register(update_hands)
        
        print("=" * 60)
        print("BLENDER HAND TRACKING ACTIVE")
        print("=" * 60)
        print("Hands will update in real-time!")
        print("")
        print("To stop: stop_tracking()")
        print("=" * 60)
