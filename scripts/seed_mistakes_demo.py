"""一次性 demo 错题种子（用于前端错题本 UI 验证）。

为指定用户写入 1 个知识点 + 若干条 is_wrong=True / is_retry=False 的训练题，
覆盖不同 question_type / ai_score（含 null=评分中）/ ai_feedback，
用真实数据验证 MistakeListScreen / MistakePracticeScreen 渲染。

幂等：按 question_text 去重，已存在则跳过。

用法：python -m scripts.seed_mistakes_demo [email]
"""
import asyncio
import sys
import uuid

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.user import User
from app.models.knowledge_point import KnowledgePoint
from app.models.training import TrainingQuestion

EMAIL = sys.argv[1] if len(sys.argv) > 1 else "test@zhiyao.com"

# (question_type, bloom_level, question_text, reference_answer, user_answer, ai_score, ai_feedback)
SEED = [
    ("calculation", "apply",
     "求函数 f(x)=x^2 在 x=1 处的导数。",
     "f'(x)=2x，故 f'(1)=2。",
     "f'(1)=1", 35,
     "导数公式套用正确，但代入时把 2x 算成了 x，注意幂函数求导 (x^n)'=n·x^(n-1)。"),
    ("short_answer", "understand",
     "用一句话说明牛顿第二定律的含义。",
     "物体加速度与所受合外力成正比、与质量成反比，方向与合外力一致（F=ma）。",
     "力等于质量", 60,
     "抓住了 F 与 m 的关系，但漏了加速度 a 和方向，表述不完整。"),
    ("choice", "remember",
     "下列哪个是细胞的能量工厂？A.细胞核 B.线粒体 C.核糖体 D.高尔基体",
     "B. 线粒体",
     "C", 0,
     "线粒体通过有氧呼吸合成 ATP，是细胞的能量工厂；核糖体负责合成蛋白质。"),
    ("proof", "analyze",
     "证明：两个偶数之和仍为偶数。",
     "设两偶数为 2m、2n，则 2m+2n=2(m+n)，仍能被 2 整除，故为偶数。",
     None, None, None),  # 未评分 → 验证「评分中」态
]


async def main() -> None:
    async with AsyncSessionLocal() as db:
        user = (await db.execute(select(User).where(User.email == EMAIL))).scalar_one_or_none()
        if not user:
            print(f"用户不存在：{EMAIL}")
            return

        # 复用或创建一个 demo 知识点（带 subject 以便 stats.by_subject 有真值）
        kp = (await db.execute(
            select(KnowledgePoint).where(
                KnowledgePoint.user_id == user.id,
                KnowledgePoint.name == "错题本 Demo 知识点",
            )
        )).scalar_one_or_none()
        if not kp:
            kp = KnowledgePoint(
                id=uuid.uuid4(), user_id=user.id, name="错题本 Demo 知识点",
                subject="math", bloom_level="apply", mastery_status="learning",
            )
            db.add(kp)
            await db.flush()
            print(f"建知识点 {kp.id}")

        created = 0
        for qtype, bloom, qtext, ref, uans, score, fb in SEED:
            exists = (await db.execute(
                select(TrainingQuestion).where(
                    TrainingQuestion.user_id == user.id,
                    TrainingQuestion.question_text == qtext,
                )
            )).scalar_one_or_none()
            if exists:
                continue
            db.add(TrainingQuestion(
                id=uuid.uuid4(), user_id=user.id, knowledge_point_id=kp.id,
                bloom_level=bloom, question_type=qtype,
                question_text=qtext, reference_answer=ref, user_answer=uans,
                ai_score=score, ai_feedback=fb,
                is_wrong=True, is_retry=False,
            ))
            created += 1

        await db.commit()
        print(f"新建错题 {created} 条（用户 {EMAIL}）")


if __name__ == "__main__":
    asyncio.run(main())
