
from database import (
    get_user,
    get_user_active_room,
    get_room_user_stats,
    add_room_points,
    consume_room_points,
    get_active_match,
    add_match_points,
    consume_match_points
)


# =====================================
# 共通処理
# =====================================

def get_point_context(user_id):
    """
    ユーザーの現在のルームとポイント情報を取得する
    """

    room_id = get_user_active_room(user_id)

    if not room_id:
        return None, None

    stats = get_room_user_stats(
        room_id,
        user_id
    )

    if not stats:
        return room_id, None

    return room_id, stats


def validate_amount(amount):
    """
    ポイント数の入力チェック
    """

    if not isinstance(amount, int) or isinstance(amount, bool):
        return False, "ポイント数は整数で指定してください"

    if amount <= 0:
        return False, "1以上のポイントを指定してください"

    return True, None


# =====================================
# ポイント獲得
# =====================================

def add_point(user_id, amount=1):
    """
    ユーザーにポイントを追加する。

    試合中:
        試合成績とルームポイントを更新

    試合外:
        ルームポイントを更新

    Returns
    -------
    tuple:
        (累計ポイント, 現在ポイント)

        失敗時:
        (False, エラーメッセージ)
    """

    valid, error = validate_amount(amount)

    if not valid:
        return False, error

    room_id, stats = get_point_context(user_id)

    if not room_id:
        return False, "所属ルームが見つかりません"

    if not stats:
        return False, "ルームのポイント情報が見つかりません"

    # 試合中か確認
    match = get_active_match(room_id)

    if match:

        success = add_match_points(
            room_id,
            user_id,
            amount
        )

    else:

        success = add_room_points(
            room_id,
            user_id,
            amount
        )

    if not success:
        return False, "ポイントの追加に失敗しました"

    # 更新後のポイントを取得
    updated_stats = get_room_user_stats(
        room_id,
        user_id
    )

    if not updated_stats:
        return False, "更新後のポイント情報を取得できません"

    total = int(
        updated_stats.get("total_points", 0)
    )

    current = int(
        updated_stats.get("current_points", 0)
    )

    return total, current


# =====================================
# ポイント消費
# =====================================

def consume_point(user_id, amount=50):
    """
    ユーザーのポイントを消費する。

    試合中:
        試合成績とルームポイントを更新

    試合外:
        ルームポイントを更新

    Returns
    -------
    tuple:
        (成功したか, 現在ポイントまたはエラー情報)
    """

    valid, error = validate_amount(amount)

    if not valid:
        return False, error

    room_id, stats = get_point_context(user_id)

    if not room_id:
        return False, "所属ルームが見つかりません"

    if not stats:
        return False, "ルームのポイント情報が見つかりません"

    current = int(
        stats.get("current_points", 0)
    )

    # ポイント不足確認
    if current < amount:
        return False, current

    # 試合中か確認
    match = get_active_match(room_id)

    if match:

        success = consume_match_points(
            room_id,
            user_id,
            amount
        )

    else:

        success = consume_room_points(
            room_id,
            user_id,
            amount
        )

    if not success:
        return False, "ポイントの消費に失敗しました"

    # 更新後のポイントを取得
    updated_stats = get_room_user_stats(
        room_id,
        user_id
    )

    if not updated_stats:
        return False, "更新後のポイント情報を取得できません"

    current = int(
        updated_stats.get("current_points", 0)
    )

    return True, current
