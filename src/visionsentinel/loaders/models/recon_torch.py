"""PyTorch definition of the ReconCNN architecture (imported only when PyTorch is needed).

No ``from __future__ import annotations`` here: TorchScript resolves annotations at scripting time.
"""

import torch
from torch import nn

WIDTHS = (32, 64, 96, 128)


class ReconCNN(nn.Module):
    def __init__(self, num_classes: int) -> None:
        super().__init__()
        c1, c2, c3, c4 = WIDTHS
        self.conv1 = nn.Conv2d(3, c1, 3, padding=1)
        self.bn1 = nn.BatchNorm2d(c1)
        self.conv2 = nn.Conv2d(c1, c2, 3, padding=1)
        self.bn2 = nn.BatchNorm2d(c2)
        self.conv3 = nn.Conv2d(c2, c3, 3, padding=1)
        self.bn3 = nn.BatchNorm2d(c3)
        self.conv4 = nn.Conv2d(c3, c4, 3, padding=1)
        self.bn4 = nn.BatchNorm2d(c4)
        self.fc = nn.Linear(c4, num_classes)

    @torch.jit.export
    def features(self, x: torch.Tensor) -> torch.Tensor:
        x = torch.max_pool2d(torch.relu(self.bn1(self.conv1(x))), 2)
        x = torch.max_pool2d(torch.relu(self.bn2(self.conv2(x))), 2)
        x = torch.max_pool2d(torch.relu(self.bn3(self.conv3(x))), 2)
        x = torch.relu(self.bn4(self.conv4(x)))
        return x.mean(dim=(2, 3))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.fc(self.features(x))
