#!/usr/bin/env python3
"""
Breakout — Minecraft-style (classic rules, blocky vibes).

Changes vs. previous neon build:
  • Proper playfield BORDER: the ball bounces on the COLOURED border itself (not a hidden line).
  • Blocky, Minecraft-inspired theme: grass/dirt frame, ore-like bricks, wood paddle, crisp pixels.
  • Collision uses a playfield rect; bottom edge costs a life exactly when touching the coloured border.

Controls:
  • Mouse = move paddle (smooth)
  • ← / →  = move paddle
  • SPACE  = launch / pause
  • R      = restart
  • ESC/Q  = quit

Deps:
  pip install pygame
"""


from __future__ import annotations
import math
import random
import sys
from dataclasses import dataclass
from typing import List, Tuple

import pygame

# --------------------------- Config --------------------------- #
W, H = 900, 640
FPS = 120

# Palette (Minecraft-ish)
BG        = (22, 24, 26)              # night sky
GRASS     = (106, 170, 59)
DIRT      = (122, 79, 46)
STONE     = (100, 100, 100)
WOOD      = (155, 111, 68)
WOOD_DARK = (124, 88, 54)

EMERALD   = (16, 163, 125)
DIAMOND   = (70, 200, 220)
GOLD      = (234, 190, 63)
REDSTONE  = (207, 66, 66)
LAPIS     = (55, 112, 198)
IRON      = (196, 196, 196)

INK       = (230, 236, 255)
MUTED     = (150, 160, 175)

# Playfield border
MARGIN = 18
TOP_BAR_H = 56
BORDER_THICK = 14            # visible coloured border thickness

# Gameplay
PADDLE_W, PADDLE_H = 120, 18
BALL_R = 7
BRICK_W, BRICK_H = 92, 26
BRICK_GAP = 6
ROWS = 6
COLS = 9

START_SPEED = 300.0
SPEED_INC   = 12.0
MAX_SPEED   = 760.0
LIVES       = 3

Vec = pygame.math.Vector2

def clamp(n, lo, hi):
    return lo if n < lo else hi if n > hi else n

# --------------------------- Theming helpers --------------------------- #

def draw_block_border(screen: pygame.Surface, rect: pygame.Rect):
    """Draw a chunky grass/dirt border around playfield.
    The inner edge (facing the play area) is grass; outside shows dirt.
    Ball collides with the *inner edge* of this coloured border.
    """
    # Outer dirt frame
    outer = rect.inflate(BORDER_THICK*2, BORDER_THICK*2)
    pygame.draw.rect(screen, DIRT, outer)

    # Carve the inner play area
    pygame.draw.rect(screen, BG, rect)

    # Grass strip hugging the playfield edge
    # Left
    pygame.draw.rect(screen, GRASS, pygame.Rect(rect.left-BORDER_THICK, rect.top, BORDER_THICK, rect.height))
    # Right
    pygame.draw.rect(screen, GRASS, pygame.Rect(rect.right, rect.top, BORDER_THICK, rect.height))
    # Top
    pygame.draw.rect(screen, GRASS, pygame.Rect(rect.left, rect.top-BORDER_THICK, rect.width, BORDER_THICK))
    # Bottom
    pygame.draw.rect(screen, GRASS, pygame.Rect(rect.left, rect.bottom, rect.width, BORDER_THICK))

    # Add blocky check pattern to the grass for pixel vibes
    tile = 8
    dark_grass = (86, 140, 49)
    for x in range(rect.left - BORDER_THICK, rect.right + BORDER_THICK, tile):
        for y in range(rect.top - BORDER_THICK, rect.bottom + BORDER_THICK, tile):
            # only paint on the border area
            if not rect.collidepoint(x, y) and not rect.inflate(BORDER_THICK*2, BORDER_THICK*2).collidepoint(x-1, y-1):
                continue
            on_border = (
                rect.left - BORDER_THICK <= x < rect.left or
                rect.right <= x < rect.right + BORDER_THICK or
                rect.top - BORDER_THICK <= y < rect.top or
                rect.bottom <= y < rect.bottom + BORDER_THICK
            )
            if on_border and ((x//tile + y//tile) % 2 == 0):
                pygame.draw.rect(screen, dark_grass, (x, y, tile, tile))


def draw_pixel_rect(screen: pygame.Surface, rect: pygame.Rect, base: Tuple[int,int,int]):
    """Rect with inner lighter face for that block look."""
    pygame.draw.rect(screen, base, rect)
    inset = rect.inflate(-8, -8)
    shade = tuple(clamp(c + 28, 0, 255) for c in base)
    pygame.draw.rect(screen, shade, inset)

# --------------------------- Entities --------------------------- #
@dataclass
class Paddle:
    rect: pygame.Rect
    speed: float = 700.0

    def update(self, dt: float, keys, mouse_x: int | None, play: pygame.Rect):
        vx = 0.0
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            vx -= self.speed
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            vx += self.speed
        if mouse_x is not None:
            target = mouse_x - self.rect.w/2
            self.rect.x = int(self.rect.x + (target - self.rect.x) * min(1.0, dt*12))
        else:
            self.rect.x += int(vx * dt)
        # clamp inside play
        left_limit = play.left + 6
        right_limit = play.right - self.rect.w - 6
        self.rect.x = clamp(self.rect.x, left_limit, right_limit)

    def draw(self, screen: pygame.Surface):
        draw_pixel_rect(screen, self.rect, WOOD)
        # plank lines
        for i in range(1, 4):
            y = self.rect.top + i*(self.rect.h//4)
            pygame.draw.line(screen, WOOD_DARK, (self.rect.left+4, y), (self.rect.right-4, y), 2)

@dataclass
class Ball:
    pos: Vec
    vel: Vec
    speed: float

    def launch_up(self):
        angle = random.uniform(-0.35, 0.35)
        self.vel = Vec(math.sin(angle), -math.cos(angle)) * self.speed

    def update(self, dt: float, play: pygame.Rect):
        self.pos += self.vel * dt
        # collide with the visible coloured border edges, i.e., the inner edge of the border
        # Left
        if self.pos.x <= play.left + BALL_R:
            self.pos.x = play.left + BALL_R
            self.vel.x *= -1
        # Right
        if self.pos.x >= play.right - BALL_R:
            self.pos.x = play.right - BALL_R
            self.vel.x *= -1
        # Top
        if self.pos.y <= play.top + BALL_R:
            self.pos.y = play.top + BALL_R
            self.vel.y *= -1

    def draw(self, screen: pygame.Surface):
        # pixel ball (no glow): outer white, small lighter face
        pygame.draw.circle(screen, (245,245,245), (int(self.pos.x), int(self.pos.y)), BALL_R)
        pygame.draw.rect(screen, (255,255,255), (int(self.pos.x-2), int(self.pos.y-4), 4, 2))

    def reflect_from_paddle(self, pad: Paddle):
        if self.vel.y > 0 and pad.rect.top - BALL_R <= self.pos.y <= pad.rect.bottom + BALL_R:
            if pad.rect.left - BALL_R <= self.pos.x <= pad.rect.right + BALL_R:
                offset = (self.pos.x - pad.rect.centerx) / (pad.rect.w/2)
                offset = clamp(offset, -1, 1)
                angle = offset * 0.6
                self.vel = Vec(math.sin(angle), -math.cos(angle)) * self.speed
                self.pos.y = pad.rect.top - BALL_R - 1

@dataclass
class Brick:
    rect: pygame.Rect
    color: Tuple[int,int,int]
    alive: bool = True

class Particles:
    def __init__(self):
        self.bits: List[Tuple[Vec, Vec, float, Tuple[int,int,int]]] = []

    def emit(self, x: int, y: int, color: Tuple[int,int,int]):
        for _ in range(10):
            vel = Vec(random.uniform(-90, 90), random.uniform(-120, 40))
            life = random.uniform(0.25, 0.5)
            self.bits.append((Vec(x, y), vel, life, color))

    def update(self, dt: float):
        next_bits = []
        for pos, vel, life, col in self.bits:
            life -= dt
            if life <= 0: continue
            vel.y += 420 * dt
            pos += vel * dt
            next_bits.append((pos, vel, life, col))
        self.bits = next_bits

    def draw(self, screen: pygame.Surface):
        for pos, _, life, col in self.bits:
            a = int(80 + 120*life)
            pygame.draw.rect(screen, (*col, a), (int(pos.x), int(pos.y), 3, 3))

# --------------------------- Level --------------------------- #
BRICK_MATS = [EMERALD, DIAMOND, GOLD, REDSTONE, LAPIS, IRON]

class Level:
    def __init__(self, idx: int, play: pygame.Rect):
        self.index = idx
        self.play = play
        self.bricks: List[Brick] = []
        self._build()

    def _build(self):
        total_w = COLS * BRICK_W + (COLS - 1) * BRICK_GAP
        start_x = self.play.left + (self.play.w - total_w)//2
        for r in range(ROWS):
            for c in range(COLS):
                x = start_x + c * (BRICK_W + BRICK_GAP)
                y = self.play.top + 40 + r * (BRICK_H + BRICK_GAP)
                col = BRICK_MATS[(r + c + self.index) % len(BRICK_MATS)]
                self.bricks.append(Brick(pygame.Rect(x, y, BRICK_W, BRICK_H), col))

    def draw(self, screen: pygame.Surface):
        for b in self.bricks:
            if not b.alive: continue
            draw_pixel_rect(screen, b.rect, b.color)

    def collide_ball(self, ball: Ball, particles: Particles) -> int:
        for b in self.bricks:
            if not b.alive: continue
            if b.rect.collidepoint(int(ball.pos.x), int(ball.pos.y)):
                b.alive = False
                particles.emit(b.rect.centerx, b.rect.centery, b.color)
                # reflect based on impact side
                dx = min(abs(ball.pos.x - b.rect.left), abs(ball.pos.x - b.rect.right))
                dy = min(abs(ball.pos.y - b.rect.top),  abs(ball.pos.y - b.rect.bottom))
                if dx < dy:
                    ball.vel.x *= -1
                else:
                    ball.vel.y *= -1
                ball.speed = min(MAX_SPEED, ball.speed + SPEED_INC)
                ball.vel = ball.vel.normalize() * ball.speed
                return 1
        return 0

    def cleared(self) -> bool:
        return all(not b.alive for b in self.bricks)

# --------------------------- Game --------------------------- #
class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Breakout — Minecraft-style")
        self.screen = pygame.display.set_mode((W, H))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("consolas, menlo, ui-monospace, monospace", 20)
        self.big  = pygame.font.SysFont("consolas, menlo, ui-monospace, monospace", 42, bold=True)

        self.play = pygame.Rect(MARGIN + BORDER_THICK, TOP_BAR_H + MARGIN + BORDER_THICK,
                                W - 2*(MARGIN + BORDER_THICK), H - (TOP_BAR_H + 2*(MARGIN + BORDER_THICK)))
        self.reset(full=True)

    def reset(self, full: bool = False):
        self.level_index = 0 if full else self.level_index + 1
        self.level = Level(self.level_index, self.play)
        self.score = 0 if full else self.score
        self.lives = LIVES if full else self.lives
        pad_y = self.play.bottom - 40
        self.paddle = Paddle(pygame.Rect(self.play.centerx - PADDLE_W//2, pad_y, PADDLE_W, PADDLE_H))
        self.ball = Ball(Vec(self.paddle.rect.centerx, self.paddle.rect.top - BALL_R - 1), Vec(0,0), START_SPEED)
        self.attached = True
        self.paused = False
        self.particles = Particles()

    # ---------------- loop ---------------- #
    def run(self):
        while True:
            dt = self.clock.tick(FPS) / 1000.0
            if not self.events(): break
            if not self.paused:
                self.update(dt)
            self.draw()
        pygame.quit(); sys.exit(0)

    # --------------- events --------------- #
    def events(self) -> bool:
        mouse_x = None
        keys = pygame.key.get_pressed()
        for e in pygame.event.get():
            if e.type == pygame.QUIT: return False
            if e.type == pygame.KEYDOWN:
                if e.key in (pygame.K_ESCAPE, pygame.K_q): return False
                if e.key == pygame.K_SPACE:
                    if self.attached:
                        self.attached = False
                        self.ball.launch_up()
                    else:
                        self.paused = not self.paused
                if e.key == pygame.K_r:
                    self.reset(full=True)
            if e.type == pygame.MOUSEMOTION:
                mouse_x = e.pos[0]
        # early paddle aim for responsiveness
        self.paddle.update(0, keys, mouse_x, self.play)
        return True

    # --------------- update --------------- #
    def update(self, dt: float):
        keys = pygame.key.get_pressed()
        mx = pygame.mouse.get_pos()[0] if pygame.mouse.get_focused() else None
        self.paddle.update(dt, keys, mx, self.play)

        if self.attached:
            self.ball.pos.update(self.paddle.rect.centerx, self.paddle.rect.top - BALL_R - 1)
        else:
            self.ball.update(dt, self.play)
            self.ball.reflect_from_paddle(self.paddle)
            self.score += self.level.collide_ball(self.ball, self.particles) * 10
            # bottom edge = life lost when touching grass border line
            if self.ball.pos.y >= self.play.bottom - BALL_R:
                self.lives -= 1
                self.attached = True
                self.ball.speed = START_SPEED
                self.ball.pos.update(self.paddle.rect.centerx, self.paddle.rect.top - BALL_R - 1)
                self.ball.vel.update(0,0)

        if self.level.cleared():
            self.level_index += 1
            self.level = Level(self.level_index, self.play)
            self.attached = True
            self.ball.speed = START_SPEED
            self.ball.pos.update(self.paddle.rect.centerx, self.paddle.rect.top - BALL_R - 1)
            self.ball.vel.update(0,0)

        self.particles.update(dt)

    # ---------------- draw ---------------- #
    def draw(self):
        self.screen.fill(BG)

        # Top HUD bar (stone slab look)
        hud = pygame.Rect(MARGIN, MARGIN, W - 2*MARGIN, TOP_BAR_H)
        pygame.draw.rect(self.screen, STONE, hud, border_radius=8)
        pygame.draw.rect(self.screen, (70,70,70), hud, 2, border_radius=8)
        self.text(f"Score: {self.score}", hud.left + 14, hud.top + 16, INK)
        self.text(f"Lives: {self.lives}", hud.centerx - 40, hud.top + 16, INK)
        self.text(f"Level: {self.level_index+1}", hud.right - 120, hud.top + 16, INK)

        # Playfield frame and border (grass/dirt)
        draw_block_border(self.screen, self.play)

        # Entities
        self.level.draw(self.screen)
        self.paddle.draw(self.screen)
        self.ball.draw(self.screen)
        self.particles.draw(self.screen)

        # overlays
        if self.attached:
            self.banner("SPACE to launch")
        elif self.paused:
            self.banner("Paused — SPACE")
        elif self.lives <= 0:
            self.banner("Game Over — R to restart")

        pygame.display.flip()

    def text(self, s: str, x: int, y: int, col: Tuple[int,int,int] = INK):
        surf = self.font.render(s, True, col)
        self.screen.blit(surf, (x, y))

    def banner(self, msg: str):
        box = pygame.Rect(0,0, 520, 70)
        box.center = (W//2, H//2)
        pygame.draw.rect(self.screen, STONE, box, border_radius=10)
        pygame.draw.rect(self.screen, (60,60,60), box, 2, border_radius=10)
        txt = self.big.render(msg, True, INK)
        self.screen.blit(txt, txt.get_rect(center=box.center))

# --------------------------- main --------------------------- #
if __name__ == "__main__":
    Game().run()