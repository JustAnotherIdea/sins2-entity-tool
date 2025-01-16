from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, 
                            QPushButton, QLabel, QFileDialog, QHBoxLayout, 
                            QLineEdit, QListWidget, QComboBox, QTreeWidget, QTreeWidgetItem,
                            QTabWidget, QScrollArea, QGroupBox, QFormLayout)
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
        self.schemas = {}
        self.files_by_type = {}
        self.schema_extensions = {}
        self.manifest_files = {}
        
        self.init_ui()
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
        
        # Player selector
        self.player_selector = QComboBox()
        self.player_selector.currentTextChanged.connect(self.on_player_selected)
        left_layout.addWidget(self.player_selector)
        
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
        
        # Right side (entity viewer/editor)
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        
        # Tab widget for different sections
        self.tab_widget = QTabWidget()
        
        # Basic Info Tab
        basic_info_widget = QWidget()
        basic_info_layout = QVBoxLayout(basic_info_widget)
        self.basic_info_form = QFormLayout()
        basic_info_layout.addLayout(self.basic_info_form)
        self.tab_widget.addTab(basic_info_widget, "Basic Info")
        
        # Home Planet Tab
        home_planet_widget = QScrollArea()
        home_planet_widget.setWidgetResizable(True)
        home_planet_content = QWidget()
        self.home_planet_layout = QVBoxLayout(home_planet_content)
        home_planet_widget.setWidget(home_planet_content)
        self.tab_widget.addTab(home_planet_widget, "Home Planet")
        
        # Units Tab
        units_widget = QScrollArea()
        units_widget.setWidgetResizable(True)
        units_content = QWidget()
        self.units_layout = QVBoxLayout(units_content)
        units_widget.setWidget(units_content)
        self.tab_widget.addTab(units_widget, "Units")
        
        # Research Tab
        research_widget = QScrollArea()
        research_widget.setWidgetResizable(True)
        research_content = QWidget()
        self.research_layout = QVBoxLayout(research_content)
        research_widget.setWidget(research_content)
        self.tab_widget.addTab(research_widget, "Research")
        
        # Planet Types Tab
        planet_types_widget = QScrollArea()
        planet_types_widget.setWidgetResizable(True)
        planet_types_content = QWidget()
        self.planet_types_layout = QVBoxLayout(planet_types_content)
        planet_types_widget.setWidget(planet_types_content)
        self.tab_widget.addTab(planet_types_widget, "Planet Types")
        
        right_layout.addWidget(self.tab_widget)
        
        # Add both sides to main layout
        main_layout.addWidget(left_widget, 1)  # 30% width
        main_layout.addWidget(right_widget, 2)  # 70% width
        
        # Enable drag and drop
        self.setAcceptDrops(True)
        
        # Add log handler
        self.log_handler = GUILogHandler(self.log_display)
        self.log_handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
        logging.getLogger().addHandler(self.log_handler)
    
    def update_player_display(self):
        """Update the display with player data"""
        if not self.current_data:
            return
            
        # Clear existing content
        self.clear_all_layouts()
        
        # Basic Info Tab
        self.basic_info_form.addRow("Version:", QLabel(str(self.current_data.get("version", ""))))
        self.basic_info_form.addRow("Race:", QLabel(str(self.current_data.get("race", ""))))
        self.basic_info_form.addRow("Fleet:", QLabel(str(self.current_data.get("fleet", ""))))
        
        if "default_starting_assets" in self.current_data:
            assets_group = QGroupBox("Starting Assets")
            assets_layout = QFormLayout()
            assets = self.current_data["default_starting_assets"]
            assets_layout.addRow("Credits:", QLabel(str(assets.get("credits", ""))))
            assets_layout.addRow("Metal:", QLabel(str(assets.get("metal", ""))))
            assets_layout.addRow("Crystal:", QLabel(str(assets.get("crystal", ""))))
            assets_group.setLayout(assets_layout)
            self.basic_info_form.addRow(assets_group)
        
        # Home Planet Tab
        if "home_planet" in self.current_data:
            home_planet = self.current_data["home_planet"]
            
            # Random Fixture
            fixture_group = QGroupBox("Random Fixture")
            fixture_layout = QFormLayout()
            fixture_layout.addRow("Type:", QLabel(str(home_planet.get("random_fixture_filling", ""))))
            fixture_group.setLayout(fixture_layout)
            self.home_planet_layout.addWidget(fixture_group)
            
            # Levels
            if "levels" in home_planet:
                levels_group = QGroupBox("Levels")
                levels_layout = QVBoxLayout()
                for i, level in enumerate(home_planet["levels"]):
                    level_widget = QGroupBox(f"Level {i+1}")
                    level_form = QFormLayout()
                    
                    if "income_rates" in level:
                        rates = level["income_rates"]
                        level_form.addRow("Credits Rate:", QLabel(str(rates.get("credits", ""))))
                        level_form.addRow("Metal Rate:", QLabel(str(rates.get("metal", ""))))
                        level_form.addRow("Crystal Rate:", QLabel(str(rates.get("crystal", ""))))
                    
                    if "modifier_values" in level:
                        mods = level["modifier_values"]
                        for mod_name, mod_data in mods.items():
                            level_form.addRow(f"{mod_name}:", QLabel(str(mod_data.get("additive", ""))))
                    
                    level_widget.setLayout(level_form)
                    levels_layout.addWidget(level_widget)
                levels_group.setLayout(levels_layout)
                self.home_planet_layout.addWidget(levels_group)
        
        # Units Tab
        units_group = QGroupBox("Buildable Units")
        units_layout = QVBoxLayout()
        
        if "buildable_units" in self.current_data:
            units_list = QListWidget()
            units_list.addItems(self.current_data["buildable_units"])
            units_layout.addWidget(units_list)
        
        units_group.setLayout(units_layout)
        self.units_layout.addWidget(units_group)
        
        # Add more sections as needed...
        
        self.tab_widget.setCurrentIndex(0)  # Show first tab
    
    def clear_all_layouts(self):
        """Clear all tab layouts"""
        # Clear Basic Info
        while self.basic_info_form.rowCount() > 0:
            self.basic_info_form.removeRow(0)
        
        # Clear Home Planet
        self.clear_layout(self.home_planet_layout)
        
        # Clear Units
        self.clear_layout(self.units_layout)
        
        # Clear Research
        self.clear_layout(self.research_layout)
        
        # Clear Planet Types
        self.clear_layout(self.planet_types_layout)
    
    def clear_layout(self, layout):
        """Clear a layout and all its widgets"""
        if layout is not None:
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
                else:
                    self.clear_layout(item.layout())
    
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
            self.player_selector.clear()  # Clear player selector
            
            # Create root item
            root_item = QTreeWidgetItem(self.file_tree, [self.current_folder.name])
            
            # First, look for and process manifest files in the entities folder
            entities_folder = self.current_folder / "entities"
            if entities_folder.exists():
                logging.info(f"Found entities folder: {entities_folder}")
                
                # Process player manifest first to populate player selector
                player_manifest = entities_folder / "player.entity_manifest"
                if player_manifest.exists():
                    try:
                        with open(player_manifest) as f:
                            data = json.load(f)
                            if 'ids' in data:
                                self.player_selector.addItems(sorted(data['ids']))
                                logging.info(f"Added {len(data['ids'])} players to selector")
                    except Exception as e:
                        logging.error(f"Error processing player manifest: {str(e)}")
                
                # Process other manifest files
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
        # This functionality has been removed
        pass
    
    def load_file(self, file_path: Path):
        try:
            with open(file_path) as f:
                self.current_data = json.load(f)
            
            self.current_file = file_path
            
            # Process manifest if applicable
            if file_path.suffix == '.entity_manifest':
                self.process_manifest_file(file_path, self.current_data)
            
            # If it's a player file, update the display
            if file_path.suffix == '.player':
                self.update_player_display()
            
            # Log data details
            logging.info(f"Successfully loaded: {file_path}")
            logging.info(f"Data type: {type(self.current_data)}")
            if isinstance(self.current_data, dict):
                logging.info(f"Top-level keys: {list(self.current_data.keys())}")
                for key, value in self.current_data.items():
                    logging.info(f"{key}: {type(value)}")
                    if isinstance(value, (list, dict)):
                        logging.info(f"{key} length: {len(value)}")
            
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
            
            logging.info(f"Successfully loaded {len(self.schemas)} schemas")
            logging.debug(f"File extensions mapped: {list(self.schema_extensions.keys())}")
                
        except Exception as e:
            logging.error(f"Error loading schemas: {str(e)}")
    
    def on_player_selected(self, player_name: str):
        """Handle player selection from dropdown"""
        if not player_name or not self.current_folder:
            return
            
        # Find and load the selected player file
        player_file = self.current_folder / "entities" / f"{player_name}.player"
        if player_file.exists():
            self.load_file(player_file)
            self.update_player_display()

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