fpid=$(ps -aux | grep "nb_cli run" | grep -v grep | tail -n 1 | awk '{print $2}')
bpid=$(ps -aux | grep "mcl" | grep -v grep | tail -n 1 | awk '{print $2}')
echo $fpid
echo $bpid
kill -9 $fpid
kill -9 $bpid