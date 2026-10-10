from database import (
    get_user,
    update_user
)

def add_point(user_id):

    user = get_user(user_id)

    total = user["total_points"] + 1
    current = user["current_points"] + 1
    used = user["used_count"]

    update_user(
        user_id,
        total,
        current,
        used
    )

    return total, current


def consume_point(user_id):

    user = get_user(user_id)

    total = user["total_points"]
    current = user["current_points"]
    used = user["used_count"]

    if current < 50:
        return False, current

    current -= 50
    used += 1

    update_user(
        user_id,
        total,
        current,
        used
    )

    return True, current
