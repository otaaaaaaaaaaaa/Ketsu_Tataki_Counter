
import os
import logging
from datetime import datetime

from fastapi import FastAPI, Request

from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError

from linebot.models import (
    MessageEvent,
    TextMessage,
    TextSendMessage,
    QuickReply,
    QuickReplyButton,
    MessageAction
)

from database import (
    get_user,
    create_user,
    get_user_by_name,
    get_all_names,
    transfer_points,
    get_total_ranking,
    get_current_ranking,
    add_oni_count,
    update_user,
    get_oni_card,
    update_oni_card,
    add_oni_history,
    get_oni_ranking,
    get_items,
    buy_item,
    get_item,
    get_user_items,
    use_item,
    get_all_oni_cards,
    add_points_all,
    reset_all_data,

    # ルーム管理
    DEFAULT_ROOM_ID,
    get_user_active_room,
    get_room,
    create_room,
    join_room,
    leave_room,
    get_room_members,
    get_room_member_ids,
    get_room_user_stats,
    update_room_user_stats,
    add_room_points,
    consume_room_points,
    get_room_ranking,

    # ルーム別鬼カード
    get_room_oni_card,
    get_all_room_oni_cards,
    update_room_oni_card,
    add_room_oni_history,
    get_room_oni_ranking,

    # ルーム別アイテム
    get_room_items,
    get_room_item,
    get_room_user_items,
    buy_room_item,
    use_room_item,

    # 試合管理
    start_match,
    get_active_match,
    finish_match,
    get_match_result,
    add_match_points,
    consume_match_points,
    reset_room_for_rematch,
    delete_room
)


# ========================================
# 基本設定
# ========================================

app = FastAPI()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CHANNEL_ACCESS_TOKEN = os.getenv("CHANNEL_ACCESS_TOKEN")
CHANNEL_SECRET = os.getenv("CHANNEL_SECRET")
ADMIN_USER_ID = os.getenv("ADMIN_USER_ID")

if not CHANNEL_ACCESS_TOKEN or not CHANNEL_SECRET:
    raise RuntimeError(
        "CHANNEL_ACCESS_TOKEN または CHANNEL_SECRET が設定されていません"
    )

line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)


# ========================================
# 入力待ち状態
# ========================================

transfer_waiting = {}
point_waiting = {}
count_waiting = {}
oni_card_waiting = {}
item_waiting = {}
item_action_waiting = {}
oni_setup_waiting = {}
oni_confirm_waiting = {}

room_join_waiting = {}


# ========================================
# 共通関数
# ========================================

def get_current_room_id(user_id):
    """ユーザーが現在利用しているルームID"""

    return get_user_active_room(user_id)


def get_current_room_members(user_id):
    """現在のルームの参加者一覧"""

    room_id = get_current_room_id(user_id)

    if not room_id:
        return []

    return get_room_members(room_id)


def is_room_owner(user_id, room_id=None):
    """ルーム管理者か確認"""

    if room_id is None:
        room_id = get_current_room_id(user_id)

    if not room_id:
        return False

    room = get_room(room_id)

    if not room:
        return False

    return room.get("owner_user_id") == user_id


def is_admin(user_id):
    return bool(
        ADMIN_USER_ID
        and user_id == ADMIN_USER_ID
    )


def get_user_name(user_id):
    user = get_user(user_id)

    if not user:
        return "不明"

    return user.get("name", "不明")


def reply_text(event, message, quick_reply=None):
    """LINEへ返信"""

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(
            text=str(message),
            quick_reply=quick_reply
        )
    )


def push_user_text(user_id, message):
    """指定ユーザーへプッシュ通知"""

    try:
        line_bot_api.push_message(
            user_id,
            TextSendMessage(text=str(message))
        )
        return True

    except Exception:
        logger.exception(
            "ユーザーへの通知に失敗しました: %s",
            user_id
        )
        return False


def push_room_text(room_id, message):
    """ルーム参加者全員に通知"""

    members = get_room_members(room_id)

    success_count = 0

    for member in members:
        user_id = member.get("user_id")

        if not user_id:
            continue

        if push_user_text(user_id, message):
            success_count += 1

    return success_count


def get_name_list(room_id):
    """ルーム参加者の名前一覧"""

    members = get_room_members(room_id)

    return [
        member.get("name", "不明")
        for member in members
    ]


def get_member_by_name(room_id, name):
    """現在のルーム内から名前でユーザーを検索"""

    members = get_room_members(room_id)

    for member in members:
        if member.get("name") == name:
            return member

    return None


def parse_datetime(value):
    """Supabaseの日時文字列をdatetimeに変換"""

    if not value:
        return None

    try:
        return datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )
    except (ValueError, TypeError):
        return None


def elapsed_seconds(start_time):
    """開始時刻からの経過秒数"""

    start = parse_datetime(start_time)

    if not start:
        return 0

    now = (
        datetime.now(start.tzinfo)
        if start.tzinfo
        else datetime.now()
    )

    return max(
        0,
        int((now - start).total_seconds())
    )


def format_duration(seconds):
    """秒数を時間・分・秒に変換"""

    seconds = max(0, int(seconds))

    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    remaining_seconds = seconds % 60

    if hours:
        return (
            f"{hours}時間"
            f"{minutes}分"
            f"{remaining_seconds}秒"
        )

    if minutes:
        return (
            f"{minutes}分"
            f"{remaining_seconds}秒"
        )

    return f"{remaining_seconds}秒"


def get_current_stats(user_id):
    """現在のルーム内ポイント情報"""

    room_id = get_current_room_id(user_id)

    if not room_id:
        return get_user(user_id)

    return get_room_user_stats(
        room_id,
        user_id
    )


def add_points_for_user(user_id, amount):
    """試合中・試合外を判定してポイントを加算"""

    room_id = get_current_room_id(user_id)

    if not room_id:
        return False

    amount = int(amount)

    if amount <= 0:
        return False

    match = get_active_match(room_id)

    if match:
        return add_match_points(
            room_id,
            user_id,
            amount
        )

    return add_room_points(
        room_id,
        user_id,
        amount
    )


def consume_points_for_user(user_id, amount):
    """試合中・試合外を判定してポイントを消費"""

    room_id = get_current_room_id(user_id)

    if not room_id:
        return False

    match = get_active_match(room_id)

    if match:
        return consume_match_points(
            room_id,
            user_id,
            amount
        )

    return consume_room_points(
        room_id,
        user_id,
        amount
    )


# ========================================
# クイックリプライ
# ========================================

def get_quick_reply():

    commands = [
        ("＊", "アナル"),
    ]

    return QuickReply(
        items=[
            QuickReplyButton(
                action=MessageAction(
                    label=label,
                    text=command
                )
            )
            for label, command in commands
        ]
    )


def get_admin_quick_reply():

    return QuickReply(
        items=[
            QuickReplyButton(
                action=MessageAction(
                    label="👹 鬼設定",
                    text="鬼設定"
                )
            ),
            QuickReplyButton(
                action=MessageAction(
                    label="♻ リセット",
                    text="リセット"
                )
            ),
            QuickReplyButton(
                action=MessageAction(
                    label="➕ 全員+20",
                    text="全員+20"
                )
            )
        ]
    )


def get_room_quick_reply():

    commands = [
        ("ルーム作成", "ルーム作成"),
        ("参加", "参加"),
        ("ルーム情報", "ルーム情報"),
        ("退出", "退出"),
    ]

    return QuickReply(
        items=[
            QuickReplyButton(
                action=MessageAction(
                    label=label,
                    text=command
                )
            )
            for label, command in commands
        ]
    )


# ========================================
# ルーム表示
# ========================================

def make_room_info(room_id):

    room = get_room(room_id)

    if not room:
        return "ルームが見つかりません"

    members = get_room_members(room_id)

    owner_id = room.get("owner_user_id")
    owner_name = get_user_name(owner_id)

    message = (
        "🏠 ルーム情報\n\n"
        f"ルームID: {room_id}\n"
        f"管理者: {owner_name}\n"
        f"参加人数: {len(members)}人\n\n"
        "【参加者】\n"
    )

    for index, member in enumerate(
        members,
        start=1
    ):
        message += (
            f"{index}. "
            f"{member.get('name', '不明')}\n"
        )

    match = get_active_match(room_id)

    if match:
        message += "\n⚔️ 試合中"
    else:
        message += "\n⏸ 試合待機中"

    return message


# ========================================
# 試合結果メッセージ
# ========================================

def make_match_result_message(result):

    if not result:
        return "試合結果を取得できませんでした"

    match = result.get("match", {})
    players = result.get("players", [])

    duration = format_duration(
        result.get("duration_seconds", 0)
    )

    message = (
        "🏁 試合終了！\n\n"
        f"試合時間: {duration}\n\n"
        "━━━━━━━━━━━━\n"
        "🏆 試合ランキング\n"
        "━━━━━━━━━━━━\n\n"
    )

    for player in players:

        rank = player.get("rank", "-")
        name = player.get("name", "不明")
        points = int(
            player.get("match_points", 0)
        )
        spent = int(
            player.get("spent_points", 0)
        )
        item_count = int(
            player.get("item_count", 0)
        )

        message += (
            f"{rank}位 {name}\n"
            f"獲得ポイント: {points}pt\n"
            f"消費ポイント: {spent}pt\n"
            f"アイテム使用: {item_count}回\n\n"
        )

    mvp = result.get("mvp")

    message += "━━━━━━━━━━━━\n"

    if mvp:
        message += (
            "🌟 MVP\n"
            f"{mvp.get('name', '不明')} "
            f"（{mvp.get('match_points', 0)}pt）\n\n"
        )

    most_item_user = result.get("most_item_user")
    most_item_count = result.get("most_item_count", 0)

    if most_item_user:
        message += (
            "🎁 最多アイテム使用\n"
            f"{most_item_user} "
            f"（{most_item_count}回）\n\n"
        )

    message += (
        "再試合する場合は「再試合」\n"
        "ルームを終了する場合は「解散」"
    )

    return message


# ========================================
# FastAPI
# ========================================

@app.api_route("/", methods=["GET", "HEAD"])
async def root():
    return {"status": "ok"}


@app.post("/callback")
async def callback(request: Request):

    body = await request.body()

    signature = request.headers.get(
        "X-Line-Signature"
    )

    if not signature:
        return {"error": "missing signature"}

    try:
        handler.handle(
            body.decode("utf-8"),
            signature
        )

    except InvalidSignatureError:
        return {"error": "invalid signature"}

    except Exception:
        logger.exception("LINE webhook処理エラー")

    return "OK"
