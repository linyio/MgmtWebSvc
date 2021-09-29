#!/bin/bash
#Usage: <this-script> <down-info-file-path (ex. /var/run/openvpn/linyovpn-down.info)> <rest-of-params-insterted-by-openvpn>

#to see the script's debug messages uncomment the next line or add " -x" at the first line
#set -x

scriptDir=$(dirname $0)
. $scriptDir/liny-ovpn-common

#Brief: displays the dns servers as listed in the /etc/resolv.conf file
function DnsServers
{
    grep -E '^nameserver ' /etc/resolv.conf |
    while read keyword dns; do
        echo $dns
    done
}

#Some sanity checks
[ -z $(BinPath iptables) ] && echo "iptables not found in path. Please install it" && exit 1
infoFile=$1
infoFileDir=$(dirname $infoFile)
[ ! -d $infoFileDir ] && mkdir -p $infoFileDir
[ ! -d $infoFileDir ] && echo "mkdir \"$infoFileDir\" failed. Please remediate the error or specify a valid dir" && exit 2

#dump the interface to a special crafted file so that it will be used afterwards by the root-down plugin
echo "Interface: $dev">$infoFile
chmod 0700 $infoFile

#save the dns servers from the system, before adding the openvpn's one so we can block access to 
#them after it will be added
dnsServers=$(DnsServers)

#run the Liny's update-resolv-conf script from within the same folder
$scriptDir/liny-ovpn-update-resolv-conf
updateExitCode=$?

[[ $updateExitCode != 0 ]] && echo "Error adding dns server. Exiting ..." && exit $updateExitCode

#Block traffic to the existing dns servers so that there will be no dns requests leaks
for dns in $dnsServers; do
    echo "Bloking access to the $dns dns server"
    echo "Blocked dns: $dns" >>$infoFile
    for proto in tcp udp; do
	iptables -D OUTPUT -d $dns -p $proto --dport 53 -j REJECT &>/dev/null
	iptables -I OUTPUT 1 -d $dns -p $proto --dport 53 -j REJECT
    done
done

