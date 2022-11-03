import datetime

import toogle.plugins.wt.get_stat as get_stat
import toogle.plugins.wt.parse_stat as parse_stat

def get_player_recent_data(player_name: str):
    get_stat.refresh_player_stat(player_name)
    stat = parse_stat.player_report(parse_stat.parse_player_stat(get_stat.get_player_stat(player_name)))
    vehicle = parse_stat.player_vehicle_report(parse_stat.parse_player_vehicle(get_stat.get_player_realistic_stat(player_name)))
    return f"{stat}\n{vehicle}"

if __name__ == "__main__":
    res = get_player_recent_data('MamiyaAika')
