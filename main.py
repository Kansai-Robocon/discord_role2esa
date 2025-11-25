import os
import requests
import re
import unicodedata
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv()

# --- 設定値 ---
DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN")
DISCORD_GUILD_ID = os.environ.get("DISCORD_GUILD_ID")

# esa設定
ESA_ACCESS_TOKEN = os.environ.get("ESA_ACCESS_TOKEN")
ESA_TEAM_NAME = os.environ.get("ESA_TEAM_NAME")
ESA_POST_ID = os.environ.get("ESA_POST_ID")

INCLUDE_ROLE_NAMES = [
    "ルール",
    "チーム対応",
    "広報",
    "資金獲得",
    "事務",
]
OFFICER_ROLE_NAME = "役つき"

MANUAL_STAR_MAPPING = {
    "ルール": ["野﨑幸汰(大阪大学/京都工芸繊維大学OB)"],
    "広報": ["森晴香（同志社大学）"],
    "チーム対応": ["奥田真生(京都大学)"],
    "資金獲得": ["豊浦 望(富山大学)"],
    "事務": ["Hideto Niwa(大阪大学OB)"]
}

DISCORD_API_BASE = "https://discord.com/api/v10"
HEADERS_DISCORD = {"Authorization": f"Bot {DISCORD_TOKEN}"}
HEADERS_ESA = {"Authorization": f"Bearer {ESA_ACCESS_TOKEN}"}


def fetch_discord_data():
    print("Fetching data from Discord...")
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


def get_visual_width(text):
    """全角2、半角1として幅を計算する"""
    width = 0
    for c in text:
        if unicodedata.east_asian_width(c) in ('F', 'W', 'A'):
            width += 2
        else:
            width += 1
    return width


def truncate_visual_width(text, max_width):
    """指定した幅(max_width)に収まるように文字列をカットする"""
    current_width = 0
    result = ""
    for c in text:
        char_width = 2 if unicodedata.east_asian_width(
            c) in ('F', 'W', 'A') else 1
        if current_width + char_width > max_width:
            break
        current_width += char_width
        result += c
    return result


def format_member_name(member, role_name, officer_role_id, truncate=False):
    user = member['user']
    raw_name = member.get('nick') or user.get(
        'global_name') or user['username']

    # 1. 先に星が付く対象かを判定
    star_list = MANUAL_STAR_MAPPING.get(role_name, [])
    found_star = False
    if raw_name in star_list:
        found_star = True

    # 2. カット処理
    if truncate:
        if found_star:
            # 星あり: 全角11文字(幅22)以上 -> 全角10文字(幅20)
            limit_width = 22
            target_width = 20
        else:
            # 星なし: 全角13文字(幅26)以上 -> 全角12文字(幅24)
            limit_width = 26
            target_width = 24

        if get_visual_width(raw_name) >= limit_width:
            raw_name = truncate_visual_width(raw_name, target_width)

    # 3. エスケープ処理
    safe_name = raw_name\
        .replace('\\', '')\
        .replace('"', "'")\
        .replace('<', '&lt;')\
        .replace('>', '&gt;')\
        .replace('[', '【')\
        .replace(']', '】')\
        .replace('{', '｛')\
        .replace('}', '｝')

    # 4. 役つき斜体
    is_officer = False
    if officer_role_id and officer_role_id in member['roles']:
        is_officer = True
        safe_name = f"<i>{safe_name}</i>"

    # 5. 星マーク付与
    if found_star:
        safe_name = f"☆ {safe_name}"

    return safe_name, is_officer


def generate_mermaid_hierarchy(roles, members):
    mermaid_text = "```mermaid\n%%{init: {'flowchart': {'curve': 'stepAfter', 'nodeSpacing': 50, 'rankSpacing': 40}}}%%\ngraph TD\n"

    # --- CSS定義 ---
    mermaid_text += "    classDef defaultBox fill:#FFFFFF,stroke:#000000,color:#000000,stroke-width:2px;\n"
    mermaid_text += "    classDef rootBox fill:#fAf,stroke:#000000,color:#000000,stroke-width:4px;\n"
    mermaid_text += "    classDef officerBox fill:#FFFFFF,stroke:#000000,color:#000000,stroke-width:4px;\n\n"

    # --- 1. 運営委員会 (Root) ---
    mermaid_text += '    Root["<div style=\'width:400px\'><span style=\'font-size:20px\'><b>関西春ロボコン運営委員会</b></span></div>"]:::rootBox\n'

    officer_role = next(
        (r for r in roles if r['name'] == OFFICER_ROLE_NAME), None)
    officer_role_id = officer_role['id'] if officer_role else None

    # --- 2. 役つきロール (Middle) ---
    if officer_role:
        officer_members = get_members_in_role(officer_role_id, members)

        display_lines = []
        for m in officer_members:
            formatted_name, _ = format_member_name(
                m, OFFICER_ROLE_NAME, officer_role_id, truncate=False)
            display_lines.append(formatted_name)

        display_lines.sort(key=lambda s: (not ("☆" in s), s))

        if not display_lines:
            content = "(所属なし)"
        else:
            content = "<br/>".join(display_lines) + "<br/><span> </span>"

        node_html = f"<div style='width:300px'><span style='font-size:20px'><b>{OFFICER_ROLE_NAME}</b></span><hr/><div style='text-align:left; font-size:16px'>{content}</div></div>"

        mermaid_text += f'    OfficerNode["{node_html}"]:::officerBox\n'
        mermaid_text += '    Root --> OfficerNode\n'
    else:
        mermaid_text += '    OfficerNode["役つき不明"]:::officerBox\n'
        mermaid_text += '    Root --> OfficerNode\n'

    # --- 3. 各実務ロール (Bottom) ---
    role_data_list = []
    max_lines = 0

    for role_name in INCLUDE_ROLE_NAMES:
        target_role = next((r for r in roles if r['name'] == role_name), None)
        if not target_role:
            continue

        role_id = target_role['id']
        role_members = get_members_in_role(role_id, members)

        display_lines = []
        for m in role_members:
            formatted_name, _ = format_member_name(
                m, role_name, officer_role_id, truncate=True)
            display_lines.append(formatted_name)

        display_lines.sort(key=lambda s: (not ("☆" in s), s))

        current_line_count = len(display_lines) if display_lines else 1
        if current_line_count > max_lines:
            max_lines = current_line_count

        role_data_list.append({
            "id": role_id,
            "name": role_name,
            "lines": display_lines
        })

    # ノード生成
    for data in role_data_list:
        display_lines = data["lines"]

        if not display_lines:
            content_body = "(所属なし)"
            current_lines = 1
        else:
            content_body = "<br/>".join(display_lines)
            current_lines = len(display_lines)

        diff = max_lines - current_lines
        if diff > 0:
            padding = "<br/><span>&nbsp;</span>" * diff
            content_body += padding

        content_body += "<br/><span> </span>"

        node_html = f"<div style='width:200px'><span style='font-size:20px'><b>{data['name']}</b></span><hr/><div style='text-align:left; font-size:16px'>{content_body}</div></div>"

        mermaid_text += f'    Role{data["id"]}["{node_html}"]:::defaultBox\n'

        mermaid_text += f'    OfficerNode --> Role{data["id"]}\n'

    mermaid_text += "    linkStyle default stroke-width:2px,fill:none,stroke:black;\n"

    mermaid_text += "```"
    return mermaid_text


def update_esa_section(new_chart_content):
    print("Updating esa.io post...")

    if not all([ESA_ACCESS_TOKEN, ESA_TEAM_NAME, ESA_POST_ID]):
        print("Error: esa settings (TOKEN, TEAM_NAME, POST_ID) are missing in .env")
        return

    url = f"https://api.esa.io/v1/teams/{ESA_TEAM_NAME}/posts/{ESA_POST_ID}"

    # 1. 現在の記事を取得
    res = requests.get(url, headers=HEADERS_ESA)
    if res.status_code != 200:
        print(f"Error getting post: {res.status_code} {res.text}")
        return

    post_data = res.json()
    current_body = post_data['body_md']

    # 【修正】 現在のWIP状態を取得（勝手に公開/非公開が変わらないようにする）
    current_wip = post_data.get('wip', False)

    start_marker = "<!--START_DIAGRAM-->"
    end_marker = "<!--END_DIAGRAM-->"

    jst = timezone(timedelta(hours=9))
    now_str = datetime.now(jst).strftime('%Y/%m/%d %H:%M')

    replacement = f"{start_marker}\n\n最終更新: {now_str}\n{new_chart_content}\n{end_marker}"

    pattern = f"({re.escape(start_marker)})(.*?)({re.escape(end_marker)})"
    new_body = re.sub(pattern, replacement, current_body, flags=re.DOTALL)

    if new_body == current_body:
        print("Warning: Markers not found in the esa post.")
        return

    payload = {
        "post": {
            "body_md": new_body,
            "wip": current_wip,   # 【修正】 現在の状態を維持
            "skip_notice": True   # 通知をスキップ
        }
    }

    patch_res = requests.patch(url, headers=HEADERS_ESA, json=payload)
    if patch_res.status_code == 200:
        print("esa updated successfully! (Notification should be skipped)")
    else:
        print(f"Error updating post: {patch_res.status_code} {patch_res.text}")
        print("\n--- [Debug] Generated Mermaid Text ---")
        print(new_chart_content)
        print("--------------------------------------")


if __name__ == "__main__":
    try:
        roles, members = fetch_discord_data()
        diagram = generate_mermaid_hierarchy(roles, members)
        update_esa_section(diagram)

    except Exception as e:
        print(f"An error occurred: {e}")
