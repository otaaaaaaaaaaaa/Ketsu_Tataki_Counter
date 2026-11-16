
import os
import random
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

DEFAULT_ROOM_ID = 10000000


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

    return _room_id(user.get("active_room_id"))


def _safe_int(value):
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


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
        for row in (result.data or [])
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

    for user in result.data or []:
        update_user(
            user["user_id"],
            _safe_int(user.get("total_points")) + amount,
            _safe_int(user.get("current_points")) + amount,
            _safe_int(user.get("used_count"))
        )

    return True


def reset_all_points():
    result = (
        supabase.table("users")
        .select("user_id")
        .execute()
    )

    for user in result.data or []:
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

    return result.data or []


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

    return result.data or []


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

    if sender_id == receiver["user_id"]:
        return False, "自分自身には譲渡できません"

    sender_room = _room_id(sender.get("active_room_id"))
    receiver_room = _room_id(receiver.get("active_room_id"))

    # ルーム内での譲渡
    if sender_room is not None or receiver_room is not None:

        if sender_room is None or receiver_room is None:
            return False, "同じルームの相手にのみ譲渡できます"

        if sender_room != receiver_room:
            return False, "別のルームの相手には譲渡できません"

        sender_stats = get_room_user_stats(
            sender_room,
            sender_id
        )

        receiver_stats = get_room_user_stats(
            sender_room,
            receiver["user_id"]
        )

        if not sender_stats or not receiver_stats:
            return False, "ルームのポイント情報がありません"

        sender_current = _safe_int(
            sender_stats.get("current_points")
        )

        if sender_current < amount:
            return False, "ポイントが不足しています"

        update_room_user_stats(
            sender_room,
            sender_id,
            total_points=_safe_int(sender_stats.get("total_points")),
            current_points=sender_current - amount,
            used_count=_safe_int(sender_stats.get("used_count")),
            oni_count=_safe_int(sender_stats.get("oni_count"))
        )

        update_room_user_stats(
            sender_room,
            receiver["user_id"],
            total_points=_safe_int(receiver_stats.get("total_points")),
            current_points=_safe_int(receiver_stats.get("current_points")) + amount,
            used_count=_safe_int(receiver_stats.get("used_count")),
            oni_count=_safe_int(receiver_stats.get("oni_count"))
        )

        return True, receiver

    # ルーム外での譲渡
    sender_current = _safe_int(sender.get("current_points"))

    if sender_current < amount:
        return False, "ポイントが不足しています"

    update_user(
        sender_id,
        _safe_int(sender.get("total_points")),
        sender_current - amount,
        _safe_int(sender.get("used_count"))
    )

    update_user(
        receiver["user_id"],
        _safe_int(receiver.get("total_points")),
        _safe_int(receiver.get("current_points")) + amount,
        _safe_int(receiver.get("used_count"))
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

        new_count = _safe_int(stats.get("oni_count")) + 1

        update_room_user_stats(
            room_id,
            user_id,
            oni_count=new_count
        )

        return new_count

    user = get_user(user_id)

    if not user:
        return 0

    new_count = _safe_int(user.get("oni_count")) + 1

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
# アイテム一覧（全体）
# =====================================

def get_items():
    result = (
        supabase.table("items")
        .select("*")
        .order("item_id")
        .execute()
    )

    return result.data or []


def get_item(item_id):
    return _get_one(
        "items",
        item_id=int(item_id)
    )


# ========================================
# ルーム管理
# ========================================

def get_user_active_room(user_id):
    room_id = _get_active_room_id(user_id)

    if room_id is None:
        return None

    return get_room(room_id)


def get_room_by_id(room_id):
    room_id = _room_id(room_id)

    if room_id is None:
        return None

    return _get_one("rooms", room_id=room_id)


def get_room(room_id):
    return get_room_by_id(room_id)


def get_room_members(room_id):
    room_id = _room_id(room_id)

    if room_id is None:
        return []

    result = (
        supabase.table("room_members")
        .select("user_id, joined_at, users(name)")
        .eq("room_id", room_id)
        .order("joined_at")
        .execute()
    )

    members = []

    for row in result.data or []:
        user_data = row.get("users") or {}

        members.append({
            "user_id": row.get("user_id"),
            "name": user_data.get("name", "不明"),
            "joined_at": row.get("joined_at")
        })

    return members


def get_room_member_ids(room_id):
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


def create_room(owner_user_id):
    user = get_user(owner_user_id)

    if not user:
        return None

    room_id = None

    # 8桁のルームIDを生成
    for _ in range(30):
        candidate = random.randint(10000000, 99999999)

        if not get_room(candidate):
            room_id = candidate
            break

    if room_id is None:
        raise RuntimeError("ルームIDを生成できませんでした")

    room_result = (
        supabase.table("rooms")
        .insert({
            "room_id": room_id,
            "owner_user_id": owner_user_id,
            "is_active": True
        })
        .execute()
    )

    if not room_result.data:
        return None

    supabase.table("room_members").insert({
        "room_id": room_id,
        "user_id": owner_user_id
    }).execute()

    supabase.table("users").update({
        "active_room_id": room_id
    }).eq("user_id", owner_user_id).execute()

    # オーナーのルーム別ポイントを初期化
    supabase.table("room_user_stats").upsert({
        "room_id": room_id,
        "user_id": owner_user_id,
        "total_points": 0,
        "current_points": 0,
        "used_count": 0,
        "oni_count": 0
    }).execute()

    # 既存アイテムをルームにコピー
    items_result = (
        supabase.table("items")
        .select("*")
        .execute()
    )

    for item in items_result.data or []:
        supabase.table("room_items").upsert({
            "room_id": room_id,
            "item_id": item["item_id"],
            "item_name": item["item_name"],
            "price": item.get("price", 0),
            "description": item.get("description")
        }).execute()

    # 鬼カードを初期化
    cards_result = (
        supabase.table("oni_cards")
        .select("*")
        .execute()
    )

    for card in cards_result.data or []:
        supabase.table("room_oni_cards").upsert({
            "room_id": room_id,
            "card_no": card["card_no"],
            "current_user_id": None,
            "current_name": None,
            "start_time": None
        }).execute()

    return get_room(room_id)


def join_room(user_id, room_id):
    room_id = _room_id(room_id)

    if room_id is None:
        return False

    user = get_user(user_id)
    room = get_room(room_id)

    if not user or not room:
        return False

    if not room.get("is_active", True):
        return False

    current_room_id = _get_active_room_id(user_id)

    # 既に別のルームに参加している場合は移動させない
    if current_room_id is not None and current_room_id != DEFAULT_ROOM_ID:
        if current_room_id != room_id:
            return False

    member_ids = get_room_member_ids(room_id)

    if user_id not in member_ids:
        supabase.table("room_members").insert({
            "room_id": room_id,
            "user_id": user_id
        }).execute()

    supabase.table("users").update({
        "active_room_id": room_id
    }).eq("user_id", user_id).execute()

    # 参加者のルーム別ポイントを初期化
    supabase.table("room_user_stats").upsert({
        "room_id": room_id,
        "user_id": user_id,
        "total_points": 0,
        "current_points": 0,
        "used_count": 0,
        "oni_count": 0
    }, on_conflict="room_id,user_id").execute()

    return True


def leave_room(user_id):
    room_id = _get_active_room_id(user_id)

    if room_id is None or room_id == DEFAULT_ROOM_ID:
        return False

    room = get_room(room_id)

    if not room:
        return False

    # 試合中は退出できない
    if get_active_match(room_id):
        return False

    supabase.table("room_members").delete().eq(
        "room_id", room_id
    ).eq(
        "user_id", user_id
    ).execute()

    supabase.table("users").update({
        "active_room_id": DEFAULT_ROOM_ID
    }).eq("user_id", user_id).execute()

    return True


# ========================================
# ルーム別ポイント
# ========================================

def get_room_user_stats(room_id, user_id):
    room_id = _room_id(room_id)

    if room_id is None:
        return None

    return _get_one(
        "room_user_stats",
        room_id=room_id,
        user_id=user_id
    )


def get_room_user(room_id, user_id):
    return get_room_user_stats(room_id, user_id)


def update_room_user_stats(room_id, user_id, **values):
    room_id = _room_id(room_id)

    if room_id is None:
        return None

    values["room_id"] = room_id
    values["user_id"] = user_id

    result = (
        supabase.table("room_user_stats")
        .upsert(
            values,
            on_conflict="room_id,user_id"
        )
        .execute()
    )

    if result.data:
        return result.data[0]

    return get_room_user_stats(room_id, user_id)


def add_room_points(room_id, user_id, amount):
    amount = _safe_int(amount)

    if amount <= 0:
        return False

    stats = get_room_user_stats(room_id, user_id)

    if not stats:
        return False

    update_room_user_stats(
        room_id,
        user_id,
        current_points=_safe_int(stats.get("current_points")) + amount,
        total_points=_safe_int(stats.get("total_points")) + amount
    )

    return True


def consume_room_points(room_id, user_id, amount):
    amount = _safe_int(amount)

    if amount <= 0:
        return False

    stats = get_room_user_stats(room_id, user_id)

    if not stats:
        return False

    current = _safe_int(stats.get("current_points"))

    if current < amount:
        return False

    update_room_user_stats(
        room_id,
        user_id,
        current_points=current - amount,
        used_count=_safe_int(stats.get("used_count")) + 1
    )

    return True


def get_room_ranking(room_id):
    room_id = _room_id(room_id)

    if room_id is None:
        return []

    result = (
        supabase.table("room_user_stats")
        .select("user_id,total_points,current_points,used_count,oni_count,users(name)")
        .eq("room_id", room_id)
        .order("current_points", desc=True)
        .execute()
    )

    ranking = []

    for row in result.data or []:
        user_data = row.get("users") or {}

        ranking.append({
            "user_id": row.get("user_id"),
            "name": user_data.get("name", "不明"),
            "total_points": _safe_int(row.get("total_points")),
            "current_points": _safe_int(row.get("current_points")),
            "used_count": _safe_int(row.get("used_count")),
            "oni_count": _safe_int(row.get("oni_count"))
        })

    return ranking


# ========================================
# ルーム別鬼カード
# ========================================

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
    current_user_id=None,
    current_name=None,
    start_time=None
):
    room_id = _room_id(room_id)

    if room_id is None:
        return False

    result = (
        supabase.table("room_oni_cards")
        .upsert({
            "room_id": room_id,
            "card_no": int(card_no),
            "current_user_id": current_user_id,
            "current_name": current_name,
            "start_time": start_time
        }, on_conflict="room_id,card_no")
        .execute()
    )

    return bool(result.data)


def add_room_oni_history(room_id, card_no, user_name, seconds):
    room_id = _room_id(room_id)

    if room_id is None:
        return False

    result = (
        supabase.table("oni_history")
        .insert({
            "room_id": room_id,
            "card_no": int(card_no),
            "user_name": user_name,
            "seconds": _safe_int(seconds)
        })
        .execute()
    )

    return bool(result.data)


def get_room_oni_ranking(room_id):
    room_id = _room_id(room_id)

    if room_id is None:
        return []

    result = (
        supabase.table("oni_history")
        .select("user_name,seconds")
        .eq("room_id", room_id)
        .execute()
    )

    totals = {}

    for row in result.data or []:
        name = row.get("user_name", "不明")
        totals[name] = totals.get(name, 0) + _safe_int(row.get("seconds"))

    ranking = [
        {
            "name": name,
            "seconds": seconds
        }
        for name, seconds in totals.items()
    ]

    ranking.sort(
        key=lambda x: x["seconds"],
        reverse=True
    )

    return ranking


# ========================================
# ルーム別アイテム一覧
# ========================================

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


# ========================================
# 試合管理
# ========================================

def get_active_match(room_id):
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


def get_match_player_stats(match_id, user_id):
    return _get_one(
        "match_player_stats",
        match_id=int(match_id),
        user_id=user_id
    )


def start_match(room_id):
    room_id = _room_id(room_id)

    if room_id is None:
        return None

    room = get_room(room_id)

    if not room or not room.get("is_active", True):
        return None

    # 既に試合中なら開始しない
    if get_active_match(room_id):
        return None

    member_ids = get_room_member_ids(room_id)

    if len(member_ids) < 2:
        return None

    # 試合を作成
    match_result = (
        supabase.table("matches")
        .insert({
            "room_id": room_id,
            "status": "playing"
        })
        .execute()
    )

    if not match_result.data:
        return None

    match = match_result.data[0]
    match_id = match["id"]

    # 全プレイヤーの試合開始時ポイントを記録
    for user_id in member_ids:
        stats = get_room_user_stats(room_id, user_id)

        if not stats:
            stats = {
                "current_points": 0
            }

        starting_points = _safe_int(
            stats.get("current_points")
        )

        supabase.table("match_player_stats").insert({
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


def add_match_points(room_id, user_id, amount):
    room_id = _room_id(room_id)
    amount = _safe_int(amount)

    if room_id is None or amount <= 0:
        return False

    match = get_active_match(room_id)

    if not match:
        return False

    match_id = match["id"]

    player_stats = get_match_player_stats(
        match_id,
        user_id
    )

    if not player_stats:
        return False

    room_stats = get_room_user_stats(
        room_id,
        user_id
    )

    if not room_stats:
        return False

    # ルーム内の所持ポイントを増やす
    update_room_user_stats(
        room_id,
        user_id,
        current_points=(
            _safe_int(room_stats.get("current_points")) + amount
        ),
        total_points=(
            _safe_int(room_stats.get("total_points")) + amount
        )
    )

    # 試合中の獲得ポイントを記録
    new_earned = (
        _safe_int(player_stats.get("earned_points")) + amount
    )

    new_match_points = (
        _safe_int(player_stats.get("match_points")) + amount
    )

    supabase.table("match_player_stats").update({
        "earned_points": new_earned,
        "match_points": new_match_points
    }).eq(
        "id", player_stats["id"]
    ).execute()

    return True


def consume_match_points(room_id, user_id, amount):
    room_id = _room_id(room_id)
    amount = _safe_int(amount)

    if room_id is None or amount <= 0:
        return False

    match = get_active_match(room_id)

    if not match:
        return False

    match_id = match["id"]

    player_stats = get_match_player_stats(
        match_id,
        user_id
    )

    if not player_stats:
        return False

    room_stats = get_room_user_stats(
        room_id,
        user_id
    )

    if not room_stats:
        return False

    current_points = _safe_int(
        room_stats.get("current_points")
    )

    if current_points < amount:
        return False

    # 所持ポイントを減らす
    update_room_user_stats(
        room_id,
        user_id,
        current_points=current_points - amount,
        used_count=(
            _safe_int(room_stats.get("used_count")) + 1
        )
    )

    # 試合中の消費ポイントを記録
    new_spent = (
        _safe_int(player_stats.get("spent_points")) + amount
    )

    supabase.table("match_player_stats").update({
        "spent_points": new_spent
    }).eq(
        "id", player_stats["id"]
    ).execute()

    return True


def add_match_item_usage(
    room_id,
    user_id,
    item_id,
    item_name=None
):
    room_id = _room_id(room_id)

    if room_id is None:
        return False

    match = get_active_match(room_id)

    if not match:
        return False

    match_id = match["id"]

    player_stats = get_match_player_stats(
        match_id,
        user_id
    )

    if not player_stats:
        return False

    # アイテム使用履歴を記録
    result = (
        supabase.table("match_item_usage")
        .insert({
            "match_id": match_id,
            "room_id": room_id,
            "user_id": user_id,
            "item_id": int(item_id),
            "item_name": item_name
        })
        .execute()
    )

    if not result.data:
        return False

    # 使用回数を加算
    supabase.table("match_player_stats").update({
        "item_count": (
            _safe_int(player_stats.get("item_count")) + 1
        )
    }).eq(
        "id", player_stats["id"]
    ).execute()

    return True


def finish_match(room_id):
    room_id = _room_id(room_id)

    if room_id is None:
        return None

    match = get_active_match(room_id)

    if not match:
        return None

    match_id = match["id"]

    # 各プレイヤーの試合終了時ポイントを保存
    result = (
        supabase.table("match_player_stats")
        .select("*")
        .eq("match_id", match_id)
        .execute()
    )

    for player in result.data or []:
        room_stats = get_room_user_stats(
            room_id,
            player["user_id"]
        )

        ending_points = 0

        if room_stats:
            ending_points = _safe_int(
                room_stats.get("current_points")
            )

        supabase.table("match_player_stats").update({
            "ending_points": ending_points
        }).eq(
            "id", player["id"]
        ).execute()

    # 試合を終了
    supabase.table("matches").update({
        "status": "finished",
        "ended_at": _now()
    }).eq(
        "id", match_id
    ).execute()

    return get_match_result(match_id)


def get_match_result(match_id):
    match_id = _safe_int(match_id)

    if match_id <= 0:
        return None

    match = _get_one(
        "matches",
        id=match_id
    )

    if not match:
        return None

    result = (
        supabase.table("match_player_stats")
        .select("*, users(name)")
        .eq("match_id", match_id)
        .execute()
    )

    players = []

    for row in result.data or []:
        user_data = row.get("users") or {}

        players.append({
            "user_id": row.get("user_id"),
            "name": user_data.get("name", "不明"),
            "match_points": _safe_int(
                row.get("match_points")
            ),
            "earned_points": _safe_int(
                row.get("earned_points")
            ),
            "spent_points": _safe_int(
                row.get("spent_points")
            ),
            "item_count": _safe_int(
                row.get("item_count")
            ),
            "starting_points": _safe_int(
                row.get("starting_points")
            ),
            "ending_points": _safe_int(
                row.get("ending_points")
            )
        })

    # 試合中に獲得したポイント順
    players.sort(
        key=lambda x: x["match_points"],
        reverse=True
    )

    for index, player in enumerate(players, start=1):
        player["rank"] = index

    # MVP
    mvp = players[0] if players else None

    # アイテム使用回数最多のプレイヤー
    most_item_user = None

    if players:
        most_item_user = max(
            players,
            key=lambda x: x["item_count"]
        )

        if most_item_user["item_count"] == 0:
            most_item_user = None

    # 試合時間
    started_at = match.get("started_at")
    ended_at = match.get("ended_at")

    duration_seconds = 0

    if started_at and ended_at:
        try:
            start = datetime.fromisoformat(
                started_at.replace("Z", "+00:00")
            )
            end = datetime.fromisoformat(
                ended_at.replace("Z", "+00:00")
            )

            duration_seconds = max(
                0,
                int((end - start).total_seconds())
            )
        except (TypeError, ValueError):
            duration_seconds = 0

    return {
        "match_id": match_id,
        "room_id": match.get("room_id"),
        "status": match.get("status"),
        "started_at": started_at,
        "ended_at": ended_at,
        "duration_seconds": duration_seconds,
        "players": players,
        "ranking": players,
        "mvp": mvp,
        "most_item_user": most_item_user
    }


# ========================================
# ルーム別アイテム所持数
# ========================================

def get_room_user_items(room_id, user_id):
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

    for row in result.data or []:
        item = get_room_item(
            room_id,
            row.get("item_id")
        )

        items.append({
            **row,
            "item_name": (
                item.get("item_name", "不明")
                if item else "不明"
            ),
            "price": (
                _safe_int(item.get("price"))
                if item else 0
            ),
            "description": (
                item.get("description")
                if item else None
            )
        })

    return items


def buy_room_item(room_id, user_id, item_id):
    room_id = _room_id(room_id)

    if room_id is None:
        return False

    # 試合中のみ購入可能
    match = get_active_match(room_id)

    if not match:
        return False

    item = get_room_item(room_id, item_id)

    if not item:
        return False

    price = _safe_int(item.get("price"))

    if price < 0:
        return False

    # ポイントを消費
    if price > 0:
        if not consume_match_points(
            room_id,
            user_id,
            price
        ):
            return False

    # 所持数を確認
    existing = (
        supabase.table("user_items")
        .select("*")
        .eq("room_id", room_id)
        .eq("user_id", user_id)
        .eq("item_id", int(item_id))
        .limit(1)
        .execute()
    )

    if existing.data:
        row = existing.data[0]

        supabase.table("user_items").update({
            "quantity": (
                _safe_int(row.get("quantity")) + 1
            )
        }).eq(
            "id", row["id"]
        ).execute()

    else:
        supabase.table("user_items").insert({
            "room_id": room_id,
            "user_id": user_id,
            "item_id": int(item_id),
            "quantity": 1
        }).execute()

    return True


def use_room_item(room_id, user_id, item_id):
    room_id = _room_id(room_id)

    if room_id is None:
        return False

    # 試合中のみ使用可能
    match = get_active_match(room_id)

    if not match:
        return False

    item = get_room_item(room_id, item_id)

    if not item:
        return False

    # 所持数を確認
    existing = (
        supabase.table("user_items")
        .select("*")
        .eq("room_id", room_id)
        .eq("user_id", user_id)
        .eq("item_id", int(item_id))
        .limit(1)
        .execute()
    )

    if not existing.data:
        return False

    row = existing.data[0]
    quantity = _safe_int(row.get("quantity"))

    if quantity <= 0:
        return False

    # 使用履歴を先に記録
    if not add_match_item_usage(
        room_id,
        user_id,
        item_id,
        item.get("item_name")
    ):
        return False

    # 所持数を減らす
    supabase.table("user_items").update({
        "quantity": quantity - 1
    }).eq(
        "id", row["id"]
    ).execute()

    return True


# ========================================
# 再試合
# ========================================

def reset_room_for_rematch(room_id):
    room_id = _room_id(room_id)

    if room_id is None:
        return False

    room = get_room(room_id)

    if not room:
        return False

    # 試合中なら再試合準備はできない
    if get_active_match(room_id):
        return False

    # ポイント・アイテム・鬼カードは維持する
    # 次の start_match() で新しい試合記録を作成する
    return True


# ========================================
# ルーム削除
# ========================================

def delete_room(room_id):
    room_id = _room_id(room_id)

    if room_id is None or room_id == DEFAULT_ROOM_ID:
        return False

    room = get_room(room_id)

    if not room:
        return False

    # 試合中のルームは削除しない
    if get_active_match(room_id):
        return False

    # このルームに所属しているユーザーを取得
    member_ids = get_room_member_ids(room_id)

    # ユーザーの所属ルームを初期ルームに戻す
    for user_id in member_ids:
        supabase.table("users").update({
            "active_room_id": DEFAULT_ROOM_ID
        }).eq(
            "user_id", user_id
        ).eq(
            "active_room_id", room_id
        ).execute()

    # 試合履歴を取得
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

    # 試合に紐づくデータを削除
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

    # ルーム関連データを削除
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


# ========================================
# 全体データリセット
# ========================================

def reset_all_data():
    # 全ユーザーのポイントをリセット
    supabase.table("users").update({
        "total_points": 0,
        "current_points": 0,
        "used_count": 0,
        "oni_count": 0
    }).neq(
        "user_id", ""
    ).execute()

    # ルーム別ポイントをリセット
    supabase.table("room_user_stats").update({
        "total_points": 0,
        "current_points": 0,
        "used_count": 0,
        "oni_count": 0
    }).neq(
        "user_id", ""
    ).execute()

    # 所持アイテムを削除
    supabase.table("user_items").delete().neq(
        "user_id", ""
    ).execute()

    # 鬼カードの履歴を削除
    supabase.table("oni_history").delete().neq(
        "user_name", ""
    ).execute()

    # 全体の鬼カードを初期化
    cards_result = (
        supabase.table("oni_cards")
        .select("card_no")
        .execute()
    )

    for card in cards_result.data or []:
        supabase.table("oni_cards").update({
            "current_user_id": None,
            "current_name": None,
            "start_time": None
        }).eq(
            "card_no", card["card_no"]
        ).execute()

    # ルーム別鬼カードを初期化
    room_cards_result = (
        supabase.table("room_oni_cards")
        .select("room_id,card_no")
        .execute()
    )

    for card in room_cards_result.data or []:
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


# ========================================
# 全体の鬼カード
# ========================================

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
        .select("user_name,seconds")
        .is_("room_id", "null")
        .execute()
    )

    totals = {}

    for row in result.data or []:
        name = row.get("user_name", "不明")

        totals[name] = (
            totals.get(name, 0)
            + _safe_int(row.get("seconds"))
        )

    ranking = [
        {
            "name": name,
            "seconds": seconds
        }
        for name, seconds in totals.items()
    ]

    ranking.sort(
        key=lambda x: x["seconds"],
        reverse=True
    )

    return ranking


# ========================================
# 旧関数との互換用
# ========================================

def get_user_items(user_id):
    room_id = _get_active_room_id(user_id)

    if room_id is not None:
        return get_room_user_items(room_id, user_id)

    result = (
        supabase.table("user_items")
        .select("*")
        .is_("room_id", "null")
        .eq("user_id", user_id)
        .execute()
    )

    return result.data or []


def buy_item(user_id, item_id):
    room_id = _get_active_room_id(user_id)

    if room_id is not None:
        return buy_room_item(
            room_id,
            user_id,
            item_id
        )

    item = get_item(item_id)

    if not item:
        return False

    user = get_user(user_id)

    if not user:
        return False

    price = _safe_int(item.get("price"))
    current = _safe_int(user.get("current_points"))

    if price < 0 or current < price:
        return False

    supabase.table("users").update({
        "current_points": current - price,
        "used_count": _safe_int(user.get("used_count")) + 1
    }).eq(
        "user_id", user_id
    ).execute()

    existing = (
        supabase.table("user_items")
        .select("*")
        .is_("room_id", "null")
        .eq("user_id", user_id)
        .eq("item_id", int(item_id))
        .limit(1)
        .execute()
    )

    if existing.data:
        row = existing.data[0]

        supabase.table("user_items").update({
            "quantity": _safe_int(row.get("quantity")) + 1
        }).eq(
            "id", row["id"]
        ).execute()

    else:
        supabase.table("user_items").insert({
            "user_id": user_id,
            "item_id": int(item_id),
            "quantity": 1
        }).execute()

    return True


def use_item(user_id, item_id):
    room_id = _get_active_room_id(user_id)

    if room_id is not None:
        return use_room_item(
            room_id,
            user_id,
            item_id
        )

    existing = (
        supabase.table("user_items")
        .select("*")
        .is_("room_id", "null")
        .eq("user_id", user_id)
        .eq("item_id", int(item_id))
        .limit(1)
        .execute()
    )

    if not existing.data:
        return False

    row = existing.data[0]
    quantity = _safe_int(row.get("quantity"))

    if quantity <= 0:
        return False

    supabase.table("user_items").update({
        "quantity": quantity - 1
    }).eq(
        "id", row["id"]
    ).execute()

    return True
