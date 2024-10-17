# 消息

## MessagePack

`MessagePack`是消息的封装类，包含了消息的发送者、群聊信息、消息内容、消息ID等信息。  
处理接收消息时，会将消息解析为`MessagePack`对象，作为入参在函数的`ret`方法中处理。

## MessageChain

消息的发送主要是通过`MessageChain`类来实现的。`MessageChain`是一个消息链，可以包含多个消息元素`Element`，每个消息元素可以是文本、图片、表情等。  
一条消息链就是一条消息，可以发送给一个或多个人。

## Element

### Plain

### At

### Image
