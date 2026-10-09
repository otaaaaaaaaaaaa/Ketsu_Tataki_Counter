from database import (
    get_user,
    update_points
)


def add_point(user_id):

    user = get_user(user_id)

    total_points = user[2] + 1
    current_points = user[3] + 1
    used_count = user[4]

    update_points(
        user_id,
        total_points,
        current_points,
        used_count
    )

    return total_points, current_points


def consume_point(user_id):

    user = get_user(user_id)

    total_points = user[2]
    current_points = user[3]
    used_count = user[4]

    if current_points < 50:
        return False, current_points

    current_points -= 50
    used_count += 1

    update_points(
        user_id,
        total_points,
        current_points,
        used_count
    )

    return True, current_points
