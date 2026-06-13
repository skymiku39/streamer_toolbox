"""LLM 問答 Subscriber：訂閱 chat.message、stt.segment，發布 chat.reply。

回覆在 safety 過濾後以 plain_text_for_chat 去除 Markdown，適合 Twitch 聊天室顯示。
"""
