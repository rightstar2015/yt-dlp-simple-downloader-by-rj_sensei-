QSS_STYLE = """
QWidget {
    background-color: #0f172a;
    color: #e2e8f0;
    font-family: 'Segoe UI', 'Microsoft JhengHei', sans-serif;
    font-size: 13px;
}

QScrollArea {
    border: none;
    background-color: #0f172a;
}

QScrollBar:vertical {
    border: none;
    background: #1e293b;
    width: 10px;
    margin: 0px;
    border-radius: 5px;
}
QScrollBar::handle:vertical {
    background: #475569;
    min-height: 20px;
    border-radius: 5px;
}
QScrollBar::handle:vertical:hover {
    background: #64748b;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QLineEdit {
    background-color: #1e293b;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 8px 12px;
    color: #f8fafc;
}
QLineEdit:focus {
    border: 1px solid #3b82f6;
    background-color: #0f172a;
}

QPushButton {
    background-color: #2563eb;
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #3b82f6;
}
QPushButton:pressed {
    background-color: #1d4ed8;
}
QPushButton:disabled {
    background-color: #334155;
    color: #64748b;
}

QPushButton#download_btn {
    background-color: #10b981;
    font-size: 14px;
    padding: 10px 20px;
}
QPushButton#download_btn:hover {
    background-color: #34d399;
}
QPushButton#download_btn:pressed {
    background-color: #059669;
}

QGroupBox {
    border: 1px solid #334155;
    border-radius: 8px;
    margin-top: 16px;
    padding-top: 16px;
    font-weight: bold;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    padding: 0 6px;
    color: #3b82f6;
}

QRadioButton, QCheckBox {
    spacing: 8px;
}
QRadioButton::indicator, QCheckBox::indicator {
    width: 16px;
    height: 16px;
}

QComboBox {
    background-color: #1e293b;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 6px 12px;
    color: #f8fafc;
}
QComboBox::drop-down {
    border: none;
}
QComboBox QAbstractItemView {
    background-color: #1e293b;
    border: 1px solid #334155;
    selection-background-color: #3b82f6;
    selection-color: #ffffff;
}

QProgressBar {
    border: 1px solid #334155;
    border-radius: 8px;
    text-align: center;
    background-color: #1e293b;
    color: #ffffff;
    font-weight: bold;
}
QProgressBar::chunk {
    background-color: #3b82f6;
    border-radius: 7px;
}

QLabel#status {
    color: #10b981;
    font-weight: bold;
}

QLabel#note {
    background-color: #1e293b;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 10px;
    color: #94a3b8;
}
"""
