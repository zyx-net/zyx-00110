import os
import sys
import shutil
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from service.device_service import DeviceService, SUPERVISORS
from model.status import DeviceStatus


def clean_data():
    data_dir = "data"
    if os.path.exists(data_dir):
        for f in os.listdir(data_dir):
            os.remove(os.path.join(data_dir, f))


def test_main_flow():
    print("=" * 60)
    print("回归测试：异常登记 → 停机 → 维修 → 主管复机 → 导出 → 重启验证")
    print("=" * 60)
    
    clean_data()
    service = DeviceService()
    
    print("\n[步骤1] 添加设备")
    success, msg = service.add_device("TEST001", "测试设备A")
    assert success, f"添加设备失败: {msg}"
    device = service.find_device("TEST001")
    assert device.status == DeviceStatus.NORMAL.value, f"设备状态应为'正常',实际为'{device.status}'"
    print(f"  ✓ 设备添加成功，初始状态: {device.status}")
    
    print("\n[步骤2] 报告异常")
    success, msg = service.report_abnormal("TEST001", "轴承异响")
    assert success, f"报告异常失败: {msg}"
    device = service.find_device("TEST001")
    assert device.status == DeviceStatus.PENDING_STOP_APPROVAL.value, f"状态应为'待停机审批',实际为'{device.status}'"
    print(f"  ✓ 异常已报告，状态变更为: {device.status}")
    
    print("\n[步骤3] 申请停机")
    success, msg = service.apply_stop("TEST001", "需停机检修")
    assert success, f"申请停机失败: {msg}"
    device = service.find_device("TEST001")
    assert device.status == DeviceStatus.STOPPED.value, f"状态应为'已停机',实际为'{device.status}'"
    print(f"  ✓ 停机申请已提交，状态变更为: {device.status}")
    
    print("\n[步骤4] 开始维修")
    success, msg = service.start_repair("TEST001", "", "")
    assert success, f"开始维修失败: {msg}"
    device = service.find_device("TEST001")
    assert device.status == DeviceStatus.UNDER_REPAIR.value, f"状态应为'维修中',实际为'{device.status}'"
    print(f"  ✓ 维修已开始，状态变更为: {device.status}")
    
    print("\n[步骤5] 登记维修记录")
    success, msg = service.record_repair("TEST001", "更换轴承并润滑", "张三")
    assert success, f"登记维修记录失败: {msg}"
    device = service.find_device("TEST001")
    assert device.status == DeviceStatus.PENDING_RESTART_APPROVAL.value, f"状态应为'待复机审批',实际为'{device.status}'"
    records = service.get_repair_records_by_device("TEST001")
    assert len(records) == 1, f"应有1条维修记录，实际有{len(records)}条"
    print(f"  ✓ 维修记录已保存，状态变更为: {device.status}")
    
    print("\n[步骤6] 主管批准复机（使用主管'李四'）")
    success, msg = service.approve_restart("TEST001", "维修合格，同意复机", "李四")
    assert success, f"主管批准复机失败: {msg}"
    device = service.find_device("TEST001")
    assert device.status == DeviceStatus.RESTARTED.value, f"状态应为'已复机',实际为'{device.status}'"
    print(f"  ✓ 主管批准复机，状态变更为: {device.status}")
    
    print("\n[步骤7] 导出记录")
    export_dir = service.config.export_dir
    success, msg = service.export_records()
    assert success, f"导出记录失败: {msg}"
    print(f"  ✓ 记录导出成功")
    print(f"    {msg}")
    
    json_file = [f for f in os.listdir(export_dir) if f.endswith('.json')][-1]
    csv_file = [f for f in os.listdir(export_dir) if f.endswith('.csv')][-1]
    assert os.path.exists(os.path.join(export_dir, json_file)), "JSON文件未生成"
    assert os.path.exists(os.path.join(export_dir, csv_file)), "CSV文件未生成"
    print(f"  ✓ JSON和CSV文件均已生成")
    
    print("\n[步骤8] 重启后验证配置和数据持久化")
    del service
    service2 = DeviceService()
    
    device2 = service2.find_device("TEST001")
    assert device2 is not None, "重启后设备丢失"
    assert device2.status == DeviceStatus.RESTARTED.value, f"重启后状态应为'已复机',实际为'{device2.status}'"
    assert device2.abnormal_desc == "轴承异响", f"重启后异常描述丢失: {device2.abnormal_desc}"
    print(f"  ✓ 重启后设备状态正确: {device2.status}")
    
    records2 = service2.get_repair_records_by_device("TEST001")
    assert len(records2) == 1, f"重启后维修记录丢失，应有1条，实际有{len(records2)}条"
    print(f"  ✓ 重启后维修记录保留")
    
    approvals2 = service2.get_approval_records_by_device("TEST001")
    assert len(approvals2) >= 2, f"重启后审批记录丢失，应至少2条，实际有{len(approvals2)}条"
    print(f"  ✓ 重启后审批记录保留（共{len(approvals2)}条）")
    
    print("\n" + "=" * 60)
    print("主流程测试：✓ 全部通过")
    print("=" * 60)


def test_failure_cases():
    print("\n" + "=" * 60)
    print("失败链路测试")
    print("=" * 60)
    
    clean_data()
    service = DeviceService()
    
    print("\n[失败案例1] 已停机设备再次重复停机")
    service.add_device("FAIL001", "失败测试设备")
    service.report_abnormal("FAIL001", "测试异常")
    service.apply_stop("FAIL001", "测试停机")
    
    success, msg = service.apply_stop("FAIL001", "再次申请停机")
    assert not success, "重复停机应该失败但却成功了"
    assert "不能重复停机" in msg, f"错误信息不正确: {msg}"
    print(f"  ✓ 已停机设备不能重复停机，错误提示: {msg}")
    
    print("\n[失败案例2] 没有维修记录却申请复机（主管身份）")
    clean_data()
    service = DeviceService()
    service.add_device("FAIL002", "无维修记录设备")
    service.report_abnormal("FAIL002", "测试异常")
    service.apply_stop("FAIL002", "测试停机")
    service.start_repair("FAIL002", "", "")
    device = service.find_device("FAIL002")
    device.status = DeviceStatus.PENDING_RESTART_APPROVAL.value
    service.save_all()
    
    success, msg = service.approve_restart("FAIL002", "未填维修内容", "李四")
    assert not success, "没有维修记录不应该能复机"
    assert "没有维修记录" in msg, f"错误信息不正确: {msg}"
    print(f"  ✓ 没有维修记录不能复机，错误提示: {msg}")
    
    print("\n[失败案例3] 普通人员无权批准复机")
    clean_data()
    service = DeviceService()
    service.add_device("FAIL003", "普通人员测试")
    service.report_abnormal("FAIL003", "测试异常")
    service.apply_stop("FAIL003", "测试停机")
    service.start_repair("FAIL003", "", "")
    service.record_repair("FAIL003", "更换零件", "张三")
    
    success, msg = service.approve_restart("FAIL003", "普通人员尝试", "普通员工")
    assert not success, "普通人员不应该能批准复机"
    assert "不是主管" in msg or "无权批准" in msg, f"错误信息不正确: {msg}"
    print(f"  ✓ 普通人员'{'普通员工'}'无权批准复机，错误提示: {msg}")
    
    success, msg = service.approve_restart("FAIL003", "主管尝试", "张三")
    assert not success, "维修人员不应该也是主管"
    assert "不是主管" in msg or "无权批准" in msg, f"错误信息不正确: {msg}"
    print(f"  ✓ 维修人员'张三'也不是主管，错误提示: {msg}")
    
    success, msg = service.approve_restart("FAIL003", "正式主管", "admin")
    assert success, f"主管'admin'应该能批准复机: {msg}"
    print(f"  ✓ 主管'admin'可以批准复机")
    
    print("\n[失败案例4] 非法导出目录不冲掉原有配置")
    clean_data()
    service = DeviceService()
    old_dir = service.config.export_dir
    valid_dir = os.path.dirname(old_dir) if os.path.dirname(old_dir) else "."
    service.config.export_dir = valid_dir
    service.save_all()
    
    success, msg, returned_dir = service.update_config("C:\\完全不存在\\这个路径\\无效", 0, 100)
    assert not success, "非法目录应该保存失败"
    assert "不存在" in msg, f"错误信息不正确: {msg}"
    assert returned_dir == valid_dir, f"应该保留原配置'{valid_dir}'，实际为'{returned_dir}'"
    print(f"  ✓ 非法目录保存失败，原配置保留: {returned_dir}")
    
    config = service.get_config()
    assert config.export_dir == valid_dir, f"config.export_dir应为'{valid_dir}'，实际为'{config.export_dir}'"
    print(f"  ✓ 磁盘上的配置也未被修改")
    
    print("\n" + "=" * 60)
    print("失败链路测试：✓ 全部通过")
    print("=" * 60)


def test_nameerror_fix():
    print("\n" + "=" * 60)
    print("根因修复验证：NameError修复")
    print("=" * 60)
    
    clean_data()
    service = DeviceService()
    
    print("\n[验证1] update_config使用os.path.isdir不抛NameError")
    try:
        success, msg, _ = service.update_config("C:\\Windows\\System32", 0, 100)
        print(f"  ✓ update_config正常执行，未抛出NameError")
    except NameError as e:
        print(f"  ✗ 抛出NameError: {e}")
        raise
    
    print("\n[验证2] export_records使用json.dump和os.path.join不抛NameError")
    try:
        success, msg = service.export_records()
        print(f"  ✓ export_records正常执行，未抛出NameError")
    except NameError as e:
        print(f"  ✗ 抛出NameError: {e}")
        raise
    
    print("\n" + "=" * 60)
    print("NameError修复验证：✓ 全部通过")
    print("=" * 60)


if __name__ == "__main__":
    try:
        test_nameerror_fix()
        test_main_flow()
        test_failure_cases()
        print("\n" + "=" * 60)
        print("所有测试通过！")
        print("=" * 60)
    except AssertionError as e:
        print(f"\n✗ 测试失败: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ 异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
