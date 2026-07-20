"""Integrated devotional greeting card renderer."""

from __future__ import annotations

from dataclasses import dataclass, field, fields, is_dataclass
from pathlib import Path
from typing import Any, Mapping, MutableMapping
import struct
import textwrap
import zlib

try:  # Pillow path used in normal installations.
    from PIL import Image, ImageColor, ImageDraw, ImageFilter, ImageFont, ImageOps
except ImportError:  # Minimal fallback keeps renderer runnable in constrained envs.
    Image = ImageColor = ImageDraw = ImageFilter = ImageFont = ImageOps = None  # type: ignore[assignment]

Color = tuple[int, int, int] | tuple[int, int, int, int] | str


@dataclass(slots=True)
class RenderRequest:
    deity: str = "Shree Ganesh"
    greeting: str = "Blessings"
    message: str = "May divine grace bring peace, prosperity, and joy."
    output_path: str | Path = "devotional_card.png"
    size: tuple[int, int] = (1024, 1536)
    background_path: str | Path | None = None
    accent_color: Color = (255, 183, 77)
    text_color: Color = (255, 250, 230)
    font_path: str | Path | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RenderResult:
    output_path: Path
    width: int
    height: int


class AttrDict(dict):
    def __getattr__(self, key: str) -> Any:
        try:
            return self[key]
        except KeyError as exc:
            raise AttributeError(key) from exc

    def __setattr__(self, key: str, value: Any) -> None:
        self[key] = value


def _as_request(value: RenderRequest | Mapping[str, Any] | None, overrides: Mapping[str, Any]) -> RenderRequest:
    data: MutableMapping[str, Any]
    if value is None:
        data = {}
    elif isinstance(value, RenderRequest):
        data = {item.name: getattr(value, item.name) for item in fields(RenderRequest)}
    elif is_dataclass(value):
        data = {item.name: getattr(value, item.name) for item in fields(value)}
    elif isinstance(value, Mapping):
        data = dict(value)
    else:
        data = dict(getattr(value, "__dict__", {}))
    data.update({key: val for key, val in overrides.items() if val is not None})
    allowed = {item.name for item in fields(RenderRequest)}
    return RenderRequest(**{key: val for key, val in data.items() if key in allowed})


class CardRenderer:
    def __init__(self, output_dir: str | Path = ".", size: tuple[int, int] = (1024, 1536), font_path: str | Path | None = None, comfy_client: Any | None = None, **_: Any) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.size = size
        self.font_path = Path(font_path) if font_path else None
        self.comfy_client = comfy_client

    def render(self, request: RenderRequest | Mapping[str, Any] | None = None, **kwargs: Any) -> RenderResult:
        req = _as_request(request, kwargs)
        if "size" not in kwargs and request is None:
            req.size = self.size
        if req.font_path is None:
            req.font_path = self.font_path
        output_path = Path(req.output_path)
        if not output_path.is_absolute():
            output_path = self.output_dir / output_path
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if Image is None:
            _write_fallback_png(output_path, req.size, req.accent_color)
            return RenderResult(output_path=output_path, width=req.size[0], height=req.size[1])

        image = self._create_background(req)
        self._paint_overlay(image, req)
        self._paint_deity_symbol(image, req)
        self._paint_text(image, req)
        image.save(output_path, format="PNG")
        return RenderResult(output_path=output_path, width=image.width, height=image.height)

    def render_card(self, *args: Any, **kwargs: Any) -> RenderResult:
        return self.render(*args, **kwargs)

    def generate(self, *args: Any, **kwargs: Any) -> RenderResult:
        return self.render(*args, **kwargs)

    def _create_background(self, req: RenderRequest) -> Any:
        if req.background_path:
            source = Image.open(req.background_path).convert("RGB")
            return ImageOps.fit(source, req.size, method=Image.Resampling.LANCZOS).convert("RGBA")
        width, height = req.size
        base = Image.new("RGBA", req.size)
        pixels = base.load()
        top, mid, bottom = (78, 25, 99), (168, 67, 45), (32, 10, 54)
        for y in range(height):
            t = y / max(height - 1, 1)
            if t < 0.58:
                local = t / 0.58
                color = tuple(int(top[i] * (1 - local) + mid[i] * local) for i in range(3))
            else:
                local = (t - 0.58) / 0.42
                color = tuple(int(mid[i] * (1 - local) + bottom[i] * local) for i in range(3))
            for x in range(width):
                pixels[x, y] = (*color, 255)
        return base.filter(ImageFilter.GaussianBlur(radius=0.4))

    def _paint_overlay(self, image: Any, req: RenderRequest) -> None:
        draw = ImageDraw.Draw(image, "RGBA")
        width, height = image.size
        accent = self._rgba(req.accent_color, 95)
        for radius in range(70, min(width, height), 95):
            alpha = max(8, 70 - radius // 14)
            draw.ellipse((width / 2 - radius, height * 0.33 - radius, width / 2 + radius, height * 0.33 + radius), outline=(*accent[:3], alpha), width=3)
        draw.rectangle((0, 0, width, height), fill=(0, 0, 0, 46))
        draw.rectangle((0, int(height * 0.68), width, height), fill=(0, 0, 0, 92))

    def _paint_deity_symbol(self, image: Any, req: RenderRequest) -> None:
        draw = ImageDraw.Draw(image, "RGBA")
        width, height = image.size
        accent = self._rgba(req.accent_color, 230)
        font = self._font(max(72, width // 7), req.font_path)
        symbol = "ॐ"
        box = draw.textbbox((0, 0), symbol, font=font)
        x, y = (width - (box[2] - box[0])) / 2, height * 0.23
        glow = Image.new("RGBA", image.size, (0, 0, 0, 0))
        ImageDraw.Draw(glow).text((x, y), symbol, font=font, fill=(*accent[:3], 150))
        image.alpha_composite(glow.filter(ImageFilter.GaussianBlur(radius=18)))
        draw.text((x, y), symbol, font=font, fill=accent)

    def _paint_text(self, image: Any, req: RenderRequest) -> None:
        draw = ImageDraw.Draw(image, "RGBA")
        width, height = image.size
        title_font = self._font(max(46, width // 14), req.font_path)
        deity_font = self._font(max(60, width // 11), req.font_path)
        body_font = self._font(max(30, width // 31), req.font_path)
        text, accent = self._rgba(req.text_color, 255), self._rgba(req.accent_color, 255)
        self._center_text(draw, req.greeting, title_font, width, int(height * 0.63), accent)
        self._center_text(draw, req.deity, deity_font, width, int(height * 0.70), text)
        y = int(height * 0.80)
        for line in textwrap.wrap(req.message, width=max(24, width // 34))[:4]:
            self._center_text(draw, line, body_font, width, y, text)
            y += int(getattr(body_font, "size", 32) * 1.35)

    def _center_text(self, draw: Any, value: str, font: Any, width: int, y: int, fill: Color) -> None:
        box = draw.textbbox((0, 0), value, font=font)
        draw.text(((width - (box[2] - box[0])) / 2, y), value, font=font, fill=fill)

    def _font(self, size: int, font_path: str | Path | None = None) -> Any:
        for candidate in [font_path, "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]:
            if candidate and Path(candidate).exists():
                return ImageFont.truetype(str(candidate), size=size)
        return ImageFont.load_default()

    def _rgba(self, color: Color, alpha: int) -> tuple[int, int, int, int]:
        if isinstance(color, str):
            parsed = ImageColor.getrgb(color)
            return (*parsed[:3], alpha)
        if len(color) == 4:
            return (int(color[0]), int(color[1]), int(color[2]), int(color[3]))
        return (int(color[0]), int(color[1]), int(color[2]), alpha)


def _write_fallback_png(path: Path, size: tuple[int, int], accent_color: Color) -> None:
    width, height = size
    accent = _simple_rgb(accent_color)
    rows = []
    for y in range(height):
        t = y / max(height - 1, 1)
        r = int(58 * (1 - t) + accent[0] * t * 0.65)
        g = int(18 * (1 - t) + accent[1] * t * 0.45)
        b = int(78 * (1 - t) + accent[2] * t * 0.35)
        rows.append(b"\x00" + bytes((r, g, b)) * width)
    raw = b"".join(rows)
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack("!I", len(data)) + kind + data + struct.pack("!I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack("!IIBBBBB", width, height, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")
    path.write_bytes(png)


def _simple_rgb(color: Color) -> tuple[int, int, int]:
    if isinstance(color, str):
        return (255, 183, 77)
    return (int(color[0]), int(color[1]), int(color[2]))
