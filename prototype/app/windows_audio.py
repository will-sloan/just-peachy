"""Read-only Windows Core Audio endpoint identities; no policy/setter API."""
from __future__ import annotations

import ctypes as C
import os
import uuid
from datetime import datetime, timezone


def endpoint_snapshot() -> dict:
    """Return active capture IDs and all three default render role IDs.

    COM is initialized/uninitialized on the calling thread. No audio stream,
    volume method, registry operation or default-endpoint setter is present.
    Non-Windows imports remain usable and return NOT_APPLICABLE.
    """
    result = {"utc": datetime.now(timezone.utc).isoformat(), "read_only": True,
              "default_render": {}, "capture_endpoints": [], "status": "NOT_APPLICABLE"}
    if os.name != "nt":
        return result

    class GUID(C.Structure):
        _fields_ = [("data", C.c_ubyte * 16)]

        @classmethod
        def parse(cls, value):
            return cls((C.c_ubyte * 16).from_buffer_copy(uuid.UUID(value).bytes_le))

    class PROPERTYKEY(C.Structure):
        _fields_ = [("fmtid", GUID), ("pid", C.c_ulong)]

    # PROPVARIANT is 24 bytes on Win64, 16 on Win32. vt and pointer are enough
    # for PKEY_Device_FriendlyName (VT_LPWSTR); native clear releases storage.
    class PV(C.Structure):
        _fields_ = [("vt", C.c_ushort), ("reserved", C.c_ushort * 3),
                    ("value", C.c_void_p), ("tail", C.c_ulonglong if C.sizeof(C.c_void_p) == 8 else C.c_ulong)]

    # WinDLL leaves HRESULT inspection to us; OleDLL would raise on the benign
    # RPC_E_CHANGED_MODE return before we can respect the caller's apartment.
    ole = C.WinDLL("ole32")
    ole.CoInitializeEx.argtypes = [C.c_void_p, C.c_ulong]
    ole.CoInitializeEx.restype = C.c_long
    ole.CoCreateInstance.argtypes = [C.POINTER(GUID), C.c_void_p, C.c_ulong, C.POINTER(GUID), C.POINTER(C.c_void_p)]
    ole.CoCreateInstance.restype = C.c_long
    ole.CoTaskMemFree.argtypes = [C.c_void_p]
    ole.PropVariantClear.argtypes = [C.POINTER(PV)]

    def method(ptr, slot, restype, *argtypes):
        table = C.cast(ptr, C.POINTER(C.POINTER(C.c_void_p))).contents
        return C.WINFUNCTYPE(restype, C.c_void_p, *argtypes)(table[slot])

    def checked(hr):
        if hr < 0:
            raise OSError(f"Core Audio HRESULT 0x{hr & 0xffffffff:08x}")

    def release(ptr):
        if ptr:
            method(ptr, 2, C.c_ulong)(ptr)

    def device_info(device):
        value = C.c_void_p()
        checked(method(device, 5, C.c_long, C.POINTER(C.c_void_p))(device, C.byref(value)))
        try:
            ident = C.wstring_at(value)
        finally:
            ole.CoTaskMemFree(value)
        store, pv = C.c_void_p(), PV()
        name = None
        try:
            checked(method(device, 4, C.c_long, C.c_ulong, C.POINTER(C.c_void_p))(device, 0, C.byref(store)))
            key = PROPERTYKEY(GUID.parse("a45c254e-df1c-4efd-8020-67d146a850e0"), 14)
            checked(method(store, 5, C.c_long, C.POINTER(PROPERTYKEY), C.POINTER(PV))(store, C.byref(key), C.byref(pv)))
            if pv.vt == 31 and pv.value:
                name = C.wstring_at(pv.value)
        finally:
            ole.PropVariantClear(C.byref(pv))
            release(store)
        return {"endpoint_id": ident, "name": name}

    enum, collection = C.c_void_p(), C.c_void_p()
    initialized = False
    try:
        hr = ole.CoInitializeEx(None, 0)
        # RPC_E_CHANGED_MODE: caller already initialized COM in an apartment.
        if (hr & 0xffffffff) != 0x80010106:
            checked(hr)
            initialized = True
        clsid = GUID.parse("bcde0395-e52f-467c-8e3d-c4579291692e")
        iid = GUID.parse("a95664d2-9614-4f35-a746-de8db63617e6")
        checked(ole.CoCreateInstance(C.byref(clsid), None, 1, C.byref(iid), C.byref(enum)))
        for role, label in enumerate(("console", "multimedia", "communications")):
            device = C.c_void_p()
            try:
                checked(method(enum, 4, C.c_long, C.c_int, C.c_int, C.POINTER(C.c_void_p))(enum, 0, role, C.byref(device)))
                result["default_render"][label] = device_info(device)
            except OSError as exc:
                result["default_render"][label] = {"error": str(exc)}
            finally:
                release(device)
        checked(method(enum, 3, C.c_long, C.c_int, C.c_ulong, C.POINTER(C.c_void_p))(enum, 1, 1, C.byref(collection)))
        count = C.c_uint()
        checked(method(collection, 3, C.c_long, C.POINTER(C.c_uint))(collection, C.byref(count)))
        for index in range(count.value):
            device = C.c_void_p()
            try:
                checked(method(collection, 4, C.c_long, C.c_uint, C.POINTER(C.c_void_p))(collection, index, C.byref(device)))
                result["capture_endpoints"].append(device_info(device))
            finally:
                release(device)
        result["status"] = "PASS"
    except Exception as exc:
        result.update(status="UNAVAILABLE", error=str(exc))
    finally:
        release(collection)
        release(enum)
        if initialized:
            ole.CoUninitialize()
    return result


def compare_defaults(before: dict, after: dict) -> dict:
    """Observation only: endpoint changes do not establish their cause."""
    changes = {}
    for role in ("console", "multimedia", "communications"):
        left = before.get("default_render", {}).get(role, {}).get("endpoint_id")
        right = after.get("default_render", {}).get(role, {}).get("endpoint_id")
        if left is None or right is None:
            changes[role] = {"status": "UNAVAILABLE", "before": left, "after": right}
        elif left != right:
            changes[role] = {"status": "CHANGED_CAUSE_UNDETERMINED", "before": left, "after": right}
    return {"status": "UNCHANGED" if not changes else "REVIEW", "roles": changes,
            "app_default_output_setters": 0, "app_render_streams": 0}
