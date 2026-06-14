import json
import os
from model.device import Device, RepairRecord, ApprovalRecord, Config, ImportLog, RollbackState


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
