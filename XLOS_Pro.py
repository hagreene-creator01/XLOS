


"""
XLOS Pro — Single-file desktop simulator
Requirements: Python 3.x and pygame (pip install pygame)
No other dependencies.
Features:
 - First-run password setup + login
 - Desktop with draggable icons
 - Start menu, taskbar with clock
 - Window manager: drag, minimize, maximize, close, resize
 - Apps: Notes (autosave), Settings (theme/wallpaper), Sketch, Calculator,
   Snake (bounded to window), Tic-Tac-Toe
 - Power menu: Shutdown / Restart / Sleep
 - All games confined to their window content rect
 - No external assets, no sound
"""
import pygame, sys, os, time, json, random, math
from pygame.locals import *

pygame.init()
pygame.font.init()

# ---------- INPUT HANDLER FIX (prevents double typing) ----------
class InputManager:
    def __init__(self):
        self.keys_held = set()

    def handle_event(self, e):
        if e.type == pygame.KEYDOWN:
            if e.key not in self.keys_held:
                self.keys_held.add(e.key)
                return e.unicode
        elif e.type == pygame.KEYUP:
            if e.key in self.keys_held:
                self.keys_held.remove(e.key)
        return ""

# Instantiate once for all apps
input_manager = InputManager()


# ---------- CONFIG ----------
W, H = 1280, 720
TITLEBAR_H = 32
TASKBAR_H = 44
RESIZE_GRIP = 12
MIN_W, MIN_H = 220, 140
PASS_FILE = "xlos_pass.txt"
NOTES_FILE = "xlos_notes.txt"

FPS = 60
ICON_SIZE = 64  # size of desktop icons

# Themes / wallpapers (simple colors)
WALLPAPERS = [(18,22,36), (38,42,60), (255,204,0), (10,40,20), (60,10,30)]
THEMES = {"Dark": {"text": (235,240,245), "panel": (32,35,48), "alt": (40,44,60)},
          "Light": {"text": (20,20,20), "panel": (230,230,235), "alt": (245,245,248)}}

SETTINGS = {"theme": "Dark", "wallpaper_index": 0}


# ---------- PYGAME SETUP ----------
screen = pygame.display.set_mode((W, H), pygame.RESIZABLE)
pygame.display.set_caption("XLOS Pro")
clock = pygame.time.Clock()

# Fonts
FONT = pygame.font.SysFont("Segoe UI", 16)
FONT_MD = pygame.font.SysFont("Segoe UI", 18)
FONT_LG = pygame.font.SysFont("Segoe UI", 20)
MONO = pygame.font.SysFont("Consolas", 15)
FONT_SM = pygame.font.SysFont("segoeui", 13)
FONT_LARGE = pygame.font.SysFont("segoeui", 22)


# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY = (180, 180, 180)
RED = (200, 60, 60)
GREEN = (60, 200, 100)
BLUE = (60, 100, 200)

# Z-index for windows (keeps track of which window is on top)
window_z = []


# ---------- UTILITY FUNCTIONS ----------
def draw_text(surf, text, pos, font=FONT, color=None):
    if color is None:
        color = THEMES[SETTINGS["theme"]]["text"]
    surf.blit(font.render(str(text), True, color), pos)

def rounded_rect(surf, rect, color, radius=8):
    pygame.draw.rect(surf, color, rect, border_radius=radius)

def center_rect(w,h,sw,sh):
    return pygame.Rect((sw-w)//2, (sh-h)//2, w, h)

def load_password():
    if os.path.exists(PASS_FILE):
        try:
            with open(PASS_FILE, "r", encoding="utf-8") as f:
                return f.read().strip()
        except:
            return ""
    return ""

def save_password(pw):
    try:
        with open(PASS_FILE, "w", encoding="utf-8") as f:
            f.write(pw)
    except:
        pass

def read_notes():
    try:
        with open(NOTES_FILE, "r", encoding="utf-8") as f:
            return f.read()
    except:
        return ""

def save_notes(text):
    try:
        with open(NOTES_FILE, "w", encoding="utf-8") as f:
            f.write(text)
    except:
        pass



# ---------- Window Manager ----------
class Window:
    _seq = 0
    def __init__(self, app, title, rect):
        self.app = app  # App instance
        self.title = title
        self.rect = pygame.Rect(rect)
        self.minimized = False
        self.maximized = False
        self.dragging = False
        self.resizing = False
        self.drag_offset = (0,0)
        self._pre_max_rect = self.rect.copy()
        self.z = Window._seq; Window._seq += 1

    def titlebar_rect(self):
        return pygame.Rect(self.rect.x, self.rect.y, self.rect.w, TITLEBAR_H)

    def content_rect(self):
        r = self.rect.copy(); r.y += TITLEBAR_H; r.h -= TITLEBAR_H; return r

    def grip_rect(self):
        return pygame.Rect(self.rect.right-RESIZE_GRIP, self.rect.bottom-RESIZE_GRIP, RESIZE_GRIP, RESIZE_GRIP)

    def handle_event(self, e):
        if self.minimized: return
        if e.type == MOUSEBUTTONDOWN and e.button == 1:
            if self.titlebar_rect().collidepoint(e.pos):
                # check title buttons
                btn = self._hit_title_buttons(e.pos)
                if btn:
                    return btn
                # start dragging
                self.dragging = True
                self.drag_offset = (e.pos[0] - self.rect.x, e.pos[1] - self.rect.y)
            elif self.grip_rect().collidepoint(e.pos):
                self.resizing = True
        elif e.type == MOUSEBUTTONUP and e.button == 1:
            self.dragging = False; self.resizing = False
        elif e.type == MOUSEMOTION:
            if self.dragging:
                nx = e.pos[0] - self.drag_offset[0]; ny = e.pos[1] - self.drag_offset[1]
                sw, sh = screen.get_size()
                # keep on-screen reasonably
                nx = max(-self.rect.w+60, min(nx, sw-60))
                ny = max(0, min(ny, sh-TASKBAR_H-TITLEBAR_H))
                self.rect.x = int(nx); self.rect.y = int(ny)
            if self.resizing:
                nx = max(MIN_W, int(e.pos[0] - self.rect.x))
                ny = max(MIN_H, int(e.pos[1] - self.rect.y))
                sw, sh = screen.get_size()
                nx = min(nx, sw - self.rect.x - 10)
                ny = min(ny, sh - TASKBAR_H - self.rect.y - 10)
                self.rect.w = nx; self.rect.h = ny
        # forward to app
        if not self.minimized:
            self.app.handle_event(e, self.content_rect())

    def draw(self, surf):
        if self.minimized: return
        # shadow
        shad = self.rect.inflate(12,12)
        s = pygame.Surface((shad.w, shad.h), pygame.SRCALPHA)
        pygame.draw.rect(s, (0,0,0,100), s.get_rect(), border_radius=12)
        surf.blit(s, shad.topleft)
        # frame
        rounded_rect(surf, self.rect, THEMES[SETTINGS["theme"]]["panel"])
        # titlebar
        t = self.titlebar_rect()
        rounded_rect(surf, t, THEMES[SETTINGS["theme"]]["alt"])
        draw_text(surf, self.title, (t.x+10, t.y+6), FONT_MD)
        # title buttons
        bx = t.right - 28
        self._btns = []
        for label in ['x','□','–']:
            r = pygame.Rect(bx, t.y+6, 22, 18)
            rounded_rect(surf, r, THEMES[SETTINGS["theme"]]["panel"])
            draw_text(surf, label, (r.x+6, r.y-2), FONT_MD)
            self._btns.append((label, r))
            bx -= 26
        # content panel
        content = self.content_rect()
        rounded_rect(surf, content, THEMES[SETTINGS["theme"]]["alt"])
        # draw app content inside
        self.app.draw(surf, content)
        # resize grip visual
        pygame.draw.polygon(surf, (120,120,120), [(self.rect.right-RESIZE_GRIP+2, self.rect.bottom-2), (self.rect.right-2, self.rect.bottom-2), (self.rect.right-2, self.rect.bottom-RESIZE_GRIP+2)])

    def _hit_title_buttons(self, pos):
        for label, r in self._btns:
            if r.collidepoint(pos):
                return label
        return None

# ---------- Apps ----------
class BaseApp:
    name = "App"
    def handle_event(self, e, rect): pass
    def draw(self, surf, rect): pass

# ---------- Notes App ----------
class NotesApp(BaseApp):
    name = "Notes"
    def __init__(self):
        self.text = read_notes()
        self.cursor = len(self.text)
        self.last_save = time.time()

    def handle_event(self, e, rect):
        char = input_manager.handle_event(e)
        if e.type == pygame.KEYDOWN:
            if e.key == pygame.K_s and (pygame.key.get_mods() & pygame.KMOD_CTRL):
                save_notes(self.text)
                self.last_save = time.time()
            elif e.key == pygame.K_BACKSPACE:
                if self.cursor > 0:
                    self.text = self.text[:self.cursor-1] + self.text[self.cursor:]
                    self.cursor -= 1
            elif e.key == pygame.K_RETURN:
                self.text = self.text[:self.cursor] + "\n" + self.text[self.cursor:]
                self.cursor += 1
            elif e.key == pygame.K_LEFT:
                self.cursor = max(0, self.cursor-1)
            elif e.key == pygame.K_RIGHT:
                self.cursor = min(len(self.text), self.cursor+1)
            elif char:
                self.text = self.text[:self.cursor] + char + self.text[self.cursor:]
                self.cursor += 1

        # autosave
        if time.time() - self.last_save > 3.0:
            save_notes(self.text)
            self.last_save = time.time()

    def draw(self, surf, rect):
        rounded_rect(surf, rect, THEMES[SETTINGS["theme"]]["panel"])
        pad = 8
        area = rect.inflate(-pad*2, -pad*2)
        y = area.y
        lh = MONO.get_height() + 4
        lines = self.text.split("\n") if self.text else [""]
        for line in lines:
            draw_text(surf, line, (area.x+4, y), MONO, THEMES[SETTINGS["theme"]]["text"])
            y += lh
            if y > area.bottom: break
        draw_text(surf, "Notes — Ctrl+S to save", (rect.right-160, rect.bottom-22), FONT_SM, (160,160,160))

# ---------- Sketch App ----------
class SketchApp(BaseApp):
    name = "Sketch"
    def __init__(self):
        self.lines = []
        self.drawing = False
        self.color = BLUE
        self.current_pos = (0,0)

    def handle_event(self, e, rect):
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            if rect.collidepoint(e.pos):
                self.drawing = True
                self.current_pos = e.pos
        elif e.type == pygame.MOUSEBUTTONUP and e.button == 1:
            self.drawing = False
        elif e.type == pygame.MOUSEMOTION and self.drawing:
            self.lines.append((self.current_pos, e.pos))
            self.current_pos = e.pos

        # keyboard shortcuts for color change
        char = input_manager.handle_event(e)
        if char:
            if char.lower() == "r":
                self.color = RED
            elif char.lower() == "g":
                self.color = GREEN
            elif char.lower() == "b":
                self.color = BLUE

    def draw(self, surf, rect):
        rounded_rect(surf, rect, THEMES[SETTINGS["theme"]]["panel"])
        for start, end in self.lines:
            pygame.draw.line(surf, self.color, start, end, 2)
        draw_text(surf, "Sketch — Press R/G/B to change color", (rect.x+10, rect.bottom-22), FONT_SM, (160,160,160))



# ---------- Settings App ----------
class SettingsApp(BaseApp):
    name = "Settings"
    def __init__(self):
        self.theme = SETTINGS["theme"]
        self.wall = SETTINGS["wallpaper_index"]

    def handle_event(self, e, rect):
        if e.type == pygame.KEYDOWN:
            if e.key == pygame.K_t:
                self.theme = "Light" if self.theme=="Dark" else "Dark"
            elif e.key == pygame.K_LEFT:
                self.wall = (self.wall - 1) % len(WALLPAPERS)
            elif e.key == pygame.K_RIGHT:
                self.wall = (self.wall + 1) % len(WALLPAPERS)
            elif e.key == pygame.K_RETURN:
                SETTINGS["theme"] = self.theme
                SETTINGS["wallpaper_index"] = self.wall

    def draw(self, surf, rect):
        rounded_rect(surf, rect, THEMES[SETTINGS["theme"]]["panel"])
        p = rect.inflate(-12,-12)
        draw_text(surf, "Settings", (p.x+8, p.y+8), FONT_LG)
        draw_text(surf, f"Theme (T): {self.theme}", (p.x+8, p.y+56), FONT_SM)
        draw_text(surf, f"Wallpaper ←/→ : {self.wall}", (p.x+8, p.y+84), FONT_SM)
        draw_text(surf, "Enter to apply", (p.x+8, p.y+p.h-28), FONT_SM, (150,150,150))




# ---------- Calculator App ----------





import pygame



import pygame


import pygame

class Calculator:
    name = "Calculator"
    WIDTH = 300
    HEIGHT = 400
    BUTTON_SIZE = 50
    title_bar_height = 30

    def __init__(self):
        self.current_input = ""   # currently typed
        self.result = ""          # last result
        self.font = pygame.font.SysFont(None, 30)
        self.buttons = [
            ["7","8","9","/"],
            ["4","5","6","*"],
            ["1","2","3","-"],
            ["0",".","=","+"]
        ]
        self.clicked = False
        self.dragging = False
        self.offset_x = 0
        self.offset_y = 0

    def handle_event(self, event, rect=None):
        area = rect if rect else pygame.Rect(0, 0, self.WIDTH, self.HEIGHT)
        mx, my = None, None

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and not self.clicked:
            mx, my = event.pos
            # Check title bar drag
            if area.collidepoint(mx, my) and my - area.y <= self.title_bar_height:
                self.dragging = True
                self.offset_x = mx - area.x
                self.offset_y = my - area.y
            else:
                # Check buttons
                for row_idx, row in enumerate(self.buttons):
                    for col_idx, label in enumerate(row):
                        bx = area.x + 10 + col_idx * (self.BUTTON_SIZE + 10)
                        by = area.y + 100 + row_idx * (self.BUTTON_SIZE + 10)
                        b_rect = pygame.Rect(bx, by, self.BUTTON_SIZE, self.BUTTON_SIZE)
                        if b_rect.collidepoint(mx, my):
                            self.on_button_click(label)
            self.clicked = True

        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.clicked = False
            self.dragging = False

        elif event.type == pygame.MOUSEMOTION and self.dragging:
            mx, my = event.pos
            area.x = mx - self.offset_x
            area.y = my - self.offset_y

    def on_button_click(self, label):
        if label == "=":
            try:
                self.result = str(eval(self.current_input))
                self.current_input = self.result
            except:
                self.result = "Error"
                self.current_input = ""
        else:
            self.current_input += label

    def draw(self, surf, rect=None):
        area = rect if rect else pygame.Rect(0, 0, self.WIDTH, self.HEIGHT)
        # Background
        pygame.draw.rect(surf, (50,50,50), area)
        # Title bar
        pygame.draw.rect(surf, (30,30,30), (area.x, area.y, self.WIDTH, self.title_bar_height))
        title_surf = self.font.render(self.name, True, (255,255,255))
        surf.blit(title_surf, (area.x+5, area.y+5))
        # Display
        display_rect = pygame.Rect(area.x+10, area.y+40, self.WIDTH-20, 50)
        pygame.draw.rect(surf, (0,0,0), display_rect)
        text_surf = self.font.render(self.current_input, True, (255,255,255))
        surf.blit(text_surf, (display_rect.x+5, display_rect.y+5))
        # Buttons
        for row_idx, row in enumerate(self.buttons):
            for col_idx, label in enumerate(row):
                bx = area.x + 10 + col_idx * (self.BUTTON_SIZE + 10)
                by = area.y + 100 + row_idx * (self.BUTTON_SIZE + 10)
                b_rect = pygame.Rect(bx, by, self.BUTTON_SIZE, self.BUTTON_SIZE)
                pygame.draw.rect(surf, (70,70,70), b_rect)
                pygame.draw.rect(surf, (200,200,200), b_rect, 2)
                label_surf = self.font.render(label, True, (255,255,255))
                surf.blit(label_surf, (bx + 15, by + 10))








# ---------- Snake App ----------
class SnakeApp(BaseApp):
    name = "Snake"
    def __init__(self):
        self.cell = 18
        self.reset()

    def reset(self):
        self.snake = [(5,5),(4,5),(3,5)]
        self.dir = (1,0)
        self.food = (10,8)
        self.last = time.time()
        self.speed = 0.12
        self.alive = True
        self.score = 0

    def handle_event(self, e, rect):
        if e.type == pygame.KEYDOWN:
            if e.key == pygame.K_UP and self.dir != (0,1): self.dir = (0,-1)
            if e.key == pygame.K_DOWN and self.dir != (0,-1): self.dir = (0,1)
            if e.key == pygame.K_LEFT and self.dir != (1,0): self.dir = (-1,0)
            if e.key == pygame.K_RIGHT and self.dir != (-1,0): self.dir = (1,0)
            if e.key == pygame.K_r: self.reset()

    def update(self, rect):
        if not self.alive: return
        if time.time() - self.last < self.speed: return
        self.last = time.time()
        cols = max(3, rect.w // self.cell)
        rows = max(3, rect.h // self.cell)
        head = (self.snake[0][0] + self.dir[0], self.snake[0][1] + self.dir[1])
        # boundaries inside window only
        if head[0] < 0 or head[1] < 0 or head[0] >= cols or head[1] >= rows or head in self.snake:
            self.alive = False
            return
        self.snake.insert(0, head)
        if head == self.food:
            self.score += 1
            free = [(x,y) for x in range(cols) for y in range(rows) if (x,y) not in self.snake]
            self.food = random.choice(free) if free else (0,0)
        else:
            self.snake.pop()

    def draw(self, surf, rect):
        rounded_rect(surf, rect, THEMES[SETTINGS["theme"]]["panel"])
        content = rect.inflate(-6,-6)
        self.update(content)
        for i,seg in enumerate(self.snake):
            pygame.draw.rect(surf, (0,180,0), (content.x + seg[0]*self.cell, content.y + seg[1]*self.cell, self.cell-1, self.cell-1))
        fx,fy = self.food
        pygame.draw.rect(surf, (220,50,50), (content.x + fx*self.cell, content.y + fy*self.cell, self.cell-1, self.cell-1))
        draw_text(surf, f"Score: {self.score}  (Arrows) R reset", (rect.x+8, rect.y+6), FONT_SM, (150,150,150))

# ---------- TicTacToe App ----------
class TTTApp(BaseApp):
    name = "TicTacToe"
    def __init__(self):
        self.board = [""]*9
        self.turn = "X"
        self.stats = {"X":0,"O":0,"Draw":0}

    def handle_event(self, e, rect):
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 and rect.collidepoint(e.pos):
            size = min(rect.w, rect.h) - 36
            cell = size // 3
            ox = rect.x + (rect.w - size)//2
            oy = rect.y + (rect.h - size)//2
            x,y = e.pos
            gx = (x - ox) // cell
            gy = (y - oy) // cell
            if 0 <= gx < 3 and 0 <= gy < 3:
                idx = int(gy*3 + gx)
                if self.board[idx] == "":
                    self.board[idx] = self.turn
                    if self._check(self.turn):
                        self.stats[self.turn] += 1
                        self._reset()
                    elif all(self.board):
                        self.stats["Draw"] += 1
                        self._reset()
                    else:
                        self.turn = "O" if self.turn == "X" else "X"
        if e.type == pygame.KEYDOWN and e.key == pygame.K_r:
            self._reset()

    def _check(self,p):
        wins = [(0,1,2),(3,4,5),(6,7,8),(0,3,6),(1,4,7),(2,5,8),(0,4,8),(2,4,6)]
        for a,b,c in wins:
            if self.board[a]==p and self.board[b]==p and self.board[c]==p:
                return True
        return False

    def _reset(self):
        self.board = [""]*9
        self.turn = "X"

    def draw(self, surf, rect):
        rounded_rect(surf, rect, THEMES[SETTINGS["theme"]]["panel"])
        draw_text(surf, f"TicTacToe — Turn {self.turn} (R reset)", (rect.x+8, rect.y+8), FONT_SM, (160,160,160))
        size = min(rect.w, rect.h) - 36
        cell = size // 3
        ox = rect.x + (rect.w - size)//2
        oy = rect.y + (rect.h - size)//2
        for i in range(4):
            pygame.draw.line(surf, (120,120,120), (ox + i*cell, oy), (ox + i*cell, oy + 3*cell), 2)
            pygame.draw.line(surf, (120,120,120), (ox, oy + i*cell), (ox + 3*cell, oy + i*cell), 2)
        for idx, v in enumerate(self.board):
            gx = idx % 3
            gy = idx // 3
            cr = pygame.Rect(ox + gx*cell, oy + gy*cell, cell, cell)
            if v == "X":
                pygame.draw.line(surf, (0,160,255), cr.topleft, cr.bottomright, 4)
                pygame.draw.line(surf, (0,160,255), cr.topright, cr.bottomleft, 4)
            elif v == "O":
                pygame.draw.circle(surf, (60,200,80), cr.center, cell//2 - 8, 4)






# ---------- Finder App ----------





import pygame
import json
import os

class Finder(BaseApp):
    name = "Finder"

    def __init__(self):
        super().__init__()
        self.notes_file = "memory.json"
        self.notes = self.load_notes()
        self.selected_note = None
        self.font = pygame.font.SysFont(None, 24)
        self.new_note_rect = pygame.Rect(20, 20, 120, 40)
        self.search_text = ""
        self.search_rect = pygame.Rect(160, 20, 200, 40)

    # ------------------ Load / Save Notes ------------------
    def load_notes(self):
        if os.path.exists(self.notes_file):
            with open(self.notes_file, "r") as f:
                raw_notes = json.load(f)
            for k, v in raw_notes.items():
                if isinstance(v, list):
                    raw_notes[k] = "\n".join(v)
                else:
                    raw_notes[k] = str(v)
            return raw_notes
        return {}

    def save_notes(self):
        with open(self.notes_file, "w") as f:
            json.dump(self.notes, f)

    # ------------------ Event Handling ------------------
    def handle_event(self, e, content_rect):
        if e.type == pygame.MOUSEBUTTONDOWN:
            if self.new_note_rect.collidepoint(e.pos):
                title = f"New Note {len(self.notes)+1}"
                self.notes[title] = ""
                self.selected_note = title
                self.save_notes()
            elif self.search_rect.collidepoint(e.pos):
                # focus search box if you implement text input focus
                pass
            else:
                y = content_rect.top
                for note_title in self.notes.keys():
                    note_rect = pygame.Rect(content_rect.left, y, content_rect.width, 30)
                    if note_rect.collidepoint(e.pos):
                        self.selected_note = note_title
                        break
                    y += 35

        elif e.type == pygame.KEYDOWN:
            if self.selected_note:
                content = self.notes[self.selected_note]
                if e.key == pygame.K_BACKSPACE:
                    content = content[:-1]
                elif e.key == pygame.K_RETURN:
                    content += "\n"
                else:
                    content += e.unicode
                self.notes[self.selected_note] = content
                self.save_notes()
            else:
                # optional: type in search
                if e.key == pygame.K_BACKSPACE:
                    self.search_text = self.search_text[:-1]
                elif e.key != pygame.K_RETURN:
                    self.search_text += e.unicode

    # ------------------ Draw ------------------
    def draw(self, surf, content_rect):
        # Draw top buttons
        pygame.draw.rect(surf, (180, 250, 180), self.new_note_rect)
        new_note_label = self.font.render("New Note", True, (0, 0, 0))
        surf.blit(new_note_label, (self.new_note_rect.left + 5, self.new_note_rect.top + 10))

        pygame.draw.rect(surf, (220, 220, 220), self.search_rect)
        search_label = self.font.render(self.search_text if self.search_text else "Search...", True, (0,0,0))
        surf.blit(search_label, (self.search_rect.left + 5, self.search_rect.top + 10))

        # Draw list of notes
        y = content_rect.top
        for note_title in self.notes.keys():
            if self.search_text.lower() in note_title.lower():
                note_rect = pygame.Rect(content_rect.left, y, content_rect.width, 30)
                pygame.draw.rect(surf, (200, 200, 255) if note_title == self.selected_note else (220,220,220), note_rect)
                note_label = self.font.render(note_title, True, (0,0,0))
                surf.blit(note_label, (note_rect.left + 5, note_rect.top + 5))
                y += 35

        # Draw editing area for selected note
        if self.selected_note:
            edit_rect = pygame.Rect(content_rect.left, content_rect.top + 200, content_rect.width, content_rect.height - 200)
            pygame.draw.rect(surf, (255, 255, 255), edit_rect)
            pygame.draw.rect(surf, (0,0,0), edit_rect, 2)  # border
            lines = self.notes[self.selected_note].split("\n")
            y_content = edit_rect.top + 5
            for line in lines:
                line_surf = self.font.render(line, True, (0,0,0))
                surf.blit(line_surf, (edit_rect.left + 5, y_content))
                y_content += 25




# ------------------------- xl_drift_adventure_app.py -------------------------

import pygame, math, random, time
from pygame.locals import *

class XLDriftApp:
    name = "XL DRIFT"

    def __init__(self):
        self.screen_rect = pygame.Rect(0, 0, 520, 360)  # default window size
        self.track_color = (50, 50, 50)
        self.track_rects = [pygame.Rect(200,100,880,520)]
        self.car = self.Car(self.screen_rect.centerx, self.screen_rect.centery)
        self.drift_score = 0
        self.font = pygame.font.SysFont(None, 24)

    class Car:
        def __init__(self, x, y):
            self.width, self.height = 100, 50
            self.image = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            pygame.draw.rect(self.image, (200, 50, 50), (0, 0, self.width, self.height))
            self.orig_image = self.image.copy()
            self.rect = self.image.get_rect(center=(x, y))
            self.x, self.y = x, y
            self.angle = 0
            self.speed = 0
            self.max_speed = 8
            self.acceleration = 0.2
            self.friction = 0.05
            self.turn_speed = 3
            self.drift_factor = 0.95

        def update(self, keys):
            if keys[K_UP]: self.speed += self.acceleration
            elif keys[K_DOWN]: self.speed -= self.acceleration
            else: self.speed *= (1 - self.friction)
            self.speed = max(min(self.speed, self.max_speed), -self.max_speed/2)
            if keys[K_LEFT]: self.angle += self.turn_speed * (self.speed/self.max_speed)
            if keys[K_RIGHT]: self.angle -= self.turn_speed * (self.speed/self.max_speed)
            rad = math.radians(self.angle)
            self.x += -self.speed * math.sin(rad) * self.drift_factor
            self.y += -self.speed * math.cos(rad)
            self.rect.center = (self.x, self.y)
            self.image = pygame.transform.rotate(self.orig_image, self.angle)

    def handle_event(self, e, rect):
        pass  # handled by main window

    def draw(self, surf, rect):
        # create a sub-surface to constrain the game inside the window
        game_surf = pygame.Surface((rect.w, rect.h))
        game_surf.fill(self.track_color)
        for r in self.track_rects:
            # adjust rect for surface coordinates
            track_r = r.copy()
            track_r.x -= rect.x
            track_r.y -= rect.y
            pygame.draw.rect(game_surf, (255, 255, 0), track_r)

        keys = pygame.key.get_pressed()
        self.car.update(keys)

        # check if car is off the track
        car_point = (int(self.car.x - rect.x), int(self.car.y - rect.y))
        on_track = any(r.collidepoint(car_point) for r in [pygame.Rect(t.x-rect.x, t.y-rect.y, t.w, t.h) for t in self.track_rects])
        if not on_track:
            self.car.speed = 0

        # drift score
        if keys[K_LEFT] or keys[K_RIGHT]:
            self.drift_score += abs(self.car.speed * 0.1)

        # draw car
        car_pos = (self.car.rect.x - rect.x, self.car.rect.y - rect.y)
        game_surf.blit(self.car.image, car_pos)

        # draw drift score
        score_surf = self.font.render(f"Drift Score: {int(self.drift_score)}", True, (255,255,255))
        game_surf.blit(score_surf, (10, 10))

        surf.blit(game_surf, rect.topleft)



        
# ----------------- Chat App -----------------



 # ---------- ChatApp ----------




# ---------- ChatApp ----------
class ChatApp:
    name = "ChatApp"

    def __init__(self):
        self.messages = []  # stores chat messages
        self.input_text = ""  # current typed text
        self.font = FONT_SM
        self.fake_response = "I’m just a robot, lol!"  # always respond with this

    def handle_event(self, e, rect):
        if e.type == pygame.KEYDOWN:
            if e.key == pygame.K_BACKSPACE:
                self.input_text = self.input_text[:-1]
            elif e.key == pygame.K_RETURN:
                if self.input_text.strip():
                    # append user message
                    self.messages.append(("You", self.input_text.strip()))
                    self.input_text = ""
                    # append bot response
                    self.messages.append(("Bot", self.fake_response))
            else:
                self.input_text += e.unicode

    def update(self):
        pass  # nothing dynamic for now

    def draw(self, surf, rect):
        # background
        pygame.draw.rect(surf, (30, 30, 30), rect)
        pygame.draw.rect(surf, (60, 60, 60), rect, 2)  # border

        # draw messages (show last 10)
        y = rect.y + 10
        for sender, msg in self.messages[-10:]:
            draw_text(surf, f"{sender}: {msg}", (rect.x + 10, y), self.font, color=(255,255,255))
            y += 20

        # draw input box
        pygame.draw.rect(surf, (50, 50, 50), (rect.x + 10, rect.bottom - 35, rect.width - 20, 25))
        draw_text(surf, self.input_text, (rect.x + 12, rect.bottom - 33), self.font, color=(255,255,255))


        


# ---------- App registry ----------
APP_MAP = {
    "Notes": NotesApp,
    "Sketch": SketchApp,
    "Settings": SettingsApp,
    "Calculator": Calculator,
    "Snake": SnakeApp,
    "TicTacToe": TTTApp,
    "Finder" : Finder,
    "XL DRIFT" : XLDriftApp,
    "ChatApp": ChatApp,

}

# ---------- Desktop / Start / Taskbar / Power ----------
class Desktop:
    def __init__(self):
        self.icons = []
        self.windows = []
        self.start_open = False
        self.menu_rect = pygame.Rect(8, H - 340 - TASKBAR_H, 260, 340)
        # create icons grid
        padx, pady = 24, 24
        x0, y0 = 24, 24
        icons = ["Notes","Sketch","Settings","Calculator","Snake","TicTacToe","Finder","XL DRIFT","ChatApp"]
        for i, name in enumerate(icons):
            x = x0 + (i%2)*(ICON_SIZE+padx); y = y0 + (i//2)*(ICON_SIZE+pady)
            self.icons.append({"name": name, "rect": pygame.Rect(x, y, ICON_SIZE, ICON_SIZE)})
        self.power_open = False
        self.sleeping = False
        # spawn a welcome Notes window
        self.spawn_window("Notes", size=(540,420))

    def spawn_window(self, app_name, size=(520,360)):
        sw, sh = screen.get_size()
        x = 180 + len(self.windows)*16
        y = 120 + len(self.windows)*12
        rect = (x, y, max(MIN_W, size[0]), max(MIN_H, size[1]))
        app_inst = APP_MAP[app_name]() if callable(APP_MAP[app_name]) else APP_MAP[app_name]()
        w = Window(app_inst, app_inst.name, rect)
        self.windows.append(w)
        self.focus(w)
        return w

    def focus(self, win):
        if self.windows and self.windows[-1] is not win:
            self.windows.remove(win); self.windows.append(win)

    def close(self, win):
        if win in self.windows: self.windows.remove(win)

    def draw_wallpaper(self, surf):
        surf.fill(WALLPAPERS[SETTINGS["wallpaper_index"] % len(WALLPAPERS)])
        if SETTINGS["theme"] == "Dark":
            vg = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
            pygame.draw.rect(vg, (0,0,0,70), vg.get_rect()); surf.blit(vg,(0,0))
        else:
            vg = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
            pygame.draw.rect(vg, (255,255,255,40), vg.get_rect()); surf.blit(vg,(0,0))

    def draw_desktop(self, surf):
        for ico in self.icons:
            rounded_rect(surf, ico["rect"], THEMES[SETTINGS["theme"]]["alt"])
            draw_text(surf, ico["name"], (ico["rect"].x-6, ico["rect"].y+ICON_SIZE+6), FONT_SM)








    def draw_taskbar(self, surf):
        w,h = surf.get_size()
        bar = pygame.Rect(0, h-TASKBAR_H, w, TASKBAR_H)
        rounded_rect(surf, bar, THEMES[SETTINGS["theme"]]["alt"], radius=0)
        # start button
        self.start_btn = pygame.Rect(8, h-TASKBAR_H+6, 120, TASKBAR_H-12)
        rounded_rect(surf, self.start_btn, THEMES[SETTINGS["theme"]]["panel"], radius=8)
        draw_text(surf, "Start", (self.start_btn.x+48, self.start_btn.y+6), FONT_MD)
        # task buttons
        x = self.start_btn.right + 8; y = h - TASKBAR_H + 6
        self.task_buttons = []
        for win in self.windows:
            btn = pygame.Rect(x, y, 160, TASKBAR_H-8)
            rounded_rect(surf, btn, THEMES[SETTINGS["theme"]]["panel"], radius=8)
            draw_text(surf, win.title[:18], (btn.x+8, btn.y+8), FONT_SM)
            self.task_buttons.append((btn, win)); x += btn.w + 6
        # clock
        draw_text(surf, time.strftime("%H:%M:%S"), (w-110, h-TASKBAR_H+12), FONT_MD)

    def draw_start_menu(self, surf):
        if not self.start_open: return
        w,h = surf.get_size(); self.menu_rect.bottomleft = (10, h-TASKBAR_H-6)
        rounded_rect(surf, self.menu_rect, THEMES[SETTINGS["theme"]]["panel"])
        draw_text(surf, "XLOS Pro", (self.menu_rect.x+16, self.menu_rect.y+12), FONT_LG)
        y = self.menu_rect.y + 58; self.menu_items = []
        for name in APP_MAP.keys():
            r = pygame.Rect(self.menu_rect.x+12, y, self.menu_rect.w-24, 36)
            rounded_rect(surf, r, THEMES[SETTINGS["theme"]]["alt"])
            draw_text(surf, name, (r.x+12, r.y+8), FONT_SM)
            self.menu_items.append((r, name)); y += 44
        # power button
        pb = pygame.Rect(self.menu_rect.x+12, self.menu_rect.bottom-64, self.menu_rect.w-24, 44)
        rounded_rect(surf, pb, (180,40,40), radius=8); draw_text(surf, "Power", (pb.x+14, pb.y+10), FONT_MD)
        self.power_btn = pb

    def draw_power_dialog(self, surf):
        if not self.power_open: return
        self.power_rect = pygame.Rect(0,0,420,180); self.power_rect.center = (W//2, H//2)
        rounded_rect(surf, self.power_rect, THEMES[SETTINGS["theme"]]["panel"])
        draw_text(surf, "Power", (self.power_rect.x+18, self.power_rect.y+12), FONT_LG)
        labels = [("Shutdown","shutdown"), ("Restart","restart"), ("Sleep","sleep"), ("Cancel","cancel")]
        bx = self.power_rect.x + 24; by = self.power_rect.y + 64; w = 92; h = 40
        for i,(lab,cmd) in enumerate(labels):
            r = pygame.Rect(bx + i*(w+12), by, w, h)
            rounded_rect(surf, r, THEMES[SETTINGS["theme"]]["alt"], radius=8)
            draw_text(surf, lab, (r.x+10, r.y+10), FONT_SM)

    def draw(self, surf):
        if self.sleeping:
            surf.fill((6,6,8))
            draw_text(surf, "Sleeping — press any key/click to wake", (W//2-220, H//2), FONT_LG, (160,160,160))
            return
        self.draw_wallpaper(surf)
        self.draw_desktop(surf)
        for win in self.windows: win.draw(surf)
        self.draw_taskbar(surf)
        self.draw_start_menu(surf)
        self.draw_power_dialog(surf)

    def handle_event(self, e):
        if self.sleeping:
            if e.type in (MOUSEBUTTONDOWN, KEYDOWN):
                self.sleeping = False
            return
        mouse = pygame.mouse.get_pos()
        if e.type == MOUSEBUTTONDOWN and e.button == 1:
            # Start button
            if hasattr(self, "start_btn") and self.start_btn.collidepoint(mouse):
                self.start_open = not self.start_open; return
            # Click in start menu
            if self.start_open:
                for r, name in getattr(self, "menu_items", []):
                    if r.collidepoint(mouse):
                        self.spawn_window(name); self.start_open = False; return
                if hasattr(self, "power_btn") and self.power_btn.collidepoint(mouse):
                    self.power_open = True; self.start_open = False; return
                if not self.menu_rect.collidepoint(mouse) and not self.start_btn.collidepoint(mouse):
                    self.start_open = False
            # Desktop icons double-click / drag
            for ico in self.icons:
                if ico["rect"].collidepoint(mouse):
                    now = time.time()
                    if ico.get("last_click", 0) and now - ico["last_click"] < 0.35:
                        # double click: open
                        self.spawn_window(ico["name"]); ico["last_click"] = 0; return
                    else:
                        ico["last_click"] = now
                        ico["dragging"] = True; ico["off"] = (mouse[0]-ico["rect"].x, mouse[1]-ico["rect"].y)
                        self._drag_icon = ico; return
            # taskbar buttons
            for btn, win in getattr(self, "task_buttons", []):
                if btn.collidepoint(mouse):
                    if win.minimized:
                        win.minimized = False; self.focus(win)
                    else:
                        top = self.windows[-1] if self.windows else None
                        if top is win: win.minimized = True
                        else: self.focus(win)
                    return
            # windows top-down
            for win in reversed(self.windows):
                if win.minimized: continue
                if win.rect.collidepoint(mouse):
                    # title buttons
                    if win.titlebar_rect().collidepoint(mouse):
                        action = win._hit_title_buttons(mouse)
                        if action == 'x':
                            self.close(win); return
                        elif action == '–':
                            win.minimized = True; return
                        elif action == '□':
                            if not win.maximized:
                                win._pre_max_rect = win.rect.copy()
                                sw, sh = screen.get_size()
                                win.rect = pygame.Rect(8, 8, sw-16, sh-TASKBAR_H-16); win.maximized = True
                            else:
                                win.rect = win._pre_max_rect; win.maximized = False
                            self.focus(win); return
                    self.focus(win)
                    # forward event to window (drag/resize handled in Window.handle_event)
                    break
        # power dialog actions
        if self.power_open:
            if e.type == MOUSEBUTTONDOWN and e.button == 1:
                mx,my = e.pos
                bx = self.power_rect.x + 24; by = self.power_rect.y + 64; w = 92; h = 40
                labels = [("Shutdown","shutdown"), ("Restart","restart"), ("Sleep","sleep"), ("Cancel","cancel")]
                for i,(_,cmd) in enumerate(labels):
                    r = pygame.Rect(bx + i*(w+12), by, w, h)
                    if r.collidepoint((mx,my)):
                        self.power_open = False
                        if cmd == "shutdown":
                            pygame.quit(); sys.exit()
                        elif cmd == "restart":
                            # restart: clear windows and respawn welcome
                            self.windows.clear(); self.spawn_window("Notes", size=(540,420)); return
                        elif cmd == "sleep":
                            for w in self.windows: w.minimized = True
                            self.sleeping = True; return
                        elif cmd == "cancel":
                            return
        # forward to focused window
        for win in reversed(self.windows):
            if not win.minimized and win.rect.collidepoint(mouse):
                win.handle_event(e)
                break
        # global keys
        if e.type == KEYDOWN:
            if e.key == K_ESCAPE:
                if self.start_open: self.start_open = False
            if e.key == K_TAB and (pygame.key.get_mods() & KMOD_ALT):
                if self.windows:
                    w = self.windows.pop(0); self.windows.append(w)

# ---------- Create Desktop ----------
desktop = Desktop()

# ---------- Main loop ----------
# Password / Login
password = load_password()
first_run = (password == "")
login_password = ""
login_prompt = "Set a password (Enter to save):" if first_run else "Enter password:"

logged_in = False
while not logged_in:
    screen.fill((20,24,32))
    draw_text(screen, login_prompt, (W//2-180, H//2-40), FONT_LG)
    draw_text(screen, "*"*len(login_password), (W//2-80, H//2), FONT_LG)
    for ev in pygame.event.get():
        if ev.type == QUIT:
            pygame.quit(); sys.exit()
        if ev.type == KEYDOWN:
            if ev.key == K_BACKSPACE:
                login_password = login_password[:-1]
            elif ev.key == K_RETURN:
                if first_run:
                    save_password(login_password)
                    password = login_password; first_run = False; login_prompt = "Enter password:"
                    login_password = ""
                else:
                    if login_password == password:
                        logged_in = True
                    else:
                        login_password = ""
                        login_prompt = "Wrong password — try again:"
            else:
                if ev.unicode:
                    login_password += ev.unicode
    pygame.display.flip()
    clock.tick(30)

# Main event loop
drag_icon = None
icon_drag_off = (0,0)

running = True
while running:
    dt = clock.tick(FPS) / 1000.0
    for ev in pygame.event.get():
        if ev.type == QUIT:
            running = False
        elif ev.type == VIDEORESIZE:
            screen = pygame.display.set_mode((ev.w, ev.h), pygame.RESIZABLE)
        else:
            # Let desktop handle high-level events first (start, icons, power, windows)
            desktop.handle_event(ev)
            # Let each window handle events (drag/resize/internal)
            # Window.handle_event is invoked by desktop for focused window
            # But we still need to handle icon dragging global state
            if ev.type == MOUSEBUTTONUP and ev.button == 1:
                # finish icon drag
                for ico in desktop.icons:
                    ico.pop("dragging", None)
            if ev.type == MOUSEMOTION:
                # if any icon is dragging, move it
                for ico in desktop.icons:
                    if ico.get("dragging"):
                        mx,my = ev.pos
                        offx, offy = ico.get("off", (0,0))
                        ico["rect"].x = mx - offx; ico["rect"].y = my - offy
        # Forward event to windows individually for their drag/resize handling
        for w in desktop.windows:
            w.handle_event(ev)

    # draw
    desktop.draw(screen)

    # update windows' app-specific logic if needed (e.g., snake)
    for w in desktop.windows:
        # if app has update method (e.g. SnakeApp uses update inside draw), it's handled in draw
        pass

    pygame.display.flip()

pygame.quit()
sys.exit()
