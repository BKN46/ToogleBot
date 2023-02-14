from PIL import Image
import requests

save_path = "data/daily_news.png"

def download_daily():
    url = "http://118.31.18.68:8080/news/api/news-file/get"
    response = requests.request("GET", url)
    url = response.json()['result'][0]
    print(response.json())
    headers = {'Referer': 'safe.soyiji.com'}
    response = requests.request("GET", url, headers=headers, stream=True)
    Image.open(response.raw).save(save_path)

if __name__ == "__main__":
    download_daily()
