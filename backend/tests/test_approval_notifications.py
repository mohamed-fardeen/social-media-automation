from unittest.mock import patch, MagicMock

from app.services.approval_notifications import build_approval_payload, send_approval_notification


def test_build_approval_payload_uses_expected_actions():
    payload = build_approval_payload(
        draft={"id": "draft_1", "platform": "instagram", "caption": "Hello", "hashtags": ["#a"], "status": "pending_approval"},
        run_id="run_1",
        channel="telegram",
        contact="12345",
    )

    assert payload["run_id"] == "run_1"
    assert payload["draft_id"] == "draft_1"
    assert [a["action"] for a in payload["actions"]] == ["approve", "regenerate", "reject"]


@patch("app.services.approval_notifications.send_message", return_value=True)
@patch("app.services.approval_notifications.send_photo", return_value=False)
def test_send_approval_notification_posts_to_telegram(mock_send_photo, mock_send_message):
    ok = send_approval_notification(
        bot_token="fake_token",
        chat_id="12345",
        draft={"id": "draft_1", "platform": "linkedin", "caption": "Hello", "hashtags": [], "status": "pending_approval", "image_url": None},
        run_id="run_1",
    )

    assert ok is True
    mock_send_message.assert_called_once()
