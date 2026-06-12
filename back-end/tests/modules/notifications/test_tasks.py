import uuid

import pytest

from app.modules.notifications import tasks


class TestSendPushTask:
    def test_parses_user_id_and_returns_count(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured: dict[str, object] = {}

        async def _stub(
            _session: object, user_id: object, title: object, body: object, data: object
        ) -> int:
            captured["user_id"] = user_id
            captured["title"] = title
            captured["body"] = body
            captured["data"] = data
            return 3

        monkeypatch.setattr(tasks.services, "send_push_to_user", _stub)

        uid = uuid.uuid4()
        result = tasks.send_push_to_user_task(str(uid), "Título", "Corpo", {"k": "v"})

        assert result == 3
        assert captured["user_id"] == uid
        assert captured["title"] == "Título"
        assert captured["data"] == {"k": "v"}

    def test_has_time_limits_declared(self) -> None:
        # CLAUDE.md rule 4/10: every Celery task must bound its runtime.
        assert tasks.send_push_to_user_task.time_limit is not None
        assert tasks.send_push_to_user_task.soft_time_limit is not None
