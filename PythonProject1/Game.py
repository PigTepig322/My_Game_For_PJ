from pygame import color
from ursina import *
from ursina import lerp_angle
from random import uniform

app = Ursina()

SPEED = 5
DASH_SPEED = 25
DASH_TIME = 0.15
DASH_COOLDOWN = 1.0
JUMP_HEIGHT = 5
GRAVITY = 9.8
CAM_DIST = 10
CAM_HEIGHT = 2
MOUSE_SENS = 800

Sky()
ground = Entity(model='plane', scale=(100,0,100), collider='box')

class DragonBoss(Entity):
    def __init__(self, target=None, **kwargs):
        super().__init__(
            model='',
            scale=10,
            position=(0, 2, 50),
            collider='box',
            **kwargs
        )
        self.target = target
        self.state = 'idle'
        self.in_fight = False
        self.trigger_radius = 30
        self.fly_height = 15
        self.attack_cooldown = 0
        self.attack_interval = 3

        self.animation = 'stand'  # стартовая анимация

    def play_anim(self, name):
        try:
            self.animation = name
            print(f"▶️ Анимация: {name}")
        except Exception as e:
            print(f"Не удалось запустить анимацию {name}: {e}")

    def start_fight(self):
        if not self.in_fight:
            self.in_fight = True
            self.play_anim('run')
            print("Босс проснулся!")
            invoke(self.fly_up, delay=0.5)

    def stop_fight(self):
        if self.in_fight:
            print("Игрок ушёл — дракон возвращается в ожидание.")
            self.in_fight = False
            self.play_anim('stand')
            self.animate_y(2, duration=2, curve=curve.in_out_sine)

    def fly_up(self):
        self.animate_y(self.fly_height, duration=3, curve=curve.out_cubic)
        invoke(self.start_attack, delay=3)

    def start_attack(self):
        if self.in_fight:
            self.state = 'attack'
            self.play_anim('skill01')
            print("Дракон атакует!")

    def update(self):
        if not self.target:
            return

        dist = distance(self, self.target)
        if dist <= self.trigger_radius:
            if not self.in_fight:
                self.start_fight()
        else:
            if self.in_fight:
                self.stop_fight()

    def update(self):
        if not self.target:
            return

        dist = distance(self, self.target)

        if dist <= self.trigger_radius:
            if not self.in_fight:
                self.start_fight()
        else:
            if self.in_fight:
                self.stop_fight()

        if self.state == 'skill01':
            self.look_at(self.target.position)
            self.attack_cooldown -= time.dt
            if self.attack_cooldown <= 0:
                self.shoot_fireball()
                self.attack_cooldown = self.attack_interval

    def shoot_fireball(self):
        Fireball(position=self.position + Vec3(0, -1, 0), target=self.target)

class Fireball(Entity):
    def __init__(self, position, target=None, **kwargs):
        super().__init__(
            model='sphere',
            color=color.orange,
            scale=0.6,
            position=position,
            collider='sphere',
            **kwargs
        )
        self.speed = 10
        self.target = target
        self.tail_timer = 0

    def update(self):
        if not hasattr(self, 'position') or not self.enabled:
            return

        if self.target and self.target.enabled:
            direction = (self.target.position - self.position).normalized()
        else:
            direction = Vec3(0, -1, 0)

        self.position += direction * time.dt * self.speed

        self.tail_timer += time.dt
        if self.tail_timer > 0.03:
            self.create_tail()
            self.tail_timer = 0

        hit_info = raycast(self.position, direction, distance=0.6, ignore=[self])
        if hit_info.hit:
            if self.target and hit_info.entity == self.target:
                print("Игрок получил урон!")
            self.explode()
            return

        if self.y < 0:
            self.explode()

    def create_tail(self):
        tail = Entity(
            model='sphere',
            color=color.rgb(uniform(150, 200), uniform(200, 255), 255),
            scale=uniform(0.2, 0.4),
            position=self.position + Vec3(
                uniform(-0.1, 0.1),
                uniform(-0.1, 0.1),
                uniform(-0.1, 0.1)
            ),
            eternal=False
        )
        tail.fade_out(0.2)
        destroy(tail, delay=0.3)

    def explode(self):
        explosion = Entity(
            model='sphere',
            color=color.rgb(255, uniform(50, 100), 0),
            scale=1.5,
            position=self.position,
        )
        explosion.animate_scale(3, duration=0.2)
        explosion.fade_out(0.3)
        destroy(explosion, delay=0.4)
        destroy(self)


player = Entity(
    model='knight.glb',
    scale=0.035,
    origin_y=-0.9,
    position=(0, 10, 0),
    collider='box'
)

mouse.locked = True
camera.rotation_x = 15
yaw = 0
pitch = 15

is_dashing = False
dash_time = 0
dash_cooldown = 0
dash_dir = Vec3(0, 0, 0)
move = Vec3(0, 0, 0)

velocity_y = 0
is_grounded = False


def update():
    global yaw, pitch, is_dashing, dash_time, dash_cooldown, dash_dir, move
    global velocity_y, is_grounded

    dt = time.dt

    if mouse.locked:
        yaw += mouse.velocity[0] * MOUSE_SENS * dt
        pitch -= mouse.velocity[1] * MOUSE_SENS * dt
        pitch = clamp(pitch, -10, 60)

    camera.rotation = Vec3(pitch, yaw, 0)
    cam_target = player.position + Vec3(0, CAM_HEIGHT, 0)
    camera.position = cam_target - camera.forward * CAM_DIST
    camera.look_at(cam_target)

    forward = Vec3(camera.forward.x, 0, camera.forward.z).normalized()
    right = Vec3(camera.right.x, 0, camera.right.z).normalized()

    move = Vec3(0, 0, 0)
    if held_keys['w']: move += forward
    if held_keys['s']: move -= forward
    if held_keys['a']: move -= right
    if held_keys['d']: move += right
    if move.length() > 0:
        move = move.normalized()

    if is_dashing:
        player.position += dash_dir * DASH_SPEED * dt
        dash_time -= dt
        if dash_time <= 0:
            is_dashing = False
            dash_cooldown = DASH_COOLDOWN
    else:
        player.position += move * SPEED * dt
        if dash_cooldown > 0:
            dash_cooldown -= dt

    ray = raycast(player.position + Vec3(0, 0.1, 0), Vec3(0, -1, 0), distance=0.1, ignore=[player])
    is_grounded = ray.hit

    if not is_grounded:
        velocity_y -= GRAVITY * dt
    else:
        velocity_y = max(0, velocity_y)

    player.position += Vec3(0, velocity_y * dt, 0)

    player.rotation_y = lerp_angle(player.rotation_y, camera.rotation_y + 180, 8 * dt)


def input(key):
    global is_dashing, dash_time, dash_dir, dash_cooldown, move
    global velocity_y

    if key == 'escape':
        application.quit()

    if key == 'q' and not is_dashing and dash_cooldown <= 0:
        if move.length() > 0:
            dash_dir = move.normalized()
            is_dashing = True
            dash_time = DASH_TIME

    if key == 'space' and is_grounded:
        velocity_y = JUMP_HEIGHT

dragon = DragonBoss(target = player, trigger_radius=50)

snowflakes = []

def spawn_snowflake():
    flake = Entity(
        model='quad',
        color=color.rgb(240, 240, 255),
        scale=0.03,
        position=(uniform(-20, 20), uniform(5, 10), uniform(-20, 20)),
        rotation=(uniform(0, 360), 0, 0),
        billboard=True
    )
    snowflakes.append(flake)

for i in range(100):
    spawn_snowflake()

def update_snow():
    for flake in snowflakes:
        flake.y -= time.dt * 1.5
        flake.rotation_x += time.dt * 50
        if flake.y < -1:
            flake.y = uniform(5, 10)
            flake.x = uniform(-20, 20)
            flake.z = uniform(-20, 20)

def update():
    global yaw, pitch, is_dashing, dash_time, dash_cooldown, dash_dir, move
    global velocity_y, is_grounded

    dt = time.dt

    update_snow()

    if mouse.locked:
        yaw += mouse.velocity[0] * MOUSE_SENS * dt
        pitch -= mouse.velocity[1] * MOUSE_SENS * dt
        pitch = clamp(pitch, -10, 60)

    camera.rotation = Vec3(pitch, yaw, 0)
    cam_target = player.position + Vec3(0, CAM_HEIGHT, 0)
    camera.position = cam_target - camera.forward * CAM_DIST
    camera.look_at(cam_target)

    forward = Vec3(camera.forward.x, 0, camera.forward.z).normalized()
    right = Vec3(camera.right.x, 0, camera.right.z).normalized()

    move = Vec3(0, 0, 0)
    if held_keys['w']: move += forward
    if held_keys['s']: move -= forward
    if held_keys['a']: move -= right
    if held_keys['d']: move += right
    if move.length() > 0:
        move = move.normalized()

    if is_dashing:
        player.position += dash_dir * DASH_SPEED * dt
        dash_time -= dt
        if dash_time <= 0:
            is_dashing = False
            dash_cooldown = DASH_COOLDOWN
    else:
        player.position += move * SPEED * dt
        if dash_cooldown > 0:
            dash_cooldown -= dt

    ray = raycast(player.position + Vec3(0, 0.1, 0), Vec3(0, -1, 0), distance=0.1, ignore=[player])
    is_grounded = ray.hit

    if not is_grounded:
        velocity_y -= GRAVITY * dt
    else:
        velocity_y = max(0, velocity_y)

    player.position += Vec3(0, velocity_y * dt, 0)
    player.rotation_y = lerp_angle(player.rotation_y, camera.rotation_y + 180, 8 * dt)
app.run()
