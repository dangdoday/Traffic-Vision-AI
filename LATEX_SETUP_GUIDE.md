# Hướng dẫn Setup LaTeX trong VS Code

## ✅ Đã cài đặt
- LaTeX Workshop extension ✓
- MiKTeX ✓

## 🔧 Cấu hình VS Code

### 1. Mở File Settings
- **Ctrl + ,** hoặc File → Preferences → Settings
- Click icon 📄 **Open Settings (JSON)** ở góc phải

### 2. Thêm cấu hình LaTeX Workshop

```json
{
  // LaTeX Workshop Configuration
  "latex-workshop.latex.autoBuild.run": "onSave",
  "latex-workshop.latex.outDir": "./build",
  "latex-workshop.view.pdf.viewer": "tab",
  "latex-workshop.latex.clean.enabled": true,
  
  "latex-workshop.latex.tools": [
    {
      "name": "xelatex",
      "command": "xelatex",
      "args": [
        "-synctex=1",
        "-interaction=nonstopmode",
        "-file-line-error",
        "-output-directory=%OUTDIR%",
        "%DOC%"
      ]
    },
    {
      "name": "pdflatex",
      "command": "pdflatex",
      "args": [
        "-synctex=1",
        "-interaction=nonstopmode",
        "-file-line-error",
        "-output-directory=%OUTDIR%",
        "%DOC%"
      ]
    },
    {
      "name": "bibtex",
      "command": "bibtex",
      "args": [
        "%DOCFILE%"
      ]
    }
  ],
  
  "latex-workshop.latex.recipes": [
    {
      "name": "XeLaTeX",
      "tools": [
        "xelatex"
      ]
    },
    {
      "name": "PDFLaTeX",
      "tools": [
        "pdflatex"
      ]
    },
    {
      "name": "XeLaTeX → BibTeX → XeLaTeX × 2",
      "tools": [
        "xelatex",
        "bibtex",
        "xelatex",
        "xelatex"
      ]
    },
    {
      "name": "PDFLaTeX → BibTeX → PDFLaTeX × 2",
      "tools": [
        "pdflatex",
        "bibtex",
        "pdflatex",
        "pdflatex"
      ]
    }
  ]
}
```

## 📁 Mở folder báo cáo

1. **File → Open Folder**
2. Navigate to: `C:\Users\ADMIN\Downloads\BÁO_CÁO_ADVC`
3. Click **Select Folder**

## 📝 Build báo cáo

### Cách 1: Auto build (khi save)
- Mở file `main.tex`
- Chỉnh sửa và **Ctrl + S** để save
- PDF sẽ tự động build

### Cách 2: Manual build
1. Mở `main.tex`
2. Click icon **Build LaTeX project** (▶️) trên thanh toolbar
3. Hoặc press **Ctrl + Alt + B**

### Cách 3: Recipe specific
1. **Ctrl + Shift + P** → gõ "LaTeX: Build with recipe"
2. Chọn recipe:
   - **XeLaTeX** - cho tiếng Việt với font Unicode
   - **PDFLaTeX** - standard, không hỗ trợ Unicode tốt
   - **XeLaTeX → BibTeX → XeLaTeX × 2** - nếu có bibliography

## 👁️ Xem PDF

### Trong VS Code
- **Ctrl + Alt + V** - View PDF in tab
- PDF tự động refresh khi rebuild

### External viewer
- PDF được tạo ở folder `build/`
- Mở bằng Adobe Reader / SumatraPDF

## 🛠️ Shortcuts hữu ích

| Shortcut | Action |
|----------|--------|
| **Ctrl + Alt + B** | Build project |
| **Ctrl + Alt + V** | View PDF |
| **Ctrl + Alt + J** | Jump to PDF location (SyncTeX) |
| **Ctrl + Alt + C** | Clean auxiliary files |
| **Ctrl + Space** | Autocomplete |

## ⚠️ Troubleshooting

### 1. MiKTeX package missing
- Khi build, MiKTeX sẽ tự động download packages
- Nếu fail, mở **MiKTeX Console** → Update packages

### 2. Font not found (với XeLaTeX)
```latex
\usepackage{fontspec}
\setmainfont{Arial}  % hoặc Times New Roman
```

### 3. Vietnamese characters
- Dùng **XeLaTeX** thay vì PDFLaTeX
- Thêm:
```latex
\usepackage[vietnamese]{babel}
\usepackage{fontspec}
```

### 4. Build fails
- Check **LaTeX Workshop output** tab
- Common issues:
  - Missing packages → Install via MiKTeX
  - Syntax errors → Check `.log` file
  - Wrong compiler → Switch to XeLaTeX

## 📋 File structure mẫu

```
BÁO_CÁO_ADVC/
├── main.tex          ← Main file (build này)
├── title.tex         ← Trang bìa
├── Tom_tat.tex       ← Tóm tắt
├── Loi_cam_on.tex    ← Lời cảm ơn
├── Mo_dau.tex        ← Mở đầu
├── Ly_thuyet_Phan1.tex
├── Phuong_phap_Phan1.tex
├── Thuc_nghiem.tex
├── Thuc_nghiem_phan2.tex
├── images/           ← Ảnh
├── build/            ← PDF output (sẽ tự tạo)
└── *.aux, *.log      ← Temp files (ignore)
```

## 🚀 Quick Start

1. **Ctrl + K, Ctrl + O** → Mở folder báo cáo
2. Mở file `main.tex`
3. **Ctrl + Alt + B** → Build
4. **Ctrl + Alt + V** → View PDF
5. Edit → Save → Auto rebuild!

## 💡 Tips

- Dùng **XeLaTeX** cho tiếng Việt
- Enable **Auto Build on Save** để xem realtime
- Dùng **SyncTeX** để jump giữa code và PDF
- Check **Problems** panel nếu có lỗi

---

**Bắt đầu ngay:**
```powershell
code "C:\Users\ADMIN\Downloads\BÁO_CÁO_ADVC"
```
