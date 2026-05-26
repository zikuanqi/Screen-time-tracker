import ctypes

class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [('cbSize', ctypes.c_uint), ('dwTime', ctypes.c_uint)]

lii = LASTINPUTINFO()
lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
result = ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii))
print("GetLastInputInfo result:", result)
print("dwTime:", lii.dwTime)
print("GetTickCount:", ctypes.windll.kernel32.GetTickCount())
if result:
    millis = ctypes.windll.kernel32.GetTickCount() - lii.dwTime
    print("idle seconds:", max(0, millis / 1000.0))