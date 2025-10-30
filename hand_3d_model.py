import numpy as np
from OpenGL.GL import *
from OpenGL.GLU import *
import math

# MediaPipe hand landmark indices
# https://google.github.io/mediapipe/solutions/hands.html
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

# Hand connections (bones)
HAND_CONNECTIONS = [
    # Thumb
    (WRIST, THUMB_CMC),
    (THUMB_CMC, THUMB_MCP),
    (THUMB_MCP, THUMB_IP),
    (THUMB_IP, THUMB_TIP),
    
    # Index finger
    (WRIST, INDEX_FINGER_MCP),
    (INDEX_FINGER_MCP, INDEX_FINGER_PIP),
    (INDEX_FINGER_PIP, INDEX_FINGER_DIP),
    (INDEX_FINGER_DIP, INDEX_FINGER_TIP),
    
    # Middle finger
    (WRIST, MIDDLE_FINGER_MCP),
    (MIDDLE_FINGER_MCP, MIDDLE_FINGER_PIP),
    (MIDDLE_FINGER_PIP, MIDDLE_FINGER_DIP),
    (MIDDLE_FINGER_DIP, MIDDLE_FINGER_TIP),
    
    # Ring finger
    (WRIST, RING_FINGER_MCP),
    (RING_FINGER_MCP, RING_FINGER_PIP),
    (RING_FINGER_PIP, RING_FINGER_DIP),
    (RING_FINGER_DIP, RING_FINGER_TIP),
    
    # Pinky
    (WRIST, PINKY_MCP),
    (PINKY_MCP, PINKY_PIP),
    (PINKY_PIP, PINKY_DIP),
    (PINKY_DIP, PINKY_TIP),
    
    # Palm
    (INDEX_FINGER_MCP, MIDDLE_FINGER_MCP),
    (MIDDLE_FINGER_MCP, RING_FINGER_MCP),
    (RING_FINGER_MCP, PINKY_MCP),
]

class Hand3DModel:
    def __init__(self, color=(1.0, 0.0, 0.0)):
        self.landmarks = None
        self.color = color
        self.joint_radius = 0.025
        self.bone_thickness = 0.018
        
        # Pre-create quadrics for performance
        self.sphere_quadric = gluNewQuadric()
        self.cylinder_quadric = gluNewQuadric()
        gluQuadricDrawStyle(self.sphere_quadric, GLU_FILL)
        gluQuadricNormals(self.sphere_quadric, GLU_SMOOTH)
        gluQuadricDrawStyle(self.cylinder_quadric, GLU_FILL)
        gluQuadricNormals(self.cylinder_quadric, GLU_SMOOTH)
        
        # Palm mesh indices for creating solid surface
        self.palm_triangles = [
            # Palm surface triangles
            (WRIST, INDEX_FINGER_MCP, MIDDLE_FINGER_MCP),
            (WRIST, MIDDLE_FINGER_MCP, RING_FINGER_MCP),
            (WRIST, RING_FINGER_MCP, PINKY_MCP),
            (WRIST, PINKY_MCP, INDEX_FINGER_MCP),
            (INDEX_FINGER_MCP, MIDDLE_FINGER_MCP, RING_FINGER_MCP),
            (INDEX_FINGER_MCP, RING_FINGER_MCP, PINKY_MCP),
        ]
        
        # Display list for optimization
        self.display_list = None
        self.last_landmarks_hash = None
        
    def update_landmarks(self, landmarks_data):
        """Update hand landmarks from tracking data"""
        if landmarks_data:
            # Convert to numpy array and normalize coordinates
            self.landmarks = np.array([
                [lm['x'], lm['y'], lm['z']] 
                for lm in landmarks_data
            ])
            # Center and scale the hand
            self.landmarks[:, 0] = (self.landmarks[:, 0] - 0.5) * 2
            self.landmarks[:, 1] = -(self.landmarks[:, 1] - 0.5) * 2  # Flip Y
            self.landmarks[:, 2] *= -2  # Scale Z
        else:
            self.landmarks = None
    
    def draw(self):
        """Render the 3D hand model with puffed-up appearance"""
        if self.landmarks is None or len(self.landmarks) < 21:
            return
        
        glPushMatrix()
        glColor3f(*self.color)
        
        # Draw palm surface (puffed)
        self.draw_palm_mesh()
        
        # Draw finger segments as thick cylinders
        for start_idx, end_idx in HAND_CONNECTIONS:
            if start_idx < len(self.landmarks) and end_idx < len(self.landmarks):
                self.draw_bone_fast(
                    self.landmarks[start_idx],
                    self.landmarks[end_idx],
                    self.bone_thickness
                )
        
        # Draw joints as spheres
        darker_color = (self.color[0] * 0.9, self.color[1] * 0.9, self.color[2] * 0.9)
        glColor3f(*darker_color)
        for landmark in self.landmarks:
            self.draw_sphere_fast(landmark, self.joint_radius)
        
        glPopMatrix()
    
    def draw_palm_mesh(self):
        """Draw a solid mesh for the palm to create volume"""
        if self.landmarks is None or len(self.landmarks) < 21:
            return
        
        # Slightly lighter color for palm
        palm_color = (self.color[0] * 0.85, self.color[1] * 0.85, self.color[2] * 0.85)
        glColor3f(*palm_color)
        
        # Draw palm triangles
        glBegin(GL_TRIANGLES)
        for tri in self.palm_triangles:
            for idx in tri:
                if idx < len(self.landmarks):
                    pos = self.landmarks[idx]
                    glVertex3f(pos[0], pos[1], pos[2])
        glEnd()
        
        # Draw back of palm (offset slightly)
        offset = 0.02
        glBegin(GL_TRIANGLES)
        for tri in self.palm_triangles:
            for idx in reversed(tri):  # Reverse winding for back face
                if idx < len(self.landmarks):
                    pos = self.landmarks[idx]
                    glVertex3f(pos[0], pos[1], pos[2] + offset)
        glEnd()
        
        # Draw connecting quads between front and back
        palm_outline = [WRIST, INDEX_FINGER_MCP, MIDDLE_FINGER_MCP, RING_FINGER_MCP, PINKY_MCP]
        glBegin(GL_QUADS)
        for i in range(len(palm_outline)):
            idx1 = palm_outline[i]
            idx2 = palm_outline[(i + 1) % len(palm_outline)]
            
            p1 = self.landmarks[idx1]
            p2 = self.landmarks[idx2]
            
            glVertex3f(p1[0], p1[1], p1[2])
            glVertex3f(p2[0], p2[1], p2[2])
            glVertex3f(p2[0], p2[1], p2[2] + offset)
            glVertex3f(p1[0], p1[1], p1[2] + offset)
        glEnd()
    
    
    def draw_sphere_fast(self, position, radius):
        """Draw a sphere at the given position (optimized)"""
        glPushMatrix()
        glTranslatef(position[0], position[1], position[2])
        gluSphere(self.sphere_quadric, radius, 8, 8)  # Reduced segments for speed
        glPopMatrix()
    
    def draw_bone_fast(self, start, end, thickness):
        """Draw a cylinder (bone) between two points (optimized)"""
        glPushMatrix()
        
        # Calculate direction and length
        direction = end - start
        length = np.linalg.norm(direction)
        
        if length < 0.001:
            glPopMatrix()
            return
        
        direction = direction / length
        
        # Position at start point
        glTranslatef(start[0], start[1], start[2])
        
        # Calculate rotation using faster method
        z_axis = np.array([0, 0, 1])
        
        if abs(1 - np.dot(direction, z_axis)) < 0.001:
            # Already aligned, no rotation
            pass
        elif abs(1 + np.dot(direction, z_axis)) < 0.001:
            # 180 degree rotation
            glRotatef(180, 1, 0, 0)
        else:
            # Use axis-angle rotation
            axis = np.cross(z_axis, direction)
            axis_length = np.linalg.norm(axis)
            if axis_length > 0.001:
                axis = axis / axis_length
                angle = math.acos(np.clip(np.dot(z_axis, direction), -1.0, 1.0)) * 180.0 / math.pi
                glRotatef(angle, axis[0], axis[1], axis[2])
        
        # Draw cylinder with reduced segments for performance
        gluCylinder(self.cylinder_quadric, thickness, thickness, length, 8, 1)
        
        # Draw caps for solid appearance
        gluDisk(self.cylinder_quadric, 0, thickness, 8, 1)
        glPushMatrix()
        glTranslatef(0, 0, length)
        gluDisk(self.cylinder_quadric, 0, thickness, 8, 1)
        glPopMatrix()
        
        glPopMatrix()
    
    def draw_wireframe(self):
        """Draw hand as wireframe (faster, for debugging)"""
        if self.landmarks is None or len(self.landmarks) < 21:
            return
        
        glPushMatrix()
        glColor3f(*self.color)
        
        # Draw bones as lines
        glBegin(GL_LINES)
        for start_idx, end_idx in HAND_CONNECTIONS:
            if start_idx < len(self.landmarks) and end_idx < len(self.landmarks):
                start = self.landmarks[start_idx]
                end = self.landmarks[end_idx]
                glVertex3f(start[0], start[1], start[2])
                glVertex3f(end[0], end[1], end[2])
        glEnd()
        
        # Draw joints as points
        glPointSize(8.0)
        glBegin(GL_POINTS)
        for landmark in self.landmarks:
            glVertex3f(landmark[0], landmark[1], landmark[2])
        glEnd()
        
        glPopMatrix()
