import contextlib
import sys
import signal
from io import StringIO

from toogle.message_handler import MessagePack, MessageHandler
from toogle.message import MessageChain, Plain


def set_timeout(num, callback):
    def wrap(func):
        def handle(signum, frame):
            raise RuntimeError("运行超时!")

        def to_do(*args, **kwargs):
            try:
                signal.signal(signal.SIGALRM, handle)  # 设置信号和回调函数
                signal.alarm(num)  # 设置 num 秒的闹钟
                print("start alarm signal.")
                r = func(*args, **kwargs)
                print("close alarm signal.")
                signal.alarm(0)  # 关闭闹钟
                return r
            except RuntimeError as e:
                callback()

        return to_do

    return wrap


def handle_TLE():
    raise Exception("运行超时!")


class RunPython(MessageHandler):
    trigger = r"^#python#"
    readme = "简易python脚本运行，屏蔽敏感库(sys,os,dir,exec,eval等)"

    async def ret(self, message: MessagePack) -> MessageChain:
        text = message.message.asDisplay()[8:]
        running_res: str = RunPython.get_exec(text, message.member.id == 1149887546)
        return MessageChain.create([Plain(running_res)])

    @staticmethod
    @contextlib.contextmanager
    def stdoutIO(stdout=None):
        old = sys.stdout
        if stdout is None:
            stdout = StringIO()
        sys.stdout = stdout
        yield stdout
        sys.stdout = old

    @staticmethod
    def sensor_extract(text):
        return [
            x
            for x in [
                "os",
                "attr",
                "sys",
                "__",
                "dir",
                "exit",
                # "ls",
                "rm",
                "exec",
                "eval",
                "proc",
                "open",
                "file",
                "write",
                "PIPE",
                "std",
                "time",
            ]
            if x in text
        ]

    @staticmethod
    @set_timeout(2, handle_TLE)
    def get_exec(text, admin=False) -> str:
        try:
            sensors = RunPython.sensor_extract(text)
            if any(sensors):
                if admin:
                    raise Exception(f"含有危险词: {sensors}")
                raise Exception("含有危险词!")
            with RunPython.stdoutIO() as s:
                exec(text)
                running_res = s.getvalue()
                if len(running_res.split("\n")) > 20:
                    raise Exception("输出行数超长!")
                elif len(running_res) > 1000:
                    raise Exception("输出字数过多!")
        except Exception as e:
            running_res = repr(e)
        return running_res
