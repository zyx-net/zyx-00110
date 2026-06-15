import json
import os
from datetime import datetime
from model.device import Device, RepairRecord, ApprovalRecord, Config, ImportLog, RollbackState
from model.device import ImportSession, SessionImportLog


class JSONStorage:
    def __init__(self, data_dir="data"):
        self.data_dir = data_dir
        self.devices_file = os.path.join(data_dir, "devices.json")
        self.repair_records_file = os.path.join(data_dir, "repair_records.json")
        self.approval_records_file = os.path.join(data_dir, "approval_records.json")
        self.config_file = os.path.join(data_dir, "config.json")
        self.import_logs_file = os.path.join(data_dir, "import_logs.json")
        self.rollback_state_file = os.path.join(data_dir, "rollback_state.json")
        self._ensure_dir()
        self._init_files()

    def _ensure_dir(self):
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)

    def _init_files(self):
        if not os.path.exists(self.devices_file):
            with open(self.devices_file, "w", encoding="utf-8") as f:
                json.dump([], f)
        if not os.path.exists(self.repair_records_file):
            with open(self.repair_records_file, "w", encoding="utf-8") as f:
                json.dump([], f)
        if not os.path.exists(self.approval_records_file):
            with open(self.approval_records_file, "w", encoding="utf-8") as f:
                json.dump([], f)
        if not os.path.exists(self.config_file):
            config = Config()
            self.save_config(config)
        if not os.path.exists(self.import_logs_file):
            with open(self.import_logs_file, "w", encoding="utf-8") as f:
                json.dump([], f)
        if not os.path.exists(self.rollback_state_file):
            self.save_rollback_state(RollbackState())

    def load_devices(self):
        try:
            with open(self.devices_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return [Device.from_dict(item) for item in data]
        except Exception:
            return []

    def save_devices(self, devices):
        with open(self.devices_file, "w", encoding="utf-8") as f:
            json.dump([d.to_dict() for d in devices], f, indent=2, ensure_ascii=False)

    def load_repair_records(self):
        try:
            with open(self.repair_records_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return [RepairRecord.from_dict(item) for item in data]
        except Exception:
            return []

    def save_repair_records(self, records):
        with open(self.repair_records_file, "w", encoding="utf-8") as f:
            json.dump([r.to_dict() for r in records], f, indent=2, ensure_ascii=False)

    def load_approval_records(self):
        try:
            with open(self.approval_records_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return [ApprovalRecord.from_dict(item) for item in data]
        except Exception:
            return []

    def save_approval_records(self, records):
        with open(self.approval_records_file, "w", encoding="utf-8") as f:
            json.dump([r.to_dict() for r in records], f, indent=2, ensure_ascii=False)

    def load_config(self):
        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return Config.from_dict(data)
        except Exception:
            return Config()

    def save_config(self, config):
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(config.to_dict(), f, indent=2, ensure_ascii=False)

    def load_import_logs(self):
        try:
            with open(self.import_logs_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return [ImportLog.from_dict(item) for item in data]
        except Exception:
            return []

    def save_import_logs(self, logs):
        with open(self.import_logs_file, "w", encoding="utf-8") as f:
            json.dump([log.to_dict() for log in logs], f, indent=2, ensure_ascii=False)

    def add_import_log(self, log):
        logs = self.load_import_logs()
        logs.append(log)
        self.save_import_logs(logs)

    def load_rollback_state(self):
        try:
            with open(self.rollback_state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return RollbackState.from_dict(data)
        except Exception:
            return RollbackState()

    def save_rollback_state(self, state):
        with open(self.rollback_state_file, "w", encoding="utf-8") as f:
            json.dump(state.to_dict(), f, indent=2, ensure_ascii=False)

    def _get_sessions_file(self):
        return os.path.join(self.data_dir, "import_sessions.json")

    def _get_session_logs_file(self):
        return os.path.join(self.data_dir, "session_import_logs.json")

    def load_active_session(self):
        try:
            with open(self._get_sessions_file(), "r", encoding="utf-8") as f:
                sessions = json.load(f)
                for session_data in sessions:
                    if session_data.get("status") in [ImportSession.STATUS_PENDING, 
                                                       ImportSession.STATUS_IN_PROGRESS,
                                                       ImportSession.STATUS_WAITING_CONFIRM]:
                        return ImportSession.from_dict(session_data)
            return None
        except Exception:
            return None

    def save_session(self, session):
        try:
            sessions = []
            if os.path.exists(self._get_sessions_file()):
                with open(self._get_sessions_file(), "r", encoding="utf-8") as f:
                    sessions = json.load(f)
            
            sessions = [s for s in sessions if s.get("session_id") != session.session_id]
            sessions.append(session.to_dict())
            
            with open(self._get_sessions_file(), "w", encoding="utf-8") as f:
                json.dump(sessions, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            return False

    def get_session(self, session_id):
        try:
            with open(self._get_sessions_file(), "r", encoding="utf-8") as f:
                sessions = json.load(f)
                for session_data in sessions:
                    if session_data.get("session_id") == session_id:
                        return ImportSession.from_dict(session_data)
            return None
        except Exception:
            return None

    def delete_session(self, session_id):
        try:
            with open(self._get_sessions_file(), "r", encoding="utf-8") as f:
                sessions = json.load(f)
            
            sessions = [s for s in sessions if s.get("session_id") != session_id]
            
            with open(self._get_sessions_file(), "w", encoding="utf-8") as f:
                json.dump(sessions, f, indent=2, ensure_ascii=False)
            return True
        except Exception:
            return False

    def load_session_import_logs(self):
        try:
            with open(self._get_session_logs_file(), "r", encoding="utf-8") as f:
                data = json.load(f)
                return [SessionImportLog.from_dict(item) for item in data]
        except Exception:
            return []

    def save_session_import_log(self, log):
        try:
            logs = self.load_session_import_logs()
            logs.append(log)
            with open(self._get_session_logs_file(), "w", encoding="utf-8") as f:
                json.dump([l.to_dict() for l in logs], f, indent=2, ensure_ascii=False)
            return True
        except Exception:
            return False

    def export_session_log(self, log, file_path):
        try:
            log_data = log.to_dict()
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(log_data, f, indent=2, ensure_ascii=False)
            return True
        except Exception:
            return False

    def load_all_sessions(self):
        try:
            if not os.path.exists(self._get_sessions_file()):
                return []
            with open(self._get_sessions_file(), "r", encoding="utf-8") as f:
                sessions = json.load(f)
                return [ImportSession.from_dict(s) for s in sessions]
        except Exception:
            return []

    def get_sessions_by_time_range(self, start_time=None, end_time=None, operator=None):
        sessions = self.load_all_sessions()
        result = []
        for session in sessions:
            if operator and session.operator != operator:
                continue
            if start_time and session.created_time < start_time:
                continue
            if end_time and session.created_time > end_time:
                continue
            result.append(session)
        result.sort(key=lambda x: x.created_time, reverse=True)
        return result

    def get_sessions_by_status(self, status):
        sessions = self.load_all_sessions()
        return [s for s in sessions if s.status == status]

    def get_failed_sessions(self):
        sessions = self.load_all_sessions()
        return [s for s in sessions if s.status == ImportSession.STATUS_FAILED]

    def get_session_history(self, session_id=None, limit=50):
        sessions = self.load_all_sessions()
        if session_id:
            sessions = [s for s in sessions if s.session_id == session_id]
        sessions.sort(key=lambda x: x.created_time, reverse=True)
        return sessions[:limit]

    def export_session_snapshot(self, session, file_path):
        try:
            snapshot = {
                "session_info": {
                    "session_id": session.session_id,
                    "file_path": session.file_path,
                    "file_type": session.file_type,
                    "operator": session.operator,
                    "is_supervisor": session.is_supervisor,
                    "created_time": session.created_time,
                    "updated_time": session.updated_time,
                    "status": session.status,
                    "committed": session.committed,
                    "commit_time": session.commit_time,
                    "result_message": session.result_message,
                    "can_undo": session.can_undo
                },
                "event_chain": [e.to_dict() for e in session.events],
                "error_snapshots": [s.to_dict() for s in session.error_snapshots],
                "conflict_resolutions": [r.to_dict() for r in session.conflict_resolutions],
                "preview_summary": None,
                "export_time": datetime.now().isoformat()
            }
            if session.preview_result:
                snapshot["preview_summary"] = {
                    "devices": {k: len(v) for k, v in session.preview_result.devices.items()},
                    "repair_records": {k: len(v) for k, v in session.preview_result.repair_records.items()},
                    "approval_records": {k: len(v) for k, v in session.preview_result.approval_records.items()}
                }
            if session.raw_data:
                snapshot["raw_data"] = session.raw_data
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(snapshot, f, indent=2, ensure_ascii=False)
            return True, None
        except Exception as e:
            return False, str(e)

    def export_failed_session_snapshot(self, session_id, file_path):
        session = self.get_session(session_id)
        if not session:
            return False, "会话不存在"
        if not session.has_error_snapshots():
            return False, "会话没有错误快照"
        return self.export_session_snapshot(session, file_path)
