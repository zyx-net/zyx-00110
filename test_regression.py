import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from service.device_service import DeviceService, SUPERVISORS
from model.status import DeviceStatus

PASS = "[PASS]"
FAIL = "[FAIL]"
OK = "[OK]"


def clean_data():
    data_dir = "data"
    if os.path.exists(data_dir):
        for f in os.listdir(data_dir):
            os.remove(os.path.join(data_dir, f))


def test_main_flow():
    print("=" * 60)
    print("Regression Test: Abnormal -> Stop -> Repair -> Restart -> Export -> Restart Verify")
    print("=" * 60)

    clean_data()
    service = DeviceService()

    print("\n[Step 1] Add Device")
    success, msg = service.add_device("TEST001", "Test Device A")
    assert success, f"Failed to add device: {msg}"
    device = service.find_device("TEST001")
    assert device.status == DeviceStatus.NORMAL.value, f"Status should be 'Normal', actual: '{device.status}'"
    print(f"  {PASS} Device added, initial status: {device.status}")

    print("\n[Step 2] Report Abnormal")
    success, msg = service.report_abnormal("TEST001", "Bearing noise")
    assert success, f"Failed to report abnormal: {msg}"
    device = service.find_device("TEST001")
    assert device.status == DeviceStatus.PENDING_STOP_APPROVAL.value, f"Status should be 'Pending Stop Approval', actual: '{device.status}'"
    print(f"  {PASS} Abnormal reported, status changed to: {device.status}")

    print("\n[Step 3] Apply Stop")
    success, msg = service.apply_stop("TEST001", "Need inspection")
    assert success, f"Failed to apply stop: {msg}"
    device = service.find_device("TEST001")
    assert device.status == DeviceStatus.STOPPED.value, f"Status should be 'Stopped', actual: '{device.status}'"
    print(f"  {PASS} Stop applied, status changed to: {device.status}")

    print("\n[Step 4] Start Repair")
    success, msg = service.start_repair("TEST001", "", "")
    assert success, f"Failed to start repair: {msg}"
    device = service.find_device("TEST001")
    assert device.status == DeviceStatus.UNDER_REPAIR.value, f"Status should be 'Under Repair', actual: '{device.status}'"
    print(f"  {PASS} Repair started, status changed to: {device.status}")

    print("\n[Step 5] Record Repair")
    success, msg = service.record_repair("TEST001", "Replace bearing and lubricate", "Zhang San")
    assert success, f"Failed to record repair: {msg}"
    device = service.find_device("TEST001")
    assert device.status == DeviceStatus.PENDING_RESTART_APPROVAL.value, f"Status should be 'Pending Restart Approval', actual: '{device.status}'"
    records = service.get_repair_records_by_device("TEST001")
    assert len(records) == 1, f"Should have 1 repair record, actual: {len(records)}"
    print(f"  {PASS} Repair record saved, status changed to: {device.status}")

    print("\n[Step 6] Supervisor Approves Restart (Using supervisor 'admin')")
    success, msg = service.approve_restart("TEST001", "Repair qualified, approve restart", "admin")
    assert success, f"Supervisor failed to approve restart: {msg}"
    device = service.find_device("TEST001")
    assert device.status == DeviceStatus.RESTARTED.value, f"Status should be 'Restarted', actual: '{device.status}'"
    print(f"  {PASS} Supervisor approved restart, status changed to: {device.status}")

    print("\n[Step 7] Export Records")
    export_dir = service.config.export_dir
    success, msg = service.export_records()
    assert success, f"Failed to export records: {msg}"
    print(f"  {PASS} Records exported")
    print(f"    {msg}")

    json_file = [f for f in os.listdir(export_dir) if f.endswith('.json')][-1]
    csv_file = [f for f in os.listdir(export_dir) if f.endswith('.csv')][-1]
    assert os.path.exists(os.path.join(export_dir, json_file)), "JSON file not generated"
    assert os.path.exists(os.path.join(export_dir, csv_file)), "CSV file not generated"
    print(f"  {PASS} Both JSON and CSV files generated")

    print("\n[Step 8] Verify Persistence After Restart")
    del service
    service2 = DeviceService()

    device2 = service2.find_device("TEST001")
    assert device2 is not None, "Device lost after restart"
    assert device2.status == DeviceStatus.RESTARTED.value, f"Status after restart should be 'Restarted', actual: '{device2.status}'"
    assert device2.abnormal_desc == "Bearing noise", f"Abnormal desc lost after restart: {device2.abnormal_desc}"
    print(f"  {PASS} Device status correct after restart: {device2.status}")

    records2 = service2.get_repair_records_by_device("TEST001")
    assert len(records2) == 1, f"Repair records lost after restart, should have 1, actual: {len(records2)}"
    print(f"  {PASS} Repair records retained after restart")

    approvals2 = service2.get_approval_records_by_device("TEST001")
    assert len(approvals2) >= 2, f"Approval records lost after restart, should have at least 2, actual: {len(approvals2)}"
    print(f"  {PASS} Approval records retained after restart ({len(approvals2)} records)")

    print("\n" + "=" * 60)
    print(f"Main Flow Test: {PASS} All Passed")
    print("=" * 60)


def test_failure_cases():
    print("\n" + "=" * 60)
    print("Failure Case Tests")
    print("=" * 60)

    clean_data()
    service = DeviceService()

    print("\n[Failure Case 1] Already stopped device cannot be stopped again")
    service.add_device("FAIL001", "Failure Test Device")
    service.report_abnormal("FAIL001", "Test abnormal")
    service.apply_stop("FAIL001", "Test stop")

    success, msg = service.apply_stop("FAIL001", "Try to stop again")
    assert not success, "Should fail but succeeded"
    assert "cannot stop again" in msg or "repetition" in msg or "重复" in msg, f"Wrong error message: {msg}"
    print(f"  {PASS} Cannot stop stopped device, error: {msg}")

    print("\n[Failure Case 2] Cannot restart without repair record (supervisor)")
    clean_data()
    service = DeviceService()
    service.add_device("FAIL002", "No Repair Record Device")
    service.report_abnormal("FAIL002", "Test abnormal")
    service.apply_stop("FAIL002", "Test stop")
    service.start_repair("FAIL002", "", "")
    device = service.find_device("FAIL002")
    device.status = DeviceStatus.PENDING_RESTART_APPROVAL.value
    service.save_all()

    success, msg = service.approve_restart("FAIL002", "No repair content", "admin")
    assert not success, "Should fail without repair record"
    assert "no repair record" in msg.lower() or "维修记录" in msg, f"Wrong error message: {msg}"
    print(f"  {PASS} Cannot restart without repair record, error: {msg}")

    print("\n[Failure Case 3] Non-supervisor cannot approve restart")
    clean_data()
    service = DeviceService()
    service.add_device("FAIL003", "Non-Supervisor Test")
    service.report_abnormal("FAIL003", "Test abnormal")
    service.apply_stop("FAIL003", "Test stop")
    service.start_repair("FAIL003", "", "")
    service.record_repair("FAIL003", "Replace parts", "Zhang San")

    success, msg = service.approve_restart("FAIL003", "Non-supervisor tries", "Regular Employee")
    assert not success, "Non-supervisor should not be able to approve"
    assert "not supervisor" in msg.lower() or "无权" in msg or "主管" in msg, f"Wrong error message: {msg}"
    print(f"  {PASS} Non-supervisor 'Regular Employee' cannot approve, error: {msg}")

    success, msg = service.approve_restart("FAIL003", "Repair person tries", "Zhang San")
    assert not success, "Repair person should not be supervisor"
    assert "not supervisor" in msg.lower() or "无权" in msg or "主管" in msg, f"Wrong error message: {msg}"
    print(f"  {PASS} Repair person 'Zhang San' is not supervisor, error: {msg}")

    success, msg = service.approve_restart("FAIL003", "Official supervisor", "admin")
    assert success, f"Supervisor 'admin' should be able to approve: {msg}"
    print(f"  {PASS} Supervisor 'admin' can approve restart")

    print("\n[Failure Case 4] Invalid export directory should not overwrite original config")
    clean_data()
    service = DeviceService()
    old_dir = service.config.export_dir
    valid_dir = os.path.dirname(old_dir) if os.path.dirname(old_dir) else "."
    service.config.export_dir = valid_dir
    service.save_all()

    success, msg, returned_dir = service.update_config("C:\\NonExistent\\ThisPath\\Invalid", 0, 100)
    assert not success, "Invalid directory should fail"
    assert "not exist" in msg.lower() or "不存在" in msg, f"Wrong error message: {msg}"
    assert returned_dir == valid_dir, f"Should keep original config '{valid_dir}', actual: '{returned_dir}'"
    print(f"  {PASS} Invalid directory failed, original config kept: {returned_dir}")

    config = service.get_config()
    assert config.export_dir == valid_dir, f"config.export_dir should be '{valid_dir}', actual: '{config.export_dir}'"
    print(f"  {PASS} Config file on disk not modified")

    print("\n" + "=" * 60)
    print(f"Failure Case Tests: {PASS} All Passed")
    print("=" * 60)


def test_nameerror_fix():
    print("\n" + "=" * 60)
    print("Root Cause Fix Verification: NameError Fix")
    print("=" * 60)

    clean_data()
    service = DeviceService()

    print("\n[Verify 1] update_config using os.path.isdir does not throw NameError")
    try:
        success, msg, _ = service.update_config("C:\\Windows\\System32", 0, 100)
        print(f"  {OK} update_config executed normally, no NameError")
    except NameError as e:
        print(f"  {FAIL} Threw NameError: {e}")
        raise

    print("\n[Verify 2] export_records using json.dump and os.path.join does not throw NameError")
    try:
        success, msg = service.export_records()
        print(f"  {OK} export_records executed normally, no NameError")
    except NameError as e:
        print(f"  {FAIL} Threw NameError: {e}")
        raise

    print("\n" + "=" * 60)
    print(f"NameError Fix Verification: {PASS} All Passed")
    print("=" * 60)


if __name__ == "__main__":
    try:
        test_nameerror_fix()
        test_main_flow()
        test_failure_cases()
        print("\n" + "=" * 60)
        print(f"All Tests Passed!")
        print("=" * 60)
    except AssertionError as e:
        print(f"\n{FAIL} Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n{FAIL} Exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
