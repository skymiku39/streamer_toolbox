TOPIC_CHAT_MESSAGE = "chat.message"
TOPIC_CHAT_REPLY = "chat.reply"
TOPIC_STT_SEGMENT = "stt.segment"
TOPIC_STREAM_METADATA = "stream.metadata"
TOPIC_STT_STATUS = "stt.status"
TOPIC_STT_ERROR = "stt.error"
TOPIC_CHARACTER_TURN = "character.turn"
TOPIC_CHARACTER_AUDIO_READY = "character.audio.ready"
TOPIC_CHARACTER_EXPRESSION_READY = "character.expression.ready"
TOPIC_EVENTSUB_PREFIX = "eventsub."
TOPIC_SYSTEM_ERROR = "system.error"
TOPIC_MEMORY_SUMMARIZE_REQUEST = "memory.summarize.request"
TOPIC_MEMORY_SUMMARY_READY = "memory.summary.ready"
TOPIC_MEMORY_QA_RECORD = "memory.qa.record"
TOPIC_CONFIG_CHANGED = "config.changed"
TOPIC_CONTROL_PROFILE_SWITCH = "control.profile.switch"
TOPIC_CONTROL_LLM_PERSONA = "control.llm.persona"
TOPIC_OVERLAY_UPDATE = "overlay.update"
TOPIC_CONTROL_MODULE_ENABLE = "control.module.enable"

SOURCE_LOGIC_COMMANDS = "logic-commands"
SOURCE_LOGIC_KEYWORDS = "logic-keywords"
SOURCE_LOGIC_EVENTS = "logic-events"
SOURCE_LOGIC_LLM = "logic-llm"
SOURCE_LOGIC_STATUS = "logic-status"
SOURCE_CHARACTER_BRAIN = "character-brain"

REPLY_SOURCES = frozenset(
    {
        SOURCE_LOGIC_COMMANDS,
        SOURCE_LOGIC_KEYWORDS,
        SOURCE_LOGIC_EVENTS,
        SOURCE_LOGIC_LLM,
        SOURCE_LOGIC_STATUS,
        SOURCE_CHARACTER_BRAIN,
    }
)
