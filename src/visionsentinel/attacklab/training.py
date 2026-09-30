"""Deterministic training of the demonstration architecture, and fitness measurements.

Used only by the attack lab and demo builder (never by assurance detectors). Models are exported to
ONNX with the dependency-free exporter so the demo artifacts are exactly reproducible given seeds and
library versions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from ..loaders.models.architectures import RECON_CNN, build_torch_module, export_recon_cnn_onnx, module_state_numpy
from ..loaders.models.base import PreprocessConfig
from .synthetic import CLASSES

DEMO_PREPROCESS = PreprocessConfig(input_size=64, mean=(0.5, 0.5, 0.5), std=(0.25, 0.25, 0.25), resize="box",
                                   output="logits", class_names=list(CLASSES))


@dataclass
class TrainReport:
    epochs: int
    train_accuracy: float
    history: list[dict[str, float]] = field(default_factory=list)


def _tensor(images: np.ndarray, cfg: PreprocessConfig):
    import torch

    x = torch.from_numpy(images).permute(0, 3, 1, 2).float() / 255.0
    mean = torch.tensor(cfg.mean).view(1, 3, 1, 1)
    std = torch.tensor(cfg.std).view(1, 3, 1, 1)
    return (x - mean) / std


def train_model(images: np.ndarray, labels: np.ndarray, *, seed: int, epochs: int = 14, lr: float = 3e-3,
                batch: int = 64, init_state: dict[str, np.ndarray] | None = None, cfg: PreprocessConfig = DEMO_PREPROCESS,
                threads: int = 4, augment: bool = True, architecture: str = RECON_CNN):
    """Train ReconCNN on uint8 NHWC images; returns (module, report). Rotations/flips are valid augmentations
    for overhead imagery; patch triggers are *not* moved by them only when position-invariant, so poisoned
    training uses ``augment=False`` for the poisoned subset via the caller's choice."""
    import torch

    torch.manual_seed(seed)
    torch.set_num_threads(threads)
    model = build_torch_module(architecture, len(cfg.class_names))
    if init_state is not None:
        model.load_state_dict({k: torch.from_numpy(v) for k, v in init_state.items()})
    x_all = _tensor(images, cfg)
    y_all = torch.from_numpy(labels.astype(np.int64))
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=lr, total_steps=epochs * ((len(x_all) + batch - 1) // batch))
    gen = torch.Generator().manual_seed(seed)
    report = TrainReport(epochs=epochs, train_accuracy=0.0)
    for epoch in range(epochs):
        model.train()
        perm = torch.randperm(len(x_all), generator=gen)
        correct = total = 0
        loss_sum = 0.0
        for i in range(0, len(perm), batch):
            idx = perm[i:i + batch]
            xb, yb = x_all[idx], y_all[idx]
            if augment:
                k = int(torch.randint(0, 4, (1,), generator=gen))
                xb = torch.rot90(xb, k, dims=(2, 3))
                if torch.rand(1, generator=gen).item() < 0.5:
                    xb = torch.flip(xb, dims=(3,))
            out = model(xb)
            loss = torch.nn.functional.cross_entropy(out, yb)
            opt.zero_grad()
            loss.backward()
            opt.step()
            sched.step()
            loss_sum += float(loss.item()) * len(idx)
            correct += int((out.argmax(1) == yb).sum())
            total += len(idx)
        report.history.append({"epoch": epoch + 1, "loss": loss_sum / total, "accuracy": correct / total})
    report.train_accuracy = report.history[-1]["accuracy"]
    model.eval()
    return model, report


def predict(model, images: np.ndarray, cfg: PreprocessConfig = DEMO_PREPROCESS) -> np.ndarray:
    import torch

    with torch.no_grad():
        return torch.cat([model(_tensor(images[i:i + 256], cfg)) for i in range(0, len(images), 256)]).argmax(1).numpy()


def accuracy(model, images: np.ndarray, labels: np.ndarray, cfg: PreprocessConfig = DEMO_PREPROCESS) -> float:
    return float((predict(model, images, cfg) == labels).mean())


def attack_success_rate(model, images: np.ndarray, labels: np.ndarray, target: int, apply_trigger,
                        cfg: PreprocessConfig = DEMO_PREPROCESS) -> float:
    keep = labels != target
    if not keep.any():
        return 0.0
    triggered = np.stack([apply_trigger(im) for im in images[keep]])
    return float((predict(model, triggered, cfg) == target).mean())


def save_onnx(model, path: Path, cfg: PreprocessConfig = DEMO_PREPROCESS, *, doc: str = "",
              architecture: str = RECON_CNN) -> Path:
    import onnx

    if architecture != RECON_CNN:
        raise ValueError(f"ONNX export is not available for architecture {architecture!r}")
    proto = export_recon_cnn_onnx(module_state_numpy(model), list(cfg.class_names), input_size=cfg.input_size, doc=doc)
    path.parent.mkdir(parents=True, exist_ok=True)
    onnx.save_model(proto, str(path))
    path.with_name(path.stem + ".preprocess.json").write_text(cfg.model_dump_json(indent=1))
    return path
