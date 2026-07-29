# {{TASK_ID}} 安全报告

- 任务名称：{{TASK_NAME}}
- 任务分支：`{{BRANCH}}`

## 扫描结果

- Key 扫描：{{KEY_SCAN}}
- Token 和凭据扫描：{{CREDENTIAL_SCAN}}
- 业务 Excel 扫描：{{WORKBOOK_SCAN}}
- 地址、手机号和经纬度扫描：{{PERSONAL_DATA_SCAN}}
- 数据库、缓存和日志扫描：{{RUNTIME_DATA_SCAN}}
- EXE、ZIP、release 扫描：{{BINARY_SCAN}}
- 大于 50 MiB 文件扫描：{{LARGE_FILE_SCAN}}

## 推送结论

是否允许推送：{{PUSH_ALLOWED}}

报告不得记录完整敏感值；如有命中，仅记录规则、文件和行号。
