# {{TASK_ID}} 测试报告

- 任务名称：{{TASK_NAME}}
- 任务分支：`{{BRANCH}}`

## 实际执行命令

{{TEST_COMMANDS}}

## 结果摘要

- 通过：{{PASSED_COUNT}}
- 失败：{{FAILED_COUNT}}
- 跳过：{{SKIPPED_COUNT}}
- 专项测试：{{FOCUSED_TEST_RESULT}}
- Excel 测试：{{EXCEL_TEST_RESULT}}
- WPS 测试：{{WPS_TEST_RESULT}}
- 真实 API 调用次数：{{REAL_API_CALL_COUNT}}
- GitHub Actions结果：以Pull Request当前HEAD对应的Checks页面为准。

## 未执行测试及原因

{{NOT_RUN_TESTS}}

## 失败或警告

{{TEST_WARNINGS}}
