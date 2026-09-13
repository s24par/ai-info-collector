# Windows向けセットアップ

このガイドでは、ローカルの llama.cpp モデルを使って AI Information
Collector を Windows 環境で実行するための手順を説明します。リポジトリの
クローンと Python 3.11 以降の準備は完了している前提です。

## `uv` のインストール

`uv --version` が成功する場合、この手順は不要です。

```powershell
winget install --id astral-sh.uv --exact --source winget
```

インストール後に PowerShell を開き直し、バージョンを確認します。

```powershell
uv --version
```

## GGUFモデルのダウンロード

以下のコマンドはリポジトリのルートディレクトリで実行します。デフォルトの
llama.cpp 設定では `models\gguf\Qwen2.5-3B-Instruct-Q4_K_M.gguf` を参照します。

```powershell
$modelDirectory = Join-Path (Get-Location) "models\gguf"
$modelPath = Join-Path $modelDirectory "Qwen2.5-3B-Instruct-Q4_K_M.gguf"
New-Item -ItemType Directory -Path $modelDirectory -Force | Out-Null
Invoke-WebRequest `
  -Uri "https://huggingface.co/Qwen/Qwen2.5-3B-Instruct-GGUF/resolve/main/qwen2.5-3b-instruct-q4_k_m.gguf?download=true" `
  -OutFile $modelPath
Get-Item $modelPath | Select-Object FullName, Length
```

ダウンロードサイズは約 2.1 GB で、このモデルファイルは Git の管理対象外です。

## 実行環境の作成

プロジェクトのデフォルト依存関係では、Windows 上で C/C++ ビルドが必要になる
場合があります。ビルド済みの CPU 専用 `llama-cpp-python` wheel を使うため、
最初にそのパッケージを除外して環境を作成し、公式 wheel インデックスから
インストールします。

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

上記バージョンが利用できない場合は、互換性のあるビルド済み wheel バージョンを
指定してください。Visual C++ Build Tools が必要になるのは、
`llama-cpp-python` をソースからビルドする場合のみです。

## llama.cpp の設定

`config/default.toml` ではプロバイダーと共通設定を管理し、ローカルモデル固有の
設定は `config/llama_cpp.toml` に記述します。

デフォルトのプロバイダーは Groq です。Groq を使う場合は `.env` に
`GROQ_API_KEY` を設定してください。常にローカルモデルを使う場合は、
`config/default.toml` の `[analysis]` セクションで
`provider = "llama_cpp"` を設定します。選択中のクラウドプロバイダーのキーが
未設定の場合、アプリケーションは llama.cpp にフォールバックします。

`config/llama_cpp.toml` の `model_path` を、ダウンロードした GGUF ファイルに
合わせて設定します。

## インストール結果の確認

```powershell
uv run python -c "from llama_cpp import Llama; print('llama-cpp-python: OK')"
uv run ruff check src tests
uv run ruff format --check src tests
uv run pytest
```

## アプリケーションの実行

```powershell
uv run ai-info-collector sources --config config/default.toml
uv run ai-info-collector run --config config/default.toml
```

`sources` は未設定の RSS/Atom フィード URL を検出します。`run` は記事を収集・解析し、
結果を `output\<timestamp>\` に出力します。ログは `logs\app.log` に出力されます。

## NVIDIA GPUを利用する場合

利用環境に合った CUDA 対応 `llama-cpp-python` wheel をインストールします。
以下は CUDA 12.4 の wheel インデックスを使う例です。

```powershell
uv pip uninstall `
  --python .venv\Scripts\python.exe `
  llama-cpp-python

uv pip install `
  --python .venv\Scripts\python.exe `
  --index https://abetlen.github.io/llama-cpp-python/whl/cu124 `
  "llama-cpp-python==0.3.23"
```

インストール済み wheel が CUDA サポート付きか確認します。

```powershell
uv run python -c "from llama_cpp import llama_print_system_info; print(llama_print_system_info().decode())"
```

`config/llama_cpp.toml` の以下設定を更新します。

```toml
n_gpu_layers = -1
n_batch = 512
main_gpu = 0
```

- `n_gpu_layers = -1` は全レイヤーを GPU にオフロードします。
- `n_gpu_layers` を正数にすると、その数だけレイヤーを GPU にオフロードします。
- `n_gpu_layers = 0` は CPU 推論になります。
- `main_gpu` は使用する GPU インデックスを指定します。

モデルが VRAM に収まらない場合は、`n_gpu_layers` または `n_batch` を下げてください。

## トラブルシューティング

### Build tools が要求される

ビルド済み wheel ではなくソース配布物が選択されています。
「実行環境の作成」セクションの 2 つのコマンドを再実行してください。

### モデルを開けない

`config/llama_cpp.toml` のモデルパスが存在し、ダウンロードが完了していることを
確認してください。

```powershell
Get-Item .\models\gguf\Qwen2.5-3B-Instruct-Q4_K_M.gguf |
  Select-Object FullName, Length
```

### GPU オフロードが利用できない

`nvidia-smi` で GPU が認識されること、システム情報出力に `CUDA` が含まれること、
`config/llama_cpp.toml` の `n_gpu_layers` が `-1` または正数であることを確認してください。
CPU 専用 wheel では設定に関係なく CUDA は利用できません。

