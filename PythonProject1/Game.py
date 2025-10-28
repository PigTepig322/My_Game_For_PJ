from ursina import *
from math import radians, degrees, atan2, sin, cos, sqrt

app = Ursina()

Sky()
ground = Entity(model='plane', scale=(100,1,100), texture='white_cube', texture_scale=(50,50), collider='box')

class Player(Entity):
    def __init__(self, model_path='cube', scale=1.0, rotation_fix=180, **kwargs):
        super().__init__()
        self.speed = 6
        self.jump_height = 2
        self.gravity = -9.81
        self.velocity = Vec3(0, 0, 0)
        self.grounded = False

        self.collider = None

        self.model_entity = Entity(
            parent=self,
            model=model_path,
            scale=scale,
            rotation_y=rotation_fix,
            y=scale * 0.9
        )

        self.hitbox = Entity(
            parent=self,
            model='cube',
            collider='box',
            color=color.clear,
            scale=(0.8*scale, 1.8*scale, 0.8*scale),
            y=0.9*scale
        )

        for k, v in kwargs.items():
            setattr(self, k, v)

    def update(self):
        x = held_keys['a'] - held_keys['d']
        z = held_keys['s'] - held_keys['w']

        yaw_rad = radians(tpc.yaw)
        cam_dir = Vec3(sin(yaw_rad), 0, cos(yaw_rad))
        cam_right = Vec3(cos(yaw_rad), 0, -sin(yaw_rad))
        move_dir = (cam_dir * z + cam_right * x)

        if move_dir.length() > 0.001:
            move_dir = move_dir.normalized()
            target_rotation = degrees(atan2(move_dir.x, move_dir.z))
            self.rotation_y = lerp_angle(self.rotation_y, target_rotation, time.dt * 12)

        self.position += move_dir * self.speed * time.dt

        origin = self.hitbox.world_position + Vec3(0, self.hitbox.scale_y * 0.5, 0)
        ray = raycast(origin, Vec3(0, -1, 0), distance=self.hitbox.scale_y * 0.6, ignore=(self,))
        self.grounded = ray.hit
        if self.grounded:
            self.velocity.y = 0
            if held_keys['space']:
                self.velocity.y = sqrt(2 * -self.gravity * self.jump_height)
        else:
            self.velocity.y += self.gravity * time.dt

        self.position += self.velocity * time.dt


class ThirdPersonCamera(Entity):
    def __init__(self, target, offset_y=1.6, distance=4.0, smoothing=8.0,
                 min_pitch=-80, max_pitch=80,
                 sensitivity=600, sensitivity_y=600):
        super().__init__()
        self.target = target
        self.offset_y = offset_y
        self.distance = distance
        self.smoothing = smoothing
        self.min_pitch = min_pitch
        self.max_pitch = max_pitch
        self.sensitivity = sensitivity
        self.sensitivity_y = sensitivity_y

        self.yaw = 0
        self.pitch = 10
        mouse.locked = True

    def update(self):
        self.yaw += mouse.velocity[0] * self.sensitivity * time.dt
        self.pitch -= mouse.velocity[1] * self.sensitivity_y * time.dt
        self.pitch = clamp(self.pitch, self.min_pitch, self.max_pitch)

        yaw_rad = radians(self.yaw)
        cam_x = self.target.x + sin(yaw_rad) * self.distance
        cam_z = self.target.z + cos(yaw_rad) * self.distance
        cam_y = self.target.y + self.offset_y + (self.distance * 0.5) * sin(radians(self.pitch))
        cam_y = max(cam_y, self.target.y + 0.2)

        desired = Vec3(cam_x, cam_y, cam_z)
        camera.world_position = lerp(camera.world_position, desired, time.dt * self.smoothing)
        camera.look_at(self.target.position + Vec3(0, self.offset_y, 0))
        camera.rotation_z = 0


player = Player(model_path='Knight.glb', scale=1.0, rotation_fix=180)
tpc = ThirdPersonCamera(target=player, distance=4.0)

EditorCamera(enabled=False)

def input(key):
    if key == 'escape':
        application.quit()

app.run()
