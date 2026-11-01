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

    if result.data:
        return result.data[0]

    return None


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
        "oni_count": 0
    }).execute()


def update_user(
    user_id,
    total_points,
    current_points,
    used_count
):
    supabase.table("users").update({
        "total_points": total_points,
        "current_points": current_points,
        "used_count": used_count
    }).eq(
        "user_id",
        user_id
    ).execute()


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

    receiver = get_user_by_name(receiver_name)

    if not receiver:
        return False, "ユーザーが見つかりません"

    if amount <= 0:
        return False, "1以上を入力してください"

    if sender["current_points"] < amount:
        return False, "ポイント不足"

    # 送信者のポイントを減らす
    supabase.table("users").update({
        "current_points":
            sender["current_points"] - amount
    }).eq(
        "user_id",
        sender_id
    ).execute()

    # 受信者のポイントを増やす
    supabase.table("users").update({
        "current_points":
            receiver["current_points"] + amount
    }).eq(
        "user_id",
        receiver["user_id"]
    ).execute()

    return True, receiver


# ========================================
# ランキング
# ========================================

def get_total_ranking():
    result = (
        supabase.table("users")
        .select("name,total_points")
        .order("total_points", desc=True)
        .limit(10)
        .execute()
    )

    return result.data


def get_current_ranking():
    result = (
        supabase.table("users")
        .select("name,current_points")
        .order("current_points", desc=True)
        .limit(10)
        .execute()
    )

    return result.data


# ========================================
# ポイントのみリセット
# ========================================

def reset_all_points():
    supabase.table("users").update({
        "total_points": 0,
        "current_points": 0,
        "used_count": 0,
        "oni_count": 0
    }).neq(
        "user_id",
        ""
    ).execute()


# ========================================
# 鬼になった回数
# ========================================

def add_oni_count(user_id):
    user = get_user(user_id)

    if not user:
        return None

    count = (user.get("oni_count") or 0) + 1

    supabase.table("users").update({
        "oni_count": count
    }).eq(
        "user_id",
        user_id
    ).execute()

    return count


# ========================================
# 鬼カード
# ========================================

def get_oni_card(card_no):
    result = (
        supabase.table("oni_cards")
        .select("*")
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
    supabase.table("oni_cards").update({
        "current_user_id": user_id,
        "current_name": name,
        "start_time": datetime.now().isoformat()
    }).eq(
        "card_no",
        card_no
    ).execute()


def get_all_oni_cards():
    result = (
        supabase.table("oni_cards")
        .select("*")
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
        "card_no": card_no,
        "user_name": user_name,
        "seconds": seconds
    }).execute()


def get_oni_ranking():
    result = (
        supabase.table("oni_history")
        .select("*")
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
        supabase.table("items")
        .select("*")
        .order("item_id")
        .execute()
    )

    return result.data


def get_item(item_id):
    result = (
        supabase.table("items")
        .select("*")
        .eq("item_id", item_id)
        .execute()
    )

    if result.data:
        return result.data[0]

    return None


# ========================================
# アイテム付与
# ========================================

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

        supabase.table("user_items").update({
            "quantity": item["quantity"] + 1
        }).eq(
            "id",
            item["id"]
        ).execute()

    else:
        supabase.table("user_items").insert({
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
    result = (
        supabase.table("user_items")
        .select("*")
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
    result = (
        supabase.table("users")
        .select("*")
        .execute()
    )

    for user in result.data:
        supabase.table("users").update({
            "current_points":
                user["current_points"] + amount,
            "total_points":
                user["total_points"] + amount
        }).eq(
            "user_id",
            user["user_id"]
        ).execute()


# ========================================
# 全データリセット
# ========================================

def reset_all_data():
    """
    全ユーザーのポイント、鬼の記録、
    所持アイテムをリセットする。

    ユーザー登録とショップの商品一覧は維持する。
    """

    # ① ポイントとカウントをリセット
    supabase.table("users").update({
        "total_points": 0,
        "current_points": 0,
        "used_count": 0,
        "oni_count": 0
    }).neq(
        "user_id",
        ""
    ).execute()

    # ② 鬼カード1〜5の登録情報をリセット
    supabase.table("oni_cards").update({
        "current_user_id": None,
        "current_name": None,
        "start_time": None
    }).in_(
        "card_no",
        [1, 2, 3, 4, 5]
    ).execute()

    # ③ 鬼の履歴をすべて削除
    supabase.table("oni_history").delete().gte(
        "card_no",
        1
    ).execute()

    # ④ 全ユーザーの所持アイテムを削除
    supabase.table("user_items").delete().neq(
        "user_id",
        ""
    ).execute()
