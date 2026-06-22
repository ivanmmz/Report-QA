# Report QA - UI Design System Specification

## Version
- **Document Version**: 1.0
- **Date**: 2026-06-22
- **Target Framework**: Tauri (Rust + Frontend)

---

## 1. Design Philosophy & Overview

The current UI is built on **Streamlit** with a custom **Microsoft Fluent Design-inspired** theme. The application is a dual-pane layout:
- **Left Pane**: Report Canvas (Markdown Editor + Preview)
- **Right Pane**: AI Copilot Chat Assistant (Edge-Copilot style)

### Core Design Principles
1. **Glassmorphism & Depth**: Extensive use of translucent backgrounds, backdrop blurs, and semi-transparent overlays
2. **High Contrast Typography**: Sharp text hierarchy with deliberate sizing
3. **Minimal Chrome**: Hidden native UI elements (hidden Streamlit headers, custom sidebars)
4. **Contextual Density**: Information-rich but not cluttered
5. **System Integration**: Native Windows feel with custom styling

---

## 2. Color System (Theme-Aware)

### 2.1 Dark Mode (Default)
```
Backgrounds:
  --bg0: #0f1117           (Main page background)
  --bg1: #1a1d2e           (Card / Dialog background)
  --bg2: rgba(255,255,255,0.03)  (Subtle hover/input bg)
  --input-bg: rgba(255,255,255,0.03)
  --sidebar-bg: rgba(16,18,27,0.95)

Text:
  --text0: #e4e6eb          (Primary text - headings, body)
  --text1: rgba(255,255,255,0.7)   (Secondary text - descriptions)
  --text2: rgba(255,255,255,0.35) (Muted - timestamps, metadata)

Accents:
  --accent: #00bcf2         (Cyan - primary action, links, active states)
  --accent-bg: rgba(0,120,212,0.08) (Subtle accent background)

Surfaces:
  --card-bg: rgba(255,255,255,0.03)
  --card-hover: rgba(255,255,255,0.05)
  --border: rgba(255,255,255,0.08)
  --border-hover: rgba(0,188,242,0.3)

Gradients:
  Main: linear-gradient(135deg, #0f1117 0%, #1a1d2e 50%, #0f1117 100%)
  Dialog Overlay: rgba(0,0,0,0.4)
```

### 2.2 Light Mode
```
Backgrounds:
  --bg0: #f8f9fa
  --bg1: #ffffff
  --bg2: rgba(0,0,0,0.02)
  --input-bg: rgba(255,255,255,0.8)
  --sidebar-bg: rgba(255,255,255,0.97)

Text:
  --text0: #1a1a2e
  --text1: rgba(0,0,0,0.7)
  --text2: rgba(0,0,0,0.4)

Accents:
  --accent: #0066cc (Darker blue for light mode contrast)
  --accent-bg: rgba(0,100,200,0.06)

Surfaces:
  --card-bg: rgba(0,0,0,0.02)
  --card-hover: rgba(0,0,0,0.04)
  --border: rgba(0,0,0,0.1)
  --border-hover: rgba(0,100,200,0.3)

Gradients:
  Main: linear-gradient(135deg, #f0f2f5 0%, #ffffff 50%, #f0f2f5 100%)
  Dialog Overlay: rgba(0,0,0,0.25)
```

### 2.3 Semantic Colors
```
Success: #00cc6a (Green dot for "ready" status)
Error: #ff4343 (Red dot for error status)
Warning: #ffb800 (Amber warning text)
Danger Action: #e05555 (Delete/Remove buttons)
Provider Status OK: #3ecf8e
Provider Status Error: #e05555
```

### 2.4 Chart Colors (8-color Palette)
```
['#00bcf2', '#ffb800', '#4ecdc4', '#ff6b6b', '#c084fc', '#fb923c', '#34d399', '#60a5fa']
```

---

## 3. Typography System

### 3.1 Font Stack
```css
font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Noto Sans SC', sans-serif;
```
For code/monospace: `Cascadia Code`, `Fira Code`, Consolas, monospace

### 3.2 Type Scale
| Level | Size | Weight | Color | Use Case |
|-------|------|--------|-------|----------|
| h1 | 1.8em / 1.6em (canvas) | 700 | --text0 | Page titles, report headings |
| h2 | 1.3em | 600 | --text0 | Section headings |
| h3 | 1.15em | 600 | --text0 | Sub-section headings |
| h4-h6 | 1.05em | 600 | --text0 | Minor headings |
| Body | 1em / 0.9em (table) | 400 | --text0 / --text1 | Body text, descriptions |
| Small | 0.85em | 400 | --text1 | Metadata, timestamps |
| Caption | 0.78em / 0.72em | 400/700 | --text2 | Labels, section headers |
| Stat Value | 1.5em | 700 | --accent | Metric display |
| Stat Label | 0.85em | 400 | --text1 | Metric description |

### 3.3 Special Text Treatments
- **Section Labels**: Uppercase, letter-spacing: 0.08em, font-size: 0.68-0.70em, font-weight: 700, color: --text2
- **Code Inline**: background: --code-bg, padding: 2px 6px, border-radius: 4px, font-size: 0.9em
- **Code Block**: background: --pre-bg, padding: 16px, border-radius: 8px, border: 1px solid --border
- **Chat Actions Label**: font-size: 0.78em, color: --text2

---

## 4. Layout System

### 4.1 Overall Layout Architecture
```
┌──────────────────────────────────────────────────────┬──────────────────────┐
│                                                      │                      │
│   TOP CONTROLS (Floating, right-aligned)             │   COPILOT SIDEBAR    │
│   [📋] [⚙️] [☀️/🌙]                                  │   (Fixed, 380px)     │
│                                                      │                      │
│─────────────────────────────────────────────────────│                      │
│                                                      │   Copilot            │
│   MAIN CONTENT AREA                                  │   Assistant          │
│   (Fluid width, padding-right: 400px)                │   Chat Interface     │
│                                                      │                      │
│   [Canvas / Editor / Preview]                        │   ┌──────────────┐   │
│                                                      │   │ Chat actions │   │
│   [Report History / Library]                         │   └──────────────┘   │
│                                                      │   ┌──────────────┐   │
│                                                      │   │ Messages     │   │
│                                                      │   └──────────────┘   │
│                                                      │   ┌──────────────┐   │
│                                                      │   │ Input (fixed)│   │
│                                                      │   └──────────────┘   │
└──────────────────────────────────────────────────────┴──────────────────────┘
```

### 4.2 Responsive Rules
- **Main Content**: `max-width: 100%; width: 100%; padding-right: 400px` (accounts for fixed Copilot sidebar)
- **Copilot Sidebar**: Fixed position, `right: 0; top: 0; width: 380px; height: 100vh`
- **Top Controls**: Fixed position, `top: 15px; right: 400px`
- **Canvas Iframe**: `height: calc(100vh - 60px); width: 100%`

### 4.3 Z-Index Hierarchy
| Element | Z-Index |
|---------|---------|
| Citation Modal | 99999 |
| Chat Input (fixed) | 9991 |
| Copilot Sidebar | 9990 |
| Top Controls | 9995 |
| Dialog Overlay | Overlay layer |

---

## 5. Component Design System

### 5.1 Buttons

#### Primary Button (Action)
```css
background: #0078d4;
color: white;
border: none;
border-radius: 8px;
padding: 10px 24px;
font-weight: 500;
transition: all 0.2s ease;
/* Hover */
background: #005a9e;
transform: translateY(-1px);
box-shadow: 0 4px 12px rgba(0, 120, 212, 0.3);
/* Active */
transform: translateY(0);
```

#### Secondary / Ghost Button
```css
background: transparent;
border: 1px solid rgba(128,128,128,0.30);
color: var(--text0);
border-radius: 7px;
padding: 4px 14px;
font-size: 0.80rem;
min-height: 30px;
/* Hover */
background: var(--hover-bg);
border-color: rgba(128,128,128,0.50);
```

#### Destructive Button (Delete)
```css
color: #e05555;
border-color: rgba(224,85,85,0.35);
background: transparent;
/* Hover */
background: rgba(224,85,85,0.08);
```

#### Icon Button (Top Controls)
```css
background: var(--bg2);
color: var(--text0);
border: 1px solid var(--border);
border-radius: 4px;
width: 28px;
height: 28px;
padding: 0;
display: inline-flex;
align-items: center;
justify-content: center;
font-size: 14px;
/* Hover */
background: rgba(0, 120, 212, 0.15);
border-color: #0078d4;
color: #0078d4;
transform: scale(1.05);
```

### 5.2 Cards

#### Standard Card
```css
background: var(--card-bg);
border: 1px solid var(--border);
border-radius: 12px;
padding: 16px;
margin-bottom: 16px;
transition: all 0.2s ease;
/* Hover */
background: var(--card-hover);
border-color: var(--border-hover);
```

#### Accent Card (Highlight)
```css
background: var(--accent-bg);
border: 1px solid rgba(0, 120, 212, 0.2);
border-radius: 12px;
padding: 16px;
```

#### Metric Card
```css
background: var(--card-bg);
border: 1px solid var(--border);
border-radius: 8px;
padding: 12px;
text-align: center;
```

### 5.3 Input Fields

#### Text Input / Text Area
```css
background: var(--input-bg);
border: 1px solid var(--border);
border-radius: 8px;
color: var(--text0);
padding: 10px 14px;
/* Focus */
border-color: rgba(0, 188, 242, 0.5);
```

#### Chat Input (Fixed Bottom)
```css
position: fixed;
bottom: 0;
right: 0;
width: 380px;
background: var(--copilot-bg);
border-top: 1px solid var(--copilot-border);
padding: 8px 16px;
z-index: 9991;
```

### 5.4 Status Indicators

#### Status Dot
```css
width: 8px;
height: 8px;
border-radius: 50%;
display: inline-block;
margin-right: 8px;
/* States */
.ready { background: #00cc6a; }
.error { background: #ff4343; }
```

#### Status Bar
```css
display: flex;
align-items: center;
padding: 8px 12px;
background: var(--bg2);
border: 1px solid var(--border);
border-radius: 6px;
margin: 6px 0;
font-size: 0.85em;
```

### 5.5 Provider Card
```css
padding: 8px 12px;
border-radius: 8px;
background: var(--prov-card-bg);
border-left: 3px solid #888; /* or #3ecf8e (ok) / #e05555 (err) */
margin: 5px 0;
font-size: 0.82rem;
```

### 5.6 Citation Modal
```css
/* Overlay */
background: rgba(0,0,0,0.5);
/* Content Card */
background: var(--bg1);
color: var(--text0);
border: 1px solid var(--border);
border-radius: 12px;
padding: 24px;
max-width: 500px;
width: 90%;
max-height: 70vh;
overflow-y: auto;
box-shadow: 0 8px 32px rgba(0,0,0,0.3);
```

---

## 6. Spacing System

### 6.1 Padding & Margins
| Token | Value | Usage |
|-------|-------|-------|
| xs | 4px | Tight spacing, inline elements |
| sm | 8px | Button padding, small gaps |
| md | 12px | Card padding, form spacing |
| lg | 16px | Default card padding, modal padding |
| xl | 20-24px | Page padding, section gaps |
| 2xl | 32px | File uploader padding |

### 6.2 Border Radius
| Token | Value | Usage |
|-------|-------|-------|
| sm | 4px | Code inline, small badges |
| md | 6px | Buttons, small cards |
| lg | 8px | Cards, inputs, dialogs |
| xl | 10-12px | Large cards, modals, chat messages |
| full | 50% | Status dots, avatars |

---

## 7. Animation & Transitions

### 7.1 Timing
```
Quick interactions: 0.15s (button hovers, small transitions)
Standard transitions: 0.2s ease (cards, borders)
Button click feedback: scale(1.05) on hover, translateY(-1px) for primary
```

### 7.2 Easing
```css
transition-timing-function: ease; /* Default for most */
```

### 7.3 Specific Animations
- **Button Hover**: Background color change, optional translateY(-1px) for primary
- **Card Hover**: Background darkens/lightens, border color shifts to accent
- **Modal**: Fade in (overlay opacity 0 → 1), no scale animation
- **Toast**: Slide in from bottom, fade out
- **Chat Message**: Fade in on render
- **Loading Spinner**: Standard Streamlit spinner

---

## 8. Special Components

### 8.1 Report Canvas Viewer
- Renders as an embedded HTML iframe
- Floating download bar (sticky, top-right) with MD and HTML buttons
- Backdrop blur on download buttons: `backdrop-filter: blur(8px)`
- Supports Chart.js rendering inside markdown

### 8.2 Chat Message
```css
background: var(--bg2);
border: 1px solid var(--border);
border-radius: 12px;
padding: 8px 12px;
/* User variant */
background: var(--accent-bg);
border-color: rgba(0, 120, 212, 0.2);
```

### 8.3 File Uploader
```css
background: var(--bg2);
border: 2px dashed var(--border);
border-radius: 12px;
padding: 32px;
color: var(--text0);
```

### 8.4 Scrollbars
```css
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: var(--bg2); }
::-webkit-scrollbar-thumb { background: rgba(128,128,128,0.2); border-radius: 3px; }
```

---

## 9. Tauri Migration Strategy

### 9.1 Recommended Tech Stack
```
Frontend: React 18+ with TypeScript
  - UI Framework: Tailwind CSS (for utility-first styling)
  - Component Library: Radix UI (headless, accessible) or shadcn/ui
  - State Management: Zustand (simple, lightweight)
  - Icons: Lucide React
  - Markdown Rendering: react-markdown + remark-gfm
  - Charts: Chart.js ( maintain compatibility) or Recharts
  
Backend: Rust (Tauri)
  - PDF Processing: pdf-extract or similar Rust crate
  - Vector DB: Keep FAISS via Python sidecar or migrate to Rust ml crate
  - Embeddings: HTTP calls to existing API
  - File I/O: Rust fs APIs through Tauri commands
```

### 9.2 Window Configuration
```json
{
  "windows": [
    {
      "title": "RAG System",
      "width": 1400,
      "height": 900,
      "minWidth": 1200,
      "minHeight": 700,
      "transparent": false,
      "resizable": true,
      "fullscreen": false,
      "decorations": true,
      "center": true
    }
  ]
}
```

### 9.3 Theme Implementation in Tailwind
```typescript
// tailwind.config.ts
export default {
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // Dark mode
        dark: {
          bg0: '#0f1117',
          bg1: '#1a1d2e',
          bg2: 'rgba(255,255,255,0.03)',
          text0: '#e4e6eb',
          text1: 'rgba(255,255,255,0. WIC 7)',
          text2: 'rgba(255,255,255,0.35)',
          border: 'rgba(255,255,255,0.08)',
          accent: '#00bcf2',
          'accent-bg': 'rgba(0,120,212,0.08)',
        },
        // Light mode
        light: {
          bg0: '#f8f9fa',
          bg1: '#ffffff',
          bg2: 'rgba(0,0,0,0.02)',
          text0: '#1a1a2e',
          text1: 'rgba(0,0,0,0.7)',
          text2: 'rgba(0,0,0,0.4)',
          border: 'rgba(0,0,0,0.1)',
          accent: '#0066cc',
          'accent-bg': 'rgba(0,100,200,0.06)',
        },
        // Semantic
        success: '#00cc6a',
        error: '#ff4343',
        warning: '#ffb800',
        danger: '#e05555',
      },
      fontFamily: {
        sans: ['-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'Noto Sans SC', 'sans-serif'],
        mono: ['Cascadia Code', 'Fira Code', 'Consolas', 'monospace'],
      },
    },
  },
};
```

### 9.4 Component Mapping

| Streamlit Component | Tauri/React Equivalent |
|---------------------|----------------------|
| `st.container()` | `<div>`, CSS Grid/Flexbox |
| `st.columns()` | CSS Grid or Flexbox layout |
| `st.button()` | Custom `<Button>` component |
| `st.chat_message()` | Custom `<ChatMessage>` component |
| `st.chat_input()` | Custom `<ChatInput>` with textarea |
| `st.text_input()` | `<Input>` from shadcn/ui |
| `st.text_area()` | `<Textarea>` from shadcn/ui |
| `st.selectbox()` | `<Select>` from shadcn/ui |
| `st.tabs()` | Custom `<Tabs>` component |
| `st.expander()` | `<Collapsible>` from shadcn/ui |
| `st.popover()` | `<Popover>` from shadcn/ui |
| `st.dialog()` | `<Dialog>` from shadcn/ui |
| `st.file_uploader()` | Custom `<FileUploader>` with drag-and-drop |
| `st.markdown()` | `react-markdown` renderer |
| `st.components.html()` | React components |
| `st.spinner()` | Custom `<Spinner>` or Skeleton |
| `st.toast()` | Sonner or custom toast library |

### 9.5 State Management Migration

```typescript
// Current: st.session_state
// Tauri: Zustand store + Tauri commands

interface AppState {
  // Theme
  isDark: boolean;
  
  // System initialization
  initialized: boolean;
  settings: Record<string, any>;
  
  // Components
  docManager: DocumentManager | null;
  ragPipeline: RAGPipeline | null;
  
  // Report editor
  activeReportTitle: string;
  activeReportContent: string;
  
  // Copilot chat
  copilotMessages: Message[];
  copilotPresets: string[];
  
  // Background tasks
  syncTask: BackgroundTask | null;
  reindexTask: BackgroundTask | null;
  reportTask: BackgroundTask | null;
  
  // Actions
  toggleTheme: () => void;
  initializeSystem: () => Promise<void>;
  sendChatMessage: (query: string) => Promise<void>;
  generateReport: (type: string, query: string) => Promise<void>;
}
```

### 9.6 Key Implementation Notes

1. **Theme Toggle**: Use `class` strategy with `dark` class on root element. Detect system preference via `window.matchMedia('(prefers-color-scheme: dark)')`.

2. **Copilot Sidebar**: Use CSS `position: fixed` with `right: 0`. In Tauri, consider native window with `tauri://` protocol or a dedicated panel.

3. **Canvas HTML Rendering**: Use `react-markdown` with custom components for tables, code blocks, and chart placeholders. Inject Chart.js script dynamically.

4. **Background Tasks**: Implement Rust-side async tasks using `tokio` and communicate progress via Tauri events (`tauri://event`).

5. **Settings Dialog**: Use Radix Dialog primitive with tabs. Store settings in Tauri config or localStorage with Rust-backed persistence.

6. **File Operations**: Use Tauri's `dialog` API for folder/file selection and `fs` API for reading/writing.

7. **Drag & Drop**: Implement using HTML5 drag-and-drop API or libraries like `react-dnd` for file uploads.

8. **Copilot Floating Input**: Use `position: fixed; bottom: 0` within the sidebar container.

9. **Chart Rendering**: Create a custom React component that parses the JSON from `chart` code blocks and renders Chart.js charts.

10. **Markdown Preview**: Implement a rich preview mode with custom CSS that matches the current theme exactly.

---

## 10. Assets & Resources

### 10.1 Icons Needed
- Settings (⚙️)
- Theme Toggle (☀️ / 🌙)
- Report Generator (📋)
- New Chat (🆕)
- History (🕐)
- Tools (➕)
- Copy (Clipboard)
- Download (MD, HTML)
- Sync (↺)
- Delete (🗑️)
- Status indicators (🟢 🔴)
- File icons (PDF, etc.)

### 10.2 External Dependencies
- Chart.js 4.4.7 (or latest)
- No external fonts (use system fonts)

---

## 11. Accessibility Considerations

- All interactive elements must be keyboard accessible
- Color contrast ratios: Minimum 4.5:1 for normal text, 3:1 for large text
- Focus indicators: Visible outline or ring on all interactive elements
- Screen reader support: Proper ARIA labels on all non-text buttons
- Reduced motion: Respect `prefers-reduced-motion` media query

---

## 12. File Structure (Tauri)

```
src/                              # Rust backend
  main.rs
  lib.rs
  commands/                       # Tauri commands
    api_settings.rs
    document_manager.rs
    report_generator.rs
    chat.rs
  state/                          # App state management
    mod.rs
  utils/
    file_io.rs
    logger.rs

src-tauri/                        # Tauri configuration
  Cargo.toml
  tauri.conf.json

src/                              # Frontend (React)
  App.tsx
  main.tsx
  components/
    ui/                           # shadcn/ui components
      button.tsx
      card.tsx
      dialog.tsx
      input.tsx
      tabs.tsx
      select.tsx
      toast.tsx
      // ...
    layout/
      MainLayout.tsx
      TopControls.tsx
      CopilotSidebar.tsx
      CanvasViewer.tsx
    chat/
      ChatMessage.tsx
      ChatInput.tsx
      ChatHistory.tsx
      CitationModal.tsx
    report/
      ReportEditor.tsx
      ReportPreview.tsx
      ReportHistory.tsx
      ChartRenderer.tsx
    settings/
      SettingsDialog.tsx
      ApiSettings.tsx
      DocumentSettings.tsx
  hooks/
    useTheme.ts
    useSystemState.ts
    useChat.ts
  stores/
    appStore.ts                   # Zustand store
  styles/
    globals.css
    theme.ts                      # Theme definitions
  types/
    index.ts

public/
  chart.js@4.4.7.min.js           # Chart.js (optional, can use CDN)

package.json
tailwind.config.ts
vite.config.ts
index.html
```

---

## 13. Critical UI Behaviors to Preserve

1. **Dual-pane layout**: Left canvas (60-70%), right Copilot (fixed 380px)
2. **Theme switching**: Instant toggle, all components must react
3. **Copilot chat input**: Fixed to bottom of sidebar
4. **Canvas floating buttons**: MD and HTML download, sticky top-right
5. **Status bar**: Documents, Vectors, LLM, Folder indicators in settings
6. **Provider cards**: Color-coded left border (green/red/grey)
7. **Chat message actions**: Copy button (appears on hover), citations expander
8. **Background task feedback**: Toast notifications, status indicators
9. **Settings as dialog**: Not a separate page, opens as overlay
10. **Report templates**: Quick presets in popover, custom template management

---

*End of Design System Specification*