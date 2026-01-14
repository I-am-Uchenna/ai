#!/usr/bin/env python3
"""
ASCII Particle Universe - An interactive terminal particle physics simulator
Press number keys to switch between different effects!
"""

import sys
import tty
import termios
import time
import random
import math
import os
from dataclasses import dataclass
from typing import List, Tuple
import select

# ANSI color codes
COLORS = {
    'red': '\033[91m',
    'green': '\033[92m',
    'yellow': '\033[93m',
    'blue': '\033[94m',
    'magenta': '\033[95m',
    'cyan': '\033[96m',
    'white': '\033[97m',
    'reset': '\033[0m',
}

# Particle characters for different visual effects
PARTICLE_CHARS = ['*', '•', '○', '●', '◦', '∘', '⋅', '·', '+', '×']


@dataclass
class Vector2D:
    """2D vector for position and velocity"""
    x: float
    y: float

    def __add__(self, other):
        return Vector2D(self.x + other.x, self.y + other.y)

    def __sub__(self, other):
        return Vector2D(self.x - other.x, self.y - other.y)

    def __mul__(self, scalar):
        return Vector2D(self.x * scalar, self.y * scalar)

    def magnitude(self):
        return math.sqrt(self.x**2 + self.y**2)

    def normalize(self):
        mag = self.magnitude()
        if mag == 0:
            return Vector2D(0, 0)
        return Vector2D(self.x / mag, self.y / mag)


class Particle:
    """A particle with position, velocity, and visual properties"""

    def __init__(self, x, y, vx=0, vy=0, lifetime=100, color='white', char='*'):
        self.pos = Vector2D(x, y)
        self.vel = Vector2D(vx, vy)
        self.lifetime = lifetime
        self.max_lifetime = lifetime
        self.color = color
        self.char = char
        self.trail = []

    def update(self, gravity=Vector2D(0, 0), drag=0.99):
        """Update particle physics"""
        self.vel = self.vel + gravity
        self.vel = self.vel * drag
        self.pos = self.pos + self.vel
        self.lifetime -= 1

    def is_alive(self):
        return self.lifetime > 0

    def get_alpha(self):
        """Get opacity based on remaining lifetime"""
        return self.lifetime / self.max_lifetime


class ParticleSystem:
    """Manages all particles and physics"""

    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.particles: List[Particle] = []
        self.mode = 'fireworks'
        self.frame = 0

    def add_particle(self, particle):
        self.particles.append(particle)

    def update(self):
        """Update all particles based on current mode"""
        self.frame += 1

        # Mode-specific particle generation
        if self.mode == 'fireworks' and random.random() < 0.1:
            self.spawn_firework()
        elif self.mode == 'fountain' and random.random() < 0.5:
            self.spawn_fountain_particle()
        elif self.mode == 'gravity':
            if random.random() < 0.2:
                self.spawn_gravity_particle()
        elif self.mode == 'rain':
            if random.random() < 0.3:
                self.spawn_rain_particle()
        elif self.mode == 'spiral':
            if random.random() < 0.4:
                self.spawn_spiral_particle()
        elif self.mode == 'explosion' and self.frame % 30 == 0:
            self.spawn_explosion()
        elif self.mode == 'wave':
            if random.random() < 0.3:
                self.spawn_wave_particle()

        # Update each particle
        gravity = self.get_gravity()
        drag = self.get_drag()

        for particle in self.particles:
            particle.update(gravity, drag)

            # Apply mode-specific forces
            if self.mode == 'gravity':
                self.apply_gravity_well(particle)
            elif self.mode == 'spiral':
                self.apply_spiral_force(particle)
            elif self.mode == 'wave':
                self.apply_wave_force(particle)

        # Remove dead particles
        self.particles = [p for p in self.particles if p.is_alive() and
                         0 <= p.pos.x < self.width and 0 <= p.pos.y < self.height]

    def get_gravity(self):
        """Get gravity vector based on mode"""
        if self.mode in ['fireworks', 'fountain', 'explosion']:
            return Vector2D(0, 0.2)
        elif self.mode == 'rain':
            return Vector2D(0, 0.5)
        return Vector2D(0, 0)

    def get_drag(self):
        """Get drag coefficient based on mode"""
        if self.mode in ['spiral', 'wave']:
            return 0.95
        return 0.99

    def spawn_firework(self):
        """Create a firework explosion"""
        x = random.uniform(self.width * 0.2, self.width * 0.8)
        y = random.uniform(self.height * 0.2, self.height * 0.5)
        color = random.choice(['red', 'yellow', 'green', 'blue', 'magenta', 'cyan'])

        # Create explosion particles
        for _ in range(random.randint(20, 40)):
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(1, 3)
            vx = math.cos(angle) * speed
            vy = math.sin(angle) * speed
            lifetime = random.randint(30, 60)
            char = random.choice(PARTICLE_CHARS)

            self.add_particle(Particle(x, y, vx, vy, lifetime, color, char))

    def spawn_fountain_particle(self):
        """Create fountain particles from bottom center"""
        x = self.width / 2 + random.uniform(-2, 2)
        y = self.height - 1
        angle = random.uniform(-math.pi * 0.7, -math.pi * 0.3)
        speed = random.uniform(3, 6)
        vx = math.cos(angle) * speed
        vy = math.sin(angle) * speed
        color = random.choice(['cyan', 'blue', 'white'])

        self.add_particle(Particle(x, y, vx, vy, 60, color, '•'))

    def spawn_gravity_particle(self):
        """Create particles affected by gravity well"""
        x = random.uniform(0, self.width)
        y = 0
        vy = random.uniform(0.5, 2)
        vx = random.uniform(-1, 1)
        color = random.choice(['yellow', 'white', 'cyan'])

        self.add_particle(Particle(x, y, vx, vy, 150, color, '○'))

    def spawn_rain_particle(self):
        """Create rain particles"""
        x = random.uniform(0, self.width)
        y = 0
        vx = random.uniform(-0.5, 0.5)
        color = random.choice(['blue', 'cyan', 'white'])

        self.add_particle(Particle(x, y, vx, 0, 100, color, '|'))

    def spawn_spiral_particle(self):
        """Create spiral particles"""
        x = self.width / 2
        y = self.height / 2
        angle = (self.frame * 0.1) % (2 * math.pi)
        speed = 2
        vx = math.cos(angle) * speed
        vy = math.sin(angle) * speed
        color = random.choice(['magenta', 'cyan', 'yellow', 'green'])

        self.add_particle(Particle(x, y, vx, vy, 80, color, '●'))

    def spawn_explosion(self):
        """Create a massive explosion"""
        x = random.uniform(self.width * 0.3, self.width * 0.7)
        y = random.uniform(self.height * 0.3, self.height * 0.7)
        colors = ['red', 'yellow', 'white']

        for _ in range(60):
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(0.5, 4)
            vx = math.cos(angle) * speed
            vy = math.sin(angle) * speed
            lifetime = random.randint(40, 80)
            color = random.choice(colors)
            char = random.choice(['*', '×', '+', '●'])

            self.add_particle(Particle(x, y, vx, vy, lifetime, color, char))

    def spawn_wave_particle(self):
        """Create wave particles"""
        x = 0
        y = self.height / 2 + math.sin(self.frame * 0.1) * 10
        vx = 2
        color = random.choice(['cyan', 'blue', 'green'])

        self.add_particle(Particle(x, y, vx, 0, 80, color, '~'))

    def apply_gravity_well(self, particle):
        """Apply gravitational attraction to center"""
        center = Vector2D(self.width / 2, self.height / 2)
        direction = center - particle.pos
        distance = direction.magnitude()

        if distance > 1:
            force = direction.normalize() * (100 / distance)
            particle.vel = particle.vel + force * 0.01

    def apply_spiral_force(self, particle):
        """Apply spiral force"""
        center = Vector2D(self.width / 2, self.height / 2)
        direction = center - particle.pos

        # Tangential force for spiral
        tangent = Vector2D(-direction.y, direction.x).normalize() * 0.5
        particle.vel = particle.vel + tangent

    def apply_wave_force(self, particle):
        """Apply wave force"""
        wave = math.sin(particle.pos.x * 0.2 + self.frame * 0.1) * 0.3
        particle.vel.y += wave

    def render(self):
        """Render particles to terminal"""
        # Create empty grid
        grid = [[' ' for _ in range(self.width)] for _ in range(self.height)]
        color_grid = [['white' for _ in range(self.width)] for _ in range(self.height)]
        char_grid = [[' ' for _ in range(self.width)] for _ in range(self.height)]

        # Place particles
        for particle in self.particles:
            x = int(particle.pos.x)
            y = int(particle.pos.y)

            if 0 <= x < self.width and 0 <= y < self.height:
                alpha = particle.get_alpha()
                if alpha > 0.3:  # Only render if visible enough
                    grid[y][x] = particle.char
                    color_grid[y][x] = particle.color
                    char_grid[y][x] = particle.char

        # Clear screen and move cursor to top
        sys.stdout.write('\033[2J\033[H')

        # Render grid with colors
        output = []
        for y in range(self.height):
            line = []
            current_color = None
            for x in range(self.width):
                if color_grid[y][x] != current_color:
                    line.append(COLORS[color_grid[y][x]])
                    current_color = color_grid[y][x]
                line.append(grid[y][x])
            output.append(''.join(line))

        sys.stdout.write('\n'.join(output))
        sys.stdout.write(COLORS['reset'])

        # Status bar
        modes = ['fireworks', 'fountain', 'gravity', 'rain', 'spiral', 'explosion', 'wave']
        status = f"\n\n{COLORS['cyan']}Mode: {self.mode.upper()}{COLORS['reset']} | "
        status += f"Particles: {len(self.particles)} | "
        status += f"Controls: 1-{len(modes)} (switch mode) | Q (quit)\n"
        status += f"Modes: " + " | ".join([f"{i+1}:{m}" for i, m in enumerate(modes)])

        sys.stdout.write(status)
        sys.stdout.flush()


def get_terminal_size():
    """Get terminal dimensions"""
    size = os.get_terminal_size()
    return size.columns, size.lines - 6  # Leave space for status


def main():
    """Main application loop"""
    # Set up terminal
    old_settings = termios.tcgetattr(sys.stdin)
    try:
        tty.setcbreak(sys.stdin.fileno())

        # Hide cursor
        sys.stdout.write('\033[?25l')
        sys.stdout.flush()

        width, height = get_terminal_size()
        system = ParticleSystem(width, height)

        modes = ['fireworks', 'fountain', 'gravity', 'rain', 'spiral', 'explosion', 'wave']

        print(f"{COLORS['green']}Welcome to ASCII Particle Universe!{COLORS['reset']}")
        print("Loading...")
        time.sleep(1)

        running = True
        while running:
            # Check for input (non-blocking)
            if select.select([sys.stdin], [], [], 0)[0]:
                key = sys.stdin.read(1)

                if key.lower() == 'q':
                    running = False
                elif key.isdigit():
                    mode_idx = int(key) - 1
                    if 0 <= mode_idx < len(modes):
                        system.mode = modes[mode_idx]
                        system.particles.clear()  # Clear particles on mode change

            system.update()
            system.render()
            time.sleep(0.033)  # ~30 FPS

    finally:
        # Restore terminal
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
        sys.stdout.write('\033[?25h')  # Show cursor
        sys.stdout.write(COLORS['reset'])
        sys.stdout.write('\n\nThanks for playing!\n')
        sys.stdout.flush()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nGoodbye!")
        sys.exit(0)
