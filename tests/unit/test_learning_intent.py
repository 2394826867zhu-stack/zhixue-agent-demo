# tests/unit/test_learning_intent.py
from app.services.learning_intent import classify_learning_intent


def test_explicit_start_learning():
    assert classify_learning_intent("帮我学高数") is True


def test_review_trigger():
    assert classify_learning_intent("复习今天的内容") is True


def test_do_practice_trigger():
    assert classify_learning_intent("给我出几道练习题") is True


def test_quiz_trigger():
    assert classify_learning_intent("测一测我的掌握情况") is True


def test_arrangement_trigger():
    assert classify_learning_intent("今天该学什么") is True


def test_greeting_not_learning():
    assert classify_learning_intent("你好") is False


def test_explain_question_not_learning():
    assert classify_learning_intent("什么是微分？") is False


def test_why_question_not_learning():
    assert classify_learning_intent("为什么要学导数") is False


def test_empty_message_not_learning():
    assert classify_learning_intent("") is False


def test_negative_sentiment_review_not_learning():
    assert classify_learning_intent("我不想复习") is False


def test_complaint_review_not_learning():
    assert classify_learning_intent("复习好累啊") is False
