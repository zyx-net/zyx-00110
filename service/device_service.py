import os
import json
from datetime import datetime
from model.status import DeviceStatus
from model.device import Device, RepairRecord, ApprovalRecord, Config
from storage.json_storage import JSONStorage

SUPERVISORS = {"李四", "王五", "赵六", "admin"}


class DeviceService:
    def __init__(self):
        self.storage = JSONStorage()
        self.devices = self.storage.load_devices()
        self.repair_records = self.storage.load_repair_records()
        self.approval_records = self.storage.load_approval_records()
        self.config = self.storage.load_config()

    def save_all(self):
        self.storage.save_devices(self.devices)
        self.storage.save_repair_records(self.repair_records)
        self.storage.save_approval_records(self.approval_records)

    def add_device(self, device_id, name):
        if any(d.device_id == device_id for d in self.devices):
            return False, "设备ID已存在"
        device = Device(device_id, name)
        self.devices.append(device)
        self.save_all()
        return True, "设备添加成功"

    def find_device(self, device_id):
        for d in self.devices:
            if d.device_id == device_id:
                return d
        return None

    def report_abnormal(self, device_id, abnormal_desc):
        device = self.find_device(device_id)
        if not device:
            return False, "设备不存在"
        if device.status != DeviceStatus.NORMAL.value:
            return False, "设备当前状态不允许报告异常"
        device.status = DeviceStatus.PENDING_STOP_APPROVAL.value
        device.abnormal_desc = abnormal_desc
        device.update_time = datetime.now().isoformat()
        self.save_all()
        return True, "异常报告成功，等待停机审批"

    def approve_stop(self, device_id, opinion, approver):
        device = self.find_device(device_id)
        if not device:
            return False, "设备不存在"
        if device.status != DeviceStatus.PENDING_STOP_APPROVAL.value:
            return False, "设备当前状态不是待停机审批"
        
        record = ApprovalRecord(
            record_id=f"APR_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            device_id=device_id,
            approval_type="停机",
            opinion=opinion,
            approver=approver
        )
        self.approval_records.append(record)
        device.status = DeviceStatus.STOPPED.value
        device.update_time = datetime.now().isoformat()
        self.save_all()
        return True, "停机审批通过"

    def apply_stop(self, device_id, reason):
        device = self.find_device(device_id)
        if not device:
            return False, "设备不存在"
        if device.status == DeviceStatus.STOPPED.value:
            return False, "设备已停机，不能重复停机"
        if device.status != DeviceStatus.PENDING_STOP_APPROVAL.value:
            return False, "设备当前状态不允许申请停机"
        
        record = ApprovalRecord(
            record_id=f"APR_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            device_id=device_id,
            approval_type="停机",
            opinion=reason,
            approver="系统"
        )
        self.approval_records.append(record)
        device.status = DeviceStatus.STOPPED.value
        device.update_time = datetime.now().isoformat()
        self.save_all()
        return True, "停机申请已提交"

    def start_repair(self, device_id, repair_desc, operator):
        device = self.find_device(device_id)
        if not device:
            return False, "设备不存在"
        if device.status != DeviceStatus.STOPPED.value:
            return False, "设备当前状态不是已停机，不能开始维修"
        
        device.status = DeviceStatus.UNDER_REPAIR.value
        device.update_time = datetime.now().isoformat()
        self.save_all()
        return True, "开始维修"

    def record_repair(self, device_id, repair_desc, operator):
        device = self.find_device(device_id)
        if not device:
            return False, "设备不存在"
        if device.status != DeviceStatus.UNDER_REPAIR.value:
            return False, "设备当前状态不是维修中"
        
        record = RepairRecord(
            record_id=f"REP_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            device_id=device_id,
            repair_desc=repair_desc,
            operator=operator
        )
        self.repair_records.append(record)
        device.status = DeviceStatus.PENDING_RESTART_APPROVAL.value
        device.update_time = datetime.now().isoformat()
        self.save_all()
        return True, "维修记录已保存，等待复机审批"

    def approve_restart(self, device_id, opinion, approver):
        device = self.find_device(device_id)
        if not device:
            return False, "设备不存在"
        if device.status != DeviceStatus.PENDING_RESTART_APPROVAL.value:
            return False, "设备当前状态不是待复机审批"
        
        if approver not in SUPERVISORS:
            return False, f"审批人'{approver}'不是主管，无权批准复机。主管包括：{', '.join(sorted(SUPERVISORS))}"
        
        repair_count = sum(1 for r in self.repair_records if r.device_id == device_id)
        if repair_count == 0:
            return False, "没有维修记录，不能批准复机"
        
        record = ApprovalRecord(
            record_id=f"APR_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            device_id=device_id,
            approval_type="复机",
            opinion=opinion,
            approver=approver
        )
        self.approval_records.append(record)
        device.status = DeviceStatus.RESTARTED.value
        device.update_time = datetime.now().isoformat()
        self.save_all()
        return True, "复机审批通过"

    def enter_observation(self, device_id):
        device = self.find_device(device_id)
        if not device:
            return False, "设备不存在"
        if device.status != DeviceStatus.RESTARTED.value:
            return False, "设备当前状态不是已复机，不能进入复发观察"
        
        device.status = DeviceStatus.OBSERVATION.value
        device.update_time = datetime.now().isoformat()
        self.save_all()
        return True, "已进入复发观察期"

    def exit_observation(self, device_id):
        device = self.find_device(device_id)
        if not device:
            return False, "设备不存在"
        if device.status != DeviceStatus.OBSERVATION.value:
            return False, "设备当前状态不是复发观察"
        
        device.status = DeviceStatus.NORMAL.value
        device.abnormal_desc = ""
        device.update_time = datetime.now().isoformat()
        self.save_all()
        return True, "已退出复发观察期，设备恢复正常"

    def get_repair_records_by_device(self, device_id):
        return [r for r in self.repair_records if r.device_id == device_id]

    def get_approval_records_by_device(self, device_id):
        return [r for r in self.approval_records if r.device_id == device_id]

    def get_all_devices(self):
        return self.devices

    def update_config(self, export_dir=None, threshold_low=None, threshold_high=None):
        old_export_dir = self.config.export_dir
        
        if export_dir is not None:
            if not os.path.isdir(export_dir):
                return False, "导出目录不存在", old_export_dir
            self.config.export_dir = export_dir
        
        if threshold_low is not None:
            self.config.threshold_low = threshold_low
        
        if threshold_high is not None:
            self.config.threshold_high = threshold_high
        
        self.storage.save_config(self.config)
        return True, "配置更新成功", self.config.export_dir

    def get_config(self):
        return self.config

    def export_records(self):
        export_dir = self.config.export_dir
        if not os.path.isdir(export_dir):
            return False, "导出目录不存在"
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        exported_files = []
        
        export_data = {
            "devices": [d.to_dict() for d in self.devices],
            "repair_records": [r.to_dict() for r in self.repair_records],
            "approval_records": [a.to_dict() for a in self.approval_records],
            "export_time": datetime.now().isoformat()
        }
        
        json_filename = f"export_{timestamp}.json"
        json_filepath = os.path.join(export_dir, json_filename)
        
        try:
            with open(json_filepath, "w", encoding="utf-8") as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            exported_files.append(json_filepath)
        except Exception as e:
            return False, f"JSON导出失败: {str(e)}"
        
        csv_filename = f"export_{timestamp}.csv"
        csv_filepath = os.path.join(export_dir, csv_filename)
        
        try:
            with open(csv_filepath, "w", encoding="utf-8-sig", newline='') as f:
                f.write("=== 设备状态 ===\n")
                f.write("设备ID,设备名称,当前状态,异常描述,创建时间,更新时间\n")
                for d in self.devices:
                    f.write(f"{d.device_id},{d.name},{d.status},{d.abnormal_desc},{d.create_time},{d.update_time}\n")
                
                f.write("\n=== 维修记录 ===\n")
                f.write("记录ID,设备ID,维修内容,维修人员,维修时间\n")
                for r in self.repair_records:
                    f.write(f"{r.record_id},{r.device_id},{r.repair_desc},{r.operator},{r.repair_time}\n")
                
                f.write("\n=== 审批记录 ===\n")
                f.write("记录ID,设备ID,审批类型,审批意见,审批人,审批时间\n")
                for a in self.approval_records:
                    f.write(f"{a.record_id},{a.device_id},{a.approval_type},{a.opinion},{a.approver},{a.approve_time}\n")
            exported_files.append(csv_filepath)
        except Exception as e:
            return False, f"CSV导出失败: {str(e)}"
        
        return True, f"记录已导出:\n1. {json_filepath}\n2. {csv_filepath}"
