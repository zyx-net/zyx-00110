import os
import sys
import json
import tempfile
import unittest
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from service.session_manager import ImportSessionManager
from storage.json_storage import JSONStorage
from model.device import ImportSession, SessionPreviewResult, ConflictDecision, SessionEventType


class TestFailedSession(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.storage = JSONStorage(data_dir=self.temp_dir)
        self.session_manager = ImportSessionManager(storage=self.storage)
        
    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_failed_session_status_transition(self):
        preview_result = SessionPreviewResult()
        preview_result.add_device_conflict({"device_id": "D001", "name": "Test Device"}, "冲突测试")
        
        session = ImportSession(file_path="/test/path.json", file_type="json", operator="test_user", is_supervisor=False)
        session.status = ImportSession.STATUS_IN_PROGRESS
        session.preview_result = preview_result
        session.raw_data = {"devices": [], "repair_records": [], "approval_records": []}
        
        self.storage.save_session(session)
        
        self.session_manager._mark_session_failed(session, "test_error", "测试错误", {"test_key": "test_value"})
        
        saved_session = self.storage.get_session(session.session_id)
        self.assertEqual(saved_session.status, ImportSession.STATUS_FAILED)
        self.assertIsNotNone(saved_session.end_time)
        self.assertEqual(saved_session.result_message, "测试错误")
        self.assertTrue(saved_session.has_error_snapshots())
        self.assertEqual(len(saved_session.error_snapshots), 1)
        self.assertEqual(saved_session.error_snapshots[0].error_type, "test_error")
        self.assertEqual(saved_session.error_snapshots[0].error_message, "测试错误")
        self.assertEqual(saved_session.error_snapshots[0].context, {"test_key": "test_value"})
        
        events = [e for e in saved_session.events if e.event_type == SessionEventType.COMMIT_FAILED]
        self.assertEqual(len(events), 1)

    def test_failed_session_in_list(self):
        preview_result = SessionPreviewResult()
        preview_result.add_device_conflict({"device_id": "D001", "name": "Test Device"}, "冲突测试")
        
        session = ImportSession(file_path="/test/path.json", file_type="json", operator="test_user", is_supervisor=False)
        session.status = ImportSession.STATUS_IN_PROGRESS
        session.preview_result = preview_result
        session.raw_data = {"devices": [], "repair_records": [], "approval_records": []}
        
        self.storage.save_session(session)
        self.session_manager._mark_session_failed(session, "test_error", "测试错误")
        
        failed_sessions = self.session_manager.get_failed_sessions()
        self.assertEqual(len(failed_sessions), 1)
        self.assertEqual(failed_sessions[0].session_id, session.session_id)

    def test_failed_session_filter_by_operator(self):
        preview_result = SessionPreviewResult()
        preview_result.add_device_conflict({"device_id": "D001", "name": "Test Device"}, "冲突测试")
        
        session1 = ImportSession(file_path="/test/path1.json", file_type="json", operator="user1", is_supervisor=False)
        session1.status = ImportSession.STATUS_IN_PROGRESS
        session1.preview_result = preview_result
        session1.raw_data = {"devices": [], "repair_records": [], "approval_records": []}
        
        session2 = ImportSession(file_path="/test/path2.json", file_type="json", operator="user2", is_supervisor=False)
        session2.status = ImportSession.STATUS_IN_PROGRESS
        session2.preview_result = preview_result
        session2.raw_data = {"devices": [], "repair_records": [], "approval_records": []}
        
        self.storage.save_session(session1)
        self.storage.save_session(session2)
        
        self.session_manager._mark_session_failed(session1, "error1", "错误1")
        self.session_manager._mark_session_failed(session2, "error2", "错误2")
        
        filtered = self.session_manager.get_failed_sessions_with_filter(operator="user1")
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].operator, "user1")
        
        filtered = self.session_manager.get_failed_sessions_with_filter(operator="user2")
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].operator, "user2")

    def test_failed_session_filter_by_error_type(self):
        preview_result = SessionPreviewResult()
        preview_result.add_device_conflict({"device_id": "D001", "name": "Test Device"}, "冲突测试")
        
        session1 = ImportSession(file_path="/test/path1.json", file_type="json", operator="user1", is_supervisor=False)
        session1.status = ImportSession.STATUS_IN_PROGRESS
        session1.preview_result = preview_result
        session1.raw_data = {"devices": [], "repair_records": [], "approval_records": []}
        
        session2 = ImportSession(file_path="/test/path2.json", file_type="json", operator="user2", is_supervisor=False)
        session2.status = ImportSession.STATUS_IN_PROGRESS
        session2.preview_result = preview_result
        session2.raw_data = {"devices": [], "repair_records": [], "approval_records": []}
        
        self.storage.save_session(session1)
        self.storage.save_session(session2)
        
        self.session_manager._mark_session_failed(session1, "validation_error", "校验错误")
        self.session_manager._mark_session_failed(session2, "permission_denied", "权限错误")
        
        filtered = self.session_manager.get_failed_sessions_with_filter(error_type="validation_error")
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].error_snapshots[0].error_type, "validation_error")
        
        filtered = self.session_manager.get_failed_sessions_with_filter(error_type="permission_denied")
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].error_snapshots[0].error_type, "permission_denied")

    def test_failed_session_count(self):
        preview_result = SessionPreviewResult()
        preview_result.add_device_conflict({"device_id": "D001", "name": "Test Device"}, "冲突测试")
        
        for i in range(5):
            session = ImportSession(file_path=f"/test/path{i}.json", file_type="json", operator="user1", is_supervisor=False)
            session.status = ImportSession.STATUS_IN_PROGRESS
            session.preview_result = preview_result
            session.raw_data = {"devices": [], "repair_records": [], "approval_records": []}
            self.storage.save_session(session)
            self.session_manager._mark_session_failed(session, "test_error", "测试错误")
        
        count = self.session_manager.get_failed_session_count()
        self.assertEqual(count, 5)
        
        count = self.session_manager.get_failed_session_count(operator="user1")
        self.assertEqual(count, 5)
        
        count = self.session_manager.get_failed_session_count(operator="user2")
        self.assertEqual(count, 0)

    def test_failed_import_log_created(self):
        preview_result = SessionPreviewResult()
        preview_result.add_device_conflict({"device_id": "D001", "name": "Test Device"}, "冲突测试")
        
        session = ImportSession(file_path="/test/path.json", file_type="json", operator="test_user", is_supervisor=False)
        session.status = ImportSession.STATUS_IN_PROGRESS
        session.preview_result = preview_result
        session.raw_data = {"devices": [], "repair_records": [], "approval_records": []}
        
        self.storage.save_session(session)
        
        log_id = self.session_manager._create_failed_import_log(session, "test_user", False, "test_error", "测试错误")
        
        self.assertIsNotNone(log_id)
        self.assertTrue(log_id.startswith("IMP_"))
        
        logs = self.session_manager.get_session_logs()
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0].session_id, session.session_id)
        self.assertEqual(logs[0].status, "failed")
        self.assertEqual(logs[0].message, "测试错误")

    def test_export_failed_session_report(self):
        preview_result = SessionPreviewResult()
        preview_result.add_device_conflict({"device_id": "D001", "name": "Test Device"}, "冲突测试")
        
        for i in range(3):
            session = ImportSession(file_path=f"/test/path{i}.json", file_type="json", operator="user1", is_supervisor=False)
            session.status = ImportSession.STATUS_IN_PROGRESS
            session.preview_result = preview_result
            session.raw_data = {"devices": [], "repair_records": [], "approval_records": []}
            self.storage.save_session(session)
            self.session_manager._mark_session_failed(session, "test_error", f"测试错误{i}")
        
        output_path = os.path.join(self.temp_dir, "failed_report.json")
        success, error = self.session_manager.export_failed_sessions_report(output_path, "user1", is_supervisor=True)
        
        if not success:
            print(f"export_failed_sessions_report error: {error}")
        self.assertTrue(success, f"export_failed_sessions_report failed: {error}")
        self.assertIsNone(error)
        self.assertTrue(os.path.exists(output_path))
        
        with open(output_path, 'r', encoding='utf-8') as f:
            report = json.load(f)
        
        self.assertEqual(report["total_failed_sessions"], 3)
        self.assertEqual(len(report["sessions"]), 3)
        self.assertIn("report_generated_time", report)
        self.assertIn("filter_params", report)

    def test_export_failed_session_detailed(self):
        preview_result = SessionPreviewResult()
        preview_result.add_device_conflict({"device_id": "D001", "name": "Test Device"}, "冲突测试")
        
        session = ImportSession(file_path="/test/path.json", file_type="json", operator="user1", is_supervisor=False)
        session.status = ImportSession.STATUS_IN_PROGRESS
        session.preview_result = preview_result
        session.raw_data = {"devices": [], "repair_records": [], "approval_records": []}
        session.set_conflict_resolution("D001", "device", {"device_id": "D001", "name": "Test"}, ConflictDecision.OVERWRITE_LOCAL)
        
        self.storage.save_session(session)
        self.session_manager._mark_session_failed(session, "test_error", "测试错误")
        
        output_path = os.path.join(self.temp_dir, "detailed_export.json")
        success, error = self.session_manager.export_failed_session_detailed(session.session_id, output_path, "user1", is_supervisor=True)
        
        if not success:
            print(f"export_failed_session_detailed error: {error}")
        self.assertTrue(success, f"export_failed_session_detailed failed: {error}")
        self.assertIsNone(error)
        self.assertTrue(os.path.exists(output_path))
        
        with open(output_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        self.assertEqual(data["session_info"]["session_id"], session.session_id)
        self.assertEqual(data["session_info"]["status"], "failed")
        self.assertEqual(len(data["error_snapshots"]), 1)
        self.assertEqual(len(data["conflict_resolutions"]), 1)
        self.assertIn("export_time", data)
        self.assertIn("event_chain", data)
        self.assertIn("preview_result", data)


if __name__ == '__main__':
    unittest.main()
