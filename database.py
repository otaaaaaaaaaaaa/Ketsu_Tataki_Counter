
import os
from datetime import datetime

from supabase import create_client


supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)


# =====================================
# 共通処理
# =====================================

def get_one(table, **conditions):

    query = (
        supabase.table(table)
        .select("*")
    )

    for key, value in conditions.items():
        query = query.eq(key, value)

    result = query.limit(1).execute()

    if result.data:
        return result.data[0]

    return None


# =====================================
# ユーザー
# =====================================

def get_user(user_id):

    return get_one(
        "users",
        user_id=user_id
    )


def get_user_by_name(name):

    return get_one(
        "users",
        name=name
    )


def get_all_names():

    result = (
        supabase.table("users")
        .select("name")
        .execute()
    )

    return [
        row["name"]
        for row in result.data
    ]


def create_user(user_id, name):

    existing = get_user(user_id)

    if existing:
        return existing

    result = (
        supabase.table("users")
        .insert({
            "user_id": user_id,
            "name": name,
            "total_points": 0,
            "current_points": 0,
            "used_count": 0,
            "oni_count": 0
        })
        .execute()
    )

    if result.data:
        return result.data[0]

    return None


def update_user(
    user_id,
    total_points,
    current_points,
    used_count
):

    (
        supabase.table("users")
        .update({
            "total_points": total_points,
            "current_points": current_points,
            "used_count": used_count
        })
        .eq("user_id", user_id)
        .execute()
    )


# =====================================
# ポイント譲渡
# =====================================

def transfer_points(
    sender_id,
    receiver_name,
    amount
):

    sender = get_user(sender_id)

    receiver = get_user_by_name(receiver_name)

    if not sender:
        return False, "送信者が見つかりません"

    if not receiver:
        return False, "ユーザーが見つかりません"

    if amount <= 0:
        return False, "1以上を入力してください"

    if sender["current_points"] < amount:
        return False, "ポイント不足"

    update_user(
        sender_id,
        sender["total_points"],
        sender["current_points"] - amount,
        sender["used_count"]
    )

    update_user(
        receiver["user_id"],
        receiver["total_points"],
        receiver["current_points"] + amount,
        receiver["used_count"]
    )

    return True, receiver


# =====================================
# ポイントランキング
# =====================================

def get_total_ranking():

    result = (
        supabase.table("users")
        .select("name,total_points")
        .order(
            "total_points",
            desc=True
        )
        .limit(10)
        .execute()
    )

    return result.data


def get_current_ranking():

    result = (
        supabase.table("users")
        .select("name,current_points")
        .order(
            "current_points",
            desc=True
        )
        .limit(10)
        .execute()
    )

    return result.data


# =====================================
# 全体ポイントリセット
# =====================================

def reset_all_points():

    (
        supabase.table("users")
        .update({
            "total_points": 0,
            "current_points": 0,
            "used_count": 0,
            "oni_count": 0
        })
        .neq("user_id", "")
        .execute()
    )


# =====================================
# 全員にポイント追加
# =====================================

def add_points_all(amount):

    if amount <= 0:
        return False

    result = (
        supabase.table("users")
        .select("*")
        .execute()
    )

    for user in result.data:

        update_user(
            user["user_id"],
            user["total_points"] + amount,
            user["current_points"] + amount,
            user["used_count"]
        )

    return True


# =====================================
# 鬼カウント
# =====================================

def add_oni_count(user_id):

    user = get_user(user_id)

    if not user:
        return 0

    count = user.get("oni_count", 0) + 1

    (
        supabase.table("users")
        .update({
            "oni_count": count
        })
        .eq("user_id", user_id)
        .execute()
    )

    return count


# =====================================
# 鬼カード
# =====================================

def get_oni_card(card_no):

    return get_one(
        "oni_cards",
        card_no=card_no
    )


def get_all_oni_cards():

    result = (
        supabase.table("oni_cards")
        .select("*")
        .order("card_no")
        .execute()
    )

    return result.data


def update_oni_card(
    card_no,
    user_id,
    name
):

    (
        supabase.table("oni_cards")
        .update({
            "current_user_id": user_id,
            "current_name": name,
            "start_time": datetime.now().isoformat()
        })
        .eq("card_no", card_no)
        .execute()
    )


def add_oni_history(
    card_no,
    user_name,
    seconds
):

    (
        supabase.table("oni_history")
        .insert({
            "card_no": card_no,
            "user_name": user_name,
            "seconds": seconds
        })
        .execute()
    )


def get_oni_ranking():

    result = (
        supabase.table("oni_history")
        .select("*")
        .execute()
    )

    totals = {}

    for row in result.data:

        name = row["user_name"]
        seconds = row["seconds"]

        if name not in totals:
            totals[name] = 0

        totals[name] += seconds

    ranking = sorted(
        totals.items(),
        key=lambda x: x[1],
        reverse=True
    )

    return ranking


# =====================================
# アイテム一覧
# =====================================

def get_items():

    result = (
        supabase.table("items")
        .select("*")
        .order("item_id")
        .execute()
    )

    return result.data


def get_item(item_id):

    return get_one(
        "items",
        item_id=item_id
    )


# =====================================
# 通常アイテム所持処理
# =====================================

def give_item(
    user_id,
    item_id
):

    result = (
        supabase.table("user_items")
        .select("*")
        .eq("user_id", user_id)
        .eq("item_id", item_id)
        .execute()
    )

    if result.data:

        item = result.data[0]

        (
            supabase.table("user_items")
            .update({
                "quantity": item["quantity"] + 1
            })
            .eq("id", item["id"])
            .execute()
        )

    else:

        (
            supabase.table("user_items")
            .insert({
                "user_id": user_id,
                "item_id": item_id,
                "quantity": 1
            })
            .execute()
        )


# =====================================
# アイテム購入
# =====================================

def buy_item(
    user_id,
    item_id
):

    user = get_user(user_id)

    item = get_item(item_id)

    if not user:
        return False, "ユーザーが見つかりません"

    if not item:
        return False, "アイテムが存在しません"

    if user["current_points"] < item["price"]:
        return False, "ポイント不足"

    update_user(
        user_id,
        user["total_points"],
        user["current_points"] - item["price"],
        user["used_count"]
    )

    give_item(
        user_id,
        item_id
    )

    return True, item


# =====================================
# アイテム所持一覧
# =====================================

def get_user_items(user_id):

    result = (
        supabase.table("user_items")
        .select("*")
        .eq("user_id", user_id)
        .execute()
    )

    return result.data


# =====================================
# アイテム使用
# =====================================

def use_item(
    user_id,
    item_id
):

    result = (
        supabase.table("user_items")
        .select("*")
        .eq("user_id", user_id)
        .eq("item_id", item_id)
        .execute()
    )

    if not result.data:
        return False

    item = result.data[0]

    if item["quantity"] <= 0:
        return False

    if item["quantity"] == 1:

        (
            supabase.table("user_items")
            .delete()
            .eq("id", item["id"])
            .execute()
        )

    else:

        (
            supabase.table("user_items")
            .update({
                "quantity": item["quantity"] - 1
            })
            .eq("id", item["id"])
            .execute()
        )

    return True


# =====================================
# ルーム共通処理
# =====================================

def _convert_room_id(room_id):

    try:
        return int(room_id)
    except (TypeError, ValueError):
        return None


def _format_room(room):

    if not room:
        return None

    room_id = room["room_id"]

    return {
        **room,
        "room_name": f"ルーム{room_id}",
        "status": (
            "waiting"
            if room.get("is_active", True)
            else "closed"
        )
    }


# =====================================
# ルーム作成
# =====================================

def create_room(
    room_id,
    room_name,
    admin_user_id
):

    room_id = _convert_room_id(room_id)

    if room_id is None:
        return None

    user = get_user(admin_user_id)

    if not user:
        return None

    existing = get_room_by_id(room_id)

    if existing:
        return None

    try:

        result = (
            supabase.table("rooms")
            .insert({
                "room_id": room_id,
                "owner_user_id": admin_user_id,
                "is_active": True
            })
            .execute()
        )

        if not result.data:
            return None

        # 作成者を参加者に登録
        (
            supabase.table("room_members")
            .insert({
                "room_id": room_id,
                "user_id": admin_user_id
            })
            .execute()
        )

        # ルーム専用ポイントを初期化
        (
            supabase.table("room_user_stats")
            .insert({
                "room_id": room_id,
                "user_id": admin_user_id,
                "total_points": 0,
                "current_points": 0,
                "used_count": 0,
                "oni_count": 0
            })
            .execute()
        )

        # 既存アイテム一覧をルームにコピー
        items = get_items()

        for item in items:

            (
                supabase.table("room_items")
                .insert({
                    "room_id": room_id,
                    "item_id": item["item_id"],
                    "item_name": item["item_name"],
                    "price": item["price"],
                    "description": item.get("description")
                })
                .execute()
            )

        # 既存の鬼カード設定をルームにコピー
        cards = get_all_oni_cards()

        for card in cards:

            (
                supabase.table("room_oni_cards")
                .insert({
                    "room_id": room_id,
                    "card_no": card["card_no"],
                    "current_user_id": card.get("current_user_id"),
                    "current_name": card.get("current_name"),
                    "start_time": card.get("start_time")
                })
                .execute()
            )

        # ユーザーの所属ルームを更新
        (
            supabase.table("users")
            .update({
                "active_room_id": room_id
            })
            .eq("user_id", admin_user_id)
            .execute()
        )

        return get_room_by_id(room_id)

    except Exception as e:

        print("ルーム作成エラー:", e)
        return None


# =====================================
# ルーム取得
# =====================================

def get_room_by_id(room_id):

    room_id = _convert_room_id(room_id)

    if room_id is None:
        return None

    room = get_one(
        "rooms",
        room_id=room_id
    )

    return _format_room(room)


def get_room(room_id):

    return get_room_by_id(room_id)


# =====================================
# ユーザーの現在のルーム
# =====================================

def get_user_active_room(user_id):

    user = get_user(user_id)

    if not user:
        return None

    room_id = user.get("active_room_id")

    if room_id is None:
        return None

    room = get_room_by_id(room_id)

    if not room or not room.get("is_active", True):
        return None

    return room


# =====================================
# ルーム参加
# =====================================

def join_room(
    room_id,
    user_id
):

    room_id = _convert_room_id(room_id)

    if room_id is None:
        return False, "ルームIDが正しくありません"

    room = get_room_by_id(room_id)

    if not room:
        return False, "ルームが見つかりません"

    if not room.get("is_active", True):
        return False, "このルームは終了しています"

    user = get_user(user_id)

    if not user:
        return False, "ユーザー登録がありません"

    active_room_id = user.get("active_room_id")

    if active_room_id is not None:
        if int(active_room_id) != room_id:
            return False, "すでに別のルームに参加しています"

    existing = get_one(
        "room_members",
        room_id=room_id,
        user_id=user_id
    )

    if existing:
        return False, "すでに参加しています"

    try:

        (
            supabase.table("room_members")
            .insert({
                "room_id": room_id,
                "user_id": user_id
            })
            .execute()
        )

        # ルーム専用ポイントを作成
        stats = get_one(
            "room_user_stats",
            room_id=room_id,
            user_id=user_id
        )

        if not stats:

            (
                supabase.table("room_user_stats")
                .insert({
                    "room_id": room_id,
                    "user_id": user_id,
                    "total_points": 0,
                    "current_points": 0,
                    "used_count": 0,
                    "oni_count": 0
                })
                .execute()
            )

        # 所属ルームを更新
        (
            supabase.table("users")
            .update({
                "active_room_id": room_id
            })
            .eq("user_id", user_id)
            .execute()
        )

        return True, room

    except Exception as e:

        print("ルーム参加エラー:", e)
        return False, "参加処理に失敗しました"


# =====================================
# ルーム退出
# =====================================

def leave_room(
    room_id,
    user_id
):

    room_id = _convert_room_id(room_id)

    if room_id is None:
        return False, "ルームIDが正しくありません"

    room = get_room_by_id(room_id)

    if not room:
        return False, "ルームが見つかりません"

    member = get_one(
        "room_members",
        room_id=room_id,
        user_id=user_id
    )

    if not member:
        return False, "このルームに参加していません"

    try:

        (
            supabase.table("room_members")
            .delete()
            .eq("room_id", room_id)
            .eq("user_id", user_id)
            .execute()
        )

        (
            supabase.table("users")
            .update({
                "active_room_id": None
            })
            .eq("user_id", user_id)
            .eq("active_room_id", room_id)
            .execute()
        )

        return True, "退出しました"

    except Exception as e:

        print("ルーム退出エラー:", e)
        return False, "退出処理に失敗しました"


# =====================================
# ルーム参加者一覧
# =====================================

def get_room_members(room_id):

    room_id = _convert_room_id(room_id)

    if room_id is None:
        return []

    result = (
        supabase.table("room_members")
        .select("user_id,joined_at")
        .eq("room_id", room_id)
        .execute()
    )

    members = []

    for row in result.data:

        user = get_user(row["user_id"])

        if not user:
            continue

        members.append({
            "user_id": row["user_id"],
            "name": user["name"],
            "joined_at": row.get("joined_at")
        })

    return members


# =====================================
# 試合開始
# =====================================

def start_match(room_id):

    room_id = _convert_room_id(room_id)

    if room_id is None:
        return False, "ルームIDが正しくありません"

    room = get_room_by_id(room_id)

    if not room or not room.get("is_active", True):
        return False, "ルームが見つかりません"

    # すでに進行中の試合があるか確認
    active_match = get_active_match(room_id)

    if active_match:
        return False, "すでに試合中です"

    members = get_room_members(room_id)

    if len(members) < 2:
        return False, "試合には2人以上必要です"

    try:

        result = (
            supabase.table("matches")
            .insert({
                "room_id": room_id,
                "status": "playing",
                "started_at": datetime.now().isoformat()
            })
            .execute()
        )

        if not result.data:
            return False, "試合を開始できませんでした"

        match = result.data[0]
        match_id = match["id"]

        # 各参加者の試合開始時点のポイントを記録
        for member in members:

            user_id = member["user_id"]

            stats = get_one(
                "room_user_stats",
                room_id=room_id,
                user_id=user_id
            )

            starting_points = (
                stats["current_points"]
                if stats
                else 0
            )

            (
                supabase.table("match_player_stats")
                .insert({
                    "match_id": match_id,
                    "room_id": room_id,
                    "user_id": user_id,
                    "match_points": 0,
                    "earned_points": 0,
                    "spent_points": 0,
                    "item_count": 0,
                    "starting_points": starting_points,
                    "ending_points": starting_points
                })
                .execute()
            )

        return True, match

    except Exception as e:

        print("試合開始エラー:", e)
        return False, "試合開始処理に失敗しました"


# =====================================
# 進行中の試合取得
# =====================================

def get_active_match(room_id):

    room_id = _convert_room_id(room_id)

    if room_id is None:
        return None

    result = (
        supabase.table("matches")
        .select("*")
        .eq("room_id", room_id)
        .eq("status", "playing")
        .order("id", desc=True)
        .limit(1)
        .execute()
    )

    if result.data:
        return result.data[0]

    return None


# =====================================
# 試合終了
# =====================================

def finish_match(room_id):

    room_id = _convert_room_id(room_id)

    if room_id is None:
        return False, "ルームIDが正しくありません"

    match = get_active_match(room_id)

    if not match:
        return False, "進行中の試合がありません"

    try:

        result = (
            supabase.table("matches")
            .update({
                "status": "finished",
                "ended_at": datetime.now().isoformat()
            })
            .eq("id", match["id"])
            .execute()
        )

        # 試合終了時のポイントを保存
        stats_result = (
            supabase.table("match_player_stats")
            .select("*")
            .eq("match_id", match["id"])
            .execute()
        )

        for row in stats_result.data:

            room_stats = get_one(
                "room_user_stats",
                room_id=room_id,
                user_id=row["user_id"]
            )

            ending_points = (
                room_stats["current_points"]
                if room_stats
                else 0
            )

            (
                supabase.table("match_player_stats")
                .update({
                    "ending_points": ending_points
                })
                .eq("id", row["id"])
                .execute()
            )

        return True, match

    except Exception as e:

        print("試合終了エラー:", e)
        return False, "試合終了処理に失敗しました"


# =====================================
# 試合結果取得
# =====================================

def get_match_result(room_id):

    room_id = _convert_room_id(room_id)

    if room_id is None:
        return None

    result = (
        supabase.table("matches")
        .select("*")
        .eq("room_id", room_id)
        .eq("status", "finished")
        .order("id", desc=True)
        .limit(1)
        .execute()
    )

    if not result.data:
        return None

    match = result.data[0]

    stats_result = (
        supabase.table("match_player_stats")
        .select("*")
        .eq("match_id", match["id"])
        .execute()
    )

    ranking = []

    for row in stats_result.data:

        user = get_user(row["user_id"])

        ranking.append({
            "user_id": row["user_id"],
            "name": user["name"] if user else "不明",
            "match_points": row["match_points"],
            "earned_points": row["earned_points"],
            "spent_points": row["spent_points"],
            "item_count": row["item_count"],
            "starting_points": row["starting_points"],
            "ending_points": row["ending_points"]
        })

    ranking.sort(
        key=lambda x: x["match_points"],
        reverse=True
    )

    # アイテム使用数を集計
    item_result = (
        supabase.table("match_item_usage")
        .select("user_id,item_name")
        .eq("match_id", match["id"])
        .execute()
    )

    item_totals = {}

    for row in item_result.data:

        user_id = row["user_id"]
        user = get_user(user_id)

        name = user["name"] if user else "不明"

        item_totals[name] = item_totals.get(name, 0) + 1

    item_stats = [
        {
            "name": name,
            "item_count": count
        }
        for name, count in item_totals.items()
    ]

    item_stats.sort(
        key=lambda x: x["item_count"],
        reverse=True
    )

    return {
        "match_id": match["id"],
        "room_id": room_id,
        "started_at": match["started_at"],
        "ended_at": match["ended_at"],
        "ranking": ranking,
        "item_stats": item_stats
    }


# =====================================
# ルームランキング
# =====================================

def get_room_ranking(room_id):

    result = get_match_result(room_id)

    if not result:
        return []

    return [
        {
            "name": row["name"],
            "match_points": row["match_points"]
        }
        for row in result["ranking"]
    ]


# =====================================
# ルーム内ユーザー情報
# =====================================

def get_room_user(
    room_id,
    user_id
):

    room_id = _convert_room_id(room_id)

    if room_id is None:
        return None

    stats = get_one(
        "room_user_stats",
        room_id=room_id,
        user_id=user_id
    )

    if not stats:
        return None

    match = get_active_match(room_id)

    if not match:
        result = get_match_result(room_id)

        if result:
            match_id = result["match_id"]
        else:
            match_id = None
    else:
        match_id = match["id"]

    match_stats = None

    if match_id:

        match_stats = get_one(
            "match_player_stats",
            match_id=match_id,
            user_id=user_id
        )

    return {
        "current_points": stats["current_points"],
        "total_points": stats["total_points"],
        "match_points": (
            match_stats["match_points"]
            if match_stats else 0
        ),
        "spent_points": (
            match_stats["spent_points"]
            if match_stats else 0
        ),
        "item_count": (
            match_stats["item_count"]
            if match_stats else 0
        )
    }


# =====================================
# 再戦準備
# =====================================

def reset_room_for_rematch(room_id):

    room_id = _convert_room_id(room_id)

    if room_id is None:
        return False, "ルームIDが正しくありません"

    room = get_room_by_id(room_id)

    if not room:
        return False, "ルームが見つかりません"

    if not room.get("is_active", True):
        return False, "このルームは終了しています"

    if get_active_match(room_id):
        return False, "試合中は再戦準備できません"

    return True, "再戦できます"


# =====================================
# ルーム解散
# =====================================

def delete_room(room_id):

    room_id = _convert_room_id(room_id)

    if room_id is None:
        return False, "ルームIDが正しくありません"

    room = get_room_by_id(room_id)

    if not room:
        return False, "ルームが見つかりません"

    if get_active_match(room_id):
        return False, "試合中は解散できません"

    try:

        # 参加者の所属ルームを解除
        (
            supabase.table("users")
            .update({
                "active_room_id": None
            })
            .eq("active_room_id", room_id)
            .execute()
        )

        # ルームを削除
        # 外部キーのON DELETE CASCADEにより
        # 関連データも削除される
        (
            supabase.table("rooms")
            .delete()
            .eq("room_id", room_id)
            .execute()
        )

        return True, "ルームを解散しました"

    except Exception as e:

        print("ルーム解散エラー:", e)
        return False, "ルーム解散に失敗しました"


# =====================================
# ルーム内アイテム取得
# =====================================

def get_room_item(
    room_id,
    item_id
):

    room_id = _convert_room_id(room_id)

    if room_id is None:
        return None

    return get_one(
        "room_items",
        room_id=room_id,
        item_id=item_id
    )


def get_room_items(room_id):

    room_id = _convert_room_id(room_id)

    if room_id is None:
        return []

    result = (
        supabase.table("room_items")
        .select("*")
        .eq("room_id", room_id)
        .order("item_id")
        .execute()
    )

    return result.data


# =====================================
# ルーム内ポイント取得・更新
# =====================================

def get_room_user_stats(
    room_id,
    user_id
):

    room_id = _convert_room_id(room_id)

    if room_id is None:
        return None

    return get_one(
        "room_user_stats",
        room_id=room_id,
        user_id=user_id
    )


def update_room_user_stats(
    room_id,
    user_id,
    total_points,
    current_points,
    used_count,
    oni_count=None
):

    room_id = _convert_room_id(room_id)

    if room_id is None:
        return False

    data = {
        "total_points": total_points,
        "current_points": current_points,
        "used_count": used_count
    }

    if oni_count is not None:
        data["oni_count"] = oni_count

    result = (
        supabase.table("room_user_stats")
        .update(data)
        .eq("room_id", room_id)
        .eq("user_id", user_id)
        .execute()
    )

    return bool(result.data)


# =====================================
# 試合中ポイント追加
# =====================================

def add_match_points(
    room_id,
    user_id,
    amount,
    reason=""
):

    room_id = _convert_room_id(room_id)

    if room_id is None:
        return False, "ルームIDが正しくありません"

    if not isinstance(amount, int) or amount <= 0:
        return False, "追加ポイントは1以上にしてください"

    match = get_active_match(room_id)

    if not match:
        return False, "試合中ではありません"

    member = get_one(
        "room_members",
        room_id=room_id,
        user_id=user_id
    )

    if not member:
        return False, "このルームの参加者ではありません"

    stats = get_room_user_stats(
        room_id,
        user_id
    )

    if not stats:
        return False, "ルームのポイント情報がありません"

    match_stats = get_one(
        "match_player_stats",
        match_id=match["id"],
        user_id=user_id
    )

    if not match_stats:
        return False, "試合参加情報がありません"

    new_total = stats["total_points"] + amount
    new_current = stats["current_points"] + amount

    # ルーム内ポイントを更新
    update_room_user_stats(
        room_id,
        user_id,
        new_total,
        new_current,
        stats["used_count"],
        stats["oni_count"]
    )

    # 試合中の獲得ポイントを更新
    new_earned = match_stats["earned_points"] + amount

    (
        supabase.table("match_player_stats")
        .update({
            "earned_points": new_earned,

            # ランキングは試合中に獲得したポイントで計算
            "match_points": new_earned,

            "ending_points": new_current
        })
        .eq("id", match_stats["id"])
        .execute()
    )

    return True, {
        "current_points": new_current,
        "earned_points": new_earned,
        "reason": reason
    }


# =====================================
# 試合中ポイント消費
# =====================================

def consume_match_points(
    room_id,
    user_id,
    amount,
    reason=""
):

    room_id = _convert_room_id(room_id)

    if room_id is None:
        return False, "ルームIDが正しくありません"

    if not isinstance(amount, int) or amount <= 0:
        return False, "消費ポイントは1以上にしてください"

    match = get_active_match(room_id)

    if not match:
        return False, "試合中ではありません"

    member = get_one(
        "room_members",
        room_id=room_id,
        user_id=user_id
    )

    if not member:
        return False, "このルームの参加者ではありません"

    stats = get_room_user_stats(
        room_id,
        user_id
    )

    if not stats:
        return False, "ポイント情報がありません"

    if stats["current_points"] < amount:
        return False, "ポイント不足です"

    match_stats = get_one(
        "match_player_stats",
        match_id=match["id"],
        user_id=user_id
    )

    if not match_stats:
        return False, "試合参加情報がありません"

    new_current = stats["current_points"] - amount
    new_used = stats["used_count"] + 1

    # ルーム内ポイントを更新
    update_room_user_stats(
        room_id,
        user_id,
        stats["total_points"],
        new_current,
        new_used,
        stats["oni_count"]
    )

    # 試合中の消費ポイントを記録
    new_spent = match_stats["spent_points"] + amount

    (
        supabase.table("match_player_stats")
        .update({
            "spent_points": new_spent,
            "ending_points": new_current
        })
        .eq("id", match_stats["id"])
        .execute()
    )

    return True, {
        "current_points": new_current,
        "spent_points": new_spent,
        "reason": reason
    }


# =====================================
# ルーム内アイテム所持数
# =====================================

def give_room_item(
    room_id,
    user_id,
    item_id
):

    room_id = _convert_room_id(room_id)

    if room_id is None:
        return False

    result = (
        supabase.table("user_items")
        .select("*")
        .eq("room_id", room_id)
        .eq("user_id", user_id)
        .eq("item_id", item_id)
        .execute()
    )

    if result.data:

        item = result.data[0]

        (
            supabase.table("user_items")
            .update({
                "quantity": item["quantity"] + 1
            })
            .eq("id", item["id"])
            .execute()
        )

    else:

        (
            supabase.table("user_items")
            .insert({
                "room_id": room_id,
                "user_id": user_id,
                "item_id": item_id,
                "quantity": 1
            })
            .execute()
        )

    return True


def get_room_user_items(
    room_id,
    user_id
):

    room_id = _convert_room_id(room_id)

    if room_id is None:
        return []

    result = (
        supabase.table("user_items")
        .select("*")
        .eq("room_id", room_id)
        .eq("user_id", user_id)
        .execute()
    )

    return result.data


# =====================================
# ルーム内アイテム購入
# =====================================

def buy_room_item(
    room_id,
    user_id,
    item_id
):

    room_id = _convert_room_id(room_id)

    if room_id is None:
        return False, "ルームIDが正しくありません"

    item = get_room_item(
        room_id,
        item_id
    )

    if not item:
        return False, "アイテムがありません"

    stats = get_room_user_stats(
        room_id,
        user_id
    )

    if not stats:
        return False, "ポイント情報がありません"

    price = item["price"]

    if stats["current_points"] < price:
        return False, "ポイント不足です"

    match = get_active_match(room_id)

    if match:
        success, result = consume_match_points(
            room_id,
            user_id,
            price,
            f"アイテム購入：{item['item_name']}"
        )

        if not success:
            return False, result

    else:

        update_room_user_stats(
            room_id,
            user_id,
            stats["total_points"],
            stats["current_points"] - price,
            stats["used_count"],
            stats["oni_count"]
        )

    give_room_item(
        room_id,
        user_id,
        item_id
    )

    return True, item


# =====================================
# ルーム内アイテム使用
# =====================================

def use_room_item(
    room_id,
    user_id,
    item_id
):

    room_id = _convert_room_id(room_id)

    if room_id is None:
        return False

    result = (
        supabase.table("user_items")
        .select("*")
        .eq("room_id", room_id)
        .eq("user_id", user_id)
        .eq("item_id", item_id)
        .execute()
    )

    if not result.data:
        return False

    item = result.data[0]

    if item["quantity"] <= 0:
        return False

    if item["quantity"] == 1:

        (
            supabase.table("user_items")
            .delete()
            .eq("id", item["id"])
            .execute()
        )

    else:

        (
            supabase.table("user_items")
            .update({
                "quantity": item["quantity"] - 1
            })
            .eq("id", item["id"])
            .execute()
        )

    return True


# =====================================
# 試合中アイテム使用記録
# =====================================

def add_match_item_usage(
    room_id,
    user_id,
    item_id
):

    room_id = _convert_room_id(room_id)

    if room_id is None:
        return False

    match = get_active_match(room_id)

    if not match:
        return False

    item = get_room_item(
        room_id,
        item_id
    )

    item_name = (
        item["item_name"]
        if item
        else "不明なアイテム"
    )

    try:

        (
            supabase.table("match_item_usage")
            .insert({
                "match_id": match["id"],
                "room_id": room_id,
                "user_id": user_id,
                "item_id": item_id,
                "item_name": item_name
            })
            .execute()
        )

        stats = get_one(
            "match_player_stats",
            match_id=match["id"],
            user_id=user_id
        )

        if stats:

            (
                supabase.table("match_player_stats")
                .update({
                    "item_count": stats["item_count"] + 1
                })
                .eq("id", stats["id"])
                .execute()
            )

        return True

    except Exception as e:

        print("アイテム使用記録エラー:", e)
        return False


# =====================================
# ルームに所属している場合のアイテム処理
# =====================================

# 既存main.pyとの互換性を保つため、
# ルーム参加中はルーム専用アイテムを使う。


def buy_item(
    user_id,
    item_id
):

    room = get_user_active_room(user_id)

    if room:

        return buy_room_item(
            room["room_id"],
            user_id,
            item_id
        )

    # ルームに所属していない場合は通常処理
    user = get_user(user_id)
    item = get_item(item_id)

    if not user:
        return False, "ユーザーが見つかりません"

    if not item:
        return False, "アイテムが存在しません"

    if user["current_points"] < item["price"]:
        return False, "ポイント不足"

    update_user(
        user_id,
        user["total_points"],
        user["current_points"] - item["price"],
        user["used_count"]
    )

    give_item(user_id, item_id)

    return True, item


def get_user_items(user_id):

    room = get_user_active_room(user_id)

    if room:

        return get_room_user_items(
            room["room_id"],
            user_id
        )

    result = (
        supabase.table("user_items")
        .select("*")
        .eq("user_id", user_id)
        .is_("room_id", "null")
        .execute()
    )

    return result.data


def use_item(
    user_id,
    item_id
):

    room = get_user_active_room(user_id)

    if room:

        success = use_room_item(
            room["room_id"],
            user_id,
            item_id
        )

        if success and get_active_match(room["room_id"]):
            add_match_item_usage(
                room["room_id"],
                user_id,
                item_id
            )

        return success

    result = (
        supabase.table("user_items")
        .select("*")
        .eq("user_id", user_id)
        .eq("item_id", item_id)
        .is_("room_id", "null")
        .execute()
    )

    if not result.data:
        return False

    item = result.data[0]

    if item["quantity"] <= 0:
        return False

    if item["quantity"] == 1:

        (
            supabase.table("user_items")
            .delete()
            .eq("id", item["id"])
            .execute()
        )

    else:

        (
            supabase.table("user_items")
            .update({
                "quantity": item["quantity"] - 1
            })
            .eq("id", item["id"])
            .execute()
        )

    return True


# =====================================
# ルーム内鬼カード
# =====================================

def get_oni_card(card_no):

    # 既存main.pyとの互換性
    # ルーム参加中はルーム専用カードを取得
    # card_noは既存テーブルの型に合わせる

    room_id = None

    # 現在のルームにいるユーザーを特定できないため、
    # ユーザーIDを受け取る版は get_room_oni_card を使う
    return get_one(
        "oni_cards",
        card_no=card_no
    )


def get_room_oni_card(
    room_id,
    card_no
):

    room_id = _convert_room_id(room_id)

    if room_id is None:
        return None

    return get_one(
        "room_oni_cards",
        room_id=room_id,
        card_no=card_no
    )


def update_room_oni_card(
    room_id,
    card_no,
    user_id,
    name
):

    room_id = _convert_room_id(room_id)

    if room_id is None:
        return False

    (
        supabase.table("room_oni_cards")
        .update({
            "current_user_id": user_id,
            "current_name": name,
            "start_time": datetime.now().isoformat()
        })
        .eq("room_id", room_id)
        .eq("card_no", card_no)
        .execute()
    )

    return True


# =====================================
# ルーム内鬼回数
# =====================================

def add_oni_count(user_id):

    room = get_user_active_room(user_id)

    if not room:
        user = get_user(user_id)

        if not user:
            return 0

        count = user.get("oni_count", 0) + 1

        (
            supabase.table("users")
            .update({"oni_count": count})
            .eq("user_id", user_id)
            .execute()
        )

        return count

    stats = get_room_user_stats(
        room["room_id"],
        user_id
    )

    if not stats:
        return 0

    count = stats["oni_count"] + 1

    update_room_user_stats(
        room["room_id"],
        user_id,
        stats["total_points"],
        stats["current_points"],
        stats["used_count"],
        count
    )

    return count


# =====================================
# ルーム別鬼履歴
# =====================================

def add_oni_history(
    card_no,
    user_name,
    seconds
):

    # 現在のルームを特定するユーザーIDが
    # 引数に含まれていないため、従来の履歴に保存
    (
        supabase.table("oni_history")
        .insert({
            "card_no": card_no,
            "user_name": user_name,
            "seconds": seconds
        })
        .execute()
    )


# =====================================
# 全データリセット
# =====================================

def reset_all_data():

    reset_all_points()

    tables = [
        "user_items",
        "oni_history"
    ]

    for table in tables:

        (
            supabase.table(table)
            .delete()
            .neq("id", -1)
            .execute()
        )

    return True


# =====================================
# ルーム解散処理の安全版
# =====================================

def delete_room(room_id):

    room_id = _convert_room_id(room_id)

    if room_id is None:
        return False, "ルームIDが正しくありません"

    room = get_room_by_id(room_id)

    if not room:
        return False, "ルームが見つかりません"

    if get_active_match(room_id):
        return False, "試合中は解散できません"

    try:

        # 所属ルームを解除
        (
            supabase.table("users")
            .update({
                "active_room_id": None
            })
            .eq("active_room_id", room_id)
            .execute()
        )

        # ルームに紐づくアイテム所持情報
        (
            supabase.table("user_items")
            .delete()
            .eq("room_id", room_id)
            .execute()
        )

        # 鬼履歴
        (
            supabase.table("oni_history")
            .delete()
            .eq("room_id", room_id)
            .execute()
        )

        # 試合履歴の子テーブルは matches の削除前に消す
        matches = (
            supabase.table("matches")
            .select("id")
            .eq("room_id", room_id)
            .execute()
        )

        for match in matches.data:

            (
                supabase.table("match_item_usage")
                .delete()
                .eq("match_id", match["id"])
                .execute()
            )

            (
                supabase.table("match_player_stats")
                .delete()
                .eq("match_id", match["id"])
                .execute()
            )

        (
            supabase.table("matches")
            .delete()
            .eq("room_id", room_id)
            .execute()
        )

        # ルーム関連テーブル
        for table in [
            "room_members",
            "room_user_stats",
            "room_items",
            "room_oni_cards"
        ]:

            (
                supabase.table(table)
                .delete()
                .eq("room_id", room_id)
                .execute()
            )

        # 最後にルーム本体を削除
        (
            supabase.table("rooms")
            .delete()
            .eq("room_id", room_id)
            .execute()
        )

        return True, "ルームを解散しました"

    except Exception as e:

        print("ルーム解散エラー:", e)
        return False, "ルーム解散に失敗しました"
