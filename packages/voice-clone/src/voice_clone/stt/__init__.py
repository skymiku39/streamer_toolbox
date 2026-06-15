"""離線 STT（faster-whisper），供 clone --stt 使用。"""

from voice_clone.stt.config import SttConfig
from voice_clone.stt.segment import TranscriptSegment

__all__ = ["SttConfig", "TranscriptSegment"]
