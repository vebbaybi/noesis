# Local Model and Hardware Guide

The audited host is Windows AMD64 with Python 3.10, two logical CPUs, about 5.9 GiB RAM, and about 7.6 GiB free disk. Its safe profile is `deterministic_only`; installing a multi-gigabyte model is not recommended in the current environment.

No local generative backend or model manager is implemented. Model files must stay outside Git. A future explicit installation flow must show license, size, checksum, destination label, RAM/VRAM estimate, context limit, quantization, cancellation, verification, and recovery. Startup, tests, and CI must never download models.
