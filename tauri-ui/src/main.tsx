import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./styles/globals.css";

// Mock Tauri Bridge for non-Tauri browser testing environments
if (typeof window !== "undefined" && !(window as any).__TAURI_INTERNALS__) {
  (window as any).__TAURI_INTERNALS__ = {
    invoke: async (cmd: string, args?: any) => {
      console.log(`[Tauri Mock Invoke] cmd=${cmd}`, args);
      if (cmd === "query_rag") {
        // Return a mock response with the exact EFF data from the past 12 months (June 2025 to May 2026)
        // wrapped in a markdown-canvas code block for automatic canvas rendering.
        return {
          answer: `根据历史数据，已为您提取过去12个月的系统效率 (EFF) 数据，并生成了以下表格与柱状趋势图：

\`\`\`markdown-canvas
# 过去12个月系统效率 (EFF) 报告

以下是过去12个月（2025年6月至2026年5月）系统效率 (EFF) 的详细数据及分析。

## 1. EFF 数据表格 (kW/RT)

| 月份 | 效率 (kW/RT) | 状态 | 来源文件 |
| :--- | :--- | :--- | :--- |
| 2025年06月 | 0.615 | 已索引 | 202506.pdf |
| 2025年07月 | 0.604 | 已索引 | 202507.pdf |
| 2025年08月 | 0.607 | 已索引 | 202508.pdf |
| 2025年09月 | 0.598 | 已索引 | 202509.pdf |
| 2025年10月 | 0.604 | 已索引 | 202510.pdf |
| 2025年11月 | 0.602 | 已索引 | 202511.pdf |
| 2025年12月 | 0.598 | 已索引 | 202512.pdf |
| 2026年01月 | 0.581 | 已索引 | 202601.pdf |
| 2026年02月 | 0.589 | 已索引 | 202602.pdf |
| 2026年03月 | 0.607 | 已索引 | 202603.pdf |
| 2026年04月 | 0.625 | 已索引 | 202604.pdf |
| 2026年05月 | 0.628 | 已索引 | 202605.pdf |

## 2. 系统效率趋势图 (kW/RT)

以下是过去12个月系统效率的交互式变化趋势图（数值越低代表系统效率越好）：

~~~chart-config
{
  "type": "bar",
  "data": {
    "labels": ["2025-06", "2025-07", "2025-08", "2025-09", "2025-10", "2025-11", "2025-12", "2026-01", "2026-02", "2026-03", "2026-04", "2026-05"],
    "datasets": [{
      "label": "系统效率 (kW/RT)",
      "data": [0.615, 0.604, 0.607, 0.598, 0.604, 0.602, 0.598, 0.581, 0.589, 0.607, 0.625, 0.628],
      "backgroundColor": "rgba(0, 188, 242, 0.15)",
      "borderColor": "#00bcf2",
      "borderWidth": 2
    }]
  },
  "options": {
    "responsive": true,
    "scales": {
      "y": {
        "min": 0.5,
        "max": 0.7
      }
    }
  }
}
~~~

## 3. 效率趋势分析
- **最佳表现期**：系统效率在 **2026年1月** 达到了过去12个月的最高水平（0.581 kW/RT），其次是 2026年2月（0.589 kW/RT）和 2025年9月/12月（0.598 kW/RT）。
- **效率下降期**：效率最低的月份为 **2026年5月**（0.628 kW/RT）和 **2026年4月**（0.625 kW/RT），主要受外部气温升高导致冷机负荷增加的影响。
- **总体表现**：过去12个月的平均系统效率保持在 **0.605 kW/RT** 的优秀水平。
\`\`\`

数据已成功提取，已将表格和图表整理到 Canvas 中！`,
          sources: [
            { source: "202601.pdf", page: 1, score: 0.95, content: "EFF Monthly\n0.581\nSystem uptime (%)\n100.00%" },
            { source: "202605.pdf", page: 1, score: 0.93, content: "EFF Monthly\n0.628\nSystem uptime (%)\n100.00%" }
          ]
        };
      }
      if (cmd === "scan_pdf_files") {
        return [
          { name: "202506.pdf", chunks: 2, status: "indexed" },
          { name: "202507.pdf", chunks: 2, status: "indexed" },
          { name: "202508.pdf", chunks: 2, status: "indexed" },
          { name: "202509.pdf", chunks: 1, status: "indexed" },
          { name: "202510.pdf", chunks: 2, status: "indexed" },
          { name: "202511.pdf", chunks: 2, status: "indexed" },
          { name: "202512.pdf", chunks: 1, status: "indexed" },
          { name: "202601.pdf", chunks: 1, status: "indexed" },
          { name: "202602.pdf", chunks: 2, status: "indexed" },
          { name: "202603.pdf", chunks: 1, status: "indexed" },
          { name: "202604.pdf", chunks: 2, status: "indexed" },
          { name: "202605.pdf", chunks: 1, status: "indexed" }
        ];
      }
      return {};
    }
  };
}

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
