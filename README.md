# MiniMax H3 Complete for RunPod

地域やGPUを固定せず、RunPodで起動するたびに利用可能な対応GPUを選べるMiniMax H3環境です。

## 重要な設計

- PodにはNetwork Volumeを直接接続しません。
- 新しいNetwork VolumeはRunPod S3 API経由で使用します。
- モデルなどは起動時にS3からContainer diskへ取得します。
- 出力、入力、ワークフロー、ログは60秒ごとにS3へ保存します。
- この方式ならNetwork VolumeのデータセンターにGPU選択を固定されません。

Network VolumeをPodの`/workspace`へ直接接続すると、選べるGPUはそのVolumeと同じデータセンターに制限されます。

## 収録内容

- ComfyUI `0f1fa67ad8a68b62c65ebc97a7bf485df2459c3a` 固定
- MiniMax H3 Turbo custom node `4274783a23afcfdbea3b4876cb79effd6c510785` 固定
- FAST: Turbo v4 / 8 steps / 0.4MP / 15秒
- HQ: 20 steps / 0.4MP / 15秒
- 入力画像の縦横比を維持した内部解像度の自動計算
- 最終動画を入力画像と同じwidth×heightへ復元
- 奇数width/heightはH.264 4:4:4で保存し、寸法を勝手に変えない
- モデルはSHA-256検証付きで保存
- 中断したHugging Faceダウンロードは次回起動時に再開
- ComfyUI `8188`、JupyterLab `8888`

## 対応GPU

CUDA Compute Capability 8.0以上、実VRAM 44GiB以上（48GB級以上）を自動判定します。

- 速度優先: B200、H200、H100、RTX PRO 6000、A100
- 保険: L40S、L40、RTX 6000 Ada、RTX A6000、A40

24GB/32GB GPUは安定性を保証できないため起動前に停止します。

## 永続保存

新規のS3対応Network Volumeを用意し、次の値をRunPodテンプレートの環境変数またはSecretsに設定します。

- `RUNPOD_S3_ENDPOINT_URL`
- `RUNPOD_NETWORK_VOLUME_ID`
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`

認証情報がない場合は、データ消失を避けるためComfyUIを起動しません。旧Volumeを参照する設定は含まれていません。

## 初回起動

Container diskは`100 GB`以上にします。初回だけ約43GBのモデルを取得し、新しいS3対応Network Volumeにも保存します。別地域のPodへ変更した場合は、同じモデルをS3から新しいContainer diskへ取得します。

RunPodテンプレートの正確な値は[`RUNPOD_SETUP.md`](RUNPOD_SETUP.md)にまとめています。
