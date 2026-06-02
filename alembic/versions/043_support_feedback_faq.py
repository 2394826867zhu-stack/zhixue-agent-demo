"""E-05/06/07 · 自建客服(support_threads/messages) + 用户反馈(feedback) + 帮助中心 FAQ(faq_items)。

附带 FAQ 初始种子内容（5 分类，13 条），上线即有可读帮助中心。
"""
import uuid
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "043"
down_revision = "042"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---- E-05 客服会话 ----
    op.create_table(
        "support_threads",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("subject", sa.String(200), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="open", index=True),
        sa.Column("last_message_at", sa.DateTime(timezone=True), server_default=sa.func.now(), index=True),
        sa.Column("user_last_read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_support_threads_user_last_msg",
        "support_threads", ["user_id", sa.text("last_message_at DESC")],
    )

    # ---- E-05 客服消息 ----
    op.create_table(
        "support_messages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("thread_id", UUID(as_uuid=True),
                  sa.ForeignKey("support_threads.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("sender", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), index=True),
    )

    # ---- E-07 用户反馈 ----
    op.create_table(
        "feedback",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("category", sa.String(30), nullable=False, server_default="other"),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("screenshot_url", sa.String(300), nullable=True),
        sa.Column("device_info", sa.JSON(), nullable=True),
        sa.Column("app_version", sa.String(20), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="open", index=True),
        sa.Column("admin_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), index=True),
    )

    # ---- E-06 帮助中心 FAQ ----
    faq = op.create_table(
        "faq_items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("category", sa.String(50), nullable=False, index=True),
        sa.Column("question", sa.String(300), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_published", sa.Boolean(), nullable=False, server_default=sa.true(), index=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # FAQ 种子内容（管家口吻，覆盖主要使用场景）
    seed = [
        # 账号与登录
        ("账号与登录", "如何修改我的资料？", "在「我的 → 偏好设置」里可以调整昵称、年级、目标等信息，修改后会即时生效。"),
        ("账号与登录", "忘记密码了怎么办？", "在登录页点击「忘记密码」，按提示用注册邮箱重置即可。如仍有问题可在帮助中心发起客服会话。"),
        ("账号与登录", "可以在多台设备上登录吗？", "可以。用同一个账号登录，你的学习数据会自动同步，闪卡、错题、项目进度在各设备保持一致。"),
        # 学习与复习
        ("学习与复习", "知曜是怎么决定我先学什么的？", "知曜会根据你的掌握度、闪卡到期情况和先修知识图谱，自动排出推荐学习动作，你也可以在学习页看到每条推荐的理由。"),
        ("学习与复习", "闪卡的复习时间是怎么算的？", "我们用 FSRS 间隔重复算法，根据你每次复习时选择的「重来/困难/良好/容易」动态安排下次复习时间，越熟的卡间隔越长。"),
        ("学习与复习", "错题会自动收集吗？", "会。训练中答错的题目会自动进入错题本，并生成「孪生题」帮你针对性重练，直到真正掌握。"),
        # 订阅与会员
        ("订阅与会员", "Pro 会员有哪些权益？", "Pro 解锁无限次 Agent 对话、AI 周报、知识库文件上传等高级功能。在「我的 → 订阅管理」可查看完整权益与到期日。"),
        ("订阅与会员", "如何管理或取消订阅？", "订阅由 App Store / Google Play 管理，请在对应商店的「订阅」设置中操作。取消后 Pro 权益会在当前周期结束时自然失效。"),
        ("订阅与会员", "教育授权（edu）是什么？", "edu 是由管理员手动授予的教育版权限，永不过期，享有与 Pro 相同的功能权益。"),
        # 数据与隐私
        ("数据与隐私", "我的学习数据会被用来做什么？", "你的数据仅用于为你提供个性化学习服务，我们对身份证、手机号等敏感信息做了脱敏处理，不会用于与学习无关的用途。"),
        ("数据与隐私", "可以导出我的数据吗？", "可以。在「我的 → 数据导出」中可将闪卡、错题导出为 JSON 或 CSV 文件。"),
        # 反馈与帮助
        ("反馈与帮助", "遇到 bug 或有建议怎么反馈？", "在帮助中心点「意见反馈」，填写描述并可附上截图，我们会带着设备信息一起收到，方便快速定位问题。"),
        ("反馈与帮助", "联系客服多久能得到回复？", "提交后系统会立即回执确认，人工客服会在工作时间内尽快回复。你可以在「我的客服会话」中查看进度。"),
    ]
    op.bulk_insert(
        faq,
        [
            {
                "id": uuid.uuid4(),
                "category": cat,
                "question": q,
                "answer": a,
                "sort_order": i,
                "is_published": True,
            }
            for i, (cat, q, a) in enumerate(seed)
        ],
    )


def downgrade() -> None:
    op.drop_table("faq_items")
    op.drop_table("feedback")
    op.drop_table("support_messages")
    op.drop_index("ix_support_threads_user_last_msg", table_name="support_threads")
    op.drop_table("support_threads")
