import base64
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from requests.exceptions import ReadTimeout

import tools.pic_recognition as pic_recognition
import toogle.adapter as toogle_adapter
from configs import config
from plugins.gpt import GetOpenAIConversation, WhatIs
from plugins.online_ai import GetDoubaoCompose
from toogle.message import Group, Image, Member, MessageChain
from toogle.message_handler import MessagePack


def make_pack(text: str) -> MessagePack:
    return MessagePack(
        id=1,
        message=MessageChain.plain(text),
        group=Group(100, "fixture group"),
        member=Member(200, "fixture member"),
        quote=None,
        message_type="group",
    )


class ArchivedFixTest(unittest.IsolatedAsyncioTestCase):
    def test_empty_picture_hash_is_never_added_or_matched(self):
        with patch.object(
            pic_recognition,
            "get_pic_average_hash",
            return_value="",
        ), patch.object(pic_recognition.SHIT_BLOOM, "add") as add:
            pic_recognition.register_shit_pic(b"invalid image")
            self.assertFalse(pic_recognition.is_shit_pic(b"invalid image"))

        add.assert_not_called()

    def test_what_is_only_matches_explicit_lookup_command(self):
        plugin = WhatIs()

        self.assertTrue(plugin.is_trigger("查一下 NapCat"))
        self.assertFalse(plugin.is_trigger("什么是 NapCat"))
        self.assertFalse(plugin.is_trigger("请问 NapCat 是什么"))

    async def test_what_is_primary_failures_do_not_charge(self):
        plugin = WhatIs()
        message = make_pack("查一下 fixture")
        for error in (ReadTimeout("timeout"), RuntimeError("service failed")):
            with self.subTest(error=type(error).__name__), patch.object(
                GetOpenAIConversation,
                "get_web_search",
                side_effect=error,
            ):
                result = await plugin.ret(message)

            self.assertTrue(result.no_charge)
            self.assertTrue(result.no_interval)

        too_long = make_pack("查一下 " + "x" * plugin.message_length_limit)
        result = await plugin.ret(too_long)
        self.assertTrue(result.no_charge)
        self.assertTrue(result.no_interval)

    async def test_paid_gpt_validation_and_service_failures_do_not_charge(self):
        plugin = GetOpenAIConversation()
        failure_messages = (
            make_pack(".gpt " + "x" * (plugin.message_length_limit + 1)),
            make_pack(".gpt[missing] fixture"),
        )
        for message in failure_messages:
            with self.subTest(message=message.message.asDisplay()[:30]):
                result = await plugin.ret(message)
                self.assertTrue(result.no_charge)
                self.assertTrue(result.no_interval)

        for error in (ReadTimeout("timeout"), RuntimeError("service failed")):
            with self.subTest(error=type(error).__name__), patch.object(
                GetOpenAIConversation,
                "get_chat_stream",
                side_effect=error,
            ):
                result = await plugin.ret(make_pack(".gpt fixture"))

            self.assertTrue(result.no_charge)
            self.assertTrue(result.no_interval)

    async def test_what_is_fallback_failures_do_not_charge(self):
        plugin = WhatIs()
        message = make_pack("查一下 fixture")
        for fallback_error in (
            ReadTimeout("timeout"),
            RuntimeError("fallback failed"),
        ):
            with self.subTest(error=type(fallback_error).__name__), patch.object(
                GetOpenAIConversation,
                "get_web_search",
                side_effect=[
                    RuntimeError("model token limit exceeded"),
                    fallback_error,
                ],
            ), patch("plugins.gpt.bot_send_message"):
                result = await plugin.ret(message)

            self.assertTrue(result.no_charge)
            self.assertTrue(result.no_interval)

    def test_doubao_image_request_uses_configured_model(self):
        response = Mock()
        response.json.return_value = {
            "data": [
                {"b64_json": base64.b64encode(b"fixture-image").decode("ascii")}
            ]
        }
        with patch.dict(
            config,
            {
                "DOUBAO_API_KEY": "fixture-key",
                "DOUBAO_IMAGE_MODEL": "fixture-image-model",
            },
        ), patch(
            "plugins.online_ai.requests.post",
            return_value=response,
        ) as post:
            result = GetDoubaoCompose.generate_image("fixture")

        self.assertEqual(result, b"fixture-image")
        self.assertEqual(post.call_args.kwargs["json"]["model"], "fixture-image-model")
        self.assertEqual(post.call_args.kwargs["timeout"], (5, 180))

    def test_doubao_video_request_uses_configured_model(self):
        create_response = Mock()
        create_response.json.return_value = {"id": "fixture-task"}
        status_response = Mock()
        status_response.json.return_value = {
            "status": "succeeded",
            "content": {"video_url": "https://example.com/video.mp4"},
            "usage": {"total_tokens": 12},
        }
        with patch.dict(
            config,
            {
                "DOUBAO_API_KEY": "fixture-key",
                "DOUBAO_VIDEO_MODEL": "fixture-video-model",
            },
        ), patch(
            "plugins.online_ai.requests.post",
            return_value=create_response,
        ) as post, patch(
            "plugins.online_ai.requests.get",
            return_value=status_response,
        ):
            result = GetDoubaoCompose.generate_video("fixture")

        self.assertEqual(result, ("https://example.com/video.mp4", 12))
        self.assertEqual(post.call_args.kwargs["json"]["model"], "fixture-video-model")
        self.assertEqual(post.call_args.kwargs["timeout"], (5, 30))

    def test_group_video_upload_uses_and_removes_temporary_file(self):
        captured: dict[str, object] = {}

        def upload(group_id: int, file_name: str, file_path: str):
            path = Path(file_path)
            captured.update(
                group_id=group_id,
                file_name=file_name,
                file_path=path,
                content=path.read_bytes(),
            )
            return {"status": "ok", "retcode": 0}

        with patch("plugins.online_ai.bot_upload_group_file", side_effect=upload):
            result = GetDoubaoCompose.upload_group_video(
                100,
                "fixture.mp4",
                b"fixture-video",
            )

        self.assertEqual(result["retcode"], 0)
        self.assertEqual(captured["content"], b"fixture-video")
        self.assertFalse(captured["file_path"].exists())

    async def test_video_upload_failure_returns_preview_without_charge(self):
        message = make_pack("/doubaov fixture")
        with patch("plugins.online_ai.bot_send_message") as progress, patch.object(
            GetDoubaoCompose,
            "generate_video",
            return_value=("https://example.com/video.mp4", 12),
        ), patch.object(
            GetDoubaoCompose,
            "download_video",
            return_value=b"fixture-video",
        ), patch.object(
            GetDoubaoCompose,
            "upload_group_video",
            side_effect=RuntimeError("upload failed"),
        ), patch(
            "plugins.online_ai.convert_mp4_to_gif",
            return_value=b"fixture-gif",
        ):
            result = await GetDoubaoCompose().ret(message)

        progress.assert_called_once()
        self.assertTrue(result.no_charge)
        self.assertEqual(result.get(Image)[0].getBytes(), b"fixture-gif")
        self.assertIn("原视频文件上传失败", result.asDisplay())

    async def test_private_video_does_not_call_group_file_action(self):
        message = make_pack("/doubaov fixture")
        message.message_type = "private"
        message.group = Group(0, "private")
        with patch("plugins.online_ai.bot_send_message"), patch.object(
            GetDoubaoCompose,
            "generate_video",
            return_value=("https://example.com/video.mp4", 12),
        ), patch.object(
            GetDoubaoCompose,
            "download_video",
            return_value=b"fixture-video",
        ), patch.object(
            GetDoubaoCompose,
            "upload_group_video",
        ) as upload, patch(
            "plugins.online_ai.convert_mp4_to_gif",
            return_value=b"fixture-gif",
        ):
            result = await GetDoubaoCompose().ret(message)

        upload.assert_not_called()
        self.assertTrue(result.no_charge)
        self.assertEqual(result.get(Image)[0].getBytes(), b"fixture-gif")


class GroupFileAdapterTest(unittest.TestCase):
    def test_platform_neutral_group_file_uploader(self):
        original = toogle_adapter.GROUP_FILE_UPLOAD
        uploader = Mock(return_value={"status": "ok", "retcode": 0})
        try:
            toogle_adapter.register_group_file_uploader(uploader)
            result = toogle_adapter.bot_upload_group_file(
                100,
                "fixture.mp4",
                "/tmp/fixture.mp4",
            )
        finally:
            toogle_adapter.register_group_file_uploader(original)

        uploader.assert_called_once_with(100, "fixture.mp4", "/tmp/fixture.mp4")
        self.assertEqual(result["retcode"], 0)


if __name__ == "__main__":
    unittest.main()
