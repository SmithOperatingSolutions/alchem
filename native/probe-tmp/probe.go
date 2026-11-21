// Temporary: what GetAddrInfoW and Go's net say of shorthand IPv4 names here.
package main

import (
	"fmt"
	"net"
	"syscall"
)

func main() {
	for _, name := range []string{"127.1", "0x7f.0.0.1", "2130706433", "127.0.0.1", "localhost"} {
		hints := syscall.AddrinfoW{Family: syscall.AF_UNSPEC, Socktype: syscall.SOCK_STREAM, Protocol: syscall.IPPROTO_IP}
		var result *syscall.AddrinfoW
		p, _ := syscall.UTF16PtrFromString(name)
		e := syscall.GetAddrInfoW(p, nil, &hints, &result)
		addrs, err := net.LookupHost(name)
		_, lerr := net.Listen("tcp", name+":0")
		fmt.Printf("%-12s GetAddrInfoW=%v  LookupHost=%v %v  Listen=%v\n", name, e, addrs, err, lerr)
	}
}
