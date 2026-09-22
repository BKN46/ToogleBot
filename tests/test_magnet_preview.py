import ast
import asyncio
import io
import math
from pathlib import Path
import tempfile
import time
import types
import unittest
import random
import hashlib
from unittest.mock import Mock, patch

import av
from PIL import Image
from plugins.others import magnet


ROOT = Path(__file__).resolve().parents[1]


class FakeTorrent:
    def __init__(self, data, piece_length=4096, offset=137):
        self.data = b"x" * offset + data + b"tail"
        self.length = piece_length
        self.alerts = []
        self.downloads = []
        self.available = set()
        self.info = Mock()
        self.info.files.return_value.file_offset.return_value = offset
        self.info.files.return_value.file_size.return_value = len(data)
        self.info.piece_length.return_value = piece_length
        self.info.piece_size.side_effect = lambda p: len(self.data[p*piece_length:(p+1)*piece_length])
        self.handle = Mock()
        self.handle.piece_priority.side_effect = self.request
        self.handle.have_piece.side_effect = lambda p: p in self.available
        self.handle.read_piece.side_effect = self.read_piece
        self.session = Mock()
        self.session.pop_alerts.side_effect = self.pop_alerts

    def request(self, piece, priority):
        self.downloads.append(piece)
        self.available.add(piece)

    def read_piece(self, piece):
        self.alerts.append(types.SimpleNamespace(
            piece=piece, error=types.SimpleNamespace(value=lambda: 0),
            buffer=self.data[piece*self.length:(piece+1)*self.length]))

    def pop_alerts(self):
        alerts, self.alerts = self.alerts, []
        return alerts

    def reader(self, **kwargs):
        return magnet.TorrentVideoReader(self.session, self.handle, self.info, 0,
                                         time.monotonic()+30, **kwargs)


class MagnetPreviewTests(unittest.TestCase):
    def setUp(self):
        self.alert_patch = patch.object(magnet.lt, "read_piece_alert", types.SimpleNamespace)
        self.alert_patch.start()
        self.addCleanup(self.alert_patch.stop)

    def test_seek_downloads_only_overlapping_pieces_and_reuses_them(self):
        torrent = FakeTorrent(bytes(range(256))*100)
        with torrent.reader() as reader:
            reader.seek(3950)
            self.assertEqual(reader.read(30), (bytes(range(256))*100)[3950:3980])
            self.assertEqual(torrent.downloads, [0, 1])
            reader.seek(3950)
            reader.read(30)
            self.assertEqual(torrent.downloads, [0, 1])
            reader.seek(-4, io.SEEK_END)
            self.assertEqual(reader.read(50), (bytes(range(256))*100)[-4:])
            self.assertEqual(reader.read(1), b"")
            self.assertEqual(torrent.downloads, [0, 1, 6])

    def test_timeout_and_budget_do_not_return_sparse_bytes(self):
        torrent = FakeTorrent(b"x"*10000)
        with torrent.reader(max_bytes=4096) as reader:
            reader.read(1)
            reader.seek(5000)
            with self.assertRaisesRegex(RuntimeError, "128 MiB"):
                reader.read(1)
            self.assertEqual(torrent.downloads, [0])
        with torrent.reader() as reader:
            reader.deadline = time.monotonic()-1
            with self.assertRaises(TimeoutError):
                reader.read(1)

    def test_piece_read_failure(self):
        torrent = FakeTorrent(b"x"*10000)
        torrent.handle.read_piece.side_effect = lambda p: torrent.alerts.append(
            types.SimpleNamespace(piece=p, error=types.SimpleNamespace(value=lambda: 1)))
        with torrent.reader() as reader:
            with self.assertRaises(RuntimeError):
                reader.read(1)

    def test_missing_piece_wait_expires_without_reading(self):
        torrent = FakeTorrent(b"x"*10000)
        torrent.handle.have_piece.return_value = False
        torrent.handle.have_piece.side_effect = None
        with torrent.reader() as reader:
            with patch.object(magnet.time, "monotonic", side_effect=[0, 0, reader.deadline+1]):
                with self.assertRaises(TimeoutError):
                    reader.read(1)
            torrent.handle.read_piece.assert_not_called()

    def test_libtorrent_reads_verified_partfile(self):
        self.alert_patch.stop()
        lt = magnet.lt
        payload = bytes(range(256))*128
        storage = lt.file_storage()
        storage.add_file("fixture/video.mp4", len(payload))
        creator = lt.create_torrent(storage, 16384, flags=lt.create_torrent.v1_only)
        for piece in range(2):
            creator.set_hash(piece, hashlib.sha1(payload[piece*16384:(piece+1)*16384]).digest())
        info = lt.torrent_info(creator.generate())
        with tempfile.TemporaryDirectory() as directory:
            session = lt.session({"listen_interfaces": "127.0.0.1:0", "enable_dht": False,
                                  "enable_lsd": False, "enable_upnp": False, "enable_natpmp": False})
            params = lt.add_torrent_params()
            params.ti, params.save_path = info, directory
            params.flags |= lt.torrent_flags.default_dont_download
            params.flags &= ~(lt.torrent_flags.paused | lt.torrent_flags.auto_managed)
            handle = session.add_torrent(params)
            try:
                self.assertEqual(handle.get_piece_priorities(), [0, 0])
                deadline = time.monotonic() + 5
                while handle.status().state in (lt.torrent_status.checking_files,
                                                lt.torrent_status.checking_resume_data):
                    if time.monotonic() >= deadline:
                        self.fail("torrent did not finish checking")
                    time.sleep(0.01)
                handle.piece_priority(1, 7)
                handle.add_piece(1, payload[16384:], 0)
                with magnet.TorrentVideoReader(session, handle, info, 0, time.monotonic()+10) as reader:
                    reader.seek(20000)
                    self.assertEqual(reader.read(100), payload[20000:20100])
                    self.assertEqual(reader.requested, {1})
                    self.assertFalse(handle.have_piece(0))
            finally:
                session.remove_torrent(handle)
                handle = session = None

    def test_real_decoder_faststart_mkv_and_variable_frame_sizes(self):
        for suffix, options in (("mp4", {"movflags": "+faststart"}), ("mkv", {})):
            with self.subTest(container=suffix), tempfile.TemporaryDirectory() as directory:
                path = Path(directory)/f"fixture.{suffix}"
                rng = random.Random(10)
                with av.open(str(path), "w", options=options) as output:
                    stream = output.add_stream("mpeg4", rate=12)
                    stream.width, stream.height, stream.pix_fmt = 320, 192, "yuv420p"
                    stream.codec_context.gop_size = 36
                    for n in range(240):
                        picture = (Image.frombytes("RGB", (320, 192), rng.randbytes(320*192*3))
                                   if n % 48 < 24 else Image.new("RGB", (320, 192), (n, 80, 100)))
                        frame = av.VideoFrame.from_image(picture)
                        picture.close()
                        for packet in stream.encode(frame):
                            output.mux(packet)
                    for packet in stream.encode():
                        output.mux(packet)
                torrent = FakeTorrent(path.read_bytes())
                with torrent.reader() as reader:
                    frames = magnet.extract_frames(reader)
                    self.assertEqual(len(frames), 6)
                    self.assertLess(reader.requested_bytes, len(torrent.data))

    def test_real_decoder_with_large_tail_index_and_sparse_video(self):
        # Pad moov with a valid free box: its beginning lies before the final two pieces.
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"fixture.mp4"
            with av.open(str(path), "w") as output:
                stream = output.add_stream("mpeg4", rate=12)
                stream.width, stream.height, stream.pix_fmt = 160, 96, "yuv420p"
                stream.codec_context.gop_size = 12
                for n in range(240):
                    picture = Image.new("RGB", (160, 96), (n % 256, 80, 100))
                    frame = av.VideoFrame.from_image(picture)
                    picture.close()
                    for packet in stream.encode(frame):
                        output.mux(packet)
                for packet in stream.encode():
                    output.mux(packet)
            data = path.read_bytes()
        offset = 0
        while data[offset+4:offset+8] != b"moov":
            offset += int.from_bytes(data[offset:offset+4], "big")
        length = int.from_bytes(data[offset:offset+4], "big")
        padding = 64*1024
        data = (data[:offset] + (length+padding).to_bytes(4, "big") + data[offset+4:offset+length]
                + padding.to_bytes(4, "big") + b"free" + b"\0"*(padding-8) + data[offset+length:])
        torrent = FakeTorrent(data, piece_length=1024)
        with torrent.reader() as reader:
            frames = magnet.extract_frames(reader)
            self.assertEqual(len(frames), 6)
            for frame in frames:
                with Image.open(io.BytesIO(frame)) as image:
                    self.assertEqual(image.size, (160, 96))
            self.assertIn((offset+137)//1024, reader.requested)
            self.assertLess(len(reader.requested), math.ceil(len(data)/1024))
            self.assertEqual(len(torrent.downloads), len(set(torrent.downloads)))

    def test_plugin_error_is_not_charged(self):
        from toogle.message import MessageChain, Plain, ForwardMessage
        tree = ast.parse((ROOT / "plugins/other.py").read_text())
        node = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "MagnetParse")
        namespace = dict(MessageHandler=object, MessagePack=object, MessageChain=MessageChain,
                         Plain=Plain, ForwardMessage=ForwardMessage, asyncio=asyncio,
                         do_magnet_preview=Mock(return_value="preview failed"),
                         parse_size=magnet.parse_size, bot_send_message=Mock())
        exec(compile(ast.Module(body=[node], type_ignores=[]), "plugins/other.py", "exec"), namespace)
        message = Mock(message=MessageChain.plain("magnet:?xt=urn:btih:abc"))
        message.as_quote.return_value = None
        result = asyncio.run(namespace["MagnetParse"]().ret(message))
        self.assertTrue(result.no_charge)
        self.assertTrue(result.no_interval)


if __name__ == "__main__":
    unittest.main()
