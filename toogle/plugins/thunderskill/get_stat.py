import requests

from toogle.utils import anti_cf_requests

BASE_URL = "https://thunderskill.com"


def get_player_realistic_stat(player_name: str):
    path = f"{BASE_URL}/en/stat/{player_name}/vehicles/r"
    res = anti_cf_requests.get(path)
    return res.text


def get_player_stat(player_name: str):
    path = f"{BASE_URL}/en/stat/{player_name}"
    res = anti_cf_requests.get(path)
    return res.text

def refresh_player_stat(player_name: str):
    path = f"{BASE_URL}/en/stat/{player_name}"
    try:
        anti_cf_requests.post(
            path,
            data="update=1",
            timeout=5,
            content_type="application/x-www-form-urlencoded; charset=UTF-8"
        )
    except:
        pass
    return


def get_player_session(player_name: str):
    path = f"{BASE_URL}/en/stat/{player_name}/session"
    res = anti_cf_requests.get(path)
    return res.text


def get_squadron_players(squadron_name: str):
    path = f"{BASE_URL}/en/squad/{squadron_name}/players"
    res = anti_cf_requests.get(path)
    return res.text

if __name__ == "__main__":
    # print(get_player_realistic_stat("BKN46"), file=open("get_r_stat.html", "w", encoding="utf-8"))
    # print(get_player_stat("BKN46"), file=open("get_stat.html", "w", encoding="utf-8"))
    print(refresh_player_stat("BKN46"))
