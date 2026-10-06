
        print(
            f"{post_type} の"
            "未投稿ストックがありません。"
        )

        # 投稿する価値のない枠を
        # 無理に埋めない
        return False

    text = post.get(
        "text",
        ""
    ).strip()

    if not text:

        print(
            "投稿本文が空です。"
        )

        return False

    image_url = get_image_url_for_post(
        post_type
    )

    buffer_post = post_to_buffer(
        text,
        image_url=image_url
    )

    print(
        f"Buffer ID: "
        f"{buffer_post['id']}"
    )

    # Buffer成功後だけ使用済みにする
    used_posts.append(
        post_id
    )

    # 履歴肥大化防止
    posted["used_posts"] = (
        used_posts[-500:]
    )

    save_posted(posted)

    commit_posted_file()

    print(
        f"{post_type} 投稿完了"
    )

    return True


# ==================================================
# MAIN
# ==================================================

def main():

    now = datetime.now(JST)

    hour = now.hour
    minute = now.minute

    print(
        f"現在時刻 JST: {now}"
    )

    print(
        f"実行時刻: {hour:02d}:{minute:02d}"
    )

    posted = load_posted()

    # GitHub Actionsは数分遅れて
    # 起動する場合があるため、
    # 「時」を中心に投稿枠を判定する。
    #
    # 同じ時刻に複数枠は設定しない。

    schedule_by_hour = {
        8: "player",
        10: "compare",
        12: "data",
        15: "analysis",
        18: "news",
        21: "vote",
        23: "review",
    }

    post_type = schedule_by_hour.get(
        hour
    )

    if post_type is None:

        print(
            "現在は投稿時間ではありません。"
        )

        return

    print(
        f"今回の投稿タイプ: {post_type}"
    )

    # ----------------------------------------------
    # 18時：重要ニュース
    # ----------------------------------------------

    if post_type == "news":

        handle_news(
            posted
        )

        return

    # ----------------------------------------------
    # その他6枠
    # ----------------------------------------------

    handle_stock_post(
