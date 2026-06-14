from sub_llm.prompts import DEFAULT_LLM_SYSTEM_PROMPT, resolve_system_prompt


def test_resolve_system_prompt_uses_default_when_empty(monkeypatch) -> None:
    monkeypatch.delenv("LLM_SYSTEM_PROMPT", raising=False)
    monkeypatch.delenv("LLM_MAX_REPLY_LENGTH", raising=False)
    monkeypatch.setenv("LLM_GENERAL_KNOWLEDGE", "true")
    prompt = resolve_system_prompt()
    assert "通識" in prompt
    assert "不要套公式" in prompt
    assert "繁體中文" in prompt
    assert "200 字" in prompt
    assert prompt == DEFAULT_LLM_SYSTEM_PROMPT


def test_resolve_system_prompt_honors_custom_prompt(monkeypatch) -> None:
    monkeypatch.setenv("LLM_SYSTEM_PROMPT", "自訂助手")
    monkeypatch.setenv("LLM_GENERAL_KNOWLEDGE", "true")
    prompt = resolve_system_prompt()
    assert prompt.startswith("自訂助手")
    assert "繁體中文" in prompt


def test_resolve_system_prompt_strict_mode_disables_general_knowledge(monkeypatch) -> None:
    monkeypatch.setenv("LLM_SYSTEM_PROMPT", "自訂助手")
    monkeypatch.setenv("LLM_GENERAL_KNOWLEDGE", "false")
    prompt = resolve_system_prompt()
    assert prompt.startswith("自訂助手")
    assert "勿使用其他常識" in prompt
