---
name: Hydral Audio + SongMaking Agent
description: Hydral専用。水音編集（/hydral）と、無関係なMIDI生成（/songMaking）を同一リポジトリ内で"運用統一"するためのCopilotカスタムエージェント。
language: ja
---

# My Agent

## Scope
このリポジトリは2つの独立サブシステムを同居させます。

A) **Hydral（水音編集）**: フィールド録音の水音を解析・編集し、素材化/配布可能な品質に整える。  
B) **SongMaking（楽曲生成）**: 水音とは無関係に、random もしくは ML によって **MIDIを生成**する。

両者はアルゴリズム的に結合しません。同居の目的は「同じ制作OSとして、CLI・設定・出力規約・品質基準を統一する」ことです。

## Primary goals
1) Water Audio Editing (/hydral)
- 水音の取り込み、品質検査、編集、書き出し、素材パック化
- メタデータ整備（タグ、収録条件、命名規則、README生成）

2) MIDI Generation (/songMaking)
- seed固定で再現可能なMIDI生成（random / ML）
- 生成物の評価（音域、跳躍、密度、反復、長さ、コード整合などの自動チェック）
- 出力フォーマット統一（MIDI + 生成パラメータのjsonログ）

3) Shared shipping & operations (repo-wide)
- 共通CLI（例：`hydral audio ...` / `hydral song ...`）
- 共通設定（config）とログ、成果物のディレクトリ規約
- テスト（fixtureによる回帰）とパフォーマンス配慮
- ライセンス/利用規約/配布物構成のテンプレ生成

## Behavior rules
- 変更は小さく、再現手順と検証を必ず添える
- /hydral と /songMaking を混ぜない（依存を増やさない）
- "同じシステム感"は、CLI・config・export・テストで出す
- **すべてのコミットメッセージ、PRタイトル・説明、コードコメント、レビューコメントは日本語で記述する**

## Typical tasks
- 水音のバッチ編集パイプライン実装、品質レポート生成
- MIDI生成器の追加（確率モデル、ルールベース、Transformer等の段階導入）
- 生成結果の自動スコアリングとフィルタ（採用候補だけ残す）
- exportのzip構成とREADME/規約の自動生成
