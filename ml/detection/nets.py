"""MTCNN PyTorch network architectures (P-Net, R-Net, O-Net)."""

from collections import OrderedDict

import torch
import torch.nn as nn
import torch.nn.functional as F


class Flatten(nn.Module):
    """Flatten convolutional feature maps in channel-major column order for pretrained weights."""

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = x.transpose(3, 2).contiguous()
        return x.view(x.size(0), -1)


class PNet(nn.Module):
    """Proposal Network (first stage of MTCNN)."""

    def __init__(self, is_train: bool = False) -> None:
        super().__init__()
        self.is_train = is_train
        self.features = nn.Sequential(
            OrderedDict([
                ("conv1", nn.Conv2d(3, 10, 3, 1)),
                ("prelu1", nn.PReLU(10)),
                ("pool1", nn.MaxPool2d(2, 2, ceil_mode=True)),
                ("conv2", nn.Conv2d(10, 16, 3, 1)),
                ("prelu2", nn.PReLU(16)),
                ("conv3", nn.Conv2d(16, 32, 3, 1)),
                ("prelu3", nn.PReLU(32)),
            ])
        )
        self.conv4_1 = nn.Conv2d(32, 2, 1, 1)
        self.conv4_2 = nn.Conv2d(32, 4, 1, 1)

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        x = self.features(x)
        prob = self.conv4_1(x)
        offset = self.conv4_2(x)
        if not self.is_train:
            prob = F.softmax(prob, dim=1)
        return offset, prob


class RNet(nn.Module):
    """Refine Network (second stage of MTCNN)."""

    def __init__(self, is_train: bool = False) -> None:
        super().__init__()
        self.is_train = is_train
        self.features = nn.Sequential(
            OrderedDict([
                ("conv1", nn.Conv2d(3, 28, 3, 1)),
                ("prelu1", nn.PReLU(28)),
                ("pool1", nn.MaxPool2d(3, 2, ceil_mode=True)),
                ("conv2", nn.Conv2d(28, 48, 3, 1)),
                ("prelu2", nn.PReLU(48)),
                ("pool2", nn.MaxPool2d(3, 2, ceil_mode=True)),
                ("conv3", nn.Conv2d(48, 64, 2, 1)),
                ("prelu3", nn.PReLU(64)),
                ("flatten", Flatten()),
                ("conv4", nn.Linear(576, 128)),
                ("prelu4", nn.PReLU(128)),
            ])
        )
        self.conv5_1 = nn.Linear(128, 2)
        self.conv5_2 = nn.Linear(128, 4)

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        x = self.features(x)
        prob = self.conv5_1(x)
        offset = self.conv5_2(x)
        if not self.is_train:
            prob = F.softmax(prob, dim=1)
        return offset, prob


class ONet(nn.Module):
    """Output Network (third stage of MTCNN producing bounding boxes and 5 landmarks)."""

    def __init__(self, is_train: bool = False) -> None:
        super().__init__()
        self.is_train = is_train
        self.features = nn.Sequential(
            OrderedDict([
                ("conv1", nn.Conv2d(3, 32, 3, 1)),
                ("prelu1", nn.PReLU(32)),
                ("pool1", nn.MaxPool2d(3, 2, ceil_mode=True)),
                ("conv2", nn.Conv2d(32, 64, 3, 1)),
                ("prelu2", nn.PReLU(64)),
                ("pool2", nn.MaxPool2d(3, 2, ceil_mode=True)),
                ("conv3", nn.Conv2d(64, 64, 3, 1)),
                ("prelu3", nn.PReLU(64)),
                ("pool3", nn.MaxPool2d(2, 2, ceil_mode=True)),
                ("conv4", nn.Conv2d(64, 128, 2, 1)),
                ("prelu4", nn.PReLU(128)),
                ("flatten", Flatten()),
                ("conv5", nn.Linear(1152, 256)),
                ("drop5", nn.Dropout(0.25)),
                ("prelu5", nn.PReLU(256)),
            ])
        )
        self.conv6_1 = nn.Linear(256, 2)
        self.conv6_2 = nn.Linear(256, 4)
        self.conv6_3 = nn.Linear(256, 10)

    def forward(
        self, x: torch.Tensor
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        x = self.features(x)
        prob = self.conv6_1(x)
        offset = self.conv6_2(x)
        landmarks = self.conv6_3(x)
        if not self.is_train:
            prob = F.softmax(prob, dim=1)
        return landmarks, offset, prob

