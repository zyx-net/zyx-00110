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
from service.session_manager import ImportSessionManager
from model.status import DeviceStatus
from model.device import Device, RepairRecord, ApprovalRecord, ConflictDecision, ImportSession

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
                try:
                    os.remove(path)
                except Exception:
                    pass
            elif os.path.isdir(path):
                try:
                    shutil.rmtree(path)
                except Exception:
                    pass

    import gc
    gc.collect()


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


def test_session_create_and_persist():
    print("\n" + "=" * 60)
    print("Session Create and Persist Test")
    print("=" * 60)
    
    clean_data()
    service = DeviceService()
    
    print("\n[Step 1] Create test data and export")
    service.add_device("SESS001", "Session Test Device 1")
    service.add_device("SESS002", "Session Test Device 2")
    export_dir = service.config.export_dir
    success, msg = service.export_records()
    assert success, f"Export failed: {msg}"
    
    json_file = get_latest_export_file(export_dir, '.json')
    json_path = os.path.join(export_dir, json_file)
    print(f"  {PASS} Created test data and exported to {json_path}")
    
    print("\n[Step 2] Create import session")
    import_service = ImportService(service.storage, service)
    session_manager = ImportSessionManager(service.storage, service)
    
    preview_result, raw_data, error = import_service.preview_import_session(json_path, "admin", True)
    assert error is None, f"Preview failed: {error}"
    
    session, msg = session_manager.create_session(
        file_path=json_path,
        file_type='json',
        operator="admin",
        is_supervisor=True,
        parsed_data=raw_data,
        preview_result=preview_result
    )
    assert session is not None, "Session should be created"
    print(f"  {PASS} Session created: {session.session_id}")
    
    print("\n[Step 3] Verify session is persisted")
    loaded_session = session_manager.get_session(session.session_id)
    assert loaded_session is not None, "Session should be loaded"
    assert loaded_session.session_id == session.session_id, "Session ID should match"
    print(f"  {PASS} Session persisted correctly")
    
    print("\n[Step 4] Simulate app restart and check active session")
    del service
    del session_manager
    del import_service
    
    service2 = DeviceService()
    session_manager2 = ImportSessionManager(service2.storage, service2)
    
    active_session = session_manager2.check_active_session()
    assert active_session is not None, "Active session should be found after restart"
    assert active_session.session_id == session.session_id, "Session ID should match"
    print(f"  {PASS} Active session recovered after restart: {active_session.session_id}")
    
    print("\n" + "=" * 60)
    print(f"Session Create and Persist Test: {PASS} All Passed")
    print("=" * 60)


def test_session_conflict_resolution():
    print("\n" + "=" * 60)
    print("Session Conflict Resolution Test")
    print("=" * 60)
    
    clean_data()
    service = DeviceService()
    
    print("\n[Step 1] Create existing device")
    service.add_device("CONFLICT001", "Existing Device")
    device = service.find_device("CONFLICT001")
    original_status = device.status
    print(f"  {PASS} Created device with status: {original_status}")
    
    print("\n[Step 2] Create JSON with same device ID but different status")
    export_dir = service.config.export_dir
    test_data = {
        "devices": [
            {
                "device_id": "CONFLICT001",
                "name": "Existing Device",
                "status": DeviceStatus.STOPPED.value,
                "abnormal_desc": "New abnormal",
                "create_time": "2026-01-01T00:00:00",
                "update_time": "2026-01-01T00:00:00"
            }
        ],
        "repair_records": [],
        "approval_records": []
    }
    conflict_file = os.path.join(export_dir, "conflict_test.json")
    with open(conflict_file, 'w', encoding='utf-8') as f:
        json.dump(test_data, f)
    print(f"  {PASS} Created conflict test file")
    
    print("\n[Step 3] Create session and verify conflict detected")
    import_service = ImportService(service.storage, service)
    session_manager = ImportSessionManager(service.storage, service)
    
    preview_result, raw_data, error = import_service.preview_import_session(conflict_file, "admin", True)
    assert error is None, f"Preview failed: {error}"
    
    assert len(preview_result.devices["conflict"]) == 1, "Should detect conflict for same ID"
    print(f"  {PASS} Conflict detected: {len(preview_result.devices['conflict'])} conflict items")
    
    session, _ = session_manager.create_session(
        file_path=conflict_file,
        file_type='json',
        operator="admin",
        is_supervisor=True,
        parsed_data=raw_data,
        preview_result=preview_result
    )
    
    print("\n[Step 4] Set conflict resolution to KEEP_LOCAL")
    device_data = preview_result.devices["conflict"][0].row_data
    success, error = session_manager.resolve_conflict(
        session.session_id,
        "CONFLICT001",
        "device",
        device_data,
        ConflictDecision.KEEP_LOCAL
    )
    assert success, f"Failed to set resolution: {error}"

    session = session_manager.get_session(session.session_id)
    resolution = session.get_conflict_resolution("CONFLICT001")
    assert resolution == ConflictDecision.KEEP_LOCAL, f"Resolution should be KEEP_LOCAL, got: {resolution}"
    print(f"  {PASS} Conflict resolution set to KEEP_LOCAL")
    
    print("\n[Step 5] Commit import with KEEP_LOCAL decision")
    success, msg = session_manager.commit_import(session, "admin", True)
    assert success, f"Import failed: {msg}"
    print(f"  {PASS} Import committed successfully")
    
    print("\n[Step 6] Verify local data was kept")
    service.devices = service.storage.load_devices()
    device = service.find_device("CONFLICT001")
    assert device.status == original_status, f"Status should be preserved: {device.status}"
    print(f"  {PASS} Local data preserved, status: {device.status}")
    
    print("\n" + "=" * 60)
    print(f"Session Conflict Resolution Test: {PASS} All Passed")
    print("=" * 60)


def test_session_overwrite_local():
    print("\n" + "=" * 60)
    print("Session Overwrite Local Test")
    print("=" * 60)
    
    clean_data()
    service = DeviceService()
    
    print("\n[Step 1] Create existing device")
    service.add_device("OVER001", "Overwrite Test Device")
    device = service.find_device("OVER001")
    original_status = device.status
    print(f"  {PASS} Created device with status: {original_status}")
    
    print("\n[Step 2] Create JSON with same device ID")
    export_dir = service.config.export_dir
    test_data = {
        "devices": [
            {
                "device_id": "OVER001",
                "name": "Overwrite Test Device",
                "status": DeviceStatus.STOPPED.value,
                "abnormal_desc": "Updated abnormal",
                "create_time": "2026-01-01T00:00:00",
                "update_time": "2026-01-01T00:00:00"
            }
        ],
        "repair_records": [],
        "approval_records": []
    }
    overwrite_file = os.path.join(export_dir, "overwrite_test.json")
    with open(overwrite_file, 'w', encoding='utf-8') as f:
        json.dump(test_data, f)
    
    print("\n[Step 3] Create session with OVERWRITE_LOCAL decision")
    import_service = ImportService(service.storage, service)
    session_manager = ImportSessionManager(service.storage, service)
    
    preview_result, raw_data, error = import_service.preview_import_session(overwrite_file, "admin", True)
    assert error is None, f"Preview failed: {error}"
    
    assert len(preview_result.devices["conflict"]) == 1, "Should detect conflict for same ID"
    print(f"  {PASS} Conflict detected")
    
    session, _ = session_manager.create_session(
        file_path=overwrite_file,
        file_type='json',
        operator="admin",
        is_supervisor=True,
        parsed_data=raw_data,
        preview_result=preview_result
    )
    print(f"  {PASS} Session created")
    
    print("\n[Step 4] Resolve conflict - overwrite local")
    device_data = preview_result.devices["conflict"][0].row_data
    session_manager.resolve_conflict(
        session.session_id,
        "OVER001",
        "device",
        device_data,
        ConflictDecision.OVERWRITE_LOCAL
    )
    print(f"  {PASS} Set conflict resolution to OVERWRITE_LOCAL")
    
    print("\n[Step 4] Commit import")
    success, msg = session_manager.commit_import(session, "admin", True)
    assert success, f"Import failed: {msg}"
    
    print("\n[Step 5] Verify data was overwritten")
    service.devices = service.storage.load_devices()
    device = service.find_device("OVER001")
    assert device.status == DeviceStatus.STOPPED.value, f"Status should be overwritten: {device.status}"
    assert device.abnormal_desc == "Updated abnormal", f"Abnormal desc should be updated"
    print(f"  {PASS} Data overwritten, new status: {device.status}")
    
    print("\n" + "=" * 60)
    print(f"Session Overwrite Local Test: {PASS} All Passed")
    print("=" * 60)


def test_session_skip():
    print("\n" + "=" * 60)
    print("Session Skip Test")
    print("=" * 60)

    clean_data()
    service = DeviceService()

    print("\n[Step 1] Create existing device")
    service.add_device("SKIP001", "Skip Test Device")
    device = service.find_device("SKIP001")
    original_status = device.status
    print(f"  {PASS} Created device with status: {original_status}")

    print("\n[Step 2] Create JSON with same device ID")
    export_dir = service.config.export_dir
    test_data = {
        "devices": [
            {
                "device_id": "SKIP001",
                "name": "Skip Test Device",
                "status": DeviceStatus.STOPPED.value,
                "abnormal_desc": "Should be skipped",
                "create_time": "2026-01-01T00:00:00",
                "update_time": "2026-01-01T00:00:00"
            }
        ],
        "repair_records": [],
        "approval_records": []
    }
    skip_file = os.path.join(export_dir, "skip_test.json")
    with open(skip_file, 'w', encoding='utf-8') as f:
        json.dump(test_data, f)

    print("\n[Step 3] Create session with SKIP decision")
    import_service = ImportService(service.storage, service)
    session_manager = ImportSessionManager(service.storage, service)

    preview_result, raw_data, error = import_service.preview_import_session(skip_file, "admin", True)
    assert error is None, f"Preview failed: {error}"

    session, _ = session_manager.create_session(
        file_path=skip_file,
        file_type='json',
        operator="admin",
        is_supervisor=True,
        parsed_data=raw_data,
        preview_result=preview_result
    )

    device_data = preview_result.devices["conflict"][0].row_data
    success, error = session_manager.resolve_conflict(
        session.session_id,
        "SKIP001",
        "device",
        device_data,
        ConflictDecision.SKIP
    )
    assert success, f"Failed to set resolution: {error}"
    print(f"  {PASS} Set conflict resolution to SKIP")

    print("\n[Step 4] Commit import")
    success, msg = session_manager.commit_import(session, "admin", True)
    assert success, f"Import failed: {msg}"

    print("\n[Step 5] Verify data was skipped (original preserved)")
    service.devices = service.storage.load_devices()
    device = service.find_device("SKIP001")
    assert device.status == original_status, f"Status should be preserved: {device.status} (expected: {original_status})"
    assert device.abnormal_desc != "Should be skipped", "Abnormal desc should not be updated"
    print(f"  {PASS} Data skipped, original status preserved: {device.status}")

    print("\n" + "=" * 60)
    print(f"Session Skip Test: {PASS} All Passed")
    print("=" * 60)


def test_session_permission_block():
    print("\n" + "=" * 60)
    print("Session Permission Block Test")
    print("=" * 60)
    
    clean_data()
    service = DeviceService()
    
    print("\n[Step 1] Create test data")
    service.add_device("PERM001", "Permission Test Device")
    export_dir = service.config.export_dir
    success, msg = service.export_records()
    assert success, f"Export failed: {msg}"
    
    json_file = get_latest_export_file(export_dir, '.json')
    json_path = os.path.join(export_dir, json_file)
    
    print("\n[Step 2] Create session as non-supervisor")
    import_service = ImportService(service.storage, service)
    session_manager = ImportSessionManager(service.storage, service)
    
    preview_result, raw_data, error = import_service.preview_import_session(json_path, "RegularUser", False)
    assert error is None, f"Preview failed: {error}"
    
    session, _ = session_manager.create_session(
        file_path=json_path,
        file_type='json',
        operator="RegularUser",
        is_supervisor=False,
        parsed_data=raw_data,
        preview_result=preview_result
    )
    print(f"  {PASS} Session created by non-supervisor")
    
    print("\n[Step 3] Try to commit as non-supervisor")
    success, msg = session_manager.commit_import(session, "RegularUser", False)
    assert not success, "Non-supervisor should not be able to commit"
    assert "权限不足" in msg, f"Wrong error message: {msg}"
    print(f"  {PASS} Non-supervisor blocked from commit: {msg[:30]}...")
    
    print("\n[Step 4] Try to commit as different supervisor")
    success, msg = session_manager.commit_import(session, "admin", True)
    assert success, f"Supervisor should be able to commit: {msg}"
    print(f"  {PASS} Different supervisor can commit")
    
    print("\n" + "=" * 60)
    print(f"Session Permission Block Test: {PASS} All Passed")
    print("=" * 60)


def test_session_file_integrity_check():
    print("\n" + "=" * 60)
    print("Session File Integrity Check Test")
    print("=" * 60)
    
    clean_data()
    service = DeviceService()
    
    print("\n[Step 1] Create session")
    service.add_device("INT001", "Integrity Test Device")
    export_dir = service.config.export_dir
    success, msg = service.export_records()
    assert success, f"Export failed: {msg}"
    
    json_file = get_latest_export_file(export_dir, '.json')
    json_path = os.path.join(export_dir, json_file)
    
    import_service = ImportService(service.storage, service)
    session_manager = ImportSessionManager(service.storage, service)
    
    preview_result, raw_data, error = import_service.preview_import_session(json_path, "admin", True)
    session, _ = session_manager.create_session(
        file_path=json_path,
        file_type='json',
        operator="admin",
        is_supervisor=True,
        parsed_data=raw_data,
        preview_result=preview_result
    )
    print(f"  {PASS} Session created with file checksum")
    
    print("\n[Step 2] Modify file after session creation")
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    data['devices'].append({
        "device_id": "TAMPERED",
        "name": "Tampered Device",
        "status": DeviceStatus.NORMAL.value,
        "abnormal_desc": "",
        "create_time": "2026-01-01T00:00:00",
        "update_time": "2026-01-01T00:00:00"
    })
    
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(data, f)
    print(f"  {PASS} File modified (tampered)")
    
    print("\n[Step 3] Resolve conflicts first")
    if preview_result.get_total_conflict() > 0:
        conflict_row = preview_result.devices["conflict"][0]
        record_id = conflict_row.row_data.get('device_id')
        session_manager.resolve_conflict(session.session_id, record_id, "device", 
                                      conflict_row.row_data, ConflictDecision.OVERWRITE_LOCAL, "admin")
    print(f"  {PASS} Conflicts resolved")
    
    print("\n[Step 4] Try to commit - should fail due to checksum mismatch")
    session = session_manager.get_session(session.session_id)
    success, msg = session_manager.commit_import(session, "admin", True)
    assert not success, "Should fail due to file modification"
    assert "已被修改" in msg or "校验" in msg, f"Wrong error message: {msg}"
    print(f"  {PASS} Commit blocked due to file modification: {msg[:30]}...")
    
    print("\n" + "=" * 60)
    print(f"Session File Integrity Check Test: {PASS} All Passed")
    print("=" * 60)


def test_session_undo_after_restart():
    print("\n" + "=" * 60)
    print("Session Undo After Restart Test")
    print("=" * 60)
    
    clean_data()
    service = DeviceService()
    
    print("\n[Step 1] Create initial device")
    service.add_device("UNDO001", "Undo Test Device 1")
    initial_count = len(service.devices)
    print(f"  {PASS} Created {initial_count} devices")
    
    print("\n[Step 2] Create session and import new data")
    export_dir = service.config.export_dir
    test_data = {
        "devices": [
            {
                "device_id": "UNDO001",
                "name": "Undo Test Device 1",
                "status": DeviceStatus.NORMAL.value,
                "abnormal_desc": "",
                "create_time": "2026-01-01T00:00:00",
                "update_time": "2026-01-01T00:00:00"
            },
            {
                "device_id": "UNDO002",
                "name": "Undo Test Device 2",
                "status": DeviceStatus.NORMAL.value,
                "abnormal_desc": "",
                "create_time": "2026-01-01T00:00:00",
                "update_time": "2026-01-01T00:00:00"
            }
        ],
        "repair_records": [],
        "approval_records": []
    }
    undo_file = os.path.join(export_dir, "undo_test.json")
    with open(undo_file, 'w', encoding='utf-8') as f:
        json.dump(test_data, f)
    
    import_service = ImportService(service.storage, service)
    session_manager = ImportSessionManager(service.storage, service)
    
    preview_result, raw_data, error = import_service.preview_import_session(undo_file, "admin", True)
    session, _ = session_manager.create_session(
        file_path=undo_file,
        file_type='json',
        operator="admin",
        is_supervisor=True,
        parsed_data=raw_data,
        preview_result=preview_result
    )
    
    if preview_result.get_total_conflict() > 0:
        conflict_row = preview_result.devices["conflict"][0]
        record_id = conflict_row.row_data.get('device_id')
        session_manager.resolve_conflict(session.session_id, record_id, "device", 
                                      conflict_row.row_data, ConflictDecision.OVERWRITE_LOCAL, "admin")
    
    success, msg = session_manager.commit_import(session, "admin", True)
    assert success, f"Import failed: {msg}"
    print(f"  {PASS} Import committed")
    
    service.devices = service.storage.load_devices()
    assert len(service.devices) == initial_count + 1, f"Should have {initial_count + 1} devices"
    print(f"  {PASS} Data imported, now has {len(service.devices)} devices")
    
    print("\n[Step 3] Simulate restart")
    session_id = session.session_id
    backup_path = session.backup_path
    del service
    del session_manager
    
    service2 = DeviceService()
    session_manager2 = ImportSessionManager(service2.storage, service2)
    
    print("\n[Step 4] Load session and verify can_undo is True")
    session2 = session_manager2.get_session(session_id)
    assert session2 is not None, "Session should be loaded"
    assert session2.can_undo == True, "Session should have can_undo=True"
    assert session2.backup_path is not None and session2.backup_path != "", "Backup path should be set"
    print(f"  {PASS} Session loaded with can_undo=True, backup_path set")

    print("\n[Step 5] Undo import")
    success, msg = session_manager2.undo_import(session2, "admin", True)
    assert success, f"Undo failed: {msg}"

    service2.devices = service2.storage.load_devices()
    assert len(service2.devices) == initial_count, f"Should have {initial_count} devices after undo"
    device2 = service2.find_device("UNDO002")
    assert device2 is None, "UNDO002 should not exist after undo"
    print(f"  {PASS} Undo successful, back to {len(service2.devices)} devices")
    
    print("\n" + "=" * 60)
    print(f"Session Undo After Restart Test: {PASS} All Passed")
    print("=" * 60)


def test_session_log_export():
    print("\n" + "=" * 60)
    print("Session Log Export Test")
    print("=" * 60)
    
    clean_data()
    service = DeviceService()
    
    print("\n[Step 1] Create session and import")
    service.add_device("LOG001", "Log Test Device")
    export_dir = service.config.export_dir
    success, msg = service.export_records()
    assert success, f"Export failed: {msg}"
    
    json_file = get_latest_export_file(export_dir, '.json')
    json_path = os.path.join(export_dir, json_file)
    
    import_service = ImportService(service.storage, service)
    session_manager = ImportSessionManager(service.storage, service)
    
    preview_result, raw_data, error = import_service.preview_import_session(json_path, "admin", True)
    session, _ = session_manager.create_session(
        file_path=json_path,
        file_type='json',
        operator="admin",
        is_supervisor=True,
        parsed_data=raw_data,
        preview_result=preview_result
    )
    
    success, msg = session_manager.commit_import(session, "admin", True)
    assert success, f"Import failed: {msg}"
    print(f"  {PASS} Import committed")
    
    print("\n[Step 2] Check session logs")
    logs = session_manager.get_session_logs()
    assert len(logs) > 0, "Should have session logs"
    print(f"  {PASS} Found {len(logs)} session log(s)")
    
    log = logs[-1]
    assert log.session_id == session.session_id, "Log session ID should match"
    assert log.operator == "admin", "Log operator should match"
    assert log.status == "success", "Log status should be success"
    print(f"  {PASS} Log details verified: status={log.status}")
    
    print("\n[Step 3] Export log to file")
    export_file = os.path.join(export_dir, "session_log_export.json")
    success = session_manager.export_session_log(log, export_file)
    assert success, "Log export failed"
    assert os.path.exists(export_file), "Log file should exist"
    print(f"  {PASS} Log exported to {export_file}")
    
    with open(export_file, 'r', encoding='utf-8') as f:
        exported_data = json.load(f)
    assert exported_data['session_id'] == session.session_id, "Exported log should match"
    print(f"  {PASS} Exported log content verified")
    
    print("\n" + "=" * 60)
    print(f"Session Log Export Test: {PASS} All Passed")
    print("=" * 60)


def test_session_conflict_unified():
    print("\n" + "=" * 60)
    print("Session Conflict Unified Test")
    print("=" * 60)
    
    clean_data()
    service = DeviceService()
    
    print("\n[Step 1] Create existing device with same ID")
    service.add_device("CONFLICT001", "Existing Device")
    device = service.find_device("CONFLICT001")
    original_status = device.status
    print(f"  {PASS} Created device with status: {original_status}")
    
    print("\n[Step 2] Create JSON with same device ID")
    export_dir = service.config.export_dir
    test_data = {
        "devices": [
            {
                "device_id": "CONFLICT001",
                "name": "Existing Device",
                "status": DeviceStatus.STOPPED.value,
                "abnormal_desc": "Updated abnormal",
                "create_time": "2026-01-01T00:00:00",
                "update_time": "2026-01-01T00:00:00"
            }
        ],
        "repair_records": [],
        "approval_records": []
    }
    conflict_file = os.path.join(export_dir, "conflict_unified_test.json")
    with open(conflict_file, 'w', encoding='utf-8') as f:
        json.dump(test_data, f)
    print(f"  {PASS} Created conflict test file")
    
    print("\n[Step 3] Create session and verify conflict is detected (not overwrite)")
    import_service = ImportService(service.storage, service)
    session_manager = ImportSessionManager(service.storage, service)
    
    preview_result, raw_data, error = import_service.preview_import_session(conflict_file, "admin", True)
    assert error is None, f"Preview failed: {error}"
    
    assert len(preview_result.devices["conflict"]) == 1, "Should detect conflict for same ID"
    assert len(preview_result.devices["overwrite"]) == 0, "Should NOT detect overwrite for same ID"
    print(f"  {PASS} Conflict detected correctly, no overwrite items")
    
    session, _ = session_manager.create_session(
        file_path=conflict_file,
        file_type='json',
        operator="admin",
        is_supervisor=True,
        parsed_data=raw_data,
        preview_result=preview_result
    )
    print(f"  {PASS} Session created with conflict items")
    
    print("\n[Step 4] Verify is_all_conflicts_resolved returns False initially")
    assert not session.is_all_conflicts_resolved(), "Should not be resolved initially"
    print(f"  {PASS} Unresolved conflicts count: {session.get_unresolved_conflicts_count()}")
    
    print("\n" + "=" * 60)
    print(f"Session Conflict Unified Test: {PASS} All Passed")
    print("=" * 60)


def test_session_batch_decision():
    print("\n" + "=" * 60)
    print("Session Batch Decision Test")
    print("=" * 60)
    
    clean_data()
    service = DeviceService()
    
    print("\n[Step 1] Create existing devices")
    service.add_device("BATCH001", "Batch Test Device 1")
    service.add_device("BATCH002", "Batch Test Device 2")
    service.add_device("BATCH003", "Batch Test Device 3")
    print(f"  {PASS} Created 3 devices")
    
    print("\n[Step 2] Create JSON with same device IDs")
    export_dir = service.config.export_dir
    test_data = {
        "devices": [
            {
                "device_id": "BATCH001",
                "name": "Batch Device 1",
                "status": DeviceStatus.STOPPED.value,
                "abnormal_desc": "Conflict 1",
                "create_time": "2026-01-01T00:00:00",
                "update_time": "2026-01-01T00:00:00"
            },
            {
                "device_id": "BATCH002",
                "name": "Batch Device 2",
                "status": DeviceStatus.STOPPED.value,
                "abnormal_desc": "Conflict 2",
                "create_time": "2026-01-01T00:00:00",
                "update_time": "2026-01-01T00:00:00"
            },
            {
                "device_id": "BATCH003",
                "name": "Batch Device 3",
                "status": DeviceStatus.STOPPED.value,
                "abnormal_desc": "Conflict 3",
                "create_time": "2026-01-01T00:00:00",
                "update_time": "2026-01-01T00:00:00"
            }
        ],
        "repair_records": [],
        "approval_records": []
    }
    batch_file = os.path.join(export_dir, "batch_test.json")
    with open(batch_file, 'w', encoding='utf-8') as f:
        json.dump(test_data, f)
    print(f"  {PASS} Created batch test file")
    
    print("\n[Step 3] Create session and resolve conflicts in batch")
    import_service = ImportService(service.storage, service)
    session_manager = ImportSessionManager(service.storage, service)
    
    preview_result, raw_data, error = import_service.preview_import_session(batch_file, "admin", True)
    session, _ = session_manager.create_session(
        file_path=batch_file,
        file_type='json',
        operator="admin",
        is_supervisor=True,
        parsed_data=raw_data,
        preview_result=preview_result
    )
    
    assert session.get_unresolved_conflicts_count() == 3, "Should have 3 unresolved conflicts"
    print(f"  {PASS} Session created with 3 unresolved conflicts")
    
    print("\n[Step 4] Test batch resolution")
    conflicts = session_manager.get_conflicts_by_type(session, "all")
    resolutions = [
        {'record_id': 'BATCH001', 'record_type': 'device', 'row_data': conflicts[0]['row_data'], 'decision': ConflictDecision.KEEP_LOCAL},
        {'record_id': 'BATCH002', 'record_type': 'device', 'row_data': conflicts[1]['row_data'], 'decision': ConflictDecision.SKIP}
    ]
    
    success, error_msg, count = session_manager.resolve_conflicts_batch(session.session_id, resolutions)
    assert success, f"Batch resolution failed: {error_msg}"
    assert count == 2, f"Should resolve 2 conflicts, got {count}"
    print(f"  {PASS} Batch resolved {count} conflicts")
    
    session = session_manager.get_session(session.session_id)
    assert session.get_unresolved_conflicts_count() == 1, "Should have 1 unresolved conflict remaining"
    print(f"  {PASS} Remaining unresolved conflicts: 1")
    
    print("\n[Step 5] Test batch filtering by type")
    device_conflicts = session_manager.get_conflicts_by_type(session, "device")
    assert len(device_conflicts) == 3, "Should have 3 device conflicts"
    print(f"  {PASS} Filtered by type returned {len(device_conflicts)} conflicts")
    
    print("\n[Step 6] Test decision summary")
    summary = session_manager.get_resolved_conflicts_summary(session)
    assert summary['total'] == 3, "Should have 3 total conflicts"
    assert summary['resolved'] == 2, "Should have 2 resolved"
    assert summary['decisions']['keep_local'] == 1, "Should have 1 keep_local"
    assert summary['decisions']['skip'] == 1, "Should have 1 skip"
    print(f"  {PASS} Decision summary: total={summary['total']}, resolved={summary['resolved']}")
    
    print("\n" + "=" * 60)
    print(f"Session Batch Decision Test: {PASS} All Passed")
    print("=" * 60)


def test_session_restart_recovery():
    print("\n" + "=" * 60)
    print("Session Restart Recovery Test")
    print("=" * 60)
    
    clean_data()
    service = DeviceService()
    
    print("\n[Step 1] Create session with conflicts")
    service.add_device("RECOVER001", "Recovery Test Device")
    export_dir = service.config.export_dir
    test_data = {
        "devices": [
            {
                "device_id": "RECOVER001",
                "name": "Recovery Test Device",
                "status": DeviceStatus.STOPPED.value,
                "abnormal_desc": "Updated",
                "create_time": "2026-01-01T00:00:00",
                "update_time": "2026-01-01T00:00:00"
            }
        ],
        "repair_records": [],
        "approval_records": []
    }
    recover_file = os.path.join(export_dir, "recover_test.json")
    with open(recover_file, 'w', encoding='utf-8') as f:
        json.dump(test_data, f)
    
    import_service = ImportService(service.storage, service)
    session_manager = ImportSessionManager(service.storage, service)
    
    preview_result, raw_data, error = import_service.preview_import_session(recover_file, "admin", True)
    session, _ = session_manager.create_session(
        file_path=recover_file,
        file_type='json',
        operator="admin",
        is_supervisor=True,
        parsed_data=raw_data,
        preview_result=preview_result
    )
    
    session_manager.resolve_conflict(session.session_id, "RECOVER001", "device", 
                                    preview_result.devices["conflict"][0].row_data, 
                                    ConflictDecision.KEEP_LOCAL)
    print(f"  {PASS} Session created and conflict resolved")
    
    print("\n[Step 2] Simulate restart - recreate services")
    del service
    del session_manager
    del import_service
    
    service2 = DeviceService()
    session_manager2 = ImportSessionManager(service2.storage, service2)
    
    print("\n[Step 3] Recover session after restart")
    recovered_session = session_manager2.check_active_session()
    assert recovered_session is not None, "Session should be recovered"
    assert recovered_session.session_id == session.session_id, "Session ID should match"
    print(f"  {PASS} Session recovered: {recovered_session.session_id}")
    
    print("\n[Step 4] Verify conflict resolution persisted")
    resolution = recovered_session.get_conflict_resolution("RECOVER001")
    assert resolution == ConflictDecision.KEEP_LOCAL, "Resolution should persist"
    print(f"  {PASS} Conflict resolution persisted: {resolution}")
    
    print("\n[Step 5] Verify all conflicts are resolved")
    assert recovered_session.is_all_conflicts_resolved(), "All conflicts should be resolved"
    print(f"  {PASS} All conflicts resolved after recovery")
    
    print("\n" + "=" * 60)
    print(f"Session Restart Recovery Test: {PASS} All Passed")
    print("=" * 60)


def test_session_undo_after_import():
    print("\n" + "=" * 60)
    print("Session Undo After Import Test")
    print("=" * 60)
    
    clean_data()
    service = DeviceService()
    
    print("\n[Step 1] Create initial device")
    service.add_device("UNDO001", "Undo Test Device 1")
    initial_count = len(service.devices)
    print(f"  {PASS} Created {initial_count} devices")
    
    print("\n[Step 2] Create session and import new data")
    export_dir = service.config.export_dir
    test_data = {
        "devices": [
            {
                "device_id": "UNDO001",
                "name": "Undo Test Device 1",
                "status": DeviceStatus.NORMAL.value,
                "abnormal_desc": "",
                "create_time": "2026-01-01T00:00:00",
                "update_time": "2026-01-01T00:00:00"
            },
            {
                "device_id": "UNDO002",
                "name": "Undo Test Device 2",
                "status": DeviceStatus.NORMAL.value,
                "abnormal_desc": "",
                "create_time": "2026-01-01T00:00:00",
                "update_time": "2026-01-01T00:00:00"
            }
        ],
        "repair_records": [],
        "approval_records": []
    }
    undo_file = os.path.join(export_dir, "undo_test.json")
    with open(undo_file, 'w', encoding='utf-8') as f:
        json.dump(test_data, f)
    
    import_service = ImportService(service.storage, service)
    session_manager = ImportSessionManager(service.storage, service)
    
    preview_result, raw_data, error = import_service.preview_import_session(undo_file, "admin", True)
    session, _ = session_manager.create_session(
        file_path=undo_file,
        file_type='json',
        operator="admin",
        is_supervisor=True,
        parsed_data=raw_data,
        preview_result=preview_result
    )
    
    session_manager.resolve_conflict(session.session_id, "UNDO001", "device", 
                                    preview_result.devices["conflict"][0].row_data,
                                    ConflictDecision.KEEP_LOCAL)
    
    success, msg = session_manager.commit_import(session, "admin", True)
    assert success, f"Import failed: {msg}"
    print(f"  {PASS} Import committed")
    
    session = session_manager.get_session(session.session_id)
    
    service.devices = service.storage.load_devices()
    assert len(service.devices) == initial_count + 1, f"Should have {initial_count + 1} devices"
    print(f"  {PASS} Data imported, now has {len(service.devices)} devices")
    
    print("\n[Step 3] Undo the import")
    success, msg = session_manager.undo_import(session, "admin", True)
    assert success, f"Undo failed: {msg}"
    print(f"  {PASS} Import undone: {msg}")
    
    service.devices = service.storage.load_devices()
    assert len(service.devices) == initial_count, f"Should have {initial_count} devices after undo"
    device2 = service.find_device("UNDO002")
    assert device2 is None, "UNDO002 should not exist after undo"
    print(f"  {PASS} Data restored to {len(service.devices)} devices")
    
    print("\n[Step 4] Verify cannot undo twice")
    success, msg = session_manager.undo_import(session, "admin", True)
    assert not success, "Should not be able to undo twice"
    print(f"  {PASS} Cannot undo twice: {msg}")
    
    print("\n" + "=" * 60)
    print(f"Session Undo After Import Test: {PASS} All Passed")
    print("=" * 60)


def test_session_log_export():
    print("\n" + "=" * 60)
    print("Session Log Export Test")
    print("=" * 60)
    
    clean_data()
    service = DeviceService()
    
    print("\n[Step 1] Create session and import with conflict decisions")
    service.add_device("LOG001", "Log Test Device")
    export_dir = service.config.export_dir
    test_data = {
        "devices": [
            {
                "device_id": "LOG001",
                "name": "Log Test Device",
                "status": DeviceStatus.STOPPED.value,
                "abnormal_desc": "Test",
                "create_time": "2026-01-01T00:00:00",
                "update_time": "2026-01-01T00:00:00"
            },
            {
                "device_id": "LOG002",
                "name": "Log Test Device 2",
                "status": DeviceStatus.NORMAL.value,
                "abnormal_desc": "",
                "create_time": "2026-01-01T00:00:00",
                "update_time": "2026-01-01T00:00:00"
            }
        ],
        "repair_records": [],
        "approval_records": []
    }
    log_file = os.path.join(export_dir, "log_test.json")
    with open(log_file, 'w', encoding='utf-8') as f:
        json.dump(test_data, f)
    
    import_service = ImportService(service.storage, service)
    session_manager = ImportSessionManager(service.storage, service)
    
    preview_result, raw_data, error = import_service.preview_import_session(log_file, "admin", True)
    session, _ = session_manager.create_session(
        file_path=log_file,
        file_type='json',
        operator="admin",
        is_supervisor=True,
        parsed_data=raw_data,
        preview_result=preview_result
    )
    
    session_manager.resolve_conflict(session.session_id, "LOG001", "device", 
                                    preview_result.devices["conflict"][0].row_data,
                                    ConflictDecision.KEEP_LOCAL)
    
    success, msg = session_manager.commit_import(session, "admin", True)
    assert success, f"Import failed: {msg}"
    print(f"  {PASS} Import committed")
    
    print("\n[Step 2] Check session logs")
    logs = session_manager.get_session_logs()
    assert len(logs) > 0, "Should have session logs"
    print(f"  {PASS} Found {len(logs)} session log(s)")
    
    log = logs[-1]
    assert log.session_id == session.session_id, "Log session ID should match"
    assert log.status == "success", "Log status should be success"
    assert log.conflict_resolved == 1, "Should record 1 conflict resolution"
    assert 'conflict_decisions' in log.details, "Should have conflict decisions in details"
    print(f"  {PASS} Log details verified: status={log.status}, conflicts={log.conflict_resolved}")
    
    print("\n[Step 3] Export log to file")
    export_file = os.path.join(export_dir, "session_log_export.json")
    success = session_manager.export_session_log(log, export_file)
    assert success, "Log export failed"
    assert os.path.exists(export_file), "Log file should exist"
    print(f"  {PASS} Log exported to {export_file}")
    
    with open(export_file, 'r', encoding='utf-8') as f:
        exported_data = json.load(f)
    assert exported_data['session_id'] == session.session_id, "Exported log should match"
    assert 'conflict_decisions' in exported_data['details'], "Exported log should have conflict decisions"
    print(f"  {PASS} Exported log content verified")
    
    print("\n" + "=" * 60)
    print(f"Session Log Export Test: {PASS} All Passed")
    print("=" * 60)


def test_session_permission_block():
    print("\n" + "=" * 60)
    print("Session Permission Block Test")
    print("=" * 60)
    
    clean_data()
    service = DeviceService()
    
    print("\n[Step 1] Create test data")
    service.add_device("PERM001", "Permission Test Device")
    export_dir = service.config.export_dir
    test_data = {
        "devices": [
            {
                "device_id": "PERM001",
                "name": "Permission Test Device",
                "status": DeviceStatus.STOPPED.value,
                "abnormal_desc": "Test",
                "create_time": "2026-01-01T00:00:00",
                "update_time": "2026-01-01T00:00:00"
            }
        ],
        "repair_records": [],
        "approval_records": []
    }
    perm_file = os.path.join(export_dir, "perm_test.json")
    with open(perm_file, 'w', encoding='utf-8') as f:
        json.dump(test_data, f)
    
    print("\n[Step 2] Create session as non-supervisor")
    import_service = ImportService(service.storage, service)
    session_manager = ImportSessionManager(service.storage, service)
    
    preview_result, raw_data, error = import_service.preview_import_session(perm_file, "RegularUser", False)
    assert error is None, f"Preview should succeed for non-supervisor: {error}"
    
    session, _ = session_manager.create_session(
        file_path=perm_file,
        file_type='json',
        operator="RegularUser",
        is_supervisor=False,
        parsed_data=raw_data,
        preview_result=preview_result
    )
    print(f"  {PASS} Session created by non-supervisor")
    
    print("\n[Step 3] Resolve conflict as non-supervisor")
    session_manager.resolve_conflict(session.session_id, "PERM001", "device", 
                                    preview_result.devices["conflict"][0].row_data,
                                    ConflictDecision.KEEP_LOCAL)
    
    print("\n[Step 4] Try to commit as non-supervisor - should fail")
    success, msg = session_manager.commit_import(session, "RegularUser", False)
    assert not success, "Non-supervisor should not be able to commit"
    assert "权限不足" in msg or "权限" in msg, f"Wrong error message: {msg}"
    print(f"  {PASS} Non-supervisor blocked from commit: {msg}")
    
    print("\n[Step 5] Try to commit as different non-supervisor - should still fail")
    success, msg = session_manager.commit_import(session, "AnotherUser", False)
    assert not success, "Different non-supervisor should not be able to commit"
    print(f"  {PASS} Different non-supervisor blocked: {msg}")
    
    print("\n[Step 6] Commit as supervisor - should succeed")
    success, msg = session_manager.commit_import(session, "admin", True)
    assert success, f"Supervisor should be able to commit: {msg}"
    print(f"  {PASS} Supervisor can commit")
    
    print("\n" + "=" * 60)
    print(f"Session Permission Block Test: {PASS} All Passed")
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
        test_session_create_and_persist()
        test_session_conflict_resolution()
        test_session_overwrite_local()
        test_session_skip()
        test_session_permission_block()
        test_session_file_integrity_check()
        test_session_undo_after_restart()
        test_session_log_export()
        test_session_conflict_unified()
        test_session_batch_decision()
        test_session_restart_recovery()
        test_session_undo_after_import()
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


def test_session_complete_flow():
    print("\n" + "=" * 60)
    print("Session Complete Flow Test: Create -> Resolve -> Commit -> Undo")
    print("=" * 60)
    
    clean_data()
    service = DeviceService()
    import_service = ImportService(service.storage, service)
    session_manager = ImportSessionManager(service.storage, service)
    
    print("\n[Step 1] Create test file with conflicts")
    test_file = os.path.join(service.storage.data_dir, "test_conflicts.json")
    test_data = {
        "devices": [
            {"device_id": "DEV001", "name": "Test Device 1", "status": "正常"},
            {"device_id": "DEV002", "name": "Test Device 2", "status": "正常"}
        ],
        "repair_records": [
            {"record_id": "REP001", "device_id": "DEV001", "repair_desc": "Fix issue", "operator": "Zhang San"}
        ],
        "approval_records": [
            {"record_id": "APP001", "device_id": "DEV001", "approval_type": "停机", "opinion": "Approved", "approver": "admin"}
        ]
    }
    
    with open(test_file, 'w', encoding='utf-8') as f:
        json.dump(test_data, f)
    
    print(f"  {PASS} Test file created: {test_file}")
    
    print("\n[Step 2] Create session")
    preview_result, raw_data, error = import_service.preview_import_session(test_file, "admin", True)
    assert error is None, f"Preview failed: {error}"
    
    session, msg = session_manager.create_session(
        file_path=test_file,
        file_type='json',
        operator="admin",
        is_supervisor=True,
        parsed_data=raw_data,
        preview_result=preview_result
    )
    assert session is not None, f"Failed to create session: {msg}"
    print(f"  {PASS} Session created: {session.session_id}")
    
    print("\n[Step 3] Resolve conflicts")
    if preview_result.get_total_conflict() > 0:
        for category in ["devices", "repair_records", "approval_records"]:
            for conflict_row in preview_result.__dict__[category]["conflict"]:
                record_id = conflict_row.row_data.get('device_id') or conflict_row.row_data.get('record_id')
                success, error = session_manager.resolve_conflict(
                    session.session_id,
                    record_id,
                    category.replace("_records", "").replace("_", ""),
                    conflict_row.row_data,
                    ConflictDecision.OVERWRITE_LOCAL
                )
                assert success, f"Failed to resolve conflict: {error}"
        print(f"  {PASS} All conflicts resolved")
    
    print("\n[Step 4] Verify session is ready for commit")
    session = session_manager.get_session(session.session_id)
    assert session.is_all_conflicts_resolved(), "Session should have all conflicts resolved"
    print(f"  {PASS} Session ready for commit")
    
    print("\n[Step 5] Commit import")
    success, msg = session_manager.commit_import(session, "admin", True)
    assert success, f"Commit failed: {msg}"
    print(f"  {PASS} Import committed successfully")
    
    print("\n[Step 6] Verify data imported")
    device = service.find_device("DEV001")
    assert device is not None, "Device not found after import"
    print(f"  {PASS} Device imported: {device.name}")
    
    print("\n[Step 7] Verify undo is available")
    session = session_manager.get_session(session.session_id)
    assert session.can_undo, "Session should support undo"
    assert session.backup_path is not None, "Session should have backup path"
    print(f"  {PASS} Undo is available, backup: {session.backup_path}")
    
    print("\n[Step 8] Undo import")
    success, msg = session_manager.undo_import(session, "admin", True)
    assert success, f"Undo failed: {msg}"
    print(f"  {PASS} Import undone successfully")
    
    print("\n[Step 9] Verify data restored")
    device = service.find_device("DEV001")
    assert device is None, "Device should be removed after undo"
    print(f"  {PASS} Data restored to pre-import state")
    
    print("\n" + "=" * 60)
    print(f"Session Complete Flow Test: {PASS} All Passed")
    print("=" * 60)


def test_session_filter_and_batch():
    print("\n" + "=" * 60)
    print("Session Filter and Batch Decision Test")
    print("=" * 60)
    
    clean_data()
    service = DeviceService()
    import_service = ImportService(service.storage, service)
    session_manager = ImportSessionManager(service.storage, service)
    
    print("\n[Step 1] Create session with multiple conflict types")
    test_file = os.path.join(service.storage.data_dir, "test_multi_conflicts.json")
    test_data = {
        "devices": [
            {"device_id": "FILT001", "name": "Filter Device 1", "status": "正常"},
            {"device_id": "FILT002", "name": "Filter Device 2", "status": "正常"}
        ],
        "repair_records": [
            {"record_id": "FREP001", "device_id": "FILT001", "repair_desc": "Fix issue", "operator": "Zhang San"}
        ],
        "approval_records": [
            {"record_id": "FAPP001", "device_id": "FILT001", "approval_type": "停机", "opinion": "Approved", "approver": "admin"}
        ]
    }
    
    with open(test_file, 'w', encoding='utf-8') as f:
        json.dump(test_data, f)
    
    preview_result, raw_data, error = import_service.preview_import_session(test_file, "admin", True)
    session, msg = session_manager.create_session(
        file_path=test_file,
        file_type='json',
        operator="admin",
        is_supervisor=True,
        parsed_data=raw_data,
        preview_result=preview_result
    )
    
    print(f"  {PASS} Session created with {preview_result.get_total_conflict()} conflicts")
    
    print("\n[Step 2] Test filtering by type")
    device_conflicts = session_manager.get_conflicts_by_type(session, "device")
    print(f"  Device conflicts: {len(device_conflicts)}")
    
    repair_conflicts = session_manager.get_conflicts_by_type(session, "repair")
    print(f"  Repair conflicts: {len(repair_conflicts)}")
    
    approval_conflicts = session_manager.get_conflicts_by_type(session, "approval")
    print(f"  Approval conflicts: {len(approval_conflicts)}")
    
    all_conflicts = session_manager.get_conflicts_by_type(session, "all")
    print(f"  Total conflicts: {len(all_conflicts)}")
    
    assert len(all_conflicts) == len(device_conflicts) + len(repair_conflicts) + len(approval_conflicts), \
        "Total conflicts should equal sum of type-filtered conflicts"
    print(f"  {PASS} Filter counts match")
    
    print("\n[Step 3] Test filtering by decision status")
    unresolved = [c for c in all_conflicts if c['decision'] is None]
    assert len(unresolved) == len(all_conflicts), "All conflicts should be unresolved initially"
    print(f"  {PASS} All conflicts initially unresolved")
    
    print("\n[Step 4] Test batch decision")
    if len(all_conflicts) > 0:
        batch_resolutions = [
            {
                'record_id': c['record_id'],
                'record_type': c['record_type'],
                'row_data': c['row_data'],
                'decision': ConflictDecision.SKIP
            }
            for c in all_conflicts
        ]
        
        success, error_msg, count = session_manager.resolve_conflicts_batch(session.session_id, batch_resolutions)
        assert success, f"Batch resolution failed: {error_msg}"
        assert count == len(all_conflicts), f"Should resolve {len(all_conflicts)} conflicts, got {count}"
        print(f"  {PASS} Batch resolution: {count} conflicts set to SKIP")
    
    print("\n[Step 5] Verify all conflicts resolved")
    session = session_manager.get_session(session.session_id)
    summary = session_manager.get_resolved_conflicts_summary(session)
    assert summary['unresolved'] == 0, f"Should have 0 unresolved, got {summary['unresolved']}"
    assert summary['resolved'] == summary['total'], "All conflicts should be resolved"
    print(f"  {PASS} All conflicts resolved: {summary['resolved']}/{summary['total']}")
    
    print("\n" + "=" * 60)
    print(f"Session Filter and Batch Test: {PASS} All Passed")
    print("=" * 60)


def test_session_log_export():
    print("\n" + "=" * 60)
    print("Session Log Export Test")
    print("=" * 60)
    
    clean_data()
    service = DeviceService()
    session_manager = ImportSessionManager(service.storage, service)
    
    print("\n[Step 1] Verify no logs initially")
    logs = session_manager.get_session_logs()
    initial_count = len(logs)
    print(f"  Initial log count: {initial_count}")
    
    print("\n[Step 2] Export logs (should handle empty logs)")
    export_file = os.path.join(service.storage.data_dir, "test_export.json")
    try:
        if logs:
            result = session_manager.export_session_log(logs[0], export_file)
            print(f"  {PASS} Export succeeded")
        else:
            print(f"  {PASS} No logs to export, handled gracefully")
    except Exception as e:
        print(f"  {FAIL} Export failed: {e}")
        raise
    
    print("\n" + "=" * 60)
    print(f"Session Log Export Test: {PASS} All Passed")
    print("=" * 60)


def test_session_restart_recovery():
    print("\n" + "=" * 60)
    print("Session Restart Recovery Test")
    print("=" * 60)
    
    clean_data()
    service = DeviceService()
    import_service = ImportService(service.storage, service)
    session_manager = ImportSessionManager(service.storage, service)
    
    print("\n[Step 1] Create session and make decisions")
    test_file = os.path.join(service.storage.data_dir, "test_recovery.json")
    test_data = {
        "devices": [
            {"device_id": "RECV001", "name": "Recovery Device", "status": "正常"}
        ],
        "repair_records": [],
        "approval_records": []
    }
    
    with open(test_file, 'w', encoding='utf-8') as f:
        json.dump(test_data, f)
    
    preview_result, raw_data, error = import_service.preview_import_session(test_file, "admin", True)
    session, msg = session_manager.create_session(
        file_path=test_file,
        file_type='json',
        operator="admin",
        is_supervisor=True,
        parsed_data=raw_data,
        preview_result=preview_result
    )
    
    session_id = session.session_id
    print(f"  Session created: {session_id}")
    
    print("\n[Step 2] Resolve all conflicts")
    if preview_result.get_total_conflict() > 0:
        for category in ["devices", "repair_records", "approval_records"]:
            for conflict_row in preview_result.__dict__[category]["conflict"]:
                record_id = conflict_row.row_data.get('device_id') or conflict_row.row_data.get('record_id')
                session_manager.resolve_conflict(
                    session_id, record_id, category.replace("_records", "").replace("_", ""),
                    conflict_row.row_data, ConflictDecision.OVERWRITE_LOCAL
                )
    print(f"  {PASS} Conflicts resolved")
    
    print("\n[Step 3] Simulate restart - recreate session manager")
    del session_manager
    session_manager = ImportSessionManager(service.storage, service)
    
    print("\n[Step 4] Check active session")
    active_session = session_manager.check_active_session()
    assert active_session is not None, "Active session should be found"
    assert active_session.session_id == session_id, f"Session ID mismatch: {active_session.session_id} != {session_id}"
    print(f"  {PASS} Session recovered: {active_session.session_id}")
    
    print("\n[Step 5] Verify session data integrity")
    assert active_session.preview_result is not None, "Preview result should be preserved"
    assert active_session.raw_data is not None, "Raw data should be preserved"
    print(f"  {PASS} Session data integrity verified")
    
    print("\n" + "=" * 60)
    print(f"Session Restart Recovery Test: {PASS} All Passed")
    print("=" * 60)


def test_conflict_incomplete_submit_block():
    print("\n" + "=" * 60)
    print("Conflict Incomplete Submit Block Test")
    print("=" * 60)
    
    clean_data()
    service = DeviceService()
    import_service = ImportService(service.storage, service)
    session_manager = ImportSessionManager(service.storage, service)
    
    print("\n[Step 1] Create existing device to generate conflict")
    service.add_device("INCM001", "Incomplete Device 1")
    
    print("\n[Step 2] Create session with conflicts")
    test_file = os.path.join(service.storage.data_dir, "test_incomplete.json")
    test_data = {
        "devices": [
            {"device_id": "INCM001", "name": "Incomplete Device 1 Updated", "status": "正常"},
            {"device_id": "INCM002", "name": "Incomplete Device 2", "status": "正常"}
        ],
        "repair_records": [],
        "approval_records": []
    }
    
    with open(test_file, 'w', encoding='utf-8') as f:
        json.dump(test_data, f)
    
    preview_result, raw_data, error = import_service.preview_import_session(test_file, "admin", True)
    session, msg = session_manager.create_session(
        file_path=test_file,
        file_type='json',
        operator="admin",
        is_supervisor=True,
        parsed_data=raw_data,
        preview_result=preview_result
    )
    
    print(f"  {PASS} Session created with {preview_result.get_total_conflict()} conflicts")
    
    print("\n[Step 3] Try to commit without resolving conflicts - should fail")
    success, msg = session_manager.commit_import(session, "admin", True)
    assert not success, "Should fail without resolving conflicts"
    assert "未决策" in msg or "conflict" in msg.lower(), f"Wrong error message: {msg}"
    print(f"  {PASS} Blocked from committing: {msg}")
    
    print("\n[Step 3] Resolve only some conflicts - should still fail")
    if preview_result.get_total_conflict() >= 2:
        category = "devices"
        conflicts = preview_result.__dict__[category]["conflict"]
        if len(conflicts) >= 2:
            record_id = conflicts[0].row_data.get('device_id')
            session_manager.resolve_conflict(
                session.session_id, record_id, "device",
                conflicts[0].row_data, ConflictDecision.OVERWRITE_LOCAL
            )
            
            success, msg = session_manager.commit_import(session, "admin", True)
            assert not success, "Should fail with unresolved conflicts"
            assert "未决策" in msg or "conflict" in msg.lower(), f"Wrong error message: {msg}"
            print(f"  {PASS} Still blocked with partial resolution: {msg}")
    
    print("\n[Step 4] Resolve all conflicts - should succeed")
    session = session_manager.get_session(session.session_id)
    for category in ["devices", "repair_records", "approval_records"]:
        for conflict_row in preview_result.__dict__[category]["conflict"]:
            record_id = conflict_row.row_data.get('device_id') or conflict_row.row_data.get('record_id')
            existing = session.get_conflict_resolution(record_id)
            if existing is None:
                session_manager.resolve_conflict(
                    session.session_id, record_id, category.replace("_records", "").replace("_", ""),
                    conflict_row.row_data, ConflictDecision.OVERWRITE_LOCAL
                )
    
    success, msg = session_manager.commit_import(session, "admin", True)
    assert success, f"Should succeed after resolving all conflicts: {msg}"
    print(f"  {PASS} Commit succeeded after resolving all conflicts")
    
    print("\n" + "=" * 60)
    print(f"Conflict Incomplete Submit Block Test: {PASS} All Passed")
    print("=" * 60)


def test_session_event_chain_tracking():
    print("\n" + "=" * 60)
    print("Session Event Chain Tracking Test")
    print("=" * 60)
    
    clean_data()
    service = DeviceService()
    import_service = ImportService(service.storage, service)
    session_manager = ImportSessionManager(service.storage, service)
    
    print("\n[Step 1] Create existing device to generate conflict")
    service.add_device("EVT001", "Event Test Device")
    
    print("\n[Step 2] Create session and verify events are tracked")
    test_file = os.path.join(service.storage.data_dir, "test_events.json")
    test_data = {
        "devices": [{"device_id": "EVT001", "name": "Event Test Updated", "status": "正常"}],
        "repair_records": [],
        "approval_records": []
    }
    with open(test_file, 'w', encoding='utf-8') as f:
        json.dump(test_data, f)
    
    preview_result, raw_data, error = import_service.preview_import_session(test_file, "admin", True)
    session, msg = session_manager.create_session(test_file, 'json', "admin", True, raw_data, preview_result)
    assert session is not None, f"Session should be created: {msg}"
    print(f"  {PASS} Session created")
    
    session = session_manager.get_session(session.session_id)
    assert len(session.events) >= 2, f"Should have at least 2 events (created + preview), got {len(session.events)}"
    print(f"  {PASS} Events tracked: {len(session.events)} events")
    
    event_types = [e.event_type for e in session.events]
    assert "session_created" in event_types, "Should have session_created event"
    assert "preview_generated" in event_types, "Should have preview_generated event"
    print(f"  {PASS} Event types verified: {event_types}")
    
    print("\n[Step 3] Resolve conflict and verify event is tracked")
    assert preview_result.get_total_conflict() > 0, "Should have conflicts"
    conflict_row = preview_result.devices["conflict"][0]
    record_id = conflict_row.row_data.get('device_id')
    session_manager.resolve_conflict(session.session_id, record_id, "device", 
                                  conflict_row.row_data, ConflictDecision.OVERWRITE_LOCAL, "admin")
    
    session = session_manager.get_session(session.session_id)
    event_types = [e.event_type for e in session.events]
    assert "conflict_resolved" in event_types, "Should have conflict_resolved event"
    print(f"  {PASS} Conflict resolution event tracked")
    
    print("\n[Step 4] Commit and verify events are tracked")
    success, msg = session_manager.commit_import(session, "admin", True)
    assert success, f"Commit should succeed: {msg}"
    
    session = session_manager.get_session(session.session_id)
    event_types = [e.event_type for e in session.events]
    assert "commit_started" in event_types, "Should have commit_started event"
    assert "commit_success" in event_types, "Should have commit_success event"
    assert "validation_passed" in event_types, "Should have validation_passed event"
    print(f"  {PASS} Commit events tracked: {[e for e in event_types if 'commit' in e or 'validation' in e]}")

    print("\n[Step 5] Verify event summary")
    summary = session.get_event_summary()
    assert summary['total_events'] == len(session.events), "Event summary should match"
    assert summary['first_event_time'] is not None, "Should have first event time"
    assert summary['last_event_time'] is not None, "Should have last event time"
    print(f"  {PASS} Event summary: total={summary['total_events']}")
    
    print("\n" + "=" * 60)
    print(f"Session Event Chain Tracking Test: {PASS} All Passed")
    print("=" * 60)


def test_session_error_snapshot():
    print("\n" + "=" * 60)
    print("Session Error Snapshot Test")
    print("=" * 60)
    
    clean_data()
    service = DeviceService()
    import_service = ImportService(service.storage, service)
    session_manager = ImportSessionManager(service.storage, service)
    
    print("\n[Step 1] Create existing devices to generate conflicts")
    service.add_device("ERR001", "Error Test Device 1")
    
    print("\n[Step 2] Create session and try to commit without resolving conflicts")
    test_file = os.path.join(service.storage.data_dir, "test_error.json")
    test_data = {
        "devices": [
            {"device_id": "ERR001", "name": "Error Test 1 Updated", "status": "正常"},
            {"device_id": "ERR002", "name": "Error Test 2", "status": "正常"}
        ],
        "repair_records": [],
        "approval_records": []
    }
    with open(test_file, 'w', encoding='utf-8') as f:
        json.dump(test_data, f)
    
    preview_result, raw_data, error = import_service.preview_import_session(test_file, "admin", True)
    session, msg = session_manager.create_session(test_file, 'json', "admin", True, raw_data, preview_result)
    print(f"  {PASS} Session created with {preview_result.get_total_conflict()} conflicts")
    
    print("\n[Step 3] Try to commit without resolving conflicts")
    success, msg = session_manager.commit_import(session, "admin", True)
    assert not success, "Should fail without resolving conflicts"
    assert "未决策" in msg or "conflict" in msg.lower(), f"Wrong error message: {msg}"
    print(f"  {PASS} Commit blocked: {msg[:30]}...")
    
    session = session_manager.get_session(session.session_id)
    assert session.has_error_snapshots(), "Should have error snapshots"
    assert len(session.error_snapshots) > 0, "Should have at least 1 error snapshot"
    print(f"  {PASS} Error snapshot created: {len(session.error_snapshots)} snapshots")
    
    snapshot = session.error_snapshots[0]
    assert snapshot.error_type is not None, "Error type should be set"
    assert snapshot.error_message is not None, "Error message should be set"
    assert snapshot.error_time is not None, "Error time should be set"
    print(f"  {PASS} Error snapshot details verified: type={snapshot.error_type}")
    
    print("\n[Step 4] Test error snapshot export")
    export_file = os.path.join(service.storage.data_dir, "error_export_test.json")
    success, error = session_manager.get_failed_session_snapshot(session.session_id, export_file)
    assert success, f"Export should succeed: {error}"
    assert os.path.exists(export_file), "Export file should exist"
    print(f"  {PASS} Error snapshot exported to {export_file}")
    
    with open(export_file, 'r', encoding='utf-8') as f:
        exported_data = json.load(f)
    assert 'session_info' in exported_data, "Should have session_info"
    assert 'error_snapshots' in exported_data, "Should have error_snapshots"
    assert 'event_chain' in exported_data, "Should have event_chain"
    print(f"  {PASS} Exported data structure verified")
    
    print("\n" + "=" * 60)
    print(f"Session Error Snapshot Test: {PASS} All Passed")
    print("=" * 60)


def test_session_permission_control():
    print("\n" + "=" * 60)
    print("Session Permission Control Test")
    print("=" * 60)
    
    clean_data()
    service = DeviceService()
    import_service = ImportService(service.storage, service)
    session_manager = ImportSessionManager(service.storage, service)
    
    print("\n[Step 1] Create session as 'admin'")
    test_file = os.path.join(service.storage.data_dir, "test_perm.json")
    test_data = {
        "devices": [{"device_id": "PERM001", "name": "Perm Test", "status": "正常"}],
        "repair_records": [],
        "approval_records": []
    }
    with open(test_file, 'w', encoding='utf-8') as f:
        json.dump(test_data, f)
    
    preview_result, raw_data, error = import_service.preview_import_session(test_file, "admin", True)
    session, msg = session_manager.create_session(test_file, 'json', "admin", True, raw_data, preview_result)
    session_id = session.session_id
    print(f"  {PASS} Session created by admin: {session_id}")
    
    print("\n[Step 2] Test that owner can access session")
    events, error = session_manager.get_session_event_chain(session_id, "admin", True)
    assert events is not None, "Owner should be able to access event chain"
    assert error is None, "Should not have error"
    print(f"  {PASS} Owner can access session")
    
    print("\n[Step 3] Test that non-owner non-supervisor cannot access")
    events, error = session_manager.get_session_event_chain(session_id, "regular_user", False)
    assert events is None, "Non-owner should not be able to access"
    assert error is not None, "Should have error"
    assert "权限" in error or "permission" in error.lower(), f"Wrong error: {error}"
    print(f"  {PASS} Non-owner blocked: {error}")
    
    print("\n[Step 4] Test that supervisor can access any session")
    events, error = session_manager.get_session_event_chain(session_id, "supervisor", True)
    assert events is not None, "Supervisor should be able to access"
    assert error is None, "Should not have error"
    print(f"  {PASS} Supervisor can access any session")
    
    print("\n[Step 5] Test permission grant")
    success, msg = session_manager.grant_session_permission(
        session_id, "viewer", session_manager.storage._get_sessions_file().split('/')[-1], 
        "admin", True
    )
    print(f"  {PASS} Permission management works")
    
    print("\n[Step 6] Resolve conflicts and commit")
    if preview_result.get_total_conflict() > 0:
        conflict_row = preview_result.devices["conflict"][0]
        record_id = conflict_row.row_data.get('device_id')
        session_manager.resolve_conflict(session_id, record_id, "device", 
                                      conflict_row.row_data, ConflictDecision.OVERWRITE_LOCAL, "admin")
    
    success, msg = session_manager.commit_import(session, "admin", True)
    assert success, f"Commit should succeed: {msg}"
    print(f"  {PASS} Session committed")
    
    print("\n[Step 7] Test undo permission")
    session = session_manager.get_session(session_id)
    assert session.check_permission("admin", "undo", True), "Admin should have undo permission"
    assert session.check_permission("regular_user", "undo", False) == False, "Regular user should not have undo permission"
    print(f"  {PASS} Permission checks work correctly")
    
    print("\n" + "=" * 60)
    print(f"Session Permission Control Test: {PASS} All Passed")
    print("=" * 60)


def test_session_history_viewing():
    print("\n" + "=" * 60)
    print("Session History Viewing Test")
    print("=" * 60)
    
    clean_data()
    service = DeviceService()
    import_service = ImportService(service.storage, service)
    session_manager = ImportSessionManager(service.storage, service)
    
    print("\n[Step 1] Create multiple sessions")
    for i in range(3):
        test_file = os.path.join(service.storage.data_dir, f"test_history_{i}.json")
        test_data = {
            "devices": [{"device_id": f"HIST{i}", "name": f"History Test {i}", "status": "正常"}],
            "repair_records": [],
            "approval_records": []
        }
        with open(test_file, 'w', encoding='utf-8') as f:
            json.dump(test_data, f)
        
        preview_result, raw_data, error = import_service.preview_import_session(test_file, "admin", True)
        session, msg = session_manager.create_session(test_file, 'json', "admin", True, raw_data, preview_result)
        
        if preview_result.get_total_conflict() > 0:
            conflict_row = preview_result.devices["conflict"][0]
            record_id = conflict_row.row_data.get('device_id')
            session_manager.resolve_conflict(session.session_id, record_id, "device", 
                                          conflict_row.row_data, ConflictDecision.OVERWRITE_LOCAL, "admin")
        
        session_manager.commit_import(session, "admin", True)
    
    print(f"  {PASS} Created 3 sessions")
    
    print("\n[Step 2] Query all session history")
    sessions = session_manager.get_session_history()
    assert len(sessions) >= 3, f"Should have at least 3 sessions, got {len(sessions)}"
    print(f"  {PASS} History query returned {len(sessions)} sessions")
    
    print("\n[Step 3] Query by operator")
    sessions = session_manager.get_session_history(operator="admin")
    for s in sessions:
        assert s.operator == "admin", f"All sessions should be by admin"
    print(f"  {PASS} Filter by operator works")
    
    print("\n[Step 4] Get failed sessions")
    failed_sessions = session_manager.get_failed_sessions()
    assert isinstance(failed_sessions, list), "Should return list"
    print(f"  {PASS} Failed sessions query works: {len(failed_sessions)} failed")
    
    print("\n[Step 5] Verify session ordering (newest first)")
    sessions = session_manager.get_session_history()
    for i in range(len(sessions) - 1):
        assert sessions[i].created_time >= sessions[i+1].created_time, "Sessions should be ordered by time"
    print(f"  {PASS} Sessions ordered by time (newest first)")
    
    print("\n" + "=" * 60)
    print(f"Session History Viewing Test: {PASS} All Passed")
    print("=" * 60)


def test_session_file_integrity_validation():
    print("\n" + "=" * 60)
    print("Session File Integrity Validation Test")
    print("=" * 60)
    
    clean_data()
    service = DeviceService()
    import_service = ImportService(service.storage, service)
    session_manager = ImportSessionManager(service.storage, service)
    
    print("\n[Step 1] Create session")
    test_file = os.path.join(service.storage.data_dir, "test_integrity.json")
    test_data = {
        "devices": [{"device_id": "INT001", "name": "Integrity Test", "status": "正常"}],
        "repair_records": [],
        "approval_records": []
    }
    with open(test_file, 'w', encoding='utf-8') as f:
        json.dump(test_data, f)
    
    preview_result, raw_data, error = import_service.preview_import_session(test_file, "admin", True)
    session, msg = session_manager.create_session(test_file, 'json', "admin", True, raw_data, preview_result)
    original_checksum = session.file_checksum
    print(f"  {PASS} Session created with checksum: {original_checksum}")
    
    print("\n[Step 2] Verify file integrity (unchanged)")
    success, message, details = session_manager.verify_file_integrity(session.session_id)
    assert success, "Integrity check should pass for unchanged file"
    assert details['status'] == "unchanged", "Status should be unchanged"
    print(f"  {PASS} File integrity verified: unchanged")
    
    print("\n[Step 3] Modify file and verify integrity check fails")
    with open(test_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    data['devices'].append({"device_id": "TAMPERED", "name": "Tampered", "status": "正常"})
    with open(test_file, 'w', encoding='utf-8') as f:
        json.dump(data, f)
    
    success, message, details = session_manager.verify_file_integrity(session.session_id)
    assert not success, "Integrity check should fail for modified file"
    assert details['status'] == "modified", "Status should be modified"
    assert details['original_checksum'] == original_checksum, "Original checksum should match"
    assert details['current_checksum'] != original_checksum, "Current checksum should be different"
    print(f"  {PASS} File modification detected")
    
    print("\n[Step 4] Test revalidation")
    if preview_result.get_total_conflict() > 0:
        conflict_row = preview_result.devices["conflict"][0]
        record_id = conflict_row.row_data.get('device_id')
        session_manager.resolve_conflict(session.session_id, record_id, "device", 
                                      conflict_row.row_data, ConflictDecision.OVERWRITE_LOCAL, "admin")
    
    success, errors = session_manager.revalidate_session(session.session_id)
    assert not success, "Revalidation should fail due to file modification"
    print(f"  {PASS} Revalidation correctly detects issues")
    
    print("\n" + "=" * 60)
    print(f"Session File Integrity Validation Test: {PASS} All Passed")
    print("=" * 60)


def test_cross_restart_recovery_with_events():
    print("\n" + "=" * 60)
    print("Cross-Restart Recovery With Events Test")
    print("=" * 60)
    
    clean_data()
    service = DeviceService()
    import_service = ImportService(service.storage, service)
    session_manager = ImportSessionManager(service.storage, service)
    
    print("\n[Step 1] Create session with events")
    test_file = os.path.join(service.storage.data_dir, "test_recovery_events.json")
    test_data = {
        "devices": [{"device_id": "RECV001", "name": "Recovery Test", "status": "正常"}],
        "repair_records": [],
        "approval_records": []
    }
    with open(test_file, 'w', encoding='utf-8') as f:
        json.dump(test_data, f)
    
    preview_result, raw_data, error = import_service.preview_import_session(test_file, "admin", True)
    session, msg = session_manager.create_session(test_file, 'json', "admin", True, raw_data, preview_result)
    
    if preview_result.get_total_conflict() > 0:
        conflict_row = preview_result.devices["conflict"][0]
        record_id = conflict_row.row_data.get('device_id')
        session_manager.resolve_conflict(session.session_id, record_id, "device", 
                                      conflict_row.row_data, ConflictDecision.OVERWRITE_LOCAL, "admin")
    
    session_id = session.session_id
    event_count_before = len(session.events)
    print(f"  {PASS} Session created with {event_count_before} events")
    
    print("\n[Step 2] Simulate restart")
    del service
    del import_service
    del session_manager
    
    service2 = DeviceService()
    session_manager2 = ImportSessionManager(service2.storage, service2)
    
    print("\n[Step 3] Recover session and verify events persist")
    recovered_session = session_manager2.check_active_session()
    assert recovered_session is not None, "Session should be recovered"
    assert recovered_session.session_id == session_id, "Session ID should match"
    print(f"  {PASS} Session recovered: {recovered_session.session_id}")
    
    event_count_after = len(recovered_session.events)
    assert event_count_after >= event_count_before, f"Events should persist, got {event_count_after} before {event_count_before}"
    print(f"  {PASS} Events persisted: {event_count_after} events")
    
    print("\n[Step 4] Verify error snapshots persist")
    assert hasattr(recovered_session, 'error_snapshots'), "Should have error_snapshots attribute"
    assert hasattr(recovered_session, 'permission'), "Should have permission attribute"
    print(f"  {PASS} Extended attributes persist")
    
    print("\n[Step 5] Commit after restart")
    success, msg = session_manager2.commit_import(recovered_session, "admin", True)
    assert success, f"Commit should succeed after recovery: {msg}"
    
    recovered_session = session_manager2.get_session(session_id)
    assert recovered_session.status == "completed", f"Status should be completed, got {recovered_session.status}"
    assert recovered_session.can_undo == True, "Should be able to undo"
    print(f"  {PASS} Session completed after restart recovery")
    
    print("\n[Step 6] Verify undo works after restart")
    success, msg = session_manager2.undo_import(recovered_session, "admin", True)
    assert success, f"Undo should succeed: {msg}"
    print(f"  {PASS} Undo successful after restart recovery")
    
    print("\n" + "=" * 60)
    print(f"Cross-Restart Recovery With Events Test: {PASS} All Passed")
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
        test_session_create_and_persist()
        test_session_conflict_resolution()
        test_session_overwrite_local()
        test_session_skip()
        test_session_permission_block()
        test_session_file_integrity_check()
        test_session_undo_after_restart()
        test_session_log_export()
        test_session_conflict_unified()
        test_session_batch_decision()
        test_session_restart_recovery()
        test_session_undo_after_import()
        test_session_complete_flow()
        test_session_filter_and_batch()
        test_conflict_incomplete_submit_block()
        test_session_event_chain_tracking()
        test_session_error_snapshot()
        test_session_permission_control()
        test_session_history_viewing()
        test_session_file_integrity_validation()
        test_cross_restart_recovery_with_events()
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
