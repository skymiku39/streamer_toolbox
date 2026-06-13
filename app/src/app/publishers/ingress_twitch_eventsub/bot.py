from __future__ import annotations

import logging

from twitchio import eventsub
from twitchio.ext import commands
from twitchio.models.eventsub_ import (
    AutomodMessageHold,
    AutomodMessageUpdate,
    ChannelBan,
    ChannelBitsUse,
    ChannelFollow,
    ChannelPointsRedemptionAdd,
    ChannelPollBegin,
    ChannelPollEnd,
    ChannelPollProgress,
    ChannelPredictionBegin,
    ChannelPredictionEnd,
    ChannelPredictionLock,
    ChannelPredictionProgress,
    ChannelRaid,
    ChannelSubscribe,
    ChannelSubscriptionGift,
    ChannelSubscriptionMessage,
    ChannelUnban,
    ChatMessage,
    ChatMessageDelete,
    HypeTrainBegin,
    HypeTrainEnd,
    HypeTrainProgress,
    StreamOffline,
    StreamOnline,
)

from ingress_twitch_eventsub.chat_status import (
    CHAT_FALLBACK_EXIT_CODE,
    CHAT_INGRESS_EVENTSUB,
    CHAT_INGRESS_IRC_FALLBACK,
    CHAT_INGRESS_STATUS_PREFIX,
)
from ingress_twitch_eventsub.first_chat import FirstChatTracker
from ingress_twitch_eventsub.normalize import (
    chat_message_from_eventsub,
    eventsub_from_automod_hold,
    eventsub_from_automod_update,
    eventsub_from_ban,
    eventsub_from_bits,
    eventsub_from_first_chat,
    eventsub_from_follow,
    eventsub_from_hype_train_begin,
    eventsub_from_hype_train_end,
    eventsub_from_hype_train_progress,
    eventsub_from_message_delete,
    eventsub_from_poll_begin,
    eventsub_from_poll_end,
    eventsub_from_poll_progress,
    eventsub_from_prediction_begin,
    eventsub_from_prediction_end,
    eventsub_from_prediction_lock,
    eventsub_from_prediction_progress,
    eventsub_from_raid,
    eventsub_from_redemption,
    eventsub_from_stream_offline,
    eventsub_from_stream_online,
    eventsub_from_subscribe,
    eventsub_from_subscription_gift,
    eventsub_from_subscription_message,
    eventsub_from_unban,
)
from ingress_twitch_eventsub.publisher import EventPublisher
from ingress_twitch_eventsub.subscriptions import AFFILIATE_ONLY_SUBS, build_subscription_list

logger = logging.getLogger(__name__)


class EventSubIngressBot(commands.Bot):
    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        bot_id: str,
        token: str,
        refresh_token: str,
        channels: list[str],
        broadcaster_id: str,
        broadcaster_type: str,
        publisher: EventPublisher,
    ) -> None:
        super().__init__(
            client_id=client_id,
            client_secret=client_secret,
            bot_id=bot_id,
            owner_id=broadcaster_id,
            prefix="!",
        )
        self.user_access_token = token
        self.user_refresh_token = refresh_token
        self.broadcaster_id = broadcaster_id
        self.broadcaster_type = broadcaster_type
        self.bot_channels = channels
        self._publisher = publisher
        self._first_chat = FirstChatTracker()
        self.chat_read_ok = False
        self._failed_subs: list[tuple] = []

    async def setup_hook(self) -> None:
        await self.add_token(self.user_access_token, self.user_refresh_token)
        await self._register_all_subscriptions()

    async def _register_all_subscriptions(self) -> None:
        is_affiliate_or_partner = self.broadcaster_type in ("affiliate", "partner")
        subs = build_subscription_list(
            broadcaster_id=self.broadcaster_id,
            bot_id=str(self.bot_id),
        )
        ok, fail, skip = 0, 0, 0
        self._failed_subs.clear()
        for entry in subs:
            name, payload, required, scope_hint, token_owner = entry
            if not is_affiliate_or_partner and name in AFFILIATE_ONLY_SUBS:
                logger.info("skip %s subscription (channel is not affiliate/partner)", name)
                skip += 1
                continue
            target_id = str(self.bot_id) if token_owner == "bot" else self.broadcaster_id
            success = await self._register_eventsub_subscription(
                subscription_name=name,
                payload=payload,
                token_for=target_id,
                required=required,
                scope_hint=scope_hint,
            )
            if success:
                ok += 1
                if name == "ChatMessage":
                    self.chat_read_ok = True
            else:
                fail += 1
                self._failed_subs.append(entry)
                if name == "ChatMessage":
                    self.chat_read_ok = False
        logger.info("EventSub subscriptions: ok=%d fail=%d skip=%d", ok, fail, skip)

    async def _register_eventsub_subscription(
        self,
        subscription_name: str,
        payload: eventsub.SubscriptionPayload,
        *,
        token_for: str | None = None,
        required: bool = False,
        scope_hint: str | None = None,
    ) -> bool:
        try:
            kwargs: dict[str, object] = {"payload": payload}
            if token_for:
                kwargs["token_for"] = token_for
            await self.subscribe_websocket(**kwargs)
            logger.info("subscribed %s", subscription_name)
            return True
        except Exception as exc:
            scope_suffix = f" (scope: {scope_hint})" if scope_hint else ""
            logger.warning("failed to subscribe %s: %s%s", subscription_name, exc, scope_suffix)
            if required and subscription_name != "ChatMessage":
                raise
            return False

    async def event_ready(self) -> None:
        logger.info("ingress-twitch-eventsub ready for channels: %s", ", ".join(self.bot_channels))
        if self.chat_read_ok:
            print(f"{CHAT_INGRESS_STATUS_PREFIX}{CHAT_INGRESS_EVENTSUB}", flush=True)
            return
        logger.error(
            "ChatMessage EventSub unavailable; requesting IRC fallback via ingress-ttv-read",
        )
        print(f"{CHAT_INGRESS_STATUS_PREFIX}{CHAT_INGRESS_IRC_FALLBACK}", flush=True)
        raise SystemExit(CHAT_FALLBACK_EXIT_CODE)

    async def event_message(self, message: ChatMessage) -> None:
        default_channel = self.bot_channels[0].lstrip("#") if self.bot_channels else ""
        chat_event = chat_message_from_eventsub(message, default_channel=default_channel)
        await self._publisher.publish_chat(chat_event)

        source_broadcaster = getattr(message, "source_broadcaster", None)
        is_shared_chat = source_broadcaster is not None
        chatter = getattr(message, "chatter", None)
        is_bot_self = str(getattr(chatter, "id", "")) == str(self.bot_id)
        is_broadcaster = str(getattr(chatter, "id", "")) == str(self.broadcaster_id)
        if is_bot_self:
            return

        claim = self._first_chat.try_claim(
            channel_name=chat_event.channel or default_channel,
            login=str(getattr(chatter, "name", "") or ""),
            display_name=chat_event.author_name,
            broadcaster_id=self.broadcaster_id,
            is_broadcaster=is_broadcaster,
            is_shared_chat=is_shared_chat,
        )
        if claim is not None:
            first_chat_event = eventsub_from_first_chat(
                broadcaster_id=claim["broadcaster_id"],
                user_id=chat_event.author_id or "",
                user_name=chat_event.login or chat_event.author_name,
                channel=claim["channel"],
                stream_id=claim["stream_id"],
            )
            await self._publisher.publish_eventsub(first_chat_event)

    async def event_stream_online(self, payload: StreamOnline) -> None:
        broadcaster = getattr(payload, "broadcaster", None)
        channel_name = str(getattr(broadcaster, "name", "") or "")
        started_at = getattr(payload, "started_at", None)
        started_value = started_at.isoformat() if hasattr(started_at, "isoformat") else ""
        self._first_chat.arm_session(
            channel_name=channel_name,
            stream_id=str(getattr(payload, "id", "") or ""),
            started_at=started_value,
        )
        await self._publisher.publish_eventsub(eventsub_from_stream_online(payload))

    async def event_stream_offline(self, payload: StreamOffline) -> None:
        broadcaster = getattr(payload, "broadcaster", None)
        channel_name = str(getattr(broadcaster, "name", "") or "")
        self._first_chat.clear_session(channel_name)
        await self._publisher.publish_eventsub(eventsub_from_stream_offline(payload))

    async def event_follow(self, payload: ChannelFollow) -> None:
        await self._publisher.publish_eventsub(eventsub_from_follow(payload))

    async def event_raid(self, payload: ChannelRaid) -> None:
        await self._publisher.publish_eventsub(eventsub_from_raid(payload))

    async def event_subscription(self, payload: ChannelSubscribe) -> None:
        await self._publisher.publish_eventsub(eventsub_from_subscribe(payload))

    async def event_subscription_gift(self, payload: ChannelSubscriptionGift) -> None:
        await self._publisher.publish_eventsub(eventsub_from_subscription_gift(payload))

    async def event_subscription_message(self, payload: ChannelSubscriptionMessage) -> None:
        await self._publisher.publish_eventsub(eventsub_from_subscription_message(payload))

    async def event_custom_redemption_add(self, payload: ChannelPointsRedemptionAdd) -> None:
        await self._publisher.publish_eventsub(eventsub_from_redemption(payload))

    async def event_bits_use(self, payload: ChannelBitsUse) -> None:
        await self._publisher.publish_eventsub(eventsub_from_bits(payload))

    async def event_chat_message_delete(self, payload: ChatMessageDelete) -> None:
        await self._publisher.publish_eventsub(eventsub_from_message_delete(payload))

    async def event_channel_ban(self, payload: ChannelBan) -> None:
        await self._publisher.publish_eventsub(eventsub_from_ban(payload))

    async def event_channel_unban(self, payload: ChannelUnban) -> None:
        await self._publisher.publish_eventsub(eventsub_from_unban(payload))

    async def event_automod_message_hold(self, payload: AutomodMessageHold) -> None:
        await self._publisher.publish_eventsub(eventsub_from_automod_hold(payload))

    async def event_automod_message_update(self, payload: AutomodMessageUpdate) -> None:
        await self._publisher.publish_eventsub(eventsub_from_automod_update(payload))

    async def event_channel_poll_begin(self, payload: ChannelPollBegin) -> None:
        await self._publisher.publish_eventsub(eventsub_from_poll_begin(payload))

    async def event_channel_poll_progress(self, payload: ChannelPollProgress) -> None:
        await self._publisher.publish_eventsub(eventsub_from_poll_progress(payload))

    async def event_channel_poll_end(self, payload: ChannelPollEnd) -> None:
        await self._publisher.publish_eventsub(eventsub_from_poll_end(payload))

    async def event_channel_prediction_begin(self, payload: ChannelPredictionBegin) -> None:
        await self._publisher.publish_eventsub(eventsub_from_prediction_begin(payload))

    async def event_channel_prediction_progress(self, payload: ChannelPredictionProgress) -> None:
        await self._publisher.publish_eventsub(eventsub_from_prediction_progress(payload))

    async def event_channel_prediction_lock(self, payload: ChannelPredictionLock) -> None:
        await self._publisher.publish_eventsub(eventsub_from_prediction_lock(payload))

    async def event_channel_prediction_end(self, payload: ChannelPredictionEnd) -> None:
        await self._publisher.publish_eventsub(eventsub_from_prediction_end(payload))

    async def event_hype_train_begin(self, payload: HypeTrainBegin) -> None:
        await self._publisher.publish_eventsub(eventsub_from_hype_train_begin(payload))

    async def event_hype_train_progress(self, payload: HypeTrainProgress) -> None:
        await self._publisher.publish_eventsub(eventsub_from_hype_train_progress(payload))

    async def event_hype_train_end(self, payload: HypeTrainEnd) -> None:
        await self._publisher.publish_eventsub(eventsub_from_hype_train_end(payload))
