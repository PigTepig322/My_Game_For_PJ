from ursina import *
from direct.actor.Actor import Actor
from random import uniform, randint, choice
import os
import math
import json

app = Ursina()


def generate_sky_texture():
    """Генерирует красивую градиентную текстуру неба (закат/день) и сохраняет её на диск.
    Возвращает путь к файлу, либо None при ошибке (тогда используется обычное цветное небо)."""
    try:
        from PIL import Image, ImageDraw, ImageFilter

        width, height = 512, 512
        img = Image.new('RGB', (width, height))
        draw = ImageDraw.Draw(img)

        # Цвета градиента: насыщенный синий зенит -> голубая середина -> тёплый закатный горизонт
        top_color = (45, 110, 200)
        mid_color = (150, 195, 235)
        horizon_color = (255, 225, 180)

        for y in range(height):
            t = y / (height - 1)
            if t < 0.6:
                local_t = t / 0.6
                r = top_color[0] + (mid_color[0] - top_color[0]) * local_t
                g = top_color[1] + (mid_color[1] - top_color[1]) * local_t
                b = top_color[2] + (mid_color[2] - top_color[2]) * local_t
            else:
                local_t = (t - 0.6) / 0.4
                r = mid_color[0] + (horizon_color[0] - mid_color[0]) * local_t
                g = mid_color[1] + (horizon_color[1] - mid_color[1]) * local_t
                b = mid_color[2] + (horizon_color[2] - mid_color[2]) * local_t
            draw.line([(0, y), (width, y)], fill=(int(r), int(g), int(b)))

        # Тёплое солнечное сияние ближе к горизонту
        sun_x, sun_y = int(width * 0.7), int(height * 0.62)
        glow = Image.new('RGB', (width, height), (0, 0, 0))
        glow_draw = ImageDraw.Draw(glow)
        glow_draw.ellipse([sun_x - 160, sun_y - 160, sun_x + 160, sun_y + 160], fill=(255, 235, 180))
        glow_draw.ellipse([sun_x - 70, sun_y - 70, sun_x + 70, sun_y + 70], fill=(255, 250, 220))
        glow = glow.filter(ImageFilter.GaussianBlur(radius=40))
        img = Image.blend(img, glow, alpha=0.45)

        # Яркий диск солнца
        sun_draw = ImageDraw.Draw(img)
        sun_draw.ellipse([sun_x - 22, sun_y - 22, sun_x + 22, sun_y + 22], fill=(255, 255, 240))

        # Облака — чёткие мягкие пятна без серого налёта (alpha-композит, не blend всей картинки)
        cloud_layer = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        cloud_draw = ImageDraw.Draw(cloud_layer)
        for _ in range(20):
            cx = randint(0, width)
            cy = randint(int(height * 0.08), int(height * 0.55))
            rw = randint(35, 75)
            rh = randint(10, 18)
            cloud_draw.ellipse([cx - rw, cy - rh, cx + rw, cy + rh], fill=(255, 255, 255, 200))
        cloud_layer = cloud_layer.filter(ImageFilter.GaussianBlur(radius=10))
        img = Image.alpha_composite(img.convert('RGBA'), cloud_layer).convert('RGB')

        out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sky_texture_generated.png')
        img.save(out_path)
        return out_path
    except Exception:
        return None


def _lerp_scalar(a, b, t):
    return a + (b - a) * t

window.title = 'DRAGON HUNTER'
window.exit_button.visible = False
window.fps_counter.enabled = True

# --- Игровые константы ---
SPEED = 5
DASH_SPEED = 25
DASH_TIME = 0.15
DASH_COOLDOWN = 1.0
JUMP_HEIGHT = 5
GRAVITY = 9.8
CAM_DIST = 10
CAM_HEIGHT = 2
MOUSE_SENS = 800

PLAYER_MAX_HEALTH = 100
DRAGON_MAX_HEALTH = 500

FIREBALL_COOLDOWN = 1.3
FIREBALL_DAMAGE = 18
FIREBALL_SPEED = 35

MELEE_COOLDOWN = 0.7
MELEE_DAMAGE = 24
MELEE_RANGE = 9

DRAGON_HIT_RADIUS = 7
DRAGON_FIREBALL_DAMAGE = 25


# --- Глобальные переменные состояния ---
is_dashing = False
dash_time = 0
dash_cooldown = 0
dash_dir = Vec3(0, 0, 0)
move = Vec3(0, 0, 0)
velocity_y = 0
is_grounded = False
yaw = 0
pitch = 15
player = None
dragon = None
combat_ui = None
cutscene_active = False
level_up_screen = None

# --- Система прокачки ---
player_stats = {
    'level': 1,
    'exp': 0,
    'exp_to_next': 100,
    'stat_points': 0,
    'speed': 5,
    'fireball_damage': 18,
    'max_health': 100,
    'kills': 0,
}

# --- Система сохранения игры ---
SAVE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'savegame.json')


def has_save():
    """Проверяет, существует ли файл сохранения"""
    return os.path.exists(SAVE_FILE)


def save_game():
    """Сохраняет текущий прогресс игрока в JSON-файл"""
    global player_stats, SPEED, FIREBALL_DAMAGE, PLAYER_MAX_HEALTH

    data = {
        'player_stats': player_stats,
        'speed': SPEED,
        'fireball_damage': FIREBALL_DAMAGE,
        'player_max_health': PLAYER_MAX_HEALTH,
    }

    # Если игрок жив и существует — сохраняем его текущую позицию и здоровье
    if player and hasattr(player, 'position') and not getattr(player, '_is_destroyed', True):
        data['player_position'] = [player.position.x, player.position.y, player.position.z]
        if hasattr(player, 'health_bar') and player.health_bar:
            data['player_health'] = player.health_bar.current_health
    else:
        data['player_position'] = None
        data['player_health'] = None

    try:
        with open(SAVE_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except:
        pass


def load_game():
    """Загружает прогресс из файла сохранения. Возвращает True при успехе"""
    global player_stats, SPEED, FIREBALL_DAMAGE, PLAYER_MAX_HEALTH

    if not has_save():
        return False

    try:
        with open(SAVE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)

        loaded_stats = data.get('player_stats')
        if loaded_stats:
            player_stats.update(loaded_stats)

        SPEED = data.get('speed', SPEED)
        FIREBALL_DAMAGE = data.get('fireball_damage', FIREBALL_DAMAGE)
        PLAYER_MAX_HEALTH = data.get('player_max_health', PLAYER_MAX_HEALTH)

        return True
    except:
        return False


def get_saved_player_position_and_health():
    """Возвращает (position, health) из сохранения, либо (None, None)"""
    if not has_save():
        return None, None
    try:
        with open(SAVE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        pos = data.get('player_position')
        health = data.get('player_health')
        if pos:
            pos = Vec3(pos[0], pos[1], pos[2])
        return pos, health
    except:
        return None, None


def spawn_damage_popup(position, amount, popup_color=color.yellow):
    """Создает всплывающую цифру урона в мировом пространстве"""
    try:
        txt = Text(
            parent=scene,
            text=str(int(amount)),
            position=position + Vec3(uniform(-0.4, 0.4), 1.6, uniform(-0.4, 0.4)),
            origin=(0, 0),
            scale=5,
            color=popup_color,
            billboard=True,
        )
        txt.animate_position(txt.position + Vec3(uniform(-0.3, 0.3), 1.6, uniform(-0.3, 0.3)),
                             duration=0.7, curve=curve.out_quad)
        txt.animate_color(color.clear, duration=0.6, delay=0.2)
        invoke(destroy, txt, delay=0.9)
    except:
        pass


class HealthBar(Entity):
    def __init__(self, max_health=100, is_boss=False, **kwargs):
        super().__init__(**kwargs)
        self.max_health = max_health
        self.current_health = max_health
        self.is_boss = is_boss

        if is_boss:
            self.bg = Entity(parent=self, model='quad', color=color.dark_gray,
                             scale=(1.5, 0.3), position=(0, 2, 0), billboard=True)
            self.fill = Entity(parent=self.bg, model='quad', color=color.red,
                               scale=(1, 1), position=(-0.49, -0.06, -0.1), origin=(-0.5, 0))
        else:
            self.bg = Entity(parent=camera.ui, model='quad', color=color.dark_gray,
                             scale=(0.4, 0.03), position=(-0.7, 0.4, 0))
            self.fill = Entity(parent=self.bg, model='quad', color=color.green,
                               scale=(1, 1), position=(-0.5, 0, -0.1), origin=(-0.5, 0))
        self.update_display()

    def update_display(self):
        health_ratio = self.current_health / self.max_health
        self.fill.scale_x = max(0, health_ratio)
        if health_ratio > 0.6:
            self.fill.color = color.green
        elif health_ratio > 0.3:
            self.fill.color = color.orange
        else:
            self.fill.color = color.red

    def take_damage(self, amount):
        self.current_health = max(0, self.current_health - amount)
        self.update_display()
        return self.current_health <= 0

    def heal(self, amount):
        self.current_health = min(self.max_health, self.current_health + amount)
        self.update_display()


class CombatUI(Entity):
    """Дополнительный HUD боя: кулдауны атак, фаза босса, предупреждения об опасных атаках"""
    def __init__(self, **kwargs):
        super().__init__(parent=camera.ui, **kwargs)

        self.boss_name_text = Text(parent=self, text='ДРЕВНИЙ ДРАКОН', origin=(0, 0),
                                   y=0.44, scale=1.1, color=color.white, enabled=False)

        self.phase_text = Text(parent=self, text='', origin=(0, 0), y=0.46,
                               scale=1.3, color=color.red, enabled=False)

        self.fireball_text = Text(parent=self, text='Огненный шар: ГОТОВ',
                                  position=(-0.7, 0.37), scale=0.8, color=color.cyan)
        self.melee_text = Text(parent=self, text='Удар клинком: ГОТОВ',
                               position=(-0.7, 0.34), scale=0.8, color=color.orange)

        self.warning_text = Text(parent=self, text='', origin=(0, 0), y=-0.35,
                                 scale=1.4, color=color.yellow, enabled=False)

        self.enabled = False

    def show(self):
        self.enabled = True
        self.boss_name_text.enabled = True
        self.set_phase(1)

    def hide(self):
        self.enabled = False
        self.warning_text.enabled = False
        self.phase_text.enabled = False

    def set_phase(self, phase_num):
        if phase_num == 1:
            self.phase_text.text = 'ФАЗА 1: ЗЕМЛЯ'
            self.phase_text.color = color.white
        else:
            self.phase_text.text = 'ФАЗА 2: ВОЗДУХ — ЯРОСТЬ'
            self.phase_text.color = color.red
        self.phase_text.enabled = True

    def set_warning(self, text, duration=2.0):
        self.warning_text.text = text
        self.warning_text.enabled = True
        invoke(self.clear_warning, delay=duration)

    def clear_warning(self):
        self.warning_text.enabled = False

    def update(self):
        if not self.enabled:
            return
        if player and hasattr(player, 'fireball_cooldown'):
            if player.fireball_cooldown <= 0:
                self.fireball_text.text = 'Огненный шар: ГОТОВ'
                self.fireball_text.color = color.cyan
            else:
                self.fireball_text.text = f'Огненный шар: {player.fireball_cooldown:.1f}с'
                self.fireball_text.color = color.gray
        if player and hasattr(player, 'melee_cooldown'):
            if player.melee_cooldown <= 0:
                self.melee_text.text = 'Удар клинком: ГОТОВ'
                self.melee_text.color = color.orange
            else:
                self.melee_text.text = f'Удар клинком: {player.melee_cooldown:.1f}с'
                self.melee_text.color = color.gray


class MainMenu(Entity):
    def __init__(self, **kwargs):
        super().__init__(parent=camera.ui, **kwargs)

        # Полноэкранный фон
        self.menu_bg = Entity(parent=self, model='quad', scale=(2, 2),
                              texture='white_cube', color=color.dark_gray.tint(-0.3),
                              position=(0, 0, 0))

        # Узоры или текстура фона
        self.bg_pattern = Entity(parent=self, model='quad', scale=(2.1, 2.1),
                                 texture='white_cube', color=color.dark_gray.tint(0.1),
                                 position=(0, 0, 0.01))

        # Полупрозрачная затемняющая панель
        self.overlay = Entity(parent=self, model='quad', scale=(1.5, 1),
                              color=color.black66, position=(0, 0, 0.02))

        # Заголовок игры
        self.title = Text(parent=self, text='DRAGON HUNTER', origin=(0, 0),
                          y=0.25, scale=4, color=color.red.tint(0.2))
        self.title_shadow = Text(parent=self, text='DRAGON HUNTER', origin=(0, 0),
                                 y=0.248, scale=4.05, color=color.black, z=0.01)

        # Подзаголовок
        self.subtitle = Text(parent=self, text='Охота на дракона', origin=(0, 0),
                             y=0.15, scale=1.5, color=color.light_gray)

        # Кнопка "Продолжить игру" — видна только если есть сохранение
        self.continue_btn = Button(parent=self, text='ПРОДОЛЖИТЬ ИГРУ', color=color.azure.tint(-0.1),
                                   scale=(0.4, 0.12), y=0.0, highlight_color=color.azure.tint(0.2),
                                   pressed_color=color.azure.tint(-0.3))
        self.continue_btn.on_click = self.continue_game

        # Кнопки
        self.start_btn = Button(parent=self, text='НАЧАТЬ ИГРУ', color=color.green.tint(-0.1),
                                scale=(0.4, 0.12), y=-0.15, highlight_color=color.green.tint(0.2),
                                pressed_color=color.green.tint(-0.3))
        self.start_btn.on_click = self.start_game

        self.quit_btn = Button(parent=self, text='ВЫЙТИ', color=color.red.tint(-0.1),
                               scale=(0.4, 0.12), y=-0.30, highlight_color=color.red.tint(0.2),
                               pressed_color=color.red.tint(-0.3))
        self.quit_btn.on_click = application.quit

        self.update_continue_button()

        # Панель с управлением
        self.controls_panel = Entity(parent=self, model='quad', color=color.black33,
                                     scale=(0.9, 0.45), position=(0, -0.55, 0))

        self.controls_title = Text(parent=self, text='Управление', origin=(0, 0),
                                   y=-0.40, scale=1.8, color=color.white)

        self.controls_text = Text(parent=self,
                                  text='WASD - движение\nSpace - прыжок\nQ - рывок\n'
                                       'Shift - даш + неуязвимость\n'
                                       'ЛКМ - огненный шар (дальняя атака)\n'
                                       'E - удар клинком (ближний бой)\n'
                                       'F / I - инвентарь / прокачка\n'
                                       'R - перезапуск после смерти\nESC - меню',
                                  position=(0, -0.55), scale=0.75, color=color.light_gray, line_height=1.2)

        # Информация о драконе
        self.dragon_info = Text(parent=self, text='Сразитесь с огнедышащим драконом в двух фазах боя!',
                                position=(0, -0.83), scale=0.65, color=color.orange)

        # Версия игры
        self.version = Text(parent=self, text='v2.0', position=(0.9, -0.95),
                            scale=0.6, color=color.gray)

    def update_continue_button(self):
        """Показывает кнопку 'Продолжить игру' только если есть сохранение"""
        if has_save():
            self.continue_btn.enabled = True
        else:
            self.continue_btn.enabled = False

    def start_game(self):
        """Начинает совершенно новую игру (сбрасывает прогресс)"""
        self.enabled = False
        mouse.locked = True
        global dragon, player, player_stats, SPEED, FIREBALL_DAMAGE, PLAYER_MAX_HEALTH

        # Сброс прогресса для новой игры
        player_stats.update({
            'level': 1, 'exp': 0, 'exp_to_next': 100, 'stat_points': 0,
            'speed': 5, 'fireball_damage': 18, 'max_health': 100, 'kills': 0,
        })
        SPEED = 5
        FIREBALL_DAMAGE = 18
        PLAYER_MAX_HEALTH = 100

        clean_up_game()  # Очищаем предыдущую игру перед созданием новой
        player = Player()
        dragon = DragonBoss(target=player, trigger_radius=50)
        if combat_ui:
            combat_ui.show()
        if level_up_screen:
            level_up_screen.refresh()
        save_game()

    def continue_game(self):
        """Продолжает игру с сохранённого места — тот же уровень, статы и позиция"""
        if not has_save():
            return

        self.enabled = False
        mouse.locked = True
        global dragon, player

        load_game()  # Загружаем player_stats, SPEED, FIREBALL_DAMAGE, PLAYER_MAX_HEALTH

        saved_pos, saved_health = get_saved_player_position_and_health()

        clean_up_game()
        player = Player()
        if saved_pos:
            player.position = saved_pos
        if saved_health is not None and hasattr(player, 'health_bar'):
            player.health_bar.max_health = PLAYER_MAX_HEALTH
            player.health_bar.current_health = saved_health
            player.health_bar.update_display()

        dragon = DragonBoss(target=player, trigger_radius=50)
        if combat_ui:
            combat_ui.show()
        if level_up_screen:
            level_up_screen.refresh()


class Spike(Entity):
    def __init__(self, position, **kwargs):
        super().__init__(model='cube', color=color.red, scale=(1, 3, 1),
                         position=position, collider='box', **kwargs)
        self.damage = 20
        self.has_damaged = False
        self.spawn_time = time.time()
        self._is_destroyed = False

        # Начинаем под землей
        self.y = -2

        # Анимация появления через 1 секунду
        invoke(self.rise, delay=1.0)

        # Автоматическое удаление через 5 секунд
        invoke(self.safe_destroy, delay=5.0)

    def rise(self):
        """Поднимает шип из-под земли"""
        if self._is_destroyed:
            return
        self.animate_y(1.5, duration=0.3, curve=curve.out_expo)
        invoke(self.check_damage, delay=0.3)

    def check_damage(self):
        """Проверяет попадание по игроку"""
        if self._is_destroyed or not player or not hasattr(player, 'position'):
            return

        if distance(self.position, player.position) < 2.5 and not self.has_damaged:
            if hasattr(player, 'take_damage'):
                player.take_damage(self.damage)
                spawn_damage_popup(player.position, self.damage, color.red)
                self.has_damaged = True

    def update(self):
        if self._is_destroyed:
            return

        # Постоянная проверка урона
        if time.time() - self.spawn_time > 1.3 and not self.has_damaged:
            self.check_damage()

    def safe_destroy(self):
        """Безопасно удаляет шип"""
        if self._is_destroyed:
            return

        self._is_destroyed = True
        if self.enabled:
            self.animate_y(-2, duration=0.2, curve=curve.in_expo)
            invoke(self.disable_spike, delay=0.2)

    def disable_spike(self):
        if self._is_destroyed and self.enabled:
            self.enabled = False
            if self in scene.entities:
                scene.entities.remove(self)


class DragonFireball(Entity):
    """Огненный шар дракона: летит вверх, затем падает вниз с красной меткой на земле"""
    def __init__(self, position, target=None, **kwargs):
        super().__init__(model='sphere', color=color.orange, scale=1.5,
                         position=position, **kwargs)
        self.target = target
        self.tail_timer = 0
        self.life_timer = 0
        self.damage = DRAGON_FIREBALL_DAMAGE
        self._is_destroyed = False
        self.trail_particles = []

        # Определяем цель на земле (позицию игрока в момент выстрела)
        if target and hasattr(target, 'position'):
            self.land_x = target.position.x + uniform(-3, 3)
            self.land_z = target.position.z + uniform(-3, 3)
        else:
            self.land_x = position.x
            self.land_z = position.z

        # Параметры параболической траектории
        self.start_pos = Vec3(position)
        self.peak_height = position.y + uniform(10, 16)  # максимальная высота дуги
        self.flight_time = 2.2  # полное время полёта
        self.elapsed = 0

        # Предупреждающий круг на земле
        self.warning_marker = Entity(
            model='circle',
            color=color.rgba(255, 0, 0, 180),
            position=(self.land_x, 0.05, self.land_z),
            rotation_x=90,
            scale=0.5
        )
        # Маркер растёт и мигает, пока шар летит
        self.warning_marker.animate_scale(5, duration=self.flight_time, curve=curve.linear)
        self.marker_blink_timer = 0

    def update(self):
        if not self.enabled or self._is_destroyed:
            return

        self.elapsed += time.dt

        # Параболическая дуга: вверх, потом вниз
        t = min(self.elapsed / self.flight_time, 1.0)
        # Горизонтальная интерполяция
        cur_x = _lerp_scalar(self.start_pos.x, self.land_x, t)
        cur_z = _lerp_scalar(self.start_pos.z, self.land_z, t)
        # Вертикальная парабола: y = start + (peak - start)*4*t*(1-t) → 0 на земле при t=1
        arc_y = _lerp_scalar(self.start_pos.y, 0, t) + (self.peak_height - self.start_pos.y) * 4 * t * (1 - t)
        self.position = Vec3(cur_x, arc_y, cur_z)

        # Мигание маркера в последние 0.5 секунды
        self.marker_blink_timer += time.dt
        if self.flight_time - self.elapsed < 0.5:
            if self.marker_blink_timer > 0.08:
                self.marker_blink_timer = 0
                if self.warning_marker and self.warning_marker.enabled:
                    self.warning_marker.color = (
                        color.rgba(255, 200, 0, 220)
                        if self.warning_marker.color == color.rgba(255, 0, 0, 180)
                        else color.rgba(255, 0, 0, 180)
                    )

        # Хвост огня
        self.tail_timer += time.dt
        if self.tail_timer > 0.05:
            self.create_tail()
            self.tail_timer = 0

        # Приземление
        if t >= 1.0:
            self.safe_explode()
            return

        if self.y < -5:
            self.safe_explode()

    def create_tail(self):
        if self._is_destroyed:
            return
        try:
            tail = Entity(model='sphere', color=color.rgb(255, uniform(80, 160), 0),
                          scale=uniform(0.2, 0.5), position=self.position)
            self.trail_particles.append(tail)

            if len(self.trail_particles) > 20:
                old_tail = self.trail_particles.pop(0)
                if old_tail and old_tail.enabled:
                    old_tail.enabled = False
                    if old_tail in scene.entities:
                        scene.entities.remove(old_tail)

            tail.animate_scale(0.05, duration=0.35)
            tail.animate_color(color.clear, duration=0.35)

            def remove_tail(t):
                if t and t.enabled:
                    t.enabled = False

            invoke(remove_tail, tail, delay=0.35)
        except:
            pass

    def safe_explode(self):
        if self._is_destroyed:
            return
        self._is_destroyed = True
        try:
            # Убираем предупреждающий маркер
            if self.warning_marker and self.warning_marker.enabled:
                self.warning_marker.enabled = False
                if self.warning_marker in scene.entities:
                    scene.entities.remove(self.warning_marker)

            explode_pos = Vec3(self.land_x, 0.5, self.land_z)

            # Взрыв
            explosion = Entity(model='sphere', color=color.rgb(255, 100, 0),
                               scale=0.5, position=explode_pos)
            explosion.animate_scale(7, duration=0.35)
            explosion.animate_color(color.clear, duration=0.35)

            # Кольцо взрыва на земле
            ring = Entity(model='circle', color=color.rgba(255, 80, 0, 180),
                          position=Vec3(self.land_x, 0.05, self.land_z),
                          rotation_x=90, scale=1)
            ring.animate_scale(8, duration=0.35, curve=curve.out_quad)
            ring.animate_color(color.clear, duration=0.35)

            def remove_fx(e):
                if e and e.enabled:
                    e.enabled = False
            invoke(remove_fx, explosion, delay=0.4)
            invoke(remove_fx, ring, delay=0.4)

            # Урон игроку если попал
            if player and hasattr(player, 'position'):
                flat_dist = distance(Vec3(self.land_x, 0, self.land_z),
                                     Vec3(player.x, 0, player.z))
                if flat_dist < 3.5 and hasattr(player, 'take_damage'):
                    player.take_damage(self.damage)
                    spawn_damage_popup(player.position, self.damage, color.red)

            for particle in self.trail_particles:
                if particle and particle.enabled:
                    particle.enabled = False
            self.trail_particles.clear()

            self.enabled = False
            if self in scene.entities:
                scene.entities.remove(self)
        except:
            pass


class PlayerFireball(Entity):
    """Огненный шар игрока — основная дальняя атака по дракону"""
    def __init__(self, position, direction, **kwargs):
        super().__init__(model='sphere', color=color.cyan, scale=0.5,
                         position=position, collider='sphere', **kwargs)
        self.direction = direction.normalized() if direction.length() > 0 else Vec3(0, 0, -1)
        self.speed = FIREBALL_SPEED
        self.life_timer = 0
        self.max_life = 3
        self.damage = FIREBALL_DAMAGE
        self._is_destroyed = False
        self.tail_timer = 0
        self.trail_particles = []
        self.glow = Entity(parent=self, model='sphere', color=color.rgba(0, 200, 255, 100), scale=1.4)

        if self.direction.length() > 0:
            self.look_at(self.position + self.direction)

    def update(self):
        if self._is_destroyed or not self.enabled:
            return

        self.life_timer += time.dt
        if self.life_timer >= self.max_life:
            self.safe_explode()
            return

        self.position += self.direction * self.speed * time.dt

        self.tail_timer += time.dt
        if self.tail_timer > 0.04:
            self.create_tail()
            self.tail_timer = 0

        if dragon and not getattr(dragon, '_is_destroyed', True) and getattr(dragon, 'is_alive', False):
            if distance(self.position, dragon.position) < DRAGON_HIT_RADIUS:
                dragon.take_damage(self.damage)
                spawn_damage_popup(dragon.position, self.damage, color.cyan)
                self.safe_explode()
                return

        if self.y < -5 or self.y > 60:
            self.safe_explode()

    def create_tail(self):
        if self._is_destroyed:
            return
        try:
            tail = Entity(model='sphere', color=color.rgb(uniform(0, 100), uniform(180, 255), 255),
                          scale=uniform(0.15, 0.3), position=self.position - self.direction * 0.3)
            self.trail_particles.append(tail)

            if len(self.trail_particles) > 20:
                old_tail = self.trail_particles.pop(0)
                if old_tail and old_tail.enabled:
                    old_tail.enabled = False
                    if old_tail in scene.entities:
                        scene.entities.remove(old_tail)

            tail.animate_scale(0.05, duration=0.3)
            tail.animate_color(color.clear, duration=0.3)

            def remove_tail(t):
                if t and t.enabled:
                    t.enabled = False

            invoke(remove_tail, tail, delay=0.3)
        except:
            pass

    def safe_explode(self):
        if self._is_destroyed:
            return
        self._is_destroyed = True
        try:
            self.collider = None

            explosion = Entity(model='sphere', color=color.rgb(0, 200, 255),
                               scale=0.4, position=self.position)
            explosion.animate_scale(4, duration=0.25)
            explosion.animate_color(color.clear, duration=0.25)

            def remove_explosion(e):
                if e and e.enabled:
                    e.enabled = False

            invoke(remove_explosion, explosion, delay=0.3)

            for particle in self.trail_particles:
                if particle and particle.enabled:
                    particle.enabled = False
            self.trail_particles.clear()

            self.enabled = False
            if self in scene.entities:
                scene.entities.remove(self)
        except:
            pass


class DragonBoss(Entity):
    def __init__(self, target=None, **kwargs):
        # Начинаем на земле (y=0), за горой-преградой, далеко от точки спавна игрока
        super().__init__(position=(0, 0, 60), collider='box', scale=20, **kwargs)
        self.actor = None
        self.animations_list = []
        self.current_animation = None
        self.actor_loaded = False
        self._is_destroyed = False
        self.load_actor_model()

        if not self.actor_loaded:
            self.create_backup_model()

        self.target = target
        self.state = 'idle'
        self.in_fight = False
        self.trigger_radius = 30
        self.fly_height = 8
        self.attack_cooldown = 0
        self.attack_interval = 10
        self.health_bar = HealthBar(max_health=DRAGON_MAX_HEALTH, is_boss=True, parent=self)
        self.is_alive = True
        self.is_attacking = False
        self.has_taken_off = False  # Флаг для отслеживания взлета
        self.is_airborne = False  # Флаг нахождения в воздухе (после взлета)

        # Флаги для разных типов атак
        self.can_fireball_attack = False  # Может ли дракон стрелять файрболами
        self.can_ground_attack = True  # Может ли дракон атаковать на земле

        # Шипы (эрупция земли) — работают в воздушной фазе
        self.spike_cooldown = 0
        self.spike_interval = 10
        self.spike_warnings = []
        self.spikes = []
        self.knockback_distance = 15
        self.knockback_force = 30
        self.knockback_cooldown = 0
        self.knockback_interval = 15  # секунд между отталкиваниями

        # Дополнительные угрозы поля боя — независимы от анимации основной атаки
        self.shockwave_cooldown = 5
        self.shockwave_interval = 14

        self.air_spike_cooldown = 6
        self.air_spike_interval = 9
        self.active_air_spikes = []

        self.meteor_cooldown = 10
        self.meteor_interval = 17
        self.active_meteors = []

        if self.actor_loaded and self.animations_list:
            self.play_animation('run')

    def load_actor_model(self):
        try:
            possible_paths = ["test12.glb", "models/test12.glb", "assets/test12.glb",
                              "test12/test12.glb", "dragon.glb", "models/dragon.glb",
                              "assets/dragon.glb"]
            model_path = None
            for path in possible_paths:
                if os.path.exists(path):
                    model_path = path
                    break

            if not model_path:
                return

            self.actor = Actor(model_path)
            if self.actor is None:
                return

            try:
                self.animations_list = self.actor.getAnimNames()
            except:
                self.animations_list = ['idle', 'run', 'attack', 'skill01', 'deaddown']

            self.actor.reparent_to(self)
            self.actor.setScale(0.1)
            self.actor.setPos(0, 0, 0)
            self.actor_loaded = True
        except:
            self.actor_loaded = False

    def create_backup_model(self):
        self.body = Entity(parent=self, model='cube', color=color.red,
                           scale=(1, 0.8, 2), position=(0, 0, 0))
        self.model = 'cube'
        self.color = color.red
        self.scale = 20

    def play_animation(self, anim_name, loop=True):
        if not self.actor_loaded or not self.actor or self._is_destroyed:
            return
        try:
            if anim_name not in self.animations_list:
                for anim in self.animations_list:
                    if anim_name.lower() in anim.lower():
                        anim_name = anim
                        break
                else:
                    if self.animations_list:
                        anim_name = self.animations_list[0]
                    else:
                        return

            if self.current_animation and self.current_animation != anim_name:
                try:
                    self.actor.stop(self.current_animation)
                except:
                    pass

            if loop:
                self.actor.loop(anim_name)
            else:
                # Анимация смерти и другие одноразовые анимации: проигрываем один раз
                # и замираем на последнем кадре, а не уходим в бесконечный цикл.
                self.actor.play(anim_name)
                try:
                    num_frames = self.actor.getNumFrames(anim_name)
                    fps = self.actor.getAnimControl(anim_name).getFrameRate()
                    duration = max(num_frames / fps, 0.05) if fps else 0.05
                except Exception:
                    duration = self.actor.getDuration(anim_name) if hasattr(self.actor, 'getDuration') else 1.5

                def _freeze_last_frame(actor=self.actor, name=anim_name):
                    if self._is_destroyed:
                        return
                    try:
                        actor.pose(name, actor.getNumFrames(name) - 1)
                    except Exception:
                        pass

                invoke(_freeze_last_frame, delay=duration)

            self.current_animation = anim_name
        except:
            pass

    def take_damage(self, amount):
        if not self.is_alive or self._is_destroyed:
            return

        old_health = self.health_bar.current_health
        if self.health_bar.take_damage(amount):
            self.die()
        else:
            # Проверяем, упало ли здоровье ниже 50% - тогда дракон взлетает
            if old_health > self.health_bar.max_health * 0.5 >= self.health_bar.current_health:
                if not self.has_taken_off:
                    self.take_off()

            if self.actor_loaded:
                try:
                    original_color = self.actor.getColor() if hasattr(self.actor, 'getColor') else None
                    if original_color:
                        self.actor.setColor(1, 0.5, 0, 1)
                        invoke(lambda: self.actor.setColor(*original_color)
                        if original_color and not self._is_destroyed else None, delay=0.2)
                except:
                    pass
            else:
                original_color = self.color
                self.color = color.orange
                invoke(setattr, self, 'color', original_color, delay=0.2)

    def take_off(self):
        """Взлет дракона при потере 50% здоровья — начало фазы 2"""
        if self._is_destroyed or not self.is_alive or self.has_taken_off:
            return

        self.has_taken_off = True
        self.is_airborne = True
        self.can_fireball_attack = True  # Теперь может стрелять файрболами
        self.can_ground_attack = False  # Больше не атакует на земле

        # Даём игроку небольшую передышку перед новыми воздушными угрозами
        self.air_spike_cooldown = 4
        self.meteor_cooldown = 7

        if combat_ui:
            combat_ui.set_phase(2)
            combat_ui.set_warning('ДРАКОН ВЗЛЕТАЕТ! НАЧИНАЕТСЯ ФАЗА ЯРОСТИ!', duration=3.5)

        # Анимация взлета
        if self.actor_loaded:
            self.play_animation('run')

        # Взлетаем на высоту fly_height
        self.animate_y(self.fly_height, duration=2, curve=curve.out_cubic)

        # Эффект взлета
        self.create_takeoff_effect()

    def create_takeoff_effect(self):
        """Создает эффект взлета дракона"""
        # Пыль при взлете
        for i in range(15):
            dust = Entity(
                model='sphere',
                color=color.gray,
                scale=uniform(0.5, 1.5),
                position=self.position + Vec3(uniform(-3, 3), 0, uniform(-3, 3)),
                enabled=True
            )

            dust.animate_position(
                dust.position + Vec3(0, uniform(2, 5), 0),
                duration=uniform(1, 2),
                curve=curve.out_expo
            )
            dust.animate_scale(0.1, duration=1.5)
            dust.animate_color(color.clear, duration=1.5)

            invoke(lambda d=dust: setattr(d, 'enabled', False) if d else None, delay=2)

        # Вихрь воздуха
        vortex = Entity(
            model='circle',
            color=color.white.tint(-0.3),
            scale=5,
            position=self.position,
            rotation_x=90,
            alpha=0.5
        )

        vortex.animate_scale(10, duration=1)
        vortex.animate_color(color.clear, duration=1)

        invoke(lambda v=vortex: setattr(v, 'enabled', False) if v else None, delay=1.5)

    def spawn_spikes(self):
        """Создает 4 шипа в случайных местах в радиусе 300 (фаза полёта)"""
        if self._is_destroyed or not self.is_alive or not self.has_taken_off:
            return

        if combat_ui:
            combat_ui.set_warning('ШИПЫ ИЗ-ПОД ЗЕМЛИ! СЛЕДИТЕ ЗА КРУГАМИ!', duration=1.8)

        self.cleanup_old_warnings()

        for i in range(4):
            angle = uniform(0, 2 * math.pi)
            distance_ = uniform(50, 300)
            x = self.x + math.cos(angle) * distance_
            z = self.z + math.sin(angle) * distance_

            warning = Entity(
                model='circle',
                color=color.red,
                position=(x, 0.01, z),
                scale=4,
                rotation_x=90,
                alpha=0.7
            )

            self.spike_warnings.append(warning)

            warning.animate_color(color.yellow, duration=0.5)
            warning.animate_color(color.red, duration=0.5, delay=0.5)

            invoke(self.create_spike_at_position, x, z, delay=1.0)
            invoke(self.remove_warning, warning, delay=1.0)

    def create_spike_at_position(self, x, z):
        """Создает шип в указанной позиции"""
        if self._is_destroyed or not self.is_alive:
            return

        spike = Spike(position=(x, -2, z))
        self.spikes.append(spike)

        effect = Entity(
            model='sphere',
            color=color.red,
            position=(x, 0, z),
            scale=0.5,
            alpha=0.7
        )
        effect.animate_scale(3, duration=0.3)
        effect.animate_color(color.clear, duration=0.3)

        invoke(lambda e=effect: setattr(e, 'enabled', False) if e else None, delay=0.3)

    def remove_warning(self, warning):
        """Убирает предупреждение шипа"""
        if warning in self.spike_warnings:
            self.spike_warnings.remove(warning)
        if warning and warning.enabled:
            warning.enabled = False
            if warning in scene.entities:
                scene.entities.remove(warning)

    def cleanup_old_warnings(self):
        """Очищает старые предупреждения"""
        for warning in self.spike_warnings[:]:
            self.remove_warning(warning)
        self.spike_warnings = []

    def cleanup_spikes(self):
        """Очищает все шипы"""
        for spike in self.spikes[:]:
            if spike and not spike._is_destroyed:
                spike.safe_destroy()
        self.spikes = []

    def knockback_player(self):
        """Взрыв и плавное отталкивание игрока если он слишком близко (только фаза 1)"""
        if not self.target or not hasattr(self.target, 'position'):
            return
        if self.is_airborne:
            return
        if self.knockback_cooldown > 0:
            return

        distance_to_player = distance(self.position, self.target.position)
        if distance_to_player < self.knockback_distance:
            self.knockback_cooldown = self.knockback_interval
            direction = self.target.position - self.position
            direction.y = 0
            if direction.length() > 0:
                direction = direction.normalized()
            else:
                direction = Vec3(1, 0, 0)

            # Урон
            if hasattr(self.target, 'take_damage'):
                self.target.take_damage(10)
                spawn_damage_popup(self.target.position, 10, color.orange)

            # Плавное горизонтальное отталкивание через animate_position
            global velocity_y
            knock_strength = 18
            self.target.position += direction * 0.5
            push_target = Vec3(
                self.target.position.x + direction.x * knock_strength,
                self.target.position.y,
                self.target.position.z + direction.z * knock_strength
            )
            self.target.animate_position(push_target, duration=0.45, curve=curve.out_quad)
            velocity_y = 6  # подбрасываем вверх

            # Большой взрыв у дракона
            boom_pos = self.position + Vec3(direction.x * 3, 1, direction.z * 3)

            boom1 = Entity(model='sphere', color=color.rgb(255, 120, 0),
                           scale=1, position=boom_pos)
            boom1.animate_scale(12, duration=0.4, curve=curve.out_quad)
            boom1.animate_color(color.clear, duration=0.4)
            invoke(lambda e=boom1: setattr(e, 'enabled', False) if e else None, delay=0.45)

            boom2 = Entity(model='sphere', color=color.rgb(255, 220, 0),
                           scale=0.5, position=boom_pos)
            boom2.animate_scale(7, duration=0.25, curve=curve.out_expo)
            boom2.animate_color(color.clear, duration=0.25)
            invoke(lambda e=boom2: setattr(e, 'enabled', False) if e else None, delay=0.3)

            ring = Entity(model='circle', color=color.rgba(255, 100, 0, 200),
                          position=(self.x, 0.05, self.z), rotation_x=90, scale=1)
            ring.animate_scale(16, duration=0.45, curve=curve.out_quad)
            ring.animate_color(color.clear, duration=0.45)
            invoke(lambda e=ring: setattr(e, 'enabled', False) if e else None, delay=0.5)

            for i in range(12):
                spark_dir = Vec3(uniform(-1, 1), uniform(0.3, 1), uniform(-1, 1)).normalized()
                spark = Entity(model='cube',
                               color=choice([color.orange, color.yellow, color.red]),
                               scale=uniform(0.2, 0.5),
                               position=boom_pos + spark_dir * uniform(0.5, 2))
                spark.animate_position(
                    spark.position + spark_dir * uniform(4, 9),
                    duration=uniform(0.3, 0.6), curve=curve.out_quad
                )
                spark.animate_color(color.clear, duration=uniform(0.3, 0.6))
                invoke(lambda e=spark: setattr(e, 'enabled', False) if e else None, delay=0.65)

            if combat_ui:
                combat_ui.set_warning('ВЗРЫВ! НЕ ПОДХОДИ К ДРАКОНУ!', duration=1.5)

    def perform_ground_attack(self):
        """Атака на земле — удар когтями с отталкиванием"""
        if self.is_attacking or not self.is_alive or self._is_destroyed or self.is_airborne:
            return

        self.is_attacking = True
        self.state = 'attack'

        if self.actor_loaded:
            self.play_animation('skill01')

        invoke(self.knockback_player, delay=1.5)
        invoke(self.return_to_idle, delay=2.0)

    def perform_air_attack(self):
        """Атака в воздухе — файрболы (анимация полёта не прерывается)"""
        if self.is_attacking or not self.is_alive or self._is_destroyed or not self.is_airborne:
            return

        self.is_attacking = True
        self.state = 'attack'

        # Не меняем анимацию — дракон продолжает анимацию полёта (run/fly)
        # Просто стреляем шаром и сразу возвращаем флаг атаки
        invoke(self.shoot_fireball, delay=0.3)
        invoke(self.return_to_idle_air, delay=1.2)

    def return_to_idle(self):
        if self.is_alive and not self._is_destroyed and self.in_fight:
            self.is_attacking = False
            self.state = 'idle'
            if self.actor_loaded:
                self.play_animation('run')

    def return_to_idle_air(self):
        """Возврат из атаки в воздухе — сохраняем анимацию полёта"""
        if self.is_alive and not self._is_destroyed and self.in_fight:
            self.is_attacking = False
            self.state = 'idle'
            # В воздушной фазе продолжаем анимацию run (полёт), не idle
            if self.actor_loaded and self.current_animation != 'run':
                self.play_animation('run')

    def ground_shockwave(self):
        """Наземная атака: предупреждающее кольцо, затем расширяющаяся ударная волна"""
        if self._is_destroyed or not self.is_alive or self.is_airborne:
            return

        self.shockwave_cooldown = self.shockwave_interval

        if combat_ui:
            combat_ui.set_warning('УДАРНАЯ ВОЛНА! ОТБЕГАЙТЕ ОТ ДРАКОНА!', duration=1.3)

        prep = Entity(model='circle', color=color.rgba(0, 140, 255, 120),
                     position=self.position + Vec3(0, 0.1, 0), rotation_x=90, scale=1)
        prep.animate_scale(6, duration=0.6, curve=curve.out_quad)
        prep.animate_color(color.clear, duration=0.6)
        invoke(self.destroy_entity, prep, delay=0.7)
        invoke(self.spawn_shockwave_ring, delay=0.6)

    def spawn_shockwave_ring(self):
        if self._is_destroyed or not self.is_alive:
            return

        all_segs = []
        seg_count = 24
        radius = 28
        duration = 1.1

        # 3 слоя по высоте — нижний, средний, верхний
        for layer, (y_pos, seg_h, seg_color) in enumerate([
            (0.5,  3.5, color.rgb(0, 180, 255)),
            (3.0,  2.5, color.rgb(80, 200, 255)),
            (5.5,  1.5, color.rgb(160, 230, 255)),
        ]):
            for i in range(seg_count):
                seg = Entity(model='cube', color=seg_color,
                             position=self.position + Vec3(0, y_pos, 0),
                             scale=(1.1, seg_h, 1.1))
                all_segs.append(seg)
                angle = (360 / seg_count) * i
                x = self.x + math.sin(math.radians(angle)) * radius
                z = self.z + math.cos(math.radians(angle)) * radius
                seg.animate_position((x, y_pos, z), duration=duration, curve=curve.linear)
                seg.animate_color(color.clear, duration=duration)

        # Наземное кольцо свечения
        glow = Entity(model='circle', color=color.rgba(0, 160, 255, 160),
                      position=self.position + Vec3(0, 0.05, 0),
                      rotation_x=90, scale=2)
        glow.animate_scale(radius * 2, duration=duration, curve=curve.linear)
        glow.animate_color(color.clear, duration=duration)
        all_segs.append(glow)

        invoke(self.check_shockwave_hit, delay=duration * 0.45)
        invoke(self.destroy_entities, all_segs, delay=duration + 0.1)

    def check_shockwave_hit(self):
        if not player or not hasattr(player, 'position') or self._is_destroyed:
            return
        flat_dist = distance(Vec3(self.x, 0, self.z), Vec3(player.x, 0, player.z))
        if flat_dist < 20 and hasattr(player, 'take_damage'):
            player.take_damage(22)
            spawn_damage_popup(player.position, 22, color.orange)

    def shoot_air_spikes(self):
        """Воздушная атака: летящие шипы, преследующие игрока"""
        if self._is_destroyed or not self.is_alive or not self.is_airborne:
            return

        self.air_spike_cooldown = self.air_spike_interval

        if combat_ui:
            combat_ui.set_warning('ЛЕТЯЩИЕ ШИПЫ!', duration=1.6)

        count = 6
        for i in range(count):
            angle = uniform(0, 360)
            d = uniform(2, 6)
            spawn_pos = self.position + Vec3(math.sin(math.radians(angle)) * d, 0,
                                            math.cos(math.radians(angle)) * d)
            spike = Entity(model='cube', color=color.rgb(190, 0, 190), position=spawn_pos,
                          scale=(0.8, 0.4, 0.8), collider='box')
            glow = Entity(model='sphere', color=color.rgba(190, 0, 190, 100),
                        position=spawn_pos, scale=1.2, alpha=0.5)
            self.active_air_spikes.append(spike)

            if player and hasattr(player, 'position'):
                target = player.position + Vec3(0, 1.5, 0)
                spike.animate_position(target, duration=1.6, curve=curve.linear)
                glow.animate_position(target, duration=1.6, curve=curve.linear)

            invoke(self.check_air_spike_hit, spike, glow, delay=1.6)
            invoke(self.destroy_entity, spike, delay=1.8)
            invoke(self.destroy_entity, glow, delay=1.8)

    def check_air_spike_hit(self, spike, glow):
        if spike and spike.enabled and player and hasattr(player, 'position'):
            if distance(spike.position, player.position) < 2.2 and hasattr(player, 'take_damage'):
                player.take_damage(16)
                spawn_damage_popup(player.position, 16, color.magenta)
        self.destroy_entity(spike)
        self.destroy_entity(glow)

    def shoot_meteors(self):
        """Воздушная атака: метеоритный дождь рядом с игроком"""
        if self._is_destroyed or not self.is_alive or not self.is_airborne:
            return

        self.meteor_cooldown = self.meteor_interval

        if combat_ui:
            combat_ui.set_warning('МЕТЕОРИТНЫЙ ДОЖДЬ!', duration=2.0)

        if not player or not hasattr(player, 'position'):
            return

        for i in range(4):
            offset = Vec3(uniform(-10, 10), uniform(22, 32), uniform(-10, 10))
            spawn = player.position + offset
            meteor = Entity(model='sphere', color=color.rgb(255, 90, 0), position=spawn,
                           scale=1.5, collider='sphere')
            fire = Entity(model='sphere', color=color.rgba(255, 200, 0, 120),
                        position=meteor.position, scale=2, alpha=0.5)
            self.active_meteors.append(meteor)
            target = player.position + Vec3(uniform(-3, 3), 0, uniform(-3, 3))
            meteor.animate_position(target, duration=1.8, curve=curve.linear)
            fire.animate_position(target, duration=1.8, curve=curve.linear)
            fire.animate_scale(0.6, duration=1.8, curve=curve.linear)

            invoke(self.meteor_impact, meteor, fire, delay=1.8)

    def meteor_impact(self, meteor, fire):
        if meteor and meteor.enabled and player and hasattr(player, 'position'):
            if distance(meteor.position, player.position) < 3 and hasattr(player, 'take_damage'):
                player.take_damage(20)
                spawn_damage_popup(player.position, 20, color.red)

        explosion_pos = meteor.position if meteor and meteor.enabled else self.position
        explosion = Entity(model='sphere', color=color.rgba(255, 150, 0, 200),
                          position=explosion_pos, scale=0.6, alpha=0.8)
        explosion.animate_scale(5, duration=0.3)
        explosion.animate_color(color.clear, duration=0.3)
        invoke(self.destroy_entity, explosion, delay=0.35)

        self.destroy_entity(meteor)
        self.destroy_entity(fire)

    def destroy_entity(self, ent):
        if ent and ent.enabled:
            destroy(ent)

    def destroy_entities(self, ents):
        for e in ents:
            self.destroy_entity(e)

    def die(self):
        if self._is_destroyed:
            return
        self.is_alive = False
        self.in_fight = False
        self.state = 'dead'
        self.is_attacking = False

        self.cleanup_old_warnings()
        self.cleanup_spikes()

        if self.actor_loaded:
            self.play_animation('deaddown', loop=False)
        else:
            self.color = color.gray

        if self.has_taken_off:
            self.animate_position((self.x, 0, self.z), duration=2, curve=curve.in_out_sine)
        self.animate_rotation((0, 0, 90), duration=2, curve=curve.in_out_sine)

        if combat_ui:
            combat_ui.hide()

        start_victory_cutscene(self)

        # Награда за победу
        global player_stats
        player_stats['kills'] += 1
        exp_reward = 150 + player_stats['level'] * 50
        gain_exp(exp_reward)
        if level_up_screen:
            invoke(level_up_screen.show_screen, delay=5.5)

        invoke(self.safe_destroy, delay=6)

    def safe_destroy(self):
        if self._is_destroyed:
            return
        self._is_destroyed = True

        self.cleanup_old_warnings()
        self.cleanup_spikes()

        if hasattr(self, 'health_bar') and self.health_bar:
            try:
                self.health_bar.enabled = False
                if hasattr(self.health_bar, 'fill'):
                    self.health_bar.fill.enabled = False
                if hasattr(self.health_bar, 'bg'):
                    self.health_bar.bg.enabled = False
            except:
                pass
        try:
            self.collider = None
            if self.actor_loaded and self.actor:
                try:
                    self.actor.stop(self.current_animation)
                    self.actor.removeNode()
                except:
                    pass
            self.enabled = False
            if self in scene.entities:
                scene.entities.remove(self)
        except:
            pass

    def start_fight(self):
        if not self.in_fight and self.is_alive and not self._is_destroyed:
            self.in_fight = True
            if self.actor_loaded:
                self.play_animation('run')

    def stop_fight(self):
        if self.in_fight and self.is_alive and not self._is_destroyed:
            self.in_fight = False
            # Анимация run продолжается всегда, не переключаем на idle

            if not self.has_taken_off:
                self.y = 0
            else:
                self.y = self.fly_height

    def shoot_fireball(self):
        """Стреляет файрболом (только в воздушной фазе)"""
        if (not self.in_fight or not self.target or not self.is_alive or
                self._is_destroyed or not self.is_airborne or not self.can_fireball_attack):
            return

        if self.is_airborne:
            fireball_pos = self.position + Vec3(0, 3, -3)
            DragonFireball(position=fireball_pos, target=self.target)

    def update(self):
        if not self.target or not self.is_alive or self._is_destroyed:
            return

        dist = distance(self.position, self.target.position)

        if dist <= self.trigger_radius:
            if not self.in_fight and self.is_alive:
                self.start_fight()
        else:
            if self.in_fight:
                self.stop_fight()

        if self.in_fight and self.is_alive:
            if self.knockback_cooldown > 0:
                self.knockback_cooldown -= time.dt
            if dist < self.knockback_distance and not self.is_airborne:
                self.knockback_player()

            direction = self.target.position - self.position
            if direction.length() > 0:
                target_rotation = math.degrees(math.atan2(-direction.x, -direction.z))
                self.rotation_y = lerp_angle(self.rotation_y, target_rotation, 6 * time.dt)

            # Основная анимированная атака
            if not self.is_attacking:
                self.attack_cooldown -= time.dt
                if self.attack_cooldown <= 0:
                    if self.is_airborne:
                        self.perform_air_attack()

                        self.spike_cooldown -= time.dt
                        if self.spike_cooldown <= 0:
                            self.spawn_spikes()
                            self.spike_cooldown = self.spike_interval
                    else:
                        self.perform_ground_attack()

                    self.attack_cooldown = self.attack_interval

            # Дополнительные угрозы поля боя — идут параллельно с основной атакой
            if not self.is_airborne:
                self.shockwave_cooldown -= time.dt
                if self.shockwave_cooldown <= 0:
                    self.ground_shockwave()
            else:
                self.air_spike_cooldown -= time.dt
                if self.air_spike_cooldown <= 0:
                    self.shoot_air_spikes()

                self.meteor_cooldown -= time.dt
                if self.meteor_cooldown <= 0:
                    self.shoot_meteors()


# --- Кат-сцена победы ---
def start_victory_cutscene(boss):
    """Запускает кат-сцену после смерти дракона"""
    global cutscene_active
    cutscene_active = True

    fade_screen = Entity(parent=camera.ui, model='quad', color=color.rgba(0, 0, 0, 0), scale=(2, 2))
    fade_screen.animate_color(color.rgba(0, 0, 0, 160), duration=1.0)

    cutscene_text = Text(parent=camera.ui, text='ДРАКОН ПОВЕРЖЕН!', origin=(0, 0),
                         position=(0, 0.25), scale=3, color=color.yellow, alpha=0)
    cutscene_text.animate_color(color.rgba(255, 255, 0, 255), duration=0.8, delay=0.6)

    invoke(explode_dragon, boss, delay=2.1)

    def show_victory_text():
        victory_text = Text(parent=camera.ui, text='ПОБЕДА!', origin=(0, 0),
                            position=(0, -0.05), scale=4, color=color.green, alpha=0)
        victory_text.animate_color(color.rgba(0, 255, 0, 255), duration=0.5)
        victory_text.animate_color(color.rgba(0, 255, 0, 0), duration=0.8, delay=2.0)
        invoke(destroy, victory_text, delay=3.0)

    invoke(show_victory_text, delay=2.3)

    def fade_out_all():
        fade_screen.animate_color(color.rgba(0, 0, 0, 0), duration=1.0)
        cutscene_text.animate_color(color.rgba(255, 255, 0, 0), duration=1.0)
        invoke(destroy, fade_screen, delay=1.1)
        invoke(destroy, cutscene_text, delay=1.1)

    invoke(fade_out_all, delay=4.2)
    invoke(end_cutscene, delay=5.4)


def explode_dragon(boss):
    """Финальный взрыв побеждённого дракона"""
    if not boss:
        return
    pos = boss.position

    for _ in range(40):
        particle = Entity(model='cube', color=choice([color.red, color.orange, color.yellow]),
                         position=pos + Vec3(uniform(-3, 3), uniform(0, 4), uniform(-3, 3)),
                         scale=uniform(0.2, 0.6))
        particle.animate_position(particle.position + Vec3(uniform(-5, 5), uniform(1, 6), uniform(-5, 5)),
                                  duration=1.4, curve=curve.out_quad)
        particle.animate_color(color.clear, duration=1.4)
        invoke(destroy, particle, delay=1.4)

    shock = Entity(model='circle', color=color.rgba(255, 150, 0, 180),
                  position=Vec3(pos.x, 0.2, pos.z), rotation_x=90, scale=1)
    shock.animate_scale(20, duration=0.6, curve=curve.out_quad)
    shock.animate_color(color.rgba(255, 150, 0, 0), duration=0.6)
    invoke(destroy, shock, delay=0.7)


def gain_exp(amount):
    """Начисляет опыт и повышает уровень если нужно"""
    global player_stats
    player_stats['exp'] += amount
    while player_stats['exp'] >= player_stats['exp_to_next']:
        player_stats['exp'] -= player_stats['exp_to_next']
        player_stats['level'] += 1
        player_stats['stat_points'] += 3
        player_stats['exp_to_next'] = int(player_stats['exp_to_next'] * 1.5)
    if level_up_screen:
        level_up_screen.refresh()
    save_game()


class LevelUpScreen(Entity):
    """Экран прокачки — инвентарь игрока (тёмно-синяя тема)"""
    def __init__(self, **kwargs):
        super().__init__(parent=camera.ui, **kwargs)
        self.enabled = False

        # Затемнение всего экрана позади панели, чтобы инвентарь не сливался с игрой
        self.dim_overlay = Entity(parent=self, model='quad', color=color.rgba(0, 0, 0, 140),
                                  scale=(2.2, 1.3), position=(0, 0, 2))

        # Внешнее свечение / рамка
        self.glow = Entity(parent=self, model='quad', color=color.rgba(60, 110, 255, 90),
                           scale=(0.82, 0.92), position=(0, 0, 1.1))
        self.border = Entity(parent=self, model='quad', color=color.rgba(90, 150, 255, 220),
                             scale=(0.78, 0.88), position=(0, 0, 1.0))

        # Основной фон панели — мягкий светлый (чтобы чёрный текст хорошо читался)
        self.panel = Entity(parent=self, model='quad', color=color.rgba(225, 232, 250, 250),
                            scale=(0.76, 0.86), position=(0, 0, 0.9))

        # Внутренняя ещё более светлая подложка для "воздуха"
        self.inner_panel = Entity(parent=self, model='quad', color=color.rgba(241, 245, 255, 255),
                                  scale=(0.72, 0.82), position=(0, 0, 0.85))

        # --- Заголовок на отдельной плашке ---
        self.title_bg = Entity(parent=self, model='quad', color=color.rgba(180, 200, 235, 255),
                               scale=(0.72, 0.10), position=(0, 0.385, 0.8))
        self.title = Text(parent=self, text='ИНВЕНТАРЬ И ХАРАКТЕРИСТИКИ', origin=(0, 0),
                          y=0.385, scale=1.25, color=color.black, z=0.79)

        # --- Карточка с общей информацией о персонаже ---
        self.info_card = Entity(parent=self, model='quad', color=color.rgba(205, 218, 245, 255),
                                scale=(0.66, 0.22), position=(0, 0.235, 0.8))
        self.info_card_border = Entity(parent=self, model='quad', color=color.rgba(90, 150, 255, 120),
                                       scale=(0.665, 0.225), position=(0, 0.235, 0.79))

        self.level_text   = Text(parent=self, text='', origin=(0, 0), y=0.305, scale=1.15,
                                 color=color.black, z=0.78)
        self.exp_text     = Text(parent=self, text='', origin=(0, 0), y=0.255, scale=0.95,
                                 color=color.black, z=0.78)
        self.points_text  = Text(parent=self, text='', origin=(0, 0), y=0.205, scale=1.05,
                                 color=color.black, z=0.78)
        self.kills_text   = Text(parent=self, text='', origin=(0, 0), y=0.165, scale=0.9,
                                 color=color.black, z=0.78)

        self.sep = Entity(parent=self, model='quad', color=color.rgba(90, 150, 255, 160),
                          scale=(0.62, 0.004), position=(0, 0.10, 0.78))

        self.stats_label = Text(parent=self, text='ПРОКАЧКА', origin=(0, 0), y=0.065,
                                scale=1.0, color=color.black, z=0.78)

        # --- Карточки прокачки характеристик ---
        btn_y = [-0.03, -0.16, -0.29]
        stat_keys = ['speed', 'fireball_damage', 'max_health']
        stat_labels = ['Скорость', 'Урон магии', 'Макс. здоровье']
        stat_colors = [color.rgb(110, 220, 255), color.rgb(255, 150, 90), color.rgb(120, 230, 140)]
        self.stat_texts = []
        self.upgrade_btns = []
        self.stat_cards = []

        for i, (key, label, col) in enumerate(zip(stat_keys, stat_labels, stat_colors)):
            card = Entity(parent=self, model='quad', color=color.rgba(213, 224, 248, 255),
                         scale=(0.62, 0.105), position=(0, btn_y[i], 0.8))
            card_border = Entity(parent=self, model='quad', color=color.rgba(90, 150, 255, 90),
                                 scale=(0.622, 0.107), position=(0, btn_y[i], 0.79))
            self.stat_cards.append(card)

            st = Text(parent=self, text='', origin=(-0.5, 0),
                      position=(-0.27, btn_y[i]), scale=0.95, color=color.black, z=0.78)
            self.stat_texts.append((key, st))

            btn = Button(parent=self, text='+', scale=(0.085, 0.085),
                         position=(0.27, btn_y[i]), z=-0.78,
                         color=color.rgba(34, 160, 85, 255),
                         highlight_color=color.rgba(64, 200, 115, 255),
                         pressed_color=color.rgba(18, 100, 50, 255),
                         text_color=color.white)
            btn._stat_key = key
            btn.on_click = Func(self.upgrade_stat, key)
            self.upgrade_btns.append(btn)

        close_btn = Button(parent=self, text='ЗАКРЫТЬ [F / I]', scale=(0.32, 0.085),
                           position=(0, -0.385), z=-0.78,
                           color=color.rgba(150, 35, 35, 230),
                           highlight_color=color.rgba(200, 55, 55, 255),
                           text_color=color.white)
        close_btn.on_click = self.hide_screen

        self.refresh()

    def refresh(self):
        ps = player_stats
        self.level_text.text  = f'Уровень: {ps["level"]}'
        self.exp_text.text    = f'Опыт: {ps["exp"]} / {ps["exp_to_next"]}'
        self.points_text.text = f'Очки навыков: {ps["stat_points"]}'
        self.kills_text.text  = f'Убито драконов: {ps["kills"]}'
        labels = {'speed': 'Скорость', 'fireball_damage': 'Урон магии', 'max_health': 'Макс. HP'}
        for key, st in self.stat_texts:
            st.text = f'{labels[key]}: {ps[key]}'
        # Кнопки приглушены (тёмно-серые, непрозрачные), если нет очков прокачки
        for btn in self.upgrade_btns:
            btn.color = (color.rgba(34, 160, 85, 255) if ps['stat_points'] > 0
                         else color.rgba(95, 100, 110, 255))

    def upgrade_stat(self, key):
        global player_stats, SPEED, FIREBALL_DAMAGE, PLAYER_MAX_HEALTH
        if player_stats['stat_points'] <= 0:
            return
        player_stats['stat_points'] -= 1
        if key == 'speed':
            player_stats['speed'] += 1
            SPEED = player_stats['speed']
        elif key == 'fireball_damage':
            player_stats['fireball_damage'] += 5
            FIREBALL_DAMAGE = player_stats['fireball_damage']
        elif key == 'max_health':
            player_stats['max_health'] += 25
            PLAYER_MAX_HEALTH = player_stats['max_health']
            if player and hasattr(player, 'health_bar'):
                player.health_bar.max_health = PLAYER_MAX_HEALTH
                player.health_bar.heal(25)
        self.refresh()
        save_game()

    def show_screen(self):
        self.enabled = True
        for child in self.children:
            child.enabled = True
        mouse.locked = False
        self.refresh()

    def hide_screen(self):
        self.enabled = False
        for child in self.children:
            child.enabled = False
        if not menu.enabled:
            mouse.locked = True


def end_cutscene():
    """Завершает кат-сцену и возвращает управление игроку"""
    global cutscene_active
    cutscene_active = False


class Player(Entity):
    def __init__(self, **kwargs):
        super().__init__(model='cube', color=color.blue, scale=(0.8, 1.8, 0.8),
                         position=(0, 4, -55), collider='box', **kwargs)
        self.health_bar = HealthBar(max_health=PLAYER_MAX_HEALTH, is_boss=False)
        self.is_alive = True
        self.invincible = False
        self.invincible_timer = 0
        self._is_destroyed = False
        self.can_dash = True
        self.dash_cooldown = 0

        # Боевые кулдауны
        self.fireball_cooldown = 0
        self.melee_cooldown = 0

    def take_damage(self, amount):
        if not self.is_alive or self.invincible or self._is_destroyed:
            return

        self.invincible = True
        self.invincible_timer = 1.0
        self.color = color.red
        invoke(self.reset_color, delay=0.3)

        if self.health_bar.take_damage(amount):
            self.die()
        else:
            original_color = self.color
            self.animate_color(color.red, duration=0.1)
            invoke(lambda: setattr(self, 'color', original_color)
            if not self._is_destroyed else None, delay=0.1)

    def reset_color(self):
        if not self._is_destroyed:
            self.color = color.blue
            self.invincible = False

    def dash(self):
        if self.can_dash:
            direction = Vec3(0, 0, 0)

            camera_forward = Vec3(camera.forward.x, 0, camera.forward.z).normalized()
            camera_right = Vec3(camera.right.x, 0, camera.right.z).normalized()

            if held_keys['w']:
                direction += camera_forward
            if held_keys['s']:
                direction -= camera_forward
            if held_keys['d']:
                direction += camera_right
            if held_keys['a']:
                direction -= camera_right

            if direction == Vec3(0, 0, 0):
                direction = camera_forward

            if direction.length() > 0:
                direction = direction.normalized()
                self.position += direction * 3

                self.invincible = True
                self.invincible_timer = 0.3

                self.can_dash = False
                self.dash_cooldown = DASH_COOLDOWN

                self.create_dash_effect(direction)

    def create_dash_effect(self, direction):
        """Создает визуальные эффекты dash"""
        dash_effect = Entity(
            model='sphere',
            color=color.cyan,
            position=self.position,
            scale=0.5,
            alpha=0.7
        )
        dash_effect.animate_scale(2, duration=0.3)
        dash_effect.animate_color(color.clear, duration=0.3)

        def remove_effect(e):
            if e and e.enabled:
                e.enabled = False

        invoke(remove_effect, dash_effect, delay=0.3)

        for i in range(3):
            trail = Entity(
                model='sphere',
                color=color.blue,
                position=self.position - direction * (i * 0.5),
                scale=0.3,
                alpha=0.5
            )
            trail.animate_scale(0.1, duration=0.5)

            def remove_trail(t):
                if t and t.enabled:
                    t.enabled = False

            invoke(remove_trail, trail, delay=0.5)

    def shoot_fireball(self):
        """Дальняя атака — огненный шар в направлении камеры"""
        if self.fireball_cooldown > 0 or not self.is_alive or self._is_destroyed:
            return

        self.fireball_cooldown = FIREBALL_COOLDOWN

        direction = camera.forward.normalized()
        spawn_pos = self.position + Vec3(0, 1, 0) + direction * 1.2

        charge = Entity(model='sphere', color=color.cyan, scale=0.3, position=spawn_pos, alpha=0.8)
        charge.animate_scale(0.6, duration=0.1, curve=curve.out_quad)
        invoke(destroy, charge, delay=0.15)

        PlayerFireball(position=spawn_pos, direction=direction)

        try:
            self.animate_rotation_x(-10, duration=0.05, curve=curve.out_quad)
            invoke(lambda: self.animate_rotation_x(0, duration=0.15)
            if not self._is_destroyed else None, delay=0.05)
        except:
            pass

    def melee_attack(self):
        """Ближняя атака — огромный клинок разрезает сверху вниз на 15 единиц"""
        if self.melee_cooldown > 0 or not self.is_alive or self._is_destroyed:
            return

        self.melee_cooldown = MELEE_COOLDOWN

        lunge_dir = Vec3(camera.forward.x, 0, camera.forward.z)
        if lunge_dir.length() > 0:
            lunge_dir = lunge_dir.normalized()
        else:
            lunge_dir = Vec3(0, 0, -1)

        slash_center = self.position + lunge_dir * 7.5 + Vec3(0, 1, 0)

        # --- Огромный клинок (вытянутый куб) ---
        # Начинает сверху, падает вниз
        blade_start = slash_center + Vec3(0, 9, 0)
        blade_end   = slash_center + Vec3(0, -5, 0)

        blade = Entity(
            model='cube',
            color=color.rgb(180, 220, 255),
            scale=(0.35, 10, 0.18),
            position=blade_start,
        )
        # Наклоняем клинок по направлению удара
        blade.look_at(blade.position + lunge_dir)
        blade.rotation_x += 90

        # Блеск клинка
        blade_glow = Entity(
            model='cube',
            color=color.rgba(200, 240, 255, 120),
            scale=(0.9, 10.5, 0.5),
            position=blade_start,
        )
        blade_glow.look_at(blade_glow.position + lunge_dir)
        blade_glow.rotation_x += 90

        # Анимация удара: клинок летит вниз
        blade.animate_position(blade_end, duration=0.18, curve=curve.out_expo)
        blade_glow.animate_position(blade_end, duration=0.18, curve=curve.out_expo)

        # Клинок исчезает после удара
        def finish_slash(b, bg):
            if b and b.enabled:
                b.animate_color(color.clear, duration=0.12)
            if bg and bg.enabled:
                bg.animate_color(color.clear, duration=0.12)
            invoke(lambda: destroy(b) if b and b.enabled else None, delay=0.14)
            invoke(lambda: destroy(bg) if bg and bg.enabled else None, delay=0.14)

            # Эффект удара на земле — горизонтальный разрез
            slash_hit = Entity(
                model='cube',
                color=color.rgba(180, 230, 255, 200),
                scale=(0.2, 0.15, 15),
                position=self.position + lunge_dir * 7.5 + Vec3(0, 0.1, 0),
            )
            slash_hit.look_at(slash_hit.position + lunge_dir)
            slash_hit.animate_scale((8, 0.15, 15), duration=0.12, curve=curve.out_quad)
            slash_hit.animate_color(color.clear, duration=0.2)
            invoke(lambda: destroy(slash_hit) if slash_hit and slash_hit.enabled else None, delay=0.22)

            # Волна от удара — белые частицы в стороны
            for i in range(10):
                side = Vec3(lunge_dir.z, 0, -lunge_dir.x)  # перпендикуляр
                t = (i / 9) * 2 - 1  # от -1 до 1
                spark_pos = self.position + lunge_dir * (4 + abs(t) * 6) + side * t * 5 + Vec3(0, 0.3, 0)
                spark = Entity(
                    model='cube',
                    color=color.rgba(200, 240, 255, 220),
                    scale=uniform(0.15, 0.4),
                    position=spark_pos
                )
                spark.animate_position(spark_pos + Vec3(0, uniform(1, 3), 0), duration=0.25, curve=curve.out_quad)
                spark.animate_color(color.clear, duration=0.25)
                invoke(lambda e=spark: destroy(e) if e and e.enabled else None, delay=0.28)

        invoke(finish_slash, blade, blade_glow, delay=0.18)

        # Урон — проверяем на всю длину удара (15 единиц), только если дракон на земле
        if dragon and not getattr(dragon, '_is_destroyed', True) and getattr(dragon, 'is_alive', False):
            if not getattr(dragon, 'is_airborne', False):
                d = distance(self.position, dragon.position)
                if d < 15:
                    dragon.take_damage(MELEE_DAMAGE)
                    spawn_damage_popup(dragon.position, MELEE_DAMAGE, color.yellow)

    def update(self):
        if self._is_destroyed:
            return

        if self.invincible:
            self.invincible_timer -= time.dt
            if self.invincible_timer <= 0:
                self.reset_color()

        if not self.can_dash:
            self.dash_cooldown -= time.dt
            if self.dash_cooldown <= 0:
                self.can_dash = True

        if self.fireball_cooldown > 0:
            self.fireball_cooldown -= time.dt
        if self.melee_cooldown > 0:
            self.melee_cooldown -= time.dt

    def die(self):
        if self._is_destroyed:
            return
        self.is_alive = False
        self.color = color.gray
        self._is_destroyed = True

        if combat_ui:
            combat_ui.hide()

        save_game()  # Сохраняем прогресс прокачки; позиция/здоровье не сохранятся, т.к. игрок уже "destroyed"

        Text(text='ВЫ ПРОИГРАЛИ!\nНажмите R для перезапуска', origin=(0, 0),
             scale=2, color=color.red, background=True)
        application.paused = True


def create_mountain(position, width, height, rotation_y=0, snow_cap=True, rock_color=None):
    """Создаёт одну выразительную гору из нескольких слоёв конусов:
    широкое тёмное подножие, более светлый средний ярус, острый пик и снежная шапка.
    Так горы выглядят объёмнее и естественнее, чем один сплошной конус."""
    x, y, z = position
    base_rock = rock_color or color.rgb(90, 92, 110)

    # Подножие — самое широкое и тёмное, слегка приплюснутое
    Entity(model='cone', color=base_rock.tint(-0.25), position=(x, y, z),
          scale=(width, height * 0.55, width), rotation=(0, rotation_y, 0))

    # Средний ярус — немного уже и выше, чуть светлее, смещён вверх
    mid_w = width * 0.68
    Entity(model='cone', color=base_rock, position=(x, y + height * 0.30, z),
          scale=(mid_w, height * 0.55, mid_w), rotation=(0, rotation_y + 25, 0))

    # Острый пик — узкий и светлый
    peak_w = width * 0.32
    Entity(model='cone', color=base_rock.tint(0.18), position=(x, y + height * 0.62, z),
          scale=(peak_w, height * 0.45, peak_w), rotation=(0, rotation_y - 15, 0))

    # Снежная шапка на самой верхушке
    if snow_cap:
        snow_w = width * 0.16
        Entity(model='cone', color=color.rgb(245, 248, 252),
              position=(x, y + height * 0.86, z),
              scale=(snow_w, height * 0.22, snow_w), rotation=(0, rotation_y + 10, 0))

    # Каменные выступы у подножия — добавляют детализации силуэту
    for _ in range(3):
        ox = uniform(-width * 0.5, width * 0.5)
        oz = uniform(-width * 0.5, width * 0.5)
        rw = uniform(width * 0.12, width * 0.22)
        Entity(model='cube', color=base_rock.tint(uniform(-0.3, 0.1)),
              position=(x + ox, y + uniform(0, height * 0.08), z + oz),
              scale=(rw, rw * uniform(0.6, 1.1), rw),
              rotation=(0, uniform(0, 360), 0))


def create_world():
    """Создает окружение: горы, деревья, камни, облака и атмосферное освещение"""
    mountain_colors = [color.rgb(95, 100, 130), color.rgb(120, 110, 150), color.rgb(80, 95, 120),
                       color.rgb(105, 95, 115)]
    for i in range(10):
        angle = (360 / 10) * i
        dist = 95
        x = math.sin(math.radians(angle)) * dist
        z = math.cos(math.radians(angle)) * dist
        mh = uniform(28, 42)
        create_mountain((x, 0, z), width=uniform(16, 24), height=mh,
                        rotation_y=uniform(0, 360), snow_cap=(mh > 33),
                        rock_color=choice(mountain_colors))

    # --- Главная гора-преграда между спавном игрока и логовом босса ---
    # Игрок стартует на z=-55, дракон спавнится на z=60 — гора стоит между ними и
    # перекрывает прямую линию видимости, заставляя обходить её по тропинке.
    create_mountain((0, -1, 5), width=40, height=52, rotation_y=18,
                    snow_cap=True, rock_color=color.rgb(85, 90, 115))
    create_mountain((-16, -2, -4), width=20, height=32, rotation_y=50,
                    snow_cap=False, rock_color=color.rgb(100, 105, 130))
    create_mountain((18, -2, 12), width=22, height=34, rotation_y=-30,
                    snow_cap=False, rock_color=color.rgb(75, 80, 105))

    # --- Тропинка от спавна игрока к логову босса, огибающая гору справа ---
    path_color = color.rgb(170, 150, 110)
    path_points = [
        (0, -55), (3, -45), (7, -35), (13, -27), (20, -19),
        (27, -10), (31, 0), (31, 10), (27, 19), (20, 27),
        (13, 35), (7, 45), (3, 53), (0, 62),
    ]
    for px, pz in path_points:
        Entity(model='cube', color=path_color, position=(px, 0.02, pz),
              scale=(5, 0.05, 7), rotation=(0, 0, 0))

    trunk_color = color.rgb(101, 67, 33)
    leaves_colors = [color.rgb(34, 130, 50), color.rgb(60, 150, 40), color.rgb(40, 120, 70)]
    for i in range(35):
        angle = uniform(0, 360)
        dist = uniform(35, 75)
        x = math.sin(math.radians(angle)) * dist
        z = math.cos(math.radians(angle)) * dist
        # Не ставим деревья на тропинке и на горе-преграде
        if abs(x) < 34 and -60 < z < 65:
            continue
        Entity(model='cylinder', color=trunk_color, position=(x, 2.5, z), scale=(0.5, 5, 0.5))
        Entity(model='sphere', color=choice(leaves_colors), position=(x, 6, z), scale=uniform(3, 5))

    for i in range(20):
        angle = uniform(0, 360)
        dist = uniform(20, 65)
        x = math.sin(math.radians(angle)) * dist
        z = math.cos(math.radians(angle)) * dist
        if abs(x) < 34 and -60 < z < 65:
            continue
        Entity(model='cube', color=color.rgb(115, 112, 118), position=(x, uniform(0, 1.5), z),
              scale=uniform(1, 2.5),
              rotation=(uniform(0, 360), uniform(0, 360), uniform(0, 360)))

    # Облака — мягкое свечение + лёгкое покачивание, чтобы небо выглядело "живым"
    for i in range(18):
        angle = uniform(0, 360)
        dist = uniform(50, 90)
        x = math.sin(math.radians(angle)) * dist
        z = math.cos(math.radians(angle)) * dist
        y = uniform(16, 28)
        cloud = Entity(model='sphere', color=color.rgba(255, 255, 255, 235),
                       position=(x, y, z), scale=uniform(3, 6.5))
        cloud.animate_y(y + uniform(0.6, 1.4), duration=uniform(4, 7),
                        loop=True, curve=curve.in_out_sine)

    # Освещение: тёплый направленный свет (солнце) + прохладный заполняющий + мягкий рассеянный
    AmbientLight(color=color.rgb(140, 150, 175))
    sun = DirectionalLight(color=color.rgb(255, 244, 214), direction=(0.6, -0.8, 0.4), shadows=True)
    DirectionalLight(color=color.rgb(120, 150, 210), direction=(-0.5, -0.3, -0.6))

    # Атмосферная дымка/туман — добавляет глубину и "кинематографичность" картинке
    try:
        from panda3d.core import Fog
        scene_fog = Fog('world_fog')
        scene_fog.setColor(190 / 255, 215 / 255, 235 / 255)
        scene_fog.setExpDensity(0.0035)
        render.setFog(scene_fog)
    except Exception:
        pass


def clean_up_game():
    """Очищает все игровые объекты перед новой игрой"""
    global player, dragon, cutscene_active

    cutscene_active = False

    if combat_ui:
        combat_ui.hide()

    if dragon and hasattr(dragon, 'safe_destroy'):
        dragon.safe_destroy()
        dragon = None

    if player:
        player._is_destroyed = True
        player.enabled = False
        if hasattr(player, 'health_bar') and player.health_bar:
            try:
                player.health_bar.enabled = False
                if hasattr(player.health_bar, 'fill'):
                    player.health_bar.fill.enabled = False
                if hasattr(player.health_bar, 'bg'):
                    player.health_bar.bg.enabled = False
            except:
                pass
        if player in scene.entities:
            scene.entities.remove(player)
        player = None

    # Очищаем все снаряды и шипы
    for entity in list(scene.entities):
        try:
            if isinstance(entity, (DragonFireball, PlayerFireball, Spike)):
                if hasattr(entity, 'safe_explode'):
                    entity.safe_explode()
                elif hasattr(entity, 'safe_destroy'):
                    entity.safe_destroy()
                else:
                    entity.enabled = False
                    if entity in scene.entities:
                        scene.entities.remove(entity)
        except:
            pass

    # Очищаем все текстовые сообщения, кроме меню и боевого HUD
    for entity in list(scene.entities):
        try:
            if isinstance(entity, Text) and entity.parent not in (menu, combat_ui):
                entity.enabled = False
                if entity in scene.entities:
                    scene.entities.remove(entity)
        except:
            pass

    global is_dashing, dash_time, dash_cooldown, dash_dir, move, velocity_y, is_grounded, yaw, pitch
    is_dashing = False
    dash_time = 0
    dash_cooldown = 0
    dash_dir = Vec3(0, 0, 0)
    move = Vec3(0, 0, 0)
    velocity_y = 0
    is_grounded = False
    yaw = 0
    pitch = 15

    application.paused = False


def restart_game():
    global player, dragon
    clean_up_game()
    player = Player()
    dragon = DragonBoss(target=player, trigger_radius=50)
    if combat_ui:
        combat_ui.show()


def input(key):
    global is_dashing, dash_time, dash_dir, dash_cooldown, move, velocity_y

    if (key == 'i' or key == 'f') and level_up_screen:
        if level_up_screen.enabled:
            level_up_screen.hide_screen()
        else:
            level_up_screen.show_screen()
        return

    if key == 'escape':
        if not menu.enabled:
            # Сохраняем прогресс перед выходом в меню, если игра шла
            if player and hasattr(player, 'is_alive') and player.is_alive:
                save_game()
            menu.enabled = True
            menu.update_continue_button()
            mouse.locked = False
            application.paused = True
            clean_up_game()
        else:
            application.quit()
        return

    if cutscene_active:
        return

    if key == 'q' and not is_dashing and dash_cooldown <= 0:
        if move.length() > 0:
            dash_dir = move.normalized()
            is_dashing = True
            dash_time = DASH_TIME

    if key == 'shift' and player and player.is_alive and player.can_dash:
        player.dash()

    if key == 'space' and is_grounded:
        velocity_y = JUMP_HEIGHT

    if key == 'left mouse down' and player and player.is_alive and player.fireball_cooldown <= 0:
        player.shoot_fireball()

    if key == 'e' and player and player.is_alive and player.melee_cooldown <= 0:
        player.melee_attack()

    if key == 'r' and player and hasattr(player, 'is_alive') and not player.is_alive:
        restart_game()


def update():
    global yaw, pitch, is_dashing, dash_time, dash_cooldown, dash_dir, move
    global velocity_y, is_grounded

    if application.paused:
        return

    dt = time.dt

    if not player:
        return

    if mouse.locked and not cutscene_active:
        yaw += mouse.velocity[0] * MOUSE_SENS * dt
        pitch -= mouse.velocity[1] * MOUSE_SENS * dt
        pitch = clamp(pitch, -30, 80)

    camera.rotation = Vec3(pitch, yaw, 0)
    cam_target = player.position + Vec3(0, CAM_HEIGHT, 0)
    camera.position = cam_target - camera.forward * CAM_DIST
    camera.look_at(cam_target)

    if cutscene_active:
        return  # во время кат-сцены игрок не двигается

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

    if move.length() > 0:
        target_rotation = math.degrees(math.atan2(-move.x, -move.z))
        player.rotation_y = lerp_angle(player.rotation_y, target_rotation, 8 * dt)


# --- Небо: процедурная градиентная текстура (закатное небо с мягким солнцем и облаками) ---
sky_texture_path = generate_sky_texture()
if sky_texture_path:
    try:
        sky = Sky(texture=load_texture(sky_texture_path))
    except Exception:
        sky = Sky(color=color.rgb(135, 206, 235))
else:
    sky = Sky(color=color.rgb(135, 206, 235))
ground = Entity(model='plane', scale=(150, 1, 150), collider='box',
                texture='grass', texture_scale=(40, 40))
create_world()

menu = MainMenu()
combat_ui = CombatUI()
level_up_screen = LevelUpScreen()
mouse.locked = False
application.paused = False

app.run()
