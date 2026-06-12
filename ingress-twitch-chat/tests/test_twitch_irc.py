from ingress_twitch_chat.twitch_irc import parse_privmsg


def test_parse_privmsg_with_tags() -> None:
    line = (
        "@badge-info=;badges=;client-nonce=abc;display-name=Viewer;"
        "id=msg-001;user-id=999;emotes= :viewer!viewer@viewer.tmi.twitch.tv "
        "PRIVMSG #skymiku39 :hello world"
    )
    msg = parse_privmsg(line)
    assert msg is not None
    assert msg.channel == "skymiku39"
    assert msg.username == "Viewer"
    assert msg.login == "viewer"
    assert msg.content == "hello world"
    assert msg.message_id == "msg-001"
    assert msg.author_id == "999"
