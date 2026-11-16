
import os
from datetime import datetime, timezone

from supabase import create_client


# =====================================
# Supabase接続
# =====================================

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError(
        "SUPABASE_URL または SUPABASE_KEY が設定されていません"
    )

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)


# =====================================
# 共通処理
# =====================================

def _get_one(table, **conditions):

    query = supabase.table(table).select("*")

    for key, value in conditions.items():
        query = query.eq(key, value)

    result = query.limit(1).execute()

    if result.data:
        return result.data[0]

    return None


def _room_id(value):

    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _now():

    return datetime.now(timezone.utc).isoformat()


def _get_active_room_id(user_id):

    user = get_user(user_id)

    if not user:
        return None

    return user.get("active_room_id")


# =====================================
# ユーザー管理
# =====================================

def get_user(user_id):

    return _get_one(
        "users",
        user_id=user_id
    )


def get_user_by_name(name):

    return _get_one(
        "users",
        name=name
    )


def get_all_names():

    result = (
        supabase.table("users")
        .select("name")
        .order("name")
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

    result = (
        supabase.table("users")
        .update({
            "total_points": total_points,
            "current_points": current_points,
            "used_count": used_count
        })
        .eq("user_id", user_id)
        .execute()
    )

    return bool(result.data)


# =====================================
# 全体ポイント管理
# =====================================

def add_points_all(amount):

    if not isinstance(amount, int) or amount <= 0:
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


def reset_all_points():

    result = (
        supabase.table("users")
        .select("user_id")
        .execute()
    )

    for user in result.data:

        (
            supabase.table("users")
            .update({
                "total_points": 0,
                "current_points": 0,
                "used_count": 0,
                "oni_count": 0
            })
            .eq("user_id", user["user_id"])
            .execute()
        )

    return True


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
# ポイント譲渡
# =====================================

def transfer_points(
    sender_id,
    receiver_name,
    amount
):

    if not isinstance(amount, int) or amount <= 0:
        return False, "1以上の数字を入力してください"

    sender = get_user(sender_id)
    receiver = get_user_by_name(receiver_name)

    if not sender:
        return False, "送信者が見つかりません"

    if not receiver:
        return False, "相手が見つかりません"

    sender_room = sender.get("active_room_id")
    receiver_room = receiver.get("active_room_id")

    # ルーム所属中は同じルーム内でのみ譲渡
    if sender_room is not None or receiver_room is not None:

        if sender_room is None or receiver_room is None:
            return False, "同じルームに参加している相手にのみ譲渡できます"

        if int(sender_room) != int(receiver_room):
            return False, "別のルームの相手には譲渡できません"

        room_id = int(sender_room)

        sender_stats = get_room_user_stats(
            room_id,
            sender_id
        )

        receiver_stats = get_room_user_stats(
            room_id,
            receiver["user_id"]
        )

        if not sender_stats or not receiver_stats:
            return False, "ルームのポイント情報がありません"

        if sender_stats["current_points"] < amount:
            return False, "ポイントが不足しています"

        update_room_user_stats(
            room_id,
            sender_id,
            sender_stats["total_points"],
            sender_stats["current_points"] - amount,
            sender_stats["used_count"],
            sender_stats["oni_count"]
        )

        update_room_user_stats(
            room_id,
            receiver["user_id"],
            receiver_stats["total_points"],
            receiver_stats["current_points"] + amount,
            receiver_stats["used_count"],
            receiver_stats["oni_count"]
        )

        return True, receiver

    # ルーム外では全体ポイントを使用
    if sender["current_points"] < amount:
        return False, "ポイントが不足しています"

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
# 鬼回数
# =====================================

def add_oni_count(user_id):

    room_id = _get_active_room_id(user_id)

    if room_id is not None:

        stats = get_room_user_stats(
            room_id,
            user_id
        )

        if not stats:
            return 0

        new_count = stats["oni_count"] + 1

        update_room_user_stats(
            room_id,
            user_id,
            stats["total_points"],
            stats["current_points"],
            stats["used_count"],
            new_count
        )

        return new_count

    user = get_user(user_id)

    if not user:
        return 0

    new_count = user.get("oni_count", 0) + 1

    (
        supabase.table("users")
        .update({
            "oni_count": new_count
        })
        .eq("user_id", user_id)
        .execute()
    )

    return new_count


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

    return _get_one(
        "items",
        item_id=item_id
    )


# =====================================
# ルーム別アイテム一覧
# =====================================

def get_room_items(room_id):

    room_id = _room_id(room_id)

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


def get_room_item(
    room_id,
    item_id
):

    room_id = _room_id(room_id)

    if room_id is None:
        return None

    return _get_one(
        "room_items",
        room_id=room_id,
        item_id=item_id
    )


# =====================================
# 通常アイテム所持
# =====================================

def give_item(
    user_id,
    item_id
):

    existing = (
        supabase.table("user_items")
        .select("*")
        .eq("user_id", user_id)
        .eq("item_id", item_id)
        .is_("room_id", "null")
        .execute()
    )

    if existing.data:

        item = existing.data[0]

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
                "quantity": 1,
                "room_id": None
            })
            .execute()
        )

    return True


def get_user_items(user_id):

    room_id = _get_active_room_id(user_id)

    if room_id is not None:

        result = (
            supabase.table("user_items")
            .select("*")
            .eq("user_id", user_id)
            .eq("room_id", int(room_id))
            .execute()
        )

        return result.data

    result = (
        supabase.table("user_items")
        .select("*")
        .eq("user_id", user_id)
        .is_("room_id", "null")
        .execute()
    )

    return result.data


# =====================================
# アイテム購入
# =====================================

def buy_item(
    user_id,
    item_id
):

    room_id = _get_active_room_id(user_id)

    if room_id is not None:

        return buy_room_item(
            room_id,
            user_id,
            item_id
        )

    user = get_user(user_id)
    item = get_item(item_id)

    if not user:
        return False, "ユーザーが見つかりません"

    if not item:
        return False, "アイテムが存在しません"

    price = int(item["price"])

    if user["current_points"] < price:
        return False, "ポイントが不足しています"

    update_user(
        user_id,
        user["total_points"],
        user["current_points"] - price,
        user["used_count"] + 1
    )

    give_item(
        user_id,
        item_id
    )

    return True, item


# =====================================
# アイテム使用
# =====================================

def use_item(
    user_id,
    item_id
):

    room_id = _get_active_room_id(user_id)

    if room_id is not None:

        return use_room_item(
            room_id,
            user_id,
            item_id
        )

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

# ========================================
# Part2：ルーム管理・ルーム別データ
# ========================================

DEFAULT_ROOM_ID = 10000000


# ----------------------------------------
# ルーム情報
# ----------------------------------------

def get_user_active_room(user_id):
    """ユーザーが現在選択しているルームを取得"""
    return _get_active_room_id(user_id)


def get_room_by_id(room_id):
    """ルームIDからルームを取得"""
    room_id = _room_id(room_id)

    if room_id is None:
        return None

    return _get_one("rooms", room_id=room_id)


def get_room(room_id):
    """get_room_by_id の別名"""
    return get_room_by_id(room_id)


def get_room_members(room_id):
    """ルームの参加者一覧を取得"""
    room_id = _room_id(room_id)

    if room_id is None:
        return []

    result = (
        supabase.table("room_members")
        .select("user_id, joined_at")
        .eq("room_id", room_id)
        .order("joined_at")
        .execute()
    )

    members = []

    for member in result.data or []:
        user = get_user(member["user_id"])

        if user:
            members.append({
                **user,
                "joined_at": member.get("joined_at")
            })

    return members


def get_room_member_ids(room_id):
    """ルームの参加者ID一覧"""
    room_id = _room_id(room_id)

    if room_id is None:
        return []

    result = (
        supabase.table("room_members")
        .select("user_id")
        .eq("room_id", room_id)
        .execute()
    )

    return [
        row["user_id"]
        for row in (result.data or [])
    ]


def create_room(owner_user_id, room_id=None):
    """
    ルームを作成する。
    room_idを指定しない場合はランダムな8桁IDを生成する。
    """

    import random

    if not get_user(owner_user_id):
        return None

    if room_id is None:
        for _ in range(100):
            candidate = random.randint(10000000, 99999999)

            if not get_room(candidate):
                room_id = candidate
                break

        if room_id is None:
            raise RuntimeError("ルームIDを生成できませんでした")

    room_id = _room_id(room_id)

    if room_id is None:
        raise ValueError("ルームIDは数字で指定してください")

    if get_room(room_id):
        return None

    # ルーム本体
    supabase.table("rooms").insert({
        "room_id": room_id,
        "owner_user_id": owner_user_id,
        "is_active": True
    }).execute()

    # 作成者を参加させる
    supabase.table("room_members").insert({
        "room_id": room_id,
        "user_id": owner_user_id
    }).execute()

    # ルーム内ポイントを初期化
    supabase.table("room_user_stats").upsert({
        "room_id": room_id,
        "user_id": owner_user_id,
        "total_points": 0,
        "current_points": 0,
        "used_count": 0,
        "oni_count": 0
    }).execute()

    # 現在のルームを切り替える
    supabase.table("users").update({
        "active_room_id": room_id
    }).eq("user_id", owner_user_id).execute()

    # アイテム一覧を新しいルームにコピー
    global_items = (
        supabase.table("items")
        .select("*")
        .execute()
    )

    for item in global_items.data or []:
        supabase.table("room_items").upsert({
            "room_id": room_id,
            "item_id": item["item_id"],
            "item_name": item["item_name"],
            "price": item.get("price", 0),
            "description": item.get("description")
        }).execute()

    # 鬼カードを新しいルームにコピー
    global_cards = (
        supabase.table("oni_cards")
        .select("*")
        .execute()
    )

    for card in global_cards.data or []:
        supabase.table("room_oni_cards").upsert({
            "room_id": room_id,
            "card_no": card["card_no"],
            "current_user_id": None,
            "current_name": None,
            "start_time": None
        }).execute()

    return get_room(room_id)


def join_room(user_id, room_id):
    """既存ルームに参加する"""

    room_id = _room_id(room_id)

    if room_id is None:
        return False

    room = get_room(room_id)

    if not room or not room.get("is_active", True):
        return False

    if not get_user(user_id):
        return False

    # すでに別の通常ルームに参加中なら切り替えを禁止
    current_room_id = get_user_active_room(user_id)

    if (
        current_room_id
        and current_room_id != DEFAULT_ROOM_ID
        and current_room_id != room_id
    ):
        return False

    # 試合中の途中参加は禁止
    active_match = get_active_match(room_id)

    if active_match:
        return False

    supabase.table("room_members").upsert({
        "room_id": room_id,
        "user_id": user_id
    }).execute()

    # ルーム用ポイントデータがなければ初期化
    supabase.table("room_user_stats").upsert({
        "room_id": room_id,
        "user_id": user_id,
        "total_points": 0,
        "current_points": 0,
        "used_count": 0,
        "oni_count": 0
    }).execute()

    # 現在のルームを切り替える
    supabase.table("users").update({
        "active_room_id": room_id
    }).eq("user_id", user_id).execute()

    return True


def leave_room(user_id):
    """現在のルームから退出する"""

    room_id = get_user_active_room(user_id)

    if not room_id:
        return False

    room = get_room(room_id)

    if not room:
        return False

    if get_active_match(room_id):
        return False

    # ルーム管理者が退出する場合も、ルーム自体は残す
    supabase.table("room_members").delete().eq(
        "room_id", room_id
    ).eq(
        "user_id", user_id
    ).execute()

    supabase.table("users").update({
        "active_room_id": None
    }).eq("user_id", user_id).execute()

    return True


# ----------------------------------------
# ルーム別ポイント
# ----------------------------------------

def get_room_user_stats(room_id, user_id):
    room_id = _room_id(room_id)

    if room_id is None:
        return None

    return _get_one(
        "room_user_stats",
        room_id=room_id,
        user_id=user_id
    )


def update_room_user_stats(room_id, user_id, **values):
    """ルーム別ポイント情報を更新"""

    room_id = _room_id(room_id)

    if room_id is None:
        return False

    allowed = {
        "total_points",
        "current_points",
        "used_count",
        "oni_count"
    }

    update_values = {
        key: value
        for key, value in values.items()
        if key in allowed
    }

    if not update_values:
        return False

    supabase.table("room_user_stats").upsert({
        "room_id": room_id,
        "user_id": user_id,
        **update_values
    }).execute()

    return True


def add_room_points(room_id, user_id, amount):
    """ルーム内ポイントを加算"""

    room_id = _room_id(room_id)
    amount = int(amount)

    stats = get_room_user_stats(room_id, user_id)

    if not stats:
        return False

    update_room_user_stats(
        room_id,
        user_id,
        total_points=int(stats.get("total_points", 0)) + amount,
        current_points=int(stats.get("current_points", 0)) + amount
    )

    return True


def consume_room_points(room_id, user_id, amount):
    """ルーム内ポイントを消費"""

    room_id = _room_id(room_id)
    amount = int(amount)

    stats = get_room_user_stats(room_id, user_id)

    if not stats:
        return False

    current = int(stats.get("current_points", 0))

    if current < amount:
        return False

    update_room_user_stats(
        room_id,
        user_id,
        current_points=current - amount,
        used_count=int(stats.get("used_count", 0)) + amount
    )

    return True


def get_room_ranking(room_id):
    """ルーム内の現在ポイントランキング"""

    room_id = _room_id(room_id)

    if room_id is None:
        return []

    result = (
        supabase.table("room_user_stats")
        .select("*")
        .eq("room_id", room_id)
        .order("current_points", desc=True)
        .execute()
    )

    ranking = []

    for row in result.data or []:
        user = get_user(row["user_id"])

        ranking.append({
            **row,
            "name": user.get("name", "不明") if user else "不明"
        })

    return ranking


def get_room_user(room_id, user_id):
    """ルーム内のユーザー情報を取得"""

    stats = get_room_user_stats(room_id, user_id)

    if not stats:
        return None

    user = get_user(user_id)

    if not user:
        return None

    return {
        **user,
        **stats
    }


# ----------------------------------------
# ルーム別アイテム一覧
# ----------------------------------------

def get_room_items(room_id):
    room_id = _room_id(room_id)

    if room_id is None:
        return []

    result = (
        supabase.table("room_items")
        .select("*")
        .eq("room_id", room_id)
        .order("item_id")
        .execute()
    )

    return result.data or []


def get_room_item(room_id, item_id):
    room_id = _room_id(room_id)

    if room_id is None:
        return None

    return _get_one(
        "room_items",
        room_id=room_id,
        item_id=int(item_id)
    )


# ----------------------------------------
# ルーム別鬼カード
# ----------------------------------------

def get_room_oni_card(room_id, card_no):
    room_id = _room_id(room_id)

    if room_id is None:
        return None

    return _get_one(
        "room_oni_cards",
        room_id=room_id,
        card_no=int(card_no)
    )


def get_all_room_oni_cards(room_id):
    room_id = _room_id(room_id)

    if room_id is None:
        return []

    result = (
        supabase.table("room_oni_cards")
        .select("*")
        .eq("room_id", room_id)
        .order("card_no")
        .execute()
    )

    return result.data or []


def update_room_oni_card(
    room_id,
    card_no,
    user_id=None,
    name=None
):
    """ルーム内の鬼カードを更新"""

    room_id = _room_id(room_id)

    if room_id is None:
        return False

    card = get_room_oni_card(room_id, card_no)

    if not card:
        return False

    values = {
        "current_user_id": user_id,
        "current_name": name,
        "start_time": _now() if user_id else None
    }

    supabase.table("room_oni_cards").update(
        values
    ).eq(
        "room_id", room_id
    ).eq(
        "card_no", int(card_no)
    ).execute()

    return True


def add_room_oni_history(
    room_id,
    card_no,
    user_name,
    seconds
):
    """ルーム別の鬼履歴を保存"""

    room_id = _room_id(room_id)

    if room_id is None:
        return False

    supabase.table("oni_history").insert({
        "room_id": room_id,
        "card_no": int(card_no),
        "user_name": user_name,
        "seconds": int(seconds)
    }).execute()

    return True


def get_room_oni_ranking(room_id):
    """ルーム別の鬼ランキング"""

    room_id = _room_id(room_id)

    if room_id is None:
        return []

    result = (
        supabase.table("oni_history")
        .select("user_name, seconds")
        .eq("room_id", room_id)
        .execute()
    )

    totals = {}

    for row in result.data or []:
        name = row.get("user_name", "不明")
        seconds = int(row.get("seconds") or 0)

        totals[name] = totals.get(name, 0) + seconds

    return sorted(
        [
            {
                "name": name,
                "seconds": seconds
            }
            for name, seconds in totals.items()
        ],
        key=lambda x: x["seconds"],
        reverse=True
    )
    
# ========================================
# Part3：試合管理・アイテム・リザルト
# ========================================


# ----------------------------------------
# 試合管理
# ----------------------------------------

def get_active_match(room_id):
    """ルームで進行中の試合を取得"""

    room_id = _room_id(room_id)

    if room_id is None:
        return None

    result = (
        supabase.table("matches")
        .select("*")
        .eq("room_id", room_id)
        .eq("status", "playing")
        .order("started_at", desc=True)
        .limit(1)
        .execute()
    )

    if result.data:
        return result.data[0]

    return None


def start_match(room_id):
    """試合を開始し、参加者の開始時ポイントを記録"""

    room_id = _room_id(room_id)

    if room_id is None:
        return None

    room = get_room(room_id)

    if not room or not room.get("is_active", True):
        return None

    # 同じルームで二重に試合を開始させない
    if get_active_match(room_id):
        return None

    member_ids = get_room_member_ids(room_id)

    if len(member_ids) < 2:
        return None

    match_result = supabase.table("matches").insert({
        "room_id": room_id,
        "status": "playing",
        "started_at": _now()
    }).execute()

    if not match_result.data:
        return None

    match = match_result.data[0]
    match_id = match["id"]

    # 試合開始時点のポイントを保存
    for user_id in member_ids:
        stats = get_room_user_stats(room_id, user_id)

        if not stats:
            stats = {
                "current_points": 0,
                "total_points": 0
            }

            update_room_user_stats(
                room_id,
                user_id,
                current_points=0,
                total_points=0,
                used_count=0,
                oni_count=0
            )

        starting_points = int(
            stats.get("current_points", 0)
        )

        supabase.table("match_player_stats").upsert({
            "match_id": match_id,
            "room_id": room_id,
            "user_id": user_id,
            "match_points": 0,
            "earned_points": 0,
            "spent_points": 0,
            "item_count": 0,
            "starting_points": starting_points,
            "ending_points": starting_points
        }).execute()

    return match


def get_match_player_stats(match_id, user_id):
    """試合中のプレイヤー成績を取得"""

    return _get_one(
        "match_player_stats",
        match_id=int(match_id),
        user_id=user_id
    )


def add_match_points(room_id, user_id, amount):
    """
    試合中のポイントを加算する。
    earned_points / match_points は獲得したポイントの累計。
    消費ポイントはランキングから差し引かない。
    """

    room_id = _room_id(room_id)
    amount = int(amount)

    if amount <= 0:
        return False

    match = get_active_match(room_id)

    if not match:
        return False

    stats = get_room_user_stats(room_id, user_id)

    if not stats:
        return False

    # ルーム内のポイントを更新
    update_room_user_stats(
        room_id,
        user_id,
        current_points=int(stats.get("current_points", 0)) + amount,
        total_points=int(stats.get("total_points", 0)) + amount
    )

    # 試合成績を更新
    player_stats = get_match_player_stats(
        match["id"],
        user_id
    )

    if not player_stats:
        return False

    earned = int(player_stats.get("earned_points", 0)) + amount

    supabase.table("match_player_stats").update({
        "earned_points": earned,
        "match_points": earned
    }).eq(
        "match_id", match["id"]
    ).eq(
        "user_id", user_id
    ).execute()

    return True


def consume_match_points(room_id, user_id, amount):
    """試合中にポイントを消費する"""

    room_id = _room_id(room_id)
    amount = int(amount)

    if amount <= 0:
        return False

    match = get_active_match(room_id)

    if not match:
        return False

    player_stats = get_match_player_stats(
        match["id"],
        user_id
    )

    if not player_stats:
        return False

    # ルーム内の所持ポイントを確認
    room_stats = get_room_user_stats(room_id, user_id)

    if not room_stats:
        return False

    current = int(room_stats.get("current_points", 0))

    if current < amount:
        return False

    update_room_user_stats(
        room_id,
        user_id,
        current_points=current - amount,
        used_count=int(room_stats.get("used_count", 0)) + amount
    )

    spent = int(player_stats.get("spent_points", 0)) + amount

    supabase.table("match_player_stats").update({
        "spent_points": spent
    }).eq(
        "match_id", match["id"]
    ).eq(
        "user_id", user_id
    ).execute()

    return True


def add_match_item_usage(
    room_id,
    user_id,
    item_id,
    item_name=None
):
    """試合中のアイテム使用履歴を保存"""

    room_id = _room_id(room_id)

    if room_id is None:
        return False

    match = get_active_match(room_id)

    if not match:
        return False

    player_stats = get_match_player_stats(
        match["id"],
        user_id
    )

    if not player_stats:
        return False

    supabase.table("match_item_usage").insert({
        "match_id": match["id"],
        "room_id": room_id,
        "user_id": user_id,
        "item_id": int(item_id),
        "item_name": item_name
    }).execute()

    supabase.table("match_player_stats").update({
        "item_count": int(player_stats.get("item_count", 0)) + 1
    }).eq(
        "match_id", match["id"]
    ).eq(
        "user_id", user_id
    ).execute()

    return True


def finish_match(room_id):
    """試合を終了し、全プレイヤーの最終ポイントを保存"""

    room_id = _room_id(room_id)

    if room_id is None:
        return None

    match = get_active_match(room_id)

    if not match:
        return None

    match_id = match["id"]

    players = (
        supabase.table("match_player_stats")
        .select("*")
        .eq("match_id", match_id)
        .execute()
    )

    for player in players.data or []:
        user_id = player["user_id"]
        room_stats = get_room_user_stats(room_id, user_id)

        ending_points = (
            int(room_stats.get("current_points", 0))
            if room_stats else 0
        )

        supabase.table("match_player_stats").update({
            "ending_points": ending_points
        }).eq(
            "match_id", match_id
        ).eq(
            "user_id", user_id
        ).execute()

    supabase.table("matches").update({
        "status": "finished",
        "ended_at": _now()
    }).eq(
        "id", match_id
    ).execute()

    return get_match_result(match_id)


def get_match_result(match_id):
    """試合結果を取得"""

    match_id = int(match_id)

    match = _get_one("matches", id=match_id)

    if not match:
        return None

    result = (
        supabase.table("match_player_stats")
        .select("*")
        .eq("match_id", match_id)
        .execute()
    )

    players = []

    for row in result.data or []:
        user = get_user(row["user_id"])

        players.append({
            **row,
            "name": user.get("name", "不明") if user else "不明"
        })

    # 獲得ポイントの多い順に並べる
    players.sort(
        key=lambda x: int(x.get("match_points", 0)),
        reverse=True
    )

    for index, player in enumerate(players, start=1):
        player["rank"] = index

    # アイテム使用履歴
    usage_result = (
        supabase.table("match_item_usage")
        .select("*")
        .eq("match_id", match_id)
        .execute()
    )

    item_usage = usage_result.data or []

    item_counts = {}

    for usage in item_usage:
        user_id = usage["user_id"]
        user = get_user(user_id)

        name = (
            user.get("name", "不明")
            if user else "不明"
        )

        item_counts[name] = item_counts.get(name, 0) + 1

    most_item_user = None
    most_item_count = 0

    if item_counts:
        most_item_user = max(
            item_counts,
            key=item_counts.get
        )
        most_item_count = item_counts[most_item_user]

    # MVP：試合中の獲得ポイントが最多のプレイヤー
    mvp = players[0] if players else None

    # 試合時間
    duration_seconds = 0

    if match.get("started_at") and match.get("ended_at"):
        try:
            start = datetime.fromisoformat(
                match["started_at"].replace("Z", "+00:00")
            )
            end = datetime.fromisoformat(
                match["ended_at"].replace("Z", "+00:00")
            )

            duration_seconds = max(
                0,
                int((end - start).total_seconds())
            )
        except (ValueError, TypeError):
            duration_seconds = 0

    return {
        "match": match,
        "players": players,
        "mvp": mvp,
        "item_usage": item_usage,
        "item_counts": item_counts,
        "most_item_user": most_item_user,
        "most_item_count": most_item_count,
        "duration_seconds": duration_seconds
    }


# ----------------------------------------
# ルーム別アイテム購入・使用
# ----------------------------------------

def buy_room_item(room_id, user_id, item_id):
    """ルーム内のアイテムを購入"""

    room_id = _room_id(room_id)

    if room_id is None:
        return False

    item = get_room_item(room_id, item_id)

    if not item:
        return False

    price = int(item.get("price", 0))

    if price < 0:
        return False

    match = get_active_match(room_id)

    if not match:
        return False

    if not consume_match_points(room_id, user_id, price):
        return False

    # 所持数を取得
    result = (
        supabase.table("user_items")
        .select("*")
        .eq("room_id", room_id)
        .eq("user_id", user_id)
        .eq("item_id", int(item_id))
        .execute()
    )

    if result.data:
        inventory = result.data[0]

        supabase.table("user_items").update({
            "quantity": int(inventory.get("quantity", 0)) + 1
        }).eq(
            "room_id", room_id
        ).eq(
            "user_id", user_id
        ).eq(
            "item_id", int(item_id)
        ).execute()

    else:
        supabase.table("user_items").insert({
            "room_id": room_id,
            "user_id": user_id,
            "item_id": int(item_id),
            "quantity": 1
        }).execute()

    return True


def get_room_user_items(room_id, user_id):
    """ルーム内で所持しているアイテム一覧"""

    room_id = _room_id(room_id)

    if room_id is None:
        return []

    result = (
        supabase.table("user_items")
        .select("*")
        .eq("room_id", room_id)
        .eq("user_id", user_id)
        .execute()
    )

    items = []

    for inventory in result.data or []:
        item = get_room_item(
            room_id,
            inventory["item_id"]
        )

        if item:
            items.append({
                **item,
                "quantity": int(inventory.get("quantity", 0))
            })

    return items


def use_room_item(room_id, user_id, item_id):
    """ルーム内のアイテムを使用"""

    room_id = _room_id(room_id)

    if room_id is None:
        return False

    match = get_active_match(room_id)

    if not match:
        return False

    result = (
        supabase.table("user_items")
        .select("*")
        .eq("room_id", room_id)
        .eq("user_id", user_id)
        .eq("item_id", int(item_id))
        .execute()
    )

    if not result.data:
        return False

    inventory = result.data[0]
    quantity = int(inventory.get("quantity", 0))

    if quantity <= 0:
        return False

    item = get_room_item(room_id, item_id)

    if not item:
        return False

    if quantity == 1:
        supabase.table("user_items").delete().eq(
            "room_id", room_id
        ).eq(
            "user_id", user_id
        ).eq(
            "item_id", int(item_id)
        ).execute()
    else:
        supabase.table("user_items").update({
            "quantity": quantity - 1
        }).eq(
            "room_id", room_id
        ).eq(
            "user_id", user_id
        ).eq(
            "item_id", int(item_id)
        ).execute()

    # アイテム使用履歴を記録
    add_match_item_usage(
        room_id,
        user_id,
        item_id,
        item.get("item_name")
    )

    return True


# ----------------------------------------
# 再試合・ルーム削除
# ----------------------------------------

def reset_room_for_rematch(room_id):
    """
    再試合用の処理。
    過去の試合記録は削除せず、新しい試合を開始できる状態にする。
    """

    room_id = _room_id(room_id)

    if room_id is None:
        return False

    if get_active_match(room_id):
        return False

    room = get_room(room_id)

    if not room:
        return False

    return True


def delete_room(room_id):
    """ルームを削除する"""

    room_id = _room_id(room_id)

    if room_id is None:
        return False

    room = get_room(room_id)

    if not room:
        return False

    if get_active_match(room_id):
        return False

    # ルームに所属していたユーザーの選択状態を解除
    members = get_room_member_ids(room_id)

    for user_id in members:
        supabase.table("users").update({
            "active_room_id": None
        }).eq(
            "user_id", user_id
        ).eq(
            "active_room_id", room_id
        ).execute()

    # 試合IDを取得
    matches_result = (
        supabase.table("matches")
        .select("id")
        .eq("room_id", room_id)
        .execute()
    )

    match_ids = [
        row["id"]
        for row in (matches_result.data or [])
    ]

    # 試合に紐づく記録
    for match_id in match_ids:
        supabase.table("match_item_usage").delete().eq(
            "match_id", match_id
        ).execute()

        supabase.table("match_player_stats").delete().eq(
            "match_id", match_id
        ).execute()

    supabase.table("matches").delete().eq(
        "room_id", room_id
    ).execute()

    # その他のルームデータ
    supabase.table("user_items").delete().eq(
        "room_id", room_id
    ).execute()

    supabase.table("oni_history").delete().eq(
        "room_id", room_id
    ).execute()

    supabase.table("room_oni_cards").delete().eq(
        "room_id", room_id
    ).execute()

    supabase.table("room_items").delete().eq(
        "room_id", room_id
    ).execute()

    supabase.table("room_user_stats").delete().eq(
        "room_id", room_id
    ).execute()

    supabase.table("room_members").delete().eq(
        "room_id", room_id
    ).execute()

    supabase.table("rooms").delete().eq(
        "room_id", room_id
    ).execute()

    return True


# ----------------------------------------
# 全体リセット
# ----------------------------------------

def reset_all_data():
    """
    全体データをリセットする。
    ユーザー登録とアイテム一覧は残す。
    """

    # 全ユーザーのポイント情報をリセット
    users_result = (
        supabase.table("users")
        .select("user_id")
        .execute()
    )

    for user in users_result.data or []:
        supabase.table("users").update({
            "total_points": 0,
            "current_points": 0,
            "used_count": 0,
            "oni_count": 0
        }).eq(
            "user_id", user["user_id"]
        ).execute()

    # ルーム別ポイントもリセット
    room_stats = (
        supabase.table("room_user_stats")
        .select("room_id, user_id")
        .execute()
    )

    for row in room_stats.data or []:
        supabase.table("room_user_stats").update({
            "total_points": 0,
            "current_points": 0,
            "used_count": 0,
            "oni_count": 0
        }).eq(
            "room_id", row["room_id"]
        ).eq(
            "user_id", row["user_id"]
        ).execute()

    # 所持アイテムと鬼履歴を削除
    supabase.table("user_items").delete().neq(
        "user_id", ""
    ).execute()

    supabase.table("oni_history").delete().neq(
        "user_name", ""
    ).execute()

    # 全体の鬼カードをリセット
    cards = (
        supabase.table("oni_cards")
        .select("card_no")
        .execute()
    )

    for card in cards.data or []:
        supabase.table("oni_cards").update({
            "current_user_id": None,
            "current_name": None,
            "start_time": None
        }).eq(
            "card_no", card["card_no"]
        ).execute()

    # ルーム別の鬼カードもリセット
    room_cards = (
        supabase.table("room_oni_cards")
        .select("room_id, card_no")
        .execute()
    )

    for card in room_cards.data or []:
        supabase.table("room_oni_cards").update({
            "current_user_id": None,
            "current_name": None,
            "start_time": None
        }).eq(
            "room_id", card["room_id"]
        ).eq(
            "card_no", card["card_no"]
        ).execute()

    return True


# ----------------------------------------
# 全体の鬼カード一覧・ランキング
# ----------------------------------------

def get_all_oni_cards():
    result = (
        supabase.table("oni_cards")
        .select("*")
        .order("card_no")
        .execute()
    )

    return result.data or []


def get_oni_ranking():
    result = (
        supabase.table("oni_history")
        .select("user_name, seconds")
        .is_("room_id", "null")
        .execute()
    )

    totals = {}

    for row in result.data or []:
        name = row.get("user_name", "不明")
        seconds = int(row.get("seconds") or 0)

        totals[name] = totals.get(name, 0) + seconds

    return sorted(
        [
            {
                "name": name,
                "seconds": seconds
            }
            for name, seconds in totals.items()
        ],
        key=lambda x: x["seconds"],
        reverse=True
    )
