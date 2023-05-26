import a2s

def source_server_info(ip, port):
    try:
        a2s_info = a2s.info((ip, port), timeout=3, encoding="utf8")
    except Exception as e:
        return f"{ip}:{port} 服务查询错误"
    text = f"{a2s_info.server_name}\n{a2s_info.game} ({a2s_info.keywords})\n人数：{a2s_info.player_count}/{a2s_info.max_players}\n北京延迟：{a2s_info.ping * 1000:.2f}ms"
    return text
