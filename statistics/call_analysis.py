import datetime
import json
import os


self_path = os.path.dirname(os.path.abspath(__file__))
log_path = "../log/call.log"
log_path = os.path.join(self_path, log_path)

def get_group_call_stats(group_id_list):
    time_split = {
        str(hour): {}
        for hour in range(24)
    }
    func_stat = {}
    total_num = 0
    with open(log_path, "r") as f:
        while True:
            line = f.readline()
            if not line:
                break
            call_func, call_timestamp, call_group_id, call_member_id = line.split('\t')
            if str(call_group_id) in group_id_list:
                continue
            call_time = datetime.datetime.fromtimestamp(float(call_timestamp))
            time_split[str(call_time.hour)][call_func] = time_split[str(call_time.hour)].get(call_func, 0) + 1
            func_stat[call_func] = func_stat.get(call_func, 0) + 1
            total_num += 1

    func_stat = dict(sorted(func_stat.items(), key=lambda x: x[1], reverse=True))
    for hour, stat in time_split.items():
        time_split[hour] = sorted(stat.items(), key=lambda x: x[1], reverse=True)
        time_split[hour] = dict(list(time_split[hour])[:3])
    
    func_stat = dict(list(func_stat.items())[:10])
    
    print(json.dumps(func_stat, indent=4, ensure_ascii=False))
    print(json.dumps(time_split, indent=4, ensure_ascii=False))

if __name__ == "__main__":
    get_group_call_stats(['867509065', '966731575'])
