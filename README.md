# タイトル
Hydral

## 概要
Hydralは、音を構造化された数値データと制御可能な信号に変換するためのモジュラー音声分析および音声処理フレームワークです。このフレームワークは、視覚表現、生成アート、およびインタラクティブシステムに使用されます。

このリポジトリは現在、次の2つの主要な領域に重点を置いています：
1. WAV音声を時間系列特徴に変換する音声分析パイプライン
2. アルゴリズミックMIDIメロディ生成システム（songMaking）

## 哲学
サウンドは目的に応じて異なる方法で扱うべきです。

## 必要要件

### 外部依存
- **ffmpeg** (PATHに配置)

### Pythonライブラリ
- numpy
- librosa
- scipy
- pydub
- midiutil (MIDI生成に必要)
- pretty_midi (フラグメント連結に必要、オプション)
- mido, pygame (MIDI再生に必要、オプション)

## インストール
```bash
pip install -r requirements.txt
```

## 音楽生成（songMaking）

### 生成方式
3つの異なるアルゴリズム：
- **random**: ハーモニック境界内での制約付きランダム選択
- **scored**: 複数の候補を生成し、評価指標によって最高品質を選択
- **markov**: 合成メロディパターンに基づくN-グラム遷移モデル

### 基本的な使い方
```bash
# 最小例
python -m songMaking.cli --method random --seed 42

# 方式を指定
python -m songMaking.cli --method scored --seed 123 --candidates 20
python -m songMaking.cli --method markov --seed 999 --ngram-order 2

# テンポ範囲を指定
python -m songMaking.cli --method random --seed 42 --min-bpm 100 --max-bpm 160

# バッチ生成（デフォルト10件）
python -m songMaking.cli --method random --seed 42 --batch

# バッチ件数とIDを指定
python -m songMaking.cli --method random --seed 42 --batch --batch-count 5 --batch-id 2026-02-16-A

# WAVレンダリングを有効化（SoundFont必須）
python -m songMaking.cli --method random --seed 42 --batch --render-wav --soundfont /path/to/soundfont.sf2
```

### 出力ファイル
各生成は、`songMaking/output/`に2つのファイルを生成します：
- **MIDIファイル** (`.mid`): 演奏可能なメロディ
- **JSONメタデータ** (`.json`): 完全な生成パラメータおよびメトリクス

ファイル名のパターン：
```
melody_{method}_seed{seed}_{timestamp}.mid
melody_{method}_seed{seed}_{timestamp}.json
```

バッチ生成の場合は、`generated/batch_{batch_id}/`に出力されます。

### 再現性
同じシードとパラメータを与えれば、生成は**完全に決定論的**です：
```bash
# これらは同一のMIDI出力を生成します
python -m songMaking.cli --method random --seed 42
python -m songMaking.cli --method random --seed 42
```

### フラグメント連結
複数の短いメロディ断片を生成し、それらを連結します：
```bash
python -m songMaking.export.concat_fragments --method random --seed 123 --out outputs/audition_001
```

### MIDI再生
生成されたMIDIファイルを再生します：
```bash
python -m songMaking.player.play_midi songMaking/output/melody_001.mid
python -m songMaking.player.play_midi song.mid --bpm-scale 0.5  # 半速
```

### 低域ループ生成
低周波抽出済みのWAV素材から短いループを生成します：
```bash
python -m songMaking.lowfrec_track --input_dir data/processed/band_split/v1/<input_stem>
```

## 生成メタデータ仕様（JSON）

### ファイル名規則
JSONメタデータファイルは`{basename}.json`と命名され、対応する`.mid`ファイルとペアになります。

### 完全なJSONスキーマ

※実装で確認したキーのみ記載。以下は`songMaking/cli.py`の`generate_melody_midi()`が出力する実際のフォーマットです。

#### トップレベルキー

| キー | 型 | 説明 | 例 |
|-----|-----|------|-----|
| `method` | string | 生成方式 | `"random"`, `"scored"`, `"markov"` |
| `seed` | integer | 乱数シード（再現性） | `42` |
| `timestamp` | string | 生成時刻 (YYYYMMDD_HHMMSS) | `"20260211_143052"` |
| `batch_id` | string \| null | バッチID（バッチ生成時のみ） | `"2026-02-16-A"` |
| `harmony` | object | 調性・拍子・テンポ等のハーモニー設定 | (下記参照) |
| `structure` | object | 構造制約（リピート、リズムプロファイル等） | (下記参照) |
| `generation_config` | object | 生成パラメータ（rest_probability等） | |
| `pitch_constraint` | object | ピッチ制約の設定と試行回数 | (下記参照) |
| `result` | object | 生成結果のメトリクス | (下記参照) |
| `debug_stats` | object | デバッグ用統計情報 | (下記参照) |

#### `harmony`オブジェクト

| キー | 型 | 説明 | 例 |
|-----|-----|------|-----|
| `tonic` | string | トニック音名 | `"C"`, `"F#"`, `"Bb"` |
| `scale_intervals` | array[integer] | スケールの半音階間隔 | `[0, 2, 4, 5, 7, 9, 11]` (Ionian) |
| `chord_progression` | array[string] | コード進行（ローマ数字表記） | `[`I`, `IV`, `V`, `vi`]` |
| `tempo_bpm` | integer | テンポ（BPM） | `120` |
| `time_signature` | string | 拍子記号 | `"4/4"` |
| `pitch_range` | array[integer] | [最低MIDIノート番号, 最高MIDIノート番号] | `[60, 84]` |
| `subdivision` | float | 最小リズム分割単位（拍数） | `0.25` (16分音符) |
| `measures` | integer | 小節数 | `2` |

#### `structure`オブジェクト

| キー | 型 | 説明 | 例 |
|-----|-----|------|-----|
| `enabled` | boolean | 構造制約が有効か | `true` / `false` |
| `repeat_unit_beats` | float \| null | リピート単位の長さ（拍数） | `4.0` (4/4で1小節), `null` |
| `rhythm_profile` | object \| null | リズムプロファイル {duration: proportion} | `{"0.5": 0.6, "1.0": 0.4}` |
| `allow_motif_variation` | boolean | モチーフの変奏を許可 | `true` / `false` |
| `variation_probability` | float | 変奏の確率 (0.0-1.0) | `0.3` |

#### `pitch_constraint`オブジェクト

| キー | 型 | 説明 | 例 |
|-----|-----|------|-----|
| `enabled` | boolean | ピッチ制約が有効か | `true` / `false` |
| `target_mean` | float \| null | 目標平均ピッチ（MIDIノート番号） | `60.0` (Middle C) |
| `tolerance` | float \| null | 許容誤差（半音） | `2.0` |
| `max_attempts` | integer \| null | 最大試行回数 | `100` |
| `attempts_used` | integer | 実際の試行回数 | `5` |

#### `result`オブジェクト

| キー | 型 | 説明 | 単位・計算方法 | 例 |
|-----|-----|------|-------------|-----|
| `note_count` | integer | ノート総数（休符含む） | 休符（pitch=0）も数える | `16` |
| `quality_score` | float | 品質スコア | 0.0-1.0 (scoredメソッドで計算) | `0.7532` |
| `total_duration_beats` | float | 合計長さ | ビート単位 (quarter note = 1 beat) | `8.0` |
| `pitch_stats` | object | ピッチ統計（レガシー用） | (下記参照) | 
| `avg_pitch` | float \| null | 平均ピッチ | 発音ノートのMIDI番号平均（休符除外）。発音ノートが0個なら `null` | `72.5` |
| `pitch_min` | integer \| null | 最低ピッチ | MIDIノート番号。発音ノートが0個なら `null` | `60` |
| `pitch_max` | integer \| null | 最高ピッチ | MIDIノート番号。発音ノートが0個なら `null` | `84` |
| `pitch_range` | integer \| null | ピッチ幅 | `pitch_max - pitch_min`。発音ノートが0個なら `null` | `24` |
| `pitch_std` | float \| null | ピッチ標準偏差 | √(Σ(p - mean)² / N)。発音ノートが0個なら `null` | `4.23` |
| `mean_interval` | float | 平均跳躍幅 | 隣接する2音の半音差絶対値の平均 | `3.25` |

**`pitch_stats`オブジェクト（レガシー互換用）:**

| キー | 型 | 説明 | 例 |
|-----|-----|------|-----|
| `mean` | float \| null | 平均ピッチ（`avg_pitch`と同値） | `72.5` |
| `min` | integer \| null | 最低ピッチ（`pitch_min`と同値） | `60` |
| `max` | integer \| null | 最高ピッチ（`pitch_max`と同値） | `84` |
| `range` | integer \| null | ピッチ幅（`pitch_range`と同値） | `24` |
| `sounding_count` | integer | 発音ノート数（休符除外） | `12` |

#### `debug_stats`オブジェクト

| キー | 型 | 説明 | 例 |
|-----|-----|------|-----|
| `duration_distribution` | object | 音価の分布 {duration_beats: count} | `{"0.5": 8, "1.0": 4}` |
| `scale_out_rejections` | integer | スケール外ピッチの棄却数 | `0` |
| `octave_up_events` | integer | オクターブ上げイベント数 | `1` |
| `total_beats` | float | 合計ビート数 | `8.0` |
| `repeat_count` | integer | リピート回数 | `2` |
| `actual_duration_distribution` | object | 実際の音価割合 {duration: proportion} | `{"0.5": 0.625, "1.0": 0.375}` |

### メトリクス定義

#### ピッチ系メトリクス

**avg_pitch (平均ピッチ)**
- **定義**: `mean(p_i)`ただし`p_i`は各発音ノートのMIDIピッチ番号
- **計算対象**: 休符（`pitch = 0`）は除外
- **型**: float | null
- **単位**: MIDIノート番号（60 = Middle C）
- **実装**: `songMaking/pitch_stats.py`の`compute_pitch_stats()`

**note_count (ノート数)**
- **定義**: ノートイベントの総数
- **計算対象**: 休符を**含む**
- **型**: integer
- **実装**: `len(pitches)`（`pitches`はMIDI pitch値のリスト）

**pitch_min / pitch_max**
- **定義**: `min(p_i)` / `max(p_i)`ただし`p_i`は発音ノートのMIDIピッチ
- **計算対象**: 休符は除外
- **型**: integer | null
- **単位**: MIDIノート番号

**pitch_range**
- **定義**: `pitch_max - pitch_min`
- **型**: integer | null
- **単位**: 半音

**pitch_std (ピッチ標準偏差)**
- **定義**: `√(Σ(p_i - avg_pitch)² / N)`ただしNは発音ノート数
- **計算対象**: 休符は除外
- **型**: float | null
- **単位**: 半音（標準偏差）
- **特殊ケース**: 発音ノート1個のみの場合は`0.0`

**mean_interval (平均跳躍幅)**
- **定義**: `mean(abs(p_i - p_{i-1}))`
- **計算対象**: MIDI生成後のnote_on (velocity > 0) を時系列順に並べたピッチ列。同tick内は最高音のみ採用
- **型**: float
- **単位**: 半音

#### リズム系メトリクス

**total_duration_beats**
- **定義**: `Σ duration_i`
- **型**: float
- **単位**: beats (quarter note = 1 beat)

**duration_distribution**
- **定義**: 各音価の出現回数
- **型**: object `{duration_beats: count}`
- **例**: `{"0.5": 8, "1.0": 4}` → 8分音符8個、4分音符4個

**actual_duration_distribution**
- **定義**: 各音価の割合
- **型**: object `{duration_beats: proportion}`
- **計算**: `count / total_count`
- **例**: `{"0.5": 0.667, "1.0": 0.333}`

### 実装依存の注意事項

1. **休符の扱い**  
   - MIDI pitch値`0`を休符として扱う  
   - `note_count`は休符を**含む**が、`avg_pitch`等のピッチ統計は休符を**除外**

2. **ノートオン/オフの単位**  
   - 1ノート = MIDIUtilの`addNote()`1回呼び出し  
   - 和音（同時発音）は未実装（現在は単旋律のみ）

3. **時間単位**  
   - すべてのdurationは**ビート単位**(quarter note = 1.0 beat)  
   - BPMとの関係: `duration_seconds = (duration_beats / tempo_bpm) * 60.0`

4. **MIDIチャンネル**  
   - 常にchannel 0  
   - 楽器: Acoustic Grand Piano (program 0)

5. **テンポ変更**  
   - 1曲中でテンポは固定（`tempo_bpm`の値）

## Hydral 音声パイプライン (`python -m hydral`)

`data/raw/` 内の音声ファイルを1コマンドで処理し、`data/processed/hydral/` に出力します。

### セットアップ

```bash
pip install -r requirements.txt
export PYTHONPATH=src   # または python -m を使う場合は不要
```

### YAMLパイプライン実行（`run`）

設定ファイル1つで全処理ステップをまとめて実行します。

#### 1. `pipeline.yaml` を編集する

リポジトリルートにある `pipeline.yaml` を開き、入力・出力パスとステップを設定します。

```yaml
pipeline:
  name: "hydral_default"
  input: "data/raw"                  # 入力ルートフォルダ（またはファイルパス）
  output: "data/processed/hydral"    # 出力ルートフォルダ
  glob:                              # 再帰的に検索する拡張子
    - "**/*.wav"
    - "**/*.mp3"
    - "**/*.flac"
    - "**/*.m4a"
  steps:
    - name: analyze          # 特徴量抽出 → JSON 出力
      enabled: true
      params:
        sr: 22050            # サンプルレート（省略可）
        hop_length: 512
        smoothing_window: 5
    - name: normalize        # ピーク正規化
      enabled: true
      params:
        target_db: -1.0
    - name: band_split       # 周波数帯域分割（無効例）
      enabled: false
      params:
        filter_order: 5
    - name: grain            # グレイン・シャッフル（無効例）
      enabled: false
      params:
        grain_sec: 0.5
        seed: 42
```

`enabled: false` にすることでステップをスキップできます。

#### 2. パイプラインを実行する

```bash
# デフォルト（./pipeline.yaml を読む）
python -m hydral run

# 設定ファイルを明示的に指定
python -m hydral run --config pipeline.yaml
```

#### 出力ディレクトリ構成

```
data/processed/hydral/
├── <ファイル名（拡張子なし）>/
│   ├── <stem>_features.json     # analyze ステップ
│   ├── <stem>_normalized.wav    # normalize ステップ
│   ├── <stem>_grain.wav         # grain ステップ
│   └── <stem>_bands/            # band_split ステップ
│       ├── band01_tonal.wav
│       ├── band01_noise.wav
│       ├── ...
│       └── split_manifest.json
├── runs/
│   └── <run_id>/
│       └── <stem>/
│           └── .cache/
│               └── manifest.json    # 再現性用フィンガープリント（各ステップのパラメータ＋入力メタ）
└── _runs/
    └── run_<YYYYMMDD_HHMMSS>.json   # 実行レポート（毎回生成）
```

#### 実行レポート（JSON）

各実行ごとに `data/processed/hydral/_runs/run_<timestamp>.json` が作成されます。

```json
{
  "run_id": "20260221_015101",
  "pipeline_name": "hydral_default",
  "started_at": "2026-02-21T01:51:01",
  "finished_at": "2026-02-21T01:51:03",
  "total_elapsed_sec": 2.1,
  "files": [
    {
      "input": "data/raw/track.wav",
      "status": "success",
      "steps": [
        { "name": "analyze",   "status": "ran",              "elapsed_sec": 0.72, "outputs": [...] },
        { "name": "normalize", "status": "ran",              "elapsed_sec": 0.01, "outputs": [...] },
        { "name": "band_split","status": "skipped_disabled", "elapsed_sec": 0    },
        { "name": "grain",     "status": "skipped_exists",   "elapsed_sec": 0    }
      ]
    }
  ]
}
```

ステップの `status` は以下のいずれかです：

| status | 意味 |
|--------|------|
| `ran` | 正常実行 |
| `skipped_disabled` | `enabled: false` のためスキップ |
| `skipped_exists` | 出力ファイルが既に存在するためスキップ |
| `failed` | エラー発生（`error` フィールドに詳細） |

#### 再現性マニフェスト（`.cache/manifest.json`）

`data/processed/hydral/runs/<run_id>/<stem>/.cache/manifest.json` に各ステップのフィンガープリントが保存されます。フィンガープリントにはステップ名・入力ファイルのサイズとmtime・ステップパラメータが含まれ、同じ入力・同じ設定で再実行したときに以前の結果と比較できます。

```json
{
  "normalize": {
    "step": "normalize",
    "input": "data/raw/track.wav",
    "input_stat": { "size": 4410044, "mtime": 1740000000.0 },
    "params": { "target_db": -1.0 }
  },
  "analyze": {
    "step": "analyze",
    "input": "data/raw/track.wav",
    "input_stat": { "size": 4410044, "mtime": 1740000000.0 },
    "params": { "hop_length": 512, "smoothing_window": 5, "sr": 22050 }
  }
}
```

#### 設定バリデーション

`load_config` は設定ファイルの読み込み時に以下を検証します。エラーがある場合はパイプライン実行前に詳細なメッセージで失敗します。

- `pipeline` キーの存在
- `steps` がリスト形式であること
- 有効（`enabled: true`）なステップ名が登録済みであること（未知の名前は `ValueError` + "Known steps: …" で通知）

> **注意**: `enabled: false` のステップは名前が未知でもエラーにならず、無視されます。

---

### 音声解析（`analyze`）

WAV / MP3 / FLAC ファイルを解析し、JSON ファイルを出力します。

```bash
# 1ファイルを解析
python -m hydral analyze data/raw/track.wav

# フォルダ内の全ファイルをまとめて解析
python -m hydral analyze data/raw/

# 出力先・サンプルレートを指定
python -m hydral analyze data/raw/track.wav --out data/processed/hydral --sr 22050
```

#### 音声処理（`process`）

1つ以上の処理ステップを組み合わせて適用します。

```bash
# ピーク正規化
python -m hydral process data/raw/track.wav --normalize

# 周波数帯域分割（低域・中域・高域・トーナル/ノイズ）
python -m hydral process data/raw/track.wav --band-split

# グレイン・シャッフル（粒状合成）
python -m hydral process data/raw/track.wav --grain

# 複数ステップを同時に適用
python -m hydral process data/raw/track.wav --normalize --band-split --grain

# フォルダ内の全ファイルを一括処理
python -m hydral process data/raw/ --normalize --grain

# グレインの長さとシードを指定
python -m hydral process data/raw/track.wav --grain --grain-sec 0.25 --seed 123
```

### 出力先ディレクトリ構成

```
data/processed/hydral/
└── <ファイル名（拡張子なし）>/
    ├── <stem>_features.json     # analyze → RMS・帯域エネルギー・オンセット
    ├── <stem>_normalized.wav    # --normalize → ピーク正規化済み音声
    ├── <stem>_grain.wav         # --grain → グレイン・シャッフル済み音声
    └── <stem>_bands/            # --band-split → 帯域分割 WAV + マニフェスト
        ├── band01_tonal.wav
        ├── band01_noise.wav
        ├── ...
        └── split_manifest.json
```

### オプション一覧

#### `analyze`

| オプション | デフォルト | 説明 |
|-----------|-----------|------|
| `input` | （必須） | WAV/MP3/FLAC ファイルまたはフォルダ |
| `--out DIR` | `data/processed/hydral` | 出力ルートディレクトリ |
| `--sr HZ` | 元のまま | リサンプリング後のサンプルレート |
| `--hop-length N` | `512` | 解析フレームのホップ幅（サンプル数） |
| `--smoothing-window N` | `5` | 平滑化窓サイズ（フレーム数） |

#### `process`

| オプション | デフォルト | 説明 |
|-----------|-----------|------|
| `input` | （必須） | WAV/MP3/FLAC ファイルまたはフォルダ |
| `--out DIR` | `data/processed/hydral` | 出力ルートディレクトリ |
| `--normalize` | off | ピーク正規化（−1 dBFS） |
| `--band-split` | off | 5帯域 × トーナル/ノイズ分割 |
| `--grain` | off | グレイン・シャッフル後に再連結 |
| `--grain-sec SEC` | `0.5` | グレイン長（秒） |
| `--seed SEED` | `42` | グレイン・シャッフルの乱数シード |

### パイプライン API（Python からの利用）

```python
from pathlib import Path
from hydral.pipeline import Pipeline, PipelineContext
from hydral.steps import AnalyzeStep, NormalizeStep, GrainStep

ctx = PipelineContext(
    input_path=Path("data/raw/track.wav"),
    output_dir=Path("data/processed/hydral/track"),
)

Pipeline([
    AnalyzeStep(),
    NormalizeStep(target_db=-3.0),
    GrainStep(grain_sec=0.25, seed=99),
]).run(ctx)
```

#### `PipelineContext` の主要フィールド

| フィールド | 説明 |
|-----------|------|
| `input_path` | 元の入力ファイルパス（変更されない） |
| `audio_path` | 現在の音声入力パス。変換ステップ（normalize / grain / band_split）が実行されるたびに出力ファイルへ更新され、後続ステップがパイプ経由で処理結果を受け取れる |
| `output_dir` | 出力ディレクトリ |
| `artifacts` | `Artifacts` インスタンス（型付き出力パス。下記参照） |
| `sample_rate` | サンプルレートの上書き（省略可） |
| `extra` | デバッグ用の自由形式 dict（コア出力には使わない） |

#### `ctx.artifacts`（型付き出力パス）

ステップ実行後に対応フィールドへ `Path` がセットされます。

```python
ctx.artifacts.features_json      # analyze → JSON パス
ctx.artifacts.normalized_wav     # normalize → WAV パス
ctx.artifacts.grain_wav          # grain → WAV パス
ctx.artifacts.band_dir           # band_split → 帯域ディレクトリ
ctx.artifacts.band_manifest_json # band_split → マニフェスト JSON パス
```

#### カスタムステップの作り方

`BaseStep` を継承してカスタムステップを作れます。`StepRegistry.register()` で登録すると YAML から利用可能になります。

```python
from hydral.steps.base import BaseStep
from hydral.steps.registry import StepRegistry
from hydral.pipeline import PipelineContext

class MyStep(BaseStep):
    step_name = "my_step"

    def __init__(self, param: float = 1.0) -> None:
        self.param = param

    def run(self, ctx: PipelineContext) -> PipelineContext:
        # 処理を実装（変換ステップは ctx.audio_path を更新する）
        return ctx

    def outputs(self, ctx):
        return [ctx.output_dir / f"{ctx.input_path.stem}_my_step.wav"]

    def fingerprint(self, ctx):
        fp = super().fingerprint(ctx)
        fp["params"] = {"param": self.param}
        return fp

StepRegistry.register("my_step", MyStep)
```

`BaseStep` の最小契約：

| メソッド / プロパティ | 必須 | 説明 |
|---------------------|------|------|
| `step_name: str` | ✓ | YAML `name` と一致する識別子 |
| `run(ctx) -> ctx` | ✓ | ステップの本体。変換ステップは `ctx.audio_path` を更新する |
| `outputs(ctx)` | 推奨 | このステップが生成するファイルパスのリスト |
| `fingerprint(ctx)` | 推奨 | JSON 直列化可能な再現性メタデータ dict |
| `validate(ctx)` | 任意 | 実行前の入力検証（問題があれば `ValueError`） |

## Design Principles

- 各モジュールの単一責任
- 隠れた副作用なし
- すべての特徴にわたる安定した時間整合性
- 分析結果は説明可能でデバッグ可能である必要があります
- `/songMaking`は`/hydral`の水音声ツールに依存しません

> Hydralは、単に聞くものではなく、計測し、構造化し、表現に変換するものとして音を扱います。

## Status

このプロジェクトはアクティブに開発中です。インターフェースは進化する可能性がありますが、レイヤー分離と分析セマンティクスは安定したものと見なされます。

## License

未定。
