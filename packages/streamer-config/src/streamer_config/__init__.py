"""外部設定目錄契約（方案 A）：路徑解析、bootstrap、驗證。"""

from streamer_config.bootstrap import BootstrapResult, ensure_layout
from streamer_config.paths import ConfigPaths, repo_root, resolve_path
from streamer_config.validate import ValidationError, validate_all, validate_file

__all__ = [
    "BootstrapResult",
    "ConfigPaths",
    "ValidationError",
    "ensure_layout",
    "repo_root",
    "resolve_path",
    "validate_all",
    "validate_file",
]
