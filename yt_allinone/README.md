# YouTube All-in-One Tool

## 🎯 Tổng quan

YouTube All-in-One Tool là một ứng dụng đa năng để tải và xử lý video từ YouTube với giao diện GUI và CLI.

## 🚀 Cách sử dụng

### Chạy ứng dụng

```bash
# GUI version
python run_gui.py

# CLI version
python run_cli.py --help
```

## 📁 Cấu trúc project

```
yt_allinone/
├── src/                    # Source code chính
│   ├── app_gui.py         # GUI application
│   ├── app_cli.py         # CLI application
│   ├── core/              # Core modules
│   ├── download/          # Download modules
│   ├── ui/                # UI components
│   └── utils/             # Utility modules
├── tests/                  # Unit tests
├── run_gui.py             # Entry point cho GUI
├── run_cli.py             # Entry point cho CLI
├── favicon.png            # Icon cho app
├── requirements.txt       # Dependencies
└── README.md             # File này
```

## 🔧 Yêu cầu hệ thống

- Python 3.8+
- Windows 10/11 (đã test)
- Các dependencies trong `requirements.txt`

## 📦 Cài đặt

```bash
pip install -r requirements.txt
```

## 🎨 Tính năng

- **GUI**: Giao diện đồ họa với PySide6
- **CLI**: Command line interface với typer và rich; hỗ trợ nhập N URL cùng lúc
- **Download**: Hỗ trợ nhiều format video
- **Processing**: Xử lý video với FFmpeg
- **Export**: Xuất metadata và thumbnails

## 🛠️ Development

### Chạy tests
```bash
python -m pytest tests/
```

### Chạy ứng dụng
```bash
# GUI
python run_gui.py

# CLI
python run_cli.py get URL1 URL2 URL3 --quality 1080p --out downloads
```

## 📞 Hỗ trợ

Nếu gặp vấn đề:
1. Kiểm tra file README này
2. Thử chạy source code trực tiếp
3. Kiểm tra dependencies
4. Chạy tests để kiểm tra

## 🎊 Thành công!

Project đã được dọn dẹp sạch sẽ với:
- ✅ Source code chính trong `src/`
- ✅ Unit tests trong `tests/`
- ✅ Entry points đơn giản: `run_gui.py`, `run_cli.py`
- ✅ Icon từ favicon.png
- ✅ Dependencies trong requirements.txt
- ✅ Documentation rõ ràng
