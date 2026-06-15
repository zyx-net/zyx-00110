#!/usr/bin/env python
import os
import sys
import subprocess
import json
from datetime import datetime


def run_command(cmd, cwd=None):
    """运行命令并返回退出码、输出和错误"""
    try:
        result = subprocess.run(cmd, shell=True, cwd=cwd, 
                               capture_output=True, text=True, timeout=120)
        return {
            'exit_code': result.returncode,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'success': result.returncode == 0
        }
    except subprocess.TimeoutExpired:
        return {
            'exit_code': -1,
            'stdout': '',
            'stderr': 'Command timeout',
            'success': False
        }
    except Exception as e:
        return {
            'exit_code': -2,
            'stdout': '',
            'stderr': str(e),
            'success': False
        }


def run_test_module(module_name, cwd=None):
    """运行单个测试模块"""
    print(f"\n{'='*60}")
    print(f"Running test: {module_name}")
    print(f"{'='*60}")
    
    result = run_command(f'python -m unittest {module_name} -v', cwd=cwd)
    
    print("STDOUT:")
    print(result['stdout'])
    if result['stderr']:
        print("STDERR:")
        print(result['stderr'])
    
    return result


def run_test_script(script_path, cwd=None):
    """运行测试脚本（非unittest格式）"""
    print(f"\n{'='*60}")
    print(f"Running script: {os.path.basename(script_path)}")
    print(f"{'='*60}")
    
    result = run_command(f'python "{script_path}"', cwd=cwd)
    
    print("STDOUT:")
    print(result['stdout'])
    if result['stderr']:
        print("STDERR:")
        print(result['stderr'])
    
    return result


def main():
    test_results = []
    all_passed = True
    start_time = datetime.now()
    
    print(f"Regression Test Suite Started at {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)
    
    # 运行失败会话测试（unittest格式）
    failed_session_result = run_test_module('test_failed_session', cwd=os.path.dirname(__file__))
    test_results.append({
        'test_name': 'failed_session_tests',
        'success': failed_session_result['success'],
        'exit_code': failed_session_result['exit_code'],
        'stdout': failed_session_result['stdout'],
        'stderr': failed_session_result['stderr']
    })
    if not failed_session_result['success']:
        all_passed = False
    
    # 运行现有的回归测试脚本（非unittest格式）
    regression_test_path = os.path.join(os.path.dirname(__file__), 'test_regression.py')
    if os.path.exists(regression_test_path):
        result = run_test_script(regression_test_path, cwd=os.path.dirname(__file__))
        test_results.append({
            'test_name': 'test_regression',
            'success': result['success'],
            'exit_code': result['exit_code'],
            'stdout': result['stdout'],
            'stderr': result['stderr']
        })
        if not result['success']:
            all_passed = False
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    print("\n" + "="*70)
    print("Regression Test Summary")
    print("="*70)
    
    for result in test_results:
        status = "PASSED" if result['success'] else "FAILED"
        print(f"  {result['test_name']}: {status} (exit code: {result['exit_code']})")
    
    print(f"\nTotal duration: {duration:.2f} seconds")
    
    # 生成测试报告
    report = {
        'run_time': end_time.isoformat(),
        'duration_seconds': duration,
        'all_passed': all_passed,
        'total_tests': len(test_results),
        'passed_tests': sum(1 for r in test_results if r['success']),
        'failed_tests': sum(1 for r in test_results if not r['success']),
        'results': test_results
    }
    
    report_path = os.path.join(os.path.dirname(__file__), 'regression_report.json')
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"\nTest report saved to: {report_path}")
    
    # 根据结果设置退出码
    if all_passed:
        print("\n✓ All tests passed!")
        sys.exit(0)
    else:
        print("\n✗ Some tests failed!")
        sys.exit(1)


if __name__ == '__main__':
    main()
