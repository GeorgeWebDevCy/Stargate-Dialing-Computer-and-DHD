# Stargate Dialing Computer + DHD (Cross-Platform)

A desktop Stargate SG-1 style dialing simulator built with Python + `pygame`.

It includes:
- Stargate render with rotating ring and chevron lock animation
- Stylized DHD console with circular symbol interaction
- Original-style DHD symbol wheel art (`assets/dhd_original.png`)
- SG-1 glyph font support for address display
- Address dialing flow (`7-9` symbols)
- Preset addresses (Abydos, Chulak, Dakara, Earth)
- Wormhole open/active/close state simulation
- Sound loading from `assets/sounds` (with generated fallback if files are missing)

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
- Assets are bundled into the EXE via PyInstaller `--add-data`.
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
- Optional version override:
  - `powershell -ExecutionPolicy Bypass -File .\build_installer.ps1 -AppVersion 1.0.0`

## Controls

- Mouse: click symbols and controls.
- Keyboard:
  - `1`..`9`: quick symbols `01`..`09`
  - `Enter`: dial
  - `Backspace`: remove last symbol
  - `Delete`: clear address
  - `Esc`: close gate

## Assets and Attribution

- This is a fan-made simulator and not affiliated with MGM or the Stargate IP owners.
- Asset source details are in `assets/ATTRIBUTION.md`.
- Replace files in `assets/sounds/` to use your preferred sound pack:
  - `press`, `lock`, `error`, `close`, `kawoosh` names are auto-mapped.
- SG-1 glyph font is loaded from `assets/fonts/sg1-glyphs.ttf` when present.
