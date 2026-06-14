import os
import hashlib
from datetime import datetime
from model.device import ImportSession, SessionPreviewResult, ConflictDecision, SessionImportLog
from model.device import Device, RepairRecord, ApprovalRecord
from model.status import DeviceStatus
from service.backup_service import BackupService
from storage.json_storage import JSONStorage


class ImportSessionManager:
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

        self.storage.save_session(session)
        return session, None

    def get_session(self, session_id):
        return self.storage.get_session(session_id)

    def resume_session(self, session_id=None):
        if session_id:
            session = self.storage.get_session(session_id)
        else:
            session = self.storage.load_active_session()

        if not session:
            return None, "没有找到未完成的会话"

        if session.file_path and os.path.exists(session.file_path):
            current_checksum = self._calculate_file_checksum(session.file_path)
            if current_checksum != session.file_checksum:
                return None, f"文件已被修改（校验和不匹配），请重新选择文件"
        else:
            return None, "会话关联的文件已不存在"

        return session, None

    def resolve_conflict(self, session_id, record_id, record_type, row_data, decision):
        session = self.storage.get_session(session_id)
        if not session:
            return False, "会话不存在"

        if decision not in [ConflictDecision.KEEP_LOCAL, ConflictDecision.OVERWRITE_LOCAL, ConflictDecision.SKIP]:
            return False, f"无效的决策: {decision}"

        session.set_conflict_resolution(record_id, record_type, row_data, decision)
        session.updated_time = datetime.now().isoformat()

        if session.is_all_conflicts_resolved():
            session.status = ImportSession.STATUS_WAITING_CONFIRM

        self.storage.save_session(session)

        for r in session.conflict_resolutions:
            if r.record_id == record_id:
                return True, None
        return False, "决策保存失败"

    def resolve_conflicts_batch(self, session_id, resolutions):
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
        imported_device_ids = set(d['device_id'] for d in session.raw_data.get('devices', []))

        for record in session.raw_data.get('repair_records', []):
            if record.get('device_id') and record['device_id'] not in imported_device_ids:
                current_devices = self._get_current_devices()
                current_device_ids = {d.device_id for d in current_devices}
                if record['device_id'] not in current_device_ids:
                    errors.append(f"维修记录 {record.get('record_id', '未知')} 关联的设备 {record['device_id']} 不存在")

        for record in session.raw_data.get('approval_records', []):
            if record.get('device_id') and record['device_id'] not in imported_device_ids:
                current_devices = self._get_current_devices()
                current_device_ids = {d.device_id for d in current_devices}
                if record['device_id'] not in current_device_ids:
                    errors.append(f"审批记录 {record.get('record_id', '未知')} 关联的设备 {record['device_id']} 不存在")

        return errors

    def validate_required_fields(self, session):
        errors = []

        for device in session.raw_data.get('devices', []):
            if not device.get('device_id'):
                errors.append(f"设备: 设备ID缺失")
            if not device.get('name'):
                errors.append(f"设备 {device.get('device_id', '未知')}: 名称缺失")
            if not device.get('status'):
                errors.append(f"设备 {device.get('device_id', '未知')}: 状态缺失")
            elif device['status'] not in DeviceStatus.values():
                errors.append(f"设备 {device.get('device_id', '未知')}: 状态值 '{device['status']}' 不合法")

        for record in session.raw_data.get('repair_records', []):
            if not record.get('record_id'):
                errors.append(f"维修记录: 记录ID缺失")
            if not record.get('device_id'):
                errors.append(f"维修记录 {record.get('record_id', '未知')}: 设备ID缺失")
            if not record.get('repair_desc'):
                errors.append(f"维修记录 {record.get('record_id', '未知')}: 维修内容缺失")
            if not record.get('operator'):
                errors.append(f"维修记录 {record.get('record_id', '未知')}: 维修人员缺失")

        for record in session.raw_data.get('approval_records', []):
            if not record.get('record_id'):
                errors.append(f"审批记录: 记录ID缺失")
            if not record.get('device_id'):
                errors.append(f"审批记录 {record.get('record_id', '未知')}: 设备ID缺失")
            if not record.get('approval_type'):
                errors.append(f"审批记录 {record.get('record_id', '未知')}: 审批类型缺失")
            if not record.get('approver'):
                errors.append(f"审批记录 {record.get('record_id', '未知')}: 审批人缺失")

        return errors

    def commit_import(self, session, operator, is_supervisor):
        if not is_supervisor:
            return False, "权限不足：只有主管才能执行导入操作"

        if operator != session.operator and not is_supervisor:
            return False, "操作人不匹配，只有创建会话的主管或当前主管可以提交"

        session = self.storage.get_session(session.session_id)
        if not session:
            return False, "会话不存在"

        if not session.is_all_conflicts_resolved():
            unresolved = session.get_unresolved_conflicts_count()
            return False, f"还有 {unresolved} 个冲突项未决策，不能执行导入"

        current_checksum = self._calculate_file_checksum(session.file_path)
        if current_checksum != session.file_checksum:
            return False, "文件已被修改，不能执行导入。请重新预览文件"

        dependency_errors = self.validate_dependencies(session)
        if dependency_errors:
            return False, f"依赖关系校验失败:\n" + "\n".join(f"- {e}" for e in dependency_errors)

        required_field_errors = self.validate_required_fields(session)
        if required_field_errors:
            return False, f"必填字段校验失败:\n" + "\n".join(f"- {e}" for e in required_field_errors)

        from service.device_service import SUPERVISORS
        for record in session.raw_data.get('approval_records', []):
            if record.get('approval_type') == '复机':
                approver = record.get('approver', '')
                if approver not in SUPERVISORS:
                    return False, f"审批人 '{approver}' 无复机审批权限"

        log_id = f"IMP_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        success, backup_path, backup_info = self.backup_service.create_backup(log_id)
        if not success:
            return False, f"创建备份失败: {backup_info}"

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
            session.commit_operator = operator
            session.can_undo = True
            session.result_message = self._generate_result_message(stats)
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
            session.status = ImportSession.STATUS_FAILED
            session.result_message = f"导入失败: {str(e)}"
            self.storage.save_session(session)

            error_log = SessionImportLog(
                log_id=log_id,
                session_id=session.session_id,
                import_time=datetime.now().isoformat(),
                operator=operator,
                is_supervisor=is_supervisor,
                total_rows=0,
                new_rows=0,
                overwrite_rows=0,
                skipped_rows=0,
                conflict_resolved=0,
                status="failed",
                message=str(e),
                details={
                    'error_type': type(e).__name__,
                    'error_message': str(e)
                }
            )
            self.storage.save_session_import_log(error_log)

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

    def undo_import(self, session):
        if not session.can_undo:
            return False, "此会话不支持撤销"

        if not session.backup_path or not os.path.exists(session.backup_path):
            return False, f"备份目录不存在: {session.backup_path}"

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
            session.result_message = "已撤销"
            self.storage.save_session(session)

            self.log_undo_result(session.session_id, True, f"撤销成功，数据已恢复")

            return True, f"已撤销会话 {session.session_id} 的导入，数据已恢复"

        except Exception as e:
            self.log_undo_result(session.session_id, False, f"撤销失败: {str(e)}")
            return False, f"撤销失败: {str(e)}"

    def cancel_session(self, session_id):
        session = self.storage.get_session(session_id)
        if not session:
            return False, "会话不存在"

        if session.committed:
            return False, "已提交的会话不能取消"

        session.status = ImportSession.STATUS_CANCELLED
        self.storage.save_session(session)
        return True, "会话已取消"

    def get_session_logs(self):
        return self.storage.load_session_import_logs()

    def export_session_log(self, log, file_path):
        return self.storage.export_session_log(log, file_path)
