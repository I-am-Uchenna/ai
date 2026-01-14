# 🎆 ASCII Particle Universe

An interactive terminal-based particle physics simulator that creates mesmerizing visual effects using ASCII art and ANSI colors!

```
        *    ○     •
    ○     ×   *   ●    *
  •   *      ●    ○   •   ×
     ×   ●      *    ○    •
  ○      •  ×     ●     *
    *   ○     •      ×    ●
```

## ✨ Features

- **7 Different Particle Modes** - Each with unique physics and visual effects
- **Real-time Physics Simulation** - Gravity, drag, attraction forces
- **Colorful ASCII Art** - ANSI color-coded particles
- **Interactive Controls** - Switch between modes on the fly
- **Smooth Animation** - 30 FPS terminal graphics

## 🎮 Particle Modes

1. **Fireworks** 🎆 - Explosive colorful bursts across the sky
2. **Fountain** ⛲ - Elegant water fountain simulation
3. **Gravity** 🌌 - Particles attracted to a central gravity well
4. **Rain** 🌧️ - Falling rain particles with natural motion
5. **Spiral** 🌀 - Hypnotic rotating spiral patterns
6. **Explosion** 💥 - Massive periodic explosions
7. **Wave** 🌊 - Flowing wave motion across the screen

## 🚀 Quick Start

### Prerequisites

- Python 3.6 or higher
- A terminal with ANSI color support (most modern terminals)
- Unix-like system (Linux, macOS) or WSL on Windows

### Installation & Running

```bash
# Make the script executable
chmod +x particle_universe.py

# Run the simulator
python3 particle_universe.py
```

Or simply:

```bash
./particle_universe.py
```

## 🎯 Controls

- **1-7** - Switch between different particle modes
- **Q** - Quit the application

## 🔬 Technical Details

### Physics Engine

The simulator implements a custom 2D physics engine with:
- **Vector mathematics** for position and velocity
- **Gravity simulation** with customizable strength
- **Drag forces** for realistic motion
- **Attraction forces** for gravity well effects
- **Tangential forces** for spiral motion
- **Wave functions** for oscillating patterns

### Rendering System

- **Grid-based rendering** for efficient terminal output
- **ANSI color codes** for vibrant visuals
- **Particle lifetime management** with alpha blending
- **Multiple particle characters** for visual variety

### Particle System

Each particle has:
- Position and velocity vectors
- Lifetime and opacity
- Color and character properties
- Mode-specific physics behaviors

## 🎨 Customization

You can easily modify the code to:
- Add new particle modes
- Change colors and characters
- Adjust physics parameters (gravity, drag, etc.)
- Create custom force fields
- Add particle trails or other effects

## 🐛 Troubleshooting

**Colors not showing?**
- Ensure your terminal supports ANSI colors
- Try a different terminal emulator (iTerm2, GNOME Terminal, etc.)

**Flickering or slow performance?**
- Reduce the number of particles by adjusting spawn rates
- Close other terminal applications

**Terminal too small?**
- Resize your terminal window to at least 80x24
- The simulator automatically adapts to terminal size

## 🎓 What Makes This Novel?

1. **Interactive Physics Playground** - Real-time physics simulation in your terminal
2. **Multiple Effect Modes** - Seven distinct particle behaviors in one app
3. **Pure Terminal Graphics** - No external dependencies, just Python standard library
4. **Educational** - Great for learning physics simulation and terminal graphics
5. **Mesmerizing** - Watch patterns emerge from simple physics rules

## 🧩 Code Structure

- `Vector2D` - 2D vector math class
- `Particle` - Individual particle with physics properties
- `ParticleSystem` - Manages all particles and simulation modes
- Mode-specific spawning and force functions
- Terminal rendering and input handling

## 🌟 Future Ideas

- Add more modes (tornado, black hole, DNA helix)
- Implement particle collisions
- Add sound effects (using system beep)
- Save/load particle configurations
- Record animations as ASCII art files
- Mouse input for interactive particle spawning

## 📜 License

Free to use, modify, and share. Have fun experimenting!

## 🙏 Credits

Built with passion for creative coding and terminal art!

---

**Enjoy the show!** Press a number key and watch the magic happen ✨
