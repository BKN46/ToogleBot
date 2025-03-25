import json
import os
import re

from bs4 import BeautifulSoup as bs
from flask.cli import F
import requests

BUFFER_FILE_DIR = 'data/gf2_mcc_data/'
DOLL_DATA = {}

def get_continues_json(s: str):
    s=re.split(';import|;return|;const|;\n', s)[17]
    s = s.split('const')[1][3:].strip()
    cnt, start_pos, pos, start=0, 0, 0, False
    for t in s:
        if t=='{':
            if not start:
                start=True
                start_pos=pos
            cnt+=1
        elif t=='}':
            cnt-=1
        if cnt==0:
            break
        pos+=1
    tmp_str = s[start_pos:pos+1]
    if tmp_str.count('{') != s.count('}'):
        tmp_str=','.join(s.split(',')[:-1])
    tmp_str = re.sub(r'([,\{])([A-z0-9]+):', r'\1"\2":', tmp_str)
    def test(matcher):
        fix_str = matcher.group(2).replace('\\','').replace('"',"").replace("'", '').replace('`', '')
        return f'{matcher.group(1)}:"{fix_str}"{matcher.group(5)}'
    tmp_str = re.sub(r'''("Desc"|"Upgrade"|"SkillUpgrade"|"PrivateSkill"|"FixedSkill"):((`|').*?(`|'))(,|\})''', test, tmp_str)
    return json.loads(tmp_str)


def reload_all_data():
    for file in os.listdir(BUFFER_FILE_DIR):
        if file.endswith('scan_buffer.json'):
            continue
        if file.endswith('.json'):
            DOLL_DATA[file.split('.')[0]] = json.loads(open(os.path.join(BUFFER_FILE_DIR, file), 'r').read())


reload_all_data()


def gf2_mcc_doll_data(overall_update=False, ignore_buffer=False):
    if not os.path.exists(BUFFER_FILE_DIR):
        os.makedirs(BUFFER_FILE_DIR, exist_ok=True)
    scan_buffer_file = os.path.join(BUFFER_FILE_DIR, 'scan_buffer.json')
    if not os.path.exists(scan_buffer_file):
        open(scan_buffer_file, 'w').write('[]')
    scan_buffer = json.loads(open(scan_buffer_file, 'r').read())

    host = 'http://gf2.mcc.wiki'
    res = requests.get(f'{host}/doll')
    soup = bs(res.text, 'html.parser')
    all_dolls_link = [
        f"{host}{x['href']}"
        for x in soup.findAll('a')
        if x['href'].startswith('/doll/')
    ]

    data_link = soup.findAll('link', {'rel': 'modulepreload'})[0]['href'] # type: ignore
    js_data = requests.get(f'{host}{data_link}').text # type: ignore        
    all_js_list = [
        x for x in json.loads(js_data.split(')))')[0].split('m.f||(m.f=')[1].strip())
        if x.endswith('.js')
    ]
    
    all_exist_js_link = [v['js_link'] for k, v in DOLL_DATA.items()]

    # filter out doll js data
    from tqdm import tqdm
    for js_link in tqdm(all_js_list):
        if not overall_update and js_link in all_exist_js_link:
            continue
        js_file = js_link.split('/')[-1] + '.raw'
        if not ignore_buffer and js_link in scan_buffer:
            continue
        js_data = requests.get(f'{host}/_nuxt{js_link[1:]}').text
        if '({__name:"Weapon_' in js_data:
            continue
        for filter_word in ['={Id:', 'Id', 'Rank', 'Desc', 'WeaponType']:
            if filter_word not in js_data:
                scan_buffer.append(js_link)
                open(scan_buffer_file, 'w').write(json.dumps(scan_buffer, indent=4))
                break
        else:
            open(os.path.join(BUFFER_FILE_DIR, js_file), 'w').write(js_data)
            try:
                json_data = get_continues_json(js_data)
            except Exception as e:
                print(f'Error in read {js_file}')
                continue
            json_data['js_link'] = js_link
            doll_code = json_data['Code']
            doll_file = f'{doll_code}.json'
            open(os.path.join(BUFFER_FILE_DIR, doll_file), 'w').write(json.dumps(json_data, indent=4, ensure_ascii=False))
            os.remove(os.path.join(BUFFER_FILE_DIR, js_file))
            print(f'Write {json_data["Name"]} {doll_file} success')
            scan_buffer.append(js_link)
            open(scan_buffer_file, 'w').write(json.dumps(scan_buffer, indent=4))
            continue
    return True


WEAPON_TYPE_MAPPING = {
    1: '',
    2: '手枪',
    3: '狙击步枪',
    4: '突击步枪',
    5: '机枪',
    6: '霰弹枪',
    7: '近战',
}
BULLET_TYPE_MAPPING = {
    1: '',
    2: '',
    3: '',
    4: '',
    5: '',
    6: '',
    7: '',
    8: '',
}
SKILL_TYPE_MAPPING = {
    'NormalAttack': '普通攻击',
    'ActiveSkill1': '技能1',
    'ActiveSkill2': '技能2',
    'UltimateSkill': '制胜技能',
    'PassiveSkill': '被动',
    'ExtraSkill1': '额外技能1',
    'ExtraSkill2': '额外技能2',
}

def parse_css_text(s, tooltip_bool=[]):
    tooltip_list = []
    def get_tooltip(matcher):
        content = matcher.group(0).split('</div>')
        content = content[0] + ': ' + ''.join(content[1:])
        content = re.sub(r'<.*?>', '', content).replace('raw-content>', '').strip()
        title = content.split(': ')[0]
        if not title in tooltip_bool:
            tooltip_list.append(content)
            tooltip_bool.append(title)
        return ''
    s = re.sub(r'<el-tooltip.*?raw-content>', get_tooltip, s)
    s = re.sub(r'<.*?>', '', s)
    return f"{s}\n" + '\n'.join(tooltip_list)

def parse_single_doll(doll_data):
    doll_name = doll_data['Name']

    weapon = doll_data['PrivateWeapon'][-1]
    weapon_name = weapon['Name']
    weapon_code = '_'.join(weapon['Code'].split('_')[1:-1])
    # weapon_type = WEAPON_TYPE_MAPPING.get(weapon['WeaponType'], '未知武器类型')
    weapon_skill = parse_css_text(weapon['Skill'][-1]['Desc']) + '\n' + parse_css_text(weapon.get('FixedSkill'))
    if 'PrivateSkill' in weapon:
        private_doll = weapon.get('PrivateDolls', [{}])[0].get('Name', '')
        weapon_skill += f'\n{private_doll}专属: ' + parse_css_text(weapon.get('PrivateSkill'))
    
    skills = {}
    for skill_type in ['NormalAttack', 'ActiveSkill1', 'ActiveSkill2', 'UltimateSkill', 'PassiveSkill', 'ExtraSkill1', 'ExtraSkill2']:
        if skill_type not in doll_data or not doll_data[skill_type]:
            continue
        skills[skill_type] = doll_data[skill_type][-1]['Name'] + ": "
        tooltip_bool = []
        skills[skill_type] += parse_css_text(doll_data[skill_type][-1]['Desc'], tooltip_bool=tooltip_bool)
        if doll_data[skill_type][-1].get('Upgrade'):
            skills[skill_type] += '\n升级: ' + parse_css_text(doll_data[skill_type][-1]['Upgrade'], tooltip_bool=tooltip_bool)
            
    talent_keys = {}
    for talent in doll_data.get('TalentKey', []):
        talent_keys[talent['Name']] = parse_css_text(talent['Desc'])

    return [
        f'[武器]{weapon_name}(原型{weapon_code}): {weapon_skill}',
        *[
            f'[{doll_name}({weapon_code})][{SKILL_TYPE_MAPPING[k]}]{v}'
            for k, v in skills.items()
        ],
        *[
            f'[{doll_name}({weapon_code})][{k}]: {v}'
            for k, v in talent_keys.items()
        ],
    ]


def general_search(text):
    query = text.split('>')
    res = []
    for doll in DOLL_DATA.values():
        search_lines = parse_single_doll(doll)
        for line in search_lines:
            q = query[0].strip()
            if q.startswith('!'):
                if q[1:] not in line:
                    res.append(line)
            elif q in line:
                res.append(line)
    if len(query) > 1:
        for q in query[1:]:
            q = q.strip()
            if q.startswith('!'):
                res = [x for x in res if q[1:] not in x]
            else:
                res = [x for x in res if q in x]
    for q in query:
        res = [x.replace(q, f'【{q}】') for x in res]
    return res


if __name__ == "__main__":
    # get_continues_json(open('data/gf2_mcc_data/Bla43Ntv.js.raw', 'r').read())
    print(gf2_mcc_doll_data(ignore_buffer=False))
    # print('\n======\n'.join(general_search("K2>驱散>!不可驱散")))