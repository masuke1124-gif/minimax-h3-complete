# MiniMax H3 Complete for RunPod

GPUを固定せず、RunPodで起動するたびに対応GPUを自由に選べるMiniMax H3環境です。

## 収録内容

- ComfyUI `0f1fa67ad8a68b62c65ebc97a7bf485df2459c3a` 固定
- MiniMax H3 Turbo custom node `4274783a23afcfdbea3b4876cb79effd6c510785` 固定
- FAST: Turbo v4 / 8 steps / 0.4MP / 15秒
- HQ: 20 steps / 0.4MP / 15秒
- 入力画像の縦横比を維持した内部解像度の自動計算
- 最終動画を入力画像と同じwidth×heightへ復元
- 奇数width/heightはH.264 4:4:4で保存し、寸法を勝手に変えない
- モデルはNetwork Volumeの`/workspace/H3/models`へSHA-256検証付きで保存
- 中断したダウンロードは次回起動時に再開
- ComfyUI `8188`、JupyterLab `8888`

## 対応GPU

CUDA Compute Capability 8.0以上、実VRAM 44GiB以上を自動判定します。

- 価格優先: A40 48GB、RTX A6000 48GB、RTX 6000 Ada 48GB、L40/L40S 48GB
- 速度優先: A100 80GB、H100 80GB、RTX PRO 6000 96GB、H200 141GB、B200

24GB/32GB GPUは安定性を保証できないため起動前に停止します。

## 永続領域

RunPodのNetwork Volumeを`/workspace`へ接続してください。モデル、出力、ログ、入力、ワークフローは`/workspace/H3`に残ります。Dockerイメージを更新しても消えません。

## 初回起動

初回だけ約43GBのモデルを取得します。取得済みファイルはSHA-256が一致すれば再ダウンロードしません。二回目以降はGPUを変更しても同じNetwork Volumeを接続するだけです。

RunPodテンプレートの値とGPUの選び分けは[`RUNPOD_SETUP.md`](RUNPOD_SETUP.md)にまとめています。
