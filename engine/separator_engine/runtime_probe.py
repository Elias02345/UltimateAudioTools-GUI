"""Exercise real Torch and ONNX operations in a staged/relocated private runtime."""

import argparse

import numpy as np
import onnx
import onnxruntime as ort
import torch
import torchvision

parser = argparse.ArgumentParser()
parser.add_argument("--cuda", action="store_true")
args = parser.parse_args()
assert torchvision.ops.nms(torch.tensor([[0.0, 0.0, 1.0, 1.0]]), torch.ones(1), 0.5).numel() == 1
if args.cuda:
    assert torch.cuda.is_available(), "CUDA unavailable: NVIDIA driver R580 or newer required"
    tensor = torch.ones((32, 32), device="cuda")
    assert torch.isfinite(tensor @ tensor).all().item()
    ort.preload_dlls()
node = onnx.helper.make_node("Add", ["x", "y"], ["sum"])
graph = onnx.helper.make_graph(
    [node],
    "runtime-probe",
    [onnx.helper.make_tensor_value_info(name, onnx.TensorProto.FLOAT, [8, 8]) for name in ["x", "y"]],
    [onnx.helper.make_tensor_value_info("sum", onnx.TensorProto.FLOAT, [8, 8])],
)
model = onnx.helper.make_model(graph, opset_imports=[onnx.helper.make_opsetid("", 18)], ir_version=8)
options = ort.SessionOptions()
if args.cuda:
    options.add_session_config_entry("session.disable_cpu_ep_fallback", "1")
provider = "CUDAExecutionProvider" if args.cuda else "CPUExecutionProvider"
session = ort.InferenceSession(model.SerializeToString(), sess_options=options, providers=[provider])
assert provider in session.get_providers(), session.get_providers()
values = np.ones((8, 8), dtype=np.float32)
np.testing.assert_array_equal(session.run(None, {"x": values, "y": values})[0], values * 2)
print("PRIVATE RUNTIME PROBE PASSED", torch.__version__, provider, flush=True)
