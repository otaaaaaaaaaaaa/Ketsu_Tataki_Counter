import os
import uuid
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

    # ルーム・試合管理用
    create_room,
    get_room,
    get_room_by_id,
    join_room,
    leave_room,
    get_room_members,
    start_match,
    finish_match,
    get_match_result,
    get_active_match,
    add_match_points,
    consume_match_points,
    get_room_ranking,
    get_room_user,
    add_match_item_usage,
    reset_room_for_rematch,
    delete_room
)

from point_service import (
    add_point,
    consume_point
)


# =====================================
# FastAPI・LINE設定
# =====================================

app = FastAPI()

CHANNEL_ACCESS_TOKEN = os.getenv("CHANNEL_ACCESS_TOKEN")
CHANNEL_SECRET = os.getenv("CHANNEL_SECRET")
ADMIN_USER_ID = os.getenv("ADMIN_USER_ID")

line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)


# =====================================
# 入力待ち状態
# =====================================

transfer_waiting = {}
point_waiting = {}
count_waiting = {}
oni_card_waiting = {}
item_waiting = {}
item_action_waiting = {}
oni_setup_waiting = {}
oni_confirm_waiting = {}

room_create_waiting = {}
room_join_waiting = {}
room_point_waiting = {}


# =====================================
# 共通関数
# =====================================

def now_iso():
    return datetime.now().isoformat()


def get_user_name(user_id):
    user = get_user(user_id)

    if not user:
        return "不明"

    return user.get("name", "不明")


def reply_text(event, text, quick_reply=None):
    message = TextSendMessage(
        text=text,
        quick_reply=quick_reply
    )

    line_bot_api.reply_message(
        event.reply_token,
        message
    )


def push_text(user_id, text):
    line_bot_api.push_message(
        user_id,
        TextSendMessage(text=text)
    )


def send_room_message(room_id, text):
    members = get_room_members(room_id)

    for member in members:
        user_id = member.get("user_id")

        if user_id:
            try:
                push_text(user_id, text)
            except Exception as e:
                print(
                    "ルームメッセージ送信エラー:",
                    user_id,
                    repr(e)
                )


def is_room_admin(user_id, room):
    if not room:
        return False

    return room.get("admin_user_id") == user_id


def get_user_room(user_id):
    """
    ユーザーが現在参加しているルームを取得する。
    """
    from database import get_user_active_room

    return get_user_active_room(user_id)


def get_active_room_and_match(user_id):
    room = get_user_room(user_id)

    if not room:
        return None, None

    match = get_active_match(room["room_id"])

    return room, match


def make_room_id():
    """
    6桁のルームIDを生成する。
    実際の重複確認はdatabase.py側で行う。
    """
    return str(uuid.uuid4().int % 900000 + 100000)


# =====================================
# クイックリプライ
# =====================================

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

    commands = [
        ("👹 鬼設定", "鬼設定"),
        ("♻ リセット", "リセット"),
        ("➕ 全員+20", "全員+20"),
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


# =====================================
# トップページ
# =====================================

@app.api_route("/", methods=["GET", "HEAD"])
async def root():

    return {
        "status": "ok"
    }


# =====================================
# LINE Webhook
# =====================================

@app.post("/callback")
async def callback(request: Request):

    body = await request.body()

    signature = request.headers.get(
        "X-Line-Signature"
    )

    if not signature:
        return {
            "error": "missing signature"
        }

    try:
        handler.handle(
            body.decode("utf-8"),
            signature
        )

    except InvalidSignatureError:
        return {
            "error": "invalid signature"
        }

    except Exception as e:
        print(
            "callbackエラー:",
            repr(e)
        )

    return "OK"


# =====================================
# ルーム作成
# =====================================

def handle_room_create(event, user_id):

    room_create_waiting[user_id] = True

    reply_text(
        event,
        "ルームを作成します。\n\n"
        "ルーム名を入力してください。\n"
        "例：土曜日の対戦",
        get_room_quick_reply()
    )


def create_new_room(event, user_id, room_name):

    if not room_name.strip():
        reply_text(
            event,
            "ルーム名を入力してください。"
        )
        return

    room_id = make_room_id()

    try:
        room = create_room(
            room_id=room_id,
            room_name=room_name,
            admin_user_id=user_id
        )

        if not room:
            reply_text(
                event,
                "ルーム作成に失敗しました。"
            )
            return

        reply_text(
            event,
            "ルームを作成しました！\n\n"
            f"ルーム名：{room_name}\n"
            f"ルームID：{room_id}\n\n"
            "参加する人にルームIDを共有してください。\n"
            "参加者は「参加」と送信してから"
            "ルームIDを入力してください。",
            get_room_quick_reply()
        )

    except Exception as e:
        print(
            "ルーム作成エラー:",
            repr(e)
        )

        reply_text(
            event,
            "ルーム作成中にエラーが発生しました。"
        )


# =====================================
# ルーム参加
# =====================================

def handle_room_join(event, user_id):

    room_join_waiting[user_id] = True

    reply_text(
        event,
        "参加したいルームの6桁のIDを入力してください。"
    )


def join_existing_room(event, user_id, room_id):

    if not room_id.isdigit() or len(room_id) != 6:
        reply_text(
            event,
            "❌ ルームIDは6桁の数字で入力してください。"
        )
        return

    try:
        room = get_room_by_id(room_id)

        if not room:
            reply_text(
                event,
                "❌ そのルームは存在しません。"
            )
            return

        if room.get("status") == "closed":
            reply_text(
                event,
                "❌ このルームは解散しています。"
            )
            return

        success, result = join_room(
            room_id,
            user_id
        )

        if not success:
            reply_text(
                event,
                f"❌ 参加できませんでした。\n{result}"
            )
            return

        user_name = get_user_name(user_id)

        send_room_message(
            room_id,
            f"👤 {user_name} がルームに参加しました。"
        )

        reply_text(
            event,
            "✅ ルームに参加しました！\n\n"
            f"ルーム名：{room['room_name']}\n"
            f"ルームID：{room_id}",
            get_room_quick_reply()
        )

    except Exception as e:
        print(
            "ルーム参加エラー:",
            repr(e)
        )

        reply_text(
            event,
            "ルーム参加中にエラーが発生しました。"
        )


# =====================================
# ルーム情報
# =====================================

def show_room_info(event, user_id):

    room = get_user_room(user_id)

    if not room:
        reply_text(
            event,
            "現在ルームに参加していません。",
            get_room_quick_reply()
        )
        return

    members = get_room_members(
        room["room_id"]
    )

    admin_name = get_user_name(
        room["admin_user_id"]
    )

    status = room.get("status", "waiting")

    if status == "playing":
        status_text = "試合中"
    elif status == "closed":
        status_text = "解散済み"
    else:
        status_text = "待機中"

    msg = (
        "🏠 ルーム情報\n\n"
        f"ルーム名：{room['room_name']}\n"
        f"ルームID：{room['room_id']}\n"
        f"管理者：{admin_name}\n"
        f"状態：{status_text}\n\n"
        f"参加人数：{len(members)}人\n\n"
        "【参加者一覧】\n"
    )

    for i, member in enumerate(
        members,
        start=1
    ):
        name = get_user_name(
            member["user_id"]
        )

        if member["user_id"] == room["admin_user_id"]:
            name += " 👑"

        msg += f"{i}. {name}\n"

    reply_text(
        event,
        msg,
        get_room_quick_reply()
    )


# =====================================
# ルーム退出
# =====================================

def leave_current_room(event, user_id):

    room = get_user_room(user_id)

    if not room:
        reply_text(
            event,
            "現在ルームに参加していません。"
        )
        return

    if room.get("status") == "playing":
        reply_text(
            event,
            "❌ 試合中は退出できません。\n"
            "試合終了後に退出してください。"
        )
        return

    if is_room_admin(user_id, room):
        reply_text(
            event,
            "❌ ルーム管理者は通常の退出ができません。\n"
            "「ルーム解散」を実行してください。"
        )
        return

    success, result = leave_room(
        room["room_id"],
        user_id
    )

    if success:
        user_name = get_user_name(user_id)

        send_room_message(
            room["room_id"],
            f"👋 {user_name} がルームを退出しました。"
        )

        reply_text(
            event,
            "ルームを退出しました。"
        )

    else:
        reply_text(
            event,
            f"退出できませんでした。\n{result}"
        )


# =====================================
# 試合開始
# =====================================

def start_room_match(event, user_id):

    room = get_user_room(user_id)

    if not room:
        reply_text(
            event,
            "ルームに参加していません。"
        )
        return

    if not is_room_admin(user_id, room):
        reply_text(
            event,
            "❌ 試合を開始できるのはルーム管理者だけです。"
        )
        return

    members = get_room_members(
        room["room_id"]
    )

    if len(members) < 2:
        reply_text(
            event,
            "❌ 試合には2人以上必要です。"
        )
        return

    if room.get("status") == "playing":
        reply_text(
            event,
            "すでに試合中です。"
        )
        return

    try:
        success, result = start_match(
            room["room_id"]
        )

        if not success:
            reply_text(
                event,
                f"試合を開始できませんでした。\n{result}"
            )
            return

        send_room_message(
            room["room_id"],
            "🎮 試合開始！\n\n"
            f"ルーム：{room['room_name']}\n"
            f"参加人数：{len(members)}人\n\n"
            "ここからのポイント獲得・消費は"
            "この試合の記録に反映されます。\n\n"
            "試合を終了するときは、"
            "ルーム管理者が「試合終了」と送信してください。"
        )

    except Exception as e:
        print(
            "試合開始エラー:",
            repr(e)
        )

        reply_text(
            event,
            "試合開始中にエラーが発生しました。"
        )

# =====================================
# 試合終了・リザルト
# =====================================

def finish_room_match(event, user_id):

    room = get_user_room(user_id)

    if not room:
        reply_text(
            event,
            "ルームに参加していません。"
        )
        return

    if not is_room_admin(user_id, room):
        reply_text(
            event,
            "❌ 試合を終了できるのはルーム管理者だけです。"
        )
        return

    if room.get("status") != "playing":
        reply_text(
            event,
            "現在、試合は行われていません。"
        )
        return

    try:
        success, result = finish_match(
            room["room_id"]
        )

        if not success:
            reply_text(
                event,
                f"試合終了に失敗しました。\n{result}"
            )
            return

        result_data = get_match_result(
            room["room_id"]
        )

        if not result_data:
            reply_text(
                event,
                "試合は終了しましたが、"
                "リザルトを取得できませんでした。"
            )
            return

        send_match_result(
            room,
            result_data
        )

        reply_text(
            event,
            "✅ 試合を終了しました。\n\n"
            "参加者全員にリザルトを送信しました。\n\n"
            "次の操作を選んでください。\n"
            "・再戦\n"
            "・ルーム解散"
        )

    except Exception as e:
        print(
            "試合終了エラー:",
            repr(e)
        )

        reply_text(
            event,
            "試合終了処理中にエラーが発生しました。"
        )


def send_match_result(room, result_data):

    room_id = room["room_id"]

    members = get_room_members(room_id)

    ranking = result_data.get(
        "ranking",
        []
    )

    started_at = result_data.get(
        "started_at"
    )

    ended_at = result_data.get(
        "ended_at"
    )

    duration_text = "不明"

    if started_at and ended_at:
        try:
            start = datetime.fromisoformat(
                started_at
            )

            end = datetime.fromisoformat(
                ended_at
            )

            seconds = max(
                0,
                int((end - start).total_seconds())
            )

            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            remain_seconds = seconds % 60

            duration_text = (
                f"{hours}時間"
                f"{minutes}分"
                f"{remain_seconds}秒"
            )

        except Exception:
            pass

    msg = (
        "🏁 試合結果\n"
        "━━━━━━━━━━━━\n\n"
        f"ルーム：{room['room_name']}\n"
        f"試合時間：{duration_text}\n\n"
        "【最終ランキング】\n"
    )

    for i, row in enumerate(
        ranking,
        start=1
    ):

        name = row.get(
            "name",
            "不明"
        )

        score = row.get(
            "match_points",
            0
        )

        current = row.get(
            "current_points",
            0
        )

        if i == 1:
            mark = "🥇"
        elif i == 2:
            mark = "🥈"
        elif i == 3:
            mark = "🥉"
        else:
            mark = f"{i}位"

        msg += (
            f"{mark} {name}\n"
            f"   試合獲得ポイント：{score}pt\n"
            f"   現在所持ポイント：{current}pt\n\n"
        )

    if ranking:
        winner = ranking[0]

        msg += (
            "🏆 MVP\n"
            f"{winner.get('name', '不明')}\n"
            f"獲得ポイント："
            f"{winner.get('match_points', 0)}pt\n\n"
        )

    # アイテム使用数最多のプレイヤー
    item_stats = result_data.get(
        "item_stats",
        []
    )

    if item_stats:
        item_stats = sorted(
            item_stats,
            key=lambda x: x.get("item_count", 0),
            reverse=True
        )

        if item_stats[0].get("item_count", 0) > 0:
            msg += (
                "🎁 アイテム使用王\n"
                f"{item_stats[0].get('name', '不明')}\n"
                f"使用数："
                f"{item_stats[0].get('item_count', 0)}回\n\n"
            )

    msg += (
        "━━━━━━━━━━━━\n"
        "お疲れさまでした！"
    )

    for member in members:
        target_id = member.get("user_id")

        if not target_id:
            continue

        try:
            push_text(
                target_id,
                msg
            )

        except Exception as e:
            print(
                "リザルト送信エラー:",
                target_id,
                repr(e)
            )


# =====================================
# 再戦
# =====================================

def rematch_room(event, user_id):

    room = get_user_room(user_id)

    if not room:
        reply_text(
            event,
            "ルームに参加していません。"
        )
        return

    if not is_room_admin(user_id, room):
        reply_text(
            event,
            "❌ 再戦を開始できるのはルーム管理者だけです。"
        )
        return

    if room.get("status") == "playing":
        reply_text(
            event,
            "現在試合中です。"
        )
        return

    try:
        success, result = reset_room_for_rematch(
            room["room_id"]
        )

        if not success:
            reply_text(
                event,
                f"再戦準備に失敗しました。\n{result}"
            )
            return

        members = get_room_members(
            room["room_id"]
        )

        send_room_message(
            room["room_id"],
            "🔄 再戦準備が完了しました！\n\n"
            f"参加人数：{len(members)}人\n"
            "管理者が「試合開始」と送信すると、"
            "新しい試合が始まります。"
        )

    except Exception as e:
        print(
            "再戦エラー:",
            repr(e)
        )

        reply_text(
            event,
            "再戦処理中にエラーが発生しました。"
        )


# =====================================
# ルーム解散
# =====================================

def disband_room(event, user_id):

    room = get_user_room(user_id)

    if not room:
        reply_text(
            event,
            "ルームに参加していません。"
        )
        return

    if not is_room_admin(user_id, room):
        reply_text(
            event,
            "❌ ルームを解散できるのは管理者だけです。"
        )
        return

    if room.get("status") == "playing":
        reply_text(
            event,
            "❌ 試合中は解散できません。\n"
            "先に「試合終了」を実行してください。"
        )
        return

    room_id = room["room_id"]

    try:
        members = get_room_members(room_id)

        success, result = delete_room(room_id)

        if not success:
            reply_text(
                event,
                f"ルーム解散に失敗しました。\n{result}"
            )
            return

        message = (
            "🏠 ルームが解散されました。\n\n"
            f"ルーム名：{room['room_name']}\n"
            "ご参加ありがとうございました。"
        )

        for member in members:
            target_id = member.get("user_id")

            if target_id:
                try:
                    push_text(
                        target_id,
                        message
                    )
                except Exception as e:
                    print(
                        "解散通知エラー:",
                        repr(e)
                    )

        reply_text(
            event,
            "ルームを解散しました。"
        )

    except Exception as e:
        print(
            "ルーム解散エラー:",
            repr(e)
        )

        reply_text(
            event,
            "ルーム解散中にエラーが発生しました。"
        )


# =====================================
# 試合中ポイント獲得
# =====================================

def add_room_points(user_id, amount, reason="ポイント獲得"):

    room, match = get_active_room_and_match(
        user_id
    )

    if not room or not match:
        return False, "試合中のルームに参加していません"

    if amount <= 0:
        return False, "1以上のポイントを指定してください"

    success, result = add_match_points(
        room["room_id"],
        user_id,
        amount,
        reason
    )

    if not success:
        return False, result

    return True, result


# =====================================
# 試合中ポイント消費
# =====================================

def consume_room_points(user_id, amount, reason="ポイント消費"):

    room, match = get_active_room_and_match(
        user_id
    )

    if not room or not match:
        return False, "試合中のルームに参加していません"

    if amount <= 0:
        return False, "1以上のポイントを指定してください"

    success, result = consume_match_points(
        room["room_id"],
        user_id,
        amount,
        reason
    )

    if not success:
        return False, result

    return True, result


# =====================================
# 試合中ポイント状況
# =====================================

def show_room_points(event, user_id):

    room, match = get_active_room_and_match(
        user_id
    )

    if not room:
        reply_text(
            event,
            "ルームに参加していません。"
        )
        return

    if not match:
        reply_text(
            event,
            "現在試合中ではありません。"
        )
        return

    user_stats = get_room_user(
        room["room_id"],
        user_id
    )

    if not user_stats:
        reply_text(
            event,
            "ポイント情報を取得できませんでした。"
        )
        return

    msg = (
        "🎮 試合中ポイント\n\n"
        f"名前：{get_user_name(user_id)}\n"
        f"試合中の獲得ポイント："
        f"{user_stats.get('match_points', 0)}pt\n"
        f"現在所持ポイント："
        f"{user_stats.get('current_points', 0)}pt\n"
        f"消費ポイント："
        f"{user_stats.get('spent_points', 0)}pt\n"
        f"アイテム使用数："
        f"{user_stats.get('item_count', 0)}回"
    )

    reply_text(
        event,
        msg
    )


# =====================================
# 試合中ランキング
# =====================================

def show_room_ranking(event, user_id):

    room, match = get_active_room_and_match(
        user_id
    )

    if not room:
        reply_text(
            event,
            "ルームに参加していません。"
        )
        return

    if not match:
        reply_text(
            event,
            "試合中ではありません。"
        )
        return

    ranking = get_room_ranking(
        room["room_id"]
    )

    msg = "🏆 試合中ランキング\n\n"

    for i, row in enumerate(
        ranking,
        start=1
    ):

        if i == 1:
            mark = "🥇"
        elif i == 2:
            mark = "🥈"
        elif i == 3:
            mark = "🥉"
        else:
            mark = f"{i}位"

        msg += (
            f"{mark} {row['name']} "
            f"{row['match_points']}pt\n"
        )

    reply_text(
        event,
        msg
    )


# =====================================
# 試合中のアイテム使用数記録
# =====================================

def record_room_item_usage(
    room_id,
    user_id,
    item_id
):

    return add_match_item_usage(
        room_id,
        user_id,
        item_id
    )

# =====================================
# LINEメッセージ処理
# =====================================

@handler.add(
    MessageEvent,
    message=TextMessage
)
def handle_message(event):

    try:
        user_id = event.source.user_id
        text = event.message.text.strip()

        # -----------------------------
        # 初回ユーザー登録
        # -----------------------------

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

        # -----------------------------
        # ルーム名入力待ち
        # -----------------------------

        if user_id in room_create_waiting:

            del room_create_waiting[user_id]

            create_new_room(
                event,
                user_id,
                text
            )

            return

        # -----------------------------
        # ルームID入力待ち
        # -----------------------------

        if user_id in room_join_waiting:

            del room_join_waiting[user_id]

            join_existing_room(
                event,
                user_id,
                text
            )

            return

        # -----------------------------
        # ルーム作成
        # -----------------------------

        if text == "ルーム作成":

            if get_user_room(user_id):
                reply_text(
                    event,
                    "すでにルームに参加しています。\n"
                    "先に退出するか、現在のルームを解散してください。"
                )
                return

            handle_room_create(
                event,
                user_id
            )

            return

        # -----------------------------
        # ルーム参加
        # -----------------------------

        if text == "参加":

            if get_user_room(user_id):
                reply_text(
                    event,
                    "すでにルームに参加しています。"
                )
                return

            handle_room_join(
                event,
                user_id
            )

            return

        # -----------------------------
        # ルーム情報
        # -----------------------------

        if text == "ルーム情報":

            show_room_info(
                event,
                user_id
            )

            return

        # -----------------------------
        # ルーム退出
        # -----------------------------

        if text == "退出":

            leave_current_room(
                event,
                user_id
            )

            return

        # -----------------------------
        # 試合開始
        # -----------------------------

        if text == "試合開始":

            start_room_match(
                event,
                user_id
            )

            return

        # -----------------------------
        # 試合終了
        # -----------------------------

        if text == "試合終了":

            finish_room_match(
                event,
                user_id
            )

            return

        # -----------------------------
        # 再戦
        # -----------------------------

        if text == "再戦":

            rematch_room(
                event,
                user_id
            )

            return

        # -----------------------------
        # ルーム解散
        # -----------------------------

        if text == "ルーム解散":

            disband_room(
                event,
                user_id
            )

            return

        # -----------------------------
        # 試合ポイント
        # -----------------------------

        if text == "試合ポイント":

            show_room_points(
                event,
                user_id
            )

            return

        # -----------------------------
        # 試合ランキング
        # -----------------------------

        if text == "試合ランキング":

            show_room_ranking(
                event,
                user_id
            )

            return

        # -----------------------------
        # ケツポ
        # -----------------------------

        if text == "ケツポ":

            point_waiting[user_id] = True

            reply_text(
                event,
                "ポイント種別を選んでください。",
                QuickReply(
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

            return

        # -----------------------------
        # ケツ・珍棒の選択
        # -----------------------------

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
                f"{text}は何回でしたか？\n"
                "数字だけ入力してください。"
            )

            return

        # -----------------------------
        # ノーパン
        # -----------------------------

        if (
            user_id in point_waiting
            and text == "ノーパン"
        ):

            amount = 20

            room, match = get_active_room_and_match(
                user_id
            )

            if room and match:
                success, result = add_room_points(
                    user_id,
                    amount,
                    "ノーパン"
                )

                if not success:
                    reply_text(
                        event,
                        f"ポイント付与失敗：{result}"
                    )
                    return

                reply_text(
                    event,
                    "ノーパン +20pt\n"
                    "試合ポイントに反映しました。"
                )

            else:
                total, current = add_point(
                    user_id,
                    amount
                )

                reply_text(
                    event,
                    "ノーパン +20pt\n\n"
                    f"所持ポイント：{current}pt\n"
                    f"累計ポイント：{total}pt"
                )

            del point_waiting[user_id]

            return

        # -----------------------------
        # 回数入力
        # -----------------------------

        if user_id in count_waiting:

            if not text.isdigit():
                reply_text(
                    event,
                    "数字だけ入力してください。"
                )
                return

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

            room, match = get_active_room_and_match(
                user_id
            )

            if room and match:

                success, result = add_room_points(
                    user_id,
                    amount,
                    point_type
                )

                if not success:
                    reply_text(
                        event,
                        f"ポイント付与失敗：{result}"
                    )
                    return

                reply = (
                    f"ポイント獲得：{point_type}\n\n"
                    f"回数：{count}回\n"
                    f"獲得：{amount}pt\n"
                    "試合ポイントに反映しました。"
                )

            else:

                total, current = add_point(
                    user_id,
                    amount
                )

                reply = (
                    f"ポイント獲得：{point_type}\n\n"
                    f"回数：{count}回\n"
                    f"獲得：{amount}pt\n\n"
                    f"所持ポイント：{current}pt\n"
                    f"累計ポイント：{total}pt"
                )

            del count_waiting[user_id]

            reply_text(
                event,
                reply,
                get_quick_reply()
            )

            return

        # -----------------------------
        # ポイント
        # -----------------------------

        if text == "ポイント":

            room, match = get_active_room_and_match(
                user_id
            )

            if room and match:

                show_room_points(
                    event,
                    user_id
                )

                return

            user = get_user(user_id)

            reply_text(
                event,
                "ポイント情報\n\n"
                f"名前：{user['name']}\n"
                f"所持ポイント：{user['current_points']}pt\n"
                f"累計ポイント：{user['total_points']}pt\n"
                f"消費回数：{user['used_count']}回\n"
                f"おに回数：{user['oni_count']}回",
                get_quick_reply()
            )

            return

        # -----------------------------
        # 消費
        # -----------------------------

        if text == "消費":

            room, match = get_active_room_and_match(
                user_id
            )

            if room and match:

                success, result = consume_room_points(
                    user_id,
                    50,
                    "通常消費"
                )

                if success:
                    reply = (
                        "50ポイント消費しました。\n"
                        "試合ポイントに反映しました。"
                    )
                else:
                    reply = (
                        f"消費できませんでした。\n{result}"
                    )

            else:

                success, current = consume_point(
                    user_id
                )

                if success:
                    reply = (
                        "50ポイント消費しました。\n\n"
                        f"残り：{current}pt"
                    )
                else:
                    reply = (
                        "ポイントが不足しています。\n\n"
                        f"現在：{current}pt"
                    )

            reply_text(
                event,
                reply,
                get_quick_reply()
            )

            return

        # -----------------------------
        # ランキング
        # -----------------------------

        if text == "ランキング":

            current_ranking = get_current_ranking()
            total_ranking = get_total_ranking()

            current_msg = (
                "現在ポイントランキング\n\n"
            )

            for i, row in enumerate(
                current_ranking,
                start=1
            ):
                current_msg += (
                    f"{i}位 {row['name']} "
                    f"{row['current_points']}pt\n"
                )

            total_msg = (
                "累計ポイントランキング\n\n"
            )

            for i, row in enumerate(
                total_ranking,
                start=1
            ):
                total_msg += (
                    f"{i}位 {row['name']} "
                    f"{row['total_points']}pt\n"
                )

            line_bot_api.reply_message(
                event.reply_token,
                [
                    TextSendMessage(
                        text=current_msg
                    ),
                    TextSendMessage(
                        text=total_msg,
                        quick_reply=get_quick_reply()
                    )
                ]
            )

            return

        # -----------------------------
        # 試合ランキング
        # -----------------------------

        if text == "試合ランキング":

            show_room_ranking(
                event,
                user_id
            )

            return

        # -----------------------------
        # 鬼カード登録
        # -----------------------------

        if text == "おに":

            oni_card_waiting[user_id] = True

            reply_text(
                event,
                "鬼カード番号を入力してください。\n\n"
                "1\n2\n3\n4\n5"
            )

            return

        if (
            user_id in oni_card_waiting
            and text in ["1", "2", "3", "4", "5"]
        ):

            oni_confirm_waiting[user_id] = int(text)

            del oni_card_waiting[user_id]

            reply_text(
                event,
                f"カード{text}で登録しますか？",
                QuickReply(
                    items=[
                        QuickReplyButton(
                            action=MessageAction(
                                label="決定",
                                text="決定"
                            )
                        ),
                        QuickReplyButton(
                            action=MessageAction(
                                label="修正",
                                text="修正"
                            )
                        )
                    ]
                )
            )

            return

        if (
            user_id in oni_confirm_waiting
            and text == "修正"
        ):

            del oni_confirm_waiting[user_id]

            oni_card_waiting[user_id] = True

            reply_text(
                event,
                "鬼カード番号を入力してください。\n"
                "1 / 2 / 3 / 4 / 5"
            )

            return

        if (
            user_id in oni_confirm_waiting
            and text == "決定"
        ):

            card_no = oni_confirm_waiting[user_id]

            card = get_oni_card(card_no)

            if not card:
                reply_text(
                    event,
                    "その鬼カードは存在しません。"
                )
                del oni_confirm_waiting[user_id]
                return

            if (
                card.get("current_name")
                and card.get("start_time")
            ):

                start = datetime.fromisoformat(
                    card["start_time"]
                )

                now = (
                    datetime.now(start.tzinfo)
                    if start.tzinfo
                    else datetime.now()
                )

                seconds = int(
                    (now - start).total_seconds()
                )

                add_oni_history(
                    card_no,
                    card["current_name"],
                    max(0, seconds)
                )

            update_oni_card(
                card_no,
                user_id,
                user["name"]
            )

            add_oni_count(user_id)

            del oni_confirm_waiting[user_id]

            reply_text(
                event,
                f"👹 カード{card_no}で鬼登録しました。\n"
                "タイマーを開始しました。"
            )

            return

        # -----------------------------
        # 鬼ランキング
        # -----------------------------

        if text == "鬼ランキング":

            ranking = get_oni_ranking()

            msg = "👹 鬼ランキング\n\n"

            for i, row in enumerate(
                ranking,
                start=1
            ):

                name = row[0]
                seconds = row[1]

                hours = seconds // 3600
                minutes = (seconds % 3600) // 60

                msg += (
                    f"{i}位 {name}\n"
                    f"{hours}時間{minutes}分\n\n"
                )

            reply_text(
                event,
                msg,
                get_quick_reply()
            )

            return

        # -----------------------------
        # 譲渡
        # -----------------------------

        if text == "譲渡":

            names = get_all_names()

            transfer_waiting[user_id] = {
                "step": "select_user"
            }

            reply_text(
                event,
                "譲渡したい相手の名前を入力してください。\n\n"
                + "\n".join(names)
            )

            return

        if (
            user_id in transfer_waiting
            and transfer_waiting[user_id]["step"]
            == "select_user"
        ):

            target = get_user_by_name(text)

            if not target:
                reply_text(
                    event,
                    "その名前のユーザーは存在しません。"
                )
                return

            transfer_waiting[user_id] = {
                "step": "input_amount",
                "target": target["name"]
            }

            reply_text(
                event,
                f"{target['name']}に何ポイント譲渡しますか？\n"
                "数字だけ入力してください。"
            )

            return

        if (
            user_id in transfer_waiting
            and transfer_waiting[user_id]["step"]
            == "input_amount"
        ):

            if not text.isdigit() or int(text) <= 0:
                reply_text(
                    event,
                    "1以上の数字を入力してください。"
                )
                return

            amount = int(text)

            target_name = transfer_waiting[user_id]["target"]

            success, result = transfer_points(
                user_id,
                target_name,
                amount
            )

            del transfer_waiting[user_id]

            if success:
                reply_text(
                    event,
                    f"{target_name}に{amount}pt譲渡しました。"
                )
            else:
                reply_text(
                    event,
                    f"譲渡失敗：{result}"
                )

            return

        # -----------------------------
        # 管理者コンソール
        # -----------------------------

        if text == "アナル":

            if user_id != ADMIN_USER_ID:
                reply_text(
                    event,
                    "松下穂高"
                )
                return

            reply_text(
                event,
                "🛠 管理者コンソール\n\n"
                "利用可能コマンド\n\n"
                "・鬼設定\n"
                "・リセット\n"
                "・全員+20",
                get_admin_quick_reply()
            )

            return

        # -----------------------------
        # 鬼設定
        # -----------------------------

        if text == "鬼設定":

            if user_id != ADMIN_USER_ID:
                reply_text(
                    event,
                    "管理者専用コマンドです。"
                )
                return

            oni_setup_waiting[user_id] = True

            reply_text(
                event,
                "鬼設定モード\n\n"
                "カード番号と名前を入力してください。\n\n"
                "例：\n"
                "1 山田\n"
                "3 佐藤\n"
                "5 央多"
            )

            return

        if user_id in oni_setup_waiting:

            success_count = 0

            for line in text.split("\n"):

                parts = line.strip().split()

                if len(parts) != 2:
                    continue

                if not parts[0].isdigit():
                    continue

                card_no = int(parts[0])

                if card_no not in [1, 2, 3, 4, 5]:
                    continue

                target = get_user_by_name(
                    parts[1]
                )

                if not target:
                    continue

                update_oni_card(
                    card_no,
                    target["user_id"],
                    target["name"]
                )

                success_count += 1

            del oni_setup_waiting[user_id]

            reply_text(
                event,
                f"鬼設定を{success_count}件反映しました。"
            )

            return

        # -----------------------------
        # 全員+20
        # -----------------------------

        if text == "全員+20":

            if user_id != ADMIN_USER_ID:
                reply_text(
                    event,
                    "管理者専用コマンドです。"
                )
                return

            add_points_all(20)

            reply_text(
                event,
                "全員に20pt付与しました。"
            )

            return

        # -----------------------------
        # リセット
        # -----------------------------

        if text == "リセット":

            if user_id != ADMIN_USER_ID:
                reply_text(
                    event,
                    "管理者専用コマンドです。"
                )
                return

            reset_all_data()

            transfer_waiting.clear()
            point_waiting.clear()
            count_waiting.clear()
            oni_card_waiting.clear()
            item_waiting.clear()
            item_action_waiting.clear()
            oni_setup_waiting.clear()
            oni_confirm_waiting.clear()

            reply_text(
                event,
                "🔄 全データをリセットしました。\n\n"
                "ユーザー登録とショップの商品一覧は維持されます。"
            )

            return

        # -----------------------------
        # アイテムメニュー
        # -----------------------------

        if text == "アイテム":

            item_waiting[user_id] = {
                "step": "menu"
            }

            reply_text(
                event,
                "アイテムメニュー",
                QuickReply(
                    items=[
                        QuickReplyButton(
                            action=MessageAction(
                                label="購入",
                                text="購入"
                            )
                        ),
                        QuickReplyButton(
                            action=MessageAction(
                                label="使用",
                                text="使用"
                            )
                        )
                    ]
                )
            )

            return

        # -----------------------------
        # アイテム購入
        # -----------------------------

        if (
            user_id in item_waiting
            and text == "購入"
        ):

            items = get_items()

            if not items:
                del item_waiting[user_id]

                reply_text(
                    event,
                    "現在販売中のアイテムはありません。"
                )

                return

            msg = "🛒 アイテムショップ\n\n"

            for item in items:
                msg += (
                    f"{item['item_id']} "
                    f"{item['item_name']} "
                    f"{item['price']}pt\n"
                )

            msg += "\n購入したい番号を入力してください。"

            item_waiting[user_id] = {
                "step": "buy"
            }

            reply_text(
                event,
                msg
            )

            return

        # -----------------------------
        # アイテム使用一覧
        # -----------------------------

        if (
            user_id in item_waiting
            and text == "使用"
        ):

            owned_items = get_user_items(
                user_id
            )

            msg = "🎁 所持アイテム\n\n"

            available = []

            for owned in owned_items:

                if owned.get("quantity", 0) <= 0:
                    continue

                item_info = get_item(
                    owned["item_id"]
                )

                if not item_info:
                    continue

                available.append(
                    item_info["item_id"]
                )

                msg += (
                    f"{item_info['item_id']} "
                    f"{item_info['item_name']} "
                    f"×{owned['quantity']}\n"
                )

            if not available:
                del item_waiting[user_id]

                reply_text(
                    event,
                    "使用できるアイテムを持っていません。"
                )

                return

            msg += "\n使用する番号を入力してください。"

            item_waiting[user_id] = {
                "step": "use",
                "available_items": available
            }

            reply_text(
                event,
                msg
            )

            return

        # -----------------------------
        # アイテム購入処理
        # -----------------------------

        if (
            user_id in item_waiting
            and item_waiting[user_id].get("step") == "buy"
        ):

            if not text.isdigit():
                reply_text(
                    event,
                    "アイテム番号を数字で入力してください。"
                )
                return

            success, result = buy_item(
                user_id,
                int(text)
            )

            del item_waiting[user_id]

            if success:
                reply_text(
                    event,
                    f"{result['item_name']}を購入しました。"
                )
            else:
                reply_text(
                    event,
                    f"購入失敗：{result}"
                )

            return

        # -----------------------------
        # アイテム使用処理
        # -----------------------------

        if (
            user_id in item_waiting
            and item_waiting[user_id].get("step") == "use"
        ):

            if not text.isdigit():
                reply_text(
                    event,
                    "アイテム番号を数字で入力してください。"
                )
                return

            item_id = int(text)

            available = item_waiting[user_id].get(
                "available_items",
                []
            )

            if item_id not in available:
                reply_text(
                    event,
                    "所持しているアイテム番号を入力してください。"
                )
                return

            item_info = get_item(item_id)

            if not item_info:
                reply_text(
                    event,
                    "アイテムが見つかりません。"
                )
                return

            item_name = item_info["item_name"]

            success = use_item(
                user_id,
                item_id
            )

            if not success:
                reply_text(
                    event,
                    "アイテムを使用できませんでした。"
                )
                return

            # 試合中なら使用数を記録
            room, match = get_active_room_and_match(
                user_id
            )

            if room and match:
                record_room_item_usage(
                    room["room_id"],
                    user_id,
                    item_id
                )

            del item_waiting[user_id]

            # 鬼チェッカー
            if item_name == "鬼チェッカー":

                cards = get_all_oni_cards()

                msg = "👹 現在の鬼\n\n"

                for card in cards:

                    name = card.get(
                        "current_name"
                    ) or "なし"

                    msg += (
                        f"カード{card['card_no']}："
                        f"{name}\n"
                    )

                reply_text(
                    event,
                    msg
                )

                return

            # 鬼引渡しカード
            if item_name == "鬼引渡しカード":

                item_action_waiting[user_id] = {
                    "type": "oni_transfer"
                }

                reply_text(
                    event,
                    "鬼を引き渡す相手の名前を入力してください。"
                )

                return

            reply_text(
                event,
                f"✅ {item_name}を使用しました。"
            )

            return

        # -----------------------------
        # 鬼引渡し先入力
        # -----------------------------

        if (
            user_id in item_action_waiting
            and item_action_waiting[user_id].get("type")
            == "oni_transfer"
        ):

            target = get_user_by_name(text)

            if not target:
                reply_text(
                    event,
                    "その名前のユーザーは存在しません。"
                )
                return

            cards = get_all_oni_cards()

            active_card = None

            for card in cards:
                if card.get("current_name"):
                    active_card = card
                    break

            if not active_card:
                reply_text(
                    event,
                    "現在鬼が登録されていません。"
                )
                del item_action_waiting[user_id]
                return

            if active_card.get("start_time"):

                start = datetime.fromisoformat(
                    active_card["start_time"]
                )

                now = (
                    datetime.now(start.tzinfo)
                    if start.tzinfo
                    else datetime.now()
                )

                seconds = int(
                    (now - start).total_seconds()
                )

                add_oni_history(
                    active_card["card_no"],
                    active_card["current_name"],
                    max(0, seconds)
                )

            update_oni_card(
                active_card["card_no"],
                target["user_id"],
                target["name"]
            )

            del item_action_waiting[user_id]

            reply_text(
                event,
                f"鬼を{target['name']}に引き渡しました。"
            )

            return

        # -----------------------------
        # その他
        # -----------------------------

        reply_text(
            event,
            "ケツ叩きカウンター\n\n"
            "コマンドを選択してください。",
            get_quick_reply()
        )

    except Exception as e:

        print(
            "handle_messageエラー:",
            repr(e)
        )

        try:
            reply_text(
                event,
                "処理中にエラーが発生しました。\n"
                "時間をおいてもう一度試してください。"
            )
        except Exception:
            pass
