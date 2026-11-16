
import os
from datetime import datetime

from supabase import create_client


# ========================================
# Supabase 接続
# ========================================

supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)

DEFAULT_ROOM_ID = 10000000


# ========================================
# ルーム関連
# ========================================

def get_active_room_id(user_id):
    user = (
        supabase.table("users")
        .select("active_room_id")
        .eq("user_id", user_id)
        .execute()
    )

    if user.data and user.data[0].get("active_room_id"):
        return user.data[0]["active_room_id"]

    return DEFAULT_ROOM_ID


def get_room(room_id):
    result = (
        supabase.table("rooms")
        .select("*")
        .eq("room_id", room_id)
        .eq("is_active", True)
        .execute()
    )

    if result.data:
        return result.data[0]

    return None


def room_exists(room_id):
    return get_room(room_id) is not None


def create_room(room_id, owner_user_id):
    if room_exists(room_id):
        return False

    owner = get_user(owner_user_id)

    if not owner:
        return False

    supabase.table("rooms").insert({
        "room_id": room_id,
        "owner_user_id": owner_user_id,
        "is_active": True
    }).execute()

    supabase.table("room_members").insert({
        "room_id": room_id,
        "user_id": owner_user_id
    }).execute()

    supabase.table("users").update({
        "active_room_id": room_id
    }).eq(
        "user_id",
        owner_user_id
    ).execute()

    supabase.table("room_user_stats").insert({
        "room_id": room_id,
        "user_id": owner_user_id,
        "total_points": 0,
        "current_points": 0,
        "used_count": 0,
        "oni_count": 0
    }).execute()

    # ショップの商品をコピー
    items = (
        supabase.table("items")
        .select("*")
        .execute()
    )

    for item in items.data:
        supabase.table("room_items").insert({
            "room_id": room_id,
            "item_id": item["item_id"],
            "item_name": item["item_name"],
            "price": item["price"],
            "description": item.get("description")
        }).execute()

    # 鬼カード1〜5を作成
    for card_no in range(1, 6):
        supabase.table("room_oni_cards").insert({
            "room_id": room_id,
            "card_no": card_no,
            "current_user_id": None,
            "current_name": None,
            "start_time": None
        }).execute()

    return True


def join_room(user_id, room_id):
    room = get_room(room_id)

    if not room:
        return False

    user = get_user(user_id)

    if not user:
        return False

    membership = (
        supabase.table("room_members")
        .select("*")
        .eq("room_id", room_id)
        .eq("user_id", user_id)
        .execute()
    )

    if not membership.data:
        supabase.table("room_members").insert({
            "room_id": room_id,
            "user_id": user_id
        }).execute()

    # ポイントデータがなければ作成
    stats = (
        supabase.table("room_user_stats")
        .select("*")
        .eq("room_id", room_id)
        .eq("user_id", user_id)
        .execute()
    )

    if not stats.data:
        supabase.table("room_user_stats").insert({
            "room_id": room_id,
            "user_id": user_id,
            "total_points": 0,
            "current_points": 0,
            "used_count": 0,
            "oni_count": 0
        }).execute()

    supabase.table("users").update({
        "active_room_id": room_id
    }).eq(
        "user_id",
        user_id
    ).execute()

    return True


def get_room_members(room_id):
    result = (
        supabase.table("room_members")
        .select("user_id")
        .eq("room_id", room_id)
        .execute()
    )

    return result.data


def get_user_rooms(user_id):
    result = (
        supabase.table("room_members")
        .select("room_id")
        .eq("user_id", user_id)
        .execute()
    )

    return result.data


def get_room_owner(room_id):
    room = get_room(room_id)

    if room:
        return room.get("owner_user_id")

    return None


def delete_room(room_id, owner_user_id):
    room = get_room(room_id)

    if not room:
        return False

    if room.get("owner_user_id") != owner_user_id:
        return False

    supabase.table("rooms").update({
        "is_active": False
    }).eq(
        "room_id",
        room_id
    ).execute()

    return True


# ========================================
# ユーザー関連
# ========================================

def get_user(user_id):
    result = (
        supabase.table("users")
        .select("*")
        .eq("user_id", user_id)
        .execute()
    )

    if not result.data:
        return None

    user = result.data[0]

    room_id = user.get("active_room_id") or DEFAULT_ROOM_ID

    stats = (
        supabase.table("room_user_stats")
        .select("*")
        .eq("room_id", room_id)
        .eq("user_id", user_id)
        .execute()
    )

    if stats.data:
        user.update(stats.data[0])
    else:
        user.update({
            "total_points": 0,
            "current_points": 0,
            "used_count": 0,
            "oni_count": 0
        })

    user["active_room_id"] = room_id

    return user


def get_user_by_name(name):
    result = (
        supabase.table("users")
        .select("*")
        .eq("name", name)
        .execute()
    )

    if result.data:
        return result.data[0]

    return None


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
    supabase.table("users").insert({
        "user_id": user_id,
        "name": name,
        "total_points": 0,
        "current_points": 0,
        "used_count": 0,
        "oni_count": 0,
        "active_room_id": DEFAULT_ROOM_ID
    }).execute()

    # 初期ルームに登録
    supabase.table("room_members").upsert({
        "room_id": DEFAULT_ROOM_ID,
        "user_id": user_id
    }).execute()

    supabase.table("room_user_stats").upsert({
        "room_id": DEFAULT_ROOM_ID,
        "user_id": user_id,
        "total_points": 0,
        "current_points": 0,
        "used_count": 0,
        "oni_count": 0
    }).execute()


def update_user(
    user_id,
    total_points,
    current_points,
    used_count
):
    room_id = get_active_room_id(user_id)

    supabase.table("room_user_stats").upsert({
        "room_id": room_id,
        "user_id": user_id,
        "total_points": total_points,
        "current_points": current_points,
        "used_count": used_count
    }).execute()


# ========================================
# ポイント移動
# ========================================

def transfer_points(
    sender_id,
    receiver_name,
    amount
):
    sender = get_user(sender_id)

    if not sender:
        return False, "送信者が見つかりません"

    room_id = sender["active_room_id"]

    receiver = get_user_by_name(receiver_name)

    if not receiver:
        return False, "ユーザーが見つかりません"

    receiver_id = receiver["user_id"]

    # 同じルームにいるか確認
    membership = (
        supabase.table("room_members")
        .select("*")
        .eq("room_id", room_id)
        .eq("user_id", receiver_id)
        .execute()
    )

    if not membership.data:
        return False, "相手は同じルームに参加していません"

    receiver_stats = (
        supabase.table("room_user_stats")
        .select("*")
        .eq("room_id", room_id)
        .eq("user_id", receiver_id)
        .execute()
    )

    if not receiver_stats.data:
        return False, "相手のポイント情報がありません"

    receiver_data = receiver_stats.data[0]

    if amount <= 0:
        return False, "1以上を入力してください"

    if sender["current_points"] < amount:
        return False, "ポイント不足"

    # 送信者
    supabase.table("room_user_stats").update({
        "current_points":
            sender["current_points"] - amount
    }).eq(
        "room_id",
        room_id
    ).eq(
        "user_id",
        sender_id
    ).execute()

    # 受信者
    supabase.table("room_user_stats").update({
        "current_points":
            receiver_data["current_points"] + amount
    }).eq(
        "room_id",
        room_id
    ).eq(
        "user_id",
        receiver_id
    ).execute()

    return True, receiver


# ========================================
# ランキング
# ========================================

def get_total_ranking():
    room_id = DEFAULT_ROOM_ID

    result = (
        supabase.table("room_user_stats")
        .select("*")
        .eq("room_id", room_id)
        .order("total_points", desc=True)
        .limit(10)
        .execute()
    )

    ranking = []

    for row in result.data:
        user = (
            supabase.table("users")
            .select("name")
            .eq("user_id", row["user_id"])
            .execute()
        )

        if user.data:
            ranking.append({
                "name": user.data[0]["name"],
                "total_points": row["total_points"]
            })

    return ranking


def get_current_ranking():
    room_id = DEFAULT_ROOM_ID

    result = (
        supabase.table("room_user_stats")
        .select("*")
        .eq("room_id", room_id)
        .order("current_points", desc=True)
        .limit(10)
        .execute()
    )

    ranking = []

    for row in result.data:
        user = (
            supabase.table("users")
            .select("name")
            .eq("user_id", row["user_id"])
            .execute()
        )

        if user.data:
            ranking.append({
                "name": user.data[0]["name"],
                "current_points": row["current_points"]
            })

    return ranking


# ========================================
# ポイントのみリセット
# ========================================

def reset_all_points():
    room_id = DEFAULT_ROOM_ID

    supabase.table("room_user_stats").update({
        "total_points": 0,
        "current_points": 0,
        "used_count": 0,
        "oni_count": 0
    }).eq(
        "room_id",
        room_id
    ).execute()


# ========================================
# 鬼になった回数
# ========================================

def add_oni_count(user_id):
    user = get_user(user_id)

    if not user:
        return None

    room_id = user["active_room_id"]
    count = (user.get("oni_count") or 0) + 1

    supabase.table("room_user_stats").update({
        "oni_count": count
    }).eq(
        "room_id",
        room_id
    ).eq(
        "user_id",
        user_id
    ).execute()

    return count


# ========================================
# 鬼カード
# ========================================

def get_oni_card(card_no):
    result = (
        supabase.table("room_oni_cards")
        .select("*")
        .eq("room_id", DEFAULT_ROOM_ID)
        .eq("card_no", card_no)
        .execute()
    )

    if result.data:
        return result.data[0]

    return None


def update_oni_card(
    card_no,
    user_id,
    name
):
    room_id = get_active_room_id(user_id)

    supabase.table("room_oni_cards").update({
        "current_user_id": user_id,
        "current_name": name,
        "start_time": datetime.now().isoformat()
    }).eq(
        "room_id",
        room_id
    ).eq(
        "card_no",
        card_no
    ).execute()


def get_all_oni_cards():
    result = (
        supabase.table("room_oni_cards")
        .select("*")
        .eq("room_id", DEFAULT_ROOM_ID)
        .order("card_no")
        .execute()
    )

    return result.data


# ========================================
# 鬼の履歴・ランキング
# ========================================

def add_oni_history(
    card_no,
    user_name,
    seconds
):
    supabase.table("oni_history").insert({
        "room_id": DEFAULT_ROOM_ID,
        "card_no": card_no,
        "user_name": user_name,
        "seconds": seconds
    }).execute()


def get_oni_ranking():
    result = (
        supabase.table("oni_history")
        .select("*")
        .eq("room_id", DEFAULT_ROOM_ID)
        .execute()
    )

    totals = {}

    for row in result.data:
        name = row["user_name"]
        seconds = row["seconds"] or 0

        if name not in totals:
            totals[name] = 0

        totals[name] += seconds

    ranking = sorted(
        totals.items(),
        key=lambda x: x[1],
        reverse=True
    )

    return ranking


# ========================================
# アイテムショップ
# ========================================

def get_items():
    result = (
        supabase.table("room_items")
        .select("*")
        .eq("room_id", DEFAULT_ROOM_ID)
        .order("item_id")
        .execute()
    )

    items = result.data

    for item in items:
        item["name"] = item.get("item_name")

    return items


def get_item(item_id):
    result = (
        supabase.table("room_items")
        .select("*")
        .eq("room_id", DEFAULT_ROOM_ID)
        .eq("item_id", item_id)
        .execute()
    )

    if result.data:
        item = result.data[0]
        item["name"] = item.get("item_name")
        return item

    return None


# ========================================
# アイテム付与
# ========================================

def give_item(
    user_id,
    item_id
):
    room_id = get_active_room_id(user_id)

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

        supabase.table("user_items").update({
            "quantity": item["quantity"] + 1
        }).eq(
            "id",
            item["id"]
        ).execute()

    else:
        supabase.table("user_items").insert({
            "room_id": room_id,
            "user_id": user_id,
            "item_id": item_id,
            "quantity": 1
        }).execute()


# ========================================
# アイテム購入
# ========================================

def buy_item(
    user_id,
    item_id
):
    user = get_user(user_id)

    if not user:
        return False, "ユーザーが見つかりません"

    item = get_item(item_id)

    if not item:
        return False, "商品が存在しません"

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


# ========================================
# 所持アイテム取得
# ========================================

def get_user_items(user_id):
    room_id = get_active_room_id(user_id)

    result = (
        supabase.table("user_items")
        .select("*")
        .eq("room_id", room_id)
        .eq("user_id", user_id)
        .execute()
    )

    return result.data


# ========================================
# アイテム使用
# ========================================

def use_item(
    user_id,
    item_id
):
    room_id = get_active_room_id(user_id)

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
        supabase.table("user_items").delete().eq(
            "id",
            item["id"]
        ).execute()

    else:
        supabase.table("user_items").update({
            "quantity": item["quantity"] - 1
        }).eq(
            "id",
            item["id"]
        ).execute()

    return True


# ========================================
# 全ユーザーにポイントを追加
# ========================================

def add_points_all(amount):
    room_id = DEFAULT_ROOM_ID

    result = (
        supabase.table("room_user_stats")
        .select("*")
        .eq("room_id", room_id)
        .execute()
    )

    for user in result.data:
        supabase.table("room_user_stats").update({
            "current_points":
                user["current_points"] + amount,
            "total_points":
                user["total_points"] + amount
        }).eq(
            "room_id",
            room_id
        ).eq(
            "user_id",
            user["user_id"]
        ).execute()


# ========================================
# 全データリセット
# ========================================

def reset_all_data():
    """
    初期ルームのデータだけをリセットする。
    ユーザー登録とショップの商品一覧は維持する。
    """

    room_id = DEFAULT_ROOM_ID

    # ① ポイントとカウントをリセット
    supabase.table("room_user_stats").update({
        "total_points": 0,
        "current_points": 0,
        "used_count": 0,
        "oni_count": 0
    }).eq(
        "room_id",
        room_id
    ).execute()

    # ② 鬼カードをリセット
    supabase.table("room_oni_cards").update({
        "current_user_id": None,
        "current_name": None,
        "start_time": None
    }).eq(
        "room_id",
        room_id
    ).execute()

    # ③ 鬼の履歴を削除
    supabase.table("oni_history").delete().eq(
        "room_id",
        room_id
    ).execute()

    # ④ 所持アイテムを削除
    supabase.table("user_items").delete().eq(
        "room_id",
        room_id
    ).execute()
