import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import bymacclbot


class CommandHandlersTests(unittest.IsolatedAsyncioTestCase):
    async def test_cmd_ini_saves_start_date_and_replies(self):
        chat_id = 123
        message = SimpleNamespace(reply_text=AsyncMock())
        update = SimpleNamespace(
            effective_chat=SimpleNamespace(id=chat_id),
            message=message,
        )
        context = SimpleNamespace(args=["2015-01-01"])

        with patch("bymacclbot.set_date", autospec=True) as mock_set_date:
            await bymacclbot.cmd_ini(update, context)
            mock_set_date.assert_called_once_with(chat_id, "start", "2015-01-01")

        message.reply_text.assert_awaited_once_with(
            "Fecha inicial guardada: 2015-01-01"
        )

    async def test_cmd_fin_saves_end_date_and_replies(self):
        chat_id = 456
        message = SimpleNamespace(reply_text=AsyncMock())
        update = SimpleNamespace(
            effective_chat=SimpleNamespace(id=chat_id),
            message=message,
        )
        context = SimpleNamespace(args=["2020-12-31"])

        with patch("bymacclbot.set_date", autospec=True) as mock_set_date:
            await bymacclbot.cmd_fin(update, context)
            mock_set_date.assert_called_once_with(chat_id, "end", "2020-12-31")

        message.reply_text.assert_awaited_once_with(
            "Fecha final guardada: 2020-12-31"
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
