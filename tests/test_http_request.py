import unittest
from unittest.mock import Mock, patch

from adapter.http_request import (
    NapCatHttpActionError,
    quit_group,
    upload_group_file,
)


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

    def test_upload_group_file_uses_path_and_extended_timeout(self):
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
            "6543",
        ), patch(
            "adapter.http_request.TOKEN",
            "fixture-token",
        ):
            result = upload_group_file(123, "video.mp4", "/tmp/video.mp4")

        request.assert_called_once_with(
            "POST",
            "http://127.0.0.1:6543/upload_group_file",
            headers={"Authorization": "Bearer fixture-token"},
            json={
                "group_id": "123",
                "file": "/tmp/video.mp4",
                "name": "video.mp4",
            },
            timeout=(3, 120),
        )
        self.assertEqual(result["retcode"], 0)

    def test_onebot_failure_response_is_not_treated_as_success(self):
        response = Mock()
        response.json.return_value = {
            "status": "failed",
            "retcode": 1200,
            "message": "fixture failure",
        }

        with patch(
            "adapter.http_request.requests.request",
            return_value=response,
        ):
            with self.assertRaises(NapCatHttpActionError):
                quit_group(123)


if __name__ == "__main__":
    unittest.main()
