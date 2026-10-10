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


def create_user(user_id, name):

    user = get_user(user_id)

    if user:
        return

    supabase.table("users").insert({
        "user_id": user_id,
        "name": name,
        "total_points": 0,
        "current_points": 0,
        "used_count": 0
    }).execute()


def update_name(user_id, name):

    supabase.table("users").update({
        "name": name
    }).eq(
        "user_id",
        user_id
    ).execute()


def update_user(
    user_id,
    total_points,
    current_points,
    used_count
):

    supabase.table(
        "users"
    ).update({
        "total_points": total_points,
        "current_points": current_points,
        "used_count": used_count
    }).eq(
        "user_id",
        user_id
    ).execute()


def get_ranking():

    result = (
        supabase.table("users")
        .select("*")
        .order(
            "total_points",
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
