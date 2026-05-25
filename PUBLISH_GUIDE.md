# AI Output Guard PyPI 发布指南

## 前置条件

- Python 3.9+
- pip
- PyPI 账号（https://pypi.org/account/register/）

## 步骤 1: 安装构建工具

```bash
cd ai-output-guard
pip install build twine
```

## 步骤 2: 构建包

```bash
# 清理旧构建
rm -rf build dist *.egg-info

# 构建 wheel 和 sdist
python -m build
```

构建成功后，会生成：
- `dist/ai_output_guard-0.1.0-py3-none-any.whl`
- `dist/ai_output_guard-0.1.0.tar.gz`

## 步骤 3: 检查包

```bash
twine check dist/*
```

应该看到：
```
Checking dist/ai_output_guard-0.1.0-py3-none-any.whl: PASSED
Checking dist/ai_output_guard-0.1.0.tar.gz: PASSED
```

## 步骤 4: 上传到 Test PyPI（可选但推荐）

```bash
# 配置 Test PyPI（只需一次）
twine upload --repository testpypi dist/*

# 测试安装
pip install --index-url https://test.pypi.org/simple/ agentguard
```

## 步骤 5: 上传到正式 PyPI

```bash
# 配置 PyPI API Token（只需一次）
# 访问 https://pypi.org/manage/account/token/ 生成 Token
# 然后配置 ~/.pypirc：
# [pypi]
# username = __token__
# password = pypi-AgEIcHlwaS5vcmcCJD...

# 上传
twine upload dist/*
```

## 步骤 6: 验证发布

```bash
# 等待几分钟让 PyPI 索引更新
pip install ai-output-guard

# 测试 CLI
agentguard --help

# 测试 Python API
python -c "from agentguard import Guard; print('OK')"
```

## 发布后的 Git 操作

```bash
# 打标签
git tag v0.1.0
git push origin v0.1.0

# 创建 GitHub Release
git push
```

## 常见问题

### 1. 包名已被占用
如果 `agentguard` 已被占用，考虑：
- `agent-guard`
- `ai-guard`
- `llm-guard`
- `agentguard-py`

在发布前检查：https://pypi.org/project/agentguard/

### 2. 版本号冲突
每次发布必须递增版本号：
```
0.1.0 → 0.1.1 (patch)
0.1.0 → 0.2.0 (minor)
0.1.0 → 1.0.0 (major)
```

### 3. 构建失败
确保 `src/agentguard/` 目录结构正确：
```
src/agentguard/
├── __init__.py
├── guard.py
├── schema_guard.py
├── semantic_guard.py
├── policy_guard.py
├── result.py
├── config.py
├── errors.py
├── cli/
├── api/
├── mcp/
├── proxy/
├── billing/
├── fix/
├── semantic/
└── policy/
```

## 快速发布脚本

已为你准备 `scripts/release.sh`：

```bash
./scripts/release.sh
```

这个脚本会：
1. 运行测试
2. 构建包
3. 检查包
4. 提示上传到 PyPI
