from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, 
                            QPushButton, QLabel, QFileDialog, QHBoxLayout, 
                            QLineEdit, QListWidget, QComboBox)
from PyQt6.QtCore import Qt, QMimeData
from PyQt6.QtGui import QDragEnterEvent, QDropEvent
import json
import logging
from pathlib import Path
import jsonschema

class EntityToolGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.current_file = None
        self.current_data = None
        self.schema_dir = None
        self.schemas = {}  # Cache for loaded schemas
        
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
        
        # Schema directory selection
        schema_layout = QHBoxLayout()
        self.schema_path_label = QLabel('No schema directory selected')
        self.schema_path_label.setWordWrap(True)
        schema_btn = QPushButton('Select Schema Directory')
        schema_btn.clicked.connect(self.select_schema_directory)
        schema_layout.addWidget(self.schema_path_label)
        schema_layout.addWidget(schema_btn)
        left_layout.addLayout(schema_layout)
        
        # Schema selector
        self.schema_selector = QComboBox()
        self.schema_selector.setEnabled(False)
        self.schema_selector.currentTextChanged.connect(self.validate_current_file)
        left_layout.addWidget(self.schema_selector)
        
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
    
    def select_schema_directory(self):
        """Open directory dialog to select schema directory"""
        dir_path = QFileDialog.getExistingDirectory(
            self,
            "Select Schema Directory",
            str(self.schema_dir) if self.schema_dir else ""
        )
        if dir_path:
            self.schema_dir = Path(dir_path)
            self.schema_path_label.setText(str(self.schema_dir))
            self.load_schemas()
    
    def load_schemas(self):
        """Load all JSON schemas from the selected directory"""
        if not self.schema_dir or not self.schema_dir.exists():
            return
        
        try:
            # Clear existing schemas
            self.schemas.clear()
            self.schema_selector.clear()
            
            # Load all schema files
            schema_files = list(self.schema_dir.glob("*.json"))
            logging.info(f"Found {len(schema_files)} schema files")
            
            for schema_file in schema_files:
                try:
                    with open(schema_file) as f:
                        schema = json.load(f)
                    self.schemas[schema_file.stem] = schema
                    logging.debug(f"Loaded schema: {schema_file.name}")
                except Exception as e:
                    logging.error(f"Error loading schema {schema_file.name}: {str(e)}")
            
            # Update schema selector
            self.schema_selector.addItems(sorted(self.schemas.keys()))
            self.schema_selector.setEnabled(True)
            
            logging.info(f"Successfully loaded {len(self.schemas)} schemas")
            
            # Validate current file if one is loaded
            if self.current_data:
                self.validate_current_file()
                
        except Exception as e:
            logging.error(f"Error loading schemas: {str(e)}")
    
    def validate_current_file(self):
        """Validate the current file against the selected schema"""
        if not self.current_data or not self.schema_selector.currentText():
            return
        
        schema_name = self.schema_selector.currentText()
        schema = self.schemas.get(schema_name)
        if not schema:
            return
        
        try:
            jsonschema.validate(self.current_data, schema)
            logging.info(f"File validates against schema: {schema_name}")
            self.status_label.setText(f"Valid {schema_name}")
            self.status_label.setProperty("status", "success")
        except jsonschema.exceptions.ValidationError as e:
            logging.error(f"Validation error: {str(e)}")
            self.status_label.setText(f"Invalid {schema_name}")
            self.status_label.setProperty("status", "error")
        except Exception as e:
            logging.error(f"Error during validation: {str(e)}")
    
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
            
            # Validate against current schema if one is selected
            if self.schema_selector.currentText():
                self.validate_current_file()
            
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