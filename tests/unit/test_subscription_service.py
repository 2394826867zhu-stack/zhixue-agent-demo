def test_subscription_event_model_importable():
    from app.models.subscription_event import SubscriptionEvent
    assert SubscriptionEvent.__tablename__ == "subscription_events"
