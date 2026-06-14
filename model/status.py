from enum import Enum


class DeviceStatus(Enum):
    NORMAL = "正常"
    PENDING_STOP_APPROVAL = "待停机审批"
    STOPPED = "已停机"
    UNDER_REPAIR = "维修中"
    PENDING_RESTART_APPROVAL = "待复机审批"
    RESTARTED = "已复机"
    OBSERVATION = "复发观察"

    @classmethod
    def values(cls):
        return [status.value for status in cls]


class ApprovalType(Enum):
    STOP = "停机"
    RESTART = "复机"
