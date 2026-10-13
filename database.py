import os
from supabase import create_client

supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)


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
        "used_count": 0
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


def transfer_points(
    sender_id,
    receiver_name,
    amount
):

    sender = get_user(sender_id)

    receiver = get_user_by_name(
        receiver_name
    )

    if not receiver:
        return False, "ユーザーが見つかりません"

    if amount <= 0:
        return False, "1以上を入力してください"

    if sender["current_points"] < amount:
        return False, "ポイント不足"

    supabase.table(
        "users"
    ).update({
        "current_points":
        sender["current_points"] - amount
    }).eq(
        "user_id",
        sender_id
    ).execute()

    supabase.table(
        "users"
    ).update({
        "current_points":
        receiver["current_points"] + amount
    }).eq(
        "user_id",
        receiver["user_id"]
    ).execute()

    return True, receiver


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


def reset_all_points():

    supabase.table("users").update({
        "total_points": 0,
        "current_points": 0,
        "used_count": 0
    }).neq(
        "user_id",
        ""
    ).execute()

def add_oni_count(user_id):

    user = get_user(user_id)

    count = user["oni_count"] + 1

    supabase.table("users").update({
        "oni_count": count
    }).eq(
        "user_id",
        user_id
    ).execute()

    return count
