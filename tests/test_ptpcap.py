# SPDX-License-Identifier: MIT
import contextlib
import io
from pathlib import Path
import struct
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import ptpcap


def ptp(kind, code, tid, data=b'', declared=None):
    return struct.pack('<IHHI', declared or len(data)+12, kind, code, tid)+data


def usb(data, ep=1, device=2):
    h=bytearray(27)
    struct.pack_into('<H',h,0,27)
    struct.pack_into('<HH',h,17,1,device)
    h[21]=ep;h[22]=3
    struct.pack_into('<I',h,23,len(data))
    return bytes(h)+data


def pcap(frames, endian='<', nano=False, linktype=249):
    magic=(b'\x4d\x3c\xb2\xa1' if nano else b'\xd4\xc3\xb2\xa1') if endian=='<' else (b'\xa1\xb2\x3c\x4d' if nano else b'\xa1\xb2\xc3\xd4')
    out=magic+struct.pack(endian+'HHIIII',2,4,0,0,65535,linktype)
    for i,frame in enumerate(frames):
        out+=struct.pack(endian+'IIII',1,500000+i,len(frame),len(frame))+frame
    return out


class CaptureTests(unittest.TestCase):
    def decode(self, data, recover=False):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'capture'; p.write_bytes(data)
            issues=[]
            return ptpcap.transactions(p,recover,issues),issues

    def test_split_header_payload_and_multiple_containers(self):
        cmd=ptp(1,0x1015,1,struct.pack('<I',0xd185))
        data=ptp(2,0x1015,1,b'abcd')
        frames=[usb(cmd[:5]),usb(cmd[5:]),usb(data[:14],129),usb(data[14:]+ptp(3,0x2001,1),129)]
        tx,issues=self.decode(pcap(frames))
        self.assertEqual(tx[1]['in'],b'abcd');self.assertEqual(tx[1]['resp'],0x2001)
        self.assertEqual(issues,[])

    def test_loss_is_explicit_and_partial_data_never_complete(self):
        frames=[usb(ptp(1,0x1009,1,struct.pack('<I',1))),
                usb(ptp(2,0x1009,1,b'JPEG prefix',declared=1000),129),
                usb(ptp(3,0x2001,1),129),
                usb(ptp(1,0x1015,2,struct.pack('<I',0xd185))),
                usb(ptp(2,0x1015,2,b'profile')+ptp(3,0x2001,2),129)]
        tx,issues=self.decode(pcap(frames),True)
        self.assertIsNone(tx[1]['in']);self.assertEqual(tx[1]['in_partial'],b'JPEG prefix')
        self.assertEqual(tx[2]['in'],b'profile')
        self.assertTrue(any(x['reason']=='packet_boundary_resync' for x in issues))
        strict,_=self.decode(pcap(frames),False)
        self.assertIsNone(strict[2]['in'])

    def test_known_usb_and_pcap_gaps_cannot_be_filled_by_later_bytes(self):
        for gap_source in ('usb', 'pcap'):
            frames=[usb(ptp(1,0x1009,1)), usb(ptp(2,0x1009,1,b'ab',declared=16),129),
                    usb(b'XY',129), usb(ptp(3,0x2001,1),129)]
            if gap_source=='usb':
                frame=bytearray(frames[1]);struct.pack_into('<I',frame,23,16);frames[1]=bytes(frame)
            data=bytearray(pcap(frames))
            if gap_source=='pcap':
                second=24+16+len(frames[0])
                struct.pack_into('<I',data,second+12,len(frames[1])+2)
            tx,issues=self.decode(bytes(data),True)
            self.assertIsNone(tx[1]['in']);self.assertEqual(tx[1]['in_partial'],b'ab')
            self.assertTrue(any(x['reason']=='known_packet_gap' for x in issues))

    def test_profile_baselines_are_per_device_and_session(self):
        frames=[]
        for device,value,tid in [(2,1,1),(3,99,1),(2,2,2)]:
            if tid==2:
                frames.append(usb(ptp(1,0x1002,8),device=device))
            profile=b'\0'*0x1fd+struct.pack('<i',value)
            frames.extend([usb(ptp(1,0x1016,tid,struct.pack('<I',0xd185)),device=device),
                           usb(ptp(2,0x1016,tid,profile),device=device)])
        tx,_=self.decode(pcap(frames));rows=ptpcap.profile_rows(tx)
        self.assertEqual([r['changes'] for r in rows],[[],[],[]])
        self.assertNotEqual(rows[0]['device'],rows[1]['device'])
        self.assertNotEqual(rows[0]['session'],rows[2]['session'])
        self.assertEqual(len({r['transaction_key'] for r in rows}),3)

    def test_getobject_error_does_not_report_successful_transfer(self):
        segment=b'Exif\0\0II*\0\x08\0\0\0\0\0\0\0\0\0'
        jpeg=b'\xff\xd8\xff\xe1'+struct.pack('>H',len(segment)+2)+segment+b'\xff\xd9'
        tx={1:{'tid':1,'op':0x1009,'in':jpeg,'in_partial':None,'resp':0x2002}}
        r=ptpcap.metadata_rows(tx)[0]
        self.assertTrue(r['data_container_complete']);self.assertFalse(r['transfer_complete'])
        self.assertEqual(r['operation_response'],0x2002)

    def test_random_header_not_matching_command_is_not_resync(self):
        fake=ptp(3,0x2001,999)
        frames=[usb(ptp(1,0x1009,1)),usb(ptp(2,0x1009,1,b'prefix',declared=30),129),usb(fake,129)]
        tx,issues=self.decode(pcap(frames),True)
        self.assertFalse(any(x['reason']=='packet_boundary_resync' for x in issues))
        self.assertEqual(tx[1]['in'],b'prefix'+fake)

    def test_isolates_devices_and_retains_reused_transaction_ids(self):
        frames=[]
        for device,value in [(2,b'aa'),(3,b'bb'),(2,b'cc')]:
            frames.extend([usb(ptp(1,0x1015,1),device=device),usb(ptp(2,0x1015,1,value),129,device)])
        tx,_=self.decode(pcap(frames))
        self.assertEqual([t['in'] for t in tx.values()],[b'aa',b'bb',b'cc'])

    def test_big_endian_nanoseconds(self):
        tx,_=self.decode(pcap([usb(ptp(1,0x1002,1))],'>',True))
        self.assertEqual(tx[1]['ts'],1000500)

    def test_usbmon_bulk_header_and_data_flag(self):
        h=bytearray(64);h[8]=ord('C');h[9]=3;h[10]=129;h[11]=2
        struct.pack_into('<H',h,12,1);struct.pack_into('<I',h,36,3)
        self.assertEqual(ptpcap.bulk_payload(220,bytes(h)+b'abc'),('IN',b'abc'))
        h[15]=ord('>');self.assertIsNone(ptpcap.bulk_payload(220,bytes(h)+b'abc'))

    def test_pcapng_binary_timestamp_and_section_reset(self):
        def block(kind,body,endian):
            size=12+len(body)
            return struct.pack(endian+'II',kind,size)+body+struct.pack(endian+'I',size)
        def section(endian,ep):
            sh=block(0x0a0d0d0a,struct.pack(endian+'IHHq',0x1a2b3c4d,1,0,-1),endian)
            opts=struct.pack(endian+'HH',9,1)+b'\x8a\0\0\0'+b'\0'*4
            idb=block(1,struct.pack(endian+'HHI',249,0,65535)+opts,endian)
            f=usb(ptp(1,0x1002,ep)); pad=b'\0'*((-len(f))%4)
            pkt=block(6,struct.pack(endian+'IIIII',0,0,1024,len(f),len(f))+f+pad,endian)
            return sh+idb+pkt
        tx,_=self.decode(section('<',1)+section('>',2))
        self.assertEqual([t['ts'] for t in tx.values()],[1000000,1000000])

    def test_merged_interfaces_with_same_usb_addresses_are_isolated(self):
        def block(kind,body):
            size=12+len(body)
            return struct.pack('<II',kind,size)+body+struct.pack('<I',size)
        sh=block(0x0a0d0d0a,struct.pack('<IHHq',0x1a2b3c4d,1,0,-1))
        idb=block(1,struct.pack('<HHI',249,0,65535))
        data=sh+idb+idb
        for iface,frame in [(0,usb(ptp(1,0x1015,1))),(1,usb(ptp(1,0x1015,1))),
                            (0,usb(ptp(2,0x1015,1,b'aa'),129)),(1,usb(ptp(2,0x1015,1,b'bb'),129))]:
            data+=block(6,struct.pack('<IIIII',iface,0,1,len(frame),len(frame))+frame+b'\0'*((-len(frame))%4))
        tx,_=self.decode(data)
        self.assertEqual([t['in'] for t in tx.values()],[b'aa',b'bb'])
        self.assertNotEqual(*[t['device'] for t in tx.values()])

    def test_rejects_corrupt_capture_structures(self):
        for data in [b'bad',pcap([])+b'bad',b'\x0a\x0d\x0d\x0a'+b'\0'*8]:
            with self.subTest(data=data),self.assertRaises(ptpcap.CaptureError): self.decode(data)

    def test_metadata_prefix_requires_complete_sequential_app1(self):
        app1=b'Exif\0\0test';segment=b'\xff\xe1'+struct.pack('>H',len(app1)+2)+app1
        jpeg=b'\xff\xd8'+segment+b'\xff\xda\0\x02pixels'
        self.assertEqual(ptpcap.jpeg_metadata_envelope(jpeg),b'\xff\xd8'+segment+b'\xff\xd9')
        self.assertIsNone(ptpcap.jpeg_metadata_envelope(jpeg[:8]))
        self.assertIsNone(ptpcap.jpeg_metadata_envelope(b'garbage'+jpeg))

    def test_text_output_does_not_dump_device_info_objects_or_names(self):
        frames=[]
        for tid,op,params in [(1,0x1001,b''),(2,0x1009,b''),(3,0x1015,struct.pack('<I',0xd18d))]:
            frames.extend([usb(ptp(1,op,tid,params)),usb(ptp(2,op,tid,b'PRIVATE')+ptp(3,0x2001,tid),129)])
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'cap';p.write_bytes(pcap(frames))
            buf=io.StringIO()
            with contextlib.redirect_stdout(buf): self.assertEqual(ptpcap.main([str(p),'--all']),0)
            self.assertNotIn('PRIVATE',buf.getvalue());self.assertNotIn(b'PRIVATE'.hex().upper(),buf.getvalue())

    def test_profile_diffs_preserve_signed_cells(self):
        data=b'\0'*0x1fd+struct.pack('<3i',1,-2,0)
        tx={1:{'op':0x1016,'params':[0xd185],'out':data,'in':None,'resp':0x2001,'tid':1}}
        rows=ptpcap.profile_rows(tx)
        self.assertEqual(rows[0]['cells'],[1,-2,0])
        tx[2]=dict(tx[1],tid=2,out=data[:-4]+struct.pack('<i',3))
        self.assertEqual(ptpcap.profile_rows(tx)[1]['changes'],[{'cell':2,'before':0,'after':3}])


if __name__=='__main__': unittest.main()
