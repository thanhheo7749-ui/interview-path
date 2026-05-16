from app.models import ChatRequest



def test_chat_request_exposes_target_topics_with_empty_default():
    request = ChatRequest(user_text="hello")

    assert request.target_topics == []
