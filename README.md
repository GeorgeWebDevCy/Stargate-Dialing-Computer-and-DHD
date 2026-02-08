# Stargate Dialing Computer + DHD (Cross-Platform)

A desktop Stargate SG-1 style dialing simulator built with Python + `pygame`.

It includes:
- Stargate render with rotating ring and chevron lock animation
- DHD-style symbol keypad (`39` symbols)
- Address dialing flow (`7-9` symbols)
- Preset addresses (Abydos, Chulak, Dakara, Earth)
- Wormhole open/active/close state simulation
- Generated sound effects (press, lock, kawoosh, close) with no external assets required

## Quick start

1. Install Python 3.10+.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Run:

```bash
python stargate_app.py
```

## Build Windows EXE (GUI)

1. Install build tools:

```bash
pip install -r requirements-build.txt
```

2. Build the executable:

```powershell
powershell -ExecutionPolicy Bypass -File .\build_exe.ps1
```

3. Run:

```powershell
.\dist\StargateDialer.exe
```

Notes:
- The build is `--windowed` (GUI app, no terminal console).
- Default output is a single-file EXE in `dist/`.
- Use `-OneDir` if you want a folder build:
  - `powershell -ExecutionPolicy Bypass -File .\build_exe.ps1 -OneDir`

### Custom icon

- The EXE uses `assets/stargate_icon.ico`.
- Source image is `assets/stargate_icon.png`.

## Build Windows Installer

1. Install Inno Setup (one-time):

```powershell
winget install --id JRSoftware.InnoSetup --accept-package-agreements --accept-source-agreements --scope user
```

2. Build installer (also rebuilds EXE):

```powershell
powershell -ExecutionPolicy Bypass -File .\build_installer.ps1
```

3. Output:

- `installer/output/StargateDialer-Setup-<version>.exe`

## Controls

- Mouse: click symbols and controls.
- Keyboard:
  - `1`..`9`: quick symbols `S01`..`S09`
  - `Enter`: dial
  - `Backspace`: remove last symbol
  - `Delete`: clear address
  - `Esc`: close gate

## Notes

- This is a fan-made simulator and not affiliated with MGM or the Stargate IP owners.
- Current symbols are generic (`S01`..`S39`). You can replace these with canonical glyph art/sound assets later.
