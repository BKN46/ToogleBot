import pickle

from thefuzz import process

DND_DATA = pickle.load(open("data/dnd_data.pickle", "rb"))

CHM_LIST = DND_DATA['CHM_LIST']


def search_chm(text):
    match_list = [x["title"] for x in CHM_LIST if text in x["title"]]
    if len(match_list) == 1:
        res = match_list[0] + ".jpg"
        return CHM_LIST['CHM_PICS'][res]
    elif text in match_list:
        return CHM_LIST['CHM_PICS'][text + ".jpg"]
    elif len(match_list) > 1:
        res = process.extract(text, CHM_LIST, limit=10)
        res = (
            "\n".join([x for x in match_list])
            + "\n"
            + "\n".join([x[0]["title"] for x in res if x[0]["title"] not in match_list])
        )
    else:
        res = process.extract(text, CHM_LIST, limit=10)
        res = "\n".join([x[0]["title"] for x in res])
    return f"{res}"
