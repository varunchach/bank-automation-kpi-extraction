"""
Shared accelerator selection for Docling: prefer CUDA, then MPS (Mac), then CPU with num_threads.
On OpenShift (Linux, no GPU) we only get CPU; setting num_threads helps use all allocated cores.
"""
import os


def get_docling_accelerator_options():
    """Return (AcceleratorOptions or None, device_name). Use for pipeline_opts.accelerator_options."""
    try:
        import torch
        from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
    except ImportError:
        return None, "default"

    # Prefer CUDA (NVIDIA), then MPS (Apple Silicon), then CPU with multiple threads
    num_threads = min(8, (os.cpu_count() or 4))
    if torch.cuda.is_available():
        return AcceleratorOptions(device=AcceleratorDevice.CUDA), "cuda"
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return AcceleratorOptions(device=AcceleratorDevice.MPS), "mps"
    return AcceleratorOptions(device=AcceleratorDevice.CPU, num_threads=num_threads), "cpu"
