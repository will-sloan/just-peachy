"""PrintWindow renders of a known synthetic Tk app on an isolated desktop only.

No screenshot of the user's screen, input injection, hardware or model calls.
Run via run_private_desktop.py; see README_N1_FRONTEND.md.
"""
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import struct
import tkinter as tk
import unittest
from unittest.mock import patch
import zlib

from prototype.app.ui import PrototypeUI, prepare_dpi_awareness
from prototype.tests.n1_event_fixtures import scenarios
from prototype.tests.test_n1_frontend import EventController
from prototype.tests.run_private_desktop import desktop_name, setup_api


def render_client(root, path):
    user32 = setup_api(); gdi = ctypes.windll.gdi32
    user32.GetAncestor.argtypes = [wintypes.HWND,wintypes.UINT]; user32.GetAncestor.restype = wintypes.HWND
    user32.GetDC.argtypes = [wintypes.HWND]; user32.GetDC.restype = wintypes.HDC
    user32.ReleaseDC.argtypes = [wintypes.HWND,wintypes.HDC]
    user32.PrintWindow.argtypes = [wintypes.HWND,wintypes.HDC,wintypes.UINT]
    gdi.CreateCompatibleDC.argtypes = [wintypes.HDC]; gdi.CreateCompatibleDC.restype = wintypes.HDC
    gdi.CreateCompatibleBitmap.argtypes = [wintypes.HDC,ctypes.c_int,ctypes.c_int]; gdi.CreateCompatibleBitmap.restype = wintypes.HBITMAP
    gdi.SelectObject.argtypes = [wintypes.HDC,wintypes.HANDLE]; gdi.SelectObject.restype = wintypes.HANDLE
    gdi.DeleteObject.argtypes = [wintypes.HANDLE]; gdi.DeleteDC.argtypes = [wintypes.HDC]
    gdi.GetDIBits.argtypes = [wintypes.HDC,wintypes.HBITMAP,wintypes.UINT,wintypes.UINT,ctypes.c_void_p,ctypes.c_void_p,wintypes.UINT]
    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [('biSize',wintypes.DWORD),('biWidth',wintypes.LONG),('biHeight',wintypes.LONG),
            ('biPlanes',wintypes.WORD),('biBitCount',wintypes.WORD),('biCompression',wintypes.DWORD),
            ('biSizeImage',wintypes.DWORD),('biXPelsPerMeter',wintypes.LONG),('biYPelsPerMeter',wintypes.LONG),
            ('biClrUsed',wintypes.DWORD),('biClrImportant',wintypes.DWORD)]
    hwnd = user32.GetAncestor(root.winfo_id(),2)
    width,height = root.winfo_width(),root.winfo_height()
    source = user32.GetDC(hwnd); target = gdi.CreateCompatibleDC(source)
    bitmap = gdi.CreateCompatibleBitmap(source,width,height); old = gdi.SelectObject(target,bitmap)
    try:
        if not user32.PrintWindow(hwnd,target,1): raise OSError('PrintWindow did not render the private app')
        info = BITMAPINFOHEADER(); info.biSize=ctypes.sizeof(info); info.biWidth=width; info.biHeight=-height
        info.biPlanes=1; info.biBitCount=32
        buffer = ctypes.create_string_buffer(width*height*4)
        gdi.SelectObject(target,old)
        if not gdi.GetDIBits(target,bitmap,0,height,buffer,ctypes.byref(info),0): raise ctypes.WinError()
        pixels = buffer.raw
        if len({pixels[i:i+3] for i in range(0,len(pixels),4)}) < 12:
            raise OSError('Private-desktop render is blank')
        rgb = bytearray(width*height*3)
        rgb[0::3] = pixels[2::4]; rgb[1::3] = pixels[1::4]; rgb[2::3] = pixels[0::4]
        # Standard-library PNG encoding keeps the original app environment intact.
        def chunk(kind, data):
            return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
        filtered = b''.join(b'\x00'+rgb[y*width*3:(y+1)*width*3] for y in range(height))
        path.write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',width,height,8,2,0,0,0))+
                         chunk(b'IDAT',zlib.compress(filtered,6))+chunk(b'IEND',b''))
        return dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),width=width,height=height,
            scope='Known app client PrintWindow rendering on private desktop; no user screen or physical scanout')
    finally:
        gdi.SelectObject(target,old); gdi.DeleteObject(bitmap); gdi.DeleteDC(target); user32.ReleaseDC(hwnd,source)


class N1CaptureTests(unittest.TestCase):
    def test_render_shared_frontend_event_screens(self):
        if os.name != 'nt' or not os.environ.get('N1_UI_RECEIPT_DIR'):
            self.skipTest('Requires explicit private-desktop launcher')
        user32 = setup_api()
        actual = desktop_name(user32.GetThreadDesktop(ctypes.windll.kernel32.GetCurrentThreadId()))
        self.assertTrue(actual.startswith('codex-n1-'), 'Refuse creating mapped Tk on user desktop')
        folder = Path(os.environ['N1_UI_RECEIPT_DIR'])/'screenshots'; folder.mkdir(exist_ok=True)
        prepare_dpi_awareness(); root = tk.Tk(); controller = EventController()
        controller.data['status'] = 'SYNTHETIC EVENT · no microphone / models'
        ui = PrototypeUI(root,controller,allow_auto_start=False)
        receipts=[]
        def capture(name):
            root.update()
            self.assertEqual((root.winfo_width(),root.winfo_height()),(480,800))
            receipts.append(render_client(root,folder/(name+'.png')))
        try:
            capture('01-idle')
            with patch('prototype.app.ui.time.perf_counter',return_value=10) as clock:
                for index,(name,steps) in enumerate(scenarios().items(),2):
                    rows=steps[-1]; controller.data['rows']=rows; ui.snapshot=controller.snapshot()
                    ui._render_rows(rows); clock.return_value += .3; ui._render_rows(rows)
                    capture(f'{index:02d}-'+name)
            ui.show_backends(); capture('07-backend-selector')
            (folder/'presentation_receipts.json').write_text(json.dumps(ui.presentation_receipts,indent=2)+'\n',encoding='utf-8')
            (folder/'render_receipts.json').write_text(json.dumps(receipts,indent=2)+'\n',encoding='utf-8')
        finally:
            ui.close(); ui.poll()


if __name__ == '__main__': unittest.main()
