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
    TextSendMessage
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

app = FastAPI()

CHANNEL_ACCESS_TOKEN = "YOUR_CHANNEL_ACCESS_TOKEN"
CHANNEL_SECRET = "YOUR_CHANNEL_SECRET"

line_bot_api = LineBotApi(
    CHANNEL_ACCESS_TOKEN
)

handler = WebhookHandler(
    CHANNEL_SECRET
)

init_db()


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
        return {"error": "invalid signature"}

    return "OK"


@handler.add(
    MessageEvent,
    message=TextMessage
)
def handle_message(event):

    user_id = event.source.user_id
    text = event.message.text

    profile = line_bot_api.get_profile(
        user_id
    )

    display_name = profile.display_name

    create_user(
        user_id,
        display_name
    )

    update_name(
        user_id,
        display_name
    )

    # ケツポイント追加

    if text == "ケツ":

        total, current = add_point(
            user_id
        )

        reply = (
            "🍑 ケツポイント +1\n\n"
            f"所持ポイント: {current}pt\n"
            f"累計ポイント: {total}pt"
        )

    # ポイント確認

    elif text == "ポイント":

        user = get_user(user_id)

        reply = (
            "📊 ポイント情報\n\n"
            f"名前: {user[1]}\n"
            f"所持ポイント: {user[3]}pt\n"
            f"累計ポイント: {user[2]}pt\n"
            f"消費回数: {user[4]}回"
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
            name = row[0]
            point = row[1]

            msg += (
                f"{i}位 "
                f"{name} "
                f"{point}pt\n"
            )

        reply = msg

    else:

        reply = (
            "使えるコマンド\n\n"
            "ケツ\n"
            "ポイント\n"
            "消費\n"
            "ランキング"
        )

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply)
    )
