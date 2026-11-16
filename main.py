
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


# ========================================
# LINEメッセージ処理
# ========================================

@handler.add(
    MessageEvent,
    message=TextMessage
)
def handle_message(event):

    try:

        user_id = getattr(
            event.source,
            "user_id",
            None
        )

        if not user_id:
            return

        text = event.message.text.strip()

        # --------------------------------
        # 初回ユーザー登録
        # --------------------------------

        user = get_user(user_id)

        if not user:

            profile = line_bot_api.get_profile(
                user_id
            )

            create_user(
                user_id,
                profile.display_name
            )

            user = get_user(user_id)

            # 新規登録者は初期ルームに参加
            if get_room(DEFAULT_ROOM_ID):
                join_room(
                    user_id,
                    DEFAULT_ROOM_ID
                )

        if not user:
            reply_text(
                event,
                "ユーザー登録に失敗しました"
            )
            return

        room_id = get_current_room_id(user_id)

        # ========================================
        # ルーム作成
        # ========================================

        if text == "ルーム作成":

            room = create_room(user_id)

            if not room:
                reply_text(
                    event,
                    "❌ ルームを作成できませんでした。\n"
                    "すでに同じIDのルームが存在する可能性があります。"
                )
                return

            new_room_id = room["room_id"]

            reply_text(
                event,
                (
                    "🏠 ルームを作成しました！\n\n"
                    f"ルームID: {new_room_id}\n"
                    f"管理者: {user['name']}\n\n"
                    "このルームの管理者として試合を開始できます。\n"
                    "友達にはルームIDを伝えてください。"
                ),
                get_room_quick_reply()
            )
            return

        # ========================================
        # ルーム参加開始
        # ========================================

        if text == "参加":

            room_join_waiting[user_id] = True

            reply_text(
                event,
                (
                    "参加したいルームのIDを入力してください。\n\n"
                    "数字だけ送信してください。"
                )
            )
            return

        # ========================================
        # ルームID入力
        # ========================================

        if user_id in room_join_waiting:

            if not text.isdigit():

                reply_text(
                    event,
                    "❌ ルームIDは数字で入力してください。"
                )
                return

            target_room_id = int(text)

            success = join_room(
                user_id,
                target_room_id
            )

            del room_join_waiting[user_id]

            if success:

                reply_text(
                    event,
                    (
                        "✅ ルームに参加しました！\n\n"
                        f"ルームID: {target_room_id}\n"
                        f"参加者: {user['name']}"
                    ),
                    get_room_quick_reply()
                )

                push_room_text(
                    target_room_id,
                    f"👋 {user['name']} がルームに参加しました。"
                )

            else:

                reply_text(
                    event,
                    (
                        "❌ ルームに参加できませんでした。\n\n"
                        "確認事項:\n"
                        "・ルームIDが正しいか\n"
                        "・ルームが存在しているか\n"
                        "・試合中ではないか\n"
                        "・別のルームに参加中ではないか"
                    )
                )

            return

        # ========================================
        # ルーム情報
        # ========================================

        if text == "ルーム情報":

            room_id = get_current_room_id(user_id)

            if not room_id:

                reply_text(
                    event,
                    "現在参加しているルームがありません。",
                    get_room_quick_reply()
                )
                return

            reply_text(
                event,
                make_room_info(room_id),
                get_room_quick_reply()
            )
            return

        # ========================================
        # ルーム退出
        # ========================================

        if text == "退出":

            room_id = get_current_room_id(user_id)

            if not room_id:

                reply_text(
                    event,
                    "現在ルームに参加していません。"
                )
                return

            if is_room_owner(user_id, room_id):

                reply_text(
                    event,
                    (
                        "❌ ルーム管理者はそのまま退出できません。\n"
                        "管理者としてルームを解散してください。"
                    )
                )
                return

            success = leave_room(user_id)

            if success:

                reply_text(
                    event,
                    "ルームから退出しました。"
                )

                push_room_text(
                    room_id,
                    f"👋 {user['name']} がルームから退出しました。"
                )

            else:

                reply_text(
                    event,
                    "❌ 退出できませんでした。試合中は退出できません。"
                )

            return

        # ========================================
        # 試合開始
        # ========================================

        if text in ["開始", "試合開始"]:

            room_id = get_current_room_id(user_id)

            if not room_id:

                reply_text(
                    event,
                    "ルームに参加していません。"
                )
                return

            if not is_room_owner(user_id, room_id):

                reply_text(
                    event,
                    "❌ 試合を開始できるのはルーム管理者だけです。"
                )
                return

            match = start_match(room_id)

            if not match:

                reply_text(
                    event,
                    (
                        "❌ 試合を開始できませんでした。\n\n"
                        "・参加者が2人以上いるか\n"
                        "・すでに試合中ではないか\n"
                        "・ルームが有効か"
                    )
                )
                return

            push_room_text(
                room_id,
                (
                    "⚔️ 試合開始！\n\n"
                    f"ルームID: {room_id}\n"
                    f"参加人数: {len(get_room_members(room_id))}人\n\n"
                    "試合中に獲得したポイントが今回のランキングに反映されます。\n"
                    "管理者が「試合終了」と送信すると結果が発表されます。"
                )
            )
            return

        # ========================================
        # 試合終了
        # ========================================

        if text == "試合終了":

            room_id = get_current_room_id(user_id)

            if not room_id:

                reply_text(
                    event,
                    "ルームに参加していません。"
                )
                return

            if not is_room_owner(user_id, room_id):

                reply_text(
                    event,
                    "❌ 試合を終了できるのはルーム管理者だけです。"
                )
                return

            if not get_active_match(room_id):

                reply_text(
                    event,
                    "現在進行中の試合はありません。"
                )
                return

            result = finish_match(room_id)

            if not result:

                reply_text(
                    event,
                    "❌ 試合終了処理に失敗しました。"
                )
                return

            result_message = make_match_result_message(
                result
            )

            # 全プレイヤーへ結果を送信
            push_room_text(
                room_id,
                result_message
            )

            reply_text(
                event,
                "🏁 試合を終了し、参加者全員にリザルトを送信しました。"
            )
            return

        # ========================================
        # 再試合
        # ========================================

        if text == "再試合":

            room_id = get_current_room_id(user_id)

            if not room_id:

                reply_text(
                    event,
                    "ルームに参加していません。"
                )
                return

            if not is_room_owner(user_id, room_id):

                reply_text(
                    event,
                    "❌ 再試合を開始できるのはルーム管理者だけです。"
                )
                return

            if get_active_match(room_id):

                reply_text(
                    event,
                    "現在試合中です。"
                )
                return

            if not reset_room_for_rematch(room_id):

                reply_text(
                    event,
                    "❌ 再試合の準備に失敗しました。"
                )
                return

            match = start_match(room_id)

            if not match:

                reply_text(
                    event,
                    "❌ 再試合を開始できませんでした。"
                )
                return

            push_room_text(
                room_id,
                "🔁 再試合を開始しました！"
            )
            return

        # ========================================
        # ルーム解散
        # ========================================

        if text == "解散":

            room_id = get_current_room_id(user_id)

            if not room_id:

                reply_text(
                    event,
                    "ルームに参加していません。"
                )
                return

            if not is_room_owner(user_id, room_id):

                reply_text(
                    event,
                    "❌ ルームを解散できるのは管理者だけです。"
                )
                return

            if get_active_match(room_id):

                reply_text(
                    event,
                    "❌ 試合中は解散できません。先に試合を終了してください。"
                )
                return

            members = get_room_members(room_id)

            message = (
                "🏠 ルームが解散されました。\n"
                "これまでの参加ありがとうございました。"
            )

            # 削除前に全員へ通知
            for member in members:
                push_user_text(
                    member["user_id"],
                    message
                )

            success = delete_room(room_id)

            if success:

                reply_text(
                    event,
                    "✅ ルームを解散しました。"
                )

            else:

                reply_text(
                    event,
                    "❌ ルームの解散に失敗しました。"
                )

            return

        # ========================================
        # 鬼引渡しカード入力待ち
        # ========================================

        if (
            user_id in item_action_waiting
            and item_action_waiting[user_id].get("type")
            == "oni_transfer"
        ):

            room_id = get_current_room_id(user_id)

            target_user = get_member_by_name(
                room_id,
                text
            )

            if not target_user:

                reply_text(
                    event,
                    "❌ その名前の参加者は現在のルームにいません。"
                )
                return

            cards = get_all_room_oni_cards(room_id)

            active_card = None

            for card in cards:

                if card.get("current_name"):

                    active_card = card
                    break

            if not active_card:

                reply_text(
                    event,
                    "❌ 現在鬼が登録されていません。"
                )
                del item_action_waiting[user_id]
                return

            seconds = elapsed_seconds(
                active_card.get("start_time")
            )

            add_room_oni_history(
                room_id,
                active_card["card_no"],
                active_card["current_name"],
                seconds
            )

            update_room_oni_card(
                room_id,
                active_card["card_no"],
                target_user["user_id"],
                target_user["name"]
            )

            del item_action_waiting[user_id]

            reply_text(
                event,
                (
                    f"✅ 鬼を {target_user['name']} に引き渡しました。\n"
                    f"前の鬼の担当時間: {format_duration(seconds)}"
                )
            )
            return

        # ========================================
        # 鬼設定入力待ち
        # ========================================

        if user_id in oni_setup_waiting:

            room_id = get_current_room_id(user_id)

            if not is_room_owner(user_id, room_id):

                del oni_setup_waiting[user_id]

                reply_text(
                    event,
                    "❌ ルーム管理者だけが鬼設定を変更できます。"
                )
                return

            lines = text.split("\n")
            success_count = 0

            for line in lines:

                parts = line.strip().split()

                if len(parts) != 2:
                    continue

                card_text, target_name = parts

                if not card_text.isdigit():
                    continue

                card_no = int(card_text)

                if card_no not in [1, 2, 3, 4, 5]:
                    continue

                target_user = get_member_by_name(
                    room_id,
                    target_name
                )

                if not target_user:
                    continue

                card = get_room_oni_card(
                    room_id,
                    card_no
                )

                if not card:
                    continue

                if (
                    card.get("current_name")
                    and card.get("start_time")
                ):

                    seconds = elapsed_seconds(
                        card["start_time"]
                    )

                    add_room_oni_history(
                        room_id,
                        card_no,
                        card["current_name"],
                        seconds
                    )

                update_room_oni_card(
                    room_id,
                    card_no,
                    target_user["user_id"],
                    target_user["name"]
                )

                success_count += 1

            del oni_setup_waiting[user_id]

            reply_text(
                event,
                f"✅ {success_count}件の鬼設定を反映しました。"
            )
            return

        # ========================================
        # 譲渡先入力待ち
        # ========================================

        if (
            user_id in transfer_waiting
            and transfer_waiting[user_id]["step"]
            == "select_user"
        ):

            target_user = get_member_by_name(
                room_id,
                text
            )

            if not target_user:

                reply_text(
                    event,
                    "❌ その名前の参加者は現在のルームにいません。"
                )
                return

            transfer_waiting[user_id] = {
                "step": "input_amount",
                "target": target_user["name"]
            }

            reply_text(
                event,
                (
                    f"{target_user['name']}へ"
                    "何ポイント譲渡しますか？\n\n"
                    "数字だけ入力してください。"
                )
            )
            return

        # ========================================
        # 譲渡金額入力待ち
        # ========================================

        if (
            user_id in transfer_waiting
            and transfer_waiting[user_id]["step"]
            == "input_amount"
        ):

            if not text.isdigit():

                reply_text(
                    event,
                    "数字だけ入力してください。"
                )
                return

            amount = int(text)

            if amount <= 0:

                reply_text(
                    event,
                    "1以上の数字を入力してください。"
                )
                return

            target = transfer_waiting[user_id]["target"]

            success, result = transfer_points(
                user_id,
                target,
                amount
            )

            del transfer_waiting[user_id]

            if success:

                reply_text(
                    event,
                    f"✅ {target} に {amount}pt譲渡しました。"
                )

            else:

                reply_text(
                    event,
                    f"❌ 譲渡に失敗しました: {result}"
                )

            return

        # ========================================
        # ケツポ
        # ========================================

        if text == "ケツポ":

            point_waiting[user_id] = True

            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(
                    text="ポイント種別を選んでください。",
                    quick_reply=QuickReply(
                        items=[
                            QuickReplyButton(
                                action=MessageAction(
                                    label="🍑 ケツ",
                                    text="ケツ"
                                )
                            ),
                            QuickReplyButton(
                                action=MessageAction(
                                    label="🌭 珍棒",
                                    text="珍棒"
                                )
                            ),
                            QuickReplyButton(
                                action=MessageAction(
                                    label="🩲 ノーパン",
                                    text="ノーパン"
                                )
                            )
                        ]
                    )
                )
            )
            return

        # ========================================
        # 回数入力が必要なもの
        # ========================================

        if (
            user_id in point_waiting
            and text in ["ケツ", "珍棒"]
        ):

            count_waiting[user_id] = {
                "type": text
            }

            del point_waiting[user_id]

            reply_text(
                event,
                (
                    f"{text}は何回でしたか？\n\n"
                    "数字だけ入力してください。"
                )
            )
            return

        # ========================================
        # 回数入力後
        # ========================================

        if (
            user_id in count_waiting
            and text.isdigit()
        ):

            count = int(text)

            if count <= 0:

                reply_text(
                    event,
                    "1以上の数字を入力してください。"
                )
                return

            point_type = count_waiting[user_id]["type"]

            if point_type == "ケツ":
                amount = count
            else:
                amount = count * 3

            success = add_points_for_user(
                user_id,
                amount
            )

            if not success:

                reply_text(
                    event,
                    "❌ ポイントを加算できませんでした。"
                )
                return

            del count_waiting[user_id]

            stats = get_current_stats(user_id)

            current = int(
                stats.get("current_points", 0)
            )

            total = int(
                stats.get("total_points", 0)
            )

            reply_text(
                event,
                (
                    f"ポイント獲得: {point_type}\n\n"
                    f"回数: {count}回\n"
                    f"獲得: {amount}pt\n\n"
                    f"所持ポイント: {current}pt\n"
                    f"累計ポイント: {total}pt"
                )
            )
            return

        # ========================================
        # ノーパン
        # ========================================

        if (
            user_id in point_waiting
            and text == "ノーパン"
        ):

            amount = 20

            success = add_points_for_user(
                user_id,
                amount
            )

            if not success:

                reply_text(
                    event,
                    "❌ ポイントを加算できませんでした。"
                )
                return

            del point_waiting[user_id]

            stats = get_current_stats(user_id)

            reply_text(
                event,
                (
                    f"ノーパン +{amount}pt\n\n"
                    f"所持ポイント: {stats['current_points']}pt\n"
                    f"累計ポイント: {stats['total_points']}pt"
                )
            )
            return

        # ========================================
        # おに
        # ========================================

        if text == "おに":

            oni_card_waiting[user_id] = True

            reply_text(
                event,
                (
                    "鬼カード番号を入力してください。\n\n"
                    "1\n2\n3\n4\n5"
                )
            )
            return

        # ========================================
        # 鬼カード修正
        # ========================================

        if (
            user_id in oni_confirm_waiting
            and text == "修正"
        ):

            del oni_confirm_waiting[user_id]

            oni_card_waiting[user_id] = True

            reply_text(
                event,
                (
                    "👹 鬼カード番号を入力してください。\n\n"
                    "1\n2\n3\n4\n5"
                )
            )
            return

        # ========================================
        # 鬼カード番号入力
        # ========================================

        if (
            user_id in oni_card_waiting
            and text in ["1", "2", "3", "4", "5"]
        ):

            oni_confirm_waiting[user_id] = int(text)

            del oni_card_waiting[user_id]

            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(
                    text=f"カード{text}で登録しますか？",
                    quick_reply=QuickReply(
                        items=[
                            QuickReplyButton(
                                action=MessageAction(
                                    label="✅ 決定",
                                    text="決定"
                                )
                            ),
                            QuickReplyButton(
                                action=MessageAction(
                                    label="🔄 修正",
                                    text="修正"
                                )
                            )
                        ]
                    )
                )
            )
            return

        # ========================================
        # 鬼カード決定
        # ========================================

        if (
            user_id in oni_confirm_waiting
            and text == "決定"
        ):

            room_id = get_current_room_id(user_id)
            card_no = oni_confirm_waiting[user_id]

            card = get_room_oni_card(
                room_id,
                card_no
            )

            if not card:

                reply_text(
                    event,
                    "❌ その鬼カードは存在しません。"
                )

                del oni_confirm_waiting[user_id]
                return

            if (
                card.get("current_name")
                and card.get("start_time")
            ):

                seconds = elapsed_seconds(
                    card["start_time"]
                )

                add_room_oni_history(
                    room_id,
                    card_no,
                    card["current_name"],
                    seconds
                )

            update_room_oni_card(
                room_id,
                card_no,
                user_id,
                user["name"]
            )

            add_oni_count(user_id)

            del oni_confirm_waiting[user_id]

            reply_text(
                event,
                (
                    f"👹 カード{card_no}で鬼登録しました。\n\n"
                    "タイマー開始！"
                )
            )
            return

        # ========================================
        # 譲渡
        # ========================================

        if text == "譲渡":

            names = get_name_list(room_id)

            transfer_waiting[user_id] = {
                "step": "select_user"
            }

            users_text = "\n".join(names)

            reply_text(
                event,
                (
                    "🎁 譲渡モード\n\n"
                    "譲渡したい相手の名前を送信してください。\n\n"
                    "【現在のルーム参加者】\n"
                    f"{users_text}"
                )
            )
            return

        # ========================================
        # アナル（管理者コンソール）
        # ========================================

        if text == "アナル":

            if not is_admin(user_id):

                reply_text(
                    event,
                    "松下穂高"
                )
                return

            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(
                    text=(
                        "🛠 管理者コンソール\n\n"
                        "利用可能コマンド\n\n"
                        "・鬼設定\n"
                        "・リセット\n"
                        "・全員+20"
                    ),
                    quick_reply=get_admin_quick_reply()
                )
            )
            return

        # ========================================
        # ポイント
        # ========================================

        if text == "ポイント":

            stats = get_current_stats(user_id)

            if not stats:

                reply_text(
                    event,
                    "ポイント情報を取得できませんでした。"
                )
                return

            reply_text(
                event,
                (
                    "📊 ポイント情報\n\n"
                    f"名前: {user['name']}\n"
                    f"所持ポイント: {stats['current_points']}pt\n"
                    f"累計ポイント: {stats['total_points']}pt\n"
                    f"消費回数: {stats['used_count']}回\n"
                    f"おに回数: {stats['oni_count']}回"
                )
            )
            return

        # ========================================
        # 消費
        # ========================================

        if text == "消費":

            amount = 50

            success = consume_points_for_user(
                user_id,
                amount
            )

            stats = get_current_stats(user_id)

            current = (
                int(stats.get("current_points", 0))
                if stats else 0
            )

            if success:

                reply_text(
                    event,
                    (
                        "✅ 50ポイント消費しました。\n\n"
                        f"残り: {current}pt"
                    )
                )

            else:

                reply_text(
                    event,
                    (
                        "❌ ポイントが不足しています。\n\n"
                        "必要: 50pt\n"
                        f"現在: {current}pt"
                    )
                )

            return

        # ========================================
        # ランキング
        # ========================================

        if text == "ランキング":

            room_id = get_current_room_id(user_id)

            ranking = get_room_ranking(room_id)

            current_message = (
                "💰 現在ポイントランキング\n\n"
            )

            for index, row in enumerate(
                ranking,
                start=1
            ):

                current_message += (
                    f"{index}位 "
                    f"{row['name']} "
                    f"{row['current_points']}pt\n"
                )

            total_rows = []

            for member in get_room_members(room_id):

                stats = get_room_user_stats(
                    room_id,
                    member["user_id"]
                )

                if stats:
                    total_rows.append({
                        "name": member["name"],
                        "total_points": int(
                            stats.get("total_points", 0)
                        )
                    })

            total_rows.sort(
                key=lambda row: row["total_points"],
                reverse=True
            )

            total_message = (
                "\n🏆 累計ポイントランキング\n\n"
            )

            for index, row in enumerate(
                total_rows,
                start=1
            ):

                total_message += (
                    f"{index}位 "
                    f"{row['name']} "
                    f"{row['total_points']}pt\n"
                )

            line_bot_api.reply_message(
                event.reply_token,
                [
                    TextSendMessage(
                        text=current_message
                    ),
                    TextSendMessage(
                        text=total_message,
                        quick_reply=get_quick_reply()
                    )
                ]
            )
            return

        # ========================================
        # 鬼ランキング
        # ========================================

        if text == "鬼ランキング":

            room_id = get_current_room_id(user_id)

            ranking = get_room_oni_ranking(room_id)

            message = "👹 鬼ランキング\n\n"

            for index, row in enumerate(
                ranking,
                start=1
            ):

                name = row["name"]
                seconds = int(row["seconds"])

                message += (
                    f"{index}位 {name}\n"
                    f"{format_duration(seconds)}\n\n"
                )

            if not ranking:
                message += "まだ記録がありません。"

            reply_text(
                event,
                message
            )
            return

        # ========================================
        # 鬼設定
        # ========================================

        if text == "鬼設定":

            room_id = get_current_room_id(user_id)

            if not is_room_owner(user_id, room_id):

                reply_text(
                    event,
                    "❌ 鬼設定を変更できるのはルーム管理者だけです。"
                )
                return

            oni_setup_waiting[user_id] = True

            reply_text(
                event,
                (
                    "👹 鬼設定モード\n\n"
                    "カード番号と名前を入力してください。\n\n"
                    "例:\n"
                    "1 山田\n"
                    "3 佐藤\n"
                    "5 央多"
                )
            )
            return

        # ========================================
        # 全員+20
        # ========================================

        if text == "全員+20":

            if not is_admin(user_id):

                reply_text(
                    event,
                    "❌ 管理者専用コマンドです。"
                )
                return

            room_id = get_current_room_id(user_id)

            members = get_room_members(room_id)

            success_count = 0

            for member in members:

                if add_points_for_user(
                    member["user_id"],
                    20
                ):
                    success_count += 1

            reply_text(
                event,
                (
                    f"✅ {success_count}人に20pt付与しました。"
                )
            )
            return

        # ========================================
        # リセット
        # ========================================

        if text == "リセット":

            if not is_admin(user_id):

                reply_text(
                    event,
                    "❌ 管理者専用コマンドです。"
                )
                return

            try:

                reset_all_data()

                transfer_waiting.clear()
                point_waiting.clear()
                count_waiting.clear()
                oni_card_waiting.clear()
                item_waiting.clear()
                item_action_waiting.clear()
                oni_setup_waiting.clear()
                oni_confirm_waiting.clear()
                room_join_waiting.clear()

                reply_text(
                    event,
                    (
                        "🔄 全データをリセットしました。\n\n"
                        "・全ユーザーのポイント\n"
                        "・ポイント使用回数\n"
                        "・鬼になった回数\n"
                        "・鬼カードの登録情報\n"
                        "・鬼の履歴・ランキング\n"
                        "・全ユーザーの所持アイテム\n\n"
                        "ユーザー登録とショップの商品一覧は維持されます。"
                    )
                )

            except Exception:

                logger.exception("リセット処理に失敗しました")

                reply_text(
                    event,
                    "❌ リセットに失敗しました。Renderのログを確認してください。"
                )

            return


        # ========================================
        # アイテムメニュー
        # ========================================

        if text == "アイテム":

            item_waiting[user_id] = {
                "step": "menu"
            }

            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(
                    text=(
                        "🎁 アイテムメニュー\n\n"
                        "購入 または 使用 を選択してください。"
                    ),
                    quick_reply=QuickReply(
                        items=[
                            QuickReplyButton(
                                action=MessageAction(
                                    label="🛒 購入",
                                    text="購入"
                                )
                            ),
                            QuickReplyButton(
                                action=MessageAction(
                                    label="🎁 使用",
                                    text="使用"
                                )
                            )
                        ]
                    )
                )
            )
            return

        # ========================================
        # アイテム購入メニュー
        # ========================================

        if (
            user_id in item_waiting
            and item_waiting[user_id].get("step") == "menu"
            and text == "購入"
        ):

            room_id = get_current_room_id(user_id)

            items = get_room_items(room_id)

            if not items:

                del item_waiting[user_id]

                reply_text(
                    event,
                    "現在、販売中のアイテムはありません。"
                )
                return

            message = "🛒 アイテムショップ\n\n"

            for item in items:

                message += (
                    f"{item['item_id']} "
                    f"{item['item_name']} "
                    f"{item['price']}pt\n"
                )

                description = item.get("description")

                if description:
                    message += f"  {description}\n"

            message += (
                "\n購入したいアイテムの番号を入力してください。"
            )

            item_waiting[user_id] = {
                "step": "buy"
            }

            reply_text(
                event,
                message
            )
            return

        # ========================================
        # アイテム使用メニュー
        # ========================================

        if (
            user_id in item_waiting
            and item_waiting[user_id].get("step") == "menu"
            and text == "使用"
        ):

            room_id = get_current_room_id(user_id)

            owned_items = get_room_user_items(
                room_id,
                user_id
            )

            available_items = []

            message = "🎁 所持アイテム\n\n"

            for item in owned_items:

                quantity = int(
                    item.get("quantity", 0)
                )

                if quantity <= 0:
                    continue

                item_id = int(item["item_id"])

                available_items.append(item_id)

                message += (
                    f"{item_id} "
                    f"{item['item_name']} "
                    f"×{quantity}\n"
                )

            if not available_items:

                del item_waiting[user_id]

                reply_text(
                    event,
                    "使用できるアイテムを持っていません。"
                )
                return

            message += (
                "\n使用するアイテムの番号を入力してください。"
            )

            item_waiting[user_id] = {
                "step": "use",
                "available_items": available_items
            }

            reply_text(
                event,
                message
            )
            return

        # ========================================
        # アイテム購入処理
        # ========================================

        if (
            user_id in item_waiting
            and item_waiting[user_id].get("step") == "buy"
            and text.isdigit()
        ):

            room_id = get_current_room_id(user_id)
            item_id = int(text)

            item = get_room_item(
                room_id,
                item_id
            )

            if not item:

                reply_text(
                    event,
                    "❌ そのアイテムは存在しません。"
                )

                del item_waiting[user_id]
                return

            if not get_active_match(room_id):

                reply_text(
                    event,
                    (
                        "❌ アイテムを購入できません。\n\n"
                        "アイテム購入は試合中に行えます。"
                    )
                )

                del item_waiting[user_id]
                return

            success = buy_room_item(
                room_id,
                user_id,
                item_id
            )

            del item_waiting[user_id]

            if success:

                stats = get_current_stats(user_id)

                current = (
                    int(stats.get("current_points", 0))
                    if stats else 0
                )

                reply_text(
                    event,
                    (
                        f"✅ {item['item_name']}を購入しました！\n\n"
                        f"残りポイント: {current}pt"
                    )
                )

            else:

                reply_text(
                    event,
                    (
                        "❌ 購入に失敗しました。\n\n"
                        "ポイント不足、試合状態、"
                        "所持データを確認してください。"
                    )
                )

            return

        # ========================================
        # アイテム使用処理
        # ========================================

        if (
            user_id in item_waiting
            and item_waiting[user_id].get("step") == "use"
            and text.isdigit()
        ):

            room_id = get_current_room_id(user_id)
            item_id = int(text)

            available_items = item_waiting[user_id].get(
                "available_items",
                []
            )

            if item_id not in available_items:

                reply_text(
                    event,
                    "❌ 所持アイテムの番号を入力してください。"
                )
                return

            item = get_room_item(
                room_id,
                item_id
            )

            if not item:

                del item_waiting[user_id]

                reply_text(
                    event,
                    "❌ アイテムが見つかりません。"
                )
                return

            item_name = item["item_name"]

            success = use_room_item(
                room_id,
                user_id,
                item_id
            )

            del item_waiting[user_id]

            if not success:

                reply_text(
                    event,
                    (
                        "❌ アイテムを使用できませんでした。\n\n"
                        "試合中か、所持数が残っているか確認してください。"
                    )
                )
                return

            # --------------------------------
            # 鬼チェッカー
            # --------------------------------

            if item_name == "鬼チェッカー":

                cards = get_all_room_oni_cards(room_id)

                message = (
                    "👹 現在の鬼\n\n"
                )

                for card in cards:

                    name = (
                        card.get("current_name")
                        or "なし"
                    )

                    message += (
                        f"カード{card['card_no']} : "
                        f"{name}\n"
                    )

                reply_text(
                    event,
                    message
                )
                return

            # --------------------------------
            # 鬼引渡しカード
            # --------------------------------

            if item_name == "鬼引渡しカード":

                item_action_waiting[user_id] = {
                    "type": "oni_transfer"
                }

                reply_text(
                    event,
                    (
                        "👹 鬼を引き渡す相手の名前を入力してください。\n\n"
                        "現在のルーム参加者から選択してください。"
                    )
                )
                return

            # --------------------------------
            # その他のアイテム
            # --------------------------------

            reply_text(
                event,
                f"✅ {item_name}を使用しました。"
            )
            return

        # ========================================
        # その他
        # ========================================

        reply_text(
            event,
            (
                "ケツ叩きカウンター\n\n"
                "下のボタンからコマンドを選んでください。"
            ),
            get_quick_reply()
        )

    except Exception:

        logger.exception(
            "handle_messageでエラーが発生しました"
        )

        try:
            reply_text(
                event,
                (
                    "❌ エラーが発生しました。\n"
                    "時間をおいて再度試してください。"
                )
            )
        except Exception:
            logger.exception(
                "エラー通知にも失敗しました"
            )
