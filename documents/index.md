# 大黄狗插件编写

## Hello world

我们首先来看一个最简单的例子，一个Hello world插件。  
目的是发送`helloworld`时，回复一条`Hello world!`消息。

```python
from toogle.message import MessageChain
from toogle.message_handler import MessageHandler, MessagePack

class HelloworldPlugin(MessageHandler):
    name = "第一个插件"
    trigger = r"^helloworld$"
    readme = "测试插件，满足正则时发送Helloworld"

    async def ret(self, message: MessagePack):
        return MessageChain.plain("Hello world!")
```

首先我们需要创建一个`MessageHandler`的子类，作为插件的主体。并填好下方`name`、`trigger`、`readme`三个属性。  
`name`是插件的名称，用于在插件列表中展示，请保持简洁。  
其中`trigger`最为重要，直接控制了插件的触发条件，文本只有在满足该正则的条件下才会触发该插件。  
`readme`是插件的说明，用于在插件列表中展示。  
