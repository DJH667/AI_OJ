# 实验报告素材归档（报告 §成果展示 引用）

> 约定（评审发现 #5，2026-09-05）：每日边界用例/截图统一在此登记，避免 9.10 突击收集。
> 截图由人工在 uvicorn + 页面/curl 环境采集后存入本目录；JSON 摘录可在 WSL 复现命令后直接拷贝。

## D4：MLE 内存超限样例（真实评测）

**复现**：
```bash
# backend/ 目录（WSL venv）
wsl ~/oj-venv/bin/python -m uvicorn main:app --port 8000
# 建题 memory_limit=16 time_limit=5 单测例；提交：x = bytearray(64*1024*1024); print(len(x))
# 等待评测完成，读取 submissions/{id}.json
```

**结果摘录**（submission JSON，字段示意）：
```json
{
  "submission_id": "1",
  "status": "success",
  "score": 0,
  "counts": 10,
  "details": [
    { "id": 1, "result": "MLE", "time": 0.083, "memory": 23.6 }
  ]
}
```

**截图建议**：① 列表接口返回该提交（pending→success）；② `details` 中 MLE 行与 memory 峰值；③（可选）Step5 log 页面（D5 后）。

---
*待补：D5 可见性三态、D7 前端页面、越权 401/403 等截图登记处（后续轮次追加）。*
