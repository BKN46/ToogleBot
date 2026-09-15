import asyncio
import hashlib
import threading
import unittest
from unittest.mock import Mock, patch

from configs import config
from plugins.other import NFSWorNot
from toogle.message import Group, Image, Member, MessageChain
from toogle.message_handler import MessagePack
from tools import pic_recognition
import toogle.msg_proc as msg_proc


class NsfwFlowTest(unittest.IsolatedAsyncioTestCase):
    def pack(self, private=False):
        return MessagePack(
            id=123, message=MessageChain.create([Image(bytes=b"fixture")]),
            group=Group(0 if private else 100, "fixture"),
            member=Member(200, "fixture"), quote=None,
            message_type="private" if private else "group",
        )

    def test_repeat_and_allowlist_do_not_depend_on_inference_cache(self):
        detector = Mock()
        detector.predict.return_value = 0.8
        seen, allowed = set(), set()
        with patch.object(pic_recognition, "PIC_BLOOM", seen), patch.object(
            pic_recognition, "SFW_BLOOM", allowed
        ), patch.object(pic_recognition, "_NSFW_DETECTOR", None), patch.object(
            pic_recognition, "_NSFW_SETTINGS", None
        ), patch.object(pic_recognition, "NsfwDetector", return_value=detector) as create:
            self.assertEqual(pic_recognition.detect_pic_nsfw(b"fixture", True), (0.8, False))
            self.assertEqual(pic_recognition.detect_pic_nsfw(b"fixture", True), (0.8, True))
            allowed.add(hashlib.md5(b"fixture").hexdigest())
            self.assertEqual(pic_recognition.detect_pic_nsfw(b"fixture", True), (0, False))
            self.assertEqual(detector.predict.call_count, 2)
            create.assert_called_once()

    def test_failed_model_load_is_not_safe_or_seen(self):
        seen = set()
        with patch.object(pic_recognition, "PIC_BLOOM", seen), patch.object(
            pic_recognition, "SFW_BLOOM", set()
        ), patch.object(pic_recognition, "_NSFW_DETECTOR", None), patch.object(
            pic_recognition, "NsfwDetector", side_effect=FileNotFoundError("missing")
        ):
            with self.assertRaises(FileNotFoundError):
                pic_recognition.detect_pic_nsfw(b"fixture")
            self.assertFalse(seen)

    def test_threshold_configuration_rejects_invalid_order(self):
        with patch.dict(config, {"NSFW_THRESHOLD": "0.1", "NSFW_SUGGESTIVE_THRESHOLD": "0.5"}):
            with self.assertRaises(ValueError):
                pic_recognition.nsfw_thresholds()

    async def test_command_offloads_download_and_inference_in_group_and_private(self):
        loop_thread = threading.get_ident()
        def get_bytes(*args):
            self.assertNotEqual(threading.get_ident(), loop_thread)
            return b"fixture"
        def detect(*args, **kwargs):
            self.assertNotEqual(threading.get_ident(), loop_thread)
            return 0.8, False
        with patch.object(Image, "getBytes", get_bytes), patch(
            "plugins.other.detect_pic_nsfw", side_effect=detect
        ):
            for private in (False, True):
                result = await NFSWorNot().ret(self.pack(private))
                self.assertIn("色", result.asDisplay())
                self.assertFalse(result.no_charge)

    async def test_invalid_image_response_is_not_charged(self):
        with patch("plugins.other.detect_pic_nsfw", return_value=(-1, False)):
            response = await NFSWorNot().ret(self.pack())
        self.assertIn("无法识别", response.asDisplay())
        self.assertTrue(response.no_charge)
        self.assertTrue(response.no_interval)

    async def test_automatic_detection_uses_new_threshold_and_repeat_contract(self):
        with patch.dict(config, {"NSFW_THRESHOLD": "0.5", "ANTI_NSFW_LIST": ["100"]}), patch.object(
            msg_proc, "detect_pic_nsfw", side_effect=[(0.3, False), (0.8, True)]
        ), patch.object(msg_proc, "give_balance") as earn, patch.object(
            msg_proc, "update_setu_record"
        ) as record, patch.object(msg_proc.DelayedRecall, "add_recall") as recall:
            pack = self.pack()
            await msg_proc.setu_detect(pack, pack.message.get(Image))
            recall.assert_not_called()
            await msg_proc.setu_detect(pack, pack.message.get(Image))
            recall.assert_called_once_with(pack.group.id, pack)
            earn.assert_not_called()
            record.assert_not_called()
