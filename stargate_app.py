"""Cross-platform Stargate SG-1 style dialing simulator.

Run:
    python stargate_app.py
"""

from __future__ import annotations

import math
import random
import sys
import traceback
from array import array
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pygame


WINDOW_SIZE = (1500, 920)
FPS = 60
SYMBOL_COUNT = 39
MIN_ADDRESS_LENGTH = 7
MAX_ADDRESS_LENGTH = 9


KNOWN_ADDRESSES: Dict[str, List[int]] = {
    "Abydos": [26, 6, 14, 31, 11, 29, 1],
    "Chulak": [8, 1, 22, 14, 36, 19, 4],
    "Dakara": [17, 28, 4, 35, 9, 21, 2],
    "Earth": [1, 11, 2, 19, 21, 24, 35],
}

ASCII_GLYPH_CHARS = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ") + list("abcdefghijklm")
FONT_GLYPH_CHARS = [chr(0xF101 + i) for i in range(SYMBOL_COUNT)]
GLYPH_CHARS = ASCII_GLYPH_CHARS


@dataclass
class Button:
    rect: pygame.Rect
    label: str
    action: str
    payload: int | str | None = None


@dataclass
class DHDSector:
    index: int
    start_angle: float
    end_angle: float
    inner_radius: float
    outer_radius: float


def _cw_angle_from_vector(dx: float, dy: float) -> float:
    """Return angle where 0 is up and positive is clockwise."""
    return math.degrees(math.atan2(dx, -dy)) % 360.0


def _angle_in_span(angle: float, start: float, end: float) -> bool:
    if start <= end:
        return start <= angle < end
    return angle >= start or angle < end


def _asset_dir() -> Path:
    script_dir = Path(__file__).resolve().parent
    candidates = [script_dir / "assets", Path.cwd() / "assets"]

    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        candidates.insert(0, Path(getattr(sys, "_MEIPASS")) / "assets")

    if getattr(sys, "frozen", False):
        exe_assets = Path(sys.executable).resolve().parent / "assets"
        candidates.insert(0, exe_assets)

    for candidate in candidates:
        if candidate.exists():
            return candidate
    return script_dir / "assets"


def _runtime_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


class AppLogger:
    """Simple file logger for app diagnostics and crash investigation."""

    def __init__(self, runtime_dir: Path) -> None:
        self.log_dir = runtime_dir / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_path = self.log_dir / f"stargate_app_{stamp}.log"
        self.max_bytes = 2_000_000
        self._write("INFO", "Logger initialized", {"log_path": str(self.log_path)})
        self.install_excepthook()

    def install_excepthook(self) -> None:
        old_hook = sys.excepthook

        def _hook(exc_type, exc_value, exc_tb):  # type: ignore[no-untyped-def]
            details = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
            self._write("CRITICAL", "Unhandled exception", {"traceback": details.strip()})
            old_hook(exc_type, exc_value, exc_tb)

        sys.excepthook = _hook

    def _rollover_if_needed(self) -> None:
        if not self.log_path.exists():
            return
        if self.log_path.stat().st_size < self.max_bytes:
            return
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_path = self.log_dir / f"stargate_app_{stamp}.log"

    def _write(self, level: str, message: str, details: Optional[Dict[str, str]] = None) -> None:
        self._rollover_if_needed()
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"{ts} [{level}] {message}"
        if details:
            safe_details = {k: str(v).replace("\n", "\\n") for k, v in details.items()}
            joined = " | ".join(f"{k}={v}" for k, v in safe_details.items())
            line = f"{line} | {joined}"
        try:
            with self.log_path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError:
            pass

    def info(self, message: str, **details: object) -> None:
        self._write("INFO", message, {k: str(v) for k, v in details.items()})

    def warning(self, message: str, **details: object) -> None:
        self._write("WARN", message, {k: str(v) for k, v in details.items()})

    def error(self, message: str, **details: object) -> None:
        self._write("ERROR", message, {k: str(v) for k, v in details.items()})

    def exception(self, message: str, exc: BaseException) -> None:
        tb = traceback.format_exc().strip()
        self._write(
            "ERROR",
            message,
            {
                "exception": repr(exc),
                "traceback": tb,
            },
        )


class GateAudio:
    def __init__(self, assets: Path) -> None:
        self.enabled = False
        self.sounds: Dict[str, pygame.mixer.Sound] = {}
        self.loop_channel: Optional[pygame.mixer.Channel] = None
        self.loaded_from: Dict[str, str] = {}

        try:
            pygame.mixer.pre_init(44100, -16, 1, 512)
            pygame.mixer.init()
        except pygame.error:
            return

        self.enabled = True
        self.loop_channel = pygame.mixer.Channel(1)
        sound_dir = assets / "sounds"
        sound_map = {
            "press": [
                "symbol_beep.mp3",
                "dhd_press.wav",
                "press.wav",
                "button.wav",
                "press.mp3",
                "press_3.mp3",
            ],
            "engage": ["symbol_engaging.mp3", "press_3.mp3", "press.mp3"],
            "ring": ["ring.mp3", "chevron_incoming_1.mp3"],
            "lock": ["chev_lock.mp3", "chevron_lock.wav", "lock.wav", "lock.mp3", "chevron.mp3"],
            "error": ["error.wav", "reject.wav", "ring_fail.mp3", "c7_failed.mp3"],
            "close": ["shutdown.mp3", "ring_stop.mp3", "gate_close.wav", "close.wav", "closeGate.mp3", "close.mp3"],
            "kawoosh": ["kawoosh.mp3", "kawoosh.wav", "open.wav", "event_horizon.mp3", "openGate.mp3"],
            "connected": ["sequence_complete.mp3", "event_horizon.mp3"],
        }

        for key, filenames in sound_map.items():
            for filename in filenames:
                path = sound_dir / filename
                if path.exists():
                    try:
                        self.sounds[key] = pygame.mixer.Sound(str(path))
                        self.loaded_from[key] = str(path.name)
                        break
                    except pygame.error:
                        continue

        # Synth fallback so app still works without external assets.
        if "press" not in self.sounds:
            self.sounds["press"] = self._tone(630, 0.06, 0.18)
            self.loaded_from["press"] = "synth_tone"
        if "engage" not in self.sounds:
            self.sounds["engage"] = self._tone(400, 0.20, 0.22)
            self.loaded_from["engage"] = "synth_tone"
        if "ring" not in self.sounds:
            self.sounds["ring"] = self._tone(300, 0.25, 0.08)
            self.loaded_from["ring"] = "synth_tone"
        if "lock" not in self.sounds:
            self.sounds["lock"] = self._tone(520, 0.15, 0.23)
            self.loaded_from["lock"] = "synth_tone"
        if "error" not in self.sounds:
            self.sounds["error"] = self._tone(220, 0.20, 0.22)
            self.loaded_from["error"] = "synth_tone"
        if "close" not in self.sounds:
            self.sounds["close"] = self._tone(170, 0.32, 0.22)
            self.loaded_from["close"] = "synth_tone"
        if "kawoosh" not in self.sounds:
            self.sounds["kawoosh"] = self._sweep(170, 900, 0.9, 0.28)
            self.loaded_from["kawoosh"] = "synth_sweep"
        if "connected" not in self.sounds:
            self.sounds["connected"] = self._tone(760, 0.22, 0.20)
            self.loaded_from["connected"] = "synth_tone"

        volumes = {
            "press": 0.58,
            "engage": 0.74,
            "ring": 0.16,
            "lock": 0.76,
            "error": 0.70,
            "close": 0.70,
            "kawoosh": 0.95,
            "connected": 0.72,
        }
        for key, snd in self.sounds.items():
            snd.set_volume(volumes.get(key, 0.70))

    def _tone(self, freq: float, seconds: float, volume: float) -> pygame.mixer.Sound:
        sample_rate = 44100
        frame_count = int(sample_rate * seconds)
        pcm = array("h")
        for i in range(frame_count):
            t = i / sample_rate
            sample = math.sin(2 * math.pi * freq * t)
            pcm.append(int(sample * 32767 * volume))
        return pygame.mixer.Sound(buffer=pcm)

    def _sweep(
        self, start_freq: float, end_freq: float, seconds: float, volume: float
    ) -> pygame.mixer.Sound:
        sample_rate = 44100
        frame_count = int(sample_rate * seconds)
        pcm = array("h")
        for i in range(frame_count):
            blend = i / max(1, frame_count - 1)
            freq = start_freq + (end_freq - start_freq) * blend
            t = i / sample_rate
            sample = math.sin(2 * math.pi * freq * t)
            envelope = min(1.0, blend * 4.0) * max(0.0, 1.0 - blend * 0.7)
            pcm.append(int(sample * 32767 * volume * envelope))
        return pygame.mixer.Sound(buffer=pcm)

    def play(self, name: str) -> None:
        if not self.enabled:
            return
        snd = self.sounds.get(name)
        if snd:
            snd.play()

    def start_loop(self, name: str) -> None:
        if not self.enabled or not self.loop_channel:
            return
        snd = self.sounds.get(name)
        if not snd:
            return
        self.loop_channel.stop()
        self.loop_channel.play(snd, loops=-1)

    def stop_loop(self) -> None:
        if self.loop_channel:
            self.loop_channel.stop()


class DHDWheel:
    def __init__(self, center: Tuple[int, int], assets: Path, font: pygame.font.Font) -> None:
        self.center = center
        self.font = font

        self.outer_radius = 280
        self.outer_ring_inner = 192
        self.inner_ring_outer = 180
        self.inner_ring_inner = 120
        self.center_button_radius = 84

        self.sectors: List[DHDSector] = []
        self.reference_source: Optional[pygame.Surface] = None
        self.image_surface: Optional[pygame.Surface] = None
        self.image_rect: Optional[pygame.Rect] = None
        self._load_reference_image(assets)
        self.set_geometry(center, 280)

    def _load_reference_image(self, assets: Path) -> None:
        filenames = ["dhd_original.png", "dhd_symbols.png", "dhd_reference.png"]
        for name in filenames:
            path = assets / name
            if not path.exists():
                continue
            try:
                source = pygame.image.load(str(path)).convert_alpha()
            except pygame.error:
                continue
            self.reference_source = source
            self._rescale_reference_image()
            return

    def _rescale_reference_image(self) -> None:
        if not self.reference_source:
            self.image_surface = None
            self.image_rect = None
            return
        size = self.outer_radius * 2 + 14
        self.image_surface = pygame.transform.smoothscale(self.reference_source, (size, size))
        self.image_rect = self.image_surface.get_rect(center=self.center)

    def set_geometry(self, center: Tuple[int, int], outer_radius: int) -> None:
        self.center = center
        self.outer_radius = max(170, outer_radius)
        self.outer_ring_inner = int(self.outer_radius * 0.69)
        self.inner_ring_outer = int(self.outer_radius * 0.64)
        self.inner_ring_inner = int(self.outer_radius * 0.43)
        self.center_button_radius = int(self.outer_radius * 0.30)
        self.sectors = self._build_sectors()
        self._rescale_reference_image()

    def _build_sectors(self) -> List[DHDSector]:
        sectors: List[DHDSector] = []
        idx = 0

        outer_count = 27
        outer_step = 360.0 / outer_count
        for i in range(outer_count):
            start = (i * outer_step) % 360.0
            end = (start + outer_step) % 360.0
            sectors.append(
                DHDSector(
                    index=idx,
                    start_angle=start,
                    end_angle=end,
                    inner_radius=self.outer_ring_inner,
                    outer_radius=self.outer_radius,
                )
            )
            idx += 1

        inner_count = 12
        inner_step = 360.0 / inner_count
        inner_offset = inner_step * 0.5
        for i in range(inner_count):
            start = (inner_offset + i * inner_step) % 360.0
            end = (start + inner_step) % 360.0
            sectors.append(
                DHDSector(
                    index=idx,
                    start_angle=start,
                    end_angle=end,
                    inner_radius=self.inner_ring_inner,
                    outer_radius=self.inner_ring_outer,
                )
            )
            idx += 1

        return sectors

    def hit_test(self, pos: Tuple[int, int]) -> Tuple[str, Optional[int]]:
        cx, cy = self.center
        dx = pos[0] - cx
        dy = pos[1] - cy
        dist = math.hypot(dx, dy)

        if dist <= self.center_button_radius:
            return ("center", None)

        angle = _cw_angle_from_vector(dx, dy)
        for sector in self.sectors:
            if not (sector.inner_radius <= dist <= sector.outer_radius):
                continue
            if _angle_in_span(angle, sector.start_angle, sector.end_angle):
                return ("symbol", sector.index)

        return ("none", None)

    def draw(
        self,
        surface: pygame.Surface,
        hovered_symbol: Optional[int],
        symbol_stage: Dict[int, int],
        pulse: float,
        connected: bool,
    ) -> None:
        if self.image_surface and self.image_rect:
            self._draw_reference_style(surface, hovered_symbol, symbol_stage, pulse, connected)
            return
        self._draw_procedural_style(surface, hovered_symbol, symbol_stage, pulse, connected)

    def _draw_reference_style(
        self,
        surface: pygame.Surface,
        hovered_symbol: Optional[int],
        symbol_stage: Dict[int, int],
        pulse: float,
        connected: bool,
    ) -> None:
        assert self.image_surface is not None
        assert self.image_rect is not None

        shadow = pygame.Surface((self.image_rect.width + 26, self.image_rect.height + 26), pygame.SRCALPHA)
        pygame.draw.circle(
            shadow,
            (0, 0, 0, 130),
            (shadow.get_width() // 2, shadow.get_height() // 2),
            self.outer_radius + 6,
        )
        surface.blit(shadow, shadow.get_rect(center=(self.center[0] + 6, self.center[1] + 8)))
        surface.blit(self.image_surface, self.image_rect)

        overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)

        for sector in self.sectors:
            stage = symbol_stage.get(sector.index, 0)
            color = None
            if stage == 2:
                color = (255, 139, 36, 150)
            elif stage == 1:
                color = (58, 173, 255, 122)
            if hovered_symbol == sector.index:
                color = (255, 218, 166, 128)

            if color:
                pygame.draw.polygon(overlay, color, self._sector_polygon(sector, pad=4))

        glow_strength = 130 + int(70 * pulse)
        center_color = (255, 134, 34, glow_strength)
        if connected:
            center_color = (68, 207, 255, 170)
        pygame.draw.circle(overlay, center_color, self.center, self.center_button_radius - 6)

        surface.blit(overlay, (0, 0))

    def _draw_procedural_style(
        self,
        surface: pygame.Surface,
        hovered_symbol: Optional[int],
        symbol_stage: Dict[int, int],
        pulse: float,
        connected: bool,
    ) -> None:
        cx, cy = self.center
        pygame.draw.circle(surface, (36, 40, 46), self.center, self.outer_radius + 9)
        pygame.draw.circle(surface, (168, 172, 177), self.center, self.outer_radius + 2)
        pygame.draw.circle(surface, (80, 86, 94), self.center, self.outer_radius + 2, 4)

        for sector in self.sectors:
            stage = symbol_stage.get(sector.index, 0)
            fill = (228, 231, 236)
            if stage == 1:
                fill = (206, 233, 252)
            elif stage == 2:
                fill = (248, 200, 140)
            if hovered_symbol == sector.index:
                fill = (255, 244, 208)

            poly = self._sector_polygon(sector, pad=3)
            pygame.draw.polygon(surface, fill, poly)
            pygame.draw.polygon(surface, (94, 100, 112), poly, 2)

            glyph = GLYPH_CHARS[sector.index] if 0 <= sector.index < len(GLYPH_CHARS) else "?"
            label = self.font.render(glyph, True, (38, 42, 48))
            mid_angle = (sector.start_angle + ((sector.end_angle - sector.start_angle) % 360.0) * 0.5) % 360.0
            rad = math.radians(mid_angle)
            mid_radius = (sector.inner_radius + sector.outer_radius) * 0.5
            x = cx + math.sin(rad) * mid_radius
            y = cy - math.cos(rad) * mid_radius
            surface.blit(label, label.get_rect(center=(int(x), int(y))))

        center_color = (255, 132, 36)
        if connected:
            center_color = (70, 208, 255)
        glow_radius = self.center_button_radius + int(7 * pulse)
        pygame.draw.circle(surface, (255, 171, 86), self.center, glow_radius)
        pygame.draw.circle(surface, center_color, self.center, self.center_button_radius)
        pygame.draw.circle(surface, (85, 48, 24), self.center, self.center_button_radius, 3)

    def _sector_polygon(self, sector: DHDSector, pad: int = 0) -> List[Tuple[int, int]]:
        start = sector.start_angle
        sweep = (sector.end_angle - sector.start_angle) % 360.0
        steps = max(6, int(sweep / 2.5))

        outer_radius = max(1.0, sector.outer_radius - pad)
        inner_radius = max(1.0, sector.inner_radius + pad)

        points: List[Tuple[int, int]] = []
        for i in range(steps + 1):
            angle = (start + sweep * (i / steps)) % 360.0
            rad = math.radians(angle)
            x = self.center[0] + math.sin(rad) * outer_radius
            y = self.center[1] - math.cos(rad) * outer_radius
            points.append((int(x), int(y)))

        for i in range(steps, -1, -1):
            angle = (start + sweep * (i / steps)) % 360.0
            rad = math.radians(angle)
            x = self.center[0] + math.sin(rad) * inner_radius
            y = self.center[1] - math.cos(rad) * inner_radius
            points.append((int(x), int(y)))

        return points


class StargateApp:
    def __init__(self) -> None:
        self.logger = AppLogger(_runtime_dir())
        pygame.init()
        self.assets = _asset_dir()

        self.screen = pygame.display.set_mode(WINDOW_SIZE, pygame.RESIZABLE)
        pygame.display.set_caption("Stargate Dialing Computer + DHD")
        self.clock = pygame.time.Clock()

        self.font_sm = pygame.font.SysFont("bahnschrift", 20)
        self.font_md = pygame.font.SysFont("bahnschrift", 28, bold=True)
        self.font_lg = pygame.font.SysFont("segoe ui", 40, bold=True)
        self.glyph_font_lg = pygame.font.SysFont("consolas", 46, bold=True)
        self.glyph_font_md = pygame.font.SysFont("consolas", 32, bold=True)
        self.glyph_chars = ASCII_GLYPH_CHARS
        glyph_font_path = self._find_glyph_font_path()
        if glyph_font_path:
            try:
                self.glyph_font_lg = pygame.font.Font(str(glyph_font_path), 46)
                self.glyph_font_md = pygame.font.Font(str(glyph_font_path), 32)
                self.glyph_chars = FONT_GLYPH_CHARS
            except pygame.error:
                self.glyph_chars = ASCII_GLYPH_CHARS

        self.audio = GateAudio(self.assets)
        self.dhd = DHDWheel(center=(1110, 520), assets=self.assets, font=self.font_sm)

        self.controls: List[Button] = []
        self.preset_buttons: List[Button] = []
        self.panel_rect = pygame.Rect(0, 0, 0, 0)
        self.left_view_rect = pygame.Rect(0, 0, 0, 0)
        self.gate_center = (380, 470)
        self.gate_outer_radius = 305
        self.gate_ring_radius = 253
        self.gate_inner_radius = 195
        self._rebuild_layout()

        self.running = True
        self.status = "Idle. Enter 7-9 symbols and press the DHD center."
        self.entered_symbols: List[int] = []
        self.current_address: List[int] = []
        self.locked_count = 0
        self.state = "IDLE"  # IDLE, DIALING, OPENING, CONNECTED

        self.hovered_symbol: Optional[int] = None
        self.ring_angle = 0.0
        self.next_lock_at = 0
        self.open_finish_at = 0
        self.connected_since = 0

        rng = random.Random(42)
        self.stars = [
            (
                rng.randint(0, WINDOW_SIZE[0] - 1),
                rng.randint(0, WINDOW_SIZE[1] - 1),
                rng.randint(1, 3),
                rng.uniform(0.0, 6.2),
            )
            for _ in range(180)
        ]
        self.logger.info(
            "Application initialized",
            assets=str(self.assets),
            window=f"{self.screen.get_width()}x{self.screen.get_height()}",
            logs=str(self.logger.log_path),
        )
        self.logger.info(
            "Audio mapping",
            press=self.audio.loaded_from.get("press", "missing"),
            engage=self.audio.loaded_from.get("engage", "missing"),
            ring=self.audio.loaded_from.get("ring", "missing"),
            lock=self.audio.loaded_from.get("lock", "missing"),
            kawoosh=self.audio.loaded_from.get("kawoosh", "missing"),
            close=self.audio.loaded_from.get("close", "missing"),
            connected=self.audio.loaded_from.get("connected", "missing"),
        )

    def _find_glyph_font_path(self) -> Optional[Path]:
        candidates = [
            self.assets / "fonts" / "sg1-glyphs.ttf",
            self.assets / "sg1-glyphs.ttf",
        ]
        for path in candidates:
            if path.exists():
                return path
        return None

    def _render_text_safe(
        self,
        font: pygame.font.Font,
        text: str,
        color: Tuple[int, int, int],
        fallback_text: str = "?",
        fallback_font: Optional[pygame.font.Font] = None,
    ) -> pygame.Surface:
        fallback_font = fallback_font or self.font_sm
        attempt = text if text else fallback_text
        try:
            surface = font.render(attempt, True, color)
            if surface.get_width() > 0:
                return surface
        except pygame.error:
            pass
        try:
            return fallback_font.render(fallback_text or "?", True, color)
        except pygame.error:
            return pygame.font.Font(None, 24).render("?", True, color)

    def _rebuild_layout(self) -> None:
        width, height = self.screen.get_size()
        margin = max(18, int(min(width, height) * 0.018))

        right_width = int(width * 0.35)
        right_width = max(460, min(640, right_width))
        right_width = min(right_width, width - margin * 3 - 300)

        self.panel_rect = pygame.Rect(
            width - right_width - margin,
            margin,
            right_width,
            height - margin * 2,
        )

        self.left_view_rect = pygame.Rect(
            margin,
            margin,
            self.panel_rect.left - margin * 2,
            height - margin * 2,
        )

        gate_outer = int(min(self.left_view_rect.width * 0.45, self.left_view_rect.height * 0.41))
        gate_outer = max(170, gate_outer)
        self.gate_center = (
            self.left_view_rect.centerx,
            int(self.left_view_rect.centery + self.left_view_rect.height * 0.03),
        )
        self.gate_outer_radius = gate_outer
        self.gate_ring_radius = int(gate_outer * 0.83)
        self.gate_inner_radius = int(gate_outer * 0.64)

        dhd_radius = int(min(self.panel_rect.width * 0.40, self.panel_rect.height * 0.29))
        dhd_center = (
            self.panel_rect.centerx,
            int(self.panel_rect.top + self.panel_rect.height * 0.55),
        )
        self.dhd.set_geometry(dhd_center, dhd_radius)
        self._build_buttons()

    def _build_buttons(self) -> None:
        gap = 10
        top_y = self.panel_rect.top + 82
        preset_w = int((self.panel_rect.width - gap * 5) / 4)
        preset_h = 42
        self.preset_buttons = []
        x = self.panel_rect.left + gap
        for name in KNOWN_ADDRESSES:
            rect = pygame.Rect(x, top_y, preset_w, preset_h)
            self.preset_buttons.append(Button(rect=rect, label=name, action="preset", payload=name))
            x += preset_w + gap

        control_h = 46
        control_gap = 10
        small_w = int((self.panel_rect.width - control_gap * 5 - 170) / 3)
        bottom_y = self.panel_rect.bottom - control_h - 14
        x = self.panel_rect.left + control_gap
        self.controls = [
            Button(rect=pygame.Rect(x, bottom_y, small_w, control_h), label="BACK", action="back"),
            Button(
                rect=pygame.Rect(x + small_w + control_gap, bottom_y, small_w, control_h),
                label="CLEAR",
                action="clear",
            ),
            Button(
                rect=pygame.Rect(x + (small_w + control_gap) * 2, bottom_y, small_w, control_h),
                label="DIAL",
                action="dial",
            ),
            Button(
                rect=pygame.Rect(self.panel_rect.right - 170 - control_gap, bottom_y, 170, control_h),
                label="CLOSE GATE",
                action="close",
            ),
        ]

    def run(self) -> None:
        while self.running:
            try:
                dt = self.clock.tick(FPS) / 1000.0
                self._handle_events()
                self._update(dt)
                self._draw()
                pygame.display.flip()
            except Exception as exc:
                self.logger.exception("Frame execution failed", exc)
                self.status = f"Runtime error logged: {exc.__class__.__name__}"
                self.running = False
        self.logger.info("Application shutting down")
        self.audio.stop_loop()
        pygame.quit()

    def _handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.VIDEORESIZE:
                self.screen = pygame.display.set_mode(event.size, pygame.RESIZABLE)
                self._rebuild_layout()
                self.logger.info("Window resized", width=event.w, height=event.h)
            elif event.type == pygame.MOUSEMOTION:
                self._handle_hover(event.pos)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self._handle_click(event.pos)
            elif event.type == pygame.KEYDOWN:
                self._handle_key(event.key)

    def _handle_hover(self, pos: Tuple[int, int]) -> None:
        kind, idx = self.dhd.hit_test(pos)
        self.hovered_symbol = idx if kind == "symbol" else None

    def _handle_click(self, pos: Tuple[int, int]) -> None:
        for btn in self.preset_buttons + self.controls:
            if btn.rect.collidepoint(pos):
                self._activate(btn)
                return

        kind, idx = self.dhd.hit_test(pos)
        if kind == "symbol" and idx is not None:
            self._add_symbol(idx)
        elif kind == "center":
            self._start_dial()

    def _handle_key(self, key: int) -> None:
        if pygame.K_1 <= key <= pygame.K_9:
            idx = key - pygame.K_1
            self._add_symbol(idx)
        elif key == pygame.K_RETURN:
            self._start_dial()
        elif key == pygame.K_BACKSPACE:
            self._remove_symbol()
        elif key == pygame.K_DELETE:
            self._clear_symbols()
        elif key == pygame.K_ESCAPE:
            self._close_gate()

    def _activate(self, btn: Button) -> None:
        if btn.action == "dial":
            self._start_dial()
        elif btn.action == "back":
            self._remove_symbol()
        elif btn.action == "clear":
            self._clear_symbols()
        elif btn.action == "close":
            self._close_gate()
        elif btn.action == "preset" and isinstance(btn.payload, str):
            self._load_preset(btn.payload)

    def _add_symbol(self, idx: int) -> None:
        if self.state != "IDLE":
            self.audio.play("error")
            return
        if len(self.entered_symbols) >= MAX_ADDRESS_LENGTH:
            self.status = "Address full (max 9 symbols)."
            self.audio.play("error")
            return
        if idx < 0 or idx >= SYMBOL_COUNT:
            return
        self.entered_symbols.append(idx)
        self.audio.play("press")
        self.status = f"Selected {len(self.entered_symbols)} symbols."

    def _remove_symbol(self) -> None:
        if self.state != "IDLE":
            return
        if self.entered_symbols:
            self.entered_symbols.pop()
            self.audio.play("press")
            self.status = f"Selected {len(self.entered_symbols)} symbols."

    def _clear_symbols(self) -> None:
        if self.state != "IDLE":
            return
        self.entered_symbols.clear()
        self.audio.play("press")
        self.status = "Address cleared."

    def _load_preset(self, name: str) -> None:
        if self.state != "IDLE":
            self.audio.play("error")
            return
        self.entered_symbols = KNOWN_ADDRESSES[name].copy()
        self.audio.play("press")
        self.status = f"Loaded preset: {name}."
        self.logger.info("Preset loaded", preset=name, symbols=len(self.entered_symbols))

    def _start_dial(self) -> None:
        if self.state != "IDLE":
            self.audio.play("error")
            return
        if len(self.entered_symbols) < MIN_ADDRESS_LENGTH:
            self.status = "Need at least 7 symbols to dial."
            self.audio.play("error")
            return
        self.current_address = self.entered_symbols.copy()
        self.locked_count = 0
        self.state = "DIALING"
        self.next_lock_at = pygame.time.get_ticks() + 420
        self.status = "Dialing sequence started."
        self.audio.play("engage")
        self.audio.start_loop("ring")
        self.logger.info("Dialing started", length=len(self.current_address), address=self.current_address)

    def _close_gate(self) -> None:
        if self.state == "IDLE":
            self.status = "Gate already idle."
            return
        self.audio.stop_loop()
        self.state = "IDLE"
        self.locked_count = 0
        self.current_address.clear()
        self.entered_symbols.clear()
        self.ring_angle = 0.0
        self.status = "Gate closed."
        self.audio.play("close")
        self.logger.info("Gate closed")

    def _update(self, dt: float) -> None:
        now = pygame.time.get_ticks()
        if self.state == "DIALING":
            self.ring_angle = (self.ring_angle + 158.0 * dt) % 360.0
            if now >= self.next_lock_at:
                self.locked_count += 1
                self.audio.play("lock")
                if self.locked_count >= len(self.current_address):
                    self.state = "OPENING"
                    self.open_finish_at = now + 1100
                    self.status = "Chevron lock complete. Opening wormhole..."
                    self.audio.stop_loop()
                    self.audio.play("kawoosh")
                    self.logger.info("Dialing complete, opening wormhole")
                else:
                    self.next_lock_at = now + 550
                    self.status = (
                        f"Chevron {self.locked_count} locked "
                        f"of {len(self.current_address)}."
                    )
        elif self.state == "OPENING":
            if now >= self.open_finish_at:
                self.state = "CONNECTED"
                self.connected_since = now
                self.status = "Wormhole established. Gate is active."
                self.audio.play("connected")
                self.logger.info("Wormhole connected")
        elif self.state == "CONNECTED":
            active_seconds = (now - self.connected_since) / 1000.0
            self.status = f"Wormhole active for {active_seconds:04.1f}s."

    def _draw(self) -> None:
        now = pygame.time.get_ticks() / 1000.0
        self._draw_background(now)
        self._draw_stargate(now)
        self._draw_console(now)

    def _draw_background(self, now: float) -> None:
        h = WINDOW_SIZE[1]
        for y in range(h):
            blend = y / h
            r = int(7 + 24 * blend)
            g = int(10 + 21 * blend)
            b = int(26 + 33 * blend)
            pygame.draw.line(self.screen, (r, g, b), (0, y), (WINDOW_SIZE[0], y))

        nebula = pygame.Surface(WINDOW_SIZE, pygame.SRCALPHA)
        for cx, cy, radius, phase in ((280, 180, 270, 0.7), (560, 680, 350, 1.2), (1240, 180, 260, 0.4)):
            glow = 30 + int(18 * (1 + math.sin(now + phase)))
            pygame.draw.circle(nebula, (26, 62, 112, glow), (cx, cy), radius)
        self.screen.blit(nebula, (0, 0))

        for x, y, size, phase in self.stars:
            twinkle = 130 + int(120 * (0.5 + 0.5 * math.sin(now * 1.4 + phase)))
            color = (twinkle, twinkle, 255)
            pygame.draw.circle(self.screen, color, (x, y), size)

    def _draw_stargate(self, now: float) -> None:
        center = self.gate_center
        outer_radius = self.gate_outer_radius
        ring_radius = self.gate_ring_radius
        inner_radius = self.gate_inner_radius

        frame_rect = pygame.Rect(
            self.left_view_rect.left + 6,
            self.left_view_rect.top + 6,
            self.left_view_rect.width - 12,
            self.left_view_rect.height - 12,
        )
        pygame.draw.rect(self.screen, (16, 21, 29), frame_rect, border_radius=16)
        pygame.draw.rect(self.screen, (44, 56, 72), frame_rect, width=2, border_radius=16)

        pygame.draw.circle(self.screen, (112, 118, 128), center, outer_radius)
        pygame.draw.circle(self.screen, (67, 73, 82), center, outer_radius - 16)
        pygame.draw.circle(self.screen, (135, 142, 152), center, ring_radius + 14, 24)
        pygame.draw.circle(self.screen, (27, 34, 43), center, inner_radius)

        self._draw_ring_symbols(center, ring_radius, self.ring_angle)
        self._draw_chevrons(center, outer_radius - 20)

        if self.state in {"OPENING", "CONNECTED"}:
            self._draw_wormhole(center, inner_radius - 2, now)

    def _draw_ring_symbols(
        self, center: Tuple[int, int], radius: int, extra_angle: float
    ) -> None:
        cx, cy = center
        for i in range(SYMBOL_COUNT):
            base = i * (360.0 / SYMBOL_COUNT) + extra_angle
            rad = math.radians(base)
            x = cx + math.cos(rad) * radius
            y = cy + math.sin(rad) * radius
            pygame.draw.circle(self.screen, (174, 183, 198), (int(x), int(y)), 4)

    def _draw_chevrons(self, center: Tuple[int, int], radius: int) -> None:
        cx, cy = center
        chevron_count = 9
        for i in range(chevron_count):
            angle = math.radians(-90 + i * (360 / chevron_count))
            x = cx + math.cos(angle) * radius
            y = cy + math.sin(angle) * radius
            lit = i < self.locked_count
            base = (112, 87, 56)
            glow = (255, 150, 50)
            color = glow if lit else base
            points = [
                (int(x), int(y - 14)),
                (int(x - 14), int(y + 12)),
                (int(x + 14), int(y + 12)),
            ]
            pygame.draw.polygon(self.screen, color, points)
            pygame.draw.polygon(self.screen, (36, 29, 18), points, 2)

    def _draw_wormhole(self, center: Tuple[int, int], radius: int, now: float) -> None:
        cx, cy = center
        for layer in range(11):
            phase = now * 2.3 + layer * 0.8
            warp = math.sin(phase) * 8.0
            r = radius - layer * 14 + warp
            color = (24 + layer * 7, 99 + layer * 11, 160 + layer * 10)
            if r > 1:
                pygame.draw.circle(self.screen, color, (cx, cy), int(r))

        for i in range(42):
            a = i * (2 * math.pi / 42) + now * 0.85
            dist = (radius - 30) * (0.35 + 0.65 * ((i % 5) / 4))
            x = cx + math.cos(a) * dist
            y = cy + math.sin(a) * dist
            pygame.draw.circle(self.screen, (195, 236, 255), (int(x), int(y)), 2)

    def _draw_console(self, now: float) -> None:
        panel_rect = self.panel_rect
        pygame.draw.rect(self.screen, (13, 17, 23), panel_rect, border_radius=18)
        pygame.draw.rect(self.screen, (43, 56, 74), panel_rect, width=2, border_radius=18)

        pad_x = panel_rect.left + 26
        title_y = panel_rect.top + 18
        title = self.font_lg.render("STARGATE COMMAND", True, (215, 227, 245))
        subtitle = self.font_sm.render("Dialing Computer + DHD", True, (148, 170, 198))
        self.screen.blit(title, (pad_x, title_y))
        self.screen.blit(subtitle, (pad_x + 2, title_y + 40))

        self.screen.blit(
            self.font_md.render("Address Glyphs:", True, (255, 208, 148)),
            (pad_x, panel_rect.top + 96),
        )
        glyph_string = "".join(self.glyph_chars[i] for i in self.entered_symbols)
        if glyph_string:
            glyph_surface = self._render_text_safe(
                self.glyph_font_lg,
                glyph_string,
                (255, 222, 183),
                fallback_text=" ".join(f"{i + 1:02d}" for i in self.entered_symbols),
                fallback_font=self.font_md,
            )
            self.screen.blit(glyph_surface, (pad_x + 258, panel_rect.top + 88))
        else:
            self.screen.blit(
                self.font_sm.render("<empty>", True, (166, 185, 206)),
                (pad_x + 258, panel_rect.top + 108),
            )

        index_text = " ".join(f"{i + 1:02d}" for i in self.entered_symbols)
        if not index_text:
            index_text = "-"
        self.screen.blit(
            self.font_sm.render(f"Symbol indexes: {index_text}", True, (166, 185, 206)),
            (pad_x, panel_rect.top + 130),
        )

        status_surface = self.font_sm.render(f"Status: {self.status}", True, (170, 190, 214))
        self.screen.blit(status_surface, (pad_x, panel_rect.top + 156))

        if self.hovered_symbol is not None:
            hover_char = self.glyph_chars[self.hovered_symbol]
            hover_label = self._render_text_safe(
                self.glyph_font_md,
                hover_char,
                (248, 205, 147),
                fallback_text=f"{self.hovered_symbol + 1:02d}",
                fallback_font=self.font_md,
            )
            self.screen.blit(
                self.font_sm.render("Hovered symbol:", True, (170, 190, 214)),
                (panel_rect.right - 220, panel_rect.top + 156),
            )
            self.screen.blit(hover_label, (panel_rect.right - 66, panel_rect.top + 145))

        for btn in self.preset_buttons:
            self._draw_pill(btn, (43, 72, 106), (214, 233, 255), hover=btn.rect.collidepoint(pygame.mouse.get_pos()))

        symbol_stage: Dict[int, int] = {}
        for sym in self.entered_symbols:
            symbol_stage[sym] = max(symbol_stage.get(sym, 0), 1)
        for i, sym in enumerate(self.current_address):
            if i < self.locked_count:
                symbol_stage[sym] = 2

        connected = self.state == "CONNECTED"
        pulse = 0.5 + 0.5 * math.sin(now * 2.8)
        self.dhd.draw(
            self.screen,
            hovered_symbol=self.hovered_symbol,
            symbol_stage=symbol_stage,
            pulse=pulse,
            connected=connected,
        )

        for btn in self.controls:
            hover = btn.rect.collidepoint(pygame.mouse.get_pos())
            fill = (89, 56, 34) if not hover else (124, 74, 43)
            text = (255, 226, 194)
            self._draw_pill(btn, fill, text, hover=hover)

        hints = [
            "Center button = DIAL / ENGAGE",
            "1-9: quick symbols 01..09",
            "Enter: DIAL | Backspace: BACK | Delete: CLEAR | Esc: CLOSE",
        ]
        y = self.controls[0].rect.top - 78 if self.controls else panel_rect.bottom - 100
        for line in hints:
            text = self.font_sm.render(line, True, (145, 164, 188))
            self.screen.blit(text, (pad_x, y))
            y += 22

    def _draw_pill(
        self,
        btn: Button,
        fill: Tuple[int, int, int],
        text_color: Tuple[int, int, int],
        hover: bool,
    ) -> None:
        border = (29, 34, 41) if not hover else (250, 198, 128)
        pygame.draw.rect(self.screen, fill, btn.rect, border_radius=12)
        pygame.draw.rect(self.screen, border, btn.rect, width=2, border_radius=12)
        label = self.font_sm.render(btn.label, True, text_color)
        self.screen.blit(label, label.get_rect(center=btn.rect.center))


def main() -> None:
    app: Optional[StargateApp] = None
    try:
        app = StargateApp()
        app.run()
    except Exception as exc:
        if app is not None:
            app.logger.exception("Fatal startup/runtime error", exc)
        else:
            fallback = AppLogger(_runtime_dir())
            fallback.exception("Fatal error before app init", exc)
        raise


if __name__ == "__main__":
    main()
