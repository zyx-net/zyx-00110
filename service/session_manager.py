import os
import hashlib
import traceback
import json
from datetime import datetime
from model.device import ImportSession, SessionPreviewResult, ConflictDecision, SessionImportLog
from model.device import Device, RepairRecord, ApprovalRecord, SessionEventType, SessionPermission
from model.status import DeviceStatus
from service.backup_service import BackupService
from storage.json_storage import JSONStorage


class ImportSessionManager:
    def __init__(self, storage=None, device_service=None):
        self.storage = storage or JSONStorage()
        self.backup_service = BackupService(self.storage)
        self.device_service = device_service
    
    def get_all_sessions(self):
        return self.storage.load_all_sessions()
    
    def get_sessions_by_status(self, status):
        return self.storage.get_sessions_by_status(status)

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

    def _calculate_file_checksum(self, file_path):
        try:
            with open(file_path, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        except Exception:
            return None

    def check_active_session(self):
        return self.storage.load_active_session()

    def create_session(self, file_path, file_type, operator, is_supervisor, parsed_data, preview_result):
        existing_session = self.check_active_session()
        if existing_session:
            if existing_session.file_path == file_path and not existing_session.committed:
                existing_session.add_event(SessionEventType.SESSION_RESUMED, operator, {"resumed_from": existing_session.created_time})
                self.storage.save_session(existing_session)
                return existing_session, "发现未完成的会话，已为您恢复"
        
        session = ImportSession(
            file_path=file_path,
            file_type=file_type,
            operator=operator,
            is_supervisor=is_supervisor
        )
        session.status = ImportSession.STATUS_IN_PROGRESS
        session.preview_result = preview_result
        session.raw_data = parsed_data
        session.file_checksum = self._calculate_file_checksum(file_path)
        
        session.add_event(SessionEventType.SESSION_CREATED, operator, {
            "file_path": file_path,
            "file_type": file_type,
            "file_checksum": session.file_checksum
        })
        
        session.add_event(SessionEventType.PREVIEW_GENERATED, operator, {
            "total_new": preview_result.get_total_new(),
            "total_overwrite": preview_result.get_total_overwrite(),
            "total_conflict": preview_result.get_total_conflict(),
            "total_invalid": preview_result.get_total_invalid()
        })

        self.storage.save_session(session)
        return session, None

    def get_session(self, session_id):
        return self.storage.get_session(session_id)

    def resume_session(self, session_id=None, operator=None, is_supervisor=False):
        if session_id:
            session = self.storage.get_session(session_id)
        else:
            session = self.storage.load_active_session()

        if not session:
            return None, "没有找到未完成的会话"

        if not session.check_permission(operator, SessionPermission.PERM_VIEW, is_supervisor):
            return None, "没有权限查看此会话"

        if session.file_path and os.path.exists(session.file_path):
            current_checksum = self._calculate_file_checksum(session.file_path)
            if current_checksum != session.file_checksum:
                return None, f"文件已被修改（校验和不匹配），请重新选择文件"
        else:
            return None, "会话关联的文件已不存在"

        session.add_event(SessionEventType.SESSION_RESUMED, operator)
        self.storage.save_session(session)
        return session, None

    def resolve_conflict(self, session_id, record_id, record_type, row_data, decision, operator=None):
        session = self.storage.get_session(session_id)
        if not session:
            return False, "会话不存在"

        if decision not in [ConflictDecision.KEEP_LOCAL, ConflictDecision.OVERWRITE_LOCAL, ConflictDecision.SKIP]:
            return False, f"无效的决策: {decision}"

        session.set_conflict_resolution(record_id, record_type, row_data, decision)
        session.updated_time = datetime.now().isoformat()

        decision_map = {
            ConflictDecision.KEEP_LOCAL: "保留本地",
            ConflictDecision.OVERWRITE_LOCAL: "覆盖本地",
            ConflictDecision.SKIP: "跳过"
        }
        session.add_event(SessionEventType.CONFLICT_RESOLVED, operator, {
            "record_id": record_id,
            "record_type": record_type,
            "decision": decision_map.get(decision, decision)
        })

        if session.is_all_conflicts_resolved():
            session.status = ImportSession.STATUS_WAITING_CONFIRM

        self.storage.save_session(session)

        for r in session.conflict_resolutions:
            if r.record_id == record_id:
                return True, None
        return False, "决策保存失败"

    def resolve_conflicts_batch(self, session_id, resolutions, operator=None):
        session = self.storage.get_session(session_id)
        if not session:
            return False, "会话不存在", 0

        success_count = 0
        failed_records = []

        for item in resolutions:
            record_id = item.get('record_id')
            record_type = item.get('record_type')
            row_data = item.get('row_data')
            decision = item.get('decision')

            if decision not in [ConflictDecision.KEEP_LOCAL, ConflictDecision.OVERWRITE_LOCAL, ConflictDecision.SKIP]:
                failed_records.append(f"{record_id}: 无效决策 {decision}")
                continue

            session.set_conflict_resolution(record_id, record_type, row_data, decision)
            success_count += 1

        session.updated_time = datetime.now().isoformat()
        
        session.add_event(SessionEventType.CONFLICT_BATCH_RESOLVED, operator, {
            "resolved_count": success_count,
            "failed_count": len(failed_records)
        })

        if session.is_all_conflicts_resolved():
            session.status = ImportSession.STATUS_WAITING_CONFIRM

        self.storage.save_session(session)

        error_msg = "\n".join(failed_records) if failed_records else None
        return True, error_msg, success_count

    def get_conflicts_by_type(self, session, record_type):
        if not session or not session.preview_result:
            return []

        conflicts = []
        type_map = {
            "device": session.preview_result.devices,
            "repair": session.preview_result.repair_records,
            "approval": session.preview_result.approval_records
        }

        if record_type == "all":
            for category in ["devices", "repair_records", "approval_records"]:
                for row in session.preview_result.__dict__[category]["conflict"]:
                    data = row.row_data
                    record_id = data.get('device_id') or data.get('record_id')
                    resolution = session.get_conflict_resolution(record_id)
                    conflicts.append({
                        'record_id': record_id,
                        'record_type': category.replace('_', '').replace('records', ''),
                        'row_data': data,
                        'reason': row.reason,
                        'decision': resolution,
                        'decision_time': self._get_decision_time(session, record_id)
                    })
        else:
            category_key = type_map.get(record_type, {})
            if category_key:
                for row in category_key.get("conflict", []):
                    data = row.row_data
                    record_id = data.get('device_id') or data.get('record_id')
                    resolution = session.get_conflict_resolution(record_id)
                    conflicts.append({
                        'record_id': record_id,
                        'record_type': record_type,
                        'row_data': data,
                        'reason': row.reason,
                        'decision': resolution,
                        'decision_time': self._get_decision_time(session, record_id)
                    })

        return conflicts

    def _get_decision_time(self, session, record_id):
        for resolution in session.conflict_resolutions:
            if resolution.record_id == record_id:
                return resolution.decision_time
        return None

    def get_resolved_conflicts_summary(self, session):
        if not session:
            return {'total': 0, 'resolved': 0, 'unresolved': 0, 'by_type': {}}

        conflicts = self.get_conflicts_by_type(session, "all")

        summary = {
            'total': len(conflicts),
            'resolved': sum(1 for c in conflicts if c['decision'] is not None),
            'unresolved': sum(1 for c in conflicts if c['decision'] is None),
            'by_type': {
                'device': {'total': 0, 'resolved': 0},
                'repair': {'total': 0, 'resolved': 0},
                'approval': {'total': 0, 'resolved': 0}
            },
            'decisions': {
                'keep_local': 0,
                'overwrite_local': 0,
                'skip': 0
            }
        }

        for c in conflicts:
            rec_type = c['record_type'].lower()
            if rec_type in summary['by_type']:
                summary['by_type'][rec_type]['total'] += 1
                if c['decision']:
                    summary['by_type'][rec_type]['resolved'] += 1

            if c['decision'] == ConflictDecision.KEEP_LOCAL:
                summary['decisions']['keep_local'] += 1
            elif c['decision'] == ConflictDecision.OVERWRITE_LOCAL:
                summary['decisions']['overwrite_local'] += 1
            elif c['decision'] == ConflictDecision.SKIP:
                summary['decisions']['skip'] += 1

        return summary

    def validate_dependencies(self, session):
        errors = []
        
        imported_device_ids = set()
        for d in session.raw_data.get('devices', []):
            device_id = getattr(d, 'device_id', None) or (d.get('device_id') if hasattr(d, 'get') else None)
            if device_id:
                imported_device_ids.add(device_id)

        for record in session.raw_data.get('repair_records', []):
            record_id = getattr(record, 'record_id', None) or (record.get('record_id') if hasattr(record, 'get') else None)
            device_id = getattr(record, 'device_id', None) or (record.get('device_id') if hasattr(record, 'get') else None)
            
            if device_id and device_id not in imported_device_ids:
                current_devices = self._get_current_devices()
                current_device_ids = {d.device_id for d in current_devices}
                if device_id not in current_device_ids:
                    errors.append(f"维修记录 {record_id or '未知'} 关联的设备 {device_id} 不存在")

        for record in session.raw_data.get('approval_records', []):
            record_id = getattr(record, 'record_id', None) or (record.get('record_id') if hasattr(record, 'get') else None)
            device_id = getattr(record, 'device_id', None) or (record.get('device_id') if hasattr(record, 'get') else None)
            
            if device_id and device_id not in imported_device_ids:
                current_devices = self._get_current_devices()
                current_device_ids = {d.device_id for d in current_devices}
                if device_id not in current_device_ids:
                    errors.append(f"审批记录 {record_id or '未知'} 关联的设备 {device_id} 不存在")

        return errors

    def validate_required_fields(self, session):
        errors = []

        for device in session.raw_data.get('devices', []):
            device_id = getattr(device, 'device_id', None) or (device.get('device_id') if hasattr(device, 'get') else None)
            name = getattr(device, 'name', None) or (device.get('name') if hasattr(device, 'get') else None)
            status = getattr(device, 'status', None) or (device.get('status') if hasattr(device, 'get') else None)
            
            if not device_id:
                errors.append(f"设备: 设备ID缺失")
            if not name:
                errors.append(f"设备 {device_id or '未知'}: 名称缺失")
            if not status:
                errors.append(f"设备 {device_id or '未知'}: 状态缺失")
            elif status not in DeviceStatus.values():
                errors.append(f"设备 {device_id or '未知'}: 状态值 '{status}' 不合法")

        for record in session.raw_data.get('repair_records', []):
            record_id = getattr(record, 'record_id', None) or (record.get('record_id') if hasattr(record, 'get') else None)
            device_id = getattr(record, 'device_id', None) or (record.get('device_id') if hasattr(record, 'get') else None)
            repair_desc = getattr(record, 'repair_desc', None) or (record.get('repair_desc') if hasattr(record, 'get') else None)
            operator = getattr(record, 'operator', None) or (record.get('operator') if hasattr(record, 'get') else None)
            
            if not record_id:
                errors.append(f"维修记录: 记录ID缺失")
            if not device_id:
                errors.append(f"维修记录 {record_id or '未知'}: 设备ID缺失")
            if not repair_desc:
                errors.append(f"维修记录 {record_id or '未知'}: 维修内容缺失")
            if not operator:
                errors.append(f"维修记录 {record_id or '未知'}: 维修人员缺失")

        for record in session.raw_data.get('approval_records', []):
            record_id = getattr(record, 'record_id', None) or (record.get('record_id') if hasattr(record, 'get') else None)
            device_id = getattr(record, 'device_id', None) or (record.get('device_id') if hasattr(record, 'get') else None)
            approval_type = getattr(record, 'approval_type', None) or (record.get('approval_type') if hasattr(record, 'get') else None)
            approver = getattr(record, 'approver', None) or (record.get('approver') if hasattr(record, 'get') else None)
            
            if not record_id:
                errors.append(f"审批记录: 记录ID缺失")
            if not device_id:
                errors.append(f"审批记录 {record_id or '未知'}: 设备ID缺失")
            if not approval_type:
                errors.append(f"审批记录 {record_id or '未知'}: 审批类型缺失")
            if not approver:
                errors.append(f"审批记录 {record_id or '未知'}: 审批人缺失")

        return errors

    def _mark_session_failed(self, session, error_type, error_message, context=None, stack_trace=None):
        session.status = ImportSession.STATUS_FAILED
        session.end_time = datetime.now().isoformat()
        session.result_message = error_message
        session.add_error_snapshot(error_type, error_message, context, stack_trace)
        session.add_event(SessionEventType.COMMIT_FAILED, session.commit_operator or session.operator, {"error": error_message})
        self.storage.save_session(session)

    def _create_failed_import_log(self, session, operator, is_supervisor, error_type, error_message):
        log_id = f"IMP_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        error_log = SessionImportLog(
            log_id=log_id,
            session_id=session.session_id,
            import_time=datetime.now().isoformat(),
            operator=operator,
            is_supervisor=is_supervisor,
            total_rows=session.preview_result.get_total("devices") + 
                       session.preview_result.get_total("repair_records") + 
                       session.preview_result.get_total("approval_records") if session.preview_result else 0,
            new_rows=0,
            overwrite_rows=0,
            skipped_rows=0,
            conflict_resolved=len(session.conflict_resolutions),
            status="failed",
            message=error_message,
            details={
                'error_type': error_type,
                'error_message': error_message,
                'conflict_decisions': [self._format_conflict_decision(r) for r in session.conflict_resolutions],
                'snapshot_count': len(session.error_snapshots),
                'preview_summary': session.preview_result.to_dict() if session.preview_result else None
            }
        )
        self.storage.save_session_import_log(error_log)
        return log_id

    def commit_import(self, session, operator, is_supervisor):
        session = self.storage.get_session(session.session_id)
        if not session:
            return False, "会话不存在"

        session.commit_operator = operator
        session.add_event(SessionEventType.COMMIT_STARTED, operator)

        if not is_supervisor:
            self._mark_session_failed(session, "permission_denied", "权限不足：只有主管才能执行导入操作", {"operator": operator})
            self._create_failed_import_log(session, operator, is_supervisor, "permission_denied", "权限不足：只有主管才能执行导入操作")
            return False, "权限不足：只有主管才能执行导入操作"

        if operator != session.operator and not is_supervisor:
            self._mark_session_failed(session, "operator_mismatch", f"操作人不匹配，只有创建会话的主管或当前主管可以提交", {"operator": operator, "session_operator": session.operator})
            self._create_failed_import_log(session, operator, is_supervisor, "operator_mismatch", f"操作人不匹配，只有创建会话的主管或当前主管可以提交")
            return False, "操作人不匹配，只有创建会话的主管或当前主管可以提交"

        if not session.is_all_conflicts_resolved():
            unresolved = session.get_unresolved_conflicts_count()
            self._mark_session_failed(session, "unresolved_conflicts", f"还有 {unresolved} 个冲突项未决策，不能执行导入", {"unresolved_count": unresolved})
            self._create_failed_import_log(session, operator, is_supervisor, "unresolved_conflicts", f"还有 {unresolved} 个冲突项未决策，不能执行导入")
            return False, f"还有 {unresolved} 个冲突项未决策，不能执行导入"

        current_checksum = self._calculate_file_checksum(session.file_path)
        if current_checksum != session.file_checksum:
            self._mark_session_failed(session, "file_modified", "文件已被修改，不能执行导入", {"original_checksum": session.file_checksum, "current_checksum": current_checksum})
            self._create_failed_import_log(session, operator, is_supervisor, "file_modified", "文件已被修改，不能执行导入")
            return False, "文件已被修改，不能执行导入。请重新预览文件"

        session.add_event(SessionEventType.VALIDATION_STARTED, operator)

        dependency_errors = self.validate_dependencies(session)
        if dependency_errors:
            error_msg = f"依赖关系校验失败:\n" + "\n".join(f"- {e}" for e in dependency_errors)
            self._mark_session_failed(session, "dependency_validation_failed", error_msg, {"errors": dependency_errors})
            self._create_failed_import_log(session, operator, is_supervisor, "dependency_validation_failed", error_msg)
            return False, error_msg

        required_field_errors = self.validate_required_fields(session)
        if required_field_errors:
            error_msg = f"必填字段校验失败:\n" + "\n".join(f"- {e}" for e in required_field_errors)
            self._mark_session_failed(session, "required_field_validation_failed", error_msg, {"errors": required_field_errors})
            self._create_failed_import_log(session, operator, is_supervisor, "required_field_validation_failed", error_msg)
            return False, error_msg

        from service.device_service import SUPERVISORS
        for record in session.raw_data.get('approval_records', []):
            if record.get('approval_type') == '复机':
                approver = record.get('approver', '')
                if approver not in SUPERVISORS:
                    error_msg = f"审批人 '{approver}' 无复机审批权限"
                    self._mark_session_failed(session, "unauthorized_approval", error_msg, {"approver": approver, "record_id": record.get('record_id')})
                    self._create_failed_import_log(session, operator, is_supervisor, "unauthorized_approval", error_msg)
                    return False, error_msg

        session.add_event(SessionEventType.VALIDATION_PASSED, operator)

        log_id = f"IMP_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        success, backup_path, backup_info = self.backup_service.create_backup(log_id)
        if not success:
            error_msg = f"创建备份失败: {backup_info}"
            self._mark_session_failed(session, "backup_failed", error_msg)
            self._create_failed_import_log(session, operator, is_supervisor, "backup_failed", error_msg)
            return False, error_msg

        session.backup_path = backup_path

        try:
            current_devices = self._get_current_devices()
            current_device_map = {d.device_id: d for d in current_devices}

            current_repair_records = self._get_current_repair_records()
            current_repair_map = {r.record_id: r for r in current_repair_records}

            current_approval_records = self._get_current_approval_records()
            current_approval_map = {a.record_id: a for a in current_approval_records}

            stats = {
                'new_devices': 0,
                'overwrite_devices': 0,
                'skipped_devices': 0,
                'new_repairs': 0,
                'overwrite_repairs': 0,
                'skipped_repairs': 0,
                'new_approvals': 0,
                'overwrite_approvals': 0,
                'skipped_approvals': 0,
                'failed_records': []
            }

            for device_data in session.raw_data.get('devices', []):
                device = Device.from_dict(device_data)
                resolution = session.get_conflict_resolution(device.device_id)

                if resolution == ConflictDecision.SKIP:
                    stats['skipped_devices'] += 1
                    continue

                if resolution == ConflictDecision.KEEP_LOCAL:
                    stats['skipped_devices'] += 1
                    continue

                if device.device_id in current_device_map:
                    idx = current_devices.index(current_device_map[device.device_id])
                    current_devices[idx] = device
                    stats['overwrite_devices'] += 1
                else:
                    current_devices.append(device)
                    stats['new_devices'] += 1

            for record_data in session.raw_data.get('repair_records', []):
                record = RepairRecord.from_dict(record_data)
                resolution = session.get_conflict_resolution(record.record_id)

                if resolution == ConflictDecision.SKIP:
                    stats['skipped_repairs'] += 1
                    continue

                if resolution == ConflictDecision.KEEP_LOCAL:
                    stats['skipped_repairs'] += 1
                    continue

                if record.record_id in current_repair_map:
                    idx = current_repair_records.index(current_repair_map[record.record_id])
                    current_repair_records[idx] = record
                    stats['overwrite_repairs'] += 1
                else:
                    current_repair_records.append(record)
                    stats['new_repairs'] += 1

            for record_data in session.raw_data.get('approval_records', []):
                record = ApprovalRecord.from_dict(record_data)
                resolution = session.get_conflict_resolution(record.record_id)

                if resolution == ConflictDecision.SKIP:
                    stats['skipped_approvals'] += 1
                    continue

                if resolution == ConflictDecision.KEEP_LOCAL:
                    stats['skipped_approvals'] += 1
                    continue

                if record.record_id in current_approval_map:
                    idx = current_approval_records.index(current_approval_map[record.record_id])
                    current_approval_records[idx] = record
                    stats['overwrite_approvals'] += 1
                else:
                    current_approval_records.append(record)
                    stats['new_approvals'] += 1

            self.storage.save_devices(current_devices)
            self.storage.save_repair_records(current_repair_records)
            self.storage.save_approval_records(current_approval_records)

            if self.device_service:
                self.device_service.devices = current_devices
                self.device_service.repair_records = current_repair_records
                self.device_service.approval_records = current_approval_records

            session.status = ImportSession.STATUS_COMPLETED
            session.committed = True
            session.commit_time = datetime.now().isoformat()
            session.can_undo = True
            session.end_time = datetime.now().isoformat()
            session.result_message = self._generate_result_message(stats)
            
            session.add_event(SessionEventType.COMMIT_SUCCESS, operator, {
                "new_devices": stats['new_devices'],
                "overwrite_devices": stats['overwrite_devices'],
                "skipped_devices": stats['skipped_devices'],
                "new_repairs": stats['new_repairs'],
                "overwrite_repairs": stats['overwrite_repairs'],
                "skipped_repairs": stats['skipped_repairs'],
                "new_approvals": stats['new_approvals'],
                "overwrite_approvals": stats['overwrite_approvals'],
                "skipped_approvals": stats['skipped_approvals']
            })
            
            self.storage.save_session(session)

            import_log = SessionImportLog(
                log_id=log_id,
                session_id=session.session_id,
                import_time=session.commit_time,
                operator=operator,
                is_supervisor=is_supervisor,
                total_rows=stats['new_devices'] + stats['overwrite_devices'] + stats['skipped_devices'] +
                           stats['new_repairs'] + stats['overwrite_repairs'] + stats['skipped_repairs'] +
                           stats['new_approvals'] + stats['overwrite_approvals'] + stats['skipped_approvals'],
                new_rows=stats['new_devices'] + stats['new_repairs'] + stats['new_approvals'],
                overwrite_rows=stats['overwrite_devices'] + stats['overwrite_repairs'] + stats['overwrite_approvals'],
                skipped_rows=stats['skipped_devices'] + stats['skipped_repairs'] + stats['skipped_approvals'],
                conflict_resolved=len(session.conflict_resolutions),
                status="success",
                message=session.result_message,
                details={
                    'devices': {k: v for k, v in stats.items() if 'device' in k},
                    'repairs': {k: v for k, v in stats.items() if 'repair' in k},
                    'approvals': {k: v for k, v in stats.items() if 'approval' in k},
                    'conflict_decisions': [self._format_conflict_decision(r) for r in session.conflict_resolutions]
                }
            )
            self.storage.save_session_import_log(import_log)

            return True, f"导入成功！\n备份位置: {backup_path}\n{session.result_message}"

        except Exception as e:
            self._mark_session_failed(session, type(e).__name__, f"导入失败: {str(e)}", 
                                      {"operator": operator, "is_supervisor": is_supervisor},
                                      traceback.format_exc())
            self._create_failed_import_log(session, operator, is_supervisor, type(e).__name__, str(e))
            return False, f"导入过程中发生错误: {str(e)}"

    def _format_conflict_decision(self, resolution):
        decision_map = {
            ConflictDecision.KEEP_LOCAL: "保留本地",
            ConflictDecision.OVERWRITE_LOCAL: "覆盖本地",
            ConflictDecision.SKIP: "跳过"
        }
        return {
            'record_id': resolution.record_id,
            'record_type': resolution.record_type,
            'decision': decision_map.get(resolution.decision, resolution.decision),
            'decision_time': resolution.decision_time
        }

    def log_undo_result(self, session_id, success, message):
        log = SessionImportLog(
            log_id=f"UNDO_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            session_id=session_id,
            import_time=datetime.now().isoformat(),
            operator="system",
            is_supervisor=False,
            total_rows=0,
            new_rows=0,
            overwrite_rows=0,
            skipped_rows=0,
            conflict_resolved=0,
            status="undone" if success else "undo_failed",
            message=message,
            details={'undo_result': 'success' if success else 'failed'}
        )
        self.storage.save_session_import_log(log)
        return True

    def _generate_result_message(self, stats):
        parts = []
        total_new = stats['new_devices'] + stats['new_repairs'] + stats['new_approvals']
        total_overwrite = stats['overwrite_devices'] + stats['overwrite_repairs'] + stats['overwrite_approvals']
        total_skipped = stats['skipped_devices'] + stats['skipped_repairs'] + stats['skipped_approvals']

        if total_new > 0:
            parts.append(f"新增 {total_new} 条")
        if total_overwrite > 0:
            parts.append(f"覆盖 {total_overwrite} 条")
        if total_skipped > 0:
            parts.append(f"跳过 {total_skipped} 条")

        return ", ".join(parts) if parts else "无变更"

    def undo_import(self, session, operator=None, is_supervisor=False):
        session = self.storage.get_session(session.session_id) if hasattr(session, 'session_id') else self.storage.get_session(session)
        if not session:
            return False, "会话不存在"

        if not session.check_permission(operator, SessionPermission.PERM_UNDO, is_supervisor):
            return False, "没有权限撤销此会话"

        if not session.can_undo:
            return False, "此会话不支持撤销"

        if not session.backup_path or not os.path.exists(session.backup_path):
            return False, f"备份目录不存在: {session.backup_path}"

        session.add_event(SessionEventType.UNDO_STARTED, operator)
        
        try:
            for f in os.listdir(self.storage.data_dir):
                if f != 'backups' and f != 'rollback_state.json' and f != 'import_sessions.json' and f != 'session_import_logs.json':
                    file_path = os.path.join(self.storage.data_dir, f)
                    if os.path.isfile(file_path):
                        os.remove(file_path)

            for f in os.listdir(session.backup_path):
                src = os.path.join(session.backup_path, f)
                dst = os.path.join(self.storage.data_dir, f)
                if os.path.isfile(src):
                    import shutil
                    shutil.copy2(src, dst)

            if self.device_service:
                self.device_service.devices = self.storage.load_devices()
                self.device_service.repair_records = self.storage.load_repair_records()
                self.device_service.approval_records = self.storage.load_approval_records()

            session.can_undo = False
            session.end_time = datetime.now().isoformat()
            session.result_message = "已撤销"
            session.add_event(SessionEventType.UNDO_SUCCESS, operator)
            self.storage.save_session(session)

            self.log_undo_result(session.session_id, True, f"撤销成功，数据已恢复")

            return True, f"已撤销会话 {session.session_id} 的导入，数据已恢复"

        except Exception as e:
            session.add_error_snapshot("undo_failed", f"撤销失败: {str(e)}", stack_trace=traceback.format_exc())
            session.add_event(SessionEventType.UNDO_FAILED, operator, {"error": str(e)})
            self.storage.save_session(session)
            self.log_undo_result(session.session_id, False, f"撤销失败: {str(e)}")
            return False, f"撤销失败: {str(e)}"

    def cancel_session(self, session_id, operator=None):
        session = self.storage.get_session(session_id)
        if not session:
            return False, "会话不存在"

        if session.committed:
            return False, "已提交的会话不能取消"

        session.status = ImportSession.STATUS_CANCELLED
        session.end_time = datetime.now().isoformat()
        session.add_event(SessionEventType.SESSION_CANCELLED, operator)
        self.storage.save_session(session)
        return True, "会话已取消"

    def get_session_logs(self):
        return self.storage.load_session_import_logs()

    def export_session_log(self, log, file_path):
        return self.storage.export_session_log(log, file_path)

    def get_session_history(self, operator=None, start_time=None, end_time=None, limit=50):
        if operator:
            return self.storage.get_sessions_by_time_range(start_time, end_time, operator)[:limit]
        return self.storage.get_session_history(limit=limit)

    def get_failed_sessions(self):
        return self.storage.get_failed_sessions()

    def get_failed_session_snapshot(self, session_id, file_path):
        return self.storage.export_failed_session_snapshot(session_id, file_path)

    def get_failed_sessions_with_filter(self, operator=None, error_type=None, start_time=None, end_time=None):
        failed_sessions = self.storage.get_failed_sessions()
        
        if operator:
            failed_sessions = [s for s in failed_sessions if s.operator == operator]
        
        if error_type:
            failed_sessions = [s for s in failed_sessions if any(snapshot.error_type == error_type for snapshot in s.error_snapshots)]
        
        if start_time:
            failed_sessions = [s for s in failed_sessions if s.created_time >= start_time]
        
        if end_time:
            failed_sessions = [s for s in failed_sessions if s.created_time <= end_time]
        
        return sorted(failed_sessions, key=lambda x: x.created_time, reverse=True)

    def get_failed_session_count(self, operator=None, error_type=None):
        failed_sessions = self.get_failed_sessions_with_filter(operator=operator, error_type=error_type)
        return len(failed_sessions)

    def get_sessions_by_status(self, status, operator=None):
        sessions = self.storage.get_sessions_by_status(status)
        if operator:
            sessions = [s for s in sessions if s.operator == operator]
        return sorted(sessions, key=lambda x: x.created_time, reverse=True)

    def get_sessions_with_errors(self):
        return self.storage.get_sessions_with_errors()

    def get_failed_import_logs(self, session_id=None, operator=None):
        logs = self.storage.load_session_import_logs()
        failed_logs = [log for log in logs if log.status == "failed"]
        
        if session_id:
            failed_logs = [log for log in failed_logs if log.session_id == session_id]
        
        if operator:
            failed_logs = [log for log in failed_logs if log.operator == operator]
        
        return sorted(failed_logs, key=lambda x: x.import_time, reverse=True)

    def get_session_event_chain(self, session_id, operator=None, is_supervisor=False):
        session = self.storage.get_session(session_id)
        if not session:
            return None, "会话不存在"

        if not session.check_permission(operator, SessionPermission.PERM_VIEW, is_supervisor):
            return None, "没有权限查看此会话"

        return session.get_event_chain(), None

    def check_session_permission(self, session_id, user, perm_type, is_supervisor=False):
        session = self.storage.get_session(session_id)
        if not session:
            return False
        return session.check_permission(user, perm_type, is_supervisor)

    def grant_session_permission(self, session_id, user, perm_type, operator=None, is_supervisor=False):
        session = self.storage.get_session(session_id)
        if not session:
            return False, "会话不存在"

        if not session.check_permission(operator, SessionPermission.PERM_UNDO, is_supervisor):
            return False, "没有权限修改此会话的权限"

        session.grant_permission(user, perm_type)
        self.storage.save_session(session)
        return True, f"已授予 {user} {perm_type} 权限"

    def revoke_session_permission(self, session_id, user, perm_type, operator=None, is_supervisor=False):
        session = self.storage.get_session(session_id)
        if not session:
            return False, "会话不存在"

        if not session.check_permission(operator, SessionPermission.PERM_UNDO, is_supervisor):
            return False, "没有权限修改此会话的权限"

        session.revoke_permission(user, perm_type)
        self.storage.save_session(session)
        return True, f"已撤销 {user} 的 {perm_type} 权限"

    def verify_file_integrity(self, session_id):
        session = self.storage.get_session(session_id)
        if not session:
            return False, "会话不存在", None

        if not session.file_path or not os.path.exists(session.file_path):
            return False, "文件不存在", None

        current_checksum = self._calculate_file_checksum(session.file_path)
        original_checksum = session.file_checksum

        if current_checksum == original_checksum:
            return True, "文件完整，未被修改", {"checksum": current_checksum, "status": "unchanged"}
        else:
            return False, "文件已被修改", {"original_checksum": original_checksum, "current_checksum": current_checksum, "status": "modified"}

    def revalidate_session(self, session_id):
        session = self.storage.get_session(session_id)
        if not session:
            return False, "会话不存在"

        dependency_errors = self.validate_dependencies(session)
        required_field_errors = self.validate_required_fields(session)
        
        all_errors = dependency_errors + required_field_errors
        
        if not all_errors:
            session.add_event(SessionEventType.VALIDATION_PASSED, details={"revalidation": True})
        else:
            session.add_event(SessionEventType.VALIDATION_FAILED, details={"revalidation": True, "errors": all_errors})
        
        self.storage.save_session(session)
        return len(all_errors) == 0, all_errors
    
    def get_user_sessions(self, user, is_supervisor=False):
        all_sessions = self.storage.load_all_sessions()
        visible_sessions = []
        for session in all_sessions:
            if session.check_permission(user, SessionPermission.PERM_VIEW, is_supervisor):
                visible_sessions.append(session)
        return sorted(visible_sessions, key=lambda x: x.created_time, reverse=True)
    
    def get_failed_sessions_for_user(self, user, is_supervisor=False):
        all_sessions = self.storage.get_failed_sessions()
        visible_sessions = []
        for session in all_sessions:
            if session.check_permission(user, SessionPermission.PERM_VIEW, is_supervisor):
                visible_sessions.append(session)
        return sorted(visible_sessions, key=lambda x: x.created_time, reverse=True)
    
    def export_failed_session_snapshot(self, session_id, file_path, user, is_supervisor=False):
        session = self.storage.get_session(session_id)
        if not session:
            return False, "会话不存在"
        
        if not session.check_permission(user, SessionPermission.PERM_EXPORT, is_supervisor):
            return False, "没有权限导出此会话"
        
        if not session.has_error_snapshots():
            return False, "会话没有错误快照"
        
        return self.storage.export_session_snapshot(session, file_path)
    
    def delete_session(self, session_id, user, is_supervisor=False):
        session = self.storage.get_session(session_id)
        if not session:
            return False, "会话不存在"
        
        if session.committed and session.can_undo:
            return False, "已提交且可撤销的会话不能删除，请先撤销"
        
        if not session.check_permission(user, SessionPermission.PERM_UNDO, is_supervisor):
            return False, "没有权限删除此会话"
        
        success = self.storage.delete_session(session_id)
        if success:
            return True, "会话已删除"
        return False, "删除失败"
    
    def get_session_summary(self, session_id, user, is_supervisor=False):
        session = self.storage.get_session(session_id)
        if not session:
            return None, "会话不存在"
        
        if not session.check_permission(user, SessionPermission.PERM_VIEW, is_supervisor):
            return None, "没有权限查看此会话"
        
        summary = {
            "session_id": session.session_id,
            "file_path": session.file_path,
            "file_type": session.file_type,
            "operator": session.operator,
            "is_supervisor": session.is_supervisor,
            "status": session.status,
            "created_time": session.created_time,
            "updated_time": session.updated_time,
            "end_time": session.end_time,
            "committed": session.committed,
            "can_undo": session.can_undo,
            "result_message": session.result_message,
            "has_errors": session.has_error_snapshots(),
            "error_count": len(session.error_snapshots),
            "event_count": len(session.events),
            "conflict_count": session.get_unresolved_conflicts_count() if session.preview_result else 0
        }
        
        if session.preview_result:
            summary["preview_summary"] = {
                "devices": {k: len(v) for k, v in session.preview_result.devices.items()},
                "repair_records": {k: len(v) for k, v in session.preview_result.repair_records.items()},
                "approval_records": {k: len(v) for k, v in session.preview_result.approval_records.items()}
            }
        
        return summary, None

    def export_failed_sessions_report(self, output_path, user, is_supervisor=False, filter_params=None):
        filter_params = filter_params or {}
        failed_sessions = self.get_failed_sessions_with_filter(**filter_params)
        
        visible_sessions = []
        for session in failed_sessions:
            if session.check_permission(user, SessionPermission.PERM_VIEW, is_supervisor):
                visible_sessions.append(session)
        
        report = {
            "report_generated_time": datetime.now().isoformat(),
            "filter_params": filter_params,
            "total_failed_sessions": len(visible_sessions),
            "sessions": []
        }
        
        for session in visible_sessions:
            session_data = {
                "session_id": session.session_id,
                "file_path": session.file_path,
                "file_type": session.file_type,
                "operator": session.operator,
                "created_time": session.created_time,
                "end_time": session.end_time,
                "status": session.status,
                "result_message": session.result_message,
                "conflict_resolutions": [self._format_conflict_decision(r) for r in session.conflict_resolutions],
                "error_snapshots": [snapshot.to_dict() for snapshot in session.error_snapshots],
                "events": [event.to_dict() for event in session.events],
                "preview_summary": None,
                "raw_data_sample": None
            }
            
            if session.preview_result:
                session_data["preview_summary"] = {
                    "devices": {k: len(v) for k, v in session.preview_result.devices.items()},
                    "repair_records": {k: len(v) for k, v in session.preview_result.repair_records.items()},
                    "approval_records": {k: len(v) for k, v in session.preview_result.approval_records.items()}
                }
            
            if session.raw_data:
                session_data["raw_data_sample"] = {
                    "devices_count": len(session.raw_data.get('devices', [])),
                    "repair_records_count": len(session.raw_data.get('repair_records', [])),
                    "approval_records_count": len(session.raw_data.get('approval_records', []))
                }
            
            report["sessions"].append(session_data)
        
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            return True, None
        except Exception as e:
            return False, str(e)

    def export_failed_session_detailed(self, session_id, output_path, user, is_supervisor=False):
        session = self.storage.get_session(session_id)
        if not session:
            return False, "会话不存在"
        
        if not session.check_permission(user, SessionPermission.PERM_EXPORT, is_supervisor):
            return False, "没有权限导出此会话"
        
        detailed_export = {
            "export_time": datetime.now().isoformat(),
            "session_info": {
                "session_id": session.session_id,
                "file_path": session.file_path,
                "file_type": session.file_type,
                "operator": session.operator,
                "is_supervisor": session.is_supervisor,
                "created_time": session.created_time,
                "updated_time": session.updated_time,
                "end_time": session.end_time,
                "status": session.status,
                "committed": session.committed,
                "commit_time": session.commit_time,
                "commit_operator": session.commit_operator,
                "result_message": session.result_message,
                "can_undo": session.can_undo,
                "file_checksum": session.file_checksum,
                "backup_path": session.backup_path
            },
            "event_chain": [event.to_dict() for event in session.events],
            "error_snapshots": [snapshot.to_dict() for snapshot in session.error_snapshots],
            "conflict_resolutions": [resolution.to_dict() for resolution in session.conflict_resolutions],
            "preview_result": session.preview_result.to_dict() if session.preview_result else None,
            "raw_data": session.raw_data,
            "permission_info": session.permission.to_dict() if session.permission else None
        }
        
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(detailed_export, f, indent=2, ensure_ascii=False)
            return True, None
        except Exception as e:
            return False, str(e)
