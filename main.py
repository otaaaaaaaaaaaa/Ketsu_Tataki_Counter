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
    add_oni_count
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

# 譲渡用
transfer_waiting = {}


def get_quick_reply():

    return QuickReply(
        items=[
            QuickReplyButton(
                action=MessageAction(
                    label="🍑 ケツ",
                    text="ケツ"
                )
            ),
            QuickReplyButton(
                action=MessageAction(
                    label="👹 おに",
                    text="おに"
                )
            ),
            QuickReplyButton(
                action=MessageAction(
                    label="🎁 譲渡",
                    text="譲渡"
                )
            ),
            QuickReplyButton(
                action=MessageAction(
                    label="🔥 消費",
                    text="消費"
                )
            ),
            QuickReplyButton(
                action=MessageAction(
                    label="📊 ポイント",
                    text="ポイント"
                )
            ),
            QuickReplyButton(
                action=MessageAction(
                    label="🏆 ランキング",
                    text="ランキング"
                )
            )
        ]
    )


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
        # ケツ
        # ----------------------

        elif text == "ケツ":

            total, current = (
                add_point(
                    user_id
                )
            )

            reply = (
                "🍑 ケツポイント +1\n\n"
                f"所持ポイント: "
                f"{current}pt\n"
                f"累計ポイント: "
                f"{total}pt"
            )

        # ----------------------
        # おに
        # ----------------------
        
        elif text == "おに":

            oni_count = add_oni_count(
                user_id
            )

            reply = (
                "👹 おに回数 +1\n\n"
                f"おに回数: {oni_count}回"
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
                f"名前: "
                f"{user['name']}\n"
                f"所持ポイント: "
                f"{user['current_points']}pt\n"
                f"累計ポイント: "
                f"{user['total_points']}pt\n"
                f"消費回数: "
                f"{user['used_count']}回"
                f"おに回数: "
                f"{user['oni_count']}回"
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
