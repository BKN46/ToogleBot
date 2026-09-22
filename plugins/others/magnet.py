"""Magnet preview backend. Network work is performed by callers off the event loop."""
import re, io, math, shutil, tempfile, time
from collections import OrderedDict
from pathlib import Path
import av
import libtorrent as lt
from PIL import Image as PILImage

def parse_size(size):
    for unit, base in (("GB", 1024**3), ("MB", 1024**2), ("KB", 1024)):
        if size >= base: return f"{size / base:.2f} {unit}"
    return f"{size} B"

def parse_magnet(text, only_magnet=False):
    pattern = r"magnet:\?xt=urn:[a-z0-9]+:[a-zA-Z0-9]+" + (r"" if only_magnet else r"[^\s<>]*")
    match = re.search(pattern, text, re.I)
    return match.group(0) if match else None

def do_magnet_preview(text):
    magnet = parse_magnet(text, only_magnet=True)
    if not magnet: return "磁链不合法"
    try:
        return preview_magnet(magnet)
    except Exception as exc:
        return f"磁链解析错误: {exc}"

def format_file_tree(entries):
    tree = {}
    for path, size in entries:
        node = tree
        parts = path.replace('\\', '/').split('/')
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = size

    def size_of(value):
        return sum(size_of(v) for v in value.values()) if isinstance(value, dict) else value

    lines = []
    count = 0
    def render(node, depth=0, prefix=''):
        nonlocal count
        items = sorted(node.items(), key=lambda item: (
            not isinstance(item[1], dict), -size_of(item[1]), item[0]))
        for name, value in items:
            if count >= 50:
                break
            folder = isinstance(value, dict)
            lines.append(f"{prefix}+-- {name}{'/' if folder else ''} [{parse_size(size_of(value))}]")
            if folder and depth < 1:
                render(value, depth + 1, prefix + '    ')
            elif not folder:
                count += 1
    render(tree)
    lines.append(f"显示 {count} 个文件（最多两层、50 个文件；目录大小含全部子项）")
    return '\n'.join(lines)

def do_magnet_parse(text):
    return do_magnet_preview(text)

class TorrentVideoReader(io.RawIOBase):
    """Expose verified torrent pieces as a seekable file, without reading sparse holes."""

    def __init__(self, session, handle, info, index, deadline, max_bytes=128 * 1024**2):
        super().__init__()
        self.session, self.handle, self.info = session, handle, info
        self.offset = info.files().file_offset(index)
        self.size = info.files().file_size(index)
        self.deadline, self.max_bytes = deadline, max_bytes
        self.position = 0
        self.requested = set()
        self.requested_bytes = 0
        self.cache = OrderedDict()

    def readable(self):
        return True

    def close(self):
        self.cache.clear()
        self.session = self.handle = None
        super().close()

    def seekable(self):
        return True

    def tell(self):
        return self.position

    def seek(self, offset, whence=io.SEEK_SET):
        bases = {io.SEEK_SET: 0, io.SEEK_CUR: self.position, io.SEEK_END: self.size}
        if whence not in bases or bases[whence] + offset < 0:
            raise ValueError("invalid seek")
        self.position = bases[whence] + offset
        return self.position

    def check_deadline(self):
        if time.monotonic() >= self.deadline:
            raise TimeoutError("下载截图所需分片超时，请稍后重试")

    def _piece(self, piece):
        self.check_deadline()
        if piece in self.cache:
            self.cache.move_to_end(piece)
            return self.cache[piece]
        if piece not in self.requested:
            size = self.info.piece_size(piece)
            if self.requested_bytes + size > self.max_bytes:
                raise RuntimeError("截图所需分片超过 128 MiB 上限，已停止下载")
            self.requested.add(piece)
            self.requested_bytes += size
            self.handle.piece_priority(piece, 7)
            self.handle.set_piece_deadline(piece, 0)
        while not self.handle.have_piece(piece):
            self.check_deadline()
            self.session.pop_alerts()
            time.sleep(0.05)
        # read_piece also works for libtorrent's partfile and pending disk writes.
        self.handle.read_piece(piece)
        while True:
            self.check_deadline()
            for alert in self.session.pop_alerts():
                if isinstance(alert, lt.read_piece_alert) and alert.piece == piece:
                    if alert.error.value():
                        raise RuntimeError("读取已下载的视频分片失败")
                    data = bytes(alert.buffer)
                    if len(data) != self.info.piece_size(piece):
                        raise RuntimeError("视频分片长度不完整")
                    self.cache[piece] = data
                    while len(self.cache) > 4:
                        self.cache.popitem(last=False)
                    return data
            time.sleep(0.01)

    def read(self, size=-1):
        self.check_deadline()
        if self.position >= self.size:
            return b""
        # Short reads are legal; cap each callback instead of prefetching a whole GOP.
        size = min(32768 if size < 0 else size, 32768, self.size - self.position)
        result = bytearray()
        while len(result) < size:
            absolute = self.offset + self.position
            piece, within = divmod(absolute, self.info.piece_length())
            data = self._piece(piece)
            length = min(size - len(result), len(data) - within)
            result.extend(data[within:within + length])
            self.position += length
        return bytes(result)


def extract_frames(reader):
    frames = []
    def reject_external_io(*args):
        raise RuntimeError("视频引用外部资源，无法生成预览")

    with av.open(reader, buffer_size=32768, io_open=reject_external_io) as container:
        if not container.streams.video:
            raise RuntimeError("未找到可解码的视频轨道")
        stream = container.streams.video[0]
        duration = (float(stream.duration * stream.time_base) if stream.duration is not None
                    else float(container.duration or 0) / av.time_base)
        if not math.isfinite(duration) or duration <= 0:
            raise RuntimeError("无法获取有效视频时长")
        start = float((stream.start_time or 0) * stream.time_base)
        for n in range(1, 7):
            reader.check_deadline()
            target = start + duration * n / 7
            container.seek(int(target / stream.time_base), stream=stream,
                           backward=True, any_frame=False)
            for frame in container.decode(stream):
                reader.check_deadline()
                if frame.time is None or frame.time < target:
                    continue
                if frame.is_corrupt:
                    raise RuntimeError("视频帧损坏，无法生成完整预览")
                picture = frame.to_image()
                picture.thumbnail((640, 640), PILImage.Resampling.LANCZOS)
                with io.BytesIO() as output:
                    picture.save(output, format="JPEG", quality=88)
                    frames.append(output.getvalue())
                picture.close()
                break
            else:
                raise RuntimeError(f"无法解码第 {n} 张截图，未生成完整预览")
    return frames

def preview_magnet(magnet, timeout=180):
    started = time.monotonic()
    work_root = Path(__file__).resolve().parents[2] / "test" / "magnet"
    work_root.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="magnet-preview-", dir=work_root))
    session = handle = None
    try:
        session = lt.session({"listen_interfaces": "0.0.0.0:0", "enable_dht": True,
                              "enable_lsd": False, "enable_upnp": False, "enable_natpmp": False,
                              "close_redundant_connections": False})
        for node in (("router.bittorrent.com", 6881), ("router.utorrent.com", 6881),
                     ("dht.transmissionbt.com", 6881), ("dht.aelitis.com", 6881)):
            session.add_dht_node(node)
        p = lt.parse_magnet_uri(magnet); p.save_path = str(work)
        p.flags |= lt.torrent_flags.default_dont_download
        p.flags &= ~(lt.torrent_flags.auto_managed | lt.torrent_flags.paused)
        handle = session.add_torrent(p)
        deadline = time.monotonic() + timeout
        next_announce = time.monotonic() + 15
        while not handle.has_metadata() and time.monotonic() < deadline:
            if time.monotonic() >= next_announce:
                handle.force_dht_announce()
                next_announce = time.monotonic() + 30
            session.pop_alerts()
            time.sleep(0.1)
        if not handle.has_metadata(): raise TimeoutError("获取 torrent metadata 超时")
        info, files = handle.torrent_file(), handle.torrent_file().files()
        candidates = [(i, files.at(i).path, files.at(i).size) for i in range(files.num_files())
                      if Path(files.at(i).path).suffix.lower() in {".mp4", ".mkv", ".webm", ".avi", ".mov", ".ts", ".m4v"}]
        if not candidates: raise RuntimeError("未找到视频文件")
        index, name, size = max(candidates, key=lambda x: x[2])
        handle.prioritize_pieces([0] * info.num_pieces())
        handle.resume()
        with TorrentVideoReader(session, handle, info, index, started + timeout * 4) as reader:
            frames = extract_frames(reader)
            requested_bytes = reader.requested_bytes
            requested_pieces = len(reader.requested)
        sheet = None
        if len(frames) == 6:
            pics = [PILImage.open(io.BytesIO(x)).convert("RGB") for x in frames]; w, h = pics[0].size
            sheet = PILImage.new("RGB", (w * 2, h * 3))
            for i, pic in enumerate(pics): sheet.paste(pic, ((i % 2) * w, (i // 2) * h))
            sheet.thumbnail((960, 960), PILImage.Resampling.LANCZOS)
        status = handle.status()
        return {"name": name, "size": size, "count": files.num_files(), "images": frames, "sheet": sheet,
                "file_tree": format_file_tree([(files.at(i).path, files.at(i).size) for i in range(files.num_files())]),
                "dht_nodes": session.status().dht_nodes, "seeds": status.num_seeds,
                "download_speed": status.download_rate, "elapsed": time.monotonic() - started,
                "requested_bytes": requested_bytes, "requested_pieces": requested_pieces}
    finally:
        if handle is not None:
            handle.pause()
            session.remove_torrent(handle)
        # Destroy the session before removing its storage, including on decode failure.
        handle = session = None
        shutil.rmtree(work, ignore_errors=True)
