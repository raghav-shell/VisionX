"""Procedural overhead-reconnaissance chip generator.

Renders top-down silhouettes of six object classes over procedurally textured terrain with cast
shadows, clutter, occasional cloud, per-sensor noise / white balance / blur and illumination
variation. Every image is a pure function of its :class:`ChipSpec`, and every spec is drawn from a
seeded generator, so a corpus is exactly reproducible from its seed.

This is synthetic data. It exists to give the attack lab exact ground truth; detector performance
on it is not a claim about operational imagery.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

CLASSES = ("armoured_vehicle", "truck", "civilian_vehicle", "aircraft", "vessel", "helicopter")
LAND_TERRAINS = ("grassland", "forest", "desert", "urban", "tarmac")
TERRAINS = LAND_TERRAINS + ("water",)
SS = 4  # supersampling factor


@dataclass(frozen=True)
class SensorModel:
    name: str
    noise: float
    gain: tuple[float, float, float]
    blur: float
    kind: str


SENSORS: dict[str, SensorModel] = {
    "EO-A2": SensorModel("EO-A2", 3.0, (1.00, 1.00, 1.00), 0.0, "electro-optical"),
    "EO-B1": SensorModel("EO-B1", 4.5, (1.05, 1.00, 0.94), 0.0, "electro-optical"),
    "UAV-C3": SensorModel("UAV-C3", 4.0, (1.00, 1.02, 0.98), 0.5, "uav"),
    "SAT-D4": SensorModel("SAT-D4", 2.5, (0.96, 1.00, 1.05), 0.3, "satellite"),
    "UAV-X9": SensorModel("UAV-X9", 3.5, (1.02, 0.99, 1.00), 0.2, "uav"),
}

_TERRAIN_PALETTE = {
    "grassland": ((78, 104, 52), (112, 132, 70), 0.55),
    "forest": ((38, 66, 34), (62, 92, 48), 0.75),
    "desert": ((186, 160, 118), (206, 184, 140), 0.45),
    "urban": ((122, 122, 118), (150, 148, 142), 0.5),
    "tarmac": ((88, 90, 92), (108, 110, 112), 0.35),
    "water": ((36, 66, 92), (52, 86, 112), 0.4),
}

_BODY_COLOURS = {
    "armoured_vehicle": [(92, 98, 62), (104, 96, 70), (84, 88, 78), (120, 110, 80)],
    "truck": [(88, 92, 60), (150, 132, 98), (196, 196, 190), (70, 90, 120), (110, 108, 96)],
    "civilian_vehicle": [(170, 40, 40), (40, 70, 150), (220, 220, 215), (170, 172, 176), (30, 30, 34), (200, 160, 40)],
    "aircraft": [(200, 202, 206), (160, 164, 168), (110, 114, 120), (228, 228, 230)],
    "vessel": [(150, 154, 160), (205, 205, 208), (90, 96, 104), (120, 90, 70)],
    "helicopter": [(80, 88, 60), (100, 104, 108), (60, 64, 58), (130, 128, 112)],
}


@dataclass
class ChipSpec:
    cls: str
    terrain: str
    angle: float
    scale: float
    dx: float
    dy: float
    colour: tuple[int, int, int]
    sun_angle: float
    shadow: float
    sensor: str
    brightness: float
    gamma: float
    clutter: int
    cloud: float
    seed: int
    shape: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def sample_spec(rng: np.random.Generator, cls: str | None = None, *, terrain: str | None = None,
                sensor: str = "EO-A2", terrain_weights: dict[str, float] | None = None,
                class_weights: dict[str, float] | None = None) -> ChipSpec:
    if cls is None:
        names = list(CLASSES)
        w = np.array([(class_weights or {}).get(c, 1.0) for c in names], dtype=float)
        cls = names[int(rng.choice(len(names), p=w / w.sum()))]
    if terrain is None:
        if cls == "vessel":
            terrain = "water"
        else:
            names = list(LAND_TERRAINS)
            w = np.array([(terrain_weights or {}).get(t, 1.0) for t in names], dtype=float)
            terrain = names[int(rng.choice(len(names), p=w / w.sum()))]
    palette = _BODY_COLOURS[cls]
    base = palette[int(rng.integers(len(palette)))]
    colour = tuple(int(np.clip(c + rng.normal(0, 8), 0, 255)) for c in base)
    shape = {
        "L": float(rng.uniform(0.9, 1.1)), "W": float(rng.uniform(0.9, 1.1)),
        "turret": float(rng.uniform(-0.7, 0.7)), "detail": float(rng.uniform(0, 1)),
        "rotor": float(rng.uniform(0, math.pi)),
    }
    return ChipSpec(
        cls=cls, terrain=terrain, angle=float(rng.uniform(0, 2 * math.pi)), scale=float(rng.uniform(0.82, 1.15)),
        dx=float(rng.uniform(-6, 6)), dy=float(rng.uniform(-6, 6)), colour=colour,  # type: ignore[arg-type]
        sun_angle=float(rng.uniform(0, 2 * math.pi)), shadow=float(rng.uniform(1.2, 3.0)), sensor=sensor,
        brightness=float(rng.uniform(0.86, 1.14)), gamma=float(rng.uniform(0.9, 1.1)),
        clutter=int(rng.integers(0, 6)), cloud=float(rng.uniform(0.3, 0.6)) if rng.random() < 0.07 else 0.0,
        seed=int(rng.integers(0, 2**31 - 1)), shape=shape,
    )


# ----------------------------------------------------------------------------- terrain

def _value_noise(rng: np.random.Generator, size: int, octaves: tuple[int, ...]) -> np.ndarray:
    acc = np.zeros((size, size), dtype=np.float32)
    total = 0.0
    for i, cells in enumerate(octaves):
        grid = rng.random((cells, cells)).astype(np.float32)
        layer = np.asarray(Image.fromarray(grid, mode="F").resize((size, size), Image.Resampling.BICUBIC))
        weight = 0.55 ** i
        acc += layer * weight
        total += weight
    acc /= total
    return (acc - acc.min()) / max(float(np.ptp(acc)), 1e-6)


def _terrain(spec: ChipSpec, rng: np.random.Generator, size: int) -> Image.Image:
    lo, hi, rough = _TERRAIN_PALETTE[spec.terrain]
    n = _value_noise(rng, size, (3, 6, 12, 24))
    fine = _value_noise(rng, size, (32,))
    t = np.clip(n * rough + fine * (1 - rough) * 0.6, 0, 1)[..., None]
    img = np.asarray(lo, np.float32) * (1 - t) + np.asarray(hi, np.float32) * t
    canvas = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))
    draw = ImageDraw.Draw(canvas, "RGBA")
    if spec.terrain == "urban":
        for _ in range(int(rng.integers(2, 6))):
            x0, y0 = rng.uniform(0, size, 2)
            w, h = rng.uniform(size * 0.12, size * 0.35, 2)
            shade = int(rng.integers(95, 175))
            draw.rectangle([x0, y0, x0 + w, y0 + h], fill=(shade, shade, shade - 6, 255))
        y = rng.uniform(size * 0.2, size * 0.8)
        draw.rectangle([0, y, size, y + size * 0.06], fill=(70, 70, 72, 255))
    elif spec.terrain == "tarmac":
        for _ in range(int(rng.integers(1, 3))):
            y = rng.uniform(0, size)
            draw.rectangle([0, y, size, y + SS * 0.8], fill=(210, 200, 120, 200))
    elif spec.terrain == "desert":
        for _ in range(int(rng.integers(2, 5))):
            y = rng.uniform(0, size)
            draw.ellipse([-size * 0.2, y, size * 1.2, y + rng.uniform(4, 10) * SS], fill=(170, 146, 106, 70))
    elif spec.terrain == "water":
        for _ in range(int(rng.integers(6, 14))):
            x, y = rng.uniform(0, size, 2)
            draw.line([x, y, x + rng.uniform(4, 12) * SS, y], fill=(70, 100, 125, 110), width=SS)
    return canvas


def _clutter(draw: ImageDraw.ImageDraw, spec: ChipSpec, rng: np.random.Generator, size: int) -> None:
    for _ in range(spec.clutter):
        x, y = rng.uniform(0, size, 2)
        r = rng.uniform(1.0, 3.2) * SS
        if spec.terrain in ("grassland", "forest"):
            fill = (int(rng.integers(25, 60)), int(rng.integers(50, 85)), int(rng.integers(20, 45)), 230)
        elif spec.terrain == "water":
            fill = (60, 90, 110, 120)
        else:
            g = int(rng.integers(70, 150))
            fill = (g, g - 4, g - 10, 220)
        draw.ellipse([x - r, y - r * 0.8, x + r, y + r * 0.8], fill=fill)


# ----------------------------------------------------------------------------- shapes

Poly = list[tuple[float, float]]


def _rect(x0: float, y0: float, x1: float, y1: float) -> Poly:
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def _ellipse(cx: float, cy: float, rx: float, ry: float, n: int = 20) -> Poly:
    return [(cx + rx * math.cos(2 * math.pi * k / n), cy + ry * math.sin(2 * math.pi * k / n)) for k in range(n)]


def _rot(poly: Poly, a: float, cx: float = 0.0, cy: float = 0.0) -> Poly:
    c, s = math.cos(a), math.sin(a)
    return [(cx + (x - cx) * c - (y - cy) * s, cy + (x - cx) * s + (y - cy) * c) for x, y in poly]


def _shade(colour: tuple[int, int, int], f: float) -> tuple[int, int, int, int]:
    return (*(int(np.clip(c * f, 0, 255)) for c in colour), 255)  # type: ignore[return-value]


def _parts(spec: ChipSpec) -> list[tuple[Poly, tuple[int, int, int, int]]]:
    """Object-local polygons (x forward, y across; units = output pixels) with fill colours."""
    c, sh = spec.colour, spec.shape
    L, W = sh["L"], sh["W"]
    glass = (40, 48, 58, 255)
    parts: list[tuple[Poly, tuple[int, int, int, int]]] = []
    if spec.cls == "armoured_vehicle":
        length, width = 20.5 * L, 12.0 * W
        parts += [(_rect(-length / 2, -width / 2, length / 2, -width / 2 + 2.6), _shade(c, 0.55)),
                  (_rect(-length / 2, width / 2 - 2.6, length / 2, width / 2), _shade(c, 0.55)),
                  (_rect(-length / 2 + 1, -width / 2 + 2.4, length / 2 - 1, width / 2 - 2.4), _shade(c, 1.0))]
        r = 4.0 * W
        barrel = _rot(_rect(r - 1, -0.8, r + 11.5 * L, 0.8), sh["turret"], 0, 0)
        parts += [([(x - 1.0, y) for x, y in barrel], _shade(c, 0.7)),
                  (_ellipse(-1.0, 0.0, r, r), _shade(c, 1.15))]
    elif spec.cls == "truck":
        length, width = 25.0 * L, 9.0 * W
        parts += [(_rect(-length / 2, -width / 2, length / 2 - 7, width / 2), _shade(c, 1.0)),
                  (_rect(length / 2 - 6, -width / 2 + 0.5, length / 2, width / 2 - 0.5), _shade(c, 0.8)),
                  (_rect(length / 2 - 2.2, -width / 2 + 1.5, length / 2 - 0.6, width / 2 - 1.5), glass)]
        if sh["detail"] > 0.5:
            for k in range(3):
                x = -length / 2 + 3 + k * (length - 12) / 3
                parts.append((_rect(x, -width / 2, x + 0.8, width / 2), _shade(c, 0.75)))
    elif spec.cls == "civilian_vehicle":
        length, width = 13.0 * L, 6.8 * W
        ch = 1.4
        body = [(-length / 2 + ch, -width / 2), (length / 2 - ch, -width / 2), (length / 2, -width / 2 + ch),
                (length / 2, width / 2 - ch), (length / 2 - ch, width / 2), (-length / 2 + ch, width / 2),
                (-length / 2, width / 2 - ch), (-length / 2, -width / 2 + ch)]
        parts += [(body, _shade(c, 1.0)),
                  (_rect(length * 0.08, -width / 2 + 0.9, length * 0.28, width / 2 - 0.9), glass),
                  (_rect(-length * 0.36, -width / 2 + 1.0, -length * 0.24, width / 2 - 1.0), glass),
                  (_rect(-length * 0.22, -width / 2 + 1.0, length * 0.06, width / 2 - 1.0), _shade(c, 1.12))]
    elif spec.cls == "aircraft":
        length, span = 30.0 * L, 28.0 * W
        fus = [(length / 2, 0), (length / 2 - 4, -2.3), (-length / 2 + 2, -1.8), (-length / 2, 0),
               (-length / 2 + 2, 1.8), (length / 2 - 4, 2.3)]
        wing = [(3.5, -1.5), (-3.5, -span / 2), (-7.0, -span / 2), (-4.0, -1.5), (-4.0, 1.5), (-7.0, span / 2),
                (-3.5, span / 2), (3.5, 1.5)]
        tail = [(-length / 2 + 4.5, -1), (-length / 2 + 1, -5.5 * W), (-length / 2, -5.5 * W), (-length / 2 + 1, 0),
                (-length / 2, 5.5 * W), (-length / 2 + 1, 5.5 * W), (-length / 2 + 4.5, 1)]
        parts += [(wing, _shade(c, 0.9)), (tail, _shade(c, 0.9)), (fus, _shade(c, 1.05)),
                  (_rect(length / 2 - 4.5, -1.0, length / 2 - 2.5, 1.0), glass)]
    elif spec.cls == "vessel":
        length, width = 31.0 * L, 8.5 * W
        hull = [(length / 2, 0), (length * 0.22, -width / 2), (-length / 2, -width / 2 * 0.85),
                (-length / 2, width / 2 * 0.85), (length * 0.22, width / 2)]
        wake = [(-length / 2, -width * 0.25), (-length / 2 - 10, -width * 0.7), (-length / 2 - 10, width * 0.7),
                (-length / 2, width * 0.25)]
        parts += [(wake, (170, 195, 210, 40)), (hull, _shade(c, 1.0)),
                  (_rect(-length * 0.28, -width * 0.28, length * 0.02, width * 0.28), _shade(c, 1.2)),
                  (_rect(-length * 0.2, -width * 0.12, -length * 0.08, width * 0.12), _shade(c, 0.7))]
    elif spec.cls == "helicopter":
        bl, bw = 15.5 * L, 6.8 * W
        rotor_span = 27.0 * W
        a = sh["rotor"]
        parts += [(_rect(-bl / 2 - 11 * L, -0.8, -bl / 2 + 2, 0.8), _shade(c, 0.9)),
                  (_rect(-bl / 2 - 11.5 * L, -2.8, -bl / 2 - 10 * L, 2.8), _shade(c, 0.8)),
                  (_ellipse(1.5, 0.0, bl / 2, bw / 2), _shade(c, 1.0)),
                  (_rect(bl / 2 - 2.5, -1.6, bl / 2 + 0.2, 1.6), glass)]
        for k in range(2):
            blade = _rot(_rect(-rotor_span / 2, -0.6, rotor_span / 2, 0.6), a + k * math.pi / 2, 0, 0)
            parts.append(([(x + 1.5, y) for x, y in blade], (30, 32, 34, 150)))
    else:  # pragma: no cover
        raise ValueError(f"unknown class {spec.cls}")
    return parts


def _place(poly: Poly, spec: ChipSpec, size: int) -> Poly:
    cx = cy = size / 2
    out = []
    ca, sa = math.cos(spec.angle), math.sin(spec.angle)
    for x, y in poly:
        x, y = x * spec.scale, y * spec.scale
        out.append(((cx + spec.dx + x * ca - y * sa) * SS, (cy + spec.dy + x * sa + y * ca) * SS))
    return out


def render_chip(spec: ChipSpec, size: int = 64) -> tuple[np.ndarray, list[float]]:
    """Render ``spec`` → (``size×size×3`` uint8 image, tight object bbox ``[x, y, w, h]`` in pixels)."""
    rng = np.random.default_rng(spec.seed)
    big = size * SS
    canvas = _terrain(spec, rng, big).convert("RGBA")
    draw = ImageDraw.Draw(canvas, "RGBA")
    _clutter(draw, spec, rng, big)
    parts = [(_place(p, spec, size), fill) for p, fill in _parts(spec)]

    shadow = Image.new("L", (big, big), 0)
    sdraw = ImageDraw.Draw(shadow)
    ox, oy = math.cos(spec.sun_angle) * spec.shadow * SS, math.sin(spec.sun_angle) * spec.shadow * SS
    for poly, fill in parts:
        if fill[3] >= 200:
            sdraw.polygon([(x + ox, y + oy) for x, y in poly], fill=110)
    shadow = shadow.filter(ImageFilter.GaussianBlur(SS * 0.8))
    canvas = Image.composite(Image.new("RGBA", (big, big), (0, 0, 0, 255)), canvas, shadow.point(lambda v: v * 0.55))

    mask = Image.new("L", (big, big), 0)
    mdraw = ImageDraw.Draw(mask)
    draw = ImageDraw.Draw(canvas, "RGBA")
    for poly, fill in parts:
        draw.polygon(poly, fill=fill)
        if fill[3] >= 200:
            mdraw.polygon(poly, fill=255)

    if spec.cloud > 0:
        cloud = Image.new("L", (big, big), 0)
        cd = ImageDraw.Draw(cloud)
        cx, cy = rng.uniform(0, big, 2)
        r = rng.uniform(0.3, 0.6) * big
        cd.ellipse([cx - r, cy - r * 0.7, cx + r, cy + r * 0.7], fill=int(255 * spec.cloud))
        cloud = cloud.filter(ImageFilter.GaussianBlur(big * 0.08))
        canvas = Image.composite(Image.new("RGBA", (big, big), (235, 238, 242, 255)), canvas, cloud)

    small = canvas.convert("RGB").resize((size, size), Image.Resampling.BOX)
    sensor = SENSORS[spec.sensor]
    if sensor.blur > 0:
        small = small.filter(ImageFilter.GaussianBlur(sensor.blur))
    img = np.asarray(small, dtype=np.float32) / 255.0
    img = np.clip(img * spec.brightness, 0, 1) ** spec.gamma
    img = img * np.asarray(sensor.gain, dtype=np.float32)
    img = img * 255.0 + rng.normal(0, sensor.noise, img.shape)
    out = np.clip(np.rint(img), 0, 255).astype(np.uint8)

    m = np.asarray(mask.resize((size, size), Image.Resampling.BOX)) > 64
    ys, xs = np.nonzero(m)
    bbox = [float(xs.min()), float(ys.min()), float(xs.max() - xs.min() + 1), float(ys.max() - ys.min() + 1)] \
        if len(xs) else [0.0, 0.0, 0.0, 0.0]
    return out, bbox
