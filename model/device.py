from datetime import datetime
from model.status import DeviceStatus


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
