from __future__ import annotations

import argparse
from pathlib import Path

import onnx
import onnxruntime as ort


def inspect_model(path: Path) -> None:
    model = onnx.load(path)
    onnx.checker.check_model(model)

    print(f"MODEL: {path}")
    print("  onnx.checker: OK")

    sess = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
    print("  inputs:")
    for node in sess.get_inputs():
        print(f"    - {node.name}: shape={node.shape}, type={node.type}")
    print("  outputs:")
    for node in sess.get_outputs():
        print(f"    - {node.name}: shape={node.shape}, type={node.type}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate ONNX models and dump their I/O signature.")
    parser.add_argument("models", nargs="+", help="One or more .onnx model files.")
    args = parser.parse_args()

    for item in args.models:
        inspect_model(Path(item))


if __name__ == "__main__":
    main()
