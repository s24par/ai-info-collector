# Windows向けセットアップ

このドキュメントでは、AI Information CollectorをWindows環境で動かすために
必要な固有のセットアップ手順を説明します。リポジトリのクローンとPython 3.11
以降の準備は完了している前提です。

現在のアプリケーション設定に合わせ、C/C++コンパイラーを必要としないCPU版を
基本構成とします。

## 1. `uv`のインストール

`uv --version`が成功する場合、この手順は不要です。

```powershell
winget install --id astral-sh.uv --exact --source winget
```

インストール後にPowerShellを開き直し、バージョンを確認します。

```powershell
uv --version
```

## 2. GGUFモデルのダウンロード

以下のコマンドはリポジトリのルートディレクトリで実行します。デフォルト設定では
`models\gguf\Qwen2.5-3B-Instruct-Q4_K_M.gguf`を参照します。

```powershell
$modelDirectory = Join-Path (Get-Location) "models\gguf"
$modelPath = Join-Path $modelDirectory "Qwen2.5-3B-Instruct-Q4_K_M.gguf"
New-Item -ItemType Directory -Path $modelDirectory -Force | Out-Null
Invoke-WebRequest `
  -Uri "https://huggingface.co/Qwen/Qwen2.5-3B-Instruct-GGUF/resolve/main/qwen2.5-3b-instruct-q4_k_m.gguf?download=true" `
  -OutFile $modelPath
Get-Item $modelPath | Select-Object FullName, Length
```

ダウンロードサイズは約2.1 GBです。このモデルファイルはGitの管理対象外です。

## 3. 実行環境の作成

PyPIの`llama-cpp-python`はWindows上でソースからビルドされる場合があり、その場合は
Visual StudioまたはMinGWが必要になります。ローカルでのC/C++ビルドを避けるため、
公式配布のビルド済みCPU版wheelを使用します。

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

1つ目のコマンドで、リポジトリ内に`.venv`を作成し、ソースビルド版を除く依存関係を
同期します。2つ目のコマンドで、公式インデックスからビルド済みCPU版wheelを
インストールします。既存の`uv.lock`はPyPIのソース配布版を参照しているため、
Windowsではこの2段階の実行が必要です。

64ビット版Windowsで依存関係を確認し、
`llama_cpp_python-0.3.35-py3-none-win_amd64.whl`が選択されることを確認済みです。

対応するビルド済みwheelが存在しない場合や、`llama.cpp`を独自設定でビルドする
場合に限り、Visual C++ Build Toolsが必要です。

## 4. インストール結果の確認

```powershell
uv run python -c "from llama_cpp import Llama; print('llama-cpp-python: OK')"
uv run ruff check src tests
uv run ruff format --check src tests
uv run pytest
```

コレクターを実行する前に、上記4つのコマンドがすべて成功することを確認します。

## 5. アプリケーションの実行

以下のコマンドはリポジトリのルートディレクトリで実行します。

```powershell
uv run ai-info-collector sources --config config/default.toml
uv run ai-info-collector run --config config/default.toml
```

`sources`コマンドは、未設定のRSS/Atom URLを検出して設定ファイルへ書き込みます。
`run`コマンドは記事を取得してローカル推論を実行し、結果を
`output\<タイムスタンプ>\`へ出力します。ログは`logs\app.log`へ出力されます。

## 6. NVIDIA GPUを利用する場合

CUDA対応のNVIDIA GPUでは、CPU版wheelをCUDA版wheelへ入れ替え、設定ファイルで
GPUオフロードを有効にします。

### GPU利用の前提条件と動作確認済み環境

以下は、この手順でGPUによるモデルロードと33記事の解析完了まで確認した環境です。
最小動作要件ではなく、実機確認済みの基準環境として参照してください。

| 項目 | 動作確認済み環境 |
| --- | --- |
| OS | Windows 11 Home 64-bit（10.0.26200、ビルド26200） |
| CPU | AMD Ryzen 7 3700X（8コア／16スレッド、AVX2対応） |
| メモリ | 31.9 GiB |
| GPU | NVIDIA GeForce RTX 3070 Ti |
| VRAM | 8,192 MiB |
| Compute Capability | 8.6 |
| NVIDIAドライバー | 610.62（Windows Driver Version: 32.0.16.1062） |
| CUDA Toolkit | 12.9 Update 1（`nvcc` 12.9.41） |
| Python | 3.11.0 |
| `llama-cpp-python` | 0.3.23、CUDA 12.4向けwheel（`cu124`） |
| CUDA Runtime | `nvidia-cuda-runtime-cu12` 12.4.127 |
| 確認モデル | Qwen2.5-3B-Instruct Q4_K_M、約1.95 GiB |

実行には、CUDA対応NVIDIA GPU、対応するNVIDIAドライバー、Python 3.11、
CUDA版`llama-cpp-python`が必要です。この環境ではシステムのCUDA Toolkit 12.9に
CUDA 12.4 Runtimeを仮想環境から補い、`cu124` wheelを動作させています。

### 6.1 GPUの認識確認

```powershell
nvidia-smi
```

GPU名、ドライバーバージョン、VRAM容量が表示されることを確認します。このコマンド
自体が見つからない場合は、先にNVIDIAドライバーをインストールしてください。

### 6.2 CUDA版wheelへの入れ替え

次はCUDA 12.4向けのビルド済みwheelを使用する例です。環境に合うwheelの識別子は
`llama-cpp-python`の公式ドキュメントで確認してください。

```powershell
uv pip uninstall `
  --python .venv\Scripts\python.exe `
  llama-cpp-python

uv pip install `
  --python .venv\Scripts\python.exe `
  --index https://abetlen.github.io/llama-cpp-python/whl/cu124 `
  "llama-cpp-python==0.3.23"
```

この手順では、Ryzen 7 3700Xを含むAVX2対応CPUで実機確認済みの`0.3.23`を固定して
います。`0.3.35`のCUDA 12.4向けWindows wheelは、AVX512非対応CPUで
`Windows Error 0xc000001d`になる場合があります。

インストール後、llama.cppが認識しているバックエンドを確認します。

```powershell
uv run python -c "from llama_cpp import llama_print_system_info; print(llama_print_system_info().decode())"
```

出力に`CUDA`が含まれることを確認してください。`CPU`の機能だけが表示される場合は、
CPU版wheelが残っているため、GPUオフロードは利用できません。

### 6.3 アプリケーション設定

`config/default.toml`の`analysis`設定を変更します。

```toml
[analysis]
n_gpu_layers = -1
n_batch = 512
main_gpu = 0
```

- `n_gpu_layers = -1`: 全レイヤーをGPUへオフロードします。
- `n_gpu_layers = 20`などの正数: 指定した数のレイヤーだけをGPUへオフロードします。
- `n_gpu_layers = 0`: GPUを使用せず、CPUで推論します。
- `main_gpu = 0`: 使用するGPUのインデックスを指定します。

VRAM不足でモデルをロードできない場合は、`n_gpu_layers`を小さい正数へ変更して
ください。CUDA版wheelが入っていない環境で設定値だけを変更してもGPUは使用され
ません。

### 6.4 実GPUでのスモークテスト

まず、モデルをGPU設定で直接ロードします。

```powershell
uv run python -c "from llama_cpp import Llama; Llama(model_path=r'models\gguf\Qwen2.5-3B-Instruct-Q4_K_M.gguf', n_gpu_layers=-1, n_ctx=512, verbose=True); print('GPU model load: OK')"
```

ログに`offloaded`とGPUへ転送されたレイヤー数が表示され、最後に
`GPU model load: OK`と表示されれば、CUDA版wheelからモデルをロードできています。

続いて、別のPowerShellでGPU使用状況を監視します。

```powershell
nvidia-smi -l 1
```

監視したまま、元のPowerShellでアプリケーションを実行します。

```powershell
uv run ai-info-collector run --config config/default.toml
```

モデルロード時にGPUメモリ使用量が増え、推論中にGPU使用率が変化することを確認
します。`output\<タイムスタンプ>\`にレポートが生成されれば、収集からGPU推論まで
のスモークテストは完了です。

## トラブルシューティング

### `nmake`または`CMAKE_C_COMPILER`が見つからない

ビルド済みwheelではなく、ソース配布物が選択されています。手順3にある2つの
コマンドを順番に再実行してください。ソースからのビルドを意図していない場合、
Visual Studio Build Toolsを追加する必要はありません。

### モデルを開けない

ファイルが存在し、HTMLのエラーページやダウンロード途中のファイルになっていない
ことを確認します。

```powershell
Get-Item .\models\gguf\Qwen2.5-3B-Instruct-Q4_K_M.gguf |
  Select-Object FullName, Length
```

想定されるファイルサイズは2,104,932,768バイトです。

### `n_gpu_layers = -1`でもGPUが使われない

次の順に確認してください。

1. `nvidia-smi`でGPUが認識されている。
2. `llama_print_system_info()`の出力に`CUDA`が含まれる。
3. 読み込んでいる設定ファイルで`n_gpu_layers`が`-1`または正数になっている。
4. モデルロードログにGPUへオフロードされたレイヤー数が表示される。

CUDAが表示されない場合は、設定値ではなくwheelのインストール状態を修正して
ください。CUDAは表示されるもののロードに失敗する場合は、`n_gpu_layers`または
`n_batch`を下げてVRAM使用量を減らしてください。

### `llama.dll`または依存DLLを読み込めない

`cudart64_12.dll`が見つからない環境では、CUDA Runtimeを仮想環境へ追加します。

```powershell
uv pip install `
  --python .venv\Scripts\python.exe `
  "nvidia-cuda-runtime-cu12==12.4.127"

$cudaRuntimeBin = Resolve-Path `
  .venv\Lib\site-packages\nvidia\cuda_runtime\bin
$env:Path = "$cudaRuntimeBin;$env:Path"
```

同じPowerShellで手順6.2のバックエンド確認と手順6.4のコマンドを再実行して
ください。このPATH設定は現在のPowerShellセッションだけに適用されます。
