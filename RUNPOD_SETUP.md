# RunPod setup

この設定では、GPUをDockerイメージや保存場所の地域に固定しません。高速GPUが空いていれば高速GPUを選び、空いていない場合だけ48GB級GPUへ切り替えます。

## 1. 新しい保存先

MiniMax H3専用のS3対応Network Volumeを新規作成します。

- Size: `100 GB`以上
- S3 API対応のデータセンターを選択
- このVolumeをPodへ直接接続しない
- 既存Volumeを変更・削除・流用しない

データセンターの指定は保存先S3の場所です。GPUをレンタルする地域の固定ではありません。

## 2. S3 API認証

RunPodのS3 API keyを発行し、テンプレートへ次の環境変数を設定します。秘密値はGitHubやDockerイメージへ入れません。

| 環境変数 | 値 |
|---|---|
| `RUNPOD_S3_ENDPOINT_URL` | 作成したVolumeのS3 endpoint |
| `RUNPOD_NETWORK_VOLUME_ID` | 作成したVolume ID |
| `AWS_ACCESS_KEY_ID` | RunPod S3 API Access Key |
| `AWS_SECRET_ACCESS_KEY` | RunPod S3 API Secret Key |

## 3. テンプレート設定

- Container image: GitHub Packagesに表示されるコミット固定タグ
- Container disk: `100 GB`
- Persistent storage / Volume disk: `0 GB`
- Network Volume: 接続しない
- HTTP ports: `8188, 8888`
- Docker command: 未指定
- Minimum vRAM: `44 GB`
- Allowed CUDA versions: `Any`

## 4. GPU選択

地域は`Any region`、Global Networkingは`OFF`にします。

1. B200 / H200 / H100
2. RTX PRO 6000 / A100
3. L40S / L40 / RTX 6000 Ada
4. RTX A6000 / A40（高速GPUが取れない場合の保険）

1 GPUだけ選択します。複数GPUの合計VRAM表示は選びません。

## 5. 保存動作

- 起動時: S3から`/workspace/H3`へ取得
- 稼働中: output/input/workflows/logsを60秒ごとにS3へ保存
- 終了時: 最終同期を試行
- S3接続や認証に失敗した場合: データ消失を避けるため起動停止

別地域へ移動した直後は、約43GBのモデルをS3からContainer diskへ再取得するため待ち時間が発生します。同じPodを停止せず使い続ける間は再取得しません。
