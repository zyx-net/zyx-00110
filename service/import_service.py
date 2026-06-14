import os
import json
import csv
from datetime import datetime
from model.device import Device, RepairRecord, ApprovalRecord, ImportLog, PreviewResult
from model.device import SessionPreviewResult
from model.status import DeviceStatus
from storage.json_storage import JSONStorage
from service.backup_service import BackupService
from service.device_service import SUPERVISORS


class ImportService:
    def __init__(self, storage=None, device_service=None):
        self.storage = storage or JSONStorage()
        self.backup_service = BackupService(self.storage)
        self.device_service = device_service

    def _get_current_devices(self):
        if self.device_service:
            return self.device_service.devices
        return self.storage.load_devices()

    def _get_current_repair_records(self):
        if self.device_service:
            return self.device_service.repair_records
        return self.storage.load_repair_records()

    def _get_current_approval_records(self):
        if self.device_service:
            return self.device_service.approval_records
        return self.storage.load_approval_records()

    def detect_file_type(self, file_path):
        if not os.path.exists(file_path):
            return None, "文件不存在"
        
        ext = os.path.splitext(file_path)[1].lower()
        if ext == '.json':
            return 'json', None
        elif ext == '.csv':
            return 'csv', None
        else:
            return None, f"不支持的文件类型: {ext}"

    def parse_json_file(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            devices = []
            repair_records = []
            approval_records = []
            parse_errors = []
            
            if isinstance(data, dict):
                if 'devices' in data:
                    for idx, d in enumerate(data['devices']):
                        try:
                            if not d.get('device_id'):
                                parse_errors.append(f"设备第{idx+1}行: 设备ID缺失")
                                continue
                            if not d.get('name'):
                                parse_errors.append(f"设备第{idx+1}行: 设备名称缺失")
                                continue
                            if not d.get('status'):
                                parse_errors.append(f"设备第{idx+1}行: 设备状态缺失")
                                continue
                            devices.append(Device.from_dict(d))
                        except Exception as e:
                            parse_errors.append(f"设备第{idx+1}行: 解析失败 - {str(e)}")
                
                if 'repair_records' in data:
                    for idx, r in enumerate(data['repair_records']):
                        try:
                            if not r.get('record_id'):
                                parse_errors.append(f"维修记录第{idx+1}行: 记录ID缺失")
                                continue
                            if not r.get('device_id'):
                                parse_errors.append(f"维修记录第{idx+1}行: 设备ID缺失")
                                continue
                            if not r.get('repair_desc'):
                                parse_errors.append(f"维修记录第{idx+1}行: 维修内容缺失")
                                continue
                            if not r.get('operator'):
                                parse_errors.append(f"维修记录第{idx+1}行: 维修人员缺失")
                                continue
                            repair_records.append(RepairRecord.from_dict(r))
                        except Exception as e:
                            parse_errors.append(f"维修记录第{idx+1}行: 解析失败 - {str(e)}")
                
                if 'approval_records' in data:
                    for idx, a in enumerate(data['approval_records']):
                        try:
                            if not a.get('record_id'):
                                parse_errors.append(f"审批记录第{idx+1}行: 记录ID缺失")
                                continue
                            if not a.get('device_id'):
                                parse_errors.append(f"审批记录第{idx+1}行: 设备ID缺失")
                                continue
                            if not a.get('approval_type'):
                                parse_errors.append(f"审批记录第{idx+1}行: 审批类型缺失")
                                continue
                            if not a.get('approver'):
                                parse_errors.append(f"审批记录第{idx+1}行: 审批人缺失")
                                continue
                            approval_records.append(ApprovalRecord.from_dict(a))
                        except Exception as e:
                            parse_errors.append(f"审批记录第{idx+1}行: 解析失败 - {str(e)}")
            elif isinstance(data, list):
                for idx, item in enumerate(data):
                    try:
                        if 'device_id' in item and 'name' in item:
                            if not item.get('device_id'):
                                parse_errors.append(f"数据第{idx+1}行: 设备ID缺失")
                                continue
                            if not item.get('name'):
                                parse_errors.append(f"数据第{idx+1}行: 设备名称缺失")
                                continue
                            devices.append(Device.from_dict(item))
                    except Exception as e:
                        parse_errors.append(f"数据第{idx+1}行: 解析失败 - {str(e)}")
            
            result = {
                'devices': devices,
                'repair_records': repair_records,
                'approval_records': approval_records
            }
            
            if parse_errors:
                return result, "\n".join(parse_errors)
            return result, None
            
        except json.JSONDecodeError as e:
            return None, f"JSON格式错误: {str(e)}"
        except Exception as e:
            return None, f"读取文件失败: {str(e)}"

    def parse_csv_file(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                content = f.read()
            
            devices = []
            repair_records = []
            approval_records = []
            parse_errors = []
            
            sections = content.split('=== ')
            line_num = 0
            
            for section in sections:
                if section.startswith('设备状态'):
                    lines = section.split('\n')
                    for idx, line in enumerate(lines[2:]):
                        line_num += 1
                        line = line.strip()
                        if line:
                            parts = line.split(',')
                            try:
                                if len(parts) < 2:
                                    parse_errors.append(f"第{line_num}行: 设备数据不完整，至少需要设备ID和名称")
                                    continue
                                if not parts[0].strip():
                                    parse_errors.append(f"第{line_num}行: 设备ID缺失")
                                    continue
                                if not parts[1].strip():
                                    parse_errors.append(f"第{line_num}行: 设备名称缺失")
                                    continue
                                
                                device = Device(
                                    device_id=parts[0].strip(),
                                    name=parts[1].strip(),
                                    status=parts[2].strip() if len(parts) > 2 else DeviceStatus.NORMAL.value,
                                    abnormal_desc=parts[3].strip() if len(parts) > 3 else "",
                                    create_time=parts[4].strip() if len(parts) > 4 else None,
                                    update_time=parts[5].strip() if len(parts) > 5 else None
                                )
                                devices.append(device)
                            except Exception as e:
                                parse_errors.append(f"第{line_num}行: 设备数据解析失败 - {str(e)}")
                                
                elif section.startswith('维修记录'):
                    lines = section.split('\n')
                    for idx, line in enumerate(lines[2:]):
                        line_num += 1
                        line = line.strip()
                        if line:
                            parts = line.split(',')
                            try:
                                if len(parts) < 4:
                                    parse_errors.append(f"第{line_num}行: 维修记录不完整，至少需要记录ID、设备ID、维修内容和维修人员")
                                    continue
                                if not parts[0].strip():
                                    parse_errors.append(f"第{line_num}行: 维修记录ID缺失")
                                    continue
                                if not parts[1].strip():
                                    parse_errors.append(f"第{line_num}行: 维修记录设备ID缺失")
                                    continue
                                if not parts[2].strip():
                                    parse_errors.append(f"第{line_num}行: 维修内容缺失")
                                    continue
                                if not parts[3].strip():
                                    parse_errors.append(f"第{line_num}行: 维修人员缺失")
                                    continue
                                
                                repair_records.append(RepairRecord(
                                    record_id=parts[0].strip(),
                                    device_id=parts[1].strip(),
                                    repair_desc=parts[2].strip(),
                                    operator=parts[3].strip(),
                                    repair_time=parts[4].strip() if len(parts) > 4 else None
                                ))
                            except Exception as e:
                                parse_errors.append(f"第{line_num}行: 维修记录解析失败 - {str(e)}")
                                
                elif section.startswith('审批记录'):
                    lines = section.split('\n')
                    for idx, line in enumerate(lines[2:]):
                        line_num += 1
                        line = line.strip()
                        if line:
                            parts = line.split(',')
                            try:
                                if len(parts) < 5:
                                    parse_errors.append(f"第{line_num}行: 审批记录不完整，至少需要记录ID、设备ID、审批类型、审批意见和审批人")
                                    continue
                                if not parts[0].strip():
                                    parse_errors.append(f"第{line_num}行: 审批记录ID缺失")
                                    continue
                                if not parts[1].strip():
                                    parse_errors.append(f"第{line_num}行: 审批记录设备ID缺失")
                                    continue
                                if not parts[2].strip():
                                    parse_errors.append(f"第{line_num}行: 审批类型缺失")
                                    continue
                                if not parts[4].strip():
                                    parse_errors.append(f"第{line_num}行: 审批人缺失")
                                    continue
                                
                                approval_records.append(ApprovalRecord(
                                    record_id=parts[0].strip(),
                                    device_id=parts[1].strip(),
                                    approval_type=parts[2].strip(),
                                    opinion=parts[3].strip(),
                                    approver=parts[4].strip(),
                                    approve_time=parts[5].strip() if len(parts) > 5 else None
                                ))
                            except Exception as e:
                                parse_errors.append(f"第{line_num}行: 审批记录解析失败 - {str(e)}")
            
            result = {
                'devices': devices,
                'repair_records': repair_records,
                'approval_records': approval_records
            }
            
            if parse_errors:
                return result, "\n".join(parse_errors)
            return result, None
            
        except Exception as e:
            return None, f"CSV解析错误: {str(e)}"

    def validate_device(self, device, existing_devices, existing_repair_records):
        errors = []
        
        if not device.device_id:
            errors.append("设备ID缺失")
        if not device.name:
            errors.append("设备名称缺失")
        
        valid_statuses = DeviceStatus.values()
        if device.status not in valid_statuses:
            errors.append(f"状态不合法: '{device.status}'，有效状态: {', '.join(valid_statuses)}")
        
        return errors

    def validate_repair_record(self, record, imported_devices):
        errors = []
        
        if not record.record_id:
            errors.append("记录ID缺失")
        if not record.device_id:
            errors.append("设备ID缺失")
        if not record.repair_desc:
            errors.append("维修内容缺失")
        if not record.operator:
            errors.append("维修人员缺失")
        
        device_ids = [d.device_id for d in imported_devices]
        if record.device_id and record.device_id not in device_ids:
            errors.append(f"关联设备不存在: {record.device_id}")
        
        return errors

    def validate_approval_record(self, record, imported_devices):
        errors = []
        
        if not record.record_id:
            errors.append("记录ID缺失")
        if not record.device_id:
            errors.append("设备ID缺失")
        if not record.approval_type:
            errors.append("审批类型缺失")
        if not record.approver:
            errors.append("审批人缺失")
        
        if record.approval_type == "复机" and record.approver not in SUPERVISORS:
            errors.append(f"审批人'{record.approver}'无复机审批权限，主管包括: {', '.join(sorted(SUPERVISORS))}")
        
        device_ids = [d.device_id for d in imported_devices]
        if record.device_id and record.device_id not in device_ids:
            errors.append(f"关联设备不存在: {record.device_id}")
        
        return errors

    def preview_import(self, file_path, operator, is_supervisor):
        file_type, error = self.detect_file_type(file_path)
        if error:
            return None, error

        if file_type == 'json':
            data, parse_error = self.parse_json_file(file_path)
        else:
            data, parse_error = self.parse_csv_file(file_path)

        if data is None:
            return None, parse_error

        preview_result = PreviewResult()

        current_devices = self._get_current_devices()
        current_device_ids = {d.device_id for d in current_devices}

        current_repair_records = self._get_current_repair_records()
        current_repair_ids = {r.record_id for r in current_repair_records}

        current_approval_records = self._get_current_approval_records()
        current_approval_ids = {a.record_id for a in current_approval_records}

        imported_device_ids = set()

        if parse_error:
            preview_result.add_invalid({'_parse_error': parse_error}, f"解析警告: {parse_error}")

        for device in data['devices']:
            validation_errors = self.validate_device(device, current_devices, current_repair_records)

            if validation_errors:
                preview_result.add_invalid(device.to_dict(), "; ".join(validation_errors))
            elif device.device_id in current_device_ids:
                preview_result.add_overwrite(device.to_dict())
            elif device.device_id in imported_device_ids:
                preview_result.add_conflict(device.to_dict(), f"设备编号重复: {device.device_id}")
            else:
                preview_result.add_new(device.to_dict())
                imported_device_ids.add(device.device_id)

        for record in data['repair_records']:
            validation_errors = self.validate_repair_record(record, data['devices'])

            if validation_errors:
                preview_result.add_invalid(record.to_dict(), "; ".join(validation_errors))
            elif record.record_id in current_repair_ids:
                preview_result.add_overwrite(record.to_dict())
            else:
                preview_result.add_new(record.to_dict())

        for record in data['approval_records']:
            validation_errors = self.validate_approval_record(record, data['devices'])

            if validation_errors:
                preview_result.add_invalid(record.to_dict(), "; ".join(validation_errors))
            elif record.record_id in current_approval_ids:
                preview_result.add_overwrite(record.to_dict())
            else:
                preview_result.add_new(record.to_dict())

        return {
            'preview': preview_result,
            'file_type': file_type,
            'operator': operator,
            'is_supervisor': is_supervisor,
            'data': data,
            'parse_error': parse_error
        }, None

    def preview_import_session(self, file_path, operator, is_supervisor):
        file_type, error = self.detect_file_type(file_path)
        if error:
            return None, None, error

        if file_type == 'json':
            data, parse_error = self.parse_json_file(file_path)
        else:
            data, parse_error = self.parse_csv_file(file_path)

        if data is None:
            return None, None, parse_error

        preview_result = SessionPreviewResult()

        current_devices = self._get_current_devices()
        current_device_ids = {d.device_id for d in current_devices}
        current_device_map = {d.device_id: d for d in current_devices}

        current_repair_records = self._get_current_repair_records()
        current_repair_ids = {r.record_id for r in current_repair_records}
        current_repair_map = {r.record_id: r for r in current_repair_records}

        current_approval_records = self._get_current_approval_records()
        current_approval_ids = {a.record_id for a in current_approval_records}
        current_approval_map = {a.record_id: a for a in current_approval_records}

        imported_device_ids = set()

        if parse_error:
            preview_result.add_device_invalid({'_parse_error': parse_error}, f"解析警告: {parse_error}")

        for device in data['devices']:
            validation_errors = self.validate_device(device, current_devices, current_repair_records)

            if validation_errors:
                preview_result.add_device_invalid(device.to_dict(), "; ".join(validation_errors))
            elif device.device_id in current_device_ids:
                preview_result.add_device_conflict(device.to_dict(), f"设备编号已存在本地记录: {device.device_id}")
            elif device.device_id in imported_device_ids:
                preview_result.add_device_conflict(device.to_dict(), f"设备编号重复: {device.device_id}")
            else:
                preview_result.add_device_new(device.to_dict())
                imported_device_ids.add(device.device_id)

        for record in data['repair_records']:
            validation_errors = self.validate_repair_record(record, data['devices'])

            if validation_errors:
                preview_result.add_repair_invalid(record.to_dict(), "; ".join(validation_errors))
            elif record.record_id in current_repair_ids:
                preview_result.add_repair_conflict(record.to_dict(), f"维修记录ID已存在本地记录: {record.record_id}")
            else:
                preview_result.add_repair_new(record.to_dict())

        for record in data['approval_records']:
            validation_errors = self.validate_approval_record(record, data['devices'])

            if validation_errors:
                preview_result.add_approval_invalid(record.to_dict(), "; ".join(validation_errors))
            elif record.record_id in current_approval_ids:
                preview_result.add_approval_conflict(record.to_dict(), f"审批记录ID已存在本地记录: {record.record_id}")
            else:
                preview_result.add_approval_new(record.to_dict())

        raw_data = {
            'devices': [d.to_dict() for d in data['devices']],
            'repair_records': [r.to_dict() for r in data['repair_records']],
            'approval_records': [a.to_dict() for a in data['approval_records']]
        }

        return preview_result, raw_data, None

    def execute_import(self, preview_info, skip_conflicts=True):
        if not preview_info['is_supervisor']:
            return False, "权限不足：只有主管才能执行导入操作"
        
        preview = preview_info['preview']
        data = preview_info['data']
        
        if preview.invalid_rows and not skip_conflicts:
            invalid_details = "\n".join([f"- {row.reason}" for row in preview.invalid_rows])
            return False, f"存在 {len(preview.invalid_rows)} 条无效记录，请先修正后再导入:\n{invalid_details}"
        
        log_id = f"IMP_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        success, backup_path, backup_info = self.backup_service.create_backup(log_id)
        if not success:
            return False, f"创建备份失败: {backup_info}"
        
        try:
            current_devices = self._get_current_devices()
            current_device_map = {d.device_id: d for d in current_devices}
            
            current_repair_records = self._get_current_repair_records()
            current_repair_map = {r.record_id: r for r in current_repair_records}
            
            current_approval_records = self._get_current_approval_records()
            current_approval_map = {a.record_id: a for a in current_approval_records}
            
            new_devices = 0
            overwrite_devices = 0
            
            new_repairs = 0
            overwrite_repairs = 0
            
            new_approvals = 0
            overwrite_approvals = 0
            
            failed_records = []
            
            for device in data['devices']:
                validation_errors = self.validate_device(device, current_devices, current_repair_records)
                if validation_errors:
                    failed_records.append(f"设备 {device.device_id or '未知'}: {'; '.join(validation_errors)}")
                    continue
                
                if device.device_id in current_device_map:
                    idx = current_devices.index(current_device_map[device.device_id])
                    current_devices[idx] = device
                    overwrite_devices += 1
                else:
                    current_devices.append(device)
                    new_devices += 1
            
            for record in data['repair_records']:
                validation_errors = self.validate_repair_record(record, data['devices'])
                if validation_errors:
                    failed_records.append(f"维修记录 {record.record_id or '未知'}: {'; '.join(validation_errors)}")
                    continue
                
                if record.record_id in current_repair_map:
                    idx = current_repair_records.index(current_repair_map[record.record_id])
                    current_repair_records[idx] = record
                    overwrite_repairs += 1
                else:
                    current_repair_records.append(record)
                    new_repairs += 1
            
            for record in data['approval_records']:
                validation_errors = self.validate_approval_record(record, data['devices'])
                if validation_errors:
                    failed_records.append(f"审批记录 {record.record_id or '未知'}: {'; '.join(validation_errors)}")
                    continue
                
                if record.record_id in current_approval_map:
                    idx = current_approval_records.index(current_approval_map[record.record_id])
                    current_approval_records[idx] = record
                    overwrite_approvals += 1
                else:
                    current_approval_records.append(record)
                    new_approvals += 1
            
            if failed_records:
                self.backup_service.rollback()
                error_msg = "\n".join(failed_records)
                return False, f"导入失败，已回滚数据。以下记录未通过校验:\n{error_msg}"
            
            self.storage.save_devices(current_devices)
            self.storage.save_repair_records(current_repair_records)
            self.storage.save_approval_records(current_approval_records)
            
            if self.device_service:
                self.device_service.devices = current_devices
                self.device_service.repair_records = current_repair_records
                self.device_service.approval_records = current_approval_records
            
            import_log = ImportLog(
                log_id=log_id,
                import_time=datetime.now().isoformat(),
                file_path=preview_info.get('file_path', ''),
                file_type=preview_info['file_type'],
                operator=preview_info['operator'],
                is_supervisor=preview_info['is_supervisor'],
                total_rows=len(data['devices']) + len(data['repair_records']) + len(data['approval_records']),
                new_rows=new_devices + new_repairs + new_approvals,
                overwrite_rows=overwrite_devices + overwrite_repairs + overwrite_approvals,
                conflict_rows=0,
                invalid_rows=len(failed_records),
                status="success",
                message=f"导入成功：新增 {new_devices + new_repairs + new_approvals} 条，覆盖 {overwrite_devices + overwrite_repairs + overwrite_approvals} 条"
            )
            self.storage.add_import_log(import_log)
            
            return True, f"导入成功！\n备份位置: {backup_path}\n{import_log.message}"
            
        except Exception as e:
            return False, f"导入过程中发生错误: {str(e)}"

    def get_import_logs(self):
        return self.storage.load_import_logs()

    def can_rollback(self):
        return self.backup_service.can_rollback()

    def get_rollback_info(self):
        return self.backup_service.get_rollback_info()

    def rollback(self):
        return self.backup_service.rollback()
