# 解决 Windows RAG System 在 Light Mode 下元素颜色和文字对比度问题的改进计划

此计划旨在彻底解决 Windows RAG System 应用在切换到 Light Mode (浅色模式) 后，由于多处 inline styles / HTML 中硬编码了深色背景下的浅色文字 (如 `#e4e6eb`, `rgba(255, 255, 255, 0.4)` 等) 导致的元素无法正确变色、浅色文字几乎不可识别等 UI/UX 问题。

---

## User Review Required

> [!IMPORTANT]
> **全局 CSS 变量的引入**：
> 所有的颜色风格应该通过 CSS 变量统一管理。在 [theme.py](file:///C:/Users/Ivan/Desktop/Report%20QA/windows-rag-system/ui/theme.py) 中，我们会把当前主题下的各类颜色注入为 CSS 自定义属性 (例如 `--text0`, `--bg2` 等)。后续所有 HTML 渲染的样式中，硬编码的颜色必须替换为对应的 `var(--variable-name)`。

> [!WARNING]
> **图表组件的动态主题支持**：
> [report_generator.py](file:///C:/Users/Ivan/Desktop/Report%20QA/windows-rag-system/ui/report_generator.py) 中使用了 Chart.js 进行报表图表绘制。图表原本硬编码了深色的网格线和灰色标签，这在浅色模式下会导致对比度不足或显示错误。我们需要在渲染图表脚本时，根据 `st.session_state.is_dark` 动态传递 Chart.js 的配置参数。

---

## Open Questions

> [!NOTE]
> 目前没有阻塞性问题。我们将默认保持与原有 Fluent Design (Windows 风格) 的主色调与设计规范一致。

---

## Proposed Changes

### Theme & Styling Core (主题与样式核心)

#### [MODIFY] [theme.py](file:///C:/Users/Ivan/Desktop/Report%20QA/windows-rag-system/ui/theme.py)
- **CSS 变量导出**：在 `.stApp` 和 `:root` 中导出当前主题所对应的所有 CSS 自定义属性：
  ```css
  :root, .stApp {
      --bg0: {bg0};
      --bg1: {bg1};
      --bg2: {bg2};
      --text0: {text0};
      --text1: {text1};
      --text2: {text2};
      --border: {border};
      --border-hover: {border_hover};
      --accent: {accent};
      --accent-bg: {accent_bg};
      --card-bg: {card_bg};
      --card-hover: {card_hover};
      --input-bg: {input_bg};
      --sidebar-bg: {sidebar_bg};
  }
  ```
- **补全组件类样式定义**：
  在 `theme_css` 的 `<style>` 中，补全原本只定义了类但无具体 CSS 规则的组件样式：
  - `.card`, `.accent-card`：卡片背景与悬浮高亮（结合 `var(--card-bg)` 和 `var(--card-hover)`）。
  - `.compact-metric`：指标卡片的文字和数值对比度。
  - `.status-bar`：状态条容器的背景色和边框（使用 `var(--bg2)` 和 `var(--border)`）。
  - `.source-item`：文件列表项的字体颜色和排版。

---

### Main Application Layout (主应用布局)

#### [MODIFY] [app.py](file:///C:/Users/Ivan/Desktop/Report%20QA/windows-rag-system/app.py)
- **侧边栏 (Sidebar) 颜色适配**：
  - 替换硬编码的 `rgba(255,255,255,0.4)` (Document Intelligence 子标题) 为 `var(--text1)`。
  - 替换硬编码的 `rgba(255,255,255,0.3)` (版本说明/页脚信息) 为 `var(--text2)`。
- **页面标题及小标题适配**：
  - 将所有硬编码的 `<h3 style='color: #e4e6eb;'>` 改为使用 CSS 变量，例如 `<h3 style='color: var(--text0);'>` 或直接去除行内颜色，依赖全局 `h3` 样式。
- **文件列表 (Source Items) 适配**：
  - 替换 `<span style="float: right; color: rgba(255,255,255,0.5);">` 为使用 `var(--text1)` 或 `var(--text2)`，确保浅色模式下 "chunks" 数值清晰可见。
- **其他提示性卡片 (Alerts) 适配**：
  - 对于 API 未配置、模型未设置等警告性 `<div style="background: rgba(255,184,0,0.1); color: ...">`，优化其在浅色模式下的文字对比度，避免白底淡黄字的情况。

---

### Report Generation & Charts (报告生成与图表)

#### [MODIFY] [report_generator.py](file:///C:/Users/Ivan/Desktop/Report%20QA/windows-rag-system/ui/report_generator.py)
- **Chart.js 主题动态注入**：
  - 替换 `Chart.defaults.borderColor = 'rgba(255,255,255,0.08)'` 为基于主题状态的值。
  - 根据 `st.session_state.is_dark` 计算当前所用的 `chart_border_color`、`chart_text_color`、`chart_grid_color`，并在 JS spec template 中动态填充对应的色值。
- **报告模板 HTML 样式 (Markdown / iframe render)**：
  - 在渲染报告时，模板内部的 CSS 中包含大量的硬编码深色主题样式 (例如 `color: #e4e6eb;`, `h1 { color: #ffffff; }`)。
  - 提取报告预览区域的样式表，根据 `is_dark` 输出不同的色盘或直接应用全局 CSS 变量。
- **Copilot 对话及历史报告面板样式**：
  - 将 `No saved sessions`、`No messages`、`Saved Reports Library` 等处的硬编码浅色文字 (如 `rgba(255,255,255,0.4)`) 统一改用 `var(--text1)` / `var(--text2)`。

---

### API Configuration Dialog (API 设置对话框)

#### [MODIFY] [api_settings.py](file:///C:/Users/Ivan/Desktop/Report%20QA/windows-rag-system/ui/api_settings.py)
- **已配置服务商项背景适配**：
  - 替换第 296 行起的 `<div style="background: rgba(255,255,255,0.02); ...">` 容器背景为 `var(--bg2)` 或 `rgba(var(--bg-rgb), 0.05)`。
  - 替换 `Base URL` 和 `Models` 说明文字中硬编码的 `rgba(255,255,255,0.5)` 为 `var(--text1)` 或 `var(--text2)`，增强其在浅色弹窗中的可读性。

---

## Verification Plan

### Automated Tests
- 运行代码格式校验与基本的 Streamlit 静态代码检查：
  ```bash
  # 运行项目的基本 python 文件校验
  python -m py_compile windows-rag-system/app.py windows-rag-system/ui/*.py
  ```

### Manual Verification
1. **模式切换测试**：
   - 启动 Streamlit 应用，切换到 Documents 页面和 Reports 页面。
   - 点击侧边栏底部的 "Dark mode" 开关，在 Light mode 和 Dark mode 之间反复切换。
2. **文字可读性检查**：
   - 检查侧边栏的所有文字是否在白底/深底上清晰可辨。
   - 检查主内容区 "System Status" 下的卡片、文档管理列表、文件夹路径等处的文字与数量标识。
   - 检查 API 设置弹窗中的 "Service Providers" 列表文字对比度。
3. **图表及报告测试**：
   - 生成一份含有 Chart.js 统计图表的报告，观察 Light 模式下网格线和图表标题、轴标签是否能正确转换为深灰色/黑色。
