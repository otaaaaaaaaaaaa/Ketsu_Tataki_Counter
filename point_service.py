
from database import (
    get_user,
    update_user
)


# =====================================
# ポイント獲得
# =====================================

def add_point(user_id, amount=1):
    """
    ユーザーにポイントを追加する。

    Parameters
    ----------
    user_id : str
        LINEユーザーID

    amount : int
        追加するポイント数
        省略した場合は1ポイント

    Returns
    -------
    tuple
        (累計ポイント, 現在ポイント)

        失敗した場合は (False, エラーメッセージ)
    """

    if not isinstance(amount, int) or isinstance(amount, bool):
        return False, "ポイント数は整数で指定してください"

    if amount <= 0:
        return False, "1以上のポイントを指定してください"

    user = get_user(user_id)

    if not user:
        return False, "ユーザーが見つかりません"

    total = int(user.get("total_points", 0))
    current = int(user.get("current_points", 0))
    used = int(user.get("used_count", 0))

    total += amount
    current += amount

    update_user(
        user_id,
        total,
        current,
        used
    )

    return total, current


# =====================================
# ポイント消費
# =====================================

def consume_point(user_id, amount=50):
    """
    ユーザーのポイントを消費する。

    Parameters
    ----------
    user_id : str
        LINEユーザーID

    amount : int
        消費するポイント数
        省略した場合は50ポイント

    Returns
    -------
    tuple
        (成功したか, 現在ポイントまたはエラー情報)
    """

    if not isinstance(amount, int) or isinstance(amount, bool):
        return False, "消費ポイント数は整数で指定してください"

    if amount <= 0:
        return False, "1以上のポイントを指定してください"

    user = get_user(user_id)

    if not user:
        return False, "ユーザーが見つかりません"

    total = int(user.get("total_points", 0))
    current = int(user.get("current_points", 0))
    used = int(user.get("used_count", 0))

    # ポイント不足確認
    if current < amount:
        return False, current

    # ポイント消費
    current -= amount
    used += 1

    update_user(
        user_id,
        total,
        current,
        used
    )

    return True, current
