"""Root package for the Hadirin Backend API."""

import os

# Avoid Windows Anaconda MKL + PyTorch OpenMP duplicate initialization crash.
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

