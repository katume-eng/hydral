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

## Audio Analysis Pipeline

(保持する既存の音声分析内容)

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
