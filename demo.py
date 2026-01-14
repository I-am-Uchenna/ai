#!/usr/bin/env python3
"""
Quick demo script to showcase the particle system capabilities
Runs through different modes automatically
"""

import sys
import time
from particle_universe import ParticleSystem, get_terminal_size, COLORS

def demo_mode(system, mode_name, duration=3):
    """Demo a specific mode for a duration"""
    system.mode = mode_name
    system.particles.clear()

    frames = int(duration * 30)  # 30 FPS

    for _ in range(frames):
        system.update()
        system.render()
        time.sleep(0.033)

def main():
    """Run automated demo"""
    print(f"{COLORS['green']}ASCII Particle Universe - Auto Demo{COLORS['reset']}")
    print("This will showcase each mode for 3 seconds...")
    print("Press Ctrl+C to exit\n")
    time.sleep(2)

    try:
        # Hide cursor
        sys.stdout.write('\033[?25l')

        width, height = get_terminal_size()
        system = ParticleSystem(width, height)

        modes = ['fireworks', 'fountain', 'gravity', 'rain', 'spiral', 'explosion', 'wave']

        while True:
            for mode in modes:
                demo_mode(system, mode, duration=3)
                time.sleep(0.5)

    except KeyboardInterrupt:
        pass
    finally:
        # Show cursor
        sys.stdout.write('\033[?25h')
        sys.stdout.write(COLORS['reset'])
        print("\n\nDemo complete!")

if __name__ == '__main__':
    main()
