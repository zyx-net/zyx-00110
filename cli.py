#!/usr/bin/env python3
import os
import sys
import json
import argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from service.device_service import DeviceService, SUPERVISORS
from service.import_service import ImportService
from service.session_manager import ImportSessionManager
from model.device import ConflictDecision, ImportSession, SessionPermission

def print_session_info(session, show_details=False):
    status_map = {
        ImportSession.STATUS_PENDING: "待处理",
        ImportSession.STATUS_IN_PROGRESS: "进行中",
        ImportSession.STATUS_WAITING_CONFIRM: "待确认",
        ImportSession.STATUS_COMPLETED: "已完成",
        ImportSession.STATUS_CANCELLED: "已取消",
        ImportSession.STATUS_FAILED: "失败"
    }
    
    print(f"会话ID: {session.session_id}")
    print(f"文件路径: {session.file_path or '-'}")
    print(f"文件类型: {session.file_type or '-'}")
    print(f"操作人: {session.operator or '-'}")
    print(f"主管权限: {'是' if session.is_supervisor else '否'}")
    print(f"状态: {status_map.get(session.status, session.status)}")
    print(f"创建时间: {session.created_time}")
    print(f"更新时间: {session.updated_time}")
    print(f"结束时间: {session.end_time or '-'}")
    print(f"已提交: {'是' if session.committed else '否'}")
    print(f"可撤销: {'是' if session.can_undo else '否'}")
    print(f"错误快照数: {len(session.error_snapshots)}")
    print(f"事件数: {len(session.events)}")
    print(f"结果消息: {session.result_message or '-'}")
    
    if show_details and session.preview_result:
        print("\n预览摘要:")
        for category in ["devices", "repair_records", "approval_records"]:
            cat_data = session.preview_result.__dict__[category]
            print(f"  {category}:")
            for key, items in cat_data.items():
                print(f"    {key}: {len(items)}")
    
    if show_details and session.conflict_resolutions:
        print("\n冲突决策:")
        for res in session.conflict_resolutions:
            decision_map = {
                ConflictDecision.KEEP_LOCAL: "保留本地",
                ConflictDecision.OVERWRITE_LOCAL: "覆盖本地",
                ConflictDecision.SKIP: "跳过"
            }
            print(f"  {res.record_id}: {decision_map.get(res.decision, res.decision)} ({res.decision_time})")

def cmd_list_sessions(args):
    service = DeviceService()
    session_manager = ImportSessionManager(service.storage, service)
    
    sessions = session_manager.get_user_sessions(args.user, args.supervisor)
    
    if not sessions:
        print("没有找到会话")
        return
    
    print(f"找到 {len(sessions)} 个会话:")
    print("-" * 120)
    print(f"{'会话ID':<30} {'操作人':<15} {'状态':<10} {'创建时间':<25} {'错误数':<6} {'可撤销'}")
    print("-" * 120)
    
    for session in sessions:
        status_map = {
            ImportSession.STATUS_PENDING: "待处理",
            ImportSession.STATUS_IN_PROGRESS: "进行中",
            ImportSession.STATUS_WAITING_CONFIRM: "待确认",
            ImportSession.STATUS_COMPLETED: "已完成",
            ImportSession.STATUS_CANCELLED: "已取消",
            ImportSession.STATUS_FAILED: "失败"
        }
        can_undo = "是" if session.can_undo else ""
        print(f"{session.session_id:<30} {session.operator:<15} {status_map.get(session.status, session.status):<10} {session.created_time:<25} {len(session.error_snapshots):<6} {can_undo}")

def cmd_show_session(args):
    service = DeviceService()
    session_manager = ImportSessionManager(service.storage, service)
    
    session = session_manager.get_session(args.session_id)
    if not session:
        print(f"错误: 会话 {args.session_id} 不存在")
        sys.exit(1)
    
    print_session_info(session, show_details=True)

def cmd_create_session(args):
    if not os.path.exists(args.file):
        print(f"错误: 文件 {args.file} 不存在")
        sys.exit(1)
    
    service = DeviceService()
    import_service = ImportService(service.storage, service)
    session_manager = ImportSessionManager(service.storage, service)
    
    preview_result, raw_data, error = import_service.preview_import_session(
        args.file, args.user, args.supervisor
    )
    
    if error:
        print(f"预览失败: {error}")
        sys.exit(1)
    
    session, msg = session_manager.create_session(
        file_path=args.file,
        file_type='json',
        operator=args.user,
        is_supervisor=args.supervisor,
        parsed_data=raw_data,
        preview_result=preview_result
    )
    
    print(f"会话创建成功: {session.session_id}")
    if msg:
        print(f"提示: {msg}")
    
    conflict_count = preview_result.get_total_conflict()
    if conflict_count > 0:
        print(f"发现 {conflict_count} 个冲突，需要先处理冲突才能提交")

def cmd_resolve_conflict(args):
    service = DeviceService()
    session_manager = ImportSessionManager(service.storage, service)
    
    session = session_manager.get_session(args.session_id)
    if not session:
        print(f"错误: 会话 {args.session_id} 不存在")
        sys.exit(1)
    
    if not session.preview_result:
        print("错误: 会话没有预览数据")
        sys.exit(1)
    
    category_map = {
        "device": "devices",
        "repair": "repair_records",
        "approval": "approval_records"
    }
    
    category = category_map.get(args.type)
    if not category:
        print(f"错误: 无效的类型 '{args.type}'，有效类型: device, repair, approval")
        sys.exit(1)
    
    conflict_data = None
    for row in session.preview_result.__dict__[category]["conflict"]:
        record_id = row.row_data.get('device_id') or row.row_data.get('record_id')
        if record_id == args.record_id:
            conflict_data = row.row_data
            break
    
    if not conflict_data:
        print(f"错误: 未找到记录ID '{args.record_id}'")
        sys.exit(1)
    
    success, error = session_manager.resolve_conflict(
        session.session_id,
        args.record_id,
        args.type,
        conflict_data,
        args.decision
    )
    
    if success:
        decision_map = {
            ConflictDecision.KEEP_LOCAL: "保留本地",
            ConflictDecision.OVERWRITE_LOCAL: "覆盖本地",
            ConflictDecision.SKIP: "跳过"
        }
        print(f"冲突决策已设置: {decision_map.get(args.decision, args.decision)}")
        
        if session.is_all_conflicts_resolved():
            print("所有冲突已解决，可以提交导入")
    else:
        print(f"设置失败: {error}")
        sys.exit(1)

def cmd_commit_session(args):
    service = DeviceService()
    session_manager = ImportSessionManager(service.storage, service)
    
    session = session_manager.get_session(args.session_id)
    if not session:
        print(f"错误: 会话 {args.session_id} 不存在")
        sys.exit(1)
    
    if not session.is_all_conflicts_resolved():
        unresolved = session.get_unresolved_conflicts_count()
        print(f"错误: 还有 {unresolved} 个冲突未解决")
        sys.exit(1)
    
    success, msg = session_manager.commit_import(session, args.user, args.supervisor)
    
    if success:
        print(f"导入成功!\n{msg}")
    else:
        print(f"导入失败: {msg}")
        sys.exit(1)

def cmd_undo_session(args):
    service = DeviceService()
    session_manager = ImportSessionManager(service.storage, service)
    
    session = session_manager.get_session(args.session_id)
    if not session:
        print(f"错误: 会话 {args.session_id} 不存在")
        sys.exit(1)
    
    if not session.can_undo:
        print("错误: 此会话不支持撤销")
        sys.exit(1)
    
    success, msg = session_manager.undo_import(session, args.user, args.supervisor)
    
    if success:
        print(f"撤销成功!\n{msg}")
    else:
        print(f"撤销失败: {msg}")
        sys.exit(1)

def cmd_cancel_session(args):
    service = DeviceService()
    session_manager = ImportSessionManager(service.storage, service)
    
    success, msg = session_manager.cancel_session(args.session_id)
    
    if success:
        print(f"会话已取消")
    else:
        print(f"取消失败: {msg}")
        sys.exit(1)

def cmd_delete_session(args):
    service = DeviceService()
    session_manager = ImportSessionManager(service.storage, service)
    
    success, msg = session_manager.delete_session(args.session_id, args.user, args.supervisor)
    
    if success:
        print(msg)
    else:
        print(f"删除失败: {msg}")
        sys.exit(1)

def cmd_export_error_snapshot(args):
    service = DeviceService()
    session_manager = ImportSessionManager(service.storage, service)
    
    success, msg = session_manager.export_failed_session_snapshot(
        args.session_id, args.output, args.user, args.supervisor
    )
    
    if success:
        print(f"错误快照已导出到: {args.output}")
    else:
        print(f"导出失败: {msg}")
        sys.exit(1)

def cmd_list_failed_sessions(args):
    service = DeviceService()
    session_manager = ImportSessionManager(service.storage, service)
    
    sessions = session_manager.get_failed_sessions_for_user(args.user, args.supervisor)
    
    if not sessions:
        print("没有失败的会话")
        return
    
    print(f"找到 {len(sessions)} 个失败会话:")
    print("-" * 120)
    print(f"{'会话ID':<30} {'操作人':<15} {'创建时间':<25} {'错误数':<6} {'错误消息'}")
    print("-" * 120)
    
    for session in sessions:
        error_msg = session.result_message[:50] if session.result_message else "-"
        print(f"{session.session_id:<30} {session.operator:<15} {session.created_time:<25} {len(session.error_snapshots):<6} {error_msg}")

def cmd_show_errors(args):
    service = DeviceService()
    session_manager = ImportSessionManager(service.storage, service)
    
    session = session_manager.get_session(args.session_id)
    if not session:
        print(f"错误: 会话 {args.session_id} 不存在")
        sys.exit(1)
    
    if not session.error_snapshots:
        print("此会话没有错误快照")
        return
    
    print(f"会话 {session.session_id} 的错误快照:")
    print("=" * 60)
    
    for i, snapshot in enumerate(session.error_snapshots, 1):
        print(f"\n[{i}] {snapshot.error_time}")
        print(f"  类型: {snapshot.error_type}")
        print(f"  消息: {snapshot.error_message}")
        if snapshot.context:
            print(f"  上下文: {json.dumps(snapshot.context, ensure_ascii=False)}")
        if snapshot.stack_trace:
            print(f"  堆栈:\n{snapshot.stack_trace}")

def cmd_verify_file_integrity(args):
    service = DeviceService()
    session_manager = ImportSessionManager(service.storage, service)
    
    success, message, details = session_manager.verify_file_integrity(args.session_id)
    
    if success:
        print(f"文件完整: {message}")
        print(f"校验和: {details['checksum']}")
    else:
        print(f"文件异常: {message}")
        print(f"原始校验和: {details.get('original_checksum', 'N/A')}")
        print(f"当前校验和: {details.get('current_checksum', 'N/A')}")
        sys.exit(1)

def cmd_revalidate_session(args):
    service = DeviceService()
    session_manager = ImportSessionManager(service.storage, service)
    
    success, errors = session_manager.revalidate_session(args.session_id)
    
    if success:
        print("校验通过，所有依赖关系和必填字段都满足要求")
    else:
        print("校验失败，发现以下问题:")
        for error in errors:
            print(f"  - {error}")
        sys.exit(1)

def cmd_grant_permission(args):
    service = DeviceService()
    session_manager = ImportSessionManager(service.storage, service)
    
    success, msg = session_manager.grant_session_permission(
        args.session_id, args.target_user, args.permission, args.user, args.supervisor
    )
    
    if success:
        print(msg)
    else:
        print(f"授权失败: {msg}")
        sys.exit(1)

def cmd_revoke_permission(args):
    service = DeviceService()
    session_manager = ImportSessionManager(service.storage, service)
    
    success, msg = session_manager.revoke_session_permission(
        args.session_id, args.target_user, args.permission, args.user, args.supervisor
    )
    
    if success:
        print(msg)
    else:
        print(f"撤销权限失败: {msg}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="设备巡检系统 - 导入会话管理CLI")
    parser.add_argument("--user", default="admin", help="操作人")
    parser.add_argument("--supervisor", action="store_true", help="是否为管理员")
    
    subparsers = parser.add_subparsers(dest="command", help="可用命令")
    
    # list-sessions
    subparsers.add_parser("list-sessions", help="列出所有会话")
    
    # show-session
    show_parser = subparsers.add_parser("show-session", help="显示会话详情")
    show_parser.add_argument("session_id", help="会话ID")
    
    # create-session
    create_parser = subparsers.add_parser("create-session", help="创建导入会话")
    create_parser.add_argument("file", help="导入文件路径")
    
    # resolve-conflict
    resolve_parser = subparsers.add_parser("resolve-conflict", help="解决冲突")
    resolve_parser.add_argument("session_id", help="会话ID")
    resolve_parser.add_argument("type", choices=["device", "repair", "approval"], help="记录类型")
    resolve_parser.add_argument("record_id", help="记录ID")
    resolve_parser.add_argument("decision", choices=[ConflictDecision.KEEP_LOCAL, ConflictDecision.OVERWRITE_LOCAL, ConflictDecision.SKIP], help="决策")
    
    # commit-session
    commit_parser = subparsers.add_parser("commit-session", help="提交导入会话")
    commit_parser.add_argument("session_id", help="会话ID")
    
    # undo-session
    undo_parser = subparsers.add_parser("undo-session", help="撤销已提交的会话")
    undo_parser.add_argument("session_id", help="会话ID")
    
    # cancel-session
    cancel_parser = subparsers.add_parser("cancel-session", help="取消会话")
    cancel_parser.add_argument("session_id", help="会话ID")
    
    # delete-session
    delete_parser = subparsers.add_parser("delete-session", help="删除会话")
    delete_parser.add_argument("session_id", help="会话ID")
    
    # list-failed
    subparsers.add_parser("list-failed", help="列出失败的会话")
    
    # show-errors
    errors_parser = subparsers.add_parser("show-errors", help="显示会话错误")
    errors_parser.add_argument("session_id", help="会话ID")
    
    # export-error-snapshot
    export_parser = subparsers.add_parser("export-error-snapshot", help="导出错误快照")
    export_parser.add_argument("session_id", help="会话ID")
    export_parser.add_argument("output", help="输出文件路径")
    
    # verify-file
    verify_parser = subparsers.add_parser("verify-file", help="校验文件完整性")
    verify_parser.add_argument("session_id", help="会话ID")
    
    # revalidate
    revalidate_parser = subparsers.add_parser("revalidate", help="重新校验会话")
    revalidate_parser.add_argument("session_id", help="会话ID")
    
    # grant-permission
    grant_parser = subparsers.add_parser("grant-permission", help="授予权限")
    grant_parser.add_argument("session_id", help="会话ID")
    grant_parser.add_argument("target_user", help="目标用户")
    grant_parser.add_argument("permission", choices=[SessionPermission.PERM_VIEW, SessionPermission.PERM_EXPORT, SessionPermission.PERM_UNDO], help="权限类型")
    
    # revoke-permission
    revoke_parser = subparsers.add_parser("revoke-permission", help="撤销权限")
    revoke_parser.add_argument("session_id", help="会话ID")
    revoke_parser.add_argument("target_user", help="目标用户")
    revoke_parser.add_argument("permission", choices=[SessionPermission.PERM_VIEW, SessionPermission.PERM_EXPORT, SessionPermission.PERM_UNDO], help="权限类型")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(0)
    
    command_map = {
        "list-sessions": cmd_list_sessions,
        "show-session": cmd_show_session,
        "create-session": cmd_create_session,
        "resolve-conflict": cmd_resolve_conflict,
        "commit-session": cmd_commit_session,
        "undo-session": cmd_undo_session,
        "cancel-session": cmd_cancel_session,
        "delete-session": cmd_delete_session,
        "list-failed": cmd_list_failed_sessions,
        "show-errors": cmd_show_errors,
        "export-error-snapshot": cmd_export_error_snapshot,
        "verify-file": cmd_verify_file_integrity,
        "revalidate": cmd_revalidate_session,
        "grant-permission": cmd_grant_permission,
        "revoke-permission": cmd_revoke_permission
    }
    
    try:
        command_map[args.command](args)
    except KeyError:
        print(f"未知命令: {args.command}")
        sys.exit(1)

if __name__ == "__main__":
    main()