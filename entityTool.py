from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, 
                            QPushButton, QLabel, QFileDialog, QHBoxLayout, 
                            QLineEdit, QListWidget, QComboBox, QTreeWidget, QTreeWidgetItem, QListWidgetItem)
from PyQt6.QtCore import Qt, QMimeData
from PyQt6.QtGui import QDragEnterEvent, QDropEvent
import json
import logging
from pathlib import Path
import jsonschema

class EntityToolGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.current_folder = None
        self.current_file = None
        self.current_data = None
        self.schema_dir = None
        self.schemas = {}  # Cache for loaded schemas
        self.files_by_type = {}  # Dictionary to store files by their type
        self.schema_extensions = {}  # Maps schema names to file extensions
        self.manifest_files = {}  # Dictionary to store manifest data
        
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
        self.status_label = QLabel('Drop mod folder here\nNo folder loaded')
        self.status_label.setObjectName("dropLabel")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setMinimumHeight(100)
        left_layout.addWidget(self.status_label)
        
        # Open folder button
        open_btn = QPushButton('Open Mod Folder')
        open_btn.clicked.connect(self.open_folder_dialog)
        left_layout.addWidget(open_btn)
        
        # File tree
        self.file_tree = QTreeWidget()
        self.file_tree.setHeaderLabel("Files")
        self.file_tree.itemClicked.connect(self.on_file_selected)
        left_layout.addWidget(self.file_tree)
        
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
        
        # Add manifest info section
        self.manifest_label = QLabel('Related Files:')
        self.manifest_label.setVisible(False)
        right_layout.addWidget(self.manifest_label)
        
        self.manifest_list = QListWidget()
        self.manifest_list.setObjectName("manifestList")
        self.manifest_list.itemClicked.connect(self.on_manifest_item_clicked)
        self.manifest_list.setVisible(False)
        right_layout.addWidget(self.manifest_list)
        
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
    
    def open_folder_dialog(self):
        """Open directory dialog to select mod folder"""
        dir_path = QFileDialog.getExistingDirectory(
            self,
            "Select Mod Folder",
            str(self.current_folder) if self.current_folder else ""
        )
        if dir_path:
            self.load_folder(Path(dir_path))
    
    def get_file_type_from_extension(self, file_path: Path) -> str:
        """Convert file extension to schema type"""
        # Remove the dot and convert to schema name format
        ext = file_path.suffix.lstrip('.')
        return ext.replace('_', '-')
    
    def load_folder(self, folder_path: Path):
        """Load all files from the mod folder"""
        try:
            self.current_folder = folder_path.resolve()  # Get absolute path
            self.files_by_type.clear()
            self.manifest_files.clear()  # Clear existing manifest data
            self.file_tree.clear()
            
            # Create root item
            root_item = QTreeWidgetItem(self.file_tree, [self.current_folder.name])
            
            # First, look for and process manifest files in the entities folder
            entities_folder = self.current_folder / "entities"
            if entities_folder.exists():
                logging.info(f"Found entities folder: {entities_folder}")
                for file_path in entities_folder.glob("*.entity_manifest"):
                    try:
                        with open(file_path) as f:
                            data = json.load(f)
                            self.process_manifest_file(file_path, data)
                            logging.info(f"Processed manifest file: {file_path.name}")
                    except Exception as e:
                        logging.error(f"Error processing manifest file {file_path}: {str(e)}")
            
            # Process all files recursively
            for file_path in self.current_folder.rglob("*"):
                if file_path.is_file():
                    # Get relative path for display
                    rel_path = file_path.relative_to(self.current_folder)
                    
                    # Create tree structure
                    current_item = root_item
                    for part in rel_path.parent.parts:
                        # Find or create folder item
                        folder_item = None
                        for i in range(current_item.childCount()):
                            if current_item.child(i).text(0) == part:
                                folder_item = current_item.child(i)
                                break
                        if not folder_item:
                            folder_item = QTreeWidgetItem(current_item, [part])
                        current_item = folder_item
                    
                    # Add file item with absolute path
                    file_item = QTreeWidgetItem(current_item, [file_path.name])
                    file_item.setData(0, Qt.ItemDataRole.UserRole, str(file_path.resolve()))
                    
                    # Check if this file extension has a corresponding schema
                    if file_path.suffix in self.schema_extensions:
                        try:
                            with open(file_path) as f:
                                data = json.load(f)
                            file_type = self.get_file_type_from_extension(file_path)
                            if file_type not in self.files_by_type:
                                self.files_by_type[file_type] = []
                            self.files_by_type[file_type].append((file_path, data))
                            logging.debug(f"Loaded file: {file_path}")
                        except Exception as e:
                            logging.error(f"Error loading file {file_path}: {str(e)}")
            
            # Expand root item and entities folder
            root_item.setExpanded(True)
            for i in range(root_item.childCount()):
                if root_item.child(i).text(0) == "entities":
                    root_item.child(i).setExpanded(True)
                    break
            
            self.status_label.setText(f'Loaded folder: {self.current_folder.name}\n'
                                    f'{len(self.files_by_type)} file types found\n'
                                    f'{len(self.manifest_files)} manifest files found')
            logging.info(f"Successfully loaded folder: {self.current_folder}")
            logging.info(f"Found files of types: {list(self.files_by_type.keys())}")
            logging.info(f"Found manifest files: {list(self.manifest_files.keys())}")
            
        except Exception as e:
            self.status_label.setText('Error loading folder')
            logging.error(f"Error loading folder: {str(e)}")
            self.current_folder = None
    
    def on_file_selected(self, item: QTreeWidgetItem, column: int):
        """Handle file selection in the tree"""
        file_path_str = item.data(0, Qt.ItemDataRole.UserRole)
        if not file_path_str:  # If no file path stored (might be a directory)
            return
        
        try:
            file_path = Path(file_path_str)
            if not file_path.exists():
                logging.error(f"File not found: {file_path}")
                return
                
            if file_path.is_file() and (file_path.suffix in self.schema_extensions or 
                                      file_path.suffix == '.entity_manifest'):
                logging.info(f"Selected file: {file_path}")
                self.load_file(file_path)
            
        except Exception as e:
            logging.error(f"Error handling file selection: {str(e)}")
            self.status_label.setText('Error selecting file')
            self.status_label.setProperty("status", "error")
            self.status_label.style().unpolish(self.status_label)
            self.status_label.style().polish(self.status_label)
    
    def process_manifest_file(self, file_path: Path, data: dict):
        """Process an entity manifest file and store its data"""
        try:
            if 'ids' in data:
                base_name = file_path.stem  # Remove .entity_manifest
                self.manifest_files[base_name] = {
                    'path': file_path,
                    'ids': data['ids']
                }
                logging.info(f"Processed manifest {base_name} with {len(data['ids'])} entries")
        except Exception as e:
            logging.error(f"Error processing manifest {file_path}: {str(e)}")
    
    def find_related_files(self, file_path: Path) -> list:
        """Find files related through manifests"""
        try:
            entities_folder = self.current_folder / "entities"
            
            # If this is a manifest file, return paths for all referenced IDs
            if file_path.suffix == '.entity_manifest':
                base_name = file_path.stem
                if base_name in self.manifest_files:
                    manifest_data = self.manifest_files[base_name]
                    base_type = base_name  # e.g., 'player' from 'player.entity_manifest'
                    return [
                        (f"{id_name}", entities_folder / f"{id_name}.{base_type}")
                        for id_name in manifest_data['ids']
                    ]
            
            # If this is a referenced file, find manifests that reference it
            base_name = file_path.stem  # e.g., 'trader_loyalist' from 'trader_loyalist.player'
            file_type = file_path.suffix.lstrip('.')  # e.g., 'player' from '.player'
            
            related = []
            if file_type in self.manifest_files:
                manifest = self.manifest_files[file_type]
                if base_name in manifest['ids']:
                    related.append((
                        f"{file_type}.entity_manifest",
                        entities_folder / f"{file_type}.entity_manifest"
                    ))
            
            return related
            
        except Exception as e:
            logging.error(f"Error finding related files: {str(e)}")
            return []
    
    def on_manifest_item_clicked(self, item):
        """Handle clicking on a manifest-related file"""
        file_path = item.data(Qt.ItemDataRole.UserRole)
        if file_path and Path(file_path).exists():
            self.load_file(Path(file_path))
    
    def update_manifest_view(self, file_path: Path):
        """Update the manifest view with related files"""
        related_files = self.find_related_files(file_path)
        
        if related_files:
            self.manifest_list.clear()
            for name, path in related_files:
                item = QListWidgetItem(name)
                item.setData(Qt.ItemDataRole.UserRole, str(path))
                self.manifest_list.addItem(item)
            
            self.manifest_label.setVisible(True)
            self.manifest_list.setVisible(True)
        else:
            self.manifest_label.setVisible(False)
            self.manifest_list.setVisible(False)
    
    def load_file(self, file_path: Path):
        try:
            with open(file_path) as f:
                self.current_data = json.load(f)
            
            self.current_file = file_path
            
            # Process manifest if applicable
            if file_path.suffix == '.entity_manifest':
                self.process_manifest_file(file_path, self.current_data)
            
            # Update manifest view
            self.update_manifest_view(file_path)
            
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
            info_text = [f"File: {file_path.name}", "Entity Data:"]
            if isinstance(self.current_data, dict):
                for key, value in self.current_data.items():
                    if isinstance(value, (list, dict)):
                        info_text.append(f"{key}: {type(value).__name__} ({len(value)} items)")
                    else:
                        info_text.append(f"{key}: {value}")
            else:
                info_text.append(str(self.current_data))
            
            self.editor_label.setText('\n'.join(info_text))
            
            # Select appropriate schema based on file extension
            if file_path.suffix in self.schema_extensions:
                schema_name = self.schema_extensions[file_path.suffix]
                if schema_name in self.schemas:
                    self.schema_selector.setCurrentText(schema_name)
            
            # Validate against current schema if one is selected
            if self.schema_selector.currentText():
                self.validate_current_file()
            
        except Exception as e:
            self.status_label.setText('Error loading file')
            logging.error(f"Error loading file: {str(e)}")
            self.current_file = None
            self.current_data = None
    
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
            self.status_label.style().unpolish(self.status_label)
            self.status_label.style().polish(self.status_label)
        except jsonschema.exceptions.ValidationError as e:
            logging.error(f"Validation error: {str(e)}")
            self.status_label.setText(f"Invalid {schema_name}")
            self.status_label.setProperty("status", "error")
            self.status_label.style().unpolish(self.status_label)
            self.status_label.style().polish(self.status_label)
        except Exception as e:
            logging.error(f"Error during validation: {str(e)}")
            self.status_label.setProperty("status", "error")
            self.status_label.style().unpolish(self.status_label)
            self.status_label.style().polish(self.status_label)
    
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()
    
    def dropEvent(self, event: QDropEvent):
        files = [Path(u.toLocalFile()) for u in event.mimeData().urls()]
        for path in files:
            if path.is_dir():
                self.load_folder(path)
            elif path.is_file():
                self.load_file(path)
            break  # Only load the first item
    
    def load_schemas(self):
        """Load all JSON schemas from the selected directory"""
        if not self.schema_dir or not self.schema_dir.exists():
            return
        
        try:
            # Clear existing schemas and extension mappings
            self.schemas.clear()
            self.schema_selector.clear()
            self.schema_extensions.clear()
            
            # Load all schema files
            schema_files = list(self.schema_dir.glob("*.json"))
            logging.info(f"Found {len(schema_files)} schema files")
            
            for schema_file in schema_files:
                try:
                    with open(schema_file) as f:
                        schema = json.load(f)
                    
                    # Store schema
                    schema_name = schema_file.stem
                    self.schemas[schema_name] = schema
                    
                    # Create extension mapping (e.g., "action-data-source-schema" -> ".action_data_source")
                    if schema_name.endswith('-schema'):
                        ext = schema_name[:-7].replace('-', '_')
                        self.schema_extensions[f".{ext}"] = schema_name
                    
                    logging.debug(f"Loaded schema: {schema_file.name}")
                except Exception as e:
                    logging.error(f"Error loading schema {schema_file.name}: {str(e)}")
            
            # Update schema selector
            self.schema_selector.addItems(sorted(self.schemas.keys()))
            self.schema_selector.setEnabled(True)
            
            logging.info(f"Successfully loaded {len(self.schemas)} schemas")
            logging.debug(f"File extensions mapped: {list(self.schema_extensions.keys())}")
            
            # Validate current file if one is loaded
            if self.current_data:
                self.validate_current_file()
                
        except Exception as e:
            logging.error(f"Error loading schemas: {str(e)}")

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