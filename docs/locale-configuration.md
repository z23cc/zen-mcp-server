# 🌍 语言配置 (LOCALE Configuration)

Zen MCP Server 支持多语言响应配置，允许您设置AI工具使用特定语言进行回复。

## 📋 配置方法

### 环境变量设置

通过设置 `LOCALE` 环境变量来配置语言：

```bash
# 设置为中文（默认）
export LOCALE=zh-CN

# 设置为英文
export LOCALE=en-US

# 设置为日文
export LOCALE=ja-JP
```

### 在 .env 文件中配置

您也可以在项目根目录的 `.env` 文件中设置：

```env
# 语言配置
LOCALE=zh-CN
```

## 🌐 支持的语言

| 语言代码 | 语言名称 | 指令示例 |
|---------|---------|---------|
| `zh-CN` | 中文（简体） | 请始终用中文回复。 |
| `zh-TW` | 中文（繁體） | 請始終用繁體中文回復。 |
| `en-US` | English | Always respond in English. |
| `ja-JP` | 日本語 | 常に日本語で回答してください。 |
| `ko-KR` | 한국어 | 항상 한국어로 답변해 주세요. |
| `fr-FR` | Français | Répondez toujours en français. |
| `de-DE` | Deutsch | Antworten Sie immer auf Deutsch. |
| `es-ES` | Español | Responde siempre en español. |
| `it-IT` | Italiano | Rispondi sempre in italiano. |
| `pt-PT` | Português | Responda sempre em português. |

## ⚙️ 工作原理

1. **自动注入**: 语言指令会自动添加到所有AI工具的系统提示词前面
2. **动态切换**: 可以通过修改环境变量动态切换语言（需要重启服务）
3. **保持功能**: 语言设置不会影响工具的分析能力，只改变响应语言

## 🔧 默认配置

- **默认语言**: `zh-CN` (中文简体)
- **空值处理**: 如果 `LOCALE` 为空，则不添加语言指令
- **未知语言**: 对于未预定义的语言代码，会生成通用格式的指令

## 📝 使用示例

### 启动服务时设置语言

```bash
# 使用中文
LOCALE=zh-CN python server.py

# 使用英文
LOCALE=en-US python server.py

# 使用日文
LOCALE=ja-JP python server.py
```

### 在代码中检查当前语言设置

```python
from config import LOCALE
print(f"当前语言设置: {LOCALE}")
```

## 🧪 测试语言配置

运行演示脚本查看所有支持的语言：

```bash
python demo_locale.py
```

## 📚 技术细节

### 实现位置

- **配置文件**: `config.py` - 定义 `LOCALE` 变量
- **基础工具**: `tools/shared/base_tool.py` - `get_language_instruction()` 方法
- **简单工具**: `tools/simple/base.py` - 系统提示词生成
- **工作流工具**: `tools/workflow/workflow_mixin.py` - 专家分析提示词生成

### 语言指令注入点

语言指令会在以下位置自动注入：

1. **SimpleTool**: 在 `execute()` 方法中生成系统提示词时
2. **WorkflowTool**: 在专家分析阶段生成系统提示词时

### 自定义语言支持

如果需要添加新的语言支持，请修改 `tools/shared/base_tool.py` 中的 `locale_map` 字典：

```python
locale_map = {
    # 现有语言...
    "your-LANG": "Your language instruction here.",
}
```

## 🔄 更新历史

- **v5.7.0+**: 添加 LOCALE 配置支持
- **默认设置**: 中文（zh-CN）作为默认语言

## 💡 最佳实践

1. **一致性**: 在整个项目中使用相同的语言设置
2. **文档**: 在团队中明确语言配置约定
3. **测试**: 使用不同语言设置测试工具功能
4. **备份**: 保留英文作为备用语言选项
