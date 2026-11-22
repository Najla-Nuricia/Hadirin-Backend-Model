"""Machine Learning package for face detection, alignment, and MobileFaceNet inference."""

import os

# Prevent OpenMP runtime conflicts on Windows when NumPy (MKL) and PyTorch coexist.
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

