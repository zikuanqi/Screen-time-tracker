import sys
sys.path.insert(0, r"C:\Users\zikua\AppData\Roaming\Tencent\Marvis\User\oAN1i2RKLm3y7JkO5T1jpStiZABI\workspace\conv_19e5c6010c2_b3d6f89719be\output\ScreenTimeTracker")
from server import stats_for_date
from datetime import date
try:
    r = stats_for_date(date.today())
    print("OK", r["total_active_seconds"], len(r["processes"]))
except Exception as e:
    import traceback
    traceback.print_exc()