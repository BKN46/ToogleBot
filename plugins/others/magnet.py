"""Magnet preview backend. Network work is performed by callers off the event loop."""
import re, io, json, shutil, subprocess, tempfile, time
from shutil import which
from pathlib import Path
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

def preview_magnet(magnet, timeout=180):
    started = time.monotonic()
    ffmpeg = Path(which("ffmpeg") or "")
    ffprobe = Path(which("ffprobe") or "")
    if not ffmpeg.is_file() or not ffprobe.is_file():
        raise RuntimeError("ffmpeg/ffprobe 不可用")
    work_root = Path(__file__).resolve().parents[2] / "test" / "magnet"
    work_root.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="magnet-preview-", dir=work_root))
    try:
        session = lt.session({"listen_interfaces": "0.0.0.0:0", "enable_dht": True,
                              "enable_lsd": False, "enable_upnp": False, "enable_natpmp": False})
        for node in (("router.bittorrent.com", 6881), ("router.utorrent.com", 6881),
                     ("dht.transmissionbt.com", 6881), ("dht.aelitis.com", 6881)):
            session.add_dht_node(node)
        p = lt.parse_magnet_uri(magnet); p.save_path = str(work)
        handle = session.add_torrent(p)
        deadline = time.monotonic() + timeout
        while not handle.has_metadata() and time.monotonic() < deadline: session.wait_for_alert(500)
        if not handle.has_metadata(): raise TimeoutError("获取 torrent metadata 超时")
        info, files = handle.torrent_file(), handle.torrent_file().files()
        candidates = [(i, files.at(i).path, files.at(i).size) for i in range(files.num_files())
                      if Path(files.at(i).path).suffix.lower() in {".mp4", ".mkv", ".webm", ".avi", ".mov", ".ts", ".m4v"}]
        if not candidates: raise RuntimeError("未找到视频文件")
        index, name, size = max(candidates, key=lambda x: x[2])
        for piece in range(info.num_pieces()): handle.piece_priority(piece, 0)
        first, last = info.map_file(index, 0, 1).piece, info.map_file(index, size - 1, 1).piece
        edges = {p for c in (first, last) for p in range(max(first, c - 1), min(last, c + 1) + 1)}
        for piece in edges: handle.piece_priority(piece, 7); handle.set_piece_deadline(piece, 120000)
        handle.resume(); path = work / name
        while not all(handle.have_piece(p) for p in edges) and time.monotonic() < deadline: session.wait_for_alert(500)
        probe = subprocess.run([str(ffprobe), "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)], capture_output=True, text=True)
        duration = float(json.loads(probe.stdout)["format"]["duration"])
        frames, output = [], work / "preview"; output.mkdir()
        for n in range(1, 7):
            center = first + (last - first) * n // 7
            wanted = range(max(first, center - 1), min(last, center + 2) + 1)
            for piece in wanted: handle.piece_priority(piece, 7); handle.set_piece_deadline(piece, 120000)
            end = time.monotonic() + timeout / 3
            while not all(handle.have_piece(p) for p in wanted) and time.monotonic() < end: session.wait_for_alert(500)
            frame = output / f"frame-{n}.jpg"
            subprocess.run([str(ffmpeg), "-hide_banner", "-loglevel", "error", "-ss", str(duration * n / 7), "-i", str(path), "-frames:v", "1", "-vf", "scale=640:-2", "-y", str(frame)], check=False)
            if frame.exists(): frames.append(frame.read_bytes())
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
                "download_speed": status.download_rate, "elapsed": time.monotonic() - started}
    finally:
        shutil.rmtree(work, ignore_errors=True)
