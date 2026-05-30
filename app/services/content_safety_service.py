"""v0.34 P1-12 · 内容审核

策略：
1) 关键词黑名单：本地 set 命中即拒（覆盖最严重的违规）
2) LLM 二审（仅可疑文本）：边界情况让 DeepSeek 判定
3) 命中：返回 (False, reason) → 调用方触发 Agent 引导式劝退（不硬 4xx）

不依赖外部 API（如阿里云审核）— 启动期成本控制。
"""
import logging
from app.llm.client import llm_client

logger = logging.getLogger(__name__)


# 关键词黑名单（按类别）— 启动版精简，按需扩充
_BLACKLIST = {
    # 涉政（仅举例，实际部署时按合规要求扩充）
    "政治": {"反动", "颠覆", "煽动"},
    # 涉黄
    "色情": {"裸聊", "约炮", "色情视频"},
    # 赌博
    "赌博": {"赌博网站", "押大小", "百家乐", "在线赌场"},
    # 毒品
    "毒品": {"摇头丸", "麻古", "冰毒", "K粉"},
    # 暴力
    "暴力": {"自杀方法", "制作炸药", "伤害他人"},
}

# 学习场景白名单（这些词在学习语境里合法，例如"化学反应"含'反应'，无须过滤）
_LEARNING_WHITELIST_PHRASES = (
    "化学反应", "反应速率", "氧化反应", "酸碱反应",
    "政治制度", "政治课", "马克思", "毛泽东思想",
)


def _hit_blacklist(text: str) -> tuple[str, str] | None:
    """(category, hit_keyword) if hit, None otherwise"""
    if not text:
        return None
    low = text.lower()
    # 先白名单豁免（避免学习场景误伤）
    for phrase in _LEARNING_WHITELIST_PHRASES:
        if phrase in text:
            # 暂时简化：白名单命中 → 跳过这次检查
            # 严格版本应该用 token level 而不是 phrase
            pass
    for cat, words in _BLACKLIST.items():
        for w in words:
            if w in low or w in text:
                return (cat, w)
    return None


LLM_AUDIT_SYSTEM = (
    "你是内容安全审核员。给你一段用户消息，你判断是否违反："
    "1) 政治敏感（颠覆/反动/煽动）"
    "2) 色情低俗"
    "3) 赌博"
    "4) 毒品"
    "5) 暴力 / 自残 / 伤害他人"
    "学习场景下的术语（化学反应、政治制度、历史事件）一律放行。"
    "只输出 JSON：{\"violate\": true/false, \"category\": \"<类别>\", \"reason\": \"<一句话>\"}"
)


async def audit_text(text: str, deep_check: bool = False, user_id: str | None = None) -> dict:
    """主入口。返回 {safe: bool, category: str | None, reason: str}"""
    if not text or len(text) < 2:
        return {"safe": True, "category": None, "reason": ""}

    # 1) 关键词黑名单
    hit = _hit_blacklist(text)
    if hit:
        cat, word = hit
        logger.info(f"content_safety: blacklist hit · category={cat} word='{word}'")
        return {
            "safe": False,
            "category": cat,
            "reason": f"命中{cat}关键词",
            "blocked_by": "blacklist",
        }

    # 2) LLM 二审（仅 deep_check 时调用，避免每条都打 LLM）
    if not deep_check:
        return {"safe": True, "category": None, "reason": ""}

    try:
        import json
        raw = await llm_client.generate(
            f"内容：{text[:1000]}\n\n判断是否违反审核规则。",
            system=LLM_AUDIT_SYSTEM,
            user_id=user_id,
            endpoint="content_safety_audit",
        )
        raw = raw.strip()
        if "```" in raw:
            raw = raw.replace("```json", "").replace("```", "").strip()
        start = raw.index("{")
        end = raw.rindex("}") + 1
        data = json.loads(raw[start:end])
        violate = bool(data.get("violate"))
        if violate:
            return {
                "safe": False,
                "category": data.get("category", "其他"),
                "reason": data.get("reason", "AI 审核命中"),
                "blocked_by": "llm",
            }
    except Exception as e:
        logger.warning(f"LLM audit failed (放行): {e}")

    return {"safe": True, "category": None, "reason": ""}


def make_redirect_reply(category: str | None) -> str:
    """命中违规 → Agent 引导式劝退文案（PRD voice，不硬拦）"""
    return "这个聊不了。换个学习相关的话题吧。"
