"""Cross-platform Stargate SG-1 style dialing simulator.

Run:
    python stargate_app.py
"""

from __future__ import annotations

import math
from array import array
from dataclasses import dataclass
from typing import Dict, List, Tuple

import pygame


WINDOW_SIZE = (1280, 800)
FPS = 60
SYMBOL_COUNT = 39
MIN_ADDRESS_LENGTH = 7
MAX_ADDRESS_LENGTH = 9


GLYPHS = [f"S{i:02d}" for i in range(1, SYMBOL_COUNT + 1)]

KNOWN_ADDRESSES: Dict[str, List[int]] = {
    "Abydos": [26, 6, 14, 31, 11, 29, 1],
    "Chulak": [8, 1, 22, 14, 36, 19, 4],
    "Dakara": [17, 28, 4, 35, 9, 21, 2],
    "Earth": [1, 11, 2, 19, 21, 24, 35],
}


@dataclass
class Button:
    rect: pygame.Rect
    label: str
    action: str
    payload: int | str | None = None


class GateAudio:
    def __init__(self) -> None:
        self.enabled = False
        self.sounds: Dict[str, pygame.mixer.Sound] = {}
        try:
            pygame.mixer.pre_init(44100, -16, 1, 512)
            pygame.mixer.init()
            self.sounds = {
                "press": self._tone(630, 0.06, 0.18),
                "lock": self._tone(520, 0.16, 0.24),
                "error": self._tone(220, 0.20, 0.20),
                "close": self._tone(170, 0.32, 0.22),
                "kawoosh": self._sweep(170, 900, 0.9, 0.28),
            }
            self.enabled = True
        except pygame.error:
            self.enabled = False

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
            p = i / max(1, frame_count - 1)
            freq = start_freq + (end_freq - start_freq) * p
            t = i / sample_rate
            sample = math.sin(2 * math.pi * freq * t)
            envelope = min(1.0, p * 4.0) * max(0.0, 1.0 - p * 0.7)
            pcm.append(int(sample * 32767 * volume * envelope))
        return pygame.mixer.Sound(buffer=pcm)

    def play(self, name: str) -> None:
        if not self.enabled:
            return
        snd = self.sounds.get(name)
        if snd:
            snd.play()


class StargateApp:
    def __init__(self) -> None:
        pygame.init()
        self.screen = pygame.display.set_mode(WINDOW_SIZE)
        pygame.display.set_caption("Stargate Dialing Computer + DHD")
        self.clock = pygame.time.Clock()

        self.font_sm = pygame.font.SysFont("consolas", 18)
        self.font_md = pygame.font.SysFont("consolas", 24, bold=True)
        self.font_lg = pygame.font.SysFont("consolas", 30, bold=True)

        self.audio = GateAudio()
        self.buttons: List[Button] = []
        self.preset_buttons: List[Button] = []
        self._build_buttons()

        self.running = True
        self.status = "Idle. Select 7-9 symbols then press DIAL."
        self.entered_symbols: List[int] = []
        self.current_address: List[int] = []
        self.locked_count = 0
        self.state = "IDLE"  # IDLE, DIALING, OPENING, CONNECTED

        self.ring_angle = 0.0
        self.next_lock_at = 0
        self.open_finish_at = 0
        self.connected_since = 0

    def _build_buttons(self) -> None:
        start_x = 760
        start_y = 180
        cols = 6
        rows = 7
        btn_w = 72
        btn_h = 58
        gap = 9

        idx = 0
        for row in range(rows):
            for col in range(cols):
                if idx >= SYMBOL_COUNT:
                    break
                x = start_x + col * (btn_w + gap)
                y = start_y + row * (btn_h + gap)
                rect = pygame.Rect(x, y, btn_w, btn_h)
                self.buttons.append(
                    Button(rect=rect, label=GLYPHS[idx], action="glyph", payload=idx)
                )
                idx += 1

        controls_y = start_y + rows * (btn_h + gap) + 18
        self.buttons.extend(
            [
                Button(
                    rect=pygame.Rect(start_x, controls_y, 150, 54),
                    label="DIAL",
                    action="dial",
                ),
                Button(
                    rect=pygame.Rect(start_x + 162, controls_y, 150, 54),
                    label="BACK",
                    action="back",
                ),
                Button(
                    rect=pygame.Rect(start_x + 324, controls_y, 150, 54),
                    label="CLEAR",
                    action="clear",
                ),
                Button(
                    rect=pygame.Rect(start_x, controls_y + 64, 474, 54),
                    label="CLOSE GATE",
                    action="close",
                ),
            ]
        )

        px = 760
        py = 38
        for name in KNOWN_ADDRESSES:
            rect = pygame.Rect(px, py, 116, 38)
            self.preset_buttons.append(
                Button(rect=rect, label=name, action="preset", payload=name)
            )
            px += 122

    def run(self) -> None:
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0
            self._handle_events()
            self._update(dt)
            self._draw()
            pygame.display.flip()
        pygame.quit()

    def _handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self._handle_click(event.pos)
            elif event.type == pygame.KEYDOWN:
                self._handle_key(event.key)

    def _handle_click(self, pos: Tuple[int, int]) -> None:
        for btn in self.preset_buttons + self.buttons:
            if btn.rect.collidepoint(pos):
                self._activate(btn)
                return

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
        if btn.action == "glyph":
            self._add_symbol(int(btn.payload))
        elif btn.action == "dial":
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
        self.next_lock_at = pygame.time.get_ticks() + 450
        self.status = "Dialing sequence started."
        self.audio.play("press")

    def _close_gate(self) -> None:
        if self.state == "IDLE":
            self.status = "Gate already idle."
            return
        self.state = "IDLE"
        self.locked_count = 0
        self.current_address.clear()
        self.entered_symbols.clear()
        self.ring_angle = 0.0
        self.status = "Gate closed."
        self.audio.play("close")

    def _update(self, dt: float) -> None:
        now = pygame.time.get_ticks()
        if self.state == "DIALING":
            self.ring_angle = (self.ring_angle + 150.0 * dt) % 360.0
            if now >= self.next_lock_at:
                self.locked_count += 1
                self.audio.play("lock")
                if self.locked_count >= len(self.current_address):
                    self.state = "OPENING"
                    self.open_finish_at = now + 1100
                    self.status = "Chevron lock complete. Opening wormhole..."
                    self.audio.play("kawoosh")
                else:
                    self.next_lock_at = now + 560
                    self.status = (
                        f"Chevron {self.locked_count} locked "
                        f"of {len(self.current_address)}."
                    )
        elif self.state == "OPENING":
            if now >= self.open_finish_at:
                self.state = "CONNECTED"
                self.connected_since = now
                self.status = "Wormhole established. Gate is active."
        elif self.state == "CONNECTED":
            active_seconds = (now - self.connected_since) / 1000.0
            self.status = f"Wormhole active for {active_seconds:04.1f}s."

    def _draw(self) -> None:
        self._draw_background()
        self._draw_stargate()
        self._draw_panel()

    def _draw_background(self) -> None:
        h = WINDOW_SIZE[1]
        for y in range(h):
            blend = y / h
            r = int(8 + 12 * blend)
            g = int(12 + 16 * blend)
            b = int(24 + 30 * blend)
            pygame.draw.line(self.screen, (r, g, b), (0, y), (WINDOW_SIZE[0], y))

    def _draw_stargate(self) -> None:
        center = (360, 400)
        outer_radius = 275
        ring_radius = 240
        inner_radius = 185

        pygame.draw.circle(self.screen, (92, 99, 110), center, outer_radius)
        pygame.draw.circle(self.screen, (46, 52, 62), center, outer_radius - 16)
        pygame.draw.circle(self.screen, (110, 118, 130), center, ring_radius + 14, 22)
        pygame.draw.circle(self.screen, (22, 28, 36), center, inner_radius)

        time_s = pygame.time.get_ticks() / 1000.0
        self._draw_ring_symbols(center, ring_radius, self.ring_angle)
        self._draw_chevrons(center, outer_radius - 20)

        if self.state in {"OPENING", "CONNECTED"}:
            self._draw_wormhole(center, inner_radius - 3, time_s)

    def _draw_ring_symbols(
        self, center: Tuple[int, int], radius: int, extra_angle: float
    ) -> None:
        cx, cy = center
        for i in range(SYMBOL_COUNT):
            base = i * (360.0 / SYMBOL_COUNT) + extra_angle
            rad = math.radians(base)
            x = cx + math.cos(rad) * radius
            y = cy + math.sin(rad) * radius
            color = (168, 176, 189)
            pygame.draw.circle(self.screen, color, (int(x), int(y)), 4)

    def _draw_chevrons(self, center: Tuple[int, int], radius: int) -> None:
        cx, cy = center
        chevron_count = 9
        for i in range(chevron_count):
            angle = math.radians(-90 + i * (360 / chevron_count))
            x = cx + math.cos(angle) * radius
            y = cy + math.sin(angle) * radius
            lit = i < self.locked_count
            color = (255, 145, 46) if lit else (96, 80, 52)
            pygame.draw.polygon(
                self.screen,
                color,
                [
                    (int(x), int(y - 12)),
                    (int(x - 12), int(y + 10)),
                    (int(x + 12), int(y + 10)),
                ],
            )

    def _draw_wormhole(
        self, center: Tuple[int, int], radius: int, time_s: float
    ) -> None:
        cx, cy = center
        for layer in range(9):
            phase = time_s * 2.2 + layer * 0.8
            warp = math.sin(phase) * 7.0
            r = radius - layer * 14 + warp
            color = (
                28 + layer * 6,
                105 + layer * 10,
                160 + layer * 10,
            )
            if r > 1:
                pygame.draw.circle(self.screen, color, (cx, cy), int(r))

        sparkle_count = 36
        for i in range(sparkle_count):
            a = i * (2 * math.pi / sparkle_count) + time_s * 0.8
            dist = (radius - 40) * (0.3 + 0.7 * ((i % 5) / 4))
            x = cx + math.cos(a) * dist
            y = cy + math.sin(a) * dist
            pygame.draw.circle(self.screen, (190, 232, 255), (int(x), int(y)), 2)

    def _draw_panel(self) -> None:
        panel_rect = pygame.Rect(720, 20, 540, 760)
        pygame.draw.rect(self.screen, (18, 22, 28), panel_rect, border_radius=12)
        pygame.draw.rect(self.screen, (42, 49, 57), panel_rect, width=2, border_radius=12)

        title = self.font_lg.render("DIALING COMPUTER + DHD", True, (225, 235, 245))
        self.screen.blit(title, (742, 90))

        addr_labels = [GLYPHS[i] for i in self.entered_symbols]
        addr_text = " ".join(addr_labels) if addr_labels else "<empty>"
        addr_surface = self.font_md.render(f"Address: {addr_text}", True, (255, 205, 140))
        self.screen.blit(addr_surface, (742, 138))

        status_surface = self.font_sm.render(f"Status: {self.status}", True, (183, 202, 219))
        self.screen.blit(status_surface, (742, 160))

        for btn in self.preset_buttons:
            self._draw_button(btn, fill=(45, 58, 74), text_color=(213, 226, 238))

        mouse = pygame.mouse.get_pos()
        for btn in self.buttons:
            hover = btn.rect.collidepoint(mouse)
            if btn.action == "glyph":
                fill = (57, 64, 75) if not hover else (82, 92, 108)
                text = (202, 222, 241)
            else:
                fill = (102, 58, 31) if not hover else (136, 76, 40)
                text = (255, 229, 198)
            self._draw_button(btn, fill=fill, text_color=text)

        help_lines = [
            "Keyboard shortcuts:",
            "1-9 = quick symbols S01..S09",
            "Enter = DIAL, Backspace = BACK",
            "Delete = CLEAR, Esc = CLOSE GATE",
        ]
        y = 708
        for line in help_lines:
            txt = self.font_sm.render(line, True, (160, 178, 194))
            self.screen.blit(txt, (742, y))
            y += 20

    def _draw_button(
        self, btn: Button, fill: Tuple[int, int, int], text_color: Tuple[int, int, int]
    ) -> None:
        pygame.draw.rect(self.screen, fill, btn.rect, border_radius=8)
        pygame.draw.rect(self.screen, (28, 33, 38), btn.rect, width=2, border_radius=8)
        label = self.font_sm.render(btn.label, True, text_color)
        self.screen.blit(label, label.get_rect(center=btn.rect.center))


def main() -> None:
    app = StargateApp()
    app.run()


if __name__ == "__main__":
    main()
