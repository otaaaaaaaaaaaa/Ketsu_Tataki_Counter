import os

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
    use_item,
    buy_item
)

from point_service import (
    add_point,
    consume_point
)

from datetime import datetime

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

# 譲渡用
transfer_waiting = {}

# ケツポ選択待ち用
point_waiting = {}

# 回数入力待ち
count_waiting = {}

# おにカウント用
oni_card_waiting = {}

# アイテム用
item_waiting = {}

# ----------------------
# ボタン
# ----------------------

# 入れるならここ

@app.get("/")
def root():

    return {
        "status": "running"
    }


@app.post("/callback")
async def callback(request: Request):

    body = await request.body()

    signature = request.headers[
        "X-Line-Signature"
    ]

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


@handler.add(
    MessageEvent,
    message=TextMessage
)
def handle_message(event):

    try:

        user_id = event.source.user_id
        text = event.message.text.strip()

        user = get_user(user_id)

        # 初回登録
        if not user:

            profile = (
                line_bot_api.get_profile(
                    user_id
                )
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
            and
            transfer_waiting[user_id][
                "step"
            ] == "select_user"
        ):

            target = text

            target_user = (
                get_user_by_name(
                    target
                )
            )

            if not target_user:

                reply = (
                    "❌ その名前は存在しません"
                )

            else:

                transfer_waiting[user_id] = {
                    "step":
                    "input_amount",
                    "target":
                    target
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
            and
            transfer_waiting[user_id][
                "step"
            ] == "input_amount"
        ):

            if not text.isdigit():

                reply = (
                    "❌ 数字だけ入力してください"
                )

            else:

                amount = int(text)

                target = (
                    transfer_waiting[
                        user_id
                    ]["target"]
                )

                success, result = (
                    transfer_points(
                        user_id,
                        target,
                        amount
                    )
                )

                if success:

                    reply = (
                        f"🎁 {target} に "
                        f"{amount}pt譲渡しました"
                    )

                else:

                    reply = (
                        f"❌ {result}"
                    )

                del transfer_waiting[
                    user_id
                ]

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


        # 回数入力が必要なもの
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

        # 回数入力後
        elif (
            user_id in count_waiting
            and text.isdigit()
        ):

            count = int(text)

            point_type = (
                count_waiting[user_id]["type"]
            )

            if point_type == "ケツ":
                add = count * 1

            else:
                add = count * 3

            user = get_user(user_id)

            total = (
                user["total_points"]
                + add
            )

            current = (
                user["current_points"]
                + add
            )

            update_user(
                user_id,
                total,
                current,
                user["used_count"]
            )

            del count_waiting[user_id]

            reply = (
                f"✅ {point_type}\n\n"
                f"回数: {count}回\n"
                f"獲得: {add}pt\n\n"
                f"所持ポイント: {current}pt\n"
                f"累計ポイント: {total}pt"
            )

        # ノーパン固定
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
                f"✅ ノーパン +{add}pt\n\n"
                f"所持ポイント: {current}pt\n"
                f"累計ポイント: {total}pt"
            )

        # セックス固定
        elif (
            user_id in point_waiting
            and text == "セックス"
        ):

            add = 15

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
                f"✅ セックス +{add}pt\n\n"
                f"所持ポイント: {current}pt\n"
                f"累計ポイント: {total}pt"
            )

        # ----------------------
        # おに
        # ----------------------
        
        elif text == "おに":

            oni_card_waiting[user_id] = True

            reply = (
                "👹 鬼カード番号を入力してください\n\n"
                "1\n"
                "2\n"
                "3\n"
                "4\n"
                "5"
            )

        elif (
            user_id in oni_card_waiting
            and text in ["1","2","3","4","5"]
        ):

            card_no = int(text)

            card = get_oni_card(
                card_no
            )

            # 前の鬼がいる場合

            if (
                card["current_name"]
                and
                card["start_time"]
            ):

                start = (
                    datetime.fromisoformat(
                        card["start_time"]
                    )
                )

                seconds = int(
                    (
                        datetime.now()
                        - start
                    ).total_seconds()
                )

                add_oni_history(
                    card_no,
                    card["current_name"],
                    seconds
                )

            update_oni_card(
                card_no,
                user_id,
                user["name"]
            )

            del oni_card_waiting[
                user_id
            ]

            reply = (
                f"👹 カード{card_no}で鬼登録\n\n"
                "タイマー開始"
            )


        # ----------------------
        # 譲渡
        # ----------------------

        elif text == "譲渡":

            names = get_all_names()

            transfer_waiting[
                user_id
            ] = {
                "step":
                "select_user"
            }

            users_text = "\n".join(
                names
            )

            reply = (
                "🎁 譲渡モード\n\n"
                "譲渡したい相手の名前を送信してください\n\n"
                "【参加者一覧】\n"
                f"{users_text}"
            )

        # ----------------------
        # ポイント
        # ----------------------

        elif text == "ポイント":

            user = get_user(
                user_id
            )

            reply = (
                "📊 ポイント情報\n\n"
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

            success, current = (
                consume_point(
                    user_id
                )
            )

            if success:

                reply = (
                    "✅ 50ポイント消費！\n\n"
                    f"残り: "
                    f"{current}pt"
                )

            else:

                reply = (
                    "❌ ポイント不足\n\n"
                    "必要: 50pt\n"
                    f"現在: "
                    f"{current}pt"
                )

        # ----------------------
        # ランキング
        # ----------------------

        elif text == "ランキング":

            current_ranking = (
                get_current_ranking()
            )

            total_ranking = (
                get_total_ranking()
            )

            current_msg = (
                "💰 現在ポイントランキング\n\n"
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
                "🏆 累計ポイントランキング\n\n"
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
                        quick_reply=
                        get_quick_reply()
                    )
                ]
            )

            return

        # ----------------------
        # 鬼ランキング
        # ----------------------

        elif text == "鬼ランキング":

            ranking = get_oni_ranking()

            msg = (
                "👑 鬼ランキング\n\n"
            )

            for i, row in enumerate(
                ranking,
                start=1
            ):

                name = row[0]
                seconds = row[1]

                hours = (
                    seconds // 3600
                )

                minutes = (
                    (seconds % 3600)
                    // 60
                )

                msg += (
                    f"{i}位 "
                    f"{name}\n"
                    f"{hours}時間"
                    f"{minutes}分\n\n"
                )

            reply = msg

        # ----------------------
        # リセット
        # ----------------------

        elif text == "リセット":

            if user_id == ADMIN_USER_ID:

                reset_all_points()

                reply = (
                    "✅ 全ユーザーのポイントをリセットしました"
                )

            else:

                reply = (
                    "❌ 管理者専用コマンドです"
                )

        # ----------------------
        # アイテム
        # ----------------------

        elif text == "アイテム":

            item_waiting[user_id] = {
                "step": "menu"
            }

            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(
                    text=(
                        "📦 アイテム\n\n"
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

        elif (
            user_id in item_waiting
            and text == "購入"
        ):
            items = get_items()

            msg = (
                "🛒 アイテムショップ\n\n"
            )

            for item in items:

                msg += (
                    f"{item['item_id']} "
                    f"{item['item_name']} "
                    f"{item['price']}pt\n"
                )

            msg += (
                "\n購入したい番号を入力"
            )

            item_waiting[user_id] = {
                "step": "buy"
            }

            reply = msg

        elif (
            user_id in item_waiting
            and
            item_waiting[user_id]["step"]
            == "buy"
            and
            text.isdigit()
        ):

            success, item = buy_item(
                user_id,
                int(text)
            )

            if success:

                reply = (
                    f"✅ "
                    f"{item['item_name']}"
                    "を購入しました"
                )

            else:

                reply = (
                    f"❌ {item}"
                )

            del item_waiting[user_id]

        else:

            reply = (
                "🍑 ケツ叩きカウンター\n\n"
                "下のボタンから選んでね"
            )

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(
                text=reply,
                quick_reply=
                get_quick_reply()
            )
        )

    except Exception as e:

        print(
            "handle_messageエラー:",
            e
        ) 
