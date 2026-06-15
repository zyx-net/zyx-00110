import os
import shutil
from datetime import datetime
from model.device import RollbackState
from storage.json_storage import JSONStorage


class BackupService:
    def __init__(self, storage=None):
        self.storage = storage or JSONStorage()
        self.data_dir = self.storage.data_dir
        self.backup_dir = os.path.join(self.data_dir, "backups")

    def _ensure_backup_dir(self):
        if not os.path.exists(self.backup_dir):
            os.makedirs(self.backup_dir)

    def create_backup(self, import_log_id):
        self._ensure_backup_dir()
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_name = f"backup_{timestamp}_{import_log_id}"
        backup_path = os.path.join(self.backup_dir, backup_name)
        
        counter = 1
        while os.path.exists(backup_path):
            backup_name = f"backup_{timestamp}_{import_log_id}_{counter}"
            backup_path = os.path.join(self.backup_dir, backup_name)
            counter += 1
        
        try:
            shutil.copytree(self.data_dir, backup_path, ignore=shutil.ignore_patterns('backups', '*.bak'))
            
            files_backed_up = []
            for f in os.listdir(backup_path):
                if f.endswith('.json'):
                    files_backed_up.append(f)
            
            rollback_state = RollbackState(
                backup_path=backup_path,
                import_log_id=import_log_id,
                import_time=datetime.now().isoformat(),
                can_rollback=True
            )
            self.storage.save_rollback_state(rollback_state)
            
            return True, backup_path, files_backed_up
        except Exception as e:
            return False, "", str(e)

    def rollback(self):
        rollback_state = self.storage.load_rollback_state()
        
        if not rollback_state.can_rollback:
            return False, "没有可撤销的导入记录"
        
        if not os.path.exists(rollback_state.backup_path):
            return False, f"备份目录不存在: {rollback_state.backup_path}"
        
        try:
            for f in os.listdir(self.data_dir):
                if f != 'backups' and f != 'rollback_state.json':
                    file_path = os.path.join(self.data_dir, f)
                    if os.path.isfile(file_path):
                        os.remove(file_path)
            
            for f in os.listdir(rollback_state.backup_path):
                src = os.path.join(rollback_state.backup_path, f)
                dst = os.path.join(self.data_dir, f)
                if os.path.isfile(src):
                    shutil.copy2(src, dst)
            
            new_rollback_state = RollbackState(can_rollback=False)
            self.storage.save_rollback_state(new_rollback_state)
            
            return True, f"已撤销导入 {rollback_state.import_log_id}，数据已恢复到 {rollback_state.import_time}"
        except Exception as e:
            return False, f"撤销失败: {str(e)}"

    def can_rollback(self):
        rollback_state = self.storage.load_rollback_state()
        return rollback_state.can_rollback

    def get_rollback_info(self):
        rollback_state = self.storage.load_rollback_state()
        if rollback_state.can_rollback:
            return {
                "import_log_id": rollback_state.import_log_id,
                "import_time": rollback_state.import_time,
                "backup_path": rollback_state.backup_path
            }
        return None

    def clear_rollback_state(self):
        new_rollback_state = RollbackState(can_rollback=False)
        self.storage.save_rollback_state(new_rollback_state)
