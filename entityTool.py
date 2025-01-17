from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, 
                            QPushButton, QLabel, QFileDialog, QHBoxLayout, 
                            QLineEdit, QListWidget, QComboBox, QTreeWidget, QTreeWidgetItem,
                            QTabWidget, QScrollArea, QGroupBox, QFormLayout, QDialog)
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
        
        # Initialize data structures
        self.current_folder = None
        self.files_by_type = {}
        self.manifest_files = {}
        self.schema_extensions = set()
        self.localized_text = {}
        self.schemas = {}  # Initialize schemas dict first
        self.current_schema = None
        self.current_game_folder = None
        self.current_file = None
        self.current_data = None
        self.schema_dir = None
        self.base_game_localized_text = {}  # Store base game localized text
        self.current_language = "en"  # Default language
        self.texture_cache = {}  # Cache for loaded textures
        
        # Load configuration and schemas
        self.config = self.load_config()
        self.load_schemas()  # Load schemas after config is loaded
        
        # Initialize UI
        self.init_ui()
        
        # Apply stylesheet
        self.load_stylesheet()
        
        self.showMaximized()
    
    def init_ui(self):
        self.setWindowTitle('Sins 2 Entity Tool')
        
        # Create central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # Top toolbar
        toolbar = QWidget()
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(10, 5, 10, 5)
        
        # Left side of toolbar (folder and settings)
        left_toolbar = QWidget()
        left_toolbar_layout = QHBoxLayout(left_toolbar)
        left_toolbar_layout.setContentsMargins(0, 0, 0, 0)
        
        # Folder button with icon
        folder_btn = QPushButton()
        folder_btn.setIcon(QIcon(str(Path(__file__).parent / "icons" / "folder.png")))  # Use custom icon
        folder_btn.setToolTip('Open Mod Folder')
        folder_btn.setFixedSize(32, 32)
        folder_btn.clicked.connect(self.open_folder_dialog)
        left_toolbar_layout.addWidget(folder_btn)
        
        # Settings button with icon
        settings_btn = QPushButton()
        settings_btn.setIcon(QIcon(str(Path(__file__).parent / "icons" / "settings.png")))  # Use custom icon
        settings_btn.setToolTip('Settings')
        settings_btn.setFixedSize(32, 32)
        settings_btn.clicked.connect(self.show_settings_dialog)
        left_toolbar_layout.addWidget(settings_btn)
        
        toolbar_layout.addWidget(left_toolbar)
        
        # Add spacer to push player selector to the right
        toolbar_layout.addStretch()
        
        # Status label in the middle
        self.status_label = QLabel()
        self.status_label.setStyleSheet("padding: 5px;")
        toolbar_layout.addWidget(self.status_label)
        
        # Player selector on the right
        self.player_selector = QComboBox()
        self.player_selector.setFixedWidth(200)
        self.player_selector.currentTextChanged.connect(self.on_player_selected)
        toolbar_layout.addWidget(self.player_selector)
        
        main_layout.addWidget(toolbar)
        
        # Tab widget for different sections (now takes full width)
        self.tab_widget = QTabWidget()
        
        # Add tabs
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
        
        main_layout.addWidget(self.tab_widget)
        
        # Enable drag and drop
        self.setAcceptDrops(True)
    
    def show_settings_dialog(self):
        """Show settings dialog"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Settings")
        layout = QVBoxLayout(dialog)
        
        # Schema folder selection
        schema_layout = QHBoxLayout()
        schema_label = QLabel("Schema Folder:")
        schema_path = QLineEdit(self.config.get("schema_folder", ""))
        schema_path.setReadOnly(True)
        schema_btn = QPushButton("Browse...")
        
        def select_schema_folder():
            folder = QFileDialog.getExistingDirectory(self, "Select Schema Folder")
            if folder:
                schema_path.setText(folder)
                self.config["schema_folder"] = folder
                self.save_config()
                self.load_schemas()  # Reload schemas with new path
        
        schema_btn.clicked.connect(select_schema_folder)
        schema_layout.addWidget(schema_label)
        schema_layout.addWidget(schema_path)
        schema_layout.addWidget(schema_btn)
        
        # Base game folder selection
        base_game_layout = QHBoxLayout()
        base_game_label = QLabel("Base Game Folder:")
        base_game_path = QLineEdit(self.config.get("base_game_folder", ""))
        base_game_path.setReadOnly(True)
        base_game_btn = QPushButton("Browse...")
        
        def select_base_game_folder():
            folder = QFileDialog.getExistingDirectory(self, "Select Base Game Folder")
            if folder:
                base_game_path.setText(folder)
                self.config["base_game_folder"] = folder
                self.save_config()
                self.load_localized_text()  # Reload localized text with new path
        
        base_game_btn.clicked.connect(select_base_game_folder)
        base_game_layout.addWidget(base_game_label)
        base_game_layout.addWidget(base_game_path)
        base_game_layout.addWidget(base_game_btn)
        
        # Add layouts to dialog
        layout.addLayout(schema_layout)
        layout.addLayout(base_game_layout)
        
        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)
        
        dialog.exec()
    
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
        if "buildable_units" in self.current_data:
            # Create split layout for units tab
            units_split = QWidget()
            units_split_layout = QHBoxLayout(units_split)
            
            # Left side - Unit list
            units_list_group = QGroupBox("Buildable Units")
            units_list_layout = QVBoxLayout()
            self.units_list = QListWidget()
            self.units_list.itemClicked.connect(self.on_unit_selected)
            
            # Add units to list
            for unit_id in sorted(self.current_data["buildable_units"]):
                self.units_list.addItem(unit_id)
            
            units_list_layout.addWidget(self.units_list)
            units_list_group.setLayout(units_list_layout)
            units_split_layout.addWidget(units_list_group)
            
            # Right side - Unit details
            unit_details_group = QGroupBox("Unit Details")
            self.unit_details_layout = QVBoxLayout()
            unit_details_group.setLayout(self.unit_details_layout)
            units_split_layout.addWidget(unit_details_group, stretch=2)  # Give details more space
            
            # Add the split layout to the units tab
            self.units_layout.addWidget(units_split)
        
        # Research Tab
        if "research" in self.current_data:
            research_view = self.create_research_view(self.current_data["research"])
            self.research_layout.addWidget(research_view)
        
        self.tab_widget.setCurrentIndex(0)  # Show first tab
    
    def on_unit_selected(self, item):
        """Handle unit selection from the list"""
        if not self.current_folder:
            return
            
        unit_id = item.text()
        unit_file = self.current_folder / "entities" / f"{unit_id}.unit"
        
        try:
            # Load unit data
            unit_data, is_base_game = self.load_file(unit_file)
            if not unit_data:
                logging.error(f"Unit file not found: {unit_file}")
                return
                
            # Clear existing details
            self.clear_layout(self.unit_details_layout)
            
            # Create and add the schema view
            schema_view = self.create_schema_view("unit", unit_data, is_base_game)
            self.unit_details_layout.addWidget(schema_view)
            
        except Exception as e:
            logging.error(f"Error loading unit {unit_id}: {str(e)}")
            error_label = QLabel(f"Error loading unit: {str(e)}")
            error_label.setStyleSheet("color: red;")
            self.unit_details_layout.addWidget(error_label)
    
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
            self.player_selector.clear()  # Clear player selector
            
            # Load localized text first
            self.load_localized_text()
            
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
            
            logging.info(f"Successfully loaded folder: {self.current_folder}")
            logging.info(f"Found files of types: {list(self.files_by_type.keys())}")
            logging.info(f"Found manifest files: {list(self.manifest_files.keys())}")
            
        except Exception as e:
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
            if try_base_game and self.config.get("base_game_folder"):
                base_game_path = Path(self.config["base_game_folder"]) / file_path.relative_to(self.current_folder)
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
        """Load schema files from the schema folder"""
        schema_folder = self.config.get("schema_folder")
        if not schema_folder:
            logging.warning("No schema folder configured")
            return
            
        schema_path = Path(schema_folder)
        if not schema_path.exists():
            logging.error(f"Schema folder does not exist: {schema_path}")
            return
            
        try:
            # Clear existing extensions and schemas
            self.schema_extensions = set()
            self.schemas = {}
            
            # Process each schema file
            schema_files = list(schema_path.glob("*-schema.json"))  # Changed pattern to match actual filenames
            logging.info(f"Found {len(schema_files)} schema files")
            
            for file_path in schema_files:
                try:
                    with open(file_path, encoding='utf-8') as f:
                        schema = json.load(f)
                        
                    # Get schema name from filename (e.g. "unit-schema.json" -> "unit-schema")
                    schema_name = file_path.stem  # This will be e.g. "unit-schema"
                    self.schemas[schema_name] = schema
                    
                    # Add file extension if specified in schema
                    if 'fileExtension' in schema:
                        ext = schema['fileExtension']
                        if not ext.startswith('.'):
                            ext = '.' + ext
                        self.schema_extensions.add(ext)
                        
                    logging.info(f"Loaded schema: {schema_name}")
                except Exception as e:
                    logging.error(f"Error loading schema {file_path}: {str(e)}")
            
            logging.info(f"Successfully loaded {len(self.schemas)} schemas")
            
        except Exception as e:
            logging.error(f"Error loading schemas: {str(e)}")
    
    def load_localized_text(self):
        """Load localized text from the base game folder"""
        base_game_folder = self.config.get("base_game_folder")
        if not base_game_folder:
            logging.warning("No base game folder configured")
            return
            
        localization_path = Path(base_game_folder) / "localization"
        if not localization_path.exists():
            logging.error(f"Localization folder does not exist: {localization_path}")
            return
            
        try:
            # Clear existing localized text
            self.localized_text.clear()
            
            # Load each language file
            for lang_file in localization_path.glob("*.json"):
                try:
                    lang_code = lang_file.stem
                    with open(lang_file, encoding='utf-8') as f:
                        self.localized_text[lang_code] = json.load(f)
                    logging.info(f"Loaded base game localized text for {lang_code}")
                except Exception as e:
                    logging.error(f"Error loading language file {lang_file}: {str(e)}")
                    
        except Exception as e:
            logging.error(f"Error loading localized text: {str(e)}")
    
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
        try:
            with open(file_path, encoding='utf-8') as f:
                data = json.load(f)
                
            self.current_file = file_path
            self.current_data = data
            
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
                
        except Exception as e:
            logging.error(f"Error loading file {file_path}: {str(e)}")
            self.current_file = None
            self.current_data = None
    
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
        base_game_folder = self.config.get("base_game_folder")
        if base_game_folder:
            texture_path = Path(base_game_folder) / "textures" / f"{texture_name}.png"
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
        if not schema:
            return QLabel("Invalid schema")
            
        # Handle schema references
        if "$ref" in schema:
            ref_path = schema["$ref"].split("/")[1:]  # Skip the '#'
            current = self.current_schema
            for part in ref_path:
                if part in current:
                    current = current[part]
                else:
                    return QLabel(f"Invalid reference: {schema['$ref']}")
            return self.create_widget_for_schema(data, current, is_base_game)
            
        schema_type = schema.get("type")
        if not schema_type:
            return QLabel("Schema missing type")
            
        if schema_type == "object":
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
            
        elif schema_type == "array":
            group = QGroupBox()
            layout = QVBoxLayout()
            
            # Get the schema for array items
            items_schema = schema.get("items", {})
            if isinstance(items_schema, dict):
                # Single schema for all items
                for i, item in enumerate(data):
                    widget = self.create_widget_for_schema(
                        item, items_schema, is_base_game
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
            elif isinstance(items_schema, list):
                # Tuple validation (different schema for each index)
                for i, (item, item_schema) in enumerate(zip(data, items_schema)):
                    widget = self.create_widget_for_schema(
                        item, item_schema, is_base_game
                    )
                    if widget:
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
        # Add property name to schema for special handling
        if isinstance(schema, dict):
            schema = schema.copy()  # Create a copy to avoid modifying the original
            schema["property_name"] = prop_name
            
        # Handle references to other schema definitions
        if "$ref" in schema:
            ref_path = schema["$ref"].split("/")[1:]  # Skip the '#'
            current = self.current_schema
            for part in ref_path:
                if part in current:
                    current = current[part]
                else:
                    return QLabel(f"Invalid reference: {schema['$ref']}")
            # Pass along the property name when resolving references
            if isinstance(current, dict):
                current = current.copy()
                current["property_name"] = prop_name
            return self.create_widget_for_schema(value, current, is_base_game)
            
        # Handle arrays
        if schema.get("type") == "array":
            return self.create_widget_for_schema(value, schema, is_base_game)
            
        # Handle objects
        if schema.get("type") == "object":
            return self.create_widget_for_schema(value, schema, is_base_game)
            
        # Handle simple values
        return self.create_widget_for_value(value, schema, is_base_game)
    
    def create_widget_for_value(self, value: any, schema: dict, is_base_game: bool) -> QWidget:
        """Create a widget for a simple value based on its schema type"""
        if isinstance(value, str) and schema.get("type") == "string":
            # Special handling for name and description fields - treat them as localized text
            if schema.get("property_name", "").lower() in ["name", "name_uppercase", "description"]:
                text, is_base = self.get_localized_text(value)
                label = QLabel(text)
                label.setWordWrap(True)
                if is_base or is_base_game:
                    label.setStyleSheet("color: #666666; font-style: italic;")
                return label
            elif schema.get("format") == "localized_text":
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
            # Clear any existing details
            while self.research_details_layout.count():
                item = self.research_details_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            
            # Create and add the schema view
            schema_view = self.create_schema_view("research-subject", subject_data, is_base_game)
            self.research_details_layout.addWidget(schema_view)
            
        except Exception as e:
            logging.error(f"Error loading research subject {subject_id}: {str(e)}")
    
    def on_research_subject_clicked(self, item):
        """Handle clicking on a research subject in the list"""
        subject_id = item.text()
        self.load_research_subject(subject_id)
    
    def load_config(self) -> dict:
        """Load configuration from file"""
        config_path = Path(__file__).parent / "config.json"
        default_config = {
            "schema_folder": "",
            "base_game_folder": ""
        }
        
        try:
            if config_path.exists():
                with open(config_path) as f:
                    return json.load(f)
            return default_config
        except Exception as e:
            logging.error(f"Error loading config: {str(e)}")
            return default_config
    
    def save_config(self):
        """Save configuration to file"""
        config_path = Path(__file__).parent / "config.json"
        try:
            with open(config_path, 'w') as f:
                json.dump(self.config, f, indent=4)
            logging.info("Configuration saved successfully")
        except Exception as e:
            logging.error(f"Error saving config: {str(e)}")

    def load_stylesheet(self):
        """Load and apply the dark theme stylesheet from QSS file"""
        try:
            style_path = Path(__file__).parent / "style.qss"
            if not style_path.exists():
                logging.error("Style file not found")
                return
                
            with open(style_path, 'r') as f:
                style = f.read()
                
            self.setStyleSheet(style)
            logging.info("Loaded stylesheet")
        except Exception as e:
            logging.error(f"Error loading stylesheet: {str(e)}")

    def on_player_selected(self, player_name: str):
        """Handle player selection from dropdown"""
        if not player_name or not self.current_folder:
            return
            
        # Find and load the selected player file
        player_file = self.current_folder / "entities" / f"{player_name}.player"
        self.load_main_file(player_file) 

    def create_schema_view(self, file_type: str, file_data: dict, is_base_game: bool = False) -> QWidget:
        """Create a reusable schema view for any file type.
        
        Args:
            file_type: The type of file (e.g. 'unit', 'research-subject')
            file_data: The data to display
            is_base_game: Whether the data is from the base game
            
        Returns:
            A QWidget containing the schema view
        """
        # Get the schema name
        schema_name = f"{file_type}-schema"
        if schema_name not in self.schemas:
            logging.error(f"Schema not found: {schema_name}")
            error_widget = QWidget()
            error_layout = QVBoxLayout(error_widget)
            error_layout.addWidget(QLabel(f"Schema not found: {schema_name}"))
            return error_widget
        
        self.current_schema = self.schemas[schema_name]
        
        # Create scrollable area for the content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        # Create content widget
        content = QWidget()
        content_layout = QVBoxLayout(content)
        
        # Add name if available
        if "name" in file_data:
            name_text, is_base_game_name = self.get_localized_text(file_data["name"])
            name_label = QLabel(name_text)
            name_label.setStyleSheet("font-size: 16px; font-weight: bold;")
            if is_base_game or is_base_game_name:
                name_label.setStyleSheet(name_label.styleSheet() + "; color: #666666; font-style: italic;")
            content_layout.addWidget(name_label)
        
        # Add description if available
        if "description" in file_data:
            desc_text, is_base_game_desc = self.get_localized_text(file_data["description"])
            desc_label = QLabel(desc_text)
            desc_label.setWordWrap(True)
            if is_base_game or is_base_game_desc:
                desc_label.setStyleSheet("color: #666666; font-style: italic;")
            content_layout.addWidget(desc_label)
        
        # Add picture if available
        if "tooltip_picture" in file_data:
            picture_label = self.create_texture_label(file_data["tooltip_picture"], max_size=256)
            content_layout.addWidget(picture_label)
        
        # Create the main details widget using the schema
        title = f"{file_type.replace('-', ' ').title()} Details (Base Game)" if is_base_game else f"{file_type.replace('-', ' ').title()} Details"
        details_group = QGroupBox(title)
        if is_base_game:
            details_group.setStyleSheet("QGroupBox { color: #666666; font-style: italic; }")
        
        # Create the content widget using the schema
        details_widget = self.create_widget_for_schema(file_data, self.current_schema, is_base_game)
        details_layout = QVBoxLayout()
        details_layout.addWidget(details_widget)
        details_group.setLayout(details_layout)
        content_layout.addWidget(details_group)
        
        scroll.setWidget(content)
        return scroll 