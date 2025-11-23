import os
import requests
import re
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv()

# --- 設定値 (前回のご要望通り ID2 を参照) ---
DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN")
DISCORD_GUILD_ID = os.environ.get("DISCORD_GUILD_ID2")

# esa設定
ESA_ACCESS_TOKEN = os.environ.get("ESA_ACCESS_TOKEN")
ESA_TEAM_NAME = os.environ.get("ESA_TEAM_NAME")
ESA_POST_ID = os.environ.get("ESA_POST_ID2")

DISCORD_API_BASE = "https://discord.com/api/v10"
HEADERS_DISCORD = {"Authorization": f"Bot {DISCORD_TOKEN}"}
HEADERS_ESA = {"Authorization": f"Bearer {ESA_ACCESS_TOKEN}"}

SPECIAL_ROLE_NAME = "関西合同練習試合🏆"


def fetch_discord_data():
    print(f"Fetching data from Discord (Guild ID: {DISCORD_GUILD_ID})...")

    if not DISCORD_GUILD_ID:
        print("Error: DISCORD_GUILD_ID2 is not set.")
        exit(1)

    roles_res = requests.get(
        f"{DISCORD_API_BASE}/guilds/{DISCORD_GUILD_ID}/roles", headers=HEADERS_DISCORD)
    if roles_res.status_code != 200:
        print(f"Error fetching roles: {roles_res.text}")
        exit(1)
    roles = roles_res.json()
    roles.sort(key=lambda x: x['position'], reverse=True)

    members_res = requests.get(
        f"{DISCORD_API_BASE}/guilds/{DISCORD_GUILD_ID}/members?limit=1000", headers=HEADERS_DISCORD)
    if members_res.status_code != 200:
        print(f"Error fetching members: {members_res.text}")
        exit(1)
    members = members_res.json()

    return roles, members


def get_members_in_role(role_id, members):
    target_members = []
    for m in members:
        if m['user'].get('bot'):
            continue
        if role_id in m['roles']:
            target_members.append(m)
    return target_members


def get_members_without_role(members):
    target_members = []
    for m in members:
        if m['user'].get('bot'):
            continue
        if not m['roles']:
            target_members.append(m)
    return target_members


def format_member_name(member):
    """メンバー名を整形（Markdownエスケープ）"""
    user = member['user']
    raw_name = member.get('nick') or user.get(
        'global_name') or user['username']

    safe_name = raw_name\
        .replace('\\', '')\
        .replace('*', '\\*')\
        .replace('_', '\\_')\
        .replace('[', '\\[')\
        .replace(']', '\\]')\
        .replace('<', '&lt;')\
        .replace('>', '&gt;')

    return safe_name


def extract_school_name(member):
    user = member['user']
    raw_name = member.get('nick') or user.get(
        'global_name') or user['username']
    match_paren = re.search(r'[（\(]([^）\)]*?(?:大学|高専)[^）\)]*?)[）\)]', raw_name)
    if match_paren:
        return match_paren.group(1).strip()
    match_direct = re.search(r'([^\s]*?(?:大学|高専)[^\s]*)', raw_name)
    if match_direct:
        return match_direct.group(1).strip()
    return "その他"


def analyze_name_error(member):
    """
    命名規則違反の理由を判定して返す (緩和版)
    規則: 苗字..._役割...(所属校)
    """
    user = member['user']
    raw_name = member.get('nick') or user.get(
        'global_name') or user['username']

    # 1. アンダースコアがあるか
    if "_" not in raw_name:
        return "区切り文字 `_` (アンダースコア) がありません"

    # 最初の_で分割して、後半部分を見る（2つ以上あってもOK）
    parts = raw_name.split("_", 1)

    # parts[0] = 名前 (ローマ字チェックは無視してOK)
    # parts[1] = 役割(所属校)

    after_underscore = parts[1]

    # 2. 後半に所属校の括弧があるか
    if not re.search(r"[（\(].+[）\)]", after_underscore):
        return "役割・所属部分に `( )` (所属校) がありません"

    return None  # OK


def generate_markdown_list_all(roles, members):
    lines = []

    # ==========================================
    # 1. ロール別 ユーザ一覧
    # ==========================================
    lines.append("\n### ロール別 ユーザ一覧")

    for role in roles:
        if role['name'] == '@everyone':
            continue

        role_members = get_members_in_role(role['id'], members)
        if not role_members:
            continue

        if role['name'] == SPECIAL_ROLE_NAME:
            lines.append(f"- **{role['name']}** (学校別)")
            school_groups = defaultdict(list)
            for m in role_members:
                school_name = extract_school_name(m)
                school_groups[school_name].append(format_member_name(m))

            sorted_schools = sorted(
                school_groups.keys(), key=lambda s: (s == "その他", s))
            for school in sorted_schools:
                lines.append(f"    - **{school}**")
                for name in sorted(school_groups[school]):
                    lines.append(f"        - {name}")
        else:
            lines.append(f"- **{role['name']}**")
            display_names = [format_member_name(m) for m in role_members]
            display_names.sort()
            for name in display_names:
                lines.append(f"    - {name}")

    # ロールなし
    no_role_members = get_members_without_role(members)
    if no_role_members:
        lines.append("- **(ロールなし)**")
        display_names = [format_member_name(m) for m in no_role_members]
        display_names.sort()
        for name in display_names:
            lines.append(f"    - {name}")

    # ==========================================
    # 2. 命名規則に従っていない人 (理由別)
    # ==========================================
    lines.append("\n### 命名規則に従っていない人")
    lines.append("> 規則: `苗字..._役割...(所属校)`")
    lines.append("> (ローマ字や_の個数は不問)")

    error_groups = defaultdict(list)

    for m in members:
        if m['user'].get('bot'):
            continue

        error_msg = analyze_name_error(m)
        if error_msg:
            error_groups[error_msg].append(format_member_name(m))

    if error_groups:
        for reason in sorted(error_groups.keys()):
            lines.append(f"\n### ⚠️ {reason}")
            for name in sorted(error_groups[reason]):
                lines.append(f"- {name}")
    else:
        lines.append("\n- (違反者なし ✅)")

    return "\n".join(lines)


def update_esa_section(new_content):
    print(f"Updating esa.io post (Post ID: {ESA_POST_ID})...")

    if not all([ESA_ACCESS_TOKEN, ESA_TEAM_NAME, ESA_POST_ID]):
        print("Error: esa settings are missing in .env")
        return

    url = f"https://api.esa.io/v1/teams/{ESA_TEAM_NAME}/posts/{ESA_POST_ID}"

    res = requests.get(url, headers=HEADERS_ESA)
    if res.status_code != 200:
        print(f"Error getting post: {res.status_code} {res.text}")
        return

    post_data = res.json()
    current_body = post_data['body_md']
    current_wip = post_data.get('wip', False)

    start_marker = "<!--START_LIST-->"
    end_marker = "<!--END_LIST-->"

    jst = timezone(timedelta(hours=9))
    now_str = datetime.now(jst).strftime('%Y/%m/%d %H:%M')

    replacement = f"{start_marker}\n\n最終更新: {now_str}\n\n{new_content}\n\n{end_marker}"

    pattern = f"({re.escape(start_marker)})(.*?)({re.escape(end_marker)})"
    new_body = re.sub(pattern, replacement, current_body, flags=re.DOTALL)

    if new_body == current_body:
        print("Warning: Markers not found in the esa post.")
        return

    payload = {
        "post": {
            "body_md": new_body,
            "message": "Update Organization List via Script",
            "wip": current_wip,
            "skip_notice": True
        }
    }

    patch_res = requests.patch(url, headers=HEADERS_ESA, json=payload)
    if patch_res.status_code == 200:
        print("esa updated successfully! (Notification Skipped)")
    else:
        print(f"Error updating post: {patch_res.status_code} {patch_res.text}")


if __name__ == "__main__":
    try:
        roles, members = fetch_discord_data()
        markdown_list = generate_markdown_list_all(roles, members)

        # コンソール確認用
        print("\n--- 生成されたMarkdown (ここから) ---\n")
        print(markdown_list)
        print("\n--- 生成されたMarkdown (ここまで) ---\n")

        # 本番更新用
        update_esa_section(markdown_list)

    except Exception as e:
        print(f"An error occurred: {e}")
