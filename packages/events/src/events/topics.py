TOPIC_CHAT_MESSAGE = "chat.message"
TOPIC_CHAT_REPLY = "chat.reply"
TOPIC_STT_SEGMENT = "stt.segment"
TOPIC_STT_STATUS = "stt.status"
TOPIC_STT_ERROR = "stt.error"
TOPIC_CHARACTER_TURN = "character.turn"
TOPIC_CHARACTER_AUDIO_READY = "character.audio.ready"
TOPIC_CHARACTER_EXPRESSION_READY = "character.expression.ready"
TOPIC_EVENTSUB_PREFIX = "eventsub."
TOPIC_SYSTEM_ERROR = "system.error"
TOPIC_MEMORY_SUMMARIZE_REQUEST = "memory.summarize.request"

SOURCE_LOGIC_COMMANDS = "logic-commands"
SOURCE_LOGIC_KEYWORDS = "logic-keywords"
SOURCE_LOGIC_EVENTS = "logic-events"
SOURCE_LOGIC_LLM = "logic-llm"
SOURCE_CHARACTER_BRAIN = "character-brain"

REPLY_SOURCES = frozenset(
    {
        SOURCE_LOGIC_COMMANDS,
        SOURCE_LOGIC_KEYWORDS,
        SOURCE_LOGIC_EVENTS,
        SOURCE_LOGIC_LLM,
        SOURCE_CHARACTER_BRAIN,
    }
)
