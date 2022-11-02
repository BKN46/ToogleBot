if["$(uname)"=="Darwin"];then
./mcl-installer-1.0.7-macos-amd64
elif["$(expr substr $(uname -s) 1 5)"=="Linux"];then   
./mcl-installer-1.0.7-linux-amd64
fi
./mcl --update-package net.mamoe:mirai-api-http --channel stable-v2 --type plugin
./mcl