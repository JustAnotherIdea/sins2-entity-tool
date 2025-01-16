from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, 
                            QPushButton, QLabel, QFileDialog, QHBoxLayout, 
                            QLineEdit, QListWidget, QComboBox, QTreeWidget, QTreeWidgetItem,
                            QTabWidget, QScrollArea, QGroupBox, QFormLayout)
from PyQt6.QtCore import Qt, QMimeData
from PyQt6.QtGui import QDragEnterEvent, QDropEvent, QPixmap, QIcon
import json
import logging
from pathlib import Path
import jsonschema
from research_view import ResearchTreeView
import os

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

class EntityToolGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.current_folder = None
        self.base_game_folder = None
        self.current_file = None
        self.current_data = None
        self.schema_dir = None
        self.schemas = {}
        self.files_by_type = {}
        self.schema_extensions = {}
        self.manifest_files = {}
        self.localized_text = {}  # Store localized text data
        self.base_game_localized_text = {}  # Store base game localized text
        self.current_language = "en"  # Default language
        self.texture_cache = {}  # Cache for loaded textures
        
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
        
        # Base game directory selection
        base_game_layout = QHBoxLayout()
        self.base_game_path_label = QLabel('No base game directory selected')
        self.base_game_path_label.setWordWrap(True)
        base_game_btn = QPushButton('Select Base Game Directory')
        base_game_btn.clicked.connect(self.select_base_game_directory)
        base_game_layout.addWidget(self.base_game_path_label)
        base_game_layout.addWidget(base_game_btn)
        left_layout.addLayout(base_game_layout)
        
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
        race_text, is_base_game_race = self.get_localized_text(str(self.current_data.get("race", "")))
        fleet_text, is_base_game_fleet = self.get_localized_text(str(self.current_data.get("fleet", "")))
        
        race_label = QLabel(race_text)
        fleet_label = QLabel(fleet_text)
        if is_base_game_race:
            race_label.setStyleSheet("color: #666666; font-style: italic;")
        if is_base_game_fleet:
            fleet_label.setStyleSheet("color: #666666; font-style: italic;")
            
        self.basic_info_form.addRow("Race:", race_label)
        self.basic_info_form.addRow("Fleet:", fleet_label)
        
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
        
        # Research Tab
        if "research" in self.current_data:
            research_view = self.create_research_view(self.current_data["research"])
            self.research_layout.addWidget(research_view)
        
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
    
    def select_base_game_directory(self):
        """Open directory dialog to select base game directory"""
        dir_path = QFileDialog.getExistingDirectory(
            self,
            "Select Base Game Directory",
            str(self.base_game_folder) if self.base_game_folder else ""
        )
        if dir_path:
            self.base_game_folder = Path(dir_path)
            self.base_game_path_label.setText(str(self.base_game_folder))
            self.load_base_game_localized_text()
    
    def load_base_game_localized_text(self):
        """Load localized text files from the base game folder"""
        if not self.base_game_folder:
            return
            
        localized_text_dir = self.base_game_folder / "localized_text"
        if not localized_text_dir.exists():
            logging.warning("No localized_text directory found in base game folder")
            return
            
        # Clear existing base game localized text
        self.base_game_localized_text.clear()
        
        # Load all localized text files
        for text_file in localized_text_dir.glob("*.localized_text"):
            try:
                language_code = text_file.stem
                with open(text_file, encoding='utf-8') as f:
                    text_data = json.load(f)
                self.base_game_localized_text[language_code] = text_data
                logging.info(f"Loaded base game localized text for {language_code}")
            except Exception as e:
                logging.error(f"Error loading base game localized text file {text_file}: {str(e)}")
    
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
            
            # Load localized text first
            self.load_localized_text()
            
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
                            with open(file_path, encoding='utf-8') as f:
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
            if file_path.is_file() and (file_path.suffix in self.schema_extensions or 
                                      file_path.suffix == '.entity_manifest'):
                logging.info(f"Selected file: {file_path}")
                self.load_main_file(file_path)
            
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
    
    def load_file(self, file_path: Path, try_base_game: bool = True) -> tuple[dict, bool]:
        """Load a file from mod folder or base game folder.
        Returns tuple of (data, is_from_base_game)"""
        try:
            # Try mod folder first
            if file_path.exists():
                with open(file_path, encoding='utf-8') as f:
                    return json.load(f), False
            
            # Try base game folder if enabled
            if try_base_game and self.base_game_folder:
                base_game_path = self.base_game_folder / file_path.relative_to(self.current_folder)
                if base_game_path.exists():
                    with open(base_game_path, encoding='utf-8') as f:
                        return json.load(f), True
            
            raise FileNotFoundError(f"File not found in mod or base game folder: {file_path}")
            
        except Exception as e:
            logging.error(f"Error loading file {file_path}: {str(e)}")
            return None, False
    
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
        self.load_main_file(player_file)
    
    def load_research_subject(self, subject_id: str):
        """Load a research subject file and display its details using the schema"""
        if not self.current_folder or not hasattr(self, 'research_details_layout'):
            return
            
        # Look for the research subject file in the entities folder
        subject_file = self.current_folder / "entities" / f"{subject_id}.research_subject"
        subject_data, is_base_game = self.load_file(subject_file)
        
        if not subject_data:
            logging.error(f"Research subject file not found: {subject_file}")
            return
            
        try:
            # Get the research subject schema
            schema_name = "research-subject-schema"
            if schema_name not in self.schemas:
                logging.error(f"Schema not found: {schema_name}")
                return
                
            self.current_schema = self.schemas[schema_name]
            
            # Create the details widget using the schema
            title = "Research Subject Details (Base Game)" if is_base_game else "Research Subject Details"
            details_group = QGroupBox(title)
            if is_base_game:
                details_group.setStyleSheet("QGroupBox { color: #666666; font-style: italic; }")
            
            # Create scrollable area for the content
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            
            # Create the content widget using the schema
            content_widget = self.create_widget_for_schema(subject_data, self.current_schema, is_base_game)
            scroll.setWidget(content_widget)
            
            # Add the scroll area to the details group
            details_layout = QVBoxLayout()
            details_layout.addWidget(scroll)
            details_group.setLayout(details_layout)
            
            # Clear any existing details and add the new ones
            while self.research_details_layout.count():
                item = self.research_details_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            
            self.research_details_layout.addWidget(details_group)
            
        except Exception as e:
            logging.error(f"Error loading research subject {subject_id}: {str(e)}")
    
    def on_research_subject_clicked(self, item):
        """Handle clicking on a research subject in the list"""
        subject_id = item.text()
        self.load_research_subject(subject_id)
    
    def load_localized_text(self):
        """Load localized text files from the localized_text folder"""
        if not self.current_folder:
            return
            
        localized_text_dir = self.current_folder / "localized_text"
        if not localized_text_dir.exists():
            logging.warning("No localized_text directory found")
            return
            
        # Clear existing localized text
        self.localized_text.clear()
        
        # Load all localized text files
        for text_file in localized_text_dir.glob("*.localized_text"):
            try:
                language_code = text_file.stem  # Get language code from filename
                with open(text_file, encoding='utf-8') as f:
                    text_data = json.load(f)
                self.localized_text[language_code] = text_data
                logging.info(f"Loaded localized text for {language_code}")
            except Exception as e:
                logging.error(f"Error loading localized text file {text_file}: {str(e)}")
    
    def get_localized_text(self, text_key: str) -> tuple[str, bool]:
        """Get localized text for a key and whether it's from base game.
        Returns tuple of (text, is_from_base_game)"""
        if not text_key:
            return "", False
            
        if text_key.startswith(":"):  # Raw string
            return text_key[1:], False
        
        # Try current language in mod folder first
        if self.current_language in self.localized_text:
            if text_key in self.localized_text[self.current_language]:
                return self.localized_text[self.current_language][text_key], False
        
        # Try English in mod folder
        if "en" in self.localized_text:
            if text_key in self.localized_text["en"]:
                return self.localized_text["en"][text_key], False
        
        # Try base game current language
        if self.current_language in self.base_game_localized_text:
            if text_key in self.base_game_localized_text[self.current_language]:
                return self.base_game_localized_text[self.current_language][text_key], True
        
        # Try base game English
        if "en" in self.base_game_localized_text:
            if text_key in self.base_game_localized_text["en"]:
                return self.base_game_localized_text["en"][text_key], True
        
        return text_key, False  # Return key if no translation found
    
    def create_localized_label(self, text_key: str) -> QLabel:
        """Create a QLabel with localized text"""
        text, is_base_game = self.get_localized_text(text_key)
        label = QLabel(text)
        label.setWordWrap(True)
        if is_base_game:
            label.setStyleSheet("color: #666666; font-style: italic;")  # Gray and italic for base game content
        return label
    
    def load_main_file(self, file_path: Path):
        """Load a file as the main displayed file"""
        data, is_base_game = self.load_file(file_path)
        if data is None:
            self.status_label.setText('Error loading file')
            self.current_file = None
            self.current_data = None
            return
            
        self.current_file = file_path
        self.current_data = data
        
        # Process manifest if applicable
        if file_path.suffix == '.entity_manifest':
            self.process_manifest_file(file_path, self.current_data)
        
        # If it's a player file, update the display
        if file_path.suffix == '.player':
            self.update_player_display()
        
        # Log data details
        source = "base game" if is_base_game else "mod"
        logging.info(f"Successfully loaded from {source}: {file_path}")
        logging.info(f"Data type: {type(self.current_data)}")
        if isinstance(self.current_data, dict):
            logging.info(f"Top-level keys: {list(self.current_data.keys())}")
            for key, value in self.current_data.items():
                logging.info(f"{key}: {type(value)}")
                if isinstance(value, (list, dict)):
                    logging.info(f"{key} length: {len(value)}")

    def load_texture(self, texture_name: str) -> tuple[QPixmap, bool]:
        """Load a texture from mod or base game folder.
        Returns tuple of (pixmap, is_from_base_game)"""
        if not texture_name:
            return QPixmap(), False
            
        # Check cache first
        cache_key = f"{self.current_folder}:{texture_name}"
        if cache_key in self.texture_cache:
            return self.texture_cache[cache_key]
            
        # Try mod folder first
        if self.current_folder:
            texture_path = self.current_folder / "textures" / f"{texture_name}.png"
            if texture_path.exists():
                pixmap = QPixmap(str(texture_path))
                if not pixmap.isNull():
                    self.texture_cache[cache_key] = (pixmap, False)
                    return pixmap, False
        
        # Try base game folder
        if self.base_game_folder:
            texture_path = self.base_game_folder / "textures" / f"{texture_name}.png"
            if texture_path.exists():
                pixmap = QPixmap(str(texture_path))
                if not pixmap.isNull():
                    self.texture_cache[cache_key] = (pixmap, True)
                    return pixmap, True
        
        # Return empty pixmap if texture not found
        logging.warning(f"Texture not found: {texture_name}")
        return QPixmap(), False
    
    def create_texture_label(self, texture_name: str, max_size: int = 128) -> QLabel:
        """Create a QLabel with a texture, scaled to max_size"""
        pixmap, is_base_game = self.load_texture(texture_name)
        
        label = QLabel()
        if not pixmap.isNull():
            # Scale pixmap while maintaining aspect ratio
            scaled_pixmap = pixmap.scaled(max_size, max_size, 
                                        Qt.AspectRatioMode.KeepAspectRatio, 
                                        Qt.TransformationMode.SmoothTransformation)
            label.setPixmap(scaled_pixmap)
            if is_base_game:
                label.setStyleSheet("QLabel { background-color: #f0f0f0; padding: 4px; font-style: italic; }")
                label.setToolTip(f"Base game texture: {texture_name}")
            else:
                label.setToolTip(f"Mod texture: {texture_name}")
        else:
            label.setText(f"[Texture not found: {texture_name}]")
            label.setStyleSheet("QLabel { color: #666666; font-style: italic; }")
        
        return label

    def create_research_view(self, research_data: dict) -> QWidget:
        """Create a custom research view that mimics the game's UI"""
        container = QWidget()
        layout = QVBoxLayout(container)
        
        # Create domain selector
        domain_widget = QWidget()
        domain_layout = QHBoxLayout(domain_widget)
        domain_layout.setContentsMargins(0, 0, 0, 10)  # Add some bottom margin
        
        # Create research tree view
        tree_view = ResearchTreeView()
        tree_view.node_clicked.connect(self.load_research_subject)
        
        # Create split layout for tree and details
        split_widget = QWidget()
        split_layout = QHBoxLayout(split_widget)
        split_layout.addWidget(tree_view, 2)  # 2/3 of the width
        
        # Create details panel
        details_widget = QWidget()
        self.research_details_layout = QVBoxLayout(details_widget)
        split_layout.addWidget(details_widget, 1)  # 1/3 of the width
        
        # Load field backgrounds from research data
        field_backgrounds = {}
        if "research_domains" in research_data:
            for domain_name, domain_data in research_data["research_domains"].items():
                if "research_fields" in domain_data:
                    for field_data in domain_data["research_fields"]:
                        field_id = field_data.get("id")
                        picture = field_data.get("picture")
                        if field_id and picture:
                            pixmap, is_base_game = self.load_texture(picture)
                            if not pixmap.isNull():
                                field_backgrounds[field_id] = pixmap
                                logging.info(f"Loaded background for field {field_id}: {picture}")
        
        # Set field backgrounds in tree view
        tree_view.set_field_backgrounds(field_backgrounds)
        
        # Add research subjects to the view
        if "research_subjects" in research_data:
            # First pass: collect all subjects and sort by tier
            subjects_by_tier = {}
            for subject_id in research_data["research_subjects"]:
                subject_file = self.current_folder / "entities" / f"{subject_id}.research_subject"
                subject_data, is_base_game = self.load_file(subject_file)
                
                if subject_data:
                    tier = subject_data.get("tier", 0)  # Default to tier 0
                    if tier not in subjects_by_tier:
                        subjects_by_tier[tier] = []
                    subjects_by_tier[tier].append((subject_id, subject_data, is_base_game))
            
            # Second pass: add nodes tier by tier
            for tier in sorted(subjects_by_tier.keys()):
                for subject_id, subject_data, is_base_game in subjects_by_tier[tier]:
                    name_text, is_base_game_name = self.get_localized_text(subject_data.get("name", subject_id))
                    icon = None
                    if "tooltip_picture" in subject_data:
                        pixmap, _ = self.load_texture(subject_data["tooltip_picture"])
                        if not pixmap.isNull():
                            icon = pixmap
                    
                    field = subject_data.get("field", "")
                    field_coord = subject_data.get("field_coord")
                    
                    tree_view.add_research_subject(
                        subject_id=subject_id,
                        name=name_text,
                        icon=icon,
                        domain=subject_data.get("domain", ""),
                        field=field,
                        tier=tier,
                        field_coord=field_coord,
                        is_base_game=is_base_game or is_base_game_name,
                        prerequisites=subject_data.get("prerequisites", [])
                    )
            
            # Add domain buttons after all nodes are added
            for domain in sorted(tree_view.domains):
                domain_btn = QPushButton(domain)
                domain_btn.setCheckable(True)
                domain_btn.setAutoExclusive(True)  # Make buttons mutually exclusive
                domain_btn.clicked.connect(lambda checked, d=domain: tree_view.set_domain(d))
                domain_layout.addWidget(domain_btn)
                
                # Select first domain by default
                if domain == next(iter(tree_view.domains)):
                    domain_btn.setChecked(True)
                    tree_view.set_domain(domain)  # Explicitly set initial domain
        
        layout.addWidget(domain_widget)
        layout.addWidget(split_widget)
        return container 

    def get_research_field_picture_path(self, domain: str, field_id: str) -> str:
        """Get the path to a research field's background picture."""
        # First check mod folder
        mod_path = f"textures/advent_research_field_picture_{domain}_{field_id}.png"
        if os.path.exists(mod_path):
            return mod_path
        
        # Then check game folder
        game_path = os.path.join(os.environ.get('SINS2_PATH', ''), 
                                f"textures/advent_research_field_picture_{domain}_{field_id}.png")
        if os.path.exists(game_path):
            return game_path
        
        return None 

    def load_field_backgrounds(self, domain: str, fields: list):
        """Load background images for all fields in a domain."""
        backgrounds = {}
        for field in fields:
            path = self.get_research_field_picture_path(domain, field['id'])
            if path:
                pixmap = QPixmap(path)
                if not pixmap.isNull():
                    backgrounds[field['id']] = pixmap
        
        self.set_field_backgrounds(backgrounds) 

    def set_domain(self, domain: str):
        """Switch to displaying a different domain"""
        self.current_domain = domain
        
        # Load field backgrounds for this domain
        if domain in self.research_data['research_domains']:
            fields = self.research_data['research_domains'][domain]['research_fields']
            self.load_field_backgrounds(domain, fields)
        
        # Rest of existing code... 

    def create_widget_for_schema(self, data: dict, schema: dict, is_base_game: bool = False) -> QWidget:
        """Create a widget to display data according to a JSON schema"""
        if not schema or "type" not in schema:
            return QLabel("Invalid schema")
            
        if schema["type"] == "object":
            group = QGroupBox()
            layout = QFormLayout() if len(schema.get("properties", {})) < 5 else QVBoxLayout()
            
            # Sort properties alphabetically but prioritize common fields
            priority_fields = ["name", "description", "id", "type", "version"]
            properties = schema.get("properties", {}).items()
            sorted_properties = sorted(properties, 
                                    key=lambda x: (x[0] not in priority_fields, x[0].lower()))
            
            for prop_name, prop_schema in sorted_properties:
                if prop_name in data:
                    widget = self.create_widget_for_property(
                        prop_name, data[prop_name], prop_schema, is_base_game
                    )
                    if widget:
                        if isinstance(layout, QFormLayout):
                            layout.addRow(prop_name.replace("_", " ").title() + ":", widget)
                        else:
                            prop_group = QGroupBox(prop_name.replace("_", " ").title())
                            prop_layout = QVBoxLayout()
                            prop_layout.addWidget(widget)
                            prop_group.setLayout(prop_layout)
                            layout.addWidget(prop_group)
            
            group.setLayout(layout)
            return group
            
        elif schema["type"] == "array":
            group = QGroupBox()
            layout = QVBoxLayout()
            
            for i, item in enumerate(data):
                widget = self.create_widget_for_schema(
                    item, schema.get("items", {}), is_base_game
                )
                if widget:
                    if isinstance(item, dict) and "modifier_type" in item:
                        # Special handling for modifier arrays
                        layout.addWidget(widget)
                    else:
                        item_group = QGroupBox(f"Item {i+1}")
                        item_layout = QVBoxLayout()
                        item_layout.addWidget(widget)
                        item_group.setLayout(item_layout)
                        layout.addWidget(item_group)
            
            group.setLayout(layout)
            return group
            
        else:
            return self.create_widget_for_value(data, schema, is_base_game)
    
    def create_widget_for_property(self, prop_name: str, value: any, schema: dict, is_base_game: bool) -> QWidget:
        """Create a widget for a specific property based on its schema"""
        if "$ref" in schema:
            # Handle references to other schema definitions
            ref_path = schema["$ref"].split("/")[1:]  # Skip the '#'
            current = self.current_schema
            for part in ref_path:
                if part in current:
                    current = current[part]
                else:
                    return QLabel(f"Invalid reference: {schema['$ref']}")
            return self.create_widget_for_schema(value, current, is_base_game)
            
        if schema.get("type") == "array":
            return self.create_widget_for_schema(value, schema, is_base_game)
            
        if schema.get("type") == "object":
            return self.create_widget_for_schema(value, schema, is_base_game)
            
        return self.create_widget_for_value(value, schema, is_base_game)
    
    def create_widget_for_value(self, value: any, schema: dict, is_base_game: bool) -> QWidget:
        """Create a widget for a simple value based on its schema type"""
        if isinstance(value, str) and schema.get("type") == "string":
            if schema.get("format") == "localized_text":
                # Handle localized text
                text, is_base = self.get_localized_text(value)
                label = QLabel(text)
                label.setWordWrap(True)
                if is_base or is_base_game:
                    label.setStyleSheet("color: #666666; font-style: italic;")
                return label
            elif schema.get("format") == "texture":
                # Handle texture references
                return self.create_texture_label(value)
            else:
                # Regular string
                label = QLabel(value)
                label.setWordWrap(True)
                return label
        else:
            # Handle numbers, booleans, etc.
            label = QLabel(str(value))
            label.setWordWrap(True)
            return label
    
    def load_research_subject(self, subject_id: str):
        """Load a research subject file and display its details using the schema"""
        if not self.current_folder or not hasattr(self, 'research_details_layout'):
            return
            
        # Look for the research subject file in the entities folder
        subject_file = self.current_folder / "entities" / f"{subject_id}.research_subject"
        subject_data, is_base_game = self.load_file(subject_file)
        
        if not subject_data:
            logging.error(f"Research subject file not found: {subject_file}")
            return
            
        try:
            # Get the research subject schema
            schema_name = "research-subject-schema"
            if schema_name not in self.schemas:
                logging.error(f"Schema not found: {schema_name}")
                return
                
            self.current_schema = self.schemas[schema_name]
            
            # Create the details widget using the schema
            title = "Research Subject Details (Base Game)" if is_base_game else "Research Subject Details"
            details_group = QGroupBox(title)
            if is_base_game:
                details_group.setStyleSheet("QGroupBox { color: #666666; font-style: italic; }")
            
            # Create scrollable area for the content
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            
            # Create the content widget using the schema
            content_widget = self.create_widget_for_schema(subject_data, self.current_schema, is_base_game)
            scroll.setWidget(content_widget)
            
            # Add the scroll area to the details group
            details_layout = QVBoxLayout()
            details_layout.addWidget(scroll)
            details_group.setLayout(details_layout)
            
            # Clear any existing details and add the new ones
            while self.research_details_layout.count():
                item = self.research_details_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            
            self.research_details_layout.addWidget(details_group)
            
        except Exception as e:
            logging.error(f"Error loading research subject {subject_id}: {str(e)}") 