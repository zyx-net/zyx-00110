import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from service.device_service import DeviceService, SUPERVISORS
from model.status import DeviceStatus


class DeviceInspectionApp:
    def __init__(self, root):
        self.root = root
        self.root.title("设备巡检停复机登记系统")
        self.root.geometry("1200x800")
        
        self.service = DeviceService()
        
        self.setup_ui()
        
    def setup_ui(self):
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.device_frame = ttk.Frame(self.notebook)
        self.config_frame = ttk.Frame(self.notebook)
        self.log_frame = ttk.Frame(self.notebook)
        
        self.notebook.add(self.device_frame, text="设备管理")
        self.notebook.add(self.config_frame, text="系统配置")
        self.notebook.add(self.log_frame, text="历史日志")
        
        self.setup_device_tab()
        self.setup_config_tab()
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
