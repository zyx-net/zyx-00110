from datetime import datetime
from model.status import DeviceStatus


class ImportLog:
    def __init__(self, log_id, import_time, file_path, file_type, operator, is_supervisor,
                 total_rows=0, new_rows=0, overwrite_rows=0, conflict_rows=0, invalid_rows=0,
                 status="", message=""):
        self.log_id = log_id
        self.import_time = import_time
        self.file_path = file_path
        self.file_type = file_type
        self.operator = operator
        self.is_supervisor = is_supervisor
        self.total_rows = total_rows
        self.new_rows = new_rows
        self.overwrite_rows = overwrite_rows
        self.conflict_rows = conflict_rows
        self.invalid_rows = invalid_rows
        self.status = status
        self.message = message

    def to_dict(self):
        return {
            "log_id": self.log_id,
            "import_time": self.import_time,
            "file_path": self.file_path,
            "file_type": self.file_type,
            "operator": self.operator,
            "is_supervisor": self.is_supervisor,
            "total_rows": self.total_rows,
            "new_rows": self.new_rows,
            "overwrite_rows": self.overwrite_rows,
            "conflict_rows": self.conflict_rows,
            "invalid_rows": self.invalid_rows,
            "status": self.status,
            "message": self.message
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            log_id=data["log_id"],
            import_time=data["import_time"],
            file_path=data["file_path"],
            file_type=data["file_type"],
            operator=data["operator"],
            is_supervisor=data["is_supervisor"],
            total_rows=data.get("total_rows", 0),
            new_rows=data.get("new_rows", 0),
            overwrite_rows=data.get("overwrite_rows", 0),
            conflict_rows=data.get("conflict_rows", 0),
            invalid_rows=data.get("invalid_rows", 0),
            status=data.get("status", ""),
            message=data.get("message", "")
        )


class PreviewRow:
    def __init__(self, row_type, row_data, reason=""):
        self.row_type = row_type
        self.row_data = row_data
        self.reason = reason

    def to_dict(self):
        return {
            "row_type": self.row_type,
            "row_data": self.row_data,
            "reason": self.reason
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            row_type=data["row_type"],
            row_data=data["row_data"],
            reason=data.get("reason", "")
        )


class PreviewResult:
    def __init__(self):
        self.new_rows = []
        self.overwrite_rows = []
        self.conflict_rows = []
        self.invalid_rows = []

    def add_new(self, row_data):
        self.new_rows.append(PreviewRow("new", row_data))

    def add_overwrite(self, row_data):
        self.overwrite_rows.append(PreviewRow("overwrite", row_data))

    def add_conflict(self, row_data, reason):
        self.conflict_rows.append(PreviewRow("conflict", row_data, reason))

    def add_invalid(self, row_data, reason):
        self.invalid_rows.append(PreviewRow("invalid", row_data, reason))

    def to_dict(self):
        return {
            "new_rows": [r.to_dict() for r in self.new_rows],
            "overwrite_rows": [r.to_dict() for r in self.overwrite_rows],
            "conflict_rows": [r.to_dict() for r in self.conflict_rows],
            "invalid_rows": [r.to_dict() for r in self.invalid_rows]
        }

    @property
    def total_rows(self):
        return len(self.new_rows) + len(self.overwrite_rows) + len(self.conflict_rows) + len(self.invalid_rows)


class RollbackState:
    def __init__(self, backup_path="", import_log_id="", import_time="", can_rollback=False):
        self.backup_path = backup_path
        self.import_log_id = import_log_id
        self.import_time = import_time
        self.can_rollback = can_rollback

    def to_dict(self):
        return {
            "backup_path": self.backup_path,
            "import_log_id": self.import_log_id,
            "import_time": self.import_time,
            "can_rollback": self.can_rollback
        }

    @classmethod
    def from_dict(cls, data):
        if not data:
            return cls()
        return cls(
            backup_path=data.get("backup_path", ""),
            import_log_id=data.get("import_log_id", ""),
            import_time=data.get("import_time", ""),
            can_rollback=data.get("can_rollback", False)
        )


class Device:
    def __init__(self, device_id, name, status=DeviceStatus.NORMAL.value, abnormal_desc="", create_time=None, update_time=None):
        self.device_id = device_id
        self.name = name
        self.status = status
        self.abnormal_desc = abnormal_desc
        self.create_time = create_time or datetime.now().isoformat()
        self.update_time = update_time or datetime.now().isoformat()

    def to_dict(self):
        return {
            "device_id": self.device_id,
            "name": self.name,
            "status": self.status,
            "abnormal_desc": self.abnormal_desc,
            "create_time": self.create_time,
            "update_time": self.update_time
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            device_id=data["device_id"],
            name=data["name"],
            status=data["status"],
            abnormal_desc=data.get("abnormal_desc", ""),
            create_time=data.get("create_time"),
            update_time=data.get("update_time")
        )


class RepairRecord:
    def __init__(self, record_id, device_id, repair_desc, operator, repair_time=None):
        self.record_id = record_id
        self.device_id = device_id
        self.repair_desc = repair_desc
        self.operator = operator
        self.repair_time = repair_time or datetime.now().isoformat()

    def to_dict(self):
        return {
            "record_id": self.record_id,
            "device_id": self.device_id,
            "repair_desc": self.repair_desc,
            "operator": self.operator,
            "repair_time": self.repair_time
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            record_id=data["record_id"],
            device_id=data["device_id"],
            repair_desc=data["repair_desc"],
            operator=data["operator"],
            repair_time=data.get("repair_time")
        )


class ApprovalRecord:
    def __init__(self, record_id, device_id, approval_type, opinion, approver, approve_time=None):
        self.record_id = record_id
        self.device_id = device_id
        self.approval_type = approval_type
        self.opinion = opinion
        self.approver = approver
        self.approve_time = approve_time or datetime.now().isoformat()

    def to_dict(self):
        return {
            "record_id": self.record_id,
            "device_id": self.device_id,
            "approval_type": self.approval_type,
            "opinion": self.opinion,
            "approver": self.approver,
            "approve_time": self.approve_time
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            record_id=data["record_id"],
            device_id=data["device_id"],
            approval_type=data["approval_type"],
            opinion=data["opinion"],
            approver=data["approver"],
            approve_time=data.get("approve_time")
        )


class Config:
    def __init__(self, export_dir=".", threshold_low=0, threshold_high=100):
        self.export_dir = export_dir
        self.threshold_low = threshold_low
        self.threshold_high = threshold_high

    def to_dict(self):
        return {
            "export_dir": self.export_dir,
            "threshold_low": self.threshold_low,
            "threshold_high": self.threshold_high
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            export_dir=data.get("export_dir", "."),
            threshold_low=data.get("threshold_low", 0),
            threshold_high=data.get("threshold_high", 100)
        )


class ConflictDecision:
    KEEP_LOCAL = "keep_local"
    OVERWRITE_LOCAL = "overwrite_local"
    SKIP = "skip"


class ConflictResolution:
    def __init__(self, record_id, record_type, row_data, decision, decision_time=None):
        self.record_id = record_id
        self.record_type = record_type
        self.row_data = row_data
        self.decision = decision
        self.decision_time = decision_time or datetime.now().isoformat()

    def to_dict(self):
        return {
            "record_id": self.record_id,
            "record_type": self.record_type,
            "row_data": self.row_data,
            "decision": self.decision,
            "decision_time": self.decision_time
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            record_id=data["record_id"],
            record_type=data["record_type"],
            row_data=data["row_data"],
            decision=data["decision"],
            decision_time=data.get("decision_time")
        )


class SessionPreviewResult:
    def __init__(self):
        self.devices = {
            "new": [],
            "overwrite": [],
            "conflict": [],
            "invalid": []
        }
        self.repair_records = {
            "new": [],
            "overwrite": [],
            "conflict": [],
            "invalid": []
        }
        self.approval_records = {
            "new": [],
            "overwrite": [],
            "conflict": [],
            "invalid": []
        }

    def add_device_new(self, row_data):
        self.devices["new"].append(PreviewRow("device", row_data))

    def add_device_overwrite(self, row_data):
        self.devices["overwrite"].append(PreviewRow("device", row_data))

    def add_device_conflict(self, row_data, reason):
        self.devices["conflict"].append(PreviewRow("device", row_data, reason))

    def add_device_invalid(self, row_data, reason):
        self.devices["invalid"].append(PreviewRow("device", row_data, reason))

    def add_repair_new(self, row_data):
        self.repair_records["new"].append(PreviewRow("repair", row_data))

    def add_repair_overwrite(self, row_data):
        self.repair_records["overwrite"].append(PreviewRow("repair", row_data))

    def add_repair_conflict(self, row_data, reason):
        self.repair_records["conflict"].append(PreviewRow("repair", row_data, reason))

    def add_repair_invalid(self, row_data, reason):
        self.repair_records["invalid"].append(PreviewRow("repair", row_data, reason))

    def add_approval_new(self, row_data):
        self.approval_records["new"].append(PreviewRow("approval", row_data))

    def add_approval_overwrite(self, row_data):
        self.approval_records["overwrite"].append(PreviewRow("approval", row_data))

    def add_approval_conflict(self, row_data, reason):
        self.approval_records["conflict"].append(PreviewRow("approval", row_data, reason))

    def add_approval_invalid(self, row_data, reason):
        self.approval_records["invalid"].append(PreviewRow("approval", row_data, reason))

    def to_dict(self):
        return {
            "devices": {
                "new": [r.to_dict() for r in self.devices["new"]],
                "overwrite": [r.to_dict() for r in self.devices["overwrite"]],
                "conflict": [r.to_dict() for r in self.devices["conflict"]],
                "invalid": [r.to_dict() for r in self.devices["invalid"]]
            },
            "repair_records": {
                "new": [r.to_dict() for r in self.repair_records["new"]],
                "overwrite": [r.to_dict() for r in self.repair_records["overwrite"]],
                "conflict": [r.to_dict() for r in self.repair_records["conflict"]],
                "invalid": [r.to_dict() for r in self.repair_records["invalid"]]
            },
            "approval_records": {
                "new": [r.to_dict() for r in self.approval_records["new"]],
                "overwrite": [r.to_dict() for r in self.approval_records["overwrite"]],
                "conflict": [r.to_dict() for r in self.approval_records["conflict"]],
                "invalid": [r.to_dict() for r in self.approval_records["invalid"]]
            }
        }

    @classmethod
    def from_dict(cls, data):
        result = cls()
        result.devices = {
            "new": [PreviewRow.from_dict(r) for r in data["devices"]["new"]],
            "overwrite": [PreviewRow.from_dict(r) for r in data["devices"]["overwrite"]],
            "conflict": [PreviewRow.from_dict(r) for r in data["devices"]["conflict"]],
            "invalid": [PreviewRow.from_dict(r) for r in data["devices"]["invalid"]]
        }
        result.repair_records = {
            "new": [PreviewRow.from_dict(r) for r in data["repair_records"]["new"]],
            "overwrite": [PreviewRow.from_dict(r) for r in data["repair_records"]["overwrite"]],
            "conflict": [PreviewRow.from_dict(r) for r in data["repair_records"]["conflict"]],
            "invalid": [PreviewRow.from_dict(r) for r in data["repair_records"]["invalid"]]
        }
        result.approval_records = {
            "new": [PreviewRow.from_dict(r) for r in data["approval_records"]["new"]],
            "overwrite": [PreviewRow.from_dict(r) for r in data["approval_records"]["overwrite"]],
            "conflict": [PreviewRow.from_dict(r) for r in data["approval_records"]["conflict"]],
            "invalid": [PreviewRow.from_dict(r) for r in data["approval_records"]["invalid"]]
        }
        return result

    def get_total(self, category):
        return sum(len(self.__dict__[category][key]) for key in ["new", "overwrite", "conflict", "invalid"])

    def get_total_new(self):
        return len(self.devices["new"]) + len(self.repair_records["new"]) + len(self.approval_records["new"])

    def get_total_overwrite(self):
        return len(self.devices["overwrite"]) + len(self.repair_records["overwrite"]) + len(self.approval_records["overwrite"])

    def get_total_conflict(self):
        return len(self.devices["conflict"]) + len(self.repair_records["conflict"]) + len(self.approval_records["conflict"])

    def get_total_invalid(self):
        return len(self.devices["invalid"]) + len(self.repair_records["invalid"]) + len(self.approval_records["invalid"])


class ImportSession:
    STATUS_PENDING = "pending"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_WAITING_CONFIRM = "waiting_confirm"
    STATUS_COMPLETED = "completed"
    STATUS_CANCELLED = "cancelled"
    STATUS_FAILED = "failed"

    def __init__(self, session_id=None, file_path=None, file_type=None, operator=None, 
                 is_supervisor=False, created_time=None):
        self.session_id = session_id or f"SESSION_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        self.file_path = file_path
        self.file_type = file_type
        self.operator = operator
        self.is_supervisor = is_supervisor
        self.created_time = created_time or datetime.now().isoformat()
        self.updated_time = datetime.now().isoformat()
        self.status = self.STATUS_PENDING
        self.preview_result = None
        self.raw_data = None
        self.conflict_resolutions = []
        self.file_checksum = None
        self.backup_path = None
        self.committed = False
        self.commit_time = None
        self.commit_operator = None
        self.result_message = ""
        self.can_undo = False

    def to_dict(self):
        return {
            "session_id": self.session_id,
            "file_path": self.file_path,
            "file_type": self.file_type,
            "operator": self.operator,
            "is_supervisor": self.is_supervisor,
            "created_time": self.created_time,
            "updated_time": self.updated_time,
            "status": self.status,
            "preview_result": self.preview_result.to_dict() if self.preview_result else None,
            "raw_data": self.raw_data,
            "conflict_resolutions": [r.to_dict() for r in self.conflict_resolutions],
            "file_checksum": self.file_checksum,
            "backup_path": self.backup_path,
            "committed": self.committed,
            "commit_time": self.commit_time,
            "commit_operator": self.commit_operator,
            "result_message": self.result_message,
            "can_undo": self.can_undo
        }

    @classmethod
    def from_dict(cls, data):
        session = cls(
            session_id=data["session_id"],
            file_path=data["file_path"],
            file_type=data["file_type"],
            operator=data["operator"],
            is_supervisor=data["is_supervisor"],
            created_time=data.get("created_time")
        )
        session.updated_time = data.get("updated_time", session.updated_time)
        session.status = data.get("status", cls.STATUS_PENDING)
        if data.get("preview_result"):
            session.preview_result = SessionPreviewResult.from_dict(data["preview_result"])
        session.raw_data = data.get("raw_data")
        session.conflict_resolutions = [ConflictResolution.from_dict(r) for r in data.get("conflict_resolutions", [])]
        session.file_checksum = data.get("file_checksum")
        session.backup_path = data.get("backup_path")
        session.committed = data.get("committed", False)
        session.commit_time = data.get("commit_time")
        session.commit_operator = data.get("commit_operator")
        session.result_message = data.get("result_message", "")
        session.can_undo = data.get("can_undo", False)
        return session

    def get_conflict_resolution(self, record_id):
        for resolution in self.conflict_resolutions:
            if resolution.record_id == record_id:
                return resolution.decision
        return None

    def set_conflict_resolution(self, record_id, record_type, row_data, decision):
        for resolution in self.conflict_resolutions:
            if resolution.record_id == record_id:
                resolution.decision = decision
                resolution.decision_time = datetime.now().isoformat()
                self.updated_time = datetime.now().isoformat()
                return
        self.conflict_resolutions.append(ConflictResolution(record_id, record_type, row_data, decision))

    def is_all_conflicts_resolved(self):
        all_conflicts = []
        if self.preview_result:
            all_conflicts.extend(self.preview_result.devices["conflict"])
            all_conflicts.extend(self.preview_result.repair_records["conflict"])
            all_conflicts.extend(self.preview_result.approval_records["conflict"])
        
        for conflict in all_conflicts:
            if self.get_conflict_resolution(conflict.row_data.get('device_id') or conflict.row_data.get('record_id')) is None:
                return False
        return True

    def get_unresolved_conflicts_count(self):
        if not self.preview_result:
            return 0
        
        count = 0
        for category in ["devices", "repair_records", "approval_records"]:
            for conflict in self.preview_result.__dict__[category]["conflict"]:
                record_id = conflict.row_data.get('device_id') or conflict.row_data.get('record_id')
                if self.get_conflict_resolution(record_id) is None:
                    count += 1
        return count


class SessionImportLog:
    def __init__(self, log_id, session_id, import_time, operator, is_supervisor,
                 total_rows=0, new_rows=0, overwrite_rows=0, skipped_rows=0, 
                 conflict_resolved=0, status="", message="", details=None):
        self.log_id = log_id
        self.session_id = session_id
        self.import_time = import_time
        self.operator = operator
        self.is_supervisor = is_supervisor
        self.total_rows = total_rows
        self.new_rows = new_rows
        self.overwrite_rows = overwrite_rows
        self.skipped_rows = skipped_rows
        self.conflict_resolved = conflict_resolved
        self.status = status
        self.message = message
        self.details = details or {}

    def to_dict(self):
        return {
            "log_id": self.log_id,
            "session_id": self.session_id,
            "import_time": self.import_time,
            "operator": self.operator,
            "is_supervisor": self.is_supervisor,
            "total_rows": self.total_rows,
            "new_rows": self.new_rows,
            "overwrite_rows": self.overwrite_rows,
            "skipped_rows": self.skipped_rows,
            "conflict_resolved": self.conflict_resolved,
            "status": self.status,
            "message": self.message,
            "details": self.details
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            log_id=data["log_id"],
            session_id=data["session_id"],
            import_time=data["import_time"],
            operator=data["operator"],
            is_supervisor=data["is_supervisor"],
            total_rows=data.get("total_rows", 0),
            new_rows=data.get("new_rows", 0),
            overwrite_rows=data.get("overwrite_rows", 0),
            skipped_rows=data.get("skipped_rows", 0),
            conflict_resolved=data.get("conflict_resolved", 0),
            status=data.get("status", ""),
            message=data.get("message", ""),
            details=data.get("details", {})
        )
