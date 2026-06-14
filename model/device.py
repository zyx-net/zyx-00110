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
