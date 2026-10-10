import os


print("SUPABASE_URL =", os.getenv("SUPABASE_URL"))
print("SUPABASE_KEY =", os.getenv("SUPABASE_KEY"))



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
    update_name,
    get_ranking,
    reset_all_points
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

        print("callbackエラー:", e)

    return "OK"


@handler.add(
    MessageEvent,
    message=TextMessage
)
def handle_message(event):

    try:

        user_id = event.source.user_id
        text = event.message.text

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

        # ケツ

        if text == "ケツ":

            total, current = add_point(
                user_id
            )

            reply = (
                "🍑 ケツポイント +1\n\n"
                f"所持ポイント: {current}pt\n"
                f"累計ポイント: {total}pt"
            )

        # ポイント

        elif text == "ポイント":

            user = get_user(user_id)

            reply = (
                "📊 ポイント情報\n\n"
                f"名前: {user['name']}\n"
                f"所持ポイント: {user['current_points']}pt\n"
                f"累計ポイント: {user['total_points']}pt\n"
                f"消費回数: {user['used_count']}回"
            )

        # 消費

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

        # ランキング

        elif text == "ランキング":

            ranking = get_ranking()

            msg = "🏆 ケツランキング\n\n"

            for i, row in enumerate(
                ranking,
                start=1
            ):

                msg += (
                    f"{i}位 "
                    f"{row['name']} "
                    f"{row['total_points']}pt\n"
                )

            reply = msg

        # リセット

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
                quick_reply=get_quick_reply()
            )
        )

    except Exception as e:

        print(
            "handle_messageエラー:",
            e
        )
