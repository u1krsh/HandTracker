import bpy

# Find armature
armature = None
for obj in bpy.data.objects:
    if obj.type == 'ARMATURE':
        armature = obj
        break

if armature:
    print("=" * 60)
    print(f"Armature: {armature.name}")
    print("=" * 60)
    
    # Switch to pose mode
    bpy.context.view_layer.objects.active = armature
    bpy.ops.object.mode_set(mode='POSE')
    
    # List all bones
    print("BONES:")
    for bone in armature.pose.bones:
        print(f"  - {bone.name}")
    
    print("=" * 60)
    print(f"Total bones: {len(armature.pose.bones)}")
else:
    print("No armature found!")