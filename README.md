![](https://github.com/Kansai-Robocon/discord_role2esa/actions/workflows/for_communication.yml/badge.svg)
![](https://github.com/Kansai-Robocon/discord_role2esa/actions/workflows/daily_org_chart.yml/badge.svg)

## レポジトリ概要
- メンバーをDiscordより取得
- 組織図やメンバーリストを生成
- esaの指定ページへコミット

## 主なフロー
### main.py
1. メンバーをDiscordより一覧取得
2. Marmaidによってロール別の組織図を生成
3. esaへコミット

### for_communication.py
1. メンバーをDiscordより一覧取得
2. ロール別にリスト生成
3. 命名規則に従っていない人リストを生成
4. esaへコミット

## ファイル構造

```bash
C:.
│  .gitignore
│  for_communication.py # for_communication.ymlによって動く、メンバーリスト生成
│  main.py # daily_org_chart.ymlによって動く、組織図生成
│  README.md
│  requirements.txt # pythonを実行するにあたり必要なライブラリインストール
│
└─.github
    └─workflows
            daily_org_chart.yml
            for_communication.yml
```