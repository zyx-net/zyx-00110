import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from service.device_service import DeviceService, SUPERVISORS
from service.import_service import ImportService
from service.session_manager import ImportSessionManager
from model.status import DeviceStatus
from model.device import ConflictDecision, ImportSession


class DeviceInspectionApp:
    def __init__(self, root):
        self.root = root
        self.root.title("设备巡检停复机登记系统")
        self.root.geometry("1200x800")

        self.service = DeviceService()
        self.import_service = ImportService(self.service.storage, self.service)
        self.session_manager = ImportSessionManager(self.service.storage, self.service)

        self.current_user = ""
        self.is_supervisor = False
        self.current_session = None

        self.setup_ui()
        self._check_rollback_on_startup()
        self._check_pending_session()
        
    def setup_ui(self):
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.device_frame = ttk.Frame(self.notebook)
        self.config_frame = ttk.Frame(self.notebook)
        self.import_frame = ttk.Frame(self.notebook)
        self.session_frame = ttk.Frame(self.notebook)
        self.log_frame = ttk.Frame(self.notebook)

        self.notebook.add(self.device_frame, text="设备管理")
        self.notebook.add(self.config_frame, text="系统配置")
        self.notebook.add(self.import_frame, text="数据导入")
        self.notebook.add(self.session_frame, text="导入会话")
        self.notebook.add(self.log_frame, text="历史日志")

        self.setup_device_tab()
        self.setup_config_tab()
        self.setup_import_tab()
        self.setup_session_tab()
        self.setup_log_tab()
        
    def setup_device_tab(self):
        top_frame = ttk.Frame(self.device_frame)
        top_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(top_frame, text="设备ID:").pack(side=tk.LEFT, padx=5)
        self.device_id_entry = ttk.Entry(top_frame, width=20)
        self.device_id_entry.pack(side=tk.LEFT, padx=5)
        
        ttk.Label(top_frame, text="设备名称:").pack(side=tk.LEFT, padx=5)
        self.device_name_entry = ttk.Entry(top_frame, width=30)
        self.device_name_entry.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(top_frame, text="添加设备", command=self.add_device).pack(side=tk.LEFT, padx=5)
        
        self.status_filter = ttk.Combobox(top_frame, values=["全部"] + DeviceStatus.values())
        self.status_filter.current(0)
        self.status_filter.bind("<<ComboboxSelected>>", self.refresh_device_list)
        self.status_filter.pack(side=tk.RIGHT, padx=5)
        ttk.Label(top_frame, text="状态筛选:").pack(side=tk.RIGHT, padx=5)
        
        self.device_tree = ttk.Treeview(self.device_frame, columns=("ID", "名称", "状态", "异常描述", "更新时间"), show="headings")
        self.device_tree.heading("ID", text="设备ID")
        self.device_tree.heading("名称", text="设备名称")
        self.device_tree.heading("状态", text="当前状态")
        self.device_tree.heading("异常描述", text="异常描述")
        self.device_tree.heading("更新时间", text="更新时间")
        
        self.device_tree.column("ID", width=100)
        self.device_tree.column("名称", width=150)
        self.device_tree.column("状态", width=120)
        self.device_tree.column("异常描述", width=300)
        self.device_tree.column("更新时间", width=200)
        
        self.device_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        action_frame = ttk.Frame(self.device_frame)
        action_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.action_buttons = [
            ("报告异常", self.report_abnormal, "正常"),
            ("申请停机", self.apply_stop, "待停机审批"),
            ("开始维修", self.start_repair, "已停机"),
            ("完成维修", self.complete_repair, "维修中"),
            ("批准复机", self.approve_restart, "待复机审批"),
            ("复发观察", self.enter_observation, "已复机"),
            ("恢复正常", self.exit_observation, "复发观察"),
            ("查看维修记录", self.view_repair_records, None),
            ("查看审批记录", self.view_approval_records, None),
            ("删除设备", self.delete_device, None)
        ]
        
        for text, cmd, required_status in self.action_buttons:
            btn = ttk.Button(action_frame, text=text, command=cmd)
            btn.pack(side=tk.LEFT, padx=5)
        
        self.refresh_device_list()
        
    def setup_config_tab(self):
        config = self.service.get_config()
        
        ttk.Label(self.config_frame, text="导出目录:").grid(row=0, column=0, padx=10, pady=10, sticky=tk.W)
        self.export_dir_entry = ttk.Entry(self.config_frame, width=60)
        self.export_dir_entry.insert(0, config.export_dir)
        self.export_dir_entry.grid(row=0, column=1, padx=10, pady=10)
        ttk.Button(self.config_frame, text="浏览", command=self.browse_export_dir).grid(row=0, column=2, padx=5)
        
        ttk.Label(self.config_frame, text="阈值下限:").grid(row=1, column=0, padx=10, pady=10, sticky=tk.W)
        self.threshold_low_entry = ttk.Entry(self.config_frame, width=20)
        self.threshold_low_entry.insert(0, str(config.threshold_low))
        self.threshold_low_entry.grid(row=1, column=1, padx=10, pady=10, sticky=tk.W)
        
        ttk.Label(self.config_frame, text="阈值上限:").grid(row=2, column=0, padx=10, pady=10, sticky=tk.W)
        self.threshold_high_entry = ttk.Entry(self.config_frame, width=20)
        self.threshold_high_entry.insert(0, str(config.threshold_high))
        self.threshold_high_entry.grid(row=2, column=1, padx=10, pady=10, sticky=tk.W)
        
        ttk.Button(self.config_frame, text="保存配置", command=self.save_config).grid(row=3, column=0, padx=10, pady=20)
        ttk.Button(self.config_frame, text="导出记录", command=self.export_records).grid(row=3, column=1, padx=10, pady=20)
        
    def setup_import_tab(self):
        user_frame = ttk.LabelFrame(self.import_frame, text="当前用户")
        user_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(user_frame, text="操作人:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.user_entry = ttk.Entry(user_frame, width=20)
        self.user_entry.grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)
        
        ttk.Button(user_frame, text="验证身份", command=self.verify_user).grid(row=0, column=2, padx=5, pady=5)
        
        self.user_status_label = ttk.Label(user_frame, text="未验证", foreground="gray")
        self.user_status_label.grid(row=0, column=3, padx=10, pady=5, sticky=tk.W)
        
        file_frame = ttk.LabelFrame(self.import_frame, text="选择导入文件")
        file_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(file_frame, text="文件路径:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.import_file_entry = ttk.Entry(file_frame, width=60)
        self.import_file_entry.grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(file_frame, text="浏览", command=self.browse_import_file).grid(row=0, column=2, padx=5, pady=5)
        
        btn_frame = ttk.Frame(file_frame)
        btn_frame.grid(row=1, column=0, columnspan=3, padx=5, pady=5)
        
        ttk.Button(btn_frame, text="预检导入", command=self.preview_import).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="执行导入", command=self.execute_import).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="撤销上次导入", command=self.rollback_import).pack(side=tk.LEFT, padx=5)
        
        self.rollback_info_label = ttk.Label(file_frame, text="", foreground="blue")
        self.rollback_info_label.grid(row=2, column=0, columnspan=3, padx=5, pady=5, sticky=tk.W)
        
        preview_frame = ttk.LabelFrame(self.import_frame, text="预检结果")
        preview_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.preview_notebook = ttk.Notebook(preview_frame)
        self.preview_notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.new_rows_frame = ttk.Frame(self.preview_notebook)
        self.overwrite_rows_frame = ttk.Frame(self.preview_notebook)
        self.conflict_rows_frame = ttk.Frame(self.preview_notebook)
        self.invalid_rows_frame = ttk.Frame(self.preview_notebook)
        
        self.preview_notebook.add(self.new_rows_frame, text="新增 (0)")
        self.preview_notebook.add(self.overwrite_rows_frame, text="覆盖 (0)")
        self.preview_notebook.add(self.conflict_rows_frame, text="冲突 (0)")
        self.preview_notebook.add(self.invalid_rows_frame, text="无效 (0)")
        
        self.new_tree = ttk.Treeview(self.new_rows_frame, columns=("类型", "ID", "详情"), show="headings")
        self.new_tree.heading("类型", text="类型")
        self.new_tree.heading("ID", text="ID")
        self.new_tree.heading("详情", text="详情")
        self.new_tree.column("类型", width=80)
        self.new_tree.column("ID", width=120)
        self.new_tree.column("详情", width=400)
        self.new_tree.pack(fill=tk.BOTH, expand=True)
        
        self.overwrite_tree = ttk.Treeview(self.overwrite_rows_frame, columns=("类型", "ID", "详情"), show="headings")
        self.overwrite_tree.heading("类型", text="类型")
        self.overwrite_tree.heading("ID", text="ID")
        self.overwrite_tree.heading("详情", text="详情")
        self.overwrite_tree.column("类型", width=80)
        self.overwrite_tree.column("ID", width=120)
        self.overwrite_tree.column("详情", width=400)
        self.overwrite_tree.pack(fill=tk.BOTH, expand=True)
        
        self.conflict_tree = ttk.Treeview(self.conflict_rows_frame, columns=("类型", "ID", "原因"), show="headings")
        self.conflict_tree.heading("类型", text="类型")
        self.conflict_tree.heading("ID", text="ID")
        self.conflict_tree.heading("原因", text="原因")
        self.conflict_tree.column("类型", width=80)
        self.conflict_tree.column("ID", width=120)
        self.conflict_tree.column("原因", width=400)
        self.conflict_tree.pack(fill=tk.BOTH, expand=True)
        
        self.invalid_tree = ttk.Treeview(self.invalid_rows_frame, columns=("类型", "ID", "错误"), show="headings")
        self.invalid_tree.heading("类型", text="类型")
        self.invalid_tree.heading("ID", text="ID")
        self.invalid_tree.heading("错误", text="错误信息")
        self.invalid_tree.column("类型", width=80)
        self.invalid_tree.column("ID", width=120)
        self.invalid_tree.column("错误", width=400)
        self.invalid_tree.pack(fill=tk.BOTH, expand=True)
        
        self.preview_info = None
        self._update_rollback_info()

    def setup_session_tab(self):
        self.session_info_frame = ttk.LabelFrame(self.session_frame, text="会话信息")
        self.session_info_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(self.session_info_frame, text="会话ID:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.session_id_label = ttk.Label(self.session_info_frame, text="无活动会话")
        self.session_id_label.grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)

        ttk.Label(self.session_info_frame, text="文件:").grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        self.session_file_label = ttk.Label(self.session_info_frame, text="-")
        self.session_file_label.grid(row=1, column=1, padx=5, pady=5, sticky=tk.W)

        ttk.Label(self.session_info_frame, text="状态:").grid(row=2, column=0, padx=5, pady=5, sticky=tk.W)
        self.session_status_label = ttk.Label(self.session_info_frame, text="-")
        self.session_status_label.grid(row=2, column=1, padx=5, pady=5, sticky=tk.W)

        ttk.Label(self.session_info_frame, text="操作人:").grid(row=3, column=0, padx=5, pady=5, sticky=tk.W)
        self.session_operator_label = ttk.Label(self.session_info_frame, text="-")
        self.session_operator_label.grid(row=3, column=1, padx=5, pady=5, sticky=tk.W)

        btn_frame = ttk.Frame(self.session_frame)
        btn_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Button(btn_frame, text="创建新会话", command=self.create_new_session).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="刷新", command=self.refresh_session_view).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="提交导入", command=self.commit_session_import).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="撤销导入", command=self.undo_session_import).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="取消会话", command=self.cancel_current_session).pack(side=tk.LEFT, padx=5)

        self.session_notebook = ttk.Notebook(self.session_frame)
        self.session_notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.device_new_frame = ttk.Frame(self.session_notebook)
        self.device_overwrite_frame = ttk.Frame(self.session_notebook)
        self.device_conflict_frame = ttk.Frame(self.session_notebook)
        self.device_invalid_frame = ttk.Frame(self.session_notebook)

        self.session_notebook.add(self.device_new_frame, text="设备-新增 (0)")
        self.session_notebook.add(self.device_overwrite_frame, text="设备-覆盖 (0)")
        self.session_notebook.add(self.device_conflict_frame, text="设备-冲突 (0)")
        self.session_notebook.add(self.device_invalid_frame, text="设备-无效 (0)")

        self.repair_new_frame = ttk.Frame(self.session_notebook)
        self.repair_overwrite_frame = ttk.Frame(self.session_notebook)
        self.repair_conflict_frame = ttk.Frame(self.session_notebook)
        self.repair_invalid_frame = ttk.Frame(self.session_notebook)

        self.session_notebook.add(self.repair_new_frame, text="维修-新增 (0)")
        self.session_notebook.add(self.repair_overwrite_frame, text="维修-覆盖 (0)")
        self.session_notebook.add(self.repair_conflict_frame, text="维修-冲突 (0)")
        self.session_notebook.add(self.repair_invalid_frame, text="维修-无效 (0)")

        self.approval_new_frame = ttk.Frame(self.session_notebook)
        self.approval_overwrite_frame = ttk.Frame(self.session_notebook)
        self.approval_conflict_frame = ttk.Frame(self.session_notebook)
        self.approval_invalid_frame = ttk.Frame(self.session_notebook)

        self.session_notebook.add(self.approval_new_frame, text="审批-新增 (0)")
        self.session_notebook.add(self.approval_overwrite_frame, text="审批-覆盖 (0)")
        self.session_notebook.add(self.approval_conflict_frame, text="审批-冲突 (0)")
        self.session_notebook.add(self.approval_invalid_frame, text="审批-无效 (0)")

        self._setup_conflict_tree(self.device_conflict_frame, True)
        self._setup_conflict_tree(self.repair_conflict_frame, True)
        self._setup_conflict_tree(self.approval_conflict_frame, True)

        self._setup_data_tree(self.device_new_frame)
        self._setup_data_tree(self.device_overwrite_frame)
        self._setup_data_tree(self.device_invalid_frame)
        self._setup_data_tree(self.repair_new_frame)
        self._setup_data_tree(self.repair_overwrite_frame)
        self._setup_data_tree(self.repair_invalid_frame)
        self._setup_data_tree(self.approval_new_frame)
        self._setup_data_tree(self.approval_overwrite_frame)
        self._setup_data_tree(self.approval_invalid_frame)

    def _setup_data_tree(self, parent):
        tree = ttk.Treeview(parent, columns=("ID", "详情"), show="headings")
        tree.heading("ID", text="ID")
        tree.heading("详情", text="详情")
        tree.column("ID", width=150)
        tree.column("详情", width=400)
        tree.pack(fill=tk.BOTH, expand=True)

    def _setup_conflict_tree(self, parent, with_buttons=False):
        frame = ttk.Frame(parent)
        frame.pack(fill=tk.BOTH, expand=True)

        tree = ttk.Treeview(frame, columns=("类型", "ID", "原因", "决策"), show="headings")
        tree.heading("类型", text="类型")
        tree.heading("ID", text="ID")
        tree.heading("原因", text="原因")
        tree.heading("决策", text="当前决策")
        tree.column("类型", width=80)
        tree.column("ID", width=120)
        tree.column("原因", width=250)
        tree.column("决策", width=150)
        tree.pack(fill=tk.BOTH, expand=True)

        if with_buttons:
            btn_frame = ttk.Frame(parent)
            btn_frame.pack(fill=tk.X, pady=5)

            ttk.Label(btn_frame, text="选中冲突项:").pack(side=tk.LEFT, padx=5)
            ttk.Button(btn_frame, text="保留本地", command=lambda: self._set_conflict_decision(tree, ConflictDecision.KEEP_LOCAL)).pack(side=tk.LEFT, padx=2)
            ttk.Button(btn_frame, text="覆盖本地", command=lambda: self._set_conflict_decision(tree, ConflictDecision.OVERWRITE_LOCAL)).pack(side=tk.LEFT, padx=2)
            ttk.Button(btn_frame, text="跳过", command=lambda: self._set_conflict_decision(tree, ConflictDecision.SKIP)).pack(side=tk.LEFT, padx=2)

        parent.tree = tree

    def _set_conflict_decision(self, tree, decision):
        selected = tree.selection()
        if not selected:
            messagebox.showwarning("提示", "请先选择冲突项")
            return

        for item in selected:
            values = tree.item(item)['values']
            record_id = values[1]
            record_type = values[0]
            decision_text = {
                ConflictDecision.KEEP_LOCAL: "保留本地",
                ConflictDecision.OVERWRITE_LOCAL: "覆盖本地",
                ConflictDecision.SKIP: "跳过"
            }.get(decision, decision)

            if self.current_session:
                record_data = {}
                if record_type == "设备":
                    for row in self.current_session.preview_result.devices["conflict"]:
                        if (row.row_data.get('device_id') or row.row_data.get('record_id')) == record_id:
                            record_data = row.row_data
                            break
                elif record_type == "维修":
                    for row in self.current_session.preview_result.repair_records["conflict"]:
                        if (row.row_data.get('device_id') or row.row_data.get('record_id')) == record_id:
                            record_data = row.row_data
                            break
                else:
                    for row in self.current_session.preview_result.approval_records["conflict"]:
                        if (row.row_data.get('device_id') or row.row_data.get('record_id')) == record_id:
                            record_data = row.row_data
                            break

                success, error = self.session_manager.resolve_conflict(
                    self.current_session.session_id,
                    record_id,
                    record_type,
                    record_data,
                    decision
                )

                if success:
                    tree.item(item, values=(values[0], values[1], values[2], decision_text))
                else:
                    messagebox.showerror("错误", f"设置决策失败: {error}")

    def _load_session_view(self, session):
        self.current_session = session
        self.session_id_label.config(text=session.session_id)
        self.session_file_label.config(text=session.file_path or "-")
        self.session_operator_label.config(text=session.operator or "-")

        status_map = {
            ImportSession.STATUS_PENDING: "待处理",
            ImportSession.STATUS_IN_PROGRESS: "进行中",
            ImportSession.STATUS_WAITING_CONFIRM: "待确认",
            ImportSession.STATUS_COMPLETED: "已完成",
            ImportSession.STATUS_CANCELLED: "已取消",
            ImportSession.STATUS_FAILED: "失败"
        }
        self.session_status_label.config(text=status_map.get(session.status, session.status))

        if session.preview_result:
            self._populate_preview_results(session.preview_result)

    def _populate_preview_results(self, preview):
        trees_to_clear = [
            (self.device_new_frame, 'tree'), (self.device_overwrite_frame, 'tree'),
            (self.device_invalid_frame, 'tree'), (self.repair_new_frame, 'tree'),
            (self.repair_overwrite_frame, 'tree'), (self.repair_invalid_frame, 'tree'),
            (self.approval_new_frame, 'tree'), (self.approval_overwrite_frame, 'tree'),
            (self.approval_invalid_frame, 'tree'),
            (self.device_conflict_frame, 'tree'), (self.repair_conflict_frame, 'tree'),
            (self.approval_conflict_frame, 'tree')
        ]

        for frame, attr in trees_to_clear:
            if hasattr(frame, attr):
                tree = getattr(frame, attr)
                for item in tree.get_children():
                    tree.delete(item)

        self._add_rows_to_tree(self.device_new_frame, 'tree', preview.devices["new"])
        self._add_rows_to_tree(self.device_overwrite_frame, 'tree', preview.devices["overwrite"])
        self._add_conflict_rows_to_tree(self.device_conflict_frame, 'tree', preview.devices["conflict"], self.current_session)
        self._add_rows_to_tree(self.device_invalid_frame, 'tree', preview.devices["invalid"])

        self._add_rows_to_tree(self.repair_new_frame, 'tree', preview.repair_records["new"])
        self._add_rows_to_tree(self.repair_overwrite_frame, 'tree', preview.repair_records["overwrite"])
        self._add_conflict_rows_to_tree(self.repair_conflict_frame, 'tree', preview.repair_records["conflict"], self.current_session)
        self._add_rows_to_tree(self.repair_invalid_frame, 'tree', preview.repair_records["invalid"])

        self._add_rows_to_tree(self.approval_new_frame, 'tree', preview.approval_records["new"])
        self._add_rows_to_tree(self.approval_overwrite_frame, 'tree', preview.approval_records["overwrite"])
        self._add_conflict_rows_to_tree(self.approval_conflict_frame, 'tree', preview.approval_records["conflict"], self.current_session)
        self._add_rows_to_tree(self.approval_invalid_frame, 'tree', preview.approval_records["invalid"])

        self.session_notebook.tab(self.device_new_frame, text=f"设备-新增 ({len(preview.devices['new'])})")
        self.session_notebook.tab(self.device_overwrite_frame, text=f"设备-覆盖 ({len(preview.devices['overwrite'])})")
        self.session_notebook.tab(self.device_conflict_frame, text=f"设备-冲突 ({len(preview.devices['conflict'])})")
        self.session_notebook.tab(self.device_invalid_frame, text=f"设备-无效 ({len(preview.devices['invalid'])})")

        self.session_notebook.tab(self.repair_new_frame, text=f"维修-新增 ({len(preview.repair_records['new'])})")
        self.session_notebook.tab(self.repair_overwrite_frame, text=f"维修-覆盖 ({len(preview.repair_records['overwrite'])})")
        self.session_notebook.tab(self.repair_conflict_frame, text=f"维修-冲突 ({len(preview.repair_records['conflict'])})")
        self.session_notebook.tab(self.repair_invalid_frame, text=f"维修-无效 ({len(preview.repair_records['invalid'])})")

        self.session_notebook.tab(self.approval_new_frame, text=f"审批-新增 ({len(preview.approval_records['new'])})")
        self.session_notebook.tab(self.approval_overwrite_frame, text=f"审批-覆盖 ({len(preview.approval_records['overwrite'])})")
        self.session_notebook.tab(self.approval_conflict_frame, text=f"审批-冲突 ({len(preview.approval_records['conflict'])})")
        self.session_notebook.tab(self.approval_invalid_frame, text=f"审批-无效 ({len(preview.approval_records['invalid'])})")

    def _add_rows_to_tree(self, frame, attr, rows):
        if hasattr(frame, attr):
            tree = getattr(frame, attr)
            for row in rows:
                data = row.row_data
                if 'name' in data:
                    row_id = data.get('device_id', '')
                    detail = f"{data.get('name', '')} - {data.get('status', '')}"
                elif 'repair_desc' in data:
                    row_id = data.get('record_id', '')
                    detail = f"{data.get('device_id', '')} - {data.get('repair_desc', '')[:30]}"
                elif 'approval_type' in data:
                    row_id = data.get('record_id', '')
                    detail = f"{data.get('device_id', '')} - {data.get('approval_type', '')}"
                else:
                    row_id = data.get('device_id') or data.get('record_id', '')
                    detail = str(data)
                tree.insert("", tk.END, values=(row_id, detail))

    def _add_conflict_rows_to_tree(self, frame, attr, rows, session):
        if hasattr(frame, attr):
            tree = getattr(frame, attr)
            for row in rows:
                data = row.row_data
                if 'name' in data:
                    row_type = "设备"
                    row_id = data.get('device_id', '')
                elif 'repair_desc' in data:
                    row_type = "维修"
                    row_id = data.get('record_id', '')
                else:
                    row_type = "审批"
                    row_id = data.get('record_id', '')

                decision = session.get_conflict_resolution(row_id) if session else None
                decision_text = {
                    ConflictDecision.KEEP_LOCAL: "保留本地",
                    ConflictDecision.OVERWRITE_LOCAL: "覆盖本地",
                    ConflictDecision.SKIP: "跳过"
                }.get(decision, "未决策")
                tree.insert("", tk.END, values=(row_type, row_id, row.reason, decision_text))

    def create_new_session(self):
        if not self.current_user:
            messagebox.showwarning("提示", "请先验证身份")
            return

        file_path = filedialog.askopenfilename(
            filetypes=[("JSON文件", "*.json"), ("CSV文件", "*.csv"), ("所有文件", "*.*")]
        )
        if not file_path:
            return

        preview_result, raw_data, error = self.import_service.preview_import_session(
            file_path, self.current_user, self.is_supervisor
        )

        if error:
            messagebox.showerror("预览失败", error)
            return

        session, msg = self.session_manager.create_session(
            file_path=file_path,
            file_type=preview_result and 'json' or 'csv',
            operator=self.current_user,
            is_supervisor=self.is_supervisor,
            parsed_data=raw_data,
            preview_result=preview_result
        )

        if msg and "已恢复" in msg:
            messagebox.showinfo("会话恢复", msg)

        self.current_session = session
        self._load_session_view(session)

    def refresh_session_view(self):
        if self.current_session:
            session = self.session_manager.get_session(self.current_session.session_id)
            if session:
                self.current_session = session
                self._load_session_view(session)
            else:
                messagebox.showinfo("提示", "会话已不存在")
                self.current_session = None
                self.session_id_label.config(text="无活动会话")
                self.session_file_label.config(text="-")
                self.session_status_label.config(text="-")
                self.session_operator_label.config(text="-")

    def commit_session_import(self):
        if not self.current_session:
            messagebox.showwarning("提示", "没有活动会话")
            return

        if not self.is_supervisor:
            messagebox.showwarning("权限不足", "只有主管才能执行导入操作")
            return

        if not self.current_session.is_all_conflicts_resolved():
            unresolved = self.current_session.get_unresolved_conflicts_count()
            messagebox.showwarning("提示", f"还有 {unresolved} 个冲突项未决策，请先处理")
            return

        if not messagebox.askyesno("确认导入", "确定要执行导入吗？\n导入前会自动备份当前数据。\n导入后可撤销一次。"):
            return

        success, msg = self.session_manager.commit_import(
            self.current_session,
            self.current_user,
            self.is_supervisor
        )

        if success:
            messagebox.showinfo("导入成功", msg)
            self.refresh_device_list()
            self.refresh_log()
            self.current_session = None
            self.session_id_label.config(text="无活动会话")
            self.session_file_label.config(text="-")
            self.session_status_label.config(text="-")
            self.session_operator_label.config(text="-")
        else:
            messagebox.showerror("导入失败", msg)

    def undo_session_import(self):
        if not self.current_session:
            messagebox.showwarning("提示", "没有活动会话")
            return

        if not self.current_session.can_undo:
            messagebox.showwarning("提示", "此会话不支持撤销")
            return

        if not messagebox.askyesno("确认撤销", "确定要撤销导入吗？\n数据将恢复到导入前的状态。"):
            return

        success, msg = self.session_manager.undo_import(self.current_session)

        if success:
            messagebox.showinfo("撤销成功", msg)
            self.service.devices = self.service.storage.load_devices()
            self.service.repair_records = self.service.storage.load_repair_records()
            self.service.approval_records = self.service.storage.load_approval_records()
            self.refresh_device_list()
            self.refresh_log()
        else:
            messagebox.showerror("撤销失败", msg)

    def cancel_current_session(self):
        if not self.current_session:
            messagebox.showwarning("提示", "没有活动会话")
            return

        if self.current_session.committed:
            messagebox.showwarning("提示", "已提交的会话不能取消")
            return

        if not messagebox.askyesno("确认取消", "确定要取消此会话吗？"):
            return

        success, msg = self.session_manager.cancel_session(self.current_session.session_id)
        if success:
            messagebox.showinfo("提示", "会话已取消")
            self.current_session = None
            self.session_id_label.config(text="无活动会话")
            self.session_file_label.config(text="-")
            self.session_status_label.config(text="-")
            self.session_operator_label.config(text="-")
        else:
            messagebox.showerror("错误", msg)
        
    def _check_rollback_on_startup(self):
        rollback_info = self.import_service.get_rollback_info()
        if rollback_info:
            self.after_startup_check = True

    def _check_pending_session(self):
        session = self.session_manager.check_active_session()
        if session:
            resume = messagebox.askyesno(
                "发现未完成的会话",
                f"发现未完成的导入会话:\n"
                f"会话ID: {session.session_id}\n"
                f"文件: {session.file_path}\n"
                f"操作人: {session.operator}\n\n"
                f"是否继续此会话？"
            )
            if resume:
                self.current_session = session
                self.notebook.select(self.session_frame)
                self._load_session_view(session)
            else:
                self.session_manager.cancel_session(session.session_id)
        
    def _update_rollback_info(self):
        rollback_info = self.import_service.get_rollback_info()
        if rollback_info:
            self.rollback_info_label.config(
                text=f"可撤销: 导入 {rollback_info['import_log_id']} ({rollback_info['import_time']})"
            )
        else:
            self.rollback_info_label.config(text="当前没有可撤销的导入记录")
        
    def verify_user(self):
        user = self.user_entry.get().strip()
        if not user:
            messagebox.showwarning("提示", "请输入操作人姓名")
            return
        
        self.current_user = user
        self.is_supervisor = user in SUPERVISORS
        
        if self.is_supervisor:
            self.user_status_label.config(text=f"已验证 - 主管 (可导入)", foreground="green")
        else:
            self.user_status_label.config(text=f"已验证 - 普通人员 (仅预览)", foreground="orange")
        
    def browse_import_file(self):
        file_path = filedialog.askopenfilename(
            filetypes=[("JSON文件", "*.json"), ("CSV文件", "*.csv"), ("所有文件", "*.*")]
        )
        if file_path:
            self.import_file_entry.delete(0, tk.END)
            self.import_file_entry.insert(0, file_path)
        
    def preview_import(self):
        if not self.current_user:
            messagebox.showwarning("提示", "请先验证身份")
            return
        
        file_path = self.import_file_entry.get().strip()
        if not file_path:
            messagebox.showwarning("提示", "请选择导入文件")
            return
        
        if not self.is_supervisor:
            messagebox.showinfo("提示", "您是普通人员，只能预览导入结果，无法执行导入")
        
        preview_info, error = self.import_service.preview_import(file_path, self.current_user, self.is_supervisor)
        
        if error:
            messagebox.showerror("预检失败", error)
            return
        
        self.preview_info = preview_info
        self.preview_info['file_path'] = file_path
        preview = preview_info['preview']
        
        for tree in [self.new_tree, self.overwrite_tree, self.conflict_tree, self.invalid_tree]:
            for item in tree.get_children():
                tree.delete(item)
        
        for row in preview.new_rows:
            row_type, row_id, detail = self._parse_preview_row(row)
            self.new_tree.insert("", tk.END, values=(row_type, row_id, detail))
        
        for row in preview.overwrite_rows:
            row_type, row_id, detail = self._parse_preview_row(row)
            self.overwrite_tree.insert("", tk.END, values=(row_type, row_id, detail))
        
        for row in preview.conflict_rows:
            row_type, row_id, _ = self._parse_preview_row(row)
            self.conflict_tree.insert("", tk.END, values=(row_type, row_id, row.reason))
        
        for row in preview.invalid_rows:
            row_type, row_id, _ = self._parse_preview_row(row)
            self.invalid_tree.insert("", tk.END, values=(row_type, row_id, row.reason))
        
        self.preview_notebook.tab(self.new_rows_frame, text=f"新增 ({len(preview.new_rows)})")
        self.preview_notebook.tab(self.overwrite_rows_frame, text=f"覆盖 ({len(preview.overwrite_rows)})")
        self.preview_notebook.tab(self.conflict_rows_frame, text=f"冲突 ({len(preview.conflict_rows)})")
        self.preview_notebook.tab(self.invalid_rows_frame, text=f"无效 ({len(preview.invalid_rows)})")
        
        summary = f"预检完成！\n文件类型: {preview_info['file_type']}\n"
        summary += f"新增: {len(preview.new_rows)} 条\n"
        summary += f"覆盖: {len(preview.overwrite_rows)} 条\n"
        summary += f"冲突: {len(preview.conflict_rows)} 条\n"
        summary += f"无效: {len(preview.invalid_rows)} 条\n"
        
        if preview.invalid_rows:
            summary += "\n警告: 存在无效记录，请检查'无效'标签页"
        
        if not self.is_supervisor:
            summary += "\n\n注意: 您是普通人员，只能预览，无法执行导入"
        
        messagebox.showinfo("预检结果", summary)
        
    def _parse_preview_row(self, row):
        data = row.row_data
        if 'name' in data and 'status' in data:
            return "设备", data.get('device_id', ''), f"{data.get('name', '')} - {data.get('status', '')}"
        elif 'repair_desc' in data:
            return "维修", data.get('record_id', ''), f"{data.get('device_id', '')} - {data.get('repair_desc', '')[:30]}"
        elif 'approval_type' in data:
            return "审批", data.get('record_id', ''), f"{data.get('device_id', '')} - {data.get('approval_type', '')}"
        else:
            return "未知", '', str(data)
        
    def execute_import(self):
        if not self.current_user:
            messagebox.showwarning("提示", "请先验证身份")
            return
        
        if not self.is_supervisor:
            messagebox.showwarning("权限不足", "只有主管才能执行导入操作")
            return
        
        if not self.preview_info:
            messagebox.showwarning("提示", "请先执行预检")
            return
        
        preview = self.preview_info['preview']
        
        if preview.invalid_rows:
            if not messagebox.askyesno("警告", f"存在 {len(preview.invalid_rows)} 条无效记录，是否跳过这些记录继续导入？"):
                return
        
        if not messagebox.askyesno("确认导入", "确定要执行导入吗？\n导入前会自动备份当前数据。"):
            return
        
        success, msg = self.import_service.execute_import(self.preview_info, skip_conflicts=True)
        
        if success:
            messagebox.showinfo("导入成功", msg)
            self.refresh_device_list()
            self.refresh_log()
            self._update_rollback_info()
            self.preview_info = None
        else:
            messagebox.showerror("导入失败", msg)
        
    def rollback_import(self):
        if not self.current_user:
            messagebox.showwarning("提示", "请先验证身份")
            return
        
        if not self.is_supervisor:
            messagebox.showwarning("权限不足", "只有主管才能执行撤销操作")
            return
        
        rollback_info = self.import_service.get_rollback_info()
        if not rollback_info:
            messagebox.showinfo("提示", "没有可撤销的导入记录")
            return
        
        if not messagebox.askyesno("确认撤销", f"确定要撤销导入 {rollback_info['import_log_id']} 吗？\n数据将恢复到 {rollback_info['import_time']}"):
            return
        
        success, msg = self.import_service.rollback()
        
        if success:
            self.service.devices = self.service.storage.load_devices()
            self.service.repair_records = self.service.storage.load_repair_records()
            self.service.approval_records = self.service.storage.load_approval_records()
            
            messagebox.showinfo("撤销成功", msg)
            self.refresh_device_list()
            self.refresh_log()
            self._update_rollback_info()
        else:
            messagebox.showerror("撤销失败", msg)
        
    def setup_log_tab(self):
        self.log_tree = ttk.Treeview(self.log_frame, columns=("类型", "设备ID", "内容", "操作人", "时间"), show="headings")
        self.log_tree.heading("类型", text="记录类型")
        self.log_tree.heading("设备ID", text="设备ID")
        self.log_tree.heading("内容", text="内容")
        self.log_tree.heading("操作人", text="操作人")
        self.log_tree.heading("时间", text="时间")
        
        self.log_tree.column("类型", width=100)
        self.log_tree.column("设备ID", width=100)
        self.log_tree.column("内容", width=400)
        self.log_tree.column("操作人", width=100)
        self.log_tree.column("时间", width=150)
        
        self.log_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.refresh_log()
        
    def refresh_device_list(self, event=None):
        for item in self.device_tree.get_children():
            self.device_tree.delete(item)
        
        devices = self.service.get_all_devices()
        filter_status = self.status_filter.get()
        
        for device in devices:
            if filter_status == "全部" or device.status == filter_status:
                self.device_tree.insert("", tk.END, values=(
                    device.device_id,
                    device.name,
                    device.status,
                    device.abnormal_desc,
                    device.update_time.split("T")[0] + " " + device.update_time.split("T")[1][:8]
                ))
        
    def refresh_log(self):
        for item in self.log_tree.get_children():
            self.log_tree.delete(item)
        
        repair_records = self.service.repair_records
        approval_records = self.service.approval_records
        
        all_records = []
        
        for r in repair_records:
            all_records.append(("维修记录", r.device_id, r.repair_desc, r.operator, r.repair_time))
        
        for a in approval_records:
            all_records.append(("审批记录", a.device_id, f"{a.approval_type}审批: {a.opinion}", a.approver, a.approve_time))
        
        all_records.sort(key=lambda x: x[4], reverse=True)
        
        for record in all_records:
            self.log_tree.insert("", tk.END, values=(
                record[0],
                record[1],
                record[2],
                record[3],
                record[4].split("T")[0] + " " + record[4].split("T")[1][:8]
            ))
        
    def get_selected_device_id(self):
        selected = self.device_tree.selection()
        if not selected:
            messagebox.showwarning("提示", "请先选择一个设备")
            return None
        item = self.device_tree.item(selected[0])
        return item["values"][0]
    
    def add_device(self):
        device_id = self.device_id_entry.get().strip()
        name = self.device_name_entry.get().strip()
        
        if not device_id or not name:
            messagebox.showwarning("提示", "请输入设备ID和名称")
            return
        
        success, msg = self.service.add_device(device_id, name)
        messagebox.showinfo("提示", msg)
        
        if success:
            self.device_id_entry.delete(0, tk.END)
            self.device_name_entry.delete(0, tk.END)
            self.refresh_device_list()
    
    def report_abnormal(self):
        device_id = self.get_selected_device_id()
        if not device_id:
            return
        
        device = self.service.find_device(device_id)
        if device.status != DeviceStatus.NORMAL.value:
            messagebox.showwarning("提示", "只有正常状态的设备才能报告异常")
            return
        
        abnormal_desc = simpledialog.askstring("报告异常", "请输入异常描述:")
        if not abnormal_desc:
            return
        
        success, msg = self.service.report_abnormal(device_id, abnormal_desc)
        messagebox.showinfo("提示", msg)
        self.refresh_device_list()
        self.refresh_log()
    
    def apply_stop(self):
        device_id = self.get_selected_device_id()
        if not device_id:
            return
        
        device = self.service.find_device(device_id)
        if device.status == DeviceStatus.STOPPED.value:
            messagebox.showwarning("提示", "设备已停机，不能重复停机")
            return
        
        if device.status != DeviceStatus.PENDING_STOP_APPROVAL.value:
            messagebox.showwarning("提示", "只有待停机审批状态的设备才能申请停机")
            return
        
        reason = simpledialog.askstring("申请停机", "请输入停机原因:")
        if not reason:
            return
        
        success, msg = self.service.apply_stop(device_id, reason)
        messagebox.showinfo("提示", msg)
        self.refresh_device_list()
        self.refresh_log()
    
    def start_repair(self):
        device_id = self.get_selected_device_id()
        if not device_id:
            return
        
        success, msg = self.service.start_repair(device_id, "", "")
        messagebox.showinfo("提示", msg)
        self.refresh_device_list()
    
    def complete_repair(self):
        device_id = self.get_selected_device_id()
        if not device_id:
            return
        
        repair_desc = simpledialog.askstring("完成维修", "请输入维修内容:")
        if not repair_desc:
            return
        
        operator = simpledialog.askstring("完成维修", "请输入维修人员:")
        if not operator:
            return
        
        success, msg = self.service.record_repair(device_id, repair_desc, operator)
        messagebox.showinfo("提示", msg)
        self.refresh_device_list()
        self.refresh_log()
    
    def approve_restart(self):
        device_id = self.get_selected_device_id()
        if not device_id:
            return
        
        device = self.service.find_device(device_id)
        if device.status != DeviceStatus.PENDING_RESTART_APPROVAL.value:
            messagebox.showwarning("提示", "只有待复机审批状态的设备才能批准复机")
            return
        
        repair_records = self.service.get_repair_records_by_device(device_id)
        if not repair_records:
            messagebox.showwarning("提示", "没有维修记录，不能批准复机")
            return
        
        supervisor_list = ", ".join(sorted(SUPERVISORS))
        approver = simpledialog.askstring("批准复机", f"请输入主管姓名（可审批人员：{supervisor_list}）:")
        if not approver:
            return
        
        if approver not in SUPERVISORS:
            messagebox.showwarning("权限不足", f"'{approver}'不是主管，无权批准复机。\n可审批主管：{supervisor_list}")
            return
        
        opinion = simpledialog.askstring("批准复机", "请输入审批意见:")
        if not opinion:
            return
        
        success, msg = self.service.approve_restart(device_id, opinion, approver)
        messagebox.showinfo("提示", msg)
        self.refresh_device_list()
        self.refresh_log()
    
    def enter_observation(self):
        device_id = self.get_selected_device_id()
        if not device_id:
            return
        
        success, msg = self.service.enter_observation(device_id)
        messagebox.showinfo("提示", msg)
        self.refresh_device_list()
    
    def exit_observation(self):
        device_id = self.get_selected_device_id()
        if not device_id:
            return
        
        success, msg = self.service.exit_observation(device_id)
        messagebox.showinfo("提示", msg)
        self.refresh_device_list()
    
    def view_repair_records(self):
        device_id = self.get_selected_device_id()
        if not device_id:
            return
        
        records = self.service.get_repair_records_by_device(device_id)
        if not records:
            messagebox.showinfo("提示", "该设备没有维修记录")
            return
        
        info = "\n".join([f"维修时间: {r.repair_time}\n维修人员: {r.operator}\n维修内容: {r.repair_desc}\n---" for r in records])
        messagebox.showinfo("维修记录", info)
    
    def view_approval_records(self):
        device_id = self.get_selected_device_id()
        if not device_id:
            return
        
        records = self.service.get_approval_records_by_device(device_id)
        if not records:
            messagebox.showinfo("提示", "该设备没有审批记录")
            return
        
        info = "\n".join([f"审批时间: {r.approve_time}\n审批类型: {r.approval_type}\n审批人: {r.approver}\n审批意见: {r.opinion}\n---" for r in records])
        messagebox.showinfo("审批记录", info)
    
    def delete_device(self):
        device_id = self.get_selected_device_id()
        if not device_id:
            return
        
        if not messagebox.askyesno("确认删除", f"确定要删除设备 {device_id} 吗?"):
            return
        
        self.service.devices = [d for d in self.service.devices if d.device_id != device_id]
        self.service.save_all()
        messagebox.showinfo("提示", "设备删除成功")
        self.refresh_device_list()
        self.refresh_log()
    
    def browse_export_dir(self):
        dir_path = filedialog.askdirectory()
        if dir_path:
            self.export_dir_entry.delete(0, tk.END)
            self.export_dir_entry.insert(0, dir_path)
    
    def save_config(self):
        export_dir = self.export_dir_entry.get().strip()
        threshold_low = self.threshold_low_entry.get().strip()
        threshold_high = self.threshold_high_entry.get().strip()
        
        try:
            threshold_low = int(threshold_low) if threshold_low else None
            threshold_high = int(threshold_high) if threshold_high else None
        except ValueError:
            messagebox.showwarning("提示", "阈值必须是整数")
            return
        
        old_dir = self.service.config.export_dir
        success, msg, new_dir = self.service.update_config(export_dir, threshold_low, threshold_high)
        messagebox.showinfo("提示", msg)
        
        if not success:
            self.export_dir_entry.delete(0, tk.END)
            self.export_dir_entry.insert(0, old_dir)
    
    def export_records(self):
        success, msg = self.service.export_records()
        messagebox.showinfo("导出结果", msg)


if __name__ == "__main__":
    root = tk.Tk()
    app = DeviceInspectionApp(root)
    root.mainloop()
