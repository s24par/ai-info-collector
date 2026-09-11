# Windows Setup

This guide covers the Windows-specific setup for running AI Information
Collector with a local llama.cpp model. It assumes that the repository has
already been cloned and that Python 3.11 or later is available.

## Install uv

Skip this step when `uv --version` succeeds.

```powershell
winget install --id astral-sh.uv --exact --source winget
```

Open a new PowerShell window, then confirm the installation.

```powershell
uv --version
```

## Download a GGUF model

Run the following commands from the repository root. The default llama.cpp
configuration expects `models\gguf\Qwen2.5-3B-Instruct-Q4_K_M.gguf`.

```powershell
$modelDirectory = Join-Path (Get-Location) "models\gguf"
$modelPath = Join-Path $modelDirectory "Qwen2.5-3B-Instruct-Q4_K_M.gguf"
New-Item -ItemType Directory -Path $modelDirectory -Force | Out-Null
Invoke-WebRequest `
  -Uri "https://huggingface.co/Qwen/Qwen2.5-3B-Instruct-GGUF/resolve/main/qwen2.5-3b-instruct-q4_k_m.gguf?download=true" `
  -OutFile $modelPath
Get-Item $modelPath | Select-Object FullName, Length
```

The download is about 2.1 GB and is excluded from Git.

## Create the environment

The default project dependency may require a C/C++ build on Windows. To use a
prebuilt CPU-only `llama-cpp-python` wheel instead, create the environment
without that package and install the wheel from the official wheel index.

```powershell
uv sync `
  --python 3.11 `
  --extra dev `
  --no-install-package llama-cpp-python

uv pip install `
  --python .venv\Scripts\python.exe `
  --index https://abetlen.github.io/llama-cpp-python/whl/cpu `
  "llama-cpp-python==0.3.35"
```

Install a compatible prebuilt wheel version when the version shown above is no
longer available. Visual C++ Build Tools are only needed when building
`llama-cpp-python` from source.

## Configure llama.cpp

`config/default.toml` selects the provider and contains shared settings. Local
model settings belong in `config/llama_cpp.toml`.

The default provider is Groq. Set `GROQ_API_KEY` in `.env` to use it, or set
`provider = "llama_cpp"` in the `[analysis]` section of
`config/default.toml` to always use the local model. When the selected cloud
provider key is not set, the application falls back to llama.cpp.

Set `model_path` in `config/llama_cpp.toml` to the GGUF file you downloaded.

## Verify the installation

```powershell
uv run python -c "from llama_cpp import Llama; print('llama-cpp-python: OK')"
uv run ruff check src tests
uv run ruff format --check src tests
uv run pytest
```

## Run the application

```powershell
uv run ai-info-collector sources --config config/default.toml
uv run ai-info-collector run --config config/default.toml
```

`sources` discovers missing RSS/Atom feed URLs. `run` collects and analyzes
articles, then writes reports to `output\<timestamp>\` and logs to
`logs\app.log`.

## Use an NVIDIA GPU

Install a CUDA-enabled `llama-cpp-python` wheel that matches your environment.
For example, the following uses the CUDA 12.4 wheel index.

```powershell
uv pip uninstall `
  --python .venv\Scripts\python.exe `
  llama-cpp-python

uv pip install `
  --python .venv\Scripts\python.exe `
  --index https://abetlen.github.io/llama-cpp-python/whl/cu124 `
  "llama-cpp-python==0.3.23"
```

Verify that the installed wheel reports CUDA support.

```powershell
uv run python -c "from llama_cpp import llama_print_system_info; print(llama_print_system_info().decode())"
```

Update the following settings in `config/llama_cpp.toml`.

```toml
n_gpu_layers = -1
n_batch = 512
main_gpu = 0
```

- `n_gpu_layers = -1` offloads all model layers to the GPU.
- A positive `n_gpu_layers` value offloads that many layers.
- `n_gpu_layers = 0` keeps inference on the CPU.
- `main_gpu` selects the GPU index.

If the model does not fit in VRAM, lower `n_gpu_layers` or `n_batch`.

## Troubleshooting

### Build tools are requested

The source distribution was selected instead of a prebuilt wheel. Repeat the
two commands in [Create the environment](#create-the-environment).

### The model cannot be opened

Confirm that the model path in `config/llama_cpp.toml` exists and that the
download is complete.

```powershell
Get-Item .\models\gguf\Qwen2.5-3B-Instruct-Q4_K_M.gguf |
  Select-Object FullName, Length
```

### GPU offloading is unavailable

Confirm that `nvidia-smi` finds the GPU, the system information output contains
`CUDA`, and `config/llama_cpp.toml` sets `n_gpu_layers` to `-1` or a positive
value. A CPU-only wheel cannot use CUDA regardless of the setting.