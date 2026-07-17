import unittest
from unittest.mock import Mock, patch

from adapter.http_request import quit_group


class HttpRequestTest(unittest.TestCase):
    def test_quit_group_uses_onebot_field_and_bounded_request(self):
        response = Mock()
        response.json.return_value = {"status": "ok", "retcode": 0}

        with patch(
            "adapter.http_request.requests.request",
            return_value=response,
        ) as request, patch(
            "adapter.http_request.HOST",
            "127.0.0.1",
        ), patch(
            "adapter.http_request.PORT",
            "3457",
        ), patch(
            "adapter.http_request.TOKEN",
            "",
        ):
            result = quit_group(123, is_dismiss=True)

        response.raise_for_status.assert_called_once_with()
        request.assert_called_once_with(
            "POST",
            "http://127.0.0.1:3457/set_group_leave",
            headers={"Authorization": "Bearer "},
            json={"group_id": "123", "is_dismiss": True},
            timeout=(3, 10),
        )
        self.assertEqual(result["retcode"], 0)


if __name__ == "__main__":
    unittest.main()
