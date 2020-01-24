import pygame
import os
import math
import time
import sys


def load_sound(name):
    fullname = os.path.join('data\\sounds', name)
    return pygame.mixer.Sound(fullname)


def load_music(name):
    fullname = os.path.join('data\\sounds', name)
    return pygame.mixer.music.load(fullname)


def load_image(name, colorkey=None):
    fullname = os.path.join('data\\images', name)
    image = pygame.image.load(fullname)
    if colorkey is not None:
        if colorkey == -1:
            colorkey = image.get_at((0, 0))
            image.set_colorkey(colorkey)
        else:
            image = image.convert_alpha()
    return image


# константы
TANK_PASSABITILY = 1
SHELL_PASSABILITY = 2
GLOBAL_TIMER_EVENT = 30
FPS = 50
GAME_DURATION = 100
TANK_SPEED = 1
SHELL_SPEED = 5
ROTATION_SPEED = 5
SHOOT_DELAY = 3
TILE_WIDTH = TILE_HEIGHT = 50
grass_image = load_image('grass.png')
box_image = load_image('box.png')
player_image = load_image('tank_50.png')
shell_image = load_image('Cannon_Ball_20.png')
wall_image = load_image('wall.png', -1)
river_image = load_image('water.png', -1)
bot_image = load_image('bot.png')
objects = list()
tiles = list()
pygame.mixer.init()
tank_move_sound = load_sound("Move.ogg")
shoot_sound = load_sound("Shoot.ogg")
boom_sound = load_sound("Boom.ogg")
tank_move_sound.set_volume(0.05)


# Функция загрузки уровня
def load_level(filename):
    filename = "data/" + filename
    # Читаем уровень, убирая символы перевода строки
    with open(filename, 'r') as mapFile:
        level_map = [line.strip() for line in mapFile]

    # И подсчитываем максимальную длину
    max_width = max(map(len, level_map))

    # Дополняем каждую строку пустыми клетками ('.')
    return list(map(lambda x: x.ljust(max_width, '.'), level_map))


# Родительский класс для всех клеток поля
class Tile(pygame.sprite.Sprite):
    def __init__(self, image, pos_x, pos_y, *groups):
        super().__init__(groups)
        self.passability = TANK_PASSABITILY | SHELL_PASSABILITY
        self.image = image
        # Поверхность клетки
        self.rect = self.image.get_rect().move(TILE_WIDTH * pos_x,
                                               TILE_HEIGHT * pos_y)
        # Задаём маску
        self.mask = pygame.mask.from_surface(self.image)
        self.destructible = True


# Задаём класс травы
class Empty(Tile):
    def __init__(self, pos_x, pos_y):
        super().__init__(grass_image, pos_x, pos_y, tiles_group, all_sprites)


# Задаём класс контейнер
class Wall(Tile):
    def __init__(self, pos_x, pos_y):
        super().__init__(box_image, pos_x, pos_y, tiles_group, all_sprites,
                         wall_group)
        self.passability = 0


# Задаём класс стены
class Stonewall(Tile):
    def __init__(self, pos_x, pos_y):
        super().__init__(wall_image, pos_x, pos_y, tiles_group, all_sprites,
                         stonewall_group)
        self.passability = 0
        self.destructible = False


# Задаём класс реки
class River(Tile):
    def __init__(self, pos_x, pos_y):
        super().__init__(river_image, pos_x, pos_y, tiles_group, all_sprites,
                         river_group)
        self.passability = SHELL_PASSABILITY


# Родительский класс для всего, что движется
class Object(pygame.sprite.Sprite):
    def __init__(self, image, pos_x, pos_y, *groups):
        super().__init__(groups)
        self.image = image
        self.rect = self.image.get_rect().move(int(TILE_WIDTH * pos_x),
                                               int(TILE_HEIGHT * pos_y))
        self.mask = pygame.mask.from_surface(self.image)
        self.x = float(self.rect.x)
        self.y = float(self.rect.y)
        objects.append(self)

    # Функция двиижения вперёд-назад
    def move(self):
        # Если смещение равно 0, то мы стоим
        if self.offset == 0:
            return self.x, self.y
        # Сохраняем старые координаты на случай столкновения танка с препятствием
        old_x = self.x
        old_y = self.y
        # Рассчёт новых координат
        self.y += self.offset * math.cos(self.angle * math.pi / 180)
        self.x -= self.offset * math.sin(self.angle * math.pi / 180)
        # Двигаем сам объект
        self.rect.x = int(self.x)
        self.rect.y = int(self.y)
        return old_x, old_y

    # Функция вращения объекта
    def rotate(self):
        pass

    # Функция столкновения техники
    def collide(self):
        """Берём x и y, отсчитываемые от верхнего левого угла поля, вне зависимости от экрана
        Данные строки позволяют избавиться от проблем с взаимодействием с камерой,
        возникающих из - за смещениия камеры"""
        y = (self.rect.y - tiles[0][0].rect.y) // TILE_HEIGHT
        x = (self.rect.x - tiles[0][0].rect.x) // TILE_WIDTH
        # Берём размерность матрицы
        height = len(tiles)
        width = len(tiles[0])
        # Задаём границы соседних с объектом клеток для проверки возможного столкновения
        y1 = max(0, y - 1)
        y2 = min(y + 2, height)
        x1 = max(0, x - 1)
        x2 = min(x + 2, width)
        # Проверяем объект на наличие столкновений с полем
        for i in range(y1, y2):
            for j in range(x1, x2):
                tile = tiles[i][j]
                if (self.type & tile.passability != self.type) and \
                        pygame.sprite.collide_mask(self, tile):
                    return tile
        # Проверяем столкновения с танками
        if self.is_bot:
            if pygame.sprite.collide_mask(self, player):
                return player
        else:
            if pygame.sprite.collide_mask(self, bot):
                return bot

        return False

    # Функция, для создания "живости" некоторых объектов
    def process(self):
        self.move()
        self.rotate()


# Класс танка
class Tank(Object):
    def __init__(self, image, shoot_delay, pos_x, pos_y, tank_speed,
                 tank_rotation_speed, is_bot,
                 *groups):
        super().__init__(image, pos_x, pos_y, groups)
        """Храним картинку неповёрнутого танка, чтобы на её основе отрисовать картинку повёрнутого 
        танка"""
        self.image_always = self.image
        # Задаём угол поворота танка относительно вертикали
        self.angle = 0
        # Задаём смещение танка
        self.offset = 0
        # Задаём угловое смещение танка
        self.angle_offset = 0
        # Задаём скорость движения танка
        self.speed = tank_speed
        # Задаём угловую скорость  танка
        self.rotation_speed = tank_rotation_speed
        # Задаём тип танков
        self.type = TANK_PASSABITILY
        # Задаём танку скорострельность
        self.shoot_delay = shoot_delay * FPS
        # Задаём задаём задержку меежду выстрелами в данный момент
        self.current_delay = self.shoot_delay
        self.is_bot = is_bot

    # Функция двиижения вперёд-назад
    def move(self):
        old_x, old_y = super().move()
        if self.angle_offset == 0 and self.offset == 0:
            tank_move_sound.stop()
        else:
            tank_move_sound.play()
        if self.collide():
            self.x = old_x
            self.y = old_y
            self.rect.x = int(self.x)
            self.rect.y = int(self.y)
            return False
        return True

    # Функция вращения объекта
    def rotate(self):
        if self.angle_offset == 0:
            return
        tank_move_sound.play()
        # Сохраняем старые координаты и значение угла на случай столкновения танка с препятствием
        old_angle = self.angle
        old_rect_y = self.y
        old_rect_x = self.x
        old_image = self.image
        old_mask = self.mask
        # Меняем значение угла
        self.angle += self.angle_offset
        # Крутим картинку
        self.image = pygame.transform.rotate(self.image_always, -self.angle)
        # Создаём новую поверхность танка
        new_rect = self.image.get_rect()
        # Высчитываем значеения для грамотного  поворота танка относительно центра
        self.x += (self.rect.width - new_rect.width) / 2
        self.y += (self.rect.height - new_rect.height) / 2
        self.rect = new_rect.move(int(self.x), int(self.y))
        self.mask = pygame.mask.from_surface(self.image)
        # Проверяем, произошло ли столкновение
        if self.collide():
            # Если да, то возвращаем координаты обратно
            self.angle = old_angle
            self.y = old_rect_y
            self.x = old_rect_x
            self.rect.x = int(self.x)
            self.rect.y = int(self.y)
            self.image = old_image
            self.mask = old_mask

    # Функция, для создания "живости" танка
    def process(self):
        super().process()
        # Если танк не может стрелять
        if self.current_delay > 0:
            # То уменшаем задержку
            self.current_delay -= 1

    # Метод стрельбы
    def shoot(self):
        # Проверка, может ли танк стрелять
        if self.current_delay > 0:
            return
        tank_move_sound.stop()
        shoot_sound.play()
        # Высчитываем габариты танка
        original_rect = self.image_always.get_rect()
        # Находим координаты той точки, из которой будут вылетать снаряды
        pos_x = self.rect.centerx + original_rect.width / 2 * \
                +math.sin(self.angle * math.pi / 180)
        pos_y = self.rect.centery - original_rect.height / 2 * \
                math.cos(self.angle * math.pi / 180)
        # Создаём снаряд
        Shell(pos_x / TILE_WIDTH, pos_y / TILE_HEIGHT, self.angle, -SHELL_SPEED, self.is_bot)
        # Обновляем задержку
        self.current_delay = self.shoot_delay


# Класс игрока
class Player(Tank):
    def __init__(self, pos_x, pos_y):
        super().__init__(player_image, SHOOT_DELAY, pos_x, pos_y, TANK_SPEED, ROTATION_SPEED, False,
                         player_group,
                         all_sprites)

    # Функция, обрабатывающая сигналы с клавиатуры
    def update(self, event):
        global start_menu
        # Проверяем на наличие сигнала
        if event:
            # Проверяем, нажали ли на кнопку
            if event.type == pygame.KEYDOWN:
                # Если нажали кнопку паузы
                if pygame.key.get_pressed()[pygame.K_END]:
                    start_menu = True
                    show_menu()
                # Если нажали на кнопку движения вверх
                if pygame.key.get_pressed()[pygame.K_UP]:
                    # Едем вверх
                    self.offset = -self.speed
                # Если нажали на кнопку движения вниз
                elif pygame.key.get_pressed()[pygame.K_DOWN]:
                    # Едем вниз
                    self.offset = self.speed
                # Если нажали кнопку поворота влево
                if pygame.key.get_pressed()[pygame.K_LEFT]:
                    # Поворачиваем влево
                    self.angle_offset = -self.rotation_speed
                # Если нажали кнопку поворота вправо
                if pygame.key.get_pressed()[pygame.K_RIGHT]:
                    # Поворачиваем вправо
                    self.angle_offset = self.rotation_speed
                # Если нажали кнопку выстрела
                if pygame.key.get_pressed()[pygame.K_SPACE]:
                    # Стреляем
                    self.shoot()
            # Проверяем отпустили ли кнопку
            elif event.type == pygame.KEYUP:
                # Проверяем, отпутили ли кнопку движения танка
                if event.key == pygame.K_UP or event.key == pygame.K_DOWN:
                    # Если да, прекращаем движение
                    self.offset = 0
                # Проверяем, отпустили ли кнопку вращения танка
                if event.key == pygame.K_LEFT or event.key == pygame.K_RIGHT:
                    # Если да, прекращаем вращение
                    self.angle_offset = 0


class Bot(Tank):
    def __init__(self, pos_x, pos_y):
        super().__init__(bot_image, SHOOT_DELAY, pos_x, pos_y, TANK_SPEED, ROTATION_SPEED, True,
                         bot_group,
                         all_sprites)
        self.angle_offset = self.rotation_speed

    @staticmethod
    def get_angle_to_player(xp, yp, xb, yb):
        distance = math.sqrt((xp - xb) ** 2 + (yp - yb) ** 2)
        required_angle = math.fabs(math.asin((xb - xp) / distance) * 180 / math.pi)
        if xp <= xb:
            if yp >= yb:
                required_angle = 180 + required_angle
            else:
                required_angle = 360 - required_angle
        elif yp >= yb:
            required_angle = 180 - required_angle

        return required_angle

    def can_shoot(self):
        xb = self.rect.centerx
        yb = self.rect.centery
        offset_x = int(TILE_WIDTH * math.sin(self.angle * math.pi / 180))
        offset_y = -int(TILE_HEIGHT * math.cos(self.angle * math.pi / 180))

        xp = player.rect.centerx
        yp = player.rect.centery

        while abs(xb - xp) >= TILE_WIDTH or abs(yb - yp) >= TILE_HEIGHT:
            xb += offset_x
            yb += offset_y
            y = (yb - tiles[0][0].rect.y) // TILE_HEIGHT
            x = (xb - tiles[0][0].rect.x) // TILE_WIDTH
            if not tiles[y][x].destructible and tiles[y][x].passability & SHELL_PASSABILITY == 0:
                return False

        return True

    def rotate(self):
        required_angle = self.get_angle_to_player(player.rect.centerx, player.rect.centery, self.rect.centerx,
                                                  self.rect.centery)
        if self.angle < 0:
            self.angle += 360
        if self.angle > 360:
            self.angle -= 360
        da = required_angle - self.angle
        if math.fabs(da) > math.fabs(360 - math.fabs(da)):
            da = -da

        if math.fabs(da) > self.rotation_speed:
            if da > 0:
                self.angle_offset = self.rotation_speed
            else:
                self.angle_offset = -self.rotation_speed
        else:
            self.angle_offset = 0
            if self.offset == 0:
                self.offset = -self.speed
            # определяем, не пора ли выстрелить, т.к. игрок находится на линии огня, но могут быть препятствия
            if self.can_shoot():
                self.shoot()
        super().rotate()

    def move(self):
        if not super().move():
            self.offset = -self.offset


# Класс снаряда
class Shell(Object):
    def __init__(self, pos_x, pos_y, angle, offset, is_bot):
        super().__init__(shell_image, pos_x, pos_y, shell_group, all_sprites)
        rect = self.image.get_rect()
        self.x -= rect.width / 2
        self.y -= rect.height / 2
        self.rect.x = int(self.x)
        self.rect.y = int(self.y)
        self.angle = angle
        self.offset = offset
        # Задаём снаряду тип
        self.type = SHELL_PASSABILITY
        self.is_bot = is_bot

    @staticmethod
    def destroy_tile(tile):
        top_x = tiles[0][0].rect.x
        top_y = tiles[0][0].rect.y
        # Координаты блока, с которым произошло столкновение
        pos_x = (tile.rect.x - top_x) // TILE_WIDTH
        pos_y = (tile.rect.y - top_y) // TILE_HEIGHT
        # Заменяем препятствие блоком травы
        new_tile = Empty(pos_x, pos_y)
        new_tile.rect.move_ip(top_x, top_y)
        tiles[pos_y][pos_x] = new_tile
        # Прекращаем отображения разрушенного препятствия
        tile.kill()

    # Функция, отвечающая за движение снаряда
    def move(self):
        super().move()
        global total
        collided_object = self.collide()
        # Определение объекта столкновения
        # Проверка на столкновение
        if collided_object != 0:
            if collided_object is player:
                total -= 10
                tank_move_sound.stop()
                boom_sound.play()
            elif collided_object is bot:
                total += 10
                tank_move_sound.stop()
                boom_sound.play()
            elif collided_object.destructible:
                self.destroy_tile(collided_object)

            # Прекращаем обновлять действия снаряда
            objects.remove(self)
            # Прекращаем отображения снаряда
            self.kill()


# Класс камеры
class Camera:
    # Зададим начальный сдвиг камеры
    def __init__(self):
        self.dx = 0
        self.dy = 0

    # Сдвинуть объект obj на смещение камеры
    def apply(self, obj):
        # Проверяем, что объект это игрок
        if obj is player or obj is bot:
            obj.x += self.dx
            obj.y += self.dy
        obj.rect.x += self.dx
        obj.rect.y += self.dy

    # Позиционировать камеру на объекте target
    def update(self, target):
        self.dx = -int(target.x + target.rect.w / 2 - width / 2)
        self.dy = -int(target.y + target.rect.h / 2 - height / 2)


# Класс кнопки
class Button:
    def __init__(self, width, height, inactive_color, active_color):
        self.width = width
        self.height = height
        self.inactive_color = inactive_color
        self.active_color = active_color

    def draw(self, x, y, message, x_r, action=None):
        global screen, start_menu, paused
        mouse = pygame.mouse.get_pos()
        cl = pygame.mouse.get_pressed()
        if x < mouse[0] < x + self.width and y < mouse[1] < y + self.height:
            pygame.draw.rect(screen, self.active_color, (x, y, self.width, self.height))
            if cl[0] == 1 and action:
                if action == 1:
                    start_menu = False
                    paused += 1
                if action == 2:
                    sys.exit()
        else:
            pygame.draw.rect(screen, self.inactive_color, (x, y, self.width, self.height))
        print_text(message, x + x_r, y + 20)


# Основной персонаж
player = None
# Группы спрайтов
all_sprites = pygame.sprite.Group()
tiles_group = pygame.sprite.Group()
player_group = pygame.sprite.Group()
wall_group = pygame.sprite.Group()
shell_group = pygame.sprite.Group()
stonewall_group = pygame.sprite.Group()
river_group = pygame.sprite.Group()
bot_group = pygame.sprite.Group()
paused = 0


# Функция создания уровней
def generate_level(level):
    new_player, x, y = None, None, None
    for y in range(len(level)):
        a = list()
        for x in range(len(level[y])):
            if level[y][x] == '.':
                tile = Empty(x, y)
            elif level[y][x] == '#':
                tile = Wall(x, y)
            elif level[y][x] == ':':
                tile = Stonewall(x, y)
            elif level[y][x] == '?':
                tile = River(x, y)
            elif level[y][x] == '@':
                tile = Empty(x, y)
                new_player = Player(x, y)
            elif level[y][x] == 'B':
                tile = Empty(x, y)
                bot = Bot(x, y)
            a.append(tile)
        tiles.append(a)
    # Вернем игрока, а также размер поля в клетках
    return new_player, bot, x, y


# Функция, отвечающая за переодическое обновление всех объектов на карте
def world_update():
    for i in objects:
        i.process()


# Функция для выведения текста
def print_text(message, x, y, font_color=(0, 0, 0), font_type=None, font_size=30):
    font_type = pygame.font.Font(font_type, font_size)
    text = font_type.render(message, True, font_color)
    screen.blit(text, (x, y))


# Основной игровой цикл
pygame.init()
clock = pygame.time.Clock()
player, bot, level_x, level_y = generate_level(load_level('map.txt'))
camera = Camera()


# Функция, проверяющая, играет ли какая-либо мелодия
def melody_check():
    return pygame.mixer.music.get_busy()


# Функция для показа меню
def show_menu():
    pygame.mouse.set_visible(1)
    bcgr = load_image("fon.png")
    global start_menu, running, event, paused
    paused += 1
    tank_move_sound.stop()
    load_music('PauseMusic.mp3')
    pygame.mixer.music.set_volume(0.3)
    pygame.mixer.music.play(-1)
    while start_menu:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                sys.exit()
        screen.blit(bcgr, (0, 0))
        if paused == 1:
            start_button.draw(175, 300, "Игра", 280, 1)
        else:
            start_button.draw(175, 300, "Продолжить", 262, 1)
        quit_button.draw(175, 500, "Выход", 280, 2)
        pygame.display.update()
        clock.tick(50)
    else:
        pygame.mixer.music.stop()
    pygame.mouse.set_visible(0)


start_menu = True
running = True
start_button = Button(600, 60, (190, 25, 25), (25, 25, 190))
quit_button = Button(600, 60, (190, 25, 25), (25, 25, 190))
size = width, height = 950, 950
screen = pygame.display.set_mode(size)
pygame.time.set_timer(GLOBAL_TIMER_EVENT, 1000 // FPS)
font = pygame.font.Font(None, 40)
total = 0
time_remaining = GAME_DURATION * FPS
show_menu()
load_music("Start.mp3")
pygame.mixer.music.set_volume(0.3)
pygame.mixer.music.play()
# Запускаем игровой цикл
while running:
    screen.fill((0, 0, 0))
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == GLOBAL_TIMER_EVENT:
            time_remaining -= 1
            time_remaining = max(0, time_remaining)
            world_update()
        # Проверяем, играет ли какая-либо мелодия
        if not melody_check():
            load_music('Melody.mp3')
            pygame.mixer.music.play(-1)
        if time_remaining > 0:
            player.update(event)
    all_sprites.draw(screen)
    player_group.draw(screen)
    bot_group.draw(screen)
    # Изменяем ракурс камеры
    camera.update(player)
    # Обновляем положение всех спрайтов
    for sprite in all_sprites:
        camera.apply(sprite)

    text = font.render("Счет: " + str(total), True, (255, 0, 0))
    screen.blit(text, (10, 10))
    text = font.render("Время: " + str(time_remaining // FPS) + " секунд", True, (255, 0, 0))
    screen.blit(text, (10, 35))
    if time_remaining == 0:
        pygame.time.set_timer(GLOBAL_TIMER_EVENT, 0)
        time_remaining = 0
        font2 = pygame.font.Font(None, 80)
        text = font2.render("Игра окончена", True, (255, 0, 0))
        screen.blit(text, (width // 2 - 200, height // 2 - 30))
    pygame.display.flip()
else:
    pygame.quit()