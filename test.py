from ursina import *
from direct.actor.Actor import Actor
from ursina.prefabs.first_person_controller import FirstPersonController
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
ground = Entity(model='plane', scale=(100, 0, 100), collider='box', texture='white_cube', texture_scale=(100, 100))


class HealthBar(Entity):
    def __init__(self, max_health=100, is_boss=False, **kwargs):
        super().__init__(**kwargs)
        self.max_health = max_health
        self.current_health = max_health
        self.is_boss = is_boss

        if is_boss:
            # Шкала здоровья для босса (над его головой)
            self.bg = Entity(
                parent=self,
                model='quad',
                color=color.dark_gray,
                scale=(1.5, 0.3),
                position=(0, 1.2, 0),
                billboard=True
            )
            self.fill = Entity(
                parent=self.bg,
                model='quad',
                color=color.red,
                scale=(1, 1),
                position=(-0.49, -0.06, -0.1),
                origin=(-0.5, 0)
            )
        else:
            # Шкала здоровья для игрока (на экране)
            self.bg = Entity(
                parent=camera.ui,
                model='quad',
                color=color.dark_gray,
                scale=(0.4, 0.03),
                position=(-0.7, 0.4, 0)
            )
            self.fill = Entity(
                parent=self.bg,
                model='quad',
                color=color.green,
                scale=(1, 1),
                position=(-0.5, 0, -0.1),
                origin=(-0.5, 0)
            )

        self.update_display()

    def update_display(self):
        """Обновляет отображение шкалы здоровья"""
        health_ratio = self.current_health / self.max_health
        self.fill.scale_x = max(0, health_ratio)  # Защита от отрицательных значений

        # Изменение цвета в зависимости от уровня здоровья
        if health_ratio > 0.6:
            self.fill.color = color.green
        elif health_ratio > 0.3:
            self.fill.color = color.orange
        else:
            self.fill.color = color.red

    def take_damage(self, amount):
        """Наносит урон"""
        self.current_health = max(0, self.current_health - amount)
        self.update_display()
        return self.current_health <= 0

    def heal(self, amount):
        """Восстанавливает здоровье"""
        self.current_health = min(self.max_health, self.current_health + amount)
        self.update_display()


class DragonBoss(Entity):
    def __init__(self, target=None, **kwargs):
        super().__init__(
            scale=20,
            position=(0, 2, 30),
            collider='box',
            **kwargs
        )

        # Безопасная загрузка модели с обработкой ошибок
        self.actor = None
        self.animations_list = []
        self.current_animation = None

        try:
            # Пробуем загрузить модель
            self.actor = Actor("test10.glb")
            if self.actor and not self.actor.is_empty():
                self.actor.reparent_to(self)
                self.actor.setScale(0.1)

                # Получаем список доступных анимаций
                self.animations_list = self.actor.getAnimNames()
                print("🐉 Доступные анимации дракона:", self.animations_list)

                # Запускаем стартовую анимацию
                if self.animations_list:
                    self.current_animation = self.animations_list[0]
                    self.actor.loop(self.current_animation)
                    print(f"▶️ Запущена анимация: {self.current_animation}")
            else:
                raise Exception("Модель не загружена или пустая")

        except Exception as e:
            print(f"❌ Ошибка загрузки анимированной модели: {e}")
            print("🔄 Используем простую модель куба")
            # Запасной вариант - простая модель
            self.model = 'cube'
            self.color = color.red
            self.texture = 'white_cube'

        self.target = target
        self.state = 'idle'
        self.in_fight = False
        self.trigger_radius = 30
        self.fly_height = 8
        self.attack_cooldown = 0
        self.attack_interval = 3

        # Здоровье босса
        self.health_bar = HealthBar(max_health=500, is_boss=True, parent=self)
        self.is_alive = True

    def play_animation(self, anim_name):
        """Воспроизводит анимацию по имени"""
        try:
            if self.actor and not self.actor.is_empty() and anim_name in self.animations_list:
                self.actor.loop(anim_name)
                self.current_animation = anim_name
                print(f"▶️ Дракон: {anim_name}")
            else:
                print(f"ℹ️ Анимация '{anim_name}' недоступна, используется простая модель")
        except Exception as e:
            print(f"❌ Ошибка воспроизведения анимации {anim_name}: {e}")

    def take_damage(self, amount):
        """Наносит урон дракону"""
        if not self.is_alive:
            return

        print(f"🐉 Дракон получает {amount} урона! Осталось здоровья: {self.health_bar.current_health - amount}")
        if self.health_bar.take_damage(amount):
            self.die()
        else:
            # Эффект получения урона
            original_color = self.color
            self.color = color.orange
            invoke(setattr, self, 'color', original_color, delay=0.2)

    def die(self):
        """Смерть дракона"""
        print("💀 Дракон побежден!")
        self.is_alive = False
        self.in_fight = False
        self.state = 'dead'

        # Анимация смерти
        self.play_animation('deaddown')

        # Падение дракона с эффектом
        self.animate_position((self.x, 0, self.z), duration=2, curve=curve.in_out_sine)
        self.animate_rotation((0, 0, 90), duration=2, curve=curve.in_out_sine)
        self.color = color.gray

        # Удаление через время
        if hasattr(self, 'health_bar') and self.health_bar:
            destroy(self.health_bar, delay=2)
        destroy(self, delay=3)

    def start_fight(self):
        if not self.in_fight and self.is_alive:
            self.in_fight = True
            print("🐉 Босс проснулся!")
            self.play_animation('stand')
            invoke(self.fly_up, delay=1.0)

    def stop_fight(self):
        if self.in_fight and self.is_alive:
            print("💤 Игрок ушёл — дракон возвращается в ожидание.")
            self.in_fight = False
            self.play_animation('stand')
            self.animate_y(2, duration=2, curve=curve.in_out_sine)

    def fly_up(self):
        if self.in_fight and self.is_alive:
            print("🛫 Дракон взлетает!")
            self.play_animation('fly')
            self.animate_y(self.fly_height, duration=2, curve=curve.out_cubic)
            invoke(self.start_attack, delay=2)

    def start_attack(self):
        if self.in_fight and self.is_alive:
            print("🔥 Дракон начинает атаку!")
            self.state = 'attack'
            self.play_animation('skill01')
            invoke(self.shoot_fireball, delay=1.0)

    def update(self):
        if not self.target or not self.is_alive:
            return

        dist = distance(self, self.target)

        # Проверка триггера боя
        if dist <= self.trigger_radius:
            if not self.in_fight and self.is_alive:
                self.start_fight()
        else:
            if self.in_fight:
                self.stop_fight()

        # Логика атаки
        if self.in_fight and self.state == 'attack' and self.is_alive:
            # Плавный поворот к цели
            direction = self.target.position - self.position
            if direction.length() > 0:
                self.rotation_y = lerp_angle(self.rotation_y, math.degrees(math.atan2(-direction.x, -direction.z)),
                                             6 * time.dt)

            self.attack_cooldown -= time.dt
            if self.attack_cooldown <= 0:
                self.shoot_fireball()
                self.attack_cooldown = self.attack_interval

    def shoot_fireball(self):
        if self.in_fight and self.target and self.is_alive:
            print("🎯 Дракон выпускает файрбол!")
            # Создаем файрбол немного перед драконом
            fireball_pos = self.position + Vec3(0, 2, -3)
            Fireball(position=fireball_pos, target=self.target)


class Fireball(Entity):
    def __init__(self, position, target=None, **kwargs):
        super().__init__(
            model='sphere',
            color=color.orange,
            scale=1.5,
            position=position,
            collider='sphere',
            **kwargs
        )
        self.speed = 12
        self.target = target
        self.tail_timer = 0
        self.life_timer = 0
        self.max_life = 5
        self.damage = 25

    def update(self):
        if not self.enabled:
            return

        self.life_timer += time.dt
        if self.life_timer >= self.max_life:
            self.explode()
            return

        # Следуем за целью
        if self.target and self.target.enabled and hasattr(self.target, 'position'):
            target_pos = self.target.position + Vec3(0, 1, 0)
            direction = (target_pos - self.position).normalized()
        else:
            # Если цель исчезла, летим прямо
            direction = Vec3(0, 0, -1)

        self.position += direction * time.dt * self.speed

        # Плавный поворот в направлении движения
        if direction.length() > 0:
            self.look_at(self.position + direction)

        # Эффект хвоста
        self.tail_timer += time.dt
        if self.tail_timer > 0.05:
            self.create_tail()
            self.tail_timer = 0

        # Проверка столкновений
        hit_info = self.intersects()
        if hit_info.hit:
            if self.target and hit_info.entity == self.target:
                print("💥 Игрок получил урон от файрбола!")
                if hasattr(self.target, 'take_damage'):
                    self.target.take_damage(self.damage)
            self.explode()
            return

        if self.y < -10:
            self.explode()

    def create_tail(self):
        tail = Entity(
            model='sphere',
            color=color.rgb(255, uniform(100, 150), 0),
            scale=uniform(0.2, 0.4),
            position=self.position - self.forward * 0.3,
        )
        tail.animate_scale(0.1, duration=0.3)
        tail.animate_color(color.clear, duration=0.3)
        destroy(tail, delay=0.3)

    def explode(self):
        # Создаем эффект взрыва
        explosion = Entity(
            model='sphere',
            color=color.rgb(255, 100, 0),
            scale=0.5,
            position=self.position,
        )
        explosion.animate_scale(6, duration=0.3)
        explosion.animate_color(color.clear, duration=0.3)
        destroy(explosion, delay=0.4)
        destroy(self)


class Player(Entity):
    def __init__(self, **kwargs):
        super().__init__(
            model='cube',
            color=color.blue,
            scale=(0.8, 1.8, 0.8),
            position=(0, 4, 0),
            collider='box',
            **kwargs
        )
        self.health_bar = HealthBar(max_health=100, is_boss=False)
        self.is_alive = True
        self.invincible = False
        self.invincible_timer = 0

    def take_damage(self, amount):
        """Наносит урон игроку"""
        if not self.is_alive or self.invincible:
            return

        print(f"❤️ Игрок получает {amount} урона! Осталось здоровья: {self.health_bar.current_health - amount}")

        # Включаем неуязвимость на 1 секунду после получения урона
        self.invincible = True
        self.invincible_timer = 1.0
        self.color = color.red
        invoke(self.reset_color, delay=0.3)

        if self.health_bar.take_damage(amount):
            self.die()
        else:
            # Мигание при получении урона
            original_color = self.color
            self.animate_color(color.red, duration=0.1)
            invoke(self.animate_color, original_color, duration=0.1, delay=0.1)

    def reset_color(self):
        """Восстанавливает цвет игрока"""
        self.color = color.blue
        self.invincible = False

    def update(self):
        # Обновление таймера неуязвимости
        if self.invincible:
            self.invincible_timer -= time.dt
            if self.invincible_timer <= 0:
                self.invincible = False
                self.color = color.blue

    def die(self):
        """Смерть игрока"""
        print("💀 Игрок погиб!")
        self.is_alive = False
        self.color = color.gray

        # Сообщение о проигрыше
        game_over_text = Text(
            text='ВЫ ПРОИГРАЛИ!\nНажмите R для перезапуска',
            origin=(0, 0),
            scale=2,
            color=color.red,
            background=True
        )

        # Останавливаем игру
        application.paused = True


player = Player()

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


for i in range(80):
    spawn_snowflake()


def update_snow():
    for flake in snowflakes:
        flake.y -= time.dt * 1.5
        flake.rotation_x += time.dt * 50
        if flake.y < -1:
            flake.y = uniform(5, 10)
            flake.x = uniform(-20, 20)
            flake.z = uniform(-20, 20)


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

    # Тестовый урон по дракону
    if key == 'f' and dragon.is_alive:
        dragon.take_damage(50)

    # Перезапуск игры
    if key == 'r' and not player.is_alive:
        application.paused = False
        scene.clear()
        invoke(restart_game, delay=0.1)


def restart_game():
    """Перезапускает игру"""
    global player, dragon
    player = Player()
    dragon = DragonBoss(target=player, trigger_radius=50)
    print("🔄 Игра перезапущена!")


def update():
    global yaw, pitch, is_dashing, dash_time, dash_cooldown, dash_dir, move
    global velocity_y, is_grounded

    if application.paused:
        return

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

    ray = raycast(player.position + Vec3(0, 0.1, 0), Vec3(0, -1, 0), distance=0.3, ignore=[player])
    is_grounded = ray.hit

    if not is_grounded:
        velocity_y -= GRAVITY * dt
    else:
        velocity_y = max(0, velocity_y)

    player.position += Vec3(0, velocity_y * dt, 0)

    # Плавный поворот игрока в направлении движения
    if move.length() > 0:
        target_rotation = math.degrees(math.atan2(-move.x, -move.z))
        player.rotation_y = lerp_angle(player.rotation_y, target_rotation, 8 * dt)


# Создаем дракона
dragon = DragonBoss(target=player, trigger_radius=50)

# Добавляем подсказки для управления
Text(
    text='Управление:\nWASD - движение\nSpace - прыжок\nQ - рывок\nF - нанести урон дракону (тест)\nR - перезапуск',
    position=(-0.85, 0.3),
    scale=1.0,
    color=color.white
)

app.run()