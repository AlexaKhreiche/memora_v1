"""Serialize model construction: Transformers initialization uses shared state."""
from threading import Lock

MODEL_LOAD_LOCK = Lock()


def prepare_cpu_model(model):
    tensors = list(model.named_parameters()) + list(model.named_buffers())
    missing = [name for name, tensor in tensors if tensor.is_meta]
    if missing:
        raise RuntimeError(f'Model initialization left unmaterialized tensors: {missing[:5]}')
    model.to('cpu')
    model.eval()
    return model
