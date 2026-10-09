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
    init_db,
    get_user,
    create_user,
    update_name,
    get_ranking
)

from point_service import (
    add_point,
    consume_point
)

from database import (
    init_db,
    get_user,
    create_user,
    update_name,
    get_ranking,
    reset_all_points
)

app = FastAPI()

# Renderの環境変数から取得
CHANNEL_ACCESS_TOKEN = os.getenv(
    "CHANNEL_ACCESS_TOKEN"
)

CHANNEL_SECRET = os.getenv(
    "CHANNEL_SECRET"
)

line_bot_api = LineBotApi(
    CHANNEL_ACCESS_TOKEN
)

handler = WebhookHandler(
    CHANNEL_SECRET
)

init_db()


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
                    label="📊 ポイント",
                    text="ポイント"
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

    print("Webhook受信")

    try:

        handler.handle(
            body.decode("utf-8"),
            signature
        )

    except InvalidSignatureError:

        print("署名エラー")

        return {
            "error": "invalid signature"
        }

    except Exception as e:

        print("エラー:", e)

    return "OK"


@handler.add(
    MessageEvent,
    message=TextMessage
)
def handle_message(event):

    try:

        user_id = event.source.user_id
        text = event.message.text

        print("受信メッセージ:", text)

        profile = line_bot_api.get_profile(
            user_id
        )

        display_name = (
            profile.display_name
        )

        create_user(
            user_id,
            display_name
        )

        update_name(
            user_id,
            display_name
        )

        if text == "ケツ":

            total, current = add_point(
                user_id
            )

            reply = (
                "🍑 ケツポイント +1\n\n"
                f"所持ポイント: {current}pt\n"
                f"累計ポイント: {total}pt"
            )

        elif text == "ポイント":

            user = get_user(
                user_id
            )

            reply = (
                "📊 ポイント情報\n\n"
                f"名前: {user[1]}\n"
                f"所持ポイント: {user[3]}pt\n"
                f"累計ポイント: {user[2]}pt\n"
                f"消費回数: {user[4]}回"
            )

        elif text == "消費":

            success, current = consume_point(
                user_id
            )

            if success:

                reply = (
                    "✅ 50ポイント消費！\n\n"
                    f"残り: {current}pt"
                )

            else:

                reply = (
                    "❌ ポイント不足\n\n"
                    "必要: 50pt\n"
                    f"現在: {current}pt"
                )

        elif text == "ランキング":

            ranking = get_ranking()

            msg = "🏆 ケツランキング\n\n"

            for i, row in enumerate(
                ranking,
                start=1
            ):

                msg += (
                    f"{i}位 "
                    f"{row[0]} "
                    f"{row[1]}pt\n"
                )

            reply = msg

        else:

            reply = (
                "🍑 ケツ叩きカウンター\n\n"
                "下のボタンから選んでね"
            )

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(
                text=reply,
                quick_reply=get_quick_reply()
            )
        )

        print("返信成功")

    except Exception as e:

        print("handle_messageエラー:", e)
        
    except Exception as e:

        print(user_id)

