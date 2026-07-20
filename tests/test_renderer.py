from pathlib import Path
import struct

from devotional_image_studio import CardRenderer, RenderRequest
from renderer import CardRenderer as ShimRenderer


def png_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    assert data.startswith(b"\x89PNG\r\n\x1a\n")
    return struct.unpack("!II", data[16:24])


def test_renderer_generates_png(tmp_path: Path) -> None:
    renderer = CardRenderer(output_dir=tmp_path, size=(320, 480))
    result = renderer.render(deity="Lakshmi", greeting="Shubh Deepavali", message="Light, love, and abundance.")

    assert result.output_path.exists()
    assert result.width == 320
    assert result.height == 480
    assert png_size(result.output_path) == (320, 480)


def test_compatibility_entrypoints(tmp_path: Path) -> None:
    request = RenderRequest(output_path="card.png", size=(256, 384))
    assert ShimRenderer(output_dir=tmp_path).render_card(request).output_path == tmp_path / "card.png"
