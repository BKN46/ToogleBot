import contextlib
import sys
from io import StringIO

from toogle.configs import config
from toogle.message import MessageChain, Plain
from toogle.message_handler import MessageHandler, MessagePack
from toogle.utils import handle_TLE, set_timeout


class RunPython(MessageHandler):
    name = "Python解释器"
    trigger = r"^#python#"
    readme = "简易python脚本运行，屏蔽敏感库(sys,os,dir,exec,eval等)"
    price = 5

    async def ret(self, message: MessagePack) -> MessageChain:
        text = message.message.asDisplay()[8:]
        running_res: str = RunPython.get_exec(text, str(message.member.id) in config["SUPERUSERS"])
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


class RunLua(MessageHandler):
    name = "Lua解释器"
    trigger = r"^#lua#"
    readme = "简易lua脚本运行"
    price = 5
    
    async def ret(self, message: MessagePack) -> MessageChain:
        text = message.message.asDisplay()[5:]
        running_res: str = RunLua.get_exec(text, str(message.member.id) in config["SUPERUSERS"])
        return MessageChain.create([Plain(running_res)])

    @staticmethod
    def sensor_extract(text):
        return [
            x
            for x in [
                "os.",
                "io.",
                "file",
            ]
            if x in text
        ]

    @staticmethod
    @set_timeout(2, handle_TLE)
    def get_exec(text, admin=False) -> str:
        try:
            sensors = RunLua.sensor_extract(text)
            if any(sensors):
                if admin:
                    raise Exception(f"含有危险词: {sensors}")
                raise Exception("含有危险词!")
            with RunPython.stdoutIO() as s:
                import lupa
                lua = lupa.LuaRuntime(unpack_returned_tuples=True)
                lua.globals()['print'] = print
                lua.execute(text)
                running_res = s.getvalue()
                if len(running_res.split("\n")) > 20:
                    raise Exception("输出行数超长!")
                elif len(running_res) > 1000:
                    raise Exception("输出字数过多!")
        except Exception as e:
            running_res = repr(e)
        return running_res
