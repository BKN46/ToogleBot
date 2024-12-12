import json

from wordcloud import WordCloud


if __name__ == "__main__":
    word_stats = {
        k: v
        for k, v in
        json.load(open("res/word_stats.json", "r", encoding="utf-8")).items()
        if 50 < v < 5000 and (len(k) > 1 or k in ["屎", "逼", "草", "妈", "顶", "日", "批", "冲"]) and not k.isascii()
    }
    word_cloud = WordCloud(
        font_path="../toogle/plugins/compose/fonts/Arial Unicode MS Font.ttf",
        width=1920,
        height=1080,
        background_color="white",
        max_words=1000,
        max_font_size=200,
        colormap="tab20",
    )
    word_cloud.generate_from_frequencies(word_stats)
    word_cloud.to_file("res/word_cloud.png")
