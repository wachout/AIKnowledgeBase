# 文件分析智能体 (File Analysis Agent)

这是一个基于 LangChain 和 LangGraph 的智能文件分析工具，支持多种文件格式和输入方式。

## 功能特性

- ✅ **多种输入方式**：支持文件路径字符串或直接文本内容输入
- ✅ **智能文件格式识别**：自动检测并解析不同类型的文件
- ✅ **内容长度限制**：文件过长时自动截取前5000字进行分析
- ✅ **结构化输出**：基于 Pydantic 的标准化分析结果
- ✅ **关键词提取**：自动提取关键词、关键短语和实体
- ✅ **详细分析报告**：生成全面的文件分析报告

## 支持的文件格式

### 无需额外依赖
- **纯文本格式**：`.txt`, `.md`, `.py`, `.js`, `.ts`, `.java`, `.cpp`, `.c`, `.cs`, `.php`, `.rb`, `.go`, `.rs`, `.html`, `.css`, `.sql`, `.sh`, `.bash`, `.json`, `.xml`, `.yaml`, `.yml`

### 需要安装额外库
- **Word文档**：`.docx` - 需要 `python-docx`
- **PowerPoint演示**：`.pptx`, `.ppt` - 需要 `python-pptx`
- **PDF文档**：`.pdf` - 需要 `PyMuPDF` (推荐) 或 `PyPDF2`

## 安装依赖

```bash
# 基础依赖（必需）
pip install langchain langchain-openai langchain-community langgraph pydantic python-dotenv

# 可选依赖（用于支持更多文件格式）
pip install python-docx      # 支持 .docx 文件
pip install python-pptx      # 支持 .pptx/.ppt 文件
pip install PyMuPDF          # 支持 .pdf 文件（推荐）
# 或
pip install PyPDF2          # 支持 .pdf 文件（备选）
```

## 使用方法

### 1. 分析文件路径

```python
from Agent.FileAnalyseAgent import analyze_file

# 分析文件
result = analyze_file("/path/to/your/file.pdf")

# 访问分析结果
print(f"文件名: {result.metadata.file_name}")
print(f"内容类型: {result.content_analysis.content_type}")
print(f"关键词: {result.keyword_analysis.keywords}")
print(f"完整分析: {result.full_analysis}")
```

### 2. 分析文本内容

```python
from Agent.FileAnalyseAgent import analyze_content

# 直接分析文本内容
content = "这是要分析的文本内容..."
result = analyze_content(content, "example.txt")

print(f"主题: {result.content_analysis.main_topics}")
```

### 3. 字典输入方式

```python
from Agent.FileAnalyseAgent import run_file_analysis

# 使用字典提供内容
input_data = {
    "file_path": "report.txt",
    "content": "这是文档内容..."
}

result = run_file_analysis(input_data)
if result["success"]:
    analysis = result["result"]
    print(f"分析成功: {analysis.metadata.file_name}")
```

### 4. 查看支持的格式

```python
from Agent.FileAnalyseAgent import get_supported_formats

formats = get_supported_formats()
for ext, desc in formats.items():
    print(f"{ext}: {desc}")
```

## 输出结构

分析结果包含以下信息：

```python
{
    "metadata": {
        "file_name": "example.pdf",
        "file_extension": ".pdf",
        "file_size": 1024,
        "content_length": 5000
    },
    "content_analysis": {
        "content_type": "document",
        "language": None,
        "main_topics": ["主题1", "主题2"],
        "summary": "内容摘要..."
    },
    "keyword_analysis": {
        "keywords": ["关键词1", "关键词2"],
        "key_phrases": ["关键短语1"],
        "entities": ["实体1"]
    },
    "full_analysis": "详细的分析报告文本..."
}
```

## 配置说明

在项目根目录创建 `.env` 文件：

```env
# 通义千问配置
QWEN_API_KEY=your_qwen_api_key
QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1

# 或 DeepSeek 配置
DEEPSEEK_API_KEY=your_deepseek_api_key
DEEPSEEK_URL_BASE=https://api.deepseek.com/v1
DEEPSEEK_MODEL_NAME=deepseek-reasoner
```

## 注意事项

1. **文件大小限制**：默认分析前5000字符的内容
2. **编码支持**：自动尝试UTF-8和GBK编码
3. **库依赖**：某些文件格式需要安装额外的Python库
4. **错误处理**：提供详细的错误信息和异常处理

## 扩展开发

如需添加新的文件格式支持：

1. 在 `parse_file_by_format()` 函数中添加新的格式处理逻辑
2. 更新 `get_supported_formats()` 函数
3. 添加相应的库导入和可用性检查

## 许可证

本项目遵循项目的许可证协议。
