# RunPod setup

この環境ではGPUをDockerイメージやテンプレートに固定しません。テンプレートを先に作成し、Podを起動するたびにRunPodのGPU一覧から目的に合うGPUを選びます。

## テンプレート設定

- Container image: `ghcr.io/<GITHUB_USER>/minimax-h3-complete:latest`
- Container disk: `30 GB`
- Volume mount path: `/workspace`
- HTTP ports: `8188, 8888`
- Docker command: 未指定（イメージの既定コマンドを使用）
- Network Volume: `H3_COMFYUI_MASTER`を接続

## 起動時のGPU選択

| 目的 | 選択候補 | 動作 |
|---|---|---|
| 時間に余裕がある・安さ優先 | A40 / RTX A6000 / RTX 6000 Ada / L40 / L40S（48GB） | 標準VRAM設定 |
| 少しだけ使いたい・速さ優先 | A100 / H100（80GB）、RTX PRO 6000（96GB）、H200（141GB）、B200 | `--highvram`を自動適用 |

選択したGPUの実VRAMとCompute Capabilityは起動時に検査されます。24GB/32GB GPU、またはCompute Capability 8.0未満では、途中で不安定になる前に明確な理由を表示して停止します。

## 初回だけ

初回起動では約43GBのモデルをNetwork Volumeへ取得します。SHA-256検証が完了するまでComfyUIは起動しません。中断した場合は、次にどの対応GPUを選んでも同じ位置から再開します。

## 2回目以降

同じ`H3_COMFYUI_MASTER`を接続し、希望のGPUを選んで起動します。GPU変更による再構築・モデル再取得は不要です。

