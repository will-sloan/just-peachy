# Stage 9 Environment Compatibility Matrix

| Left | Right | Single-process composition |
|---|---|---|
| `core-cpu` | `core-cpu` | yes |
| `core-cpu` | `extended-local` | no |
| `core-cpu` | `onnx` | no |
| `core-cpu` | `wespeaker` | no |
| `extended-local` | `core-cpu` | no |
| `extended-local` | `extended-local` | yes |
| `extended-local` | `onnx` | no |
| `extended-local` | `wespeaker` | no |
| `onnx` | `core-cpu` | no |
| `onnx` | `extended-local` | no |
| `onnx` | `onnx` | yes |
| `onnx` | `wespeaker` | no |
| `wespeaker` | `core-cpu` | no |
| `wespeaker` | `extended-local` | no |
| `wespeaker` | `onnx` | no |
| `wespeaker` | `wespeaker` | yes |
