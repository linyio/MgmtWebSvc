#!/bin/bash
#executed by the down-root plugin as root
#Usage: <this-script> <down-info-file-path (ex. /var/run/openvpn/linyovpn-down.info)>

#to see the script's debug messages uncomment the next line or add " -x" at the first line
#set -x

scriptDir=$(dirname $0)
. $scriptDir/liny-ovpn-common

#the script will be executed by the openvpn's down-root plugin which will discard the script's output. Messages we'll be logged to syslog using logger
loggerTag=liny-ovpn-down-root
log="logger -t $loggerTag"


#Some sanity checks
[ -z $1 ] && $log "Down root script No param given. Usage: \"$0\" <down-info-file-path (ex. /var/run/openvpn/linyovpn-down.info)>\""
infoFile=$1
[ -z $(BinPath iptables) ] && $log "iptables not found in path. Please install it" && exit 1
[ ! -r $infoFile ] && $log "The \"$infoFile\" info file is missing or has no read access" && exit 2

#run the update-resolv-conf script from within the same folder
script_type=down dev=$(Dev $infoFile) $scriptDir/liny-ovpn-update-resolv-conf

#unblock access to the original dns servers
for dns in $(BlockedDns $infoFile); do
    iptables -D OUTPUT -d $dns -p tcp --dport 53 -j REJECT
    iptables -D OUTPUT -d $dns -p udp --dport 53 -j REJECT
done

#cleanup the info file
rm $infoFile
