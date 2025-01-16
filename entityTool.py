from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, 
                            QPushButton, QLabel, QFileDialog, QHBoxLayout, 
                            QLineEdit, QListWidget)
from PyQt6.QtCore import Qt, QMimeData
from PyQt6.QtGui import QDragEnterEvent, QDropEvent
import json
import logging
from pathlib import Path

class EntityToolGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.current_file = None
        self.current_data = None
        
        # Initialize UI
        self.init_ui()
        
        # Open in full screen
        self.showMaximized()
    
    def init_ui(self):
        self.setWindowTitle('Sins 2 Entity Tool')
        
        # Create central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        
        # Left side (file operations)
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        
        # Status/drop label
        self.status_label = QLabel('Drop entity file here\nNo file loaded')
        self.status_label.setObjectName("dropLabel")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setMinimumHeight(100)
        left_layout.addWidget(self.status_label)
        
        # Open file button
        open_btn = QPushButton('Open Entity File')
        open_btn.clicked.connect(self.open_file_dialog)
        left_layout.addWidget(open_btn)
        
        # Log display
        self.log_display = QListWidget()
        self.log_display.setObjectName("logDisplay")
        self.log_display.setMaximumHeight(100)
        left_layout.addWidget(self.log_display)
        
        # Add log handler
        self.log_handler = GUILogHandler(self.log_display)
        self.log_handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
        logging.getLogger().addHandler(self.log_handler)
        
        # Right side (entity viewer/editor)
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        
        # Add editor label with scrollable text
        self.editor_label = QLabel('Entity Editor\n(No file loaded)')
        self.editor_label.setObjectName("editorLabel")
        self.editor_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.editor_label.setWordWrap(True)
        right_layout.addWidget(self.editor_label)
        
        # Add both sides to main layout
        main_layout.addWidget(left_widget, 1)  # 30% width
        main_layout.addWidget(right_widget, 2)  # 70% width
        
        # Enable drag and drop
        self.setAcceptDrops(True)
    
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()
    
    def dropEvent(self, event: QDropEvent):
        files = [u.toLocalFile() for u in event.mimeData().urls()]
        for file_path in files:
            self.load_file(Path(file_path))
            break  # Only load the first file
    
    def open_file_dialog(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Entity File",
            "",
            "JSON Files (*.json);;All Files (*.*)"
        )
        if file_path:
            self.load_file(Path(file_path))
    
    def load_file(self, file_path: Path):
        try:
            with open(file_path) as f:
                self.current_data = json.load(f)
            
            self.current_file = file_path
            self.status_label.setText(f'Loaded: {file_path.name}')
            
            # Log data details
            logging.info(f"Successfully loaded: {file_path}")
            logging.info(f"Data type: {type(self.current_data)}")
            if isinstance(self.current_data, dict):
                logging.info(f"Top-level keys: {list(self.current_data.keys())}")
                for key, value in self.current_data.items():
                    logging.info(f"{key}: {type(value)}")
                    if isinstance(value, (list, dict)):
                        logging.info(f"{key} length: {len(value)}")
            
            # Update the editor label with basic info
            info_text = ["Entity Data:"]
            if isinstance(self.current_data, dict):
                for key, value in self.current_data.items():
                    if isinstance(value, (list, dict)):
                        info_text.append(f"{key}: {type(value).__name__} ({len(value)} items)")
                    else:
                        info_text.append(f"{key}: {value}")
            else:
                info_text.append(str(self.current_data))
            
            self.editor_label.setText('\n'.join(info_text))
            
        except Exception as e:
            self.status_label.setText('Error loading file')
            logging.error(f"Error loading file: {str(e)}")
            self.current_file = None
            self.current_data = None

class GUILogHandler(logging.Handler):
    def __init__(self, log_widget):
        super().__init__()
        self.log_widget = log_widget
        
    def emit(self, record):
        msg = self.format(record)
        self.log_widget.addItem(msg)
        item = self.log_widget.item(self.log_widget.count() - 1)
        item.setForeground(Qt.GlobalColor.red if 'ERROR' in msg else Qt.GlobalColor.black)
        self.log_widget.scrollToBottom() 