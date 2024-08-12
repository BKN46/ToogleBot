import base64
import json
import random

import PIL.Image
import PIL.ImageDraw
import PIL.ImageFont

import toogle.plugins.waifu_utils.waifu_random as Waifu
from toogle.message import Image, Member, MessageChain, Plain
from toogle.message_handler import MessageHandler, MessagePack, get_user_name
from toogle.plugins.waifu_utils.waifu_battle import Dice
from toogle.plugins.waifu_utils.waifu_card import get_waifu_card, ranking_compose
from toogle.sql import DatetimeUtils, SQLConnection
from toogle.utils import draw_pic_text, text2img


class GetRandomAnimeFemale(MessageHandler):
    name = "随机ACG老婆"
    trigger = r"^(随机老婆|随机老公|我的老婆$|我的老公$|锁定老婆$|锁定老公$|对象排行|可选对象属性$|我要NTR|我要ntr|换妻)"
    thread_limit = True
    readme = "随机冻漫角色\n可以使用'对象排行 #2'进行翻页等"
    price = 3

    atk_dice_list = ["2d6", "d12", "d10", "2d4", "d8", "d6", "d4"]
    def_dice_list = ["4d6", "3d8", "5d4", "2d12", "2d10", "3d6", "2d8", "4d4", "d20kh"]

    async def ret(self, message: MessagePack) -> MessageChain:
        user = SQLConnection.get_user(message.member.id)
        message_text = message.message.asDisplay()
        s, schn = "f", "老婆"
        if "老公" in message_text:
            s, schn = "m", "老公"
        # return MessageChain.create([Plain("Waifu功能敏感时期暂时维护")])
        if message_text.startswith("随机"):
            if not user or not DatetimeUtils.is_today(user[2]) or user[1] > 5:

                my_waifu = SQLConnection.search(
                    "qq_waifu", {"id": str(message.member.id)}
                )

                is_debug = "`" in message_text and user and user[1] > 5
                feat_list = message_text.split()
                if len(feat_list) > 1 and len(feat_list[1]) > 0:
                    try:
                        res, req_url = Waifu.get_designated_search(s, feat_list[1:])
                        res_pic_url, res_text, res_id, res_raw = res
                        if is_debug:
                            text = f"\n随机结果是:\n{res[1]}"
                            pic_bytes = get_waifu_card(
                                get_user_name(message),
                                res_raw['姓名'],
                                res_pic_url or '',
                                res_raw['来源'],
                                res_raw['类型'],
                                res_text,
                                res_raw['CV'],
                            )
                            return MessageChain.create(
                                [
                                    message.as_quote(),
                                    Image(bytes=pic_bytes),
                                    Plain(f"\n本次随机池: {req_url}"),
                                ]
                            )
                    except Waifu.ACError as e:
                        return MessageChain.create([Plain(f"参数错误: {e}")])
                else:
                    res = Waifu.get_random_anime_character(s)
                    res_pic_url, res_text, res_id, res_raw = res

                others = SQLConnection.search("qq_waifu", {"waifuId": res[2]})

                is_shine = random.random() < 0.05
                no_center_box = random.random() < 0.1 and is_shine

                if others and not str(others[0][0]) == str(message.member.id):
                    text = f"\n{get_user_name(message)}你的{schn}是:\n{res[1]}\n\n但是已经被{others[0][0]}抢先下手了"
                    SQLConnection.update_user(
                        message.member.id, f"last_luck='{DatetimeUtils.get_now_time()}'"
                    )
                    pic_bytes = get_waifu_card(
                        get_user_name(message),
                        res_raw['姓名'],
                        res_pic_url or '',
                        res_raw['来源'],
                        res_raw['类型'],
                        res_text,
                        res_raw['CV'],
                        is_repeat=str(others[0][0]),
                        is_shine=is_shine,
                        no_center_box=no_center_box,
                    )
                else:
                    text = f"\n{get_user_name(message)}你的{schn}是:\n{res[1]}\n输入【锁定{schn}】即可锁定{schn}"

                    SQLConnection.update(
                        "qq_user",
                        {
                            "last_luck": str(DatetimeUtils.get_now_time()),
                            "waifu": json.dumps({
                                "id": res[2],
                                "is_shine": is_shine,
                                "no_center_box": no_center_box,
                            }, ensure_ascii=False)
                        },
                        {"id": str(message.member.id),},
                    )

                    pic_bytes = get_waifu_card(
                        get_user_name(message),
                        res_raw['姓名'],
                        res_pic_url or '',
                        res_raw['来源'],
                        res_raw['类型'],
                        res_text,
                        res_raw['CV'],
                        is_shine=is_shine,
                        no_center_box=no_center_box,
                    )
                return MessageChain.create([
                    message.as_quote(),
                    Image(bytes=pic_bytes),
                ])
            else:
                return MessageChain.create([
                    message.as_quote(),
                    Plain(f"每天运势/随机{schn}/NTR只能一次")
                ])

        elif message_text in ["我的老婆", "我的老公"]:
            waifu_id, waifu_is_shine, waifu_no_center_box = self.get_tmp_waifu(user)
            my_waifu = SQLConnection.search("qq_waifu", {"id": str(message.member.id)})
            if not waifu_id and not my_waifu: # type: ignore
                return MessageChain.create(
                    [Plain(f"{get_user_name(message)}你还没有{schn}\n输入【随机老婆】来抽一个")]
                )
            if not my_waifu:
                return MessageChain.create(
                    [Plain(f"{get_user_name(message)}你还没有锁定{schn}")]
                )
            res_data = json.loads(my_waifu[0][3].replace("\\\"", "\""))
            if my_waifu and len(res_data) > 0 and 'CV' in res_data:
                if 'pic_bytes' in res_data:
                    return MessageChain.create([
                        message.as_quote(),
                        Image(base64=res_data['pic_bytes']),
                    ])
                res_str, res_pic = (
                    Waifu.parse_popularity_data(res_data),
                    res_data["pic"],
                )
                waifu_is_shine, waifu_no_center_box = res_data.get('is_shine', False), res_data.get('no_center_box', False)
                is_new = False
            elif my_waifu:
                res_str, res_pic, res_data = Waifu.get_anime_character_popularity(
                    acdb_id=my_waifu[0][1],
                    extra_ratio=self.get_shine_score_ratio(waifu_is_shine, waifu_no_center_box),
                )
                res_data.update({ # type: ignore
                    "def": random.choice(self.def_dice_list),
                    "is_shine": waifu_is_shine,
                    "no_center_box": waifu_no_center_box,
                })
                SQLConnection.update(
                    "qq_waifu",
                    {"otherDict": json.dumps(res_data, ensure_ascii=False)},
                    {"id": str(message.member.id)},
                )
                is_new = False
            else:
                res_str, res_pic, res_data = Waifu.get_anime_character_popularity(
                    acdb_id=waifu_id,
                    extra_ratio=self.get_shine_score_ratio(waifu_is_shine, waifu_no_center_box),
                )
                is_new = True

            pic_bytes = get_waifu_card(
                get_user_name(message),
                res_data['name'], # type: ignore
                res_pic, # type: ignore
                res_data['src'], # type: ignore
                res_data['type'], # type: ignore
                '\n'.join([x for x in res_str.split('\n')][4:]),
                res_data['CV'], # type: ignore
                is_new=is_new,
                waifu_score=res_data['score'], # type: ignore
                waifu_rank=res_data['rank'], # type: ignore
                is_shine=waifu_is_shine,
                no_center_box=waifu_no_center_box,
            )
            base64_str = base64.b64encode(pic_bytes).decode()
            self.update_waifu_dict(message.member.id, { "pic_bytes": base64_str })
            m_res = MessageChain.create(
                [   
                    message.as_quote(),
                    Image(bytes=pic_bytes)
                ]
            )
            # req_url = f"https://www.animecharactersdatabase.com/characters.php?id={user[5]}"
            # m_res = MessageChain.create([Plain(f"{get_user_name(message)}的对象是:\n{req_url}")])
            return m_res

        elif message_text in ["锁定老婆", "锁定老公"]:
            waifu_id, waifu_is_shine, waifu_no_center_box = self.get_tmp_waifu(user)
            if not waifu_id:
                return MessageChain.create([Plain(f"{get_user_name(message)}你还没有对象")])
            my_waifu = SQLConnection.search("qq_waifu", {"id": str(message.member.id)})
            others = SQLConnection.search("qq_waifu", {"waifuId": waifu_id})
            if others and others[0][0] != str(message.member.id):
                return MessageChain.create(
                    [
                        Plain(f"{get_user_name(message)}你的{schn}已经被{others[0][0]}抢了"),
                    ]
                )
            
            res_str, res_pic, res_data = Waifu.get_anime_character_popularity(
                acdb_id=waifu_id,
                extra_ratio=self.get_shine_score_ratio(waifu_is_shine, waifu_no_center_box),
            )
            pic_bytes = get_waifu_card(
                get_user_name(message),
                res_data['name'], # type: ignore
                res_pic, # type: ignore
                res_data['src'], # type: ignore
                res_data['type'], # type: ignore
                '\n'.join([x for x in res_str.split('\n')][4:]),
                res_data['CV'], # type: ignore
                is_new=False,
                waifu_score=res_data['score'], # type: ignore
                waifu_rank=res_data['rank'], # type: ignore
                is_shine=waifu_is_shine,
                no_center_box=waifu_no_center_box,
            )
            res_data.update({ # type: ignore
                "def": random.choice(self.def_dice_list),
                "is_shine": waifu_is_shine,
                "no_center_box": waifu_no_center_box,
                "pic_bytes": base64.b64encode(pic_bytes).decode(),
            })
            
            if len(my_waifu) > 0:
                if my_waifu[0][1] != waifu_id:
                    res = Waifu.get_anime_character(waifu_id)
                    SQLConnection.update(
                        "qq_waifu",
                        {
                            "name": str(get_user_name(message)),
                            "waifuId": res[2],
                            "waifuDict": json.dumps(res[3], ensure_ascii=False),
                            "otherDict": json.dumps(res_data, ensure_ascii=False),
                        },
                        {"id": str(message.member.id)},
                    )
                else:
                    waifu_data = json.loads(my_waifu[0][2].replace("\\\"", "\""))
                    return MessageChain.plain(f"{get_user_name(message)}你的{schn}{waifu_data['姓名']}已经锁定上了")
            else:
                res = Waifu.get_anime_character(waifu_id)
                SQLConnection.insert(
                    "qq_waifu",
                    {
                        "name": str(get_user_name(message)),
                        "id": str(message.member.id),
                        "waifuId": res[2],
                        "waifuDict": json.dumps(res[3], ensure_ascii=False),
                        "otherDict": json.dumps(res_data, ensure_ascii=False),
                    },
                )
            return MessageChain.create(
                [
                    Plain(f"{get_user_name(message)}你的{schn}{res[3]['姓名']}已成功锁定"),
                ]
            )

        elif message_text in ["可选对象属性"]:
            text = Waifu.get_keyword_explain()
            return MessageChain.create([
                Image(bytes=text2img(
                    text,
                    word_size=15,
                    max_size=(500,2000),
                    font_height_adjust=6,
                ))
            ])

        elif message_text.startswith("对象排行"):
            waifu_list = self.get_waifu_list()
            if message_text == "对象排行":
                pic_bytes = ranking_compose(waifu_list[:10])
                m_res = MessageChain.create([Image(bytes=pic_bytes)])
                return m_res
            elif message_text.split()[-1].startswith("#"):
                page = int(message_text.split()[-1][1:]) - 1
                if page < 0 or page * 10 >= len(waifu_list):
                    return MessageChain.create([Plain(f"页数不合法")])
                page_range = [max(0, page * 10), min((page + 1) * 10, len(waifu_list))]
                pic_bytes = ranking_compose(waifu_list[page_range[0] : page_range[1]])
                m_res = MessageChain.create([Image(bytes=pic_bytes)])
                return m_res
            elif "我" in message_text:
                pos = [x for x in waifu_list if x["qq"] == str(message.member.id)]
                if not pos:
                    return MessageChain.create(
                        [Plain(f"{get_user_name(message)}你还没有锁定老婆，请【随机老婆】后【锁定老婆】才能进入排行")]
                    )
            else:
                member_id = message_text.strip().split()[-1]
                pos = [x for x in waifu_list if x["qq"] == member_id]
                if not pos:
                    return MessageChain.create([Plain(f"{member_id}不存在，或是没有锁定老婆")])
            display_range = [
                max(0, pos[0]["rank"] - 5),
                min(pos[0]["rank"] + 5, len(waifu_list)),
            ]
            pic_bytes = ranking_compose(
                waifu_list[display_range[0] : display_range[1]],
                highlight=pos[0]["rank"],
            )
            m_res = MessageChain.create([Image(bytes=pic_bytes)])
            return m_res

        elif message_text.startswith("我要NTR") or message_text.startswith("我要ntr"):
            content = message_text[5:].strip().replace("@", "")
            if not content:
                return MessageChain.create(
                    [
                        Plain(
                            f"输入【我要NTR QQ号】即可NTR对应人。NTR采取自动骰点进行，固定对象是固定防御骰。若NTR成功则直接替换我的对象。"
                        )
                    ]
                )

            try:
                tgt_user = SQLConnection.search(
                    "qq_waifu",
                    {
                        "id": content,
                    },
                )
                if not tgt_user:
                    raise Exception("id不存在")
            except Exception as e:
                return MessageChain.create([Plain(f"{content}不存在，或是未锁定对象")])
            if not (
                not user or not DatetimeUtils.is_today(tgt_user[0][6]) or user[1] > 5
            ):
                return MessageChain.create([Plain(f"每天一个人只能被NTR一次")])
            elif DatetimeUtils.is_today(user[2]) and not user[1] > 5: # type: ignore
                return MessageChain.create([Plain(f"每天运势/随机{schn}/NTR只能一次")])

            tgt_waifu = json.loads(tgt_user[0][3].replace("\\\"", "\""))
            if not tgt_waifu["def"]:
                tgt_dice = random.choice(self.def_dice_list)
                SQLConnection.update(
                    "qq_waifu",
                    { 
                        "otherDict": json.dumps(tgt_waifu, ensure_ascii=False),
                    },
                    {"id": content},
                )
            else:
                tgt_dice = tgt_waifu["def"]
            atk_dice = random.choice(self.atk_dice_list)
            tgt_roll = Dice.roll(tgt_dice)
            atk_roll = Dice.roll(atk_dice)
            info = (
                f"{get_user_name(message)}骰点({atk_dice})为: {atk_roll}\n"
                f"{tgt_waifu['name']}抵抗骰点({tgt_dice})为: {tgt_roll}\n"
            )
            SQLConnection.update_user(
                message.member.id, f"last_luck='{DatetimeUtils.get_now_time()}'"
            )

            if atk_roll <= tgt_roll:
                return MessageChain.create([Plain(info + f"NTR失败!")])

            tgt_waifu.update({"def": random.choice(self.def_dice_list)})
            if "pic_bytes" in tgt_waifu:
                tgt_waifu.__delitem__("pic_bytes")

            SQLConnection.delete("qq_waifu", {"id": content})
            my_waifu = SQLConnection.search("qq_waifu", {"id": str(message.member.id)})
            if not my_waifu:
                SQLConnection.insert(
                    "qq_waifu",
                    {
                        "name": str(get_user_name(message)),
                        "id": str(message.member.id),
                        "waifuId": tgt_user[0][1],
                        "waifuDict": tgt_user[0][2],
                        "otherDict": json.dumps(tgt_waifu, ensure_ascii=False),
                        "last_ntr": DatetimeUtils.get_now_time(),
                    },
                )
            else:
                SQLConnection.update(
                    "qq_waifu",
                    {
                        "waifuId": tgt_user[0][1],
                        "waifuDict": tgt_user[0][2],
                        "otherDict": json.dumps(tgt_waifu, ensure_ascii=False),
                        "last_ntr": DatetimeUtils.get_now_time(),
                    },
                    {"id": str(message.member.id)},
                )
            return MessageChain.create([Plain(info + f"NTR成功!")])

        return MessageChain.create([])

    def get_tmp_waifu(self, user):
        try:
            waifu_dict = json.loads(user[5]) # type: ignore
            waifu_id = waifu_dict['id']
            waifu_is_shine = waifu_dict['is_shine']
            waifu_no_center_box = waifu_dict['no_center_box']
        except Exception as e:
            waifu_id = user[5] # type: ignore
            waifu_is_shine, waifu_no_center_box = False, False
        return waifu_id,waifu_is_shine,waifu_no_center_box

    def get_waifu_list(self):
        waifu_list = SQLConnection.search("qq_waifu", {})
        waifu_list = sorted(
            [
                {
                    "id": x[4] if x[4] else x[0],
                    "qq": x[0],
                    "data": json.loads(x[3].replace("\\\"", "\"")),
                }
                for x in waifu_list
                if x[3] != "{}"
            ],
            key=lambda y: y["data"]["score"],
            reverse=True,
        )
        waifu_list = [
            {
                **x,
                "rank": i + 1,
            }
            for i, x in enumerate(waifu_list)
        ]
        return waifu_list

    def get_shine_score_ratio(self, is_shine, no_center_box):
        if is_shine:
            if no_center_box:
                return 2
            else:
                return 1.5
        else:
            return 1

    def get_waifu(self, qq_id):
        # id, waifuId, waifuDict, otherDict, name, credit
        src_user = SQLConnection.search(
            "qq_waifu",
            {
                "id": str(qq_id),
            },
        )
        if not src_user:
            return None
        else:
            return {
                "qq": src_user[0][0],
                "waifu_id": src_user[0][1],
                "waifu_dict": json.loads(src_user[0][2].replace("\\\"", "\"")),
                "other_dict": json.loads(src_user[0][3].replace("\\\"", "\"")),
                "qq_name": src_user[0][4],
            }

    def update_waifu_dict(self, qq_id, update_content):
        src_user = SQLConnection.search(
            "qq_waifu",
            { "id": str(qq_id) },
        )
        if not src_user:
            return False
        other_dict = json.loads(src_user[0][3].replace("\\\"", "\""))
        other_dict.update(update_content)
        SQLConnection.update(
            "qq_waifu",
            {
                "otherDict": json.dumps(other_dict, ensure_ascii=False),
            },
            { "id": str(qq_id) }
        )
