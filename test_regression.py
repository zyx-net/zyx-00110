import os
import sys
import json
import shutil

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from service.device_service import DeviceService, SUPERVISORS
from service.import_service import ImportService
from service.backup_service import BackupService
from model.status import DeviceStatus
from model.device import Device, RepairRecord, ApprovalRecord

PASS = "[PASS]"
FAIL = "[FAIL]"
OK = "[OK]"


def get_latest_export_file(export_dir, extension):
    files = [f for f in os.listdir(export_dir) if f.endswith(extension) and f.startswith('export_')]
    if not files:
        return None
    return max(files, key=lambda x: os.path.getmtime(os.path.join(export_dir, x)))


def clean_data():
    data_dir = "data"
    if os.path.exists(data_dir):
        for f in os.listdir(data_dir):
            path = os.path.join(data_dir, f)
            if os.path.isfile(path):
                os.remove(path)
            elif os.path.isdir(path):
                shutil.rmtree(path)


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

    json_file = get_latest_export_file(export_dir, '.json')
    csv_file = get_latest_export_file(export_dir, '.csv')
    assert json_file is not None, "JSON file not generated"
    assert csv_file is not None, "CSV file not generated"
    assert os.path.exists(os.path.join(export_dir, json_file)), "JSON file not found"
    assert os.path.exists(os.path.join(export_dir, csv_file)), "CSV file not found"
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


def test_json_import():
    print("\n" + "=" * 60)
    print("JSON Import Test")
    print("=" * 60)
    
    clean_data()
    service = DeviceService()
    
    print("\n[Step 1] Create test data and export")
    service.add_device("IMP001", "Import Test Device 1")
    service.add_device("IMP002", "Import Test Device 2")
    service.report_abnormal("IMP001", "Test abnormal")
    service.apply_stop("IMP001", "Need repair")
    service.start_repair("IMP001", "", "")
    service.record_repair("IMP001", "Fixed the issue", "Zhang San")
    
    success, msg = service.export_records()
    assert success, f"Export failed: {msg}"
    
    export_dir = service.config.export_dir
    json_file = get_latest_export_file(export_dir, '.json')
    assert json_file is not None, "No export JSON file found"
    json_path = os.path.join(export_dir, json_file)
    print(f"  {PASS} Exported to {json_path}")
    
    print("\n[Step 2] Clear data and import from JSON")
    clean_data()
    service = DeviceService()
    import_service = ImportService(service.storage, service)
    
    preview_info, error = import_service.preview_import(json_path, "admin", True)
    assert error is None, f"Preview failed: {error}"
    assert len(preview_info['preview'].new_rows) > 0, "Should have new rows"
    print(f"  {PASS} Preview found {len(preview_info['preview'].new_rows)} new rows")
    
    success, msg = import_service.execute_import(preview_info)
    assert success, f"Import failed: {msg}"
    print(f"  {PASS} Import succeeded: {msg[:50]}...")
    
    print("\n[Step 3] Verify imported data")
    device = service.find_device("IMP001")
    assert device is not None, "Device IMP001 not found after import"
    assert device.status == DeviceStatus.PENDING_RESTART_APPROVAL.value, f"Wrong status: {device.status}"
    print(f"  {PASS} Device IMP001 imported with correct status: {device.status}")
    
    records = service.get_repair_records_by_device("IMP001")
    assert len(records) == 1, f"Should have 1 repair record, actual: {len(records)}"
    print(f"  {PASS} Repair records imported correctly")
    
    print("\n" + "=" * 60)
    print(f"JSON Import Test: {PASS} All Passed")
    print("=" * 60)


def test_csv_import():
    print("\n" + "=" * 60)
    print("CSV Import Test")
    print("=" * 60)
    
    clean_data()
    service = DeviceService()
    
    print("\n[Step 1] Create test data and export CSV")
    service.add_device("CSV001", "CSV Test Device 1")
    service.add_device("CSV002", "CSV Test Device 2")
    service.report_abnormal("CSV001", "CSV test abnormal")
    
    success, msg = service.export_records()
    assert success, f"Export failed: {msg}"
    
    export_dir = service.config.export_dir
    csv_file = get_latest_export_file(export_dir, '.csv')
    assert csv_file is not None, "No export CSV file found"
    csv_path = os.path.join(export_dir, csv_file)
    print(f"  {PASS} Exported to {csv_path}")
    
    print("\n[Step 2] Clear data and import from CSV")
    clean_data()
    service = DeviceService()
    import_service = ImportService(service.storage, service)
    
    preview_info, error = import_service.preview_import(csv_path, "admin", True)
    assert error is None, f"Preview failed: {error}"
    print(f"  {PASS} CSV preview found {preview_info['preview'].total_rows} rows")
    
    success, msg = import_service.execute_import(preview_info)
    assert success, f"Import failed: {msg}"
    print(f"  {PASS} CSV import succeeded")
    
    print("\n[Step 3] Verify imported data")
    device = service.find_device("CSV001")
    assert device is not None, "Device CSV001 not found after import"
    assert device.abnormal_desc == "CSV test abnormal", f"Wrong abnormal_desc: {device.abnormal_desc}"
    print(f"  {PASS} Device CSV001 imported correctly")
    
    print("\n" + "=" * 60)
    print(f"CSV Import Test: {PASS} All Passed")
    print("=" * 60)


def test_conflict_skip():
    print("\n" + "=" * 60)
    print("Conflict Skip Test")
    print("=" * 60)
    
    clean_data()
    service = DeviceService()
    
    print("\n[Step 1] Create existing device and export")
    service.add_device("CONFLICT001", "Existing Device")
    service.report_abnormal("CONFLICT001", "Original abnormal")
    
    success, msg = service.export_records()
    assert success, f"Export failed: {msg}"
    
    export_dir = service.config.export_dir
    json_file = get_latest_export_file(export_dir, '.json')
    assert json_file is not None, "No export JSON file found"
    json_path = os.path.join(export_dir, json_file)
    
    print("\n[Step 2] Modify device and try to import")
    device = service.find_device("CONFLICT001")
    device.status = DeviceStatus.STOPPED.value
    service.save_all()
    
    import_service = ImportService(service.storage, service)
    preview_info, error = import_service.preview_import(json_path, "admin", True)
    assert error is None, f"Preview failed: {error}"
    
    overwrite_count = len(preview_info['preview'].overwrite_rows)
    assert overwrite_count > 0, "Should have overwrite rows"
    print(f"  {PASS} Preview found {overwrite_count} overwrite rows")
    
    success, msg = import_service.execute_import(preview_info, skip_conflicts=True)
    assert success, f"Import failed: {msg}"
    print(f"  {PASS} Import with conflict skip succeeded")
    
    print("\n" + "=" * 60)
    print(f"Conflict Skip Test: {PASS} All Passed")
    print("=" * 60)


def test_permission_block():
    print("\n" + "=" * 60)
    print("Permission Block Test")
    print("=" * 60)
    
    clean_data()
    service = DeviceService()
    
    print("\n[Step 1] Create test data and export")
    service.add_device("PERM001", "Permission Test Device")
    success, msg = service.export_records()
    assert success, f"Export failed: {msg}"
    
    export_dir = service.config.export_dir
    json_file = get_latest_export_file(export_dir, '.json')
    assert json_file is not None, "No export JSON file found"
    json_path = os.path.join(export_dir, json_file)
    
    print("\n[Step 2] Test non-supervisor can preview but cannot import")
    clean_data()
    service = DeviceService()
    import_service = ImportService(service.storage, service)
    
    preview_info, error = import_service.preview_import(json_path, "RegularUser", False)
    assert error is None, f"Preview should succeed for non-supervisor: {error}"
    print(f"  {PASS} Non-supervisor can preview")
    
    success, msg = import_service.execute_import(preview_info)
    assert not success, "Non-supervisor should not be able to import"
    assert "permission" in msg.lower() or "权限" in msg, f"Wrong error message: {msg}"
    print(f"  {PASS} Non-supervisor blocked from import: {msg[:50]}...")
    
    print("\n[Step 3] Test supervisor can import")
    preview_info, error = import_service.preview_import(json_path, "admin", True)
    assert error is None, f"Preview failed: {error}"
    
    success, msg = import_service.execute_import(preview_info)
    assert success, f"Supervisor should be able to import: {msg}"
    print(f"  {PASS} Supervisor can import")
    
    print("\n" + "=" * 60)
    print(f"Permission Block Test: {PASS} All Passed")
    print("=" * 60)


def test_rollback_restore():
    print("\n" + "=" * 60)
    print("Rollback Restore Test")
    print("=" * 60)
    
    clean_data()
    service = DeviceService()
    
    print("\n[Step 1] Create initial data")
    service.add_device("ROLL001", "Rollback Test Device 1")
    service.add_device("ROLL002", "Rollback Test Device 2")
    initial_count = len(service.devices)
    print(f"  {PASS} Created {initial_count} devices")
    
    print("\n[Step 2] Export and prepare import with new data")
    success, msg = service.export_records()
    assert success, f"Export failed: {msg}"
    
    export_dir = service.config.export_dir
    json_file = get_latest_export_file(export_dir, '.json')
    assert json_file is not None, "No export JSON file found"
    json_path = os.path.join(export_dir, json_file)
    
    with open(json_path, 'r', encoding='utf-8') as f:
        export_data = json.load(f)
    
    export_data['devices'].append({
        "device_id": "ROLL003",
        "name": "New Device After Import",
        "status": DeviceStatus.NORMAL.value,
        "abnormal_desc": "",
        "create_time": "2026-01-01T00:00:00",
        "update_time": "2026-01-01T00:00:00"
    })
    
    new_json_path = os.path.join(export_dir, "import_test.json")
    with open(new_json_path, 'w', encoding='utf-8') as f:
        json.dump(export_data, f)
    
    print("\n[Step 3] Import new data")
    import_service = ImportService(service.storage, service)
    preview_info, error = import_service.preview_import(new_json_path, "admin", True)
    assert error is None, f"Preview failed: {error}"
    
    success, msg = import_service.execute_import(preview_info)
    assert success, f"Import failed: {msg}"
    
    service.devices = service.storage.load_devices()
    assert len(service.devices) == initial_count + 1, f"Should have {initial_count + 1} devices after import"
    print(f"  {PASS} Import added new device, total: {len(service.devices)}")
    
    print("\n[Step 4] Rollback import")
    assert import_service.can_rollback(), "Should be able to rollback"
    success, msg = import_service.rollback()
    assert success, f"Rollback failed: {msg}"
    print(f"  {PASS} Rollback succeeded: {msg[:50]}...")
    
    print("\n[Step 5] Verify data restored")
    service.devices = service.storage.load_devices()
    assert len(service.devices) == initial_count, f"Should have {initial_count} devices after rollback, actual: {len(service.devices)}"
    
    device3 = service.find_device("ROLL003")
    assert device3 is None, "ROLL003 should not exist after rollback"
    print(f"  {PASS} Data restored to {len(service.devices)} devices")
    
    print("\n" + "=" * 60)
    print(f"Rollback Restore Test: {PASS} All Passed")
    print("=" * 60)


def test_restart_persistence():
    print("\n" + "=" * 60)
    print("Restart Persistence Test")
    print("=" * 60)
    
    clean_data()
    service = DeviceService()
    
    print("\n[Step 1] Create data and export")
    service.add_device("RESTART001", "Restart Test Device")
    success, msg = service.export_records()
    assert success, f"Export failed: {msg}"
    
    export_dir = service.config.export_dir
    json_file = get_latest_export_file(export_dir, '.json')
    assert json_file is not None, "No export JSON file found"
    json_path = os.path.join(export_dir, json_file)
    
    print("\n[Step 2] Import and verify rollback state saved")
    import_service = ImportService(service.storage, service)
    preview_info, error = import_service.preview_import(json_path, "admin", True)
    assert error is None, f"Preview failed: {error}"
    
    success, msg = import_service.execute_import(preview_info)
    assert success, f"Import failed: {msg}"
    
    rollback_info = import_service.get_rollback_info()
    assert rollback_info is not None, "Rollback info should exist"
    print(f"  {PASS} Rollback state saved: {rollback_info['import_log_id']}")
    
    print("\n[Step 3] Simulate restart by creating new service instances")
    del service
    del import_service
    
    service2 = DeviceService()
    import_service2 = ImportService(service2.storage, service2)
    
    rollback_info2 = import_service2.get_rollback_info()
    assert rollback_info2 is not None, "Rollback info should persist after restart"
    assert rollback_info2['import_log_id'] == rollback_info['import_log_id'], "Rollback log ID mismatch"
    print(f"  {PASS} Rollback state persisted after restart: {rollback_info2['import_log_id']}")
    
    print("\n[Step 4] Verify import logs persisted")
    logs = import_service2.get_import_logs()
    assert len(logs) > 0, "Import logs should exist after restart"
    print(f"  {PASS} Import logs persisted: {len(logs)} log(s) found")
    
    print("\n" + "=" * 60)
    print(f"Restart Persistence Test: {PASS} All Passed")
    print("=" * 60)


def test_unauthorized_approval_import():
    print("\n" + "=" * 60)
    print("Unauthorized Approval Import Test")
    print("=" * 60)
    
    clean_data()
    service = DeviceService()
    
    print("\n[Step 1] Create device with approval record")
    service.add_device("UNAUTH001", "Unauthorized Test Device")
    service.report_abnormal("UNAUTH001", "Test")
    service.apply_stop("UNAUTH001", "Test")
    service.start_repair("UNAUTH001", "", "")
    service.record_repair("UNAUTH001", "Fixed", "Zhang San")
    
    export_dir = service.config.export_dir
    success, msg = service.export_records()
    assert success, f"Export failed: {msg}"
    
    json_file = get_latest_export_file(export_dir, '.json')
    assert json_file is not None, "No export JSON file found"
    json_path = os.path.join(export_dir, json_file)
    
    with open(json_path, 'r', encoding='utf-8') as f:
        export_data = json.load(f)
    
    export_data['approval_records'].append({
        "record_id": "APR_TEST_UNAUTH",
        "device_id": "UNAUTH001",
        "approval_type": "复机",
        "opinion": "Approved",
        "approver": "RegularUser",
        "approve_time": "2026-01-01T00:00:00"
    })
    
    test_file = os.path.join(export_dir, "unauthorized_test.json")
    with open(test_file, 'w', encoding='utf-8') as f:
        json.dump(export_data, f)
    
    print("\n[Step 2] Preview should mark unauthorized approval as invalid")
    clean_data()
    service = DeviceService()
    import_service = ImportService(service.storage, service)
    
    preview_info, error = import_service.preview_import(test_file, "admin", True)
    assert error is None, f"Preview failed: {error}"
    
    invalid_count = len(preview_info['preview'].invalid_rows)
    assert invalid_count > 0, "Should have invalid rows"
    
    has_unauthorized_error = any("无复机审批权限" in row.reason for row in preview_info['preview'].invalid_rows)
    assert has_unauthorized_error, "Should detect unauthorized approval"
    print(f"  {PASS} Preview correctly identified unauthorized approval as invalid")
    
    print("\n[Step 3] Execute import should fail due to unauthorized approval")
    success, msg = import_service.execute_import(preview_info, skip_conflicts=False)
    assert not success, "Import should fail with unauthorized approval"
    assert "无复机审批权限" in msg or "权限" in msg, f"Wrong error message: {msg}"
    print(f"  {PASS} Import blocked: {msg[:50]}...")
    
    print("\n[Step 4] Verify no data was imported")
    service.devices = service.storage.load_devices()
    assert len(service.devices) == 0, "No devices should be imported"
    print(f"  {PASS} No data imported due to validation failure")
    
    print("\n" + "=" * 60)
    print(f"Unauthorized Approval Import Test: {PASS} All Passed")
    print("=" * 60)


def test_missing_fields_import():
    print("\n" + "=" * 60)
    print("Missing Fields Import Test")
    print("=" * 60)
    
    clean_data()
    service = DeviceService()
    
    print("\n[Step 1] Create test JSON with missing fields")
    test_data = {
        "devices": [
            {
                "device_id": "DEV001",
                "name": "Valid Device",
                "status": "Normal"
            },
            {
                "name": "Missing Device ID",
                "status": "Normal"
            },
            {
                "device_id": "DEV003",
                "status": "Normal"
            },
            {
                "device_id": "",
                "name": "Empty Device ID",
                "status": "Normal"
            }
        ],
        "repair_records": [
            {
                "record_id": "R001",
                "device_id": "DEV001",
                "repair_desc": "Fixed",
                "operator": "Zhang San"
            },
            {
                "record_id": "R002",
                "device_id": "DEV001",
                "repair_desc": "Fixed"
            }
        ],
        "approval_records": [
            {
                "record_id": "A001",
                "device_id": "DEV001",
                "approval_type": "停机",
                "opinion": "OK",
                "approver": "admin"
            },
            {
                "record_id": "A002",
                "device_id": "DEV001",
                "approval_type": "复机",
                "opinion": "OK"
            }
        ]
    }
    
    export_dir = service.config.export_dir
    test_file = os.path.join(export_dir, "missing_fields_test.json")
    with open(test_file, 'w', encoding='utf-8') as f:
        json.dump(test_data, f)
    
    print("\n[Step 2] Preview should detect missing fields")
    import_service = ImportService(service.storage, service)
    
    preview_info, error = import_service.preview_import(test_file, "admin", True)
    assert error is None, f"Preview failed: {error}"
    
    invalid_count = len(preview_info['preview'].invalid_rows)
    assert invalid_count > 0, "Should have invalid rows"
    
    reasons = [row.reason for row in preview_info['preview'].invalid_rows]
    
    has_missing_device_id = any("设备ID缺失" in r for r in reasons)
    assert has_missing_device_id, "Should detect missing device ID"
    
    has_missing_name = any("设备名称缺失" in r for r in reasons)
    assert has_missing_name, "Should detect missing device name"
    
    has_missing_operator = any("维修人员缺失" in r for r in reasons)
    assert has_missing_operator, "Should detect missing repair operator"
    
    has_missing_approver = any("审批人缺失" in r for r in reasons)
    assert has_missing_approver, "Should detect missing approver"
    
    print(f"  {PASS} Preview found {invalid_count} invalid rows with specific errors")
    for reason in reasons:
        print(f"    - {reason}")
    
    print("\n[Step 3] Execute import should fail with specific errors")
    success, msg = import_service.execute_import(preview_info, skip_conflicts=False)
    assert not success, "Import should fail with missing fields"
    assert "设备ID缺失" in msg or "设备名称缺失" in msg, f"Wrong error message: {msg}"
    print(f"  {PASS} Import blocked with specific errors")
    
    print("\n" + "=" * 60)
    print(f"Missing Fields Import Test: {PASS} All Passed")
    print("=" * 60)


def test_csv_missing_fields_import():
    print("\n" + "=" * 60)
    print("CSV Missing Fields Import Test")
    print("=" * 60)
    
    clean_data()
    service = DeviceService()
    
    print("\n[Step 1] Create test CSV with missing fields")
    csv_content = """=== 设备状态 ===
设备ID,名称,状态,异常描述,创建时间,更新时间
DEV001,Valid Device,Normal,,2026-01-01,2026-01-01
,Missing ID,Normal,,2026-01-01,2026-01-01
DEV003,,Normal,,2026-01-01,2026-01-01

=== 维修记录 ===
记录ID,设备ID,维修内容,维修人员,维修时间
R001,DEV001,Fixed,Zhang San,2026-01-01
R002,DEV001,Fixed,,2026-01-01

=== 审批记录 ===
记录ID,设备ID,审批类型,审批意见,审批人,审批时间
A001,DEV001,停机,OK,admin,2026-01-01
A002,DEV001,复机,OK,,2026-01-01
"""
    
    export_dir = service.config.export_dir
    test_file = os.path.join(export_dir, "csv_missing_fields_test.csv")
    with open(test_file, 'w', encoding='utf-8') as f:
        f.write(csv_content)
    
    print("\n[Step 2] Preview should detect missing fields in CSV")
    import_service = ImportService(service.storage, service)
    
    preview_info, error = import_service.preview_import(test_file, "admin", True)
    assert error is None, f"Preview failed: {error}"
    
    invalid_count = len(preview_info['preview'].invalid_rows)
    assert invalid_count > 0, "Should have invalid rows"
    
    reasons = [row.reason for row in preview_info['preview'].invalid_rows]
    
    has_missing_device_id = any("设备ID缺失" in r for r in reasons)
    assert has_missing_device_id, "Should detect missing device ID in CSV"
    
    has_missing_name = any("设备名称缺失" in r for r in reasons)
    assert has_missing_name, "Should detect missing device name in CSV"
    
    has_missing_operator = any("维修人员缺失" in r for r in reasons)
    assert has_missing_operator, "Should detect missing repair operator in CSV"
    
    has_missing_approver = any("审批人缺失" in r for r in reasons)
    assert has_missing_approver, "Should detect missing approver in CSV"
    
    print(f"  {PASS} Preview found {invalid_count} invalid rows in CSV")
    
    print("\n[Step 3] Execute import should fail")
    success, msg = import_service.execute_import(preview_info, skip_conflicts=False)
    assert not success, "Import should fail"
    print(f"  {PASS} CSV import blocked with specific errors")
    
    print("\n" + "=" * 60)
    print(f"CSV Missing Fields Import Test: {PASS} All Passed")
    print("=" * 60)


def test_validation_during_write():
    print("\n" + "=" * 60)
    print("Validation During Write Test")
    print("=" * 60)
    
    clean_data()
    service = DeviceService()
    
    print("\n[Step 1] Create valid export")
    service.add_device("VAL001", "Validation Test Device")
    export_dir = service.config.export_dir
    success, msg = service.export_records()
    assert success, f"Export failed: {msg}"
    
    json_file = get_latest_export_file(export_dir, '.json')
    assert json_file is not None, "No export JSON file found"
    json_path = os.path.join(export_dir, json_file)
    
    print("\n[Step 2] Preview with valid data")
    import_service = ImportService(service.storage, service)
    
    preview_info, error = import_service.preview_import(json_path, "admin", True)
    assert error is None, f"Preview failed: {error}"
    
    print("\n[Step 3] Add malicious approval record to preview data (simulating tampering)")
    malicious_record = ApprovalRecord(
        record_id="APR_POST_PREVIEW",
        device_id="VAL001",
        approval_type="复机",
        opinion="Invalid",
        approver="Hacker"
    )
    preview_info['data']['approval_records'].append(malicious_record)
    
    print("\n[Step 4] Execute import should still validate during write")
    success, msg = import_service.execute_import(preview_info)
    assert not success, "Import should fail due to validation during write"
    assert "无复机审批权限" in msg or "Hacker" in msg, f"Wrong error message: {msg}"
    print(f"  {PASS} Write-time validation blocked malicious data: {msg[:50]}...")
    
    print("\n[Step 5] Verify data was rolled back")
    service.devices = service.storage.load_devices()
    assert len(service.devices) == 1, "Should have original device after rollback"
    assert service.find_device("VAL001") is not None, "Original device should exist"
    
    approvals = service.get_approval_records_by_device("VAL001")
    malicious_found = any(a.record_id == "APR_POST_PREVIEW" for a in approvals)
    assert not malicious_found, "Malicious record should not be imported"
    print(f"  {PASS} Data rolled back, malicious record blocked")
    
    print("\n" + "=" * 60)
    print(f"Validation During Write Test: {PASS} All Passed")
    print("=" * 60)


if __name__ == "__main__":
    try:
        test_nameerror_fix()
        test_main_flow()
        test_failure_cases()
        test_json_import()
        test_csv_import()
        test_conflict_skip()
        test_permission_block()
        test_rollback_restore()
        test_restart_persistence()
        test_unauthorized_approval_import()
        test_missing_fields_import()
        test_csv_missing_fields_import()
        test_validation_during_write()
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
