import os
from datetime import datetime

from fastapi import FastAPI, Request

from linebot import (
    LineBotApi,
    WebhookHandler
)

from linebot.exceptions import (
    InvalidSignatureError
)

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
    reset_all_points,
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
    use_item
)

from point_service import (
    add_point,
    consume_point
)


app = FastAPI()

CHANNEL_ACCESS_TOKEN = os.getenv(
    "CHANNEL_ACCESS_TOKEN"
)

CHANNEL_SECRET = os.getenv(
    "CHANNEL_SECRET"
)

ADMIN_USER_ID = os.getenv(
    "ADMIN_USER_ID"
)

line_bot_api = LineBotApi(
    CHANNEL_ACCESS_TOKEN
)

handler = WebhookHandler(
    CHANNEL_SECRET
)


# ----------------------
# 入力待ち状態
# ----------------------

transfer_waiting = {}
point_waiting = {}
count_waiting = {}
oni_card_waiting = {}
item_waiting = {}


# ----------------------
# クイックリプライ
# ----------------------

def get_quick_reply():
    return QuickReply(
        items=[]
    )


# ----------------------
# トップページ
# ----------------------

@app.get("/")
def root():
    return {
        "status": "running"
    }


# ----------------------
# LINE Webhook
# ----------------------

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
            e
        )

    return "OK"


# ----------------------
# メッセージ処理
# ----------------------

@handler.add(
    MessageEvent,
    message=TextMessage
)
def handle_message(event):

    try:

        user_id = event.source.user_id
        text = event.message.text.strip()

        user = get_user(user_id)

        # ----------------------
        # 初回登録
        # ----------------------

        if not user:

            profile = line_bot_api.get_profile(
                user_id
            )

            create_user(
                user_id,
                profile.display_name
            )

            user = get_user(user_id)

        # ----------------------
        # 譲渡先入力待ち
        # ----------------------

        if (
            user_id in transfer_waiting
            and transfer_waiting[user_id]["step"]
            == "select_user"
        ):

            target = text

            target_user = get_user_by_name(
                target
            )

            if not target_user:

                reply = (
                    "その名前は存在しません"
                )

            else:

                transfer_waiting[user_id] = {
                    "step": "input_amount",
                    "target": target
                }

                reply = (
                    f"{target}へ何ポイント譲渡しますか？\n\n"
                    "数字だけ入力してください"
                )

        # ----------------------
        # 譲渡金額入力待ち
        # ----------------------

        elif (
            user_id in transfer_waiting
            and transfer_waiting[user_id]["step"]
            == "input_amount"
        ):

            if not text.isdigit():

                reply = (
                    "数字だけ入力してください"
                )

            else:

                amount = int(text)

                target = transfer_waiting[
                    user_id
                ]["target"]

                success, result = transfer_points(
                    user_id,
                    target,
                    amount
                )

                if success:

                    reply = (
                        f"{target} に "
                        f"{amount}pt譲渡しました"
                    )

                else:

                    reply = f"譲渡失敗: {result}"

                del transfer_waiting[user_id]

        # ----------------------
        # ケツポ
        # ----------------------

        elif text == "ケツポ":

            point_waiting[user_id] = True

            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(
                    text="ポイント種別を選んでください",
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

        # ----------------------
        # 回数入力が必要なもの
        # ----------------------

        elif (
            user_id in point_waiting
            and text in ["ケツ", "珍棒"]
        ):

            count_waiting[user_id] = {
                "type": text
            }

            del point_waiting[user_id]

            reply = (
                f"{text}は何回でしたか？\n\n"
                "数字だけ入力してください"
            )

        # ----------------------
        # 回数入力後
        # ----------------------

        elif (
            user_id in count_waiting
            and text.isdigit()
        ):

            count = int(text)

            point_type = count_waiting[
                user_id
            ]["type"]

            if point_type == "ケツ":
                add = count * 1
            else:
                add = count * 3

            user = get_user(user_id)

            total = (
                user["total_points"] + add
            )

            current = (
                user["current_points"] + add
            )

            update_user(
                user_id,
                total,
                current,
                user["used_count"]
            )

            del count_waiting[user_id]

            reply = (
                f"ポイント獲得: {point_type}\n\n"
                f"回数: {count}回\n"
                f"獲得: {add}pt\n\n"
                f"所持ポイント: {current}pt\n"
                f"累計ポイント: {total}pt"
            )

        # ----------------------
        # ノーパン
        # ----------------------

        elif (
            user_id in point_waiting
            and text == "ノーパン"
        ):

            add = 20

            user = get_user(user_id)

            total = user["total_points"] + add
            current = user["current_points"] + add

            update_user(
                user_id,
                total,
                current,
                user["used_count"]
            )

            del point_waiting[user_id]

            reply = (
                f"ノーパン +{add}pt\n\n"
                f"所持ポイント: {current}pt\n"
                f"累計ポイント: {total}pt"
            )

        # ----------------------
        # おに
        # ----------------------

        elif text == "おに":

            oni_card_waiting[user_id] = True

            reply = (
                "鬼カード番号を入力してください\n\n"
                "1\n"
                "2\n"
                "3\n"
                "4\n"
                "5"
            )

        elif (
            user_id in oni_card_waiting
            and text in ["1", "2", "3", "4", "5"]
        ):

            card_no = int(text)

            card = get_oni_card(card_no)

            if not card:

                reply = (
                    "その鬼カードは存在しません"
                )

                del oni_card_waiting[user_id]

            else:

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

                del oni_card_waiting[user_id]

                reply = (
                    f"カード{card_no}で鬼登録しました\n\n"
                    "タイマー開始"
                )

        # ----------------------
        # 譲渡
        # ----------------------

        elif text == "譲渡":

            names = get_all_names()

            transfer_waiting[user_id] = {
                "step": "select_user"
            }

            users_text = "\n".join(names)

            reply = (
                "譲渡モード\n\n"
                "譲渡したい相手の名前を送信してください\n\n"
                "参加者一覧\n"
                f"{users_text}"
            )

        # ----------------------
        # ポイント
        # ----------------------

        elif text == "ポイント":

            user = get_user(user_id)

            reply = (
                "ポイント情報\n\n"
                f"名前: {user['name']}\n"
                f"所持ポイント: {user['current_points']}pt\n"
                f"累計ポイント: {user['total_points']}pt\n"
                f"消費回数: {user['used_count']}回\n"
                f"おに回数: {user['oni_count']}回"
            )

        # ----------------------
        # 消費
        # ----------------------

        elif text == "消費":

            success, current = consume_point(
                user_id
            )

            if success:

                reply = (
                    "50ポイント消費しました\n\n"
                    f"残り: {current}pt"
                )

            else:

                reply = (
                    "ポイントが不足しています\n\n"
                    f"現在: {current}pt"
                )

        # ----------------------
        # ランキング
        # ----------------------

        elif text == "ランキング":

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
                    f"{i}位 "
                    f"{row['name']} "
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
                    f"{i}位 "
                    f"{row['name']} "
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

        # ----------------------
        # 鬼ランキング
        # ----------------------

        elif text == "鬼ランキング":

            ranking = get_oni_ranking()

            msg = "鬼ランキング\n\n"

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

            reply = msg

        # ----------------------
        # リセット
        # ----------------------

        elif text == "リセット":

            if user_id == ADMIN_USER_ID:

                reset_all_points()

                reply = (
                    "全ユーザーのポイントをリセットしました"
                )

            else:

                reply = (
                    "管理者専用コマンドです"
                )

        # ----------------------
        # アイテムメニュー
        # ----------------------

        elif text == "アイテム":

            item_waiting[user_id] = {
                "step": "menu"
            }

            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(
                    text=(
                        "アイテム\n\n"
                        "購入\n"
                        "使用"
                    ),
                    quick_reply=QuickReply(
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
            )

            return

        # ----------------------
        # アイテム購入メニュー
        # ----------------------

        elif (
            user_id in item_waiting
            and text == "購入"
        ):

            items = get_items()

            if not items:

                reply = (
                    "現在、販売中のアイテムはありません"
                )

                del item_waiting[user_id]

            else:

                msg = "アイテムショップ\n\n"

                for item in items:

                    msg += (
                        f"{item['item_id']} "
                        f"{item['item_name']} "
                        f"{item['price']}pt\n"
                    )

                msg += (
                    "\n購入したい番号を入力してください"
                )

                item_waiting[user_id] = {
                    "step": "buy"
                }

                reply = msg

        # ----------------------
        # アイテム使用メニュー
        # ----------------------

        elif (
            user_id in item_waiting
            and text == "使用"
        ):

            owned_items = get_user_items(user_id)

            if not owned_items:

                reply = (
                    "使用できるアイテムを持っていません"
                )

                del item_waiting[user_id]

            else:

                msg = "所持アイテム\n\n"
                available_items = []

                for owned in owned_items:

                    if owned.get("quantity", 0) <= 0:
                        continue

                    item_info = get_item(
                        owned["item_id"]
                    )

                    if not item_info:
                        continue

                    available_items.append(
                        item_info["item_id"]
                    )

                    msg += (
                        f"{item_info['item_id']} "
                        f"{item_info['item_name']} "
                        f"×{owned['quantity']}\n"
                    )

                if not available_items:

                    reply = (
                        "使用できるアイテムを持っていません"
                    )

                    del item_waiting[user_id]

                else:

                    msg += (
                        "\n使用するアイテムの番号を入力してください"
                    )

                    item_waiting[user_id] = {
                        "step": "use",
                        "available_items": available_items
                    }

                    reply = msg

        # ----------------------
        # アイテム使用処理
        # ----------------------

        elif (
            user_id in item_waiting
            and item_waiting[user_id].get("step") == "use"
            and text.isdigit()
        ):

            item_id = int(text)

            available_items = item_waiting[
                user_id
            ].get("available_items", [])

            if item_id not in available_items:

                reply = (
                    "所持アイテムの番号を入力してください"
                )

            else:

                success = use_item(
                    user_id,
                    item_id
                )

                item_info = get_item(item_id)

                if success:

                    item_name = (
                        item_info["item_name"]
                        if item_info
                        else f"アイテム{item_id}"
                    )

                    reply = (
                        f"{item_name}を使用しました"
                    )

                else:

                    reply = (
                        "アイテムを使用できませんでした"
                    )

                del item_waiting[user_id]

        # ----------------------
        # アイテム購入処理
        # ----------------------

        elif (
            user_id in item_waiting
            and item_waiting[user_id].get("step") == "buy"
            and text.isdigit()
        ):

            success, item = buy_item(
                user_id,
                int(text)
            )

            if success:

                reply = (
                    f"{item['item_name']}を購入しました"
                )

            else:

                reply = f"購入失敗: {item}"

            del item_waiting[user_id]

        # ----------------------
        # その他
        # ----------------------

        else:

            reply = (
                "ケツ叩きカウンター\n\n"
                "下のボタンから選んでね"
            )

        # ----------------------
        # 共通返信
        # ----------------------

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(
                text=reply,
                quick_reply=get_quick_reply()
            )
        )

    except Exception as e:

        print(
            "handle_messageエラー:",
            repr(e)
        )
