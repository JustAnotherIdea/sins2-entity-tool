from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, 
                            QPushButton, QLabel, QFileDialog, QHBoxLayout, 
                            QLineEdit, QListWidget, QComboBox, QTreeWidget, QTreeWidgetItem,
                            QTabWidget, QScrollArea, QGroupBox, QFormLayout, QDialog, QSplitter, QToolButton,
                            QSpinBox, QDoubleSpinBox, QCheckBox)
from PyQt6.QtCore import Qt, QMimeData
from PyQt6.QtGui import (QDragEnterEvent, QDropEvent, QPixmap, QIcon, QKeySequence,
                        QShortcut)
import json
import logging
from pathlib import Path
import jsonschema
from research_view import ResearchTreeView
import os
from command_stack import CommandStack, EditValueCommand
from typing import List, Any

logging.basicConfig(level=logging.DEBUG)

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
        
        # Initialize variables
        self.current_folder = None
        self.base_game_folder = None  # Initialize base game folder
        self.current_file = None
        self.current_data = None
        self.current_schema = None
        self.current_language = "en"  # Default to English
        self.files_by_type = {}
        self.manifest_files = {}
        self.texture_cache = {}
        self.schemas = {}
        self.schema_extensions = set()
        self.localized_text = {}
        self.base_game_localized_text = {}
        self.command_stack = CommandStack()
        
        # Load config
        try:
            with open('config.json', 'r') as f:
                self.config = json.load(f)
                if "base_game_folder" in self.config:
                    self.base_game_folder = Path(self.config["base_game_folder"])
                    logging.info(f"Loaded base game folder from config: {self.base_game_folder}")
        except FileNotFoundError:
            self.config = {}
            logging.warning("No config.json found, using defaults")
        except json.JSONDecodeError:
            self.config = {}
            logging.error("Error parsing config.json, using defaults")
        
        # Load schemas
        self.load_schemas()
        
        # Initialize UI
        self.init_ui()
        
        # Apply stylesheet
        self.load_stylesheet()
        
        self.showMaximized()
        
        self.setup_shortcuts()
    
    def setup_shortcuts(self):
        """Set up keyboard shortcuts for undo/redo"""
        undo_shortcut = QShortcut(QKeySequence.StandardKey.Undo, self)
        undo_shortcut.activated.connect(self.undo)
        
        redo_shortcut = QShortcut(QKeySequence.StandardKey.Redo, self)
        redo_shortcut.activated.connect(self.redo)
    
    def undo(self):
        """Undo the last command"""
        self.command_stack.undo()
        self.update_save_button()  # Update button states
    
    def redo(self):
        """Redo the last undone command"""
        self.command_stack.redo()
        self.update_save_button()  # Update button states
    
    def update_data_value(self, data_path: list, new_value: any):
        """Update a value in the data structure using its path"""
        logging.info(f"Updating data value at path {data_path} to {new_value}")
        logging.debug(f"Current data before update: {self.current_data}")
        
        current = self.current_data
        for i, key in enumerate(data_path[:-1]):
            logging.debug(f"Traversing path element {i}: {key}")
            if isinstance(current, dict):
                if key not in current:
                    current[key] = {} if isinstance(data_path[i + 1], str) else []
                    logging.debug(f"Created new dict/list for key {key}")
                current = current[key]
            elif isinstance(current, list):
                while len(current) <= key:
                    current.append({} if isinstance(data_path[i + 1], str) else [])
                    logging.debug(f"Extended list to accommodate index {key}")
                current = current[key]
        
        if data_path:
            if isinstance(current, dict):
                logging.debug(f"Setting dict key {data_path[-1]} to {new_value}")
                current[data_path[-1]] = new_value
            elif isinstance(current, list):
                while len(current) <= data_path[-1]:
                    current.append(None)
                    logging.debug(f"Extended list to accommodate final index {data_path[-1]}")
                logging.debug(f"Setting list index {data_path[-1]} to {new_value}")
                current[data_path[-1]] = new_value
                
        logging.debug(f"Current data after update: {self.current_data}")
    
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
        folder_btn.setIcon(QIcon(str(Path(__file__).parent / "icons" / "folder.png")))
        folder_btn.setToolTip('Open Mod Folder')
        folder_btn.setFixedSize(32, 32)
        folder_btn.clicked.connect(self.open_folder_dialog)
        left_toolbar_layout.addWidget(folder_btn)
        
        # Settings button with icon
        settings_btn = QPushButton()
        settings_btn.setIcon(QIcon(str(Path(__file__).parent / "icons" / "settings.png")))
        settings_btn.setToolTip('Settings')
        settings_btn.setFixedSize(32, 32)
        settings_btn.clicked.connect(self.show_settings_dialog)
        left_toolbar_layout.addWidget(settings_btn)
        
        # Save button with icon
        save_btn = QPushButton()
        save_btn.setIcon(QIcon(str(Path(__file__).parent / "icons" / "save.png")))
        save_btn.setToolTip('Save Changes')
        save_btn.setFixedSize(32, 32)
        save_btn.clicked.connect(self.save_changes)
        save_btn.setEnabled(False)  # Initially disabled
        self.save_btn = save_btn  # Store reference
        left_toolbar_layout.addWidget(save_btn)
        
        # Undo button with icon
        undo_btn = QPushButton()
        undo_btn.setIcon(QIcon(str(Path(__file__).parent / "icons" / "undo.png")))
        undo_btn.setToolTip('Undo (Ctrl+Z)')
        undo_btn.setFixedSize(32, 32)
        undo_btn.clicked.connect(self.undo)
        undo_btn.setEnabled(False)  # Initially disabled
        self.undo_btn = undo_btn  # Store reference
        left_toolbar_layout.addWidget(undo_btn)
        
        # Redo button with icon
        redo_btn = QPushButton()
        redo_btn.setIcon(QIcon(str(Path(__file__).parent / "icons" / "redo.png")))
        redo_btn.setToolTip('Redo (Ctrl+Y)')
        redo_btn.setFixedSize(32, 32)
        redo_btn.clicked.connect(self.redo)
        redo_btn.setEnabled(False)  # Initially disabled
        self.redo_btn = redo_btn  # Store reference
        left_toolbar_layout.addWidget(redo_btn)
        
        toolbar_layout.addWidget(left_toolbar)
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
        
        # Tab widget for different sections
        self.tab_widget = QTabWidget()
        
        # Basic Info Tab
        basic_info_widget = QScrollArea()
        basic_info_widget.setWidgetResizable(True)
        basic_info_content = QWidget()
        basic_info_layout = QVBoxLayout(basic_info_content)
        self.basic_info_form = QFormLayout()
        basic_info_layout.addLayout(self.basic_info_form)
        basic_info_widget.setWidget(basic_info_content)
        self.tab_widget.addTab(basic_info_widget, "Basic Info")
        
        # Home Planet Tab
        home_planet_widget = QScrollArea()
        home_planet_widget.setWidgetResizable(True)
        home_planet_content = QWidget()
        self.home_planet_layout = QVBoxLayout(home_planet_content)
        home_planet_widget.setWidget(home_planet_content)
        self.tab_widget.addTab(home_planet_widget, "Home Planet")
        
        # Units Tab with split panels
        units_widget = QScrollArea()
        units_widget.setWidgetResizable(True)
        units_content = QWidget()
        self.units_layout = QVBoxLayout(units_content)  # Store reference to units layout

        # Create split layout for units tab
        units_split = QSplitter(Qt.Orientation.Horizontal)
        
        # Left side - Unit list
        units_list_group = QGroupBox("Buildable Units")
        units_list_layout = QVBoxLayout()
        self.units_list = QListWidget()
        self.units_list.itemClicked.connect(self.on_unit_selected)
        units_list_layout.addWidget(self.units_list)
        units_list_group.setLayout(units_list_layout)
        units_split.addWidget(units_list_group)
        
        # Right side - Details panels
        details_widget = QWidget()
        details_layout = QVBoxLayout(details_widget)
        details_layout.setSpacing(10)  # Add spacing between rows
        
        # Top row of details (Unit Details and Unit Skin)
        top_row = QSplitter(Qt.Orientation.Horizontal)
        
        # Unit Details panel
        unit_details_group = QGroupBox("Unit Details")
        self.unit_details_layout = QVBoxLayout(unit_details_group)
        top_row.addWidget(unit_details_group)
        
        # Unit Skin panel
        skin_details_group = QGroupBox("Unit Skin")
        self.skin_details_layout = QVBoxLayout(skin_details_group)
        top_row.addWidget(skin_details_group)
        
        # Set sizes for top row (1:1 ratio)
        top_row.setSizes([100, 100])
        
        # Bottom row of details (Weapon and Ability)
        bottom_row = QSplitter(Qt.Orientation.Horizontal)
        
        # Weapon panel
        weapon_details_group = QGroupBox("Weapon")
        self.weapon_details_layout = QVBoxLayout(weapon_details_group)
        bottom_row.addWidget(weapon_details_group)
        
        # Ability panel
        ability_details_group = QGroupBox("Ability")
        self.ability_details_layout = QVBoxLayout(ability_details_group)
        bottom_row.addWidget(ability_details_group)
        
        # Set sizes for bottom row (1:1 ratio)
        bottom_row.setSizes([100, 100])
        
        # Add rows to details layout with equal stretch factors
        details_layout.addWidget(top_row, stretch=1)
        details_layout.addWidget(bottom_row, stretch=1)
        
        # Add details widget to splitter
        units_split.addWidget(details_widget)
        
        # Set initial sizes for the main splitter (1:4 ratio)
        units_split.setSizes([100, 400])
        
        # Add the split layout to the units tab
        self.units_layout.addWidget(units_split)
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
                self.base_game_folder = Path(folder)  # Update base_game_folder path
                self.save_config()
                self.load_all_localized_strings()  # Reload localized strings with new path
                self.load_all_texture_files()  # Reload texture files with new path
        
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
        
        # Units Tab
        if "buildable_units" in self.current_data:
            # Clear the units list
            self.units_list.clear()
            
            # Add units to list
            for unit_id in sorted(self.current_data["buildable_units"]):
                self.units_list.addItem(unit_id)
            
            # Clear all detail panels
            self.clear_layout(self.unit_details_layout)
            self.clear_layout(self.weapon_details_layout)
            self.clear_layout(self.skin_details_layout)
            self.clear_layout(self.ability_details_layout)
        
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
            # Check if we have data in the command stack first
            unit_data = self.command_stack.get_file_data(unit_file)
            is_base_game = False
            
            if unit_data is None:
                # Load from file if not in command stack
                unit_data, is_base_game = self.load_file(unit_file)
                if not unit_data:
                    logging.error(f"Unit file not found: {unit_file}")
                    return
                    
                # Store initial data in command stack
                self.command_stack.update_file_data(unit_file, unit_data)
            else:
                logging.info(f"Using data from command stack for {unit_file}")
                
            # Update current file and data
            self.current_file = unit_file
            self.current_data = unit_data
                
            # Clear existing details in all panels
            self.clear_layout(self.unit_details_layout)
            self.clear_layout(self.weapon_details_layout)
            self.clear_layout(self.skin_details_layout)
            self.clear_layout(self.ability_details_layout)
            
            # Create and add the schema view for unit details
            schema_view = self.create_schema_view("unit", unit_data, is_base_game, unit_file)
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
        self.units_list.clear()
        self.clear_layout(self.unit_details_layout)
        self.clear_layout(self.weapon_details_layout)
        self.clear_layout(self.skin_details_layout)
        self.clear_layout(self.ability_details_layout)
        
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
            
            # Load localized text and textures
            self.load_all_localized_strings()  # Load all strings into memory
            self.load_all_texture_files()  # Load all texture files into memory
            
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
                        print(f"Adding schema extension: {schema['fileExtension']}")
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

        # Check if text_key is a dictionary and extract the 'group' if it is
        if isinstance(text_key, dict) and 'group' in text_key:
            text_key = text_key['group']

        if text_key.startswith(":"):  # Raw string
            return text_key[1:], False
        
        # Try current language in mod folder first
        if self.current_language in self.all_localized_strings['mod']:
            if text_key in self.all_localized_strings['mod'][self.current_language]:
                return self.all_localized_strings['mod'][self.current_language][text_key], False
        
        # Try English in mod folder
        if "en" in self.all_localized_strings['mod']:
            if text_key in self.all_localized_strings['mod']["en"]:
                return self.all_localized_strings['mod']["en"][text_key], False
        
        # Try base game current language
        if self.current_language in self.all_localized_strings['base_game']:
            if text_key in self.all_localized_strings['base_game'][self.current_language]:
                return self.all_localized_strings['base_game'][self.current_language][text_key], True
        
        # Try base game English
        if "en" in self.all_localized_strings['base_game']:
            if text_key in self.all_localized_strings['base_game']["en"]:
                return self.all_localized_strings['base_game']["en"][text_key], True
        
        return text_key, False  # Return key if no translation found
    
    def create_localized_label(self, text_key: str) -> QLabel:
        """Create a QLabel with localized text"""
        text, is_base_game = self.get_localized_text(text_key)
        label = QLabel(text)
        label.setWordWrap(True)
        if is_base_game:
            label.setStyleSheet("color: #666666; font-style: italic;")  # Gray and italic for base game content
        return label
    
    def load_player_file(self, file_path: Path):
        """Load a player file into the application"""
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
        if texture_name in self.all_texture_files['mod']:
            texture_path = self.current_folder / "textures" / f"{texture_name}.png"
            if texture_path.exists():
                pixmap = QPixmap(str(texture_path))
                if not pixmap.isNull():
                    self.texture_cache[cache_key] = (pixmap, False)
                    return pixmap, False
                    
            # Try DDS if PNG not found
            texture_path = self.current_folder / "textures" / f"{texture_name}.dds"
            if texture_path.exists():
                pixmap = QPixmap(str(texture_path))
                if not pixmap.isNull():
                    self.texture_cache[cache_key] = (pixmap, False)
                    return pixmap, False
        
        # Try base game folder
        if texture_name in self.all_texture_files['base_game']:
            base_game_folder = self.config.get("base_game_folder")
            if base_game_folder:
                texture_path = Path(base_game_folder) / "textures" / f"{texture_name}.png"
                if texture_path.exists():
                    pixmap = QPixmap(str(texture_path))
                    if not pixmap.isNull():
                        self.texture_cache[cache_key] = (pixmap, True)
                        return pixmap, True
                        
                # Try DDS if PNG not found
                texture_path = Path(base_game_folder) / "textures" / f"{texture_name}.dds"
            if texture_path.exists():
                pixmap = QPixmap(str(texture_path))
                if not pixmap.isNull():
                    self.texture_cache[cache_key] = (pixmap, True)
                    return pixmap, True
        
        # Return empty pixmap if texture not found
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

    def create_widget_for_schema(self, data: dict, schema: dict, is_base_game: bool = False, path: list = None) -> QWidget:
        """Create a widget to display data according to a JSON schema"""
        if path is None:
            path = []
            
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
            return self.create_widget_for_schema(data, current, is_base_game, path)
            
        schema_type = schema.get("type")
        if not schema_type:
            return QLabel("Schema missing type")
            
        if schema_type == "object":
            container = QWidget()
            container_layout = QVBoxLayout(container)
            container_layout.setContentsMargins(0, 0, 0, 0)
            container_layout.setSpacing(0)
            
            # Sort properties alphabetically but prioritize common fields
            priority_fields = ["name", "description", "id", "type", "version"]
            properties = schema.get("properties", {}).items()
            sorted_properties = sorted(properties, 
                                    key=lambda x: (x[0] not in priority_fields, x[0].lower()))
            
            for prop_name, prop_schema in sorted_properties:
                if prop_name in data:
                    value = data[prop_name]
                    
                    # Check if this is a simple value or array of simple values
                    is_simple_value = isinstance(value, (str, int, float, bool))
                    is_simple_array = (
                        isinstance(value, list) and
                        value and  # Check if array is not empty
                        all(isinstance(x, (str, int, float, bool)) for x in value)
                    )
                    # Update path for this property
                    prop_path = path + [prop_name]
                    
                    # Special handling for abilities array
                    if prop_name == "abilities" and isinstance(value, list):
                        group_widget = QWidget()
                        group_layout = QVBoxLayout(group_widget)
                        group_layout.setContentsMargins(0, 0, 0, 0)
                        
                        # Create collapsible button
                        toggle_btn = QToolButton()
                        toggle_btn.setStyleSheet("QToolButton { border: none; }")
                        toggle_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
                        toggle_btn.setArrowType(Qt.ArrowType.RightArrow)
                        toggle_btn.setText("Abilities")
                        toggle_btn.setCheckable(True)
                        
                        # Create content widget
                        content = QWidget()
                        content_layout = QVBoxLayout(content)
                        content_layout.setContentsMargins(20, 0, 0, 0)  # Add left margin for indentation
                        
                        for ability_group in value:
                            if isinstance(ability_group, dict) and "abilities" in ability_group:
                                for ability_id in ability_group["abilities"]:
                                    btn = QPushButton(ability_id)
                                    btn.setStyleSheet("text-align: left; padding: 2px;")
                                    btn.clicked.connect(lambda checked, a=ability_id: self.load_referenced_entity(a, "ability"))
                                    content_layout.addWidget(btn)
                        
                        content.setVisible(False)  # Initially collapsed
                        
                        def update_arrow_state(checked, btn=toggle_btn):
                            btn.setArrowType(Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow)
                        
                        toggle_btn.toggled.connect(content.setVisible)
                        toggle_btn.toggled.connect(update_arrow_state)
                        
                        group_layout.addWidget(toggle_btn)
                        group_layout.addWidget(content)
                        container_layout.addWidget(group_widget)
                        continue
                        
                    # Special handling for skin_groups array
                    elif prop_name == "skin_groups" and isinstance(value, list):
                        group_widget = QWidget()
                        group_layout = QVBoxLayout(group_widget)
                        group_layout.setContentsMargins(0, 0, 0, 0)
                        
                        # Create collapsible button
                        toggle_btn = QToolButton()
                        toggle_btn.setStyleSheet("QToolButton { border: none; }")
                        toggle_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
                        toggle_btn.setArrowType(Qt.ArrowType.RightArrow)
                        toggle_btn.setText("Skins")
                        toggle_btn.setCheckable(True)
                        
                        # Create content widget
                        content = QWidget()
                        content_layout = QVBoxLayout(content)
                        content_layout.setContentsMargins(20, 0, 0, 0)  # Add left margin for indentation
                        
                        for skin_group in value:
                            if isinstance(skin_group, dict) and "skins" in skin_group:
                                for skin_id in skin_group["skins"]:
                                    btn = QPushButton(skin_id)
                                    btn.setStyleSheet("text-align: left; padding: 2px;")
                                    btn.clicked.connect(lambda checked, s=skin_id: self.load_referenced_entity(s, "unit_skin"))
                                    content_layout.addWidget(btn)
                        
                        content.setVisible(False)  # Initially collapsed
                        
                        def update_arrow_state(checked, btn=toggle_btn):
                            btn.setArrowType(Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow)
                        
                        toggle_btn.toggled.connect(content.setVisible)
                        toggle_btn.toggled.connect(update_arrow_state)
                        
                        group_layout.addWidget(toggle_btn)
                        group_layout.addWidget(content)
                        container_layout.addWidget(group_widget)
                        continue
                    
                    # Create widget for the property with updated path
                    widget = self.create_widget_for_property(
                        prop_name, value, prop_schema, is_base_game, prop_path
                    )
                    if widget:
                        if is_simple_value or is_simple_array:
                            # Create simple label and value layout for primitive types and simple arrays
                            row_widget = QWidget()
                            row_layout = QHBoxLayout(row_widget)
                            row_layout.setContentsMargins(0, 2, 0, 2)  # Add small vertical spacing
                            
                            label = QLabel(prop_name.replace("_", " ").title() + ":")
                            row_layout.addWidget(label)
                            row_layout.addWidget(widget)
                            row_layout.addStretch()
                            
                            container_layout.addWidget(row_widget)
                        else:
                            # Create collapsible section for complex types
                            group_widget = QWidget()
                            group_layout = QVBoxLayout(group_widget)
                            group_layout.setContentsMargins(0, 0, 0, 0)
                            
                            # Create collapsible button
                            toggle_btn = QToolButton()
                            toggle_btn.setStyleSheet("QToolButton { border: none; }")
                            toggle_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
                            toggle_btn.setArrowType(Qt.ArrowType.RightArrow)
                            toggle_btn.setText(prop_name.replace("_", " ").title())
                            toggle_btn.setCheckable(True)
                            
                            # Create content widget
                            content = QWidget()
                            content_layout = QVBoxLayout(content)
                            content_layout.setContentsMargins(20, 0, 0, 0)  # Add left margin for indentation
                            content_layout.addWidget(widget)
                            
                            content.setVisible(False)  # Initially collapsed
                            
                            def update_arrow_state(checked, btn=toggle_btn):
                                btn.setArrowType(Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow)
                            
                            toggle_btn.toggled.connect(content.setVisible)
                            toggle_btn.toggled.connect(update_arrow_state)
                            
                            group_layout.addWidget(toggle_btn)
                            group_layout.addWidget(content)
                            container_layout.addWidget(group_widget)
            
            return container
            
        elif schema_type == "array":
            container = QWidget()
            container_layout = QVBoxLayout(container)
            container_layout.setContentsMargins(0, 0, 0, 0)
            container_layout.setSpacing(0)
            
            # Get the schema for array items
            items_schema = schema.get("items", {})
            if isinstance(items_schema, dict):
                # Check if array contains simple values
                is_simple_array = (
                    items_schema.get("type") in ["string", "number", "boolean", "integer"] and
                    not any(key in items_schema for key in ["$ref", "format", "properties"]) and
                    all(isinstance(x, (str, int, float, bool)) for x in data)
                )
                
                if is_simple_array:
                    # For simple arrays, show values directly in a vertical layout
                    for i, item in enumerate(data):
                        # Update path for this array item
                        item_path = path + [i]
                        widget = self.create_widget_for_value(item, items_schema, is_base_game, item_path)
                        container_layout.addWidget(widget)
                else:
                    # For complex arrays, use collapsible sections
                    for i, item in enumerate(data):
                        # Update path for this array item
                        item_path = path + [i]
                        widget = self.create_widget_for_schema(
                            item, items_schema, is_base_game, item_path
                        )
                        if widget:
                            if isinstance(item, dict) and "modifier_type" in item:
                                # Special handling for modifier arrays
                                container_layout.addWidget(widget)
                            else:
                                group_widget = QWidget()
                                group_layout = QVBoxLayout(group_widget)
                                group_layout.setContentsMargins(0, 0, 0, 0)
                                
                                # Create collapsible button
                                toggle_btn = QToolButton()
                                toggle_btn.setStyleSheet("QToolButton { border: none; }")
                                toggle_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
                                toggle_btn.setArrowType(Qt.ArrowType.RightArrow)
                                toggle_btn.setText(f"Item {i+1}")
                                toggle_btn.setCheckable(True)
                                
                                # Create content widget
                                content = QWidget()
                                content_layout = QVBoxLayout(content)
                                content_layout.setContentsMargins(20, 0, 0, 0)  # Add left margin for indentation
                                content_layout.addWidget(widget)
                                
                                content.setVisible(False)  # Initially collapsed
                                
                                def update_arrow_state(checked, btn=toggle_btn):
                                    btn.setArrowType(Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow)
                                
                                toggle_btn.toggled.connect(content.setVisible)
                                toggle_btn.toggled.connect(update_arrow_state)
                                
                                group_layout.addWidget(toggle_btn)
                                group_layout.addWidget(content)
                                container_layout.addWidget(group_widget)
            
            return container
            
        else:
            # For simple values, use create_widget_for_value with path
            return self.create_widget_for_value(data, schema, is_base_game, path)
    
    def create_widget_for_property(self, prop_name: str, value: any, schema: dict, is_base_game: bool, path: list = None) -> QWidget:
        """Create a widget for a specific property based on its schema"""
        if path is None:
            path = []
            
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
            return self.create_widget_for_schema(value, current, is_base_game, path)
            
        # Handle arrays
        if schema.get("type") == "array":
            return self.create_widget_for_schema(value, schema, is_base_game, path)
            
        # Handle objects
        if schema.get("type") == "object":
            return self.create_widget_for_schema(value, schema, is_base_game, path)
            
        # Handle simple values
        return self.create_widget_for_value(value, schema, is_base_game, path)
    
    def create_widget_for_value(self, value: any, schema: dict, is_base_game: bool, path: list = None) -> QWidget:
        """Create an editable widget for a value based on its schema type"""
        if path is None:
            path = []
            
        from PyQt6.QtWidgets import QSpinBox, QDoubleSpinBox, QComboBox, QLineEdit, QCheckBox
        
        # Handle references to other entity types first
        property_name = schema.get("property_name", "").lower()
        
        # Convert value to string if it's not already
        value_str = str(value) if value is not None else ""
        
        # Check if this is a reference to another entity type
        is_weapon = isinstance(value, str) and property_name in ["weapon"]
        is_skin = isinstance(value, str) and property_name in ["skins"]
        is_ability = isinstance(value, str) and property_name in ["abilities"]
        if is_weapon or is_skin or is_ability:
            btn = QPushButton(value_str)
            btn.setStyleSheet("text-align: left; padding: 2px;")
            
            if is_weapon:
                btn.clicked.connect(lambda: self.load_referenced_entity(value_str, "weapon"))
            elif is_skin:
                btn.clicked.connect(lambda: self.load_referenced_entity(value_str, "unit_skin"))
            elif is_ability:
                btn.clicked.connect(lambda: self.load_referenced_entity(value_str, "ability"))
            
            if is_base_game:
                btn.setStyleSheet(btn.styleSheet() + "; color: #666666; font-style: italic;")
            
            # Store path and original value
            btn.setProperty("data_path", path)
            btn.setProperty("original_value", value)
            return btn
            
        # Special handling for name and description fields - treat them as localized text
        elif property_name in ["name", "name_uppercase", "description"] or schema.get("format") == "localized_text":
            text, is_base = self.get_localized_text(value_str)
            edit = QLineEdit(text)
            if is_base or is_base_game:
                edit.setStyleSheet("color: #666666; font-style: italic;")
                edit.setReadOnly(True)
            else:
                # Connect text changed signal to command creation
                edit.textChanged.connect(lambda text: self.on_text_changed(edit, text))
            
            # Store path and original value
            edit.setProperty("data_path", path)
            edit.setProperty("original_value", value)
            return edit
            
        elif schema.get("format") == "texture":
            # Handle texture references - keep as non-editable for now
            label = self.create_texture_label(value_str)
            label.setProperty("data_path", path)
            label.setProperty("original_value", value)
            return label
            
        # Handle different schema types
        schema_type = schema.get("type")
        
        if schema_type == "string":
            if "enum" in schema:
                # Create dropdown for enum values
                combo = QComboBox()
                combo.addItems(schema["enum"])
                current_index = combo.findText(value_str)
                if current_index >= 0:
                    combo.setCurrentIndex(current_index)
                if is_base_game:
                    combo.setStyleSheet("color: #666666; font-style: italic;")
                    combo.setEnabled(False)  # Disable combo box for base game content
                else:
                    # Connect currentTextChanged signal to command creation
                    combo.currentTextChanged.connect(lambda text: self.on_combo_changed(combo, text))
                
                # Store path and original value
                combo.setProperty("data_path", path)
                combo.setProperty("original_value", value)
                return combo
            else:
                edit = QLineEdit(value_str)
                if is_base_game:
                    edit.setStyleSheet("color: #666666; font-style: italic;")
                    edit.setReadOnly(True)
                else:
                    # Connect text changed signal to command creation
                    edit.textChanged.connect(lambda text: self.on_text_changed(edit, text))
                
                # Store path and original value
                edit.setProperty("data_path", path)
                edit.setProperty("original_value", value)
                return edit
                
        elif schema_type == "integer":
            spin = QSpinBox()
            spin.setValue(int(value) if value is not None else 0)
            
            # Set minimum and maximum if specified
            if "minimum" in schema:
                spin.setMinimum(schema["minimum"])
            else:
                spin.setMinimum(-1000000)  # Reasonable default minimum
                
            if "maximum" in schema:
                spin.setMaximum(schema["maximum"])
            else:
                spin.setMaximum(1000000)  # Reasonable default maximum
                
            if is_base_game:
                spin.setStyleSheet("color: #666666; font-style: italic;")
                spin.setReadOnly(True)  # Make spinbox read-only for base game content
                spin.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)  # Hide up/down buttons
            else:
                # Connect valueChanged signal to command creation
                spin.valueChanged.connect(lambda value: self.on_spin_changed(spin, value))
            
            # Store path and original value
            spin.setProperty("data_path", path)
            spin.setProperty("original_value", value)
            return spin
            
        elif schema_type == "number":
            spin = QDoubleSpinBox()
            
            # Convert value to float, handling scientific notation
            try:
                float_value = float(value) if value is not None else 0.0
            except (ValueError, TypeError):
                float_value = 0.0
            
            # Set range first to ensure value can be set
            spin.setRange(-1e20, 1e20)
            
            # Set decimals before value to ensure precision
            spin.setDecimals(15)  # Maximum precision
            
            # Now set the value
            spin.setValue(float_value)
            
            # Set step size
            spin.setStepType(QDoubleSpinBox.StepType.AdaptiveDecimalStepType)
            spin.setSingleStep(0.000001)  # Small step size for precision
            
            if is_base_game:
                spin.setStyleSheet("color: #666666; font-style: italic;")
                spin.setReadOnly(True)  # Make spinbox read-only for base game content
                spin.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)  # Hide up/down buttons
            else:
                # Connect valueChanged signal to command creation
                spin.valueChanged.connect(lambda value: self.on_spin_changed(spin, value))
            
            # Store path and original value
            spin.setProperty("data_path", path)
            spin.setProperty("original_value", value)
            return spin
            
        elif schema_type == "boolean":
            checkbox = QCheckBox()
            checkbox.setChecked(bool(value))
            if is_base_game:
                checkbox.setStyleSheet("color: #666666; font-style: italic;")
                checkbox.setEnabled(False)  # Disable checkbox for base game content
            else:
                # Connect stateChanged signal to command creation
                checkbox.stateChanged.connect(lambda state: self.on_checkbox_changed(checkbox, state))
            
            # Store path and original value
            checkbox.setProperty("data_path", path)
            checkbox.setProperty("original_value", value)
            return checkbox
            
        elif schema_type == "object":
            # For objects, create a widget that shows the object's structure
            group = QGroupBox()
            layout = QVBoxLayout()
            for key, val in value.items():
                if isinstance(val, dict):
                    # Recursively handle nested objects
                    nested_widget = self.create_widget_for_value(val, {"type": "object"}, is_base_game, path + [key])
                    layout.addWidget(QLabel(key))
                    layout.addWidget(nested_widget)
                else:
                    # Handle simple values
                    row_widget = QWidget()
                    row_layout = QHBoxLayout(row_widget)
                    row_layout.addWidget(QLabel(f"{key}:"))
                    value_widget = self.create_widget_for_value(val, {"type": type(val).__name__}, is_base_game, path + [key])
                    row_layout.addWidget(value_widget)
                    layout.addWidget(row_widget)
            group.setLayout(layout)
            
            # Store path and original value
            group.setProperty("data_path", path)
            group.setProperty("original_value", value)
            return group
            
        else:
            # Fallback for unknown types
            edit = QLineEdit(str(value))
            if is_base_game:
                edit.setStyleSheet("color: #666666; font-style: italic;")
                edit.setReadOnly(True)
            
            # Store path and original value
            edit.setProperty("data_path", path)
            edit.setProperty("original_value", value)
            return edit
    
    def load_referenced_entity(self, entity_id: str, entity_type: str):
        """Load a referenced entity file and display it in the appropriate panel"""
        if not self.current_folder:
            return
            
        # Try mod folder first
        entity_file = self.current_folder / "entities" / f"{entity_id}.{entity_type}"
        entity_data = None
        is_base_game = False
        
        try:
            # Check if we have data in the command stack first
            entity_data = self.command_stack.get_file_data(entity_file)
            if entity_data is not None:
                logging.info(f"Using data from command stack for {entity_file}")
                is_base_game = False
            else:
                # Try mod folder first
                if entity_file.exists():
                    logging.info(f"Loading referenced entity from mod folder: {entity_file}")
                    with open(entity_file, encoding='utf-8') as f:
                        entity_data = json.load(f)
                        is_base_game = False
                    logging.info(f"Successfully loaded data for {entity_file}")
                    logging.debug(f"Initial data for {entity_file}: {entity_data}")
                
                # Try base game folder if not found in mod folder
                elif self.config.get("base_game_folder"):
                    base_game_file = Path(self.config["base_game_folder"]) / "entities" / f"{entity_id}.{entity_type}"
                    if base_game_file.exists():
                        logging.info(f"Loading referenced entity from base game: {base_game_file}")
                        with open(base_game_file, encoding='utf-8') as f:
                            entity_data = json.load(f)
                            is_base_game = True
                        entity_file = base_game_file
                        logging.info(f"Successfully loaded base game data for {entity_file}")
                        logging.debug(f"Initial base game data for {entity_file}: {entity_data}")
            
            if not entity_data:
                logging.error(f"{entity_type} file not found: {entity_id}")
                return
                
            # Store data in command stack if it wasn't already there
            if entity_file not in self.command_stack.file_data:
                logging.info(f"Storing initial data in command stack for {entity_file}")
                self.command_stack.update_file_data(entity_file, entity_data)
            
            # Clear the appropriate panel and display the new data
            if entity_type == "weapon":
                self.clear_layout(self.weapon_details_layout)
                schema_view = self.create_schema_view("weapon", entity_data, is_base_game, entity_file)
                self.weapon_details_layout.addWidget(schema_view)
                self.weapon_file = entity_file  # Store file path
                logging.info(f"Created weapon schema view for {entity_file}")
            elif entity_type == "unit_skin":
                self.clear_layout(self.skin_details_layout)
                schema_view = self.create_schema_view("unit-skin", entity_data, is_base_game, entity_file)
                self.skin_details_layout.addWidget(schema_view)
                self.skin_file = entity_file  # Store file path
                logging.info(f"Created unit skin schema view for {entity_file}")
            elif entity_type == "ability":
                self.clear_layout(self.ability_details_layout)
                schema_view = self.create_schema_view("ability", entity_data, is_base_game, entity_file)
                self.ability_details_layout.addWidget(schema_view)
                self.ability_file = entity_file  # Store file path
                logging.info(f"Created ability schema view for {entity_file}")
                
        except Exception as e:
            logging.error(f"Error loading {entity_type} {entity_id}: {str(e)}")
            # Add error message to appropriate panel
            error_label = QLabel(f"Error loading {entity_type}: {str(e)}")
            error_label.setStyleSheet("color: red;")
            if entity_type == "weapon":
                self.weapon_details_layout.addWidget(error_label)
            elif entity_type == "unit_skin":
                self.skin_details_layout.addWidget(error_label)
            elif entity_type == "ability":
                self.ability_details_layout.addWidget(error_label)
    
    def load_research_subject(self, subject_id: str):
        """Load a research subject file and display its details using the schema"""
        if not self.current_folder or not hasattr(self, 'research_details_layout'):
            return
            
        # Look for the research subject file in the entities folder
        subject_file = self.current_folder / "entities" / f"{subject_id}.research_subject"
        
        try:
            # Check if we have data in the command stack first
            subject_data = self.command_stack.get_file_data(subject_file)
            is_base_game = False
            
            if subject_data is None:
                # Load from file if not in command stack
                subject_data, is_base_game = self.load_file(subject_file)
                if not subject_data:
                    logging.error(f"Research subject file not found: {subject_file}")
                    return
                    
                # Store initial data in command stack
                self.command_stack.update_file_data(subject_file, subject_data)
            else:
                logging.info(f"Using data from command stack for {subject_file}")
            
            # Clear any existing details
            while self.research_details_layout.count():
                item = self.research_details_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            
            # Create and add the schema view
            schema_view = self.create_schema_view("research-subject", subject_data, is_base_game, subject_file)
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
        self.load_player_file(player_file) 

    def create_schema_view(self, file_type: str, file_data: dict, is_base_game: bool = False, file_path: Path = None) -> QWidget:
        """Create a reusable schema view for any file type.
        
        Args:
            file_type: The type of file (e.g. 'unit', 'research-subject')
            file_data: The data to display
            is_base_game: Whether the data is from the base game
            file_path: The path to the file being displayed
            
        Returns:
            A QWidget containing the schema view
        """
        logging.debug(f"Creating schema view for {file_type}")
        logging.debug(f"Is base game: {is_base_game}")
        logging.debug(f"File path: {file_path}")
        
        # Store file data in command stack if file path is provided
        if file_path is not None:
            self.command_stack.update_file_data(file_path, file_data)
            logging.debug(f"Stored file data for {file_path} in command stack")
        
        # Get the schema name
        schema_name = f"{file_type}-schema"
        if schema_name not in self.schemas:
            logging.error(f"Schema not found: {schema_name}")
            error_widget = QWidget()
            error_layout = QVBoxLayout(error_widget)
            error_layout.addWidget(QLabel(f"Schema not found: {schema_name}"))
            return error_widget
        
        logging.debug(f"Found schema: {schema_name}")
        self.current_schema = self.schemas[schema_name]
        
        # Create scrollable area for the content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        # Store file path and type in the scroll area
        scroll.setProperty("file_path", str(file_path) if file_path else None)
        scroll.setProperty("file_type", file_type)
        
        # Create content widget
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(10)  # Add spacing between elements
        
        def update_content(new_data: dict, data_path: List[str] = None, value: Any = None, source_widget = None):
            """Update the content widget with new data"""
            logging.info(f"Updating schema view content for {file_path}")
            logging.debug(f"Data path: {data_path}, Value: {value}, Source widget: {source_widget}")
            
            if data_path is None or source_widget is None:
                # Full update - recreate entire view
                logging.debug("Performing full update")
                
                # Clear existing content
                while content_layout.count():
                    item = content_layout.takeAt(0)
                    if item.widget():
                        item.widget().deleteLater()
                
                # Add name if available
                if "name" in new_data:
                    logging.debug("Adding name field")
                    name_text, is_base_game_name = self.get_localized_text(new_data["name"])
                    name_label = QLabel(name_text)
                    name_label.setStyleSheet("font-size: 16px; font-weight: bold;")
                    if is_base_game or is_base_game_name:
                        name_label.setStyleSheet(name_label.styleSheet() + "; color: #666666; font-style: italic;")
                    content_layout.addWidget(name_label)
                
                # Add description if available
                if "description" in new_data:
                    logging.debug("Adding description field")
                    desc_text, is_base_game_desc = self.get_localized_text(new_data["description"])
                    desc_label = QLabel(desc_text)
                    desc_label.setWordWrap(True)
                    if is_base_game or is_base_game_desc:
                        desc_label.setStyleSheet("color: #666666; font-style: italic;")
                    content_layout.addWidget(desc_label)
                
                # Add picture if available
                if "tooltip_picture" in new_data:
                    logging.debug("Adding tooltip picture")
                    picture_label = self.create_texture_label(new_data["tooltip_picture"], max_size=256)
                    content_layout.addWidget(picture_label)
                
                # Create the main details widget using the schema
                title = f"{file_type.replace('-', ' ').title()} Details (Base Game)" if is_base_game else f"{file_type.replace('-', ' ').title()} Details"
                logging.debug(f"Creating details group with title: {title}")
                details_group = QGroupBox(title)
                if is_base_game:
                    details_group.setStyleSheet("QGroupBox { color: #666666; font-style: italic; }")
                
                # Create the content widget using the schema, passing an empty path to start tracking
                logging.debug("Creating schema content widget")
                details_widget = self.create_widget_for_schema(new_data, self.current_schema, is_base_game, [])
                details_layout = QVBoxLayout()
                details_layout.addWidget(details_widget)
                details_group.setLayout(details_layout)
                content_layout.addWidget(details_group)
            else:
                # Partial update - find and update specific widget
                logging.debug("Performing partial update")
                
                def find_widget_by_path(widget: QWidget, target_path: List[str]) -> QWidget:
                    """Recursively find a widget by its data path"""
                    if hasattr(widget, 'property'):
                        widget_path = widget.property('data_path')
                        if widget_path == target_path:
                            return widget
                            
                    # Search children
                    if hasattr(widget, 'children'):
                        for child in widget.children():
                            result = find_widget_by_path(child, target_path)
                            if result is not None:
                                return result
                    return None
                
                # Find widget with matching data path
                target_widget = find_widget_by_path(content, data_path)
                if target_widget is not None and target_widget is not source_widget:
                    logging.debug(f"Found widget to update: {target_widget}")
                    # Update widget value based on its type
                    if isinstance(target_widget, QLineEdit):
                        target_widget.setText(str(value) if value is not None else "")
                    elif isinstance(target_widget, QSpinBox):
                        target_widget.setValue(int(value) if value is not None else 0)
                    elif isinstance(target_widget, QDoubleSpinBox):
                        target_widget.setValue(float(value) if value is not None else 0.0)
                    elif isinstance(target_widget, QCheckBox):
                        target_widget.setChecked(bool(value))
                    elif isinstance(target_widget, QComboBox):
                        target_widget.setCurrentText(str(value) if value is not None else "")
                    # Update original value property
                    target_widget.setProperty("original_value", value)
        
        # Initial content update
        update_content(file_data)
        
        # Register for data changes if file path is provided
        if file_path is not None:
            self.command_stack.register_data_change_callback(file_path, update_content)
            
            # Clean up callback when widget is destroyed
            def cleanup():
                self.command_stack.unregister_data_change_callback(file_path, update_content)
            scroll.destroyed.connect(cleanup)
        
        scroll.setWidget(content)
        logging.debug("Finished creating schema view")
        return scroll

    def get_schema_view_file_path(self, widget: QWidget) -> Path | None:
        """Get the file path from the parent schema view of a widget"""
        # Walk up the widget hierarchy until we find a QScrollArea (schema view)
        current = widget
        while current is not None:
            if isinstance(current, QScrollArea):
                file_path_str = current.property("file_path")
                if file_path_str:
                    return Path(file_path_str)
                break
            current = current.parent()
        return None

    def on_text_changed(self, widget: QLineEdit, new_text: str):
        """Handle text changes in QLineEdit widgets"""
        # Get file path from parent schema view
        file_path = self.get_schema_view_file_path(widget)
        if not file_path:
            return
            
        data_path = widget.property("data_path")
        old_value = widget.property("original_value")
        
        # Convert None to empty string for comparison
        old_value_str = str(old_value) if old_value is not None else ""
        
        if data_path is not None and old_value_str != new_text:
            command = EditValueCommand(
                file_path,
                data_path,
                old_value,
                new_text,
                lambda value: widget.setText(str(value) if value is not None else ""),
                self.update_data_value
            )
            command.source_widget = widget  # Track which widget initiated the change
            self.command_stack.push(command)
            widget.setProperty("original_value", new_text)
            self.update_save_button()  # Update save button state
            
    def on_combo_changed(self, widget: QComboBox, new_text: str):
        """Handle selection changes in QComboBox widgets"""
        # Get file path from parent schema view
        file_path = self.get_schema_view_file_path(widget)
        if not file_path:
            return
            
        data_path = widget.property("data_path")
        old_value = widget.property("original_value")
        
        if data_path is not None and old_value != new_text:
            command = EditValueCommand(
                file_path,
                data_path,
                old_value,
                new_text,
                lambda value: widget.setCurrentText(value),
                self.update_data_value
            )
            command.source_widget = widget  # Track which widget initiated the change
            self.command_stack.push(command)
            widget.setProperty("original_value", new_text)
            self.update_save_button()  # Update save button state
            
    def on_spin_changed(self, widget: QSpinBox | QDoubleSpinBox, new_value: int | float):
        """Handle value changes in QSpinBox and QDoubleSpinBox widgets"""
        # Get file path from parent schema view
        file_path = self.get_schema_view_file_path(widget)
        if not file_path:
            return
            
        data_path = widget.property("data_path")
        old_value = widget.property("original_value")
        
        if data_path is not None and old_value != new_value:
            command = EditValueCommand(
                file_path,
                data_path,
                old_value,
                new_value,
                lambda value: widget.setValue(value),
                self.update_data_value
            )
            command.source_widget = widget  # Track which widget initiated the change
            self.command_stack.push(command)
            widget.setProperty("original_value", new_value)
            self.update_save_button()  # Update save button state
            
    def on_checkbox_changed(self, widget: QCheckBox, new_state: int):
        """Handle state changes in QCheckBox widgets"""
        # Get file path from parent schema view
        file_path = self.get_schema_view_file_path(widget)
        if not file_path:
            return
            
        data_path = widget.property("data_path")
        old_value = widget.property("original_value")
        new_value = bool(new_state == Qt.CheckState.Checked.value)
        
        if data_path is not None and old_value != new_value:
            command = EditValueCommand(
                file_path,
                data_path,
                old_value,
                new_value,
                lambda value: widget.setChecked(value),
                self.update_data_value
            )
            command.source_widget = widget  # Track which widget initiated the change
            self.command_stack.push(command)
            widget.setProperty("original_value", new_value)
            self.update_save_button()  # Update save button state
    
    def save_changes(self):
        """Save all pending changes"""
        if not self.command_stack.has_unsaved_changes():
            logging.info("No unsaved changes to save")
            return
            
        # Get all modified files
        modified_files = self.command_stack.get_modified_files()
        logging.info(f"Found {len(modified_files)} modified files to save")
        logging.debug(f"Modified files list: {modified_files}")
        
        success = True
        for file_path in modified_files:
            logging.info(f"Processing file for save: {file_path}")
            
            # Get the latest data from the command stack
            data = self.command_stack.get_file_data(file_path)
            logging.debug(f"Retrieved data from command stack for {file_path}: {data}")
            
            if not data:
                logging.error(f"No data found in command stack for file: {file_path}")
                success = False
                continue
                    
            # Save the file
            logging.info(f"Attempting to save file: {file_path}")
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=4)
                logging.info(f"Successfully saved file: {file_path}")
                logging.debug(f"Saved data for {file_path}: {data}")
            except Exception as e:
                logging.error(f"Failed to save file {file_path}: {str(e)}")
                success = False
                continue
                
        # Update UI
        if success:
            self.status_label.setText("All changes saved")
            self.status_label.setProperty("status", "success")
            logging.info("All files saved successfully")
        else:
            self.status_label.setText("Error saving some changes")
            self.status_label.setProperty("status", "error")
            logging.error("Some files failed to save")
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)
        
        # Update save button state
        self.save_btn.setEnabled(self.command_stack.has_unsaved_changes())
        logging.info(f"Save button enabled: {self.command_stack.has_unsaved_changes()}")
        
    def update_save_button(self):
        """Update save button enabled state"""
        if hasattr(self, 'save_btn'):
            has_changes = self.command_stack.has_unsaved_changes()
            self.save_btn.setEnabled(has_changes)
            
        # Also update undo/redo buttons
        if hasattr(self, 'undo_btn'):
            self.undo_btn.setEnabled(self.command_stack.can_undo())
        if hasattr(self, 'redo_btn'):
            self.redo_btn.setEnabled(self.command_stack.can_redo())
            
    def undo(self):
        """Undo the last command"""
        self.command_stack.undo()
        self.update_save_button()  # Update button states
    
    def redo(self):
        """Redo the last undone command"""
        self.command_stack.redo()
        self.update_save_button()  # Update button states

    def load_all_localized_strings(self) -> None:
        """Load all localized strings from both mod and base game into memory"""
        logging.info("Loading all localized strings...")
        
        # Initialize dictionaries to store all strings
        self.all_localized_strings = {
            'mod': {},  # {language: {key: text}}
            'base_game': {}  # {language: {key: text}}
        }
        
        # Load mod strings (.str files)
        if self.current_folder:
            strings_folder = self.current_folder / "strings"
            if strings_folder.exists():
                for lang_file in strings_folder.glob("*.str"):
                    language = lang_file.stem
                    self.all_localized_strings['mod'][language] = {}
                    try:
                        with open(lang_file, 'r', encoding='utf-8') as f:
                            for line in f:
                                line = line.strip()
                                if line and not line.startswith("//"):
                                    key, value = line.split('\t', 1)
                                    self.all_localized_strings['mod'][language][key] = value
                        logging.info(f"Loaded {len(self.all_localized_strings['mod'][language])} strings for language {language} from mod")
                    except Exception as e:
                        logging.error(f"Error loading strings for language {language} from mod: {str(e)}")
        
        # Load base game strings (both .str and .json files)
        if self.base_game_folder:
            # Load .str files from strings folder
            strings_folder = self.base_game_folder / "strings"
            if strings_folder.exists():
                for lang_file in strings_folder.glob("*.str"):
                    language = lang_file.stem
                    if language not in self.all_localized_strings['base_game']:
                        self.all_localized_strings['base_game'][language] = {}
                    try:
                        with open(lang_file, 'r', encoding='utf-8') as f:
                            for line in f:
                                line = line.strip()
                                if line and not line.startswith("//"):
                                    key, value = line.split('\t', 1)
                                    self.all_localized_strings['base_game'][language][key] = value
                        logging.info(f"Loaded {len(self.all_localized_strings['base_game'][language])} strings for language {language} from base game .str file")
                    except Exception as e:
                        logging.error(f"Error loading strings for language {language} from base game .str file: {str(e)}")
            
            # Load .json files from localization folder
            localization_folder = self.base_game_folder / "localization"
            if localization_folder.exists():
                for lang_file in localization_folder.glob("*.json"):
                    language = lang_file.stem
                    if language not in self.all_localized_strings['base_game']:
                        self.all_localized_strings['base_game'][language] = {}
                    try:
                        with open(lang_file, 'r', encoding='utf-8') as f:
                            json_data = json.load(f)
                            self.all_localized_strings['base_game'][language].update(json_data)
                        logging.info(f"Loaded strings for language {language} from base game .json file")
                    except Exception as e:
                        logging.error(f"Error loading strings for language {language} from base game .json file: {str(e)}")
                        
        # Log summary
        for source in ['mod', 'base_game']:
            for language in self.all_localized_strings[source]:
                count = len(self.all_localized_strings[source][language])
                logging.info(f"Total {source} strings for {language}: {count}")
    
    def load_all_texture_files(self) -> None:
        """Load list of all texture files from both mod and base game into memory"""
        logging.info("Loading all texture files...")
        
        # Initialize lists to store texture file paths
        self.all_texture_files = {
            'mod': set(),  # Set of texture file names without extension
            'base_game': set()  # Set of texture file names without extension
        }
        
        # Load mod textures
        if self.current_folder:
            textures_folder = self.current_folder / "textures"
            if textures_folder.exists():
                for texture_file in textures_folder.glob("*.*"):
                    if texture_file.suffix.lower() in ['.png', '.dds']:
                        self.all_texture_files['mod'].add(texture_file.stem)
                logging.info(f"Found {len(self.all_texture_files['mod'])} texture files in mod")
        
        # Load base game textures
        if self.base_game_folder:
            textures_folder = self.base_game_folder / "textures"
            if textures_folder.exists():
                for texture_file in textures_folder.glob("*.*"):
                    if texture_file.suffix.lower() in ['.png', '.dds']:
                        self.all_texture_files['base_game'].add(texture_file.stem)
                logging.info(f"Found {len(self.all_texture_files['base_game'])} texture files in base game")
