from events import TOPIC_STREAM_METADATA, StreamMetadataEvent
from safety import PassThroughSafetyFilter

from sub_llm.config import LlmSubscriberConfig
from sub_llm.ask_response import AskResponse
from sub_llm.context_buffer import LiveContextBuffer
from sub_llm.handler import LlmSubscriber
from sub_llm.knowledge import EmptyKnowledgeStore
from game_info.models import GameReviewInfo


def _chat_payload(content: str) -> dict:
    from events import TOPIC_CHAT_MESSAGE, ChatMessageEvent

    return ChatMessageEvent(
        schema_version=1,
        topic=TOPIC_CHAT_MESSAGE,
        platform="twitch",
        message_id="msg-game-1",
        author_name="viewer",
        author_id="viewer-id",
        content=content,
        timestamp="2026-06-13T10:00:00+00:00",
        channel="demo_channel",
    ).to_dict()


class CapturingLlm:
    def __init__(self) -> None:
        self.last_game_reference = ""

    def ask(
        self,
        question: str,
        *,
        context: str,
        knowledge: str = "",
        game_reference: str = "",
        session_recap_reference: str = "",
    ) -> AskResponse:
        self.last_game_reference = game_reference
        return AskResponse(reply="ok")


class StubGameProvider:
    def lookup(self, game_name: str) -> GameReviewInfo | None:
        return GameReviewInfo(
            name=game_name,
            summary="Viking tactics.",
            critic_score=81.0,
            user_score=72.0,
            genres=("Strategy",),
            release_year=2018,
        )


def test_handler_injects_game_reference_for_game_question() -> None:
    llm = CapturingLlm()
    subscriber = LlmSubscriber(
        config=LlmSubscriberConfig(trigger_prefixes=["!ask"]),
        llm=llm,
        safety=PassThroughSafetyFilter(),
        knowledge=EmptyKnowledgeStore(),
        context_buffer=LiveContextBuffer(window_minutes=5),
        publish=lambda topic, payload: None,
        game_info=StubGameProvider(),
    )
    subscriber.handle(
        StreamMetadataEvent(
            schema_version=1,
            topic=TOPIC_STREAM_METADATA,
            platform="twitch",
            channel="demo_channel",
            timestamp="2026-06-13T10:00:00+00:00",
            snapshot_id="meta-game",
            is_live=True,
            title="工作實況",
            game_name="Bad North",
            duration_seconds=3600,
        ).to_dict()
    )
    subscriber.handle(_chat_payload("!ask 這遊戲好玩嗎"))

    assert "【遊戲資料參考：Bad North】" in llm.last_game_reference
    assert "媒體評分" in llm.last_game_reference
