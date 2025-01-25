from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, 
                            QPushButton, QLabel, QFileDialog, QHBoxLayout, 
                            QLineEdit, QListWidget, QComboBox, QTabWidget, QScrollArea, QGroupBox, QDialog, QSplitter, QToolButton,
                            QSpinBox, QDoubleSpinBox, QCheckBox, QMessageBox, QListWidgetItem)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import (QDragEnterEvent, QDropEvent, QPixmap, QIcon, QKeySequence,
                        QColor, QShortcut)
import json
import logging
from pathlib import Path
from research_view import ResearchTreeView
import os
from command_stack import CommandStack, EditValueCommand
from typing import List, Any

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
        self.base_game_folder = None
        self.current_file = None
        self.current_data = None
        self.current_schema = None
        self.current_language = "en"
        self.files_by_type = {}
        self.manifest_files = {}
        self.manifest_data = {
            'mod': {},      # {manifest_type: {id: data}}
            'base_game': {} # {manifest_type: {id: data}}
        }
        self.texture_cache = {}
        self.schemas = {}
        self.schema_extensions = set()
        self.all_localized_strings = {
            'mod': {},
            'base_game': {}
        }
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

        # Load manifest files
        self.load_base_game_manifest_files()
        
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
        
        # Player Tab
        player_widget = QScrollArea()
        player_widget.setWidgetResizable(True)
        player_content = QWidget()
        self.player_layout = QVBoxLayout(player_content)
        player_widget.setWidget(player_content)
        self.tab_widget.addTab(player_widget, "Player")
        
        # Units Tab
        units_widget = QScrollArea()
        units_widget.setWidgetResizable(True)
        units_content = QWidget()
        self.units_layout = QVBoxLayout(units_content)  # Store reference to units layout

        # Create split layout for units tab
        units_layout = QVBoxLayout(units_widget)
        units_split = QSplitter(Qt.Orientation.Horizontal)
        units_layout.addWidget(units_split)
        
        # Left side - Lists
        lists_widget = QWidget()
        lists_layout = QVBoxLayout(lists_widget)
        lists_layout.setContentsMargins(0, 0, 0, 0)
        
        # Buildable Units
        units_list_group = QGroupBox("Buildable Units")
        units_list_layout = QVBoxLayout()
        self.units_list = QListWidget()
        self.units_list.itemClicked.connect(self.on_unit_selected)
        units_list_layout.addWidget(self.units_list)
        units_list_group.setLayout(units_list_layout)
        lists_layout.addWidget(units_list_group)
        
        # Strikecraft
        strikecraft_list_group = QGroupBox("Buildable Strikecraft")
        strikecraft_list_layout = QVBoxLayout()
        self.strikecraft_list = QListWidget()
        self.strikecraft_list.itemClicked.connect(self.on_unit_selected)
        strikecraft_list_layout.addWidget(self.strikecraft_list)
        strikecraft_list_group.setLayout(strikecraft_list_layout)
        lists_layout.addWidget(strikecraft_list_group)
        
        # All Units
        all_units_group = QGroupBox("All Units")
        all_units_layout = QVBoxLayout()
        self.all_units_list = QListWidget()
        self.all_units_list.itemClicked.connect(self.on_unit_selected)
        all_units_layout.addWidget(self.all_units_list)
        all_units_group.setLayout(all_units_layout)
        lists_layout.addWidget(all_units_group)
        
        units_split.addWidget(lists_widget)
        
        # Right side - Details panels
        details_widget = QWidget()
        details_layout = QVBoxLayout(details_widget)
        details_layout.setSpacing(10)  # Add spacing between rows
        
        # Top row of details (Unit Details and Unit Skin)
        top_row = QSplitter(Qt.Orientation.Horizontal)
        
        # Unit Details panel - now full height on left
        unit_details_group = QGroupBox("Unit Details")
        self.unit_details_layout = QVBoxLayout(unit_details_group)
        top_row.addWidget(unit_details_group)
        
        # Right side vertical split for skin and weapon
        right_side = QWidget()
        right_layout = QVBoxLayout(right_side)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        # Unit Skin panel
        skin_details_group = QGroupBox("Unit Skin")
        self.skin_details_layout = QVBoxLayout(skin_details_group)
        right_layout.addWidget(skin_details_group)
        
        # Weapon panel - now below skin on right
        weapon_details_group = QGroupBox("Weapon")
        self.weapon_details_layout = QVBoxLayout(weapon_details_group)
        right_layout.addWidget(weapon_details_group)
        
        # Add right side to top row
        top_row.addWidget(right_side)
        
        # Set sizes for top row (2:1 ratio for unit details to right side)
        top_row.setSizes([200, 100])
        
        # Add top row to details layout
        details_layout.addWidget(top_row)
        
        # Add details widget to splitter
        units_split.addWidget(details_widget)
        
        # Set initial sizes for the main splitter (1:4 ratio)
        units_split.setSizes([100, 400])
        
        # Add the split layout to the units tab
        self.units_layout.addWidget(units_split)
        units_widget.setWidget(units_content)
        self.tab_widget.addTab(units_widget, "Units")

        # Unit Items Tab
        unit_items_widget = QScrollArea()
        unit_items_widget.setWidgetResizable(True)
        unit_items_content = QWidget()
        unit_items_layout = QVBoxLayout(unit_items_content)
        
        # Create split layout for unit items tab
        unit_items_split = QSplitter(Qt.Orientation.Horizontal)
        
        # Left side - Items list
        items_list_group = QGroupBox("Unit Items")
        items_list_layout = QVBoxLayout()
        self.items_list = QListWidget()
        self.items_list.itemClicked.connect(self.on_item_selected)
        items_list_layout.addWidget(self.items_list)
        items_list_group.setLayout(items_list_layout)
        unit_items_split.addWidget(items_list_group)
        
        # Right side - Item details
        item_details_group = QGroupBox("Item Details")
        self.item_details_layout = QVBoxLayout(item_details_group)
        unit_items_split.addWidget(item_details_group)
        
        # Set initial sizes (1:4 ratio)
        unit_items_split.setSizes([100, 400])
        
        unit_items_layout.addWidget(unit_items_split)
        unit_items_widget.setWidget(unit_items_content)
        self.tab_widget.addTab(unit_items_widget, "Unit Items")

        # Abilities/Buffs Tab
        abilities_widget = QScrollArea()
        abilities_widget.setWidgetResizable(True)
        abilities_content = QWidget()
        abilities_layout = QVBoxLayout(abilities_content)
        
        abilities_split = QSplitter(Qt.Orientation.Horizontal)
        
        # Left side - Selection panels
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        # Ability selection
        ability_group = QGroupBox("Abilities")
        ability_layout = QVBoxLayout()
        self.ability_list = QListWidget()
        self.ability_list.itemClicked.connect(self.on_ability_selected)
        ability_layout.addWidget(self.ability_list)
        ability_group.setLayout(ability_layout)
        left_layout.addWidget(ability_group)
        
        # Action Data Source selection
        action_group = QGroupBox("Action Data Sources")
        action_layout = QVBoxLayout()
        self.action_list = QListWidget()
        self.action_list.itemClicked.connect(self.on_action_selected)
        action_layout.addWidget(self.action_list)
        action_group.setLayout(action_layout)
        left_layout.addWidget(action_group)
        
        # Buff selection
        buff_group = QGroupBox("Buffs")
        buff_layout = QVBoxLayout()
        self.buff_list = QListWidget()
        self.buff_list.itemClicked.connect(self.on_buff_selected)
        buff_layout.addWidget(self.buff_list)
        buff_group.setLayout(buff_layout)
        left_layout.addWidget(buff_group)
        
        abilities_split.addWidget(left_panel)
        
        # Right side - Schema views
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        # Ability details
        ability_details_group = QGroupBox("Ability Details")
        self.ability_details_layout = QVBoxLayout(ability_details_group)
        right_layout.addWidget(ability_details_group)
        
        # Action Data Source details
        action_details_group = QGroupBox("Action Data Source Details")
        self.action_details_layout = QVBoxLayout(action_details_group)
        right_layout.addWidget(action_details_group)
        
        # Buff details
        buff_details_group = QGroupBox("Buff Details")
        self.buff_details_layout = QVBoxLayout(buff_details_group)
        right_layout.addWidget(buff_details_group)
        
        abilities_split.addWidget(right_panel)
        
        # Set initial sizes (1:4 ratio)
        abilities_split.setSizes([100, 400])
        
        abilities_layout.addWidget(abilities_split)
        abilities_widget.setWidget(abilities_content)
        self.tab_widget.addTab(abilities_widget, "Abilities/Buffs")

        # Research Tab (existing)
        research_widget = QScrollArea()
        research_widget.setWidgetResizable(True)
        research_content = QWidget()
        self.research_layout = QVBoxLayout(research_content)
        research_widget.setWidget(research_content)
        self.tab_widget.addTab(research_widget, "Research")

        # Formations/Flight Patterns Tab
        formations_widget = QScrollArea()
        formations_widget.setWidgetResizable(True)
        formations_content = QWidget()
        formations_layout = QVBoxLayout(formations_content)
        
        formations_split = QSplitter(Qt.Orientation.Horizontal)
        
        # Left side - Selection panels
        formations_left = QWidget()
        formations_left_layout = QVBoxLayout(formations_left)
        
        # Formations selection
        formations_group = QGroupBox("Formations")
        formations_list_layout = QVBoxLayout()
        self.formations_list = QListWidget()
        self.formations_list.itemClicked.connect(self.on_formation_selected)
        formations_list_layout.addWidget(self.formations_list)
        formations_group.setLayout(formations_list_layout)
        formations_left_layout.addWidget(formations_group)
        
        # Flight Patterns selection
        patterns_group = QGroupBox("Flight Patterns")
        patterns_list_layout = QVBoxLayout()
        self.patterns_list = QListWidget()
        self.patterns_list.itemClicked.connect(self.on_pattern_selected)
        patterns_list_layout.addWidget(self.patterns_list)
        patterns_group.setLayout(patterns_list_layout)
        formations_left_layout.addWidget(patterns_group)
        
        formations_split.addWidget(formations_left)
        
        # Right side - Schema views
        formations_right = QWidget()
        formations_right_layout = QVBoxLayout(formations_right)
        
        # Formation details
        formation_details_group = QGroupBox("Formation Details")
        self.formation_details_layout = QVBoxLayout(formation_details_group)
        formations_right_layout.addWidget(formation_details_group)
        
        # Flight Pattern details
        pattern_details_group = QGroupBox("Flight Pattern Details")
        self.pattern_details_layout = QVBoxLayout(pattern_details_group)
        formations_right_layout.addWidget(pattern_details_group)
        
        formations_split.addWidget(formations_right)
        
        # Set initial sizes (1:4 ratio)
        formations_split.setSizes([100, 400])
        
        formations_layout.addWidget(formations_split)
        formations_widget.setWidget(formations_content)
        self.tab_widget.addTab(formations_widget, "Formations/Flight Patterns")

        # NPC Rewards Tab
        rewards_widget = QScrollArea()
        rewards_widget.setWidgetResizable(True)
        rewards_content = QWidget()
        rewards_layout = QVBoxLayout(rewards_content)
        
        rewards_split = QSplitter(Qt.Orientation.Horizontal)
        
        # Left side - Rewards list
        rewards_list_group = QGroupBox("NPC Rewards")
        rewards_list_layout = QVBoxLayout()
        self.rewards_list = QListWidget()
        self.rewards_list.itemClicked.connect(self.on_reward_selected)
        rewards_list_layout.addWidget(self.rewards_list)
        rewards_list_group.setLayout(rewards_list_layout)
        rewards_split.addWidget(rewards_list_group)
        
        # Right side - Reward details
        reward_details_group = QGroupBox("Reward Details")
        self.reward_details_layout = QVBoxLayout(reward_details_group)
        rewards_split.addWidget(reward_details_group)
        
        # Set initial sizes (1:4 ratio)
        rewards_split.setSizes([100, 400])
        
        rewards_layout.addWidget(rewards_split)
        rewards_widget.setWidget(rewards_content)
        self.tab_widget.addTab(rewards_widget, "NPC Rewards")

        # Exotics Tab
        exotics_widget = QScrollArea()
        exotics_widget.setWidgetResizable(True)
        exotics_content = QWidget()
        exotics_layout = QVBoxLayout(exotics_content)
        
        exotics_split = QSplitter(Qt.Orientation.Horizontal)
        
        # Left side - Exotics list
        exotics_list_group = QGroupBox("Exotics")
        exotics_list_layout = QVBoxLayout()
        self.exotics_list = QListWidget()
        self.exotics_list.itemClicked.connect(self.on_exotic_selected)
        exotics_list_layout.addWidget(self.exotics_list)
        exotics_list_group.setLayout(exotics_list_layout)
        exotics_split.addWidget(exotics_list_group)
        
        # Right side - Exotic details
        exotic_details_group = QGroupBox("Exotic Details")
        self.exotic_details_layout = QVBoxLayout(exotic_details_group)
        exotics_split.addWidget(exotic_details_group)
        
        # Set initial sizes (1:4 ratio)
        exotics_split.setSizes([100, 400])
        
        exotics_layout.addWidget(exotics_split)
        exotics_widget.setWidget(exotics_content)
        self.tab_widget.addTab(exotics_widget, "Exotics")

        # Uniforms Tab
        uniforms_widget = QScrollArea()
        uniforms_widget.setWidgetResizable(True)
        uniforms_content = QWidget()
        uniforms_layout = QVBoxLayout(uniforms_content)
        
        uniforms_split = QSplitter(Qt.Orientation.Horizontal)
        
        # Left side - Uniforms list
        uniforms_list_group = QGroupBox("Uniforms")
        uniforms_list_layout = QVBoxLayout()
        self.uniforms_list = QListWidget()
        self.uniforms_list.itemClicked.connect(self.on_uniform_selected)
        uniforms_list_layout.addWidget(self.uniforms_list)
        uniforms_list_group.setLayout(uniforms_list_layout)
        uniforms_split.addWidget(uniforms_list_group)
        
        # Right side - Uniform details
        uniform_details_group = QGroupBox("Uniform Details")
        self.uniform_details_layout = QVBoxLayout(uniform_details_group)
        uniforms_split.addWidget(uniform_details_group)
        
        # Set initial sizes (1:4 ratio)
        uniforms_split.setSizes([100, 400])
        
        uniforms_layout.addWidget(uniforms_split)
        uniforms_widget.setWidget(uniforms_content)
        self.tab_widget.addTab(uniforms_widget, "Uniforms")

        # Mod Meta Data Tab
        meta_widget = QScrollArea()
        meta_widget.setWidgetResizable(True)
        meta_content = QWidget()
        self.meta_layout = QVBoxLayout(meta_content)
        meta_widget.setWidget(meta_content)
        self.tab_widget.addTab(meta_widget, "Mod Meta Data")
        
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
                self.load_base_game_manifest_files()  # Reload base game manifest files
        
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
        self.clear_layout(self.player_layout)
        
        # Create schema view for player data
        schema_view = self.create_schema_view("player", self.current_data, False, self.current_file)
        self.player_layout.addWidget(schema_view)
        
        # Units Tab
        # Clear the lists
        self.units_list.clear()
        self.strikecraft_list.clear()
        # Don't clear all_units_list as it's populated from folder load
            
        # Add buildable units
        if "buildable_units" in self.current_data:
            for unit_id in sorted(self.current_data["buildable_units"]):
                item = QListWidgetItem(unit_id)
                # Check if unit exists in mod folder first
                mod_file = self.current_folder / "entities" / f"{unit_id}.unit"
                # Style as base game if it doesn't exist in mod folder
                if (not mod_file.exists() and self.base_game_folder and 
                    unit_id in self.manifest_data['base_game'].get('unit', {})):
                    item.setForeground(QColor(150, 150, 150))
                    font = item.font()
                    font.setItalic(True)
                    item.setFont(font)
                self.units_list.addItem(item)
        
        # Add buildable strikecraft
        if "buildable_strikecraft" in self.current_data:
            for unit_id in sorted(self.current_data["buildable_strikecraft"]):
                item = QListWidgetItem(unit_id)
                self.strikecraft_list.addItem(item)
            
            # Clear all detail panels
            self.clear_layout(self.unit_details_layout)
            self.clear_layout(self.weapon_details_layout)
            self.clear_layout(self.skin_details_layout)
            self.clear_layout(self.ability_details_layout)
        
        # Research Tab
        if "research" in self.current_data:
            # Clear existing research view
            self.clear_layout(self.research_layout)
            # Create and add new research view
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
    
    def open_folder_dialog(self):
        """Open directory dialog to select mod folder"""
        dir_path = QFileDialog.getExistingDirectory(
            self,
            "Select Mod Folder",
            str(self.current_folder) if self.current_folder else ""
        )
        if dir_path:
            self.load_folder(Path(dir_path))
    
    def load_folder(self, folder_path: Path):
        """Load all files from the mod folder"""
        try:
            self.current_folder = folder_path.resolve()  # Get absolute path
            self.files_by_type.clear()
            self.manifest_files.clear()
            self.player_selector.clear()
            
            # Load all data into memory
            self.load_all_localized_strings()
            self.load_all_texture_files()
            self.load_mod_manifest_files()
            
            # Clear all lists
            self.items_list.clear()
            self.ability_list.clear()
            self.action_list.clear()
            self.buff_list.clear()
            self.formations_list.clear()
            self.patterns_list.clear()
            self.rewards_list.clear()
            self.exotics_list.clear()
            self.uniforms_list.clear()
            
            # Process all files recursively
            entities_folder = self.current_folder / "entities"
            base_entities_folder = None if not self.base_game_folder else self.base_game_folder / "entities"
            
            def add_items_to_list(list_widget, pattern, folder, is_base_game=False):
                """Add items to a list widget with optional base game styling"""
                if not folder or not folder.exists():
                    return
                for file in folder.glob(pattern):
                    item = QListWidgetItem(file.stem)
                    if is_base_game:
                        item.setForeground(QColor(150, 150, 150))
                        font = item.font()
                        font.setItalic(True)
                        item.setFont(font)
                    list_widget.addItem(item)

            if entities_folder.exists():
                # Load all units first
                self.all_units_list.clear()
                add_items_to_list(self.all_units_list, "*.unit", entities_folder)
                if base_entities_folder:
                    add_items_to_list(self.all_units_list, "*.unit", base_entities_folder, True)
                
                # Load unit items
                add_items_to_list(self.items_list, "*.unit_item", entities_folder)
                if base_entities_folder:
                    add_items_to_list(self.items_list, "*.unit_item", base_entities_folder, True)
                
                # Load abilities
                add_items_to_list(self.ability_list, "*.ability", entities_folder)
                if base_entities_folder:
                    add_items_to_list(self.ability_list, "*.ability", base_entities_folder, True)
                
                # Load action data sources
                add_items_to_list(self.action_list, "*.action_data_source", entities_folder)
                if base_entities_folder:
                    add_items_to_list(self.action_list, "*.action_data_source", base_entities_folder, True)
                
                # Load buffs
                add_items_to_list(self.buff_list, "*.buff", entities_folder)
                if base_entities_folder:
                    add_items_to_list(self.buff_list, "*.buff", base_entities_folder, True)
                
                # Load formations
                add_items_to_list(self.formations_list, "*.formation", entities_folder)
                if base_entities_folder:
                    add_items_to_list(self.formations_list, "*.formation", base_entities_folder, True)
                
                # Load flight patterns
                add_items_to_list(self.patterns_list, "*.flight_pattern", entities_folder)
                if base_entities_folder:
                    add_items_to_list(self.patterns_list, "*.flight_pattern", base_entities_folder, True)
                
                # Load NPC rewards
                add_items_to_list(self.rewards_list, "*.npc_reward", entities_folder)
                if base_entities_folder:
                    add_items_to_list(self.rewards_list, "*.npc_reward", base_entities_folder, True)
                
                # Load exotics
                add_items_to_list(self.exotics_list, "*.exotic", entities_folder)
                if base_entities_folder:
                    add_items_to_list(self.exotics_list, "*.exotic", base_entities_folder, True)

            # Load uniforms from uniforms folder
            uniforms_folder = self.current_folder / "uniforms"
            base_uniforms_folder = None if not self.base_game_folder else self.base_game_folder / "uniforms"
            add_items_to_list(self.uniforms_list, "*.uniforms", uniforms_folder)
            if base_uniforms_folder and base_uniforms_folder.exists():
                add_items_to_list(self.uniforms_list, "*.uniforms", base_uniforms_folder, True)
            
            # Load mod meta data if exists
            meta_file = self.current_folder / ".mod_meta_data"
            if meta_file.exists():
                try:
                    with open(meta_file, 'r', encoding='utf-8') as f:
                        meta_data = json.load(f)
                    self.clear_layout(self.meta_layout)
                    schema_view = self.create_schema_view("mod-meta-data", meta_data, False, meta_file)
                    self.meta_layout.addWidget(schema_view)
                except Exception as e:
                    logging.error(f"Error loading mod meta data: {str(e)}")
            
            # Update player selector from manifest data
            if 'player' in self.manifest_data['mod']:
                player_ids = sorted(self.manifest_data['mod']['player'].keys())
                self.player_selector.addItems(player_ids)
                logging.info(f"Added {len(player_ids)} players to selector")
            
            logging.info(f"Successfully loaded folder: {self.current_folder}")
            
        except Exception as e:
            logging.error(f"Error loading folder: {str(e)}")
            self.current_folder = None
           
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
        
    def load_player_file(self, file_path: Path):
        """Load a player file into the application"""
        try:
            with open(file_path, encoding='utf-8') as f:
                data = json.load(f)
                
            self.current_file = file_path
            self.current_data = data
            
            # If it's a player file, update the display,otherwise error
            if file_path.suffix == '.player':
                self.update_player_display()
            else:
                raise ValueError(f"File is not a player file: {file_path}")
            
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
            
        logging.debug(f"create_widget_for_value called with:")
        logging.debug(f"  value: {value}")
        logging.debug(f"  schema: {schema}")
        logging.debug(f"  path: {path}")
        
        # Handle different schema types
        schema_type = schema.get("type")
        
        if schema_type == "string":
            # Convert value to string if it's not already
            value_str = str(value) if value is not None else "ERROR: No value"

            # Get property name from the path - use the last string in the path
            property_name = next((p for p in reversed(path) if isinstance(p, str)), "").lower()
            logging.debug(f"Extracted property_name from path: {property_name}")
            
            manifest_type_map = {
                "weapon": "weapon",
                "weapons": "weapon",
                "skins": "unit_skin",
                "skin": "unit_skin",
                "abilities": "ability",
                "ability": "ability",
                "action_data_source": "action_data_source",
                "buffs": "buff",
                "buff": "buff",
                "unit_items": "unit_item",
                "unit_item": "unit_item",
                "formations": "formation",
                "formation": "formation",
                "flight_patterns": "flight_pattern",
                "flight_pattern": "flight_pattern",
                "npc_rewards": "npc_reward",
                "npc_reward": "npc_reward",
                "exotics": "exotic",
                "exotic": "exotic",
                "uniforms": "uniform",
                "uniform": "uniform",
                "research_subjects": "research_subject",
                "research_subject": "research_subject"
            }

            # Special handling for arrays and objects
            if isinstance(value, list):
                container = QWidget()
                layout = QVBoxLayout(container)
                layout.setContentsMargins(0, 0, 0, 0)
                layout.setSpacing(2)
                
                logging.debug(f"Processing array with schema: {schema}")
                
                for i, item in enumerate(value):
                    if isinstance(item, dict):
                        # For objects in arrays (like skin_groups), recursively process their values
                        for key, val in item.items():
                            if isinstance(val, list):
                                # For arrays within objects (like "skins" array), process each item
                                for sub_item in val:
                                    # Skip non-string values
                                    if not isinstance(sub_item, str):
                                        label = QLabel(str(sub_item))
                                        layout.addWidget(label)
                                        continue
                                        
                                    logging.debug(f"Creating widget for array item with key: {key}")
                                    # Create widget with property name from key
                                    widget = self.create_widget_for_value(
                                        sub_item,
                                        {"type": "string", "property_name": key},
                                        is_base_game,
                                        path + [i, key]
                                    )
                                    layout.addWidget(widget)
                            else:
                                # Handle non-list values in the dictionary
                                widget = self.create_widget_for_value(
                                    val,
                                    {"type": "string", "property_name": key},
                                    is_base_game,
                                    path + [i, key]
                                )
                                layout.addWidget(widget)
                    else:
                        # For simple values in arrays, use the parent property name
                        parent_property = schema.get("property_name", "")
                        logging.debug(f"Creating widget for simple array item with parent property: {parent_property}")
                        widget = self.create_widget_for_value(
                            item,
                            {"type": "string", "property_name": parent_property},
                            is_base_game,
                            path + [i]
                        )
                        layout.addWidget(widget)
                
                return container

            # Check if property name indicates a specific entity type
            entity_type = None
            logging.debug(f"Checking for {value_str} in manifest type {property_name}")
            if property_name in manifest_type_map:
                logging.debug(f"Found manifest type mapping: {property_name} -> {manifest_type_map[property_name]}")
                expected_type = manifest_type_map[property_name]
                logging.debug(f"Checking for {value_str} in manifest type {expected_type}")
                # Only check the expected type based on property name
                if (value_str in self.manifest_data['mod'].get(expected_type, {}) or 
                    value_str in self.manifest_data['base_game'].get(expected_type, {})):
                    entity_type = expected_type
                    logging.debug(f"Found {value_str} in manifest {expected_type}")
                else:
                    # If not found in the expected type, log a warning
                    logging.warning(f"Referenced {expected_type} not found: {value_str}")
                    # Don't search other manifests if we have a specific type
                    return QLabel(value_str)
            else:
                # Only search all manifests if no specific type is mapped
                logging.debug(f"Checking all manifests for {value_str}")
                for manifest_type, manifest_data in self.manifest_data['mod'].items():
                    if value_str in manifest_data:
                        logging.debug(f"Found {value_str} in mod manifest {manifest_type}")
                        entity_type = manifest_type
                        break
                if not entity_type:
                    for manifest_type, manifest_data in self.manifest_data['base_game'].items():
                        if value_str in manifest_data:
                            logging.debug(f"Found {value_str} in base game manifest {manifest_type}")
                            entity_type = manifest_type
                            break
            
            if entity_type:
                logging.debug(f"Creating button for {value_str} of type {entity_type}")
                btn = QPushButton(value_str)
                btn.setStyleSheet("text-align: left; padding: 2px;")
                
                # Create a closure to properly capture the values
                def create_click_handler(entity_id=str(value_str), entity_type=entity_type):
                    def handler(checked):
                        try:
                            if not isinstance(entity_id, str):
                                QMessageBox.warning(self, "Error", f"Invalid entity ID: {entity_id}")
                                return
                                
                            # Check if the file exists before trying to load it
                            mod_file = self.current_folder / "entities" / f"{entity_id}.{entity_type}"
                            base_file = None if not self.base_game_folder else self.base_game_folder / "entities" / f"{entity_id}.{entity_type}"
                            
                            if not mod_file.exists() and (not base_file or not base_file.exists()):
                                error_msg = f"Could not find {entity_type} file: {entity_id}\n\n"
                                if not self.base_game_folder:
                                    error_msg += "Note: Base game folder is not configured. Some references may not be found."
                                else:
                                    error_msg += f"Looked in:\n- {mod_file}\n- {base_file}"
                                QMessageBox.warning(self, "Error", error_msg)
                                return
                                
                            self.load_referenced_entity(entity_id, entity_type)
                        except Exception as e:
                            QMessageBox.warning(self, "Error", f"Error loading {entity_type} {entity_id}:\n{str(e)}")
                    return handler
                
                btn.clicked.connect(create_click_handler())
                
                if is_base_game:
                    btn.setStyleSheet(btn.styleSheet() + "; color: #666666; font-style: italic;")
                
                # Store path and original value
                btn.setProperty("data_path", path)
                btn.setProperty("original_value", value)
                return btn
                
            # Check if the string value is a localized text key
            is_localized_key = False
            localized_text = None
            is_base = False
            
            # Try mod strings first
            if self.current_language in self.all_localized_strings['mod'] and value_str in self.all_localized_strings['mod'][self.current_language]:
                is_localized_key = True
                localized_text = self.all_localized_strings['mod'][self.current_language][value_str]
                is_base = False
                logging.debug(f"Found localized text in mod {self.current_language}: {localized_text}")
            elif "en" in self.all_localized_strings['mod'] and value_str in self.all_localized_strings['mod']["en"]:
                is_localized_key = True
                localized_text = self.all_localized_strings['mod']["en"][value_str]
                is_base = False
                logging.debug(f"Found localized text in mod en: {localized_text}")
            # Try base game strings
            elif self.current_language in self.all_localized_strings['base_game'] and value_str in self.all_localized_strings['base_game'][self.current_language]:
                is_localized_key = True
                localized_text = self.all_localized_strings['base_game'][self.current_language][value_str]
                is_base = True
                logging.debug(f"Found localized text in base game {self.current_language}: {localized_text}")
            elif "en" in self.all_localized_strings['base_game'] and value_str in self.all_localized_strings['base_game']["en"]:
                is_localized_key = True
                localized_text = self.all_localized_strings['base_game']["en"][value_str]
                is_base = True
                logging.debug(f"Found localized text in base game en: {localized_text}")
            
            if is_localized_key:
                logging.debug(f"Creating localized text widget for key: {value_str}")
                # Create a container with both localized text and editable field
                container = QWidget()
                layout = QVBoxLayout(container)
                layout.setContentsMargins(0, 0, 0, 0)
                layout.setSpacing(4)
                
                # Add localized text preview
                preview = QLabel(f"{localized_text} [{value_str}]")  # Show both text and key
                preview.setWordWrap(True)
                if is_base:
                    preview.setStyleSheet("color: #666666; font-style: italic;")
                layout.addWidget(preview)
                
                # Add editable field if not base game
                if not is_base_game:
                    edit = QLineEdit(value_str)
                    edit.textChanged.connect(lambda text: self.on_text_changed(edit, text))
                    edit.setProperty("data_path", path)
                    edit.setProperty("original_value", value)
                    layout.addWidget(edit)
                
                container.setProperty("data_path", path)
                container.setProperty("original_value", value)
                return container
            
            # Check if the string value is a texture file name
            elif value_str in self.all_texture_files['mod'] or value_str in self.all_texture_files['base_game']:
                # Handle texture references - create a container with both texture and editable field
                container = QWidget()
                layout = QVBoxLayout(container)
                layout.setContentsMargins(0, 0, 0, 0)
                layout.setSpacing(4)
                
                # Add texture preview
                label = self.create_texture_label(value_str)
                layout.addWidget(label)
                
                # Add editable field if not base game
                if not is_base_game:
                    edit = QLineEdit(value_str)
                    edit.textChanged.connect(lambda text: self.on_text_changed(edit, text))
                    edit.setProperty("data_path", path)
                    edit.setProperty("original_value", value)
                    layout.addWidget(edit)
                
                container.setProperty("data_path", path)
                container.setProperty("original_value", value)
                return container

            # Handle enum values
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

            # Handle all other values
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
        if not isinstance(entity_id, str):
            logging.error(f"Invalid entity_id type: {type(entity_id)}. Expected string.")
            QMessageBox.warning(self, "Error", f"Invalid entity ID: {entity_id}")
            return
            
        if not self.current_folder:
            QMessageBox.warning(self, "Error", "No mod folder is currently loaded.")
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
                    with open(entity_file, 'r', encoding='utf-8') as f:
                        entity_data = json.load(f)
                        is_base_game = False
                    logging.info(f"Successfully loaded data for {entity_file}")
                    logging.debug(f"Initial data for {entity_file}: {entity_data}")
                
                # Try base game folder if not found in mod folder
                elif self.base_game_folder:
                    base_game_file = self.base_game_folder / "entities" / f"{entity_id}.{entity_type}"
                    if base_game_file.exists():
                        logging.info(f"Loading referenced entity from base game: {base_game_file}")
                        with open(base_game_file, 'r', encoding='utf-8') as f:
                            entity_data = json.load(f)
                            is_base_game = True
                        entity_file = base_game_file
                        logging.info(f"Successfully loaded base game data for {entity_file}")
                        logging.debug(f"Initial base game data for {entity_file}: {entity_data}")
                
            if not entity_data:
                error_msg = f"Could not find {entity_type} file: {entity_id}\n\n"
                if not self.base_game_folder:
                    error_msg += "Note: Base game folder is not configured. Some references may not be found."
                else:
                    error_msg += f"Looked in:\n- {entity_file}\n- {self.base_game_folder}/entities/{entity_id}.{entity_type}"
                QMessageBox.warning(self, "Error", error_msg)
                logging.error(f"{entity_type} file not found: {entity_id}")
                return
                
            # Store data in command stack if it wasn't already there
            if entity_file not in self.command_stack.file_data:
                logging.info(f"Storing initial data in command stack for {entity_file}")
                self.command_stack.update_file_data(entity_file, entity_data)
            
            # Handle different entity types and switch to appropriate tab
            if entity_type == "weapon":
                # Weapons are shown in the Units tab
                units_tab = next((i for i in range(self.tab_widget.count()) if self.tab_widget.tabText(i) == "Units"), 0)
                self.tab_widget.setCurrentIndex(units_tab)
                
                # Only clear and update the weapon panel content
                while self.weapon_details_layout.count():
                    item = self.weapon_details_layout.takeAt(0)
                    if item.widget():
                        item.widget().deleteLater()
                
                schema_view = self.create_schema_view("weapon", entity_data, is_base_game, entity_file)
                self.weapon_details_layout.addWidget(schema_view)
                self.weapon_file = entity_file  # Store file path
                logging.info(f"Created weapon schema view for {entity_file}")

            elif entity_type == "research_subject":
                # Switch to Research tab
                research_tab = next((i for i in range(self.tab_widget.count()) if self.tab_widget.tabText(i) == "Research"), 0)
                self.tab_widget.setCurrentIndex(research_tab)
                
                # Load the research subject
                self.load_research_subject(entity_id)
                
            elif entity_type == "unit_skin":
                # Unit skins are shown in the Units tab
                units_tab = next((i for i in range(self.tab_widget.count()) if self.tab_widget.tabText(i) == "Units"), 0)
                self.tab_widget.setCurrentIndex(units_tab)
                
                # Only clear and update the skin panel content
                while self.skin_details_layout.count():
                    item = self.skin_details_layout.takeAt(0)
                    if item.widget():
                        item.widget().deleteLater()
                
                schema_view = self.create_schema_view("unit-skin", entity_data, is_base_game, entity_file)
                self.skin_details_layout.addWidget(schema_view)
                self.skin_file = entity_file  # Store file path
                logging.info(f"Created unit skin schema view for {entity_file}")
                
            elif entity_type == "ability":
                # Switch to Abilities/Buffs tab
                abilities_tab = next((i for i in range(self.tab_widget.count()) if self.tab_widget.tabText(i) == "Abilities/Buffs"), 0)
                self.tab_widget.setCurrentIndex(abilities_tab)
                
                # Select the ability in the list if it exists
                for i in range(self.ability_list.count()):
                    if self.ability_list.item(i).text() == entity_id:
                        self.ability_list.setCurrentRow(i)
                        break
                
                # Only clear and update the ability panel content
                while self.ability_details_layout.count():
                    item = self.ability_details_layout.takeAt(0)
                    if item.widget():
                        item.widget().deleteLater()
                
                schema_view = self.create_schema_view("ability", entity_data, is_base_game, entity_file)
                self.ability_details_layout.addWidget(schema_view)
                self.ability_file = entity_file  # Store file path
                logging.info(f"Created ability schema view for {entity_file}")
                
            elif entity_type == "unit_item":
                # Switch to Unit Items tab
                items_tab = next((i for i in range(self.tab_widget.count()) if self.tab_widget.tabText(i) == "Unit Items"), 0)
                self.tab_widget.setCurrentIndex(items_tab)
                
                # Select the item in the list if it exists
                for i in range(self.items_list.count()):
                    if self.items_list.item(i).text() == entity_id:
                        self.items_list.setCurrentRow(i)
                        break
                
                # Only clear and update the item panel content
                while self.item_details_layout.count():
                    item = self.item_details_layout.takeAt(0)
                    if item.widget():
                        item.widget().deleteLater()
                
                schema_view = self.create_schema_view("unit-item", entity_data, is_base_game, entity_file)
                self.item_details_layout.addWidget(schema_view)
                
            elif entity_type == "buff":
                # Switch to Abilities/Buffs tab
                abilities_tab = next((i for i in range(self.tab_widget.count()) if self.tab_widget.tabText(i) == "Abilities/Buffs"), 0)
                self.tab_widget.setCurrentIndex(abilities_tab)
                
                # Select the buff in the list if it exists
                for i in range(self.buff_list.count()):
                    if self.buff_list.item(i).text() == entity_id:
                        self.buff_list.setCurrentRow(i)
                        break
                
                # Only clear and update the buff panel content
                while self.buff_details_layout.count():
                    item = self.buff_details_layout.takeAt(0)
                    if item.widget():
                        item.widget().deleteLater()
                
                schema_view = self.create_schema_view("buff", entity_data, is_base_game, entity_file)
                self.buff_details_layout.addWidget(schema_view)
                
            elif entity_type == "action_data_source":
                # Switch to Abilities/Buffs tab
                abilities_tab = next((i for i in range(self.tab_widget.count()) if self.tab_widget.tabText(i) == "Abilities/Buffs"), 0)
                self.tab_widget.setCurrentIndex(abilities_tab)
                
                # Select the action in the list if it exists
                for i in range(self.action_list.count()):
                    if self.action_list.item(i).text() == entity_id:
                        self.action_list.setCurrentRow(i)
                        break
                
                # Only clear and update the action panel content
                while self.action_details_layout.count():
                    item = self.action_details_layout.takeAt(0)
                    if item.widget():
                        item.widget().deleteLater()
                
                schema_view = self.create_schema_view("action-data-source", entity_data, is_base_game, entity_file)
                self.action_details_layout.addWidget(schema_view)
                
            elif entity_type == "formation":
                # Switch to Formations tab
                formations_tab = next((i for i in range(self.tab_widget.count()) if self.tab_widget.tabText(i) == "Formations"), 0)
                self.tab_widget.setCurrentIndex(formations_tab)
                
                # Select the formation in the list if it exists
                for i in range(self.formations_list.count()):
                    if self.formations_list.item(i).text() == entity_id:
                        self.formations_list.setCurrentRow(i)
                        break
                
                # Only clear and update the formation panel content
                while self.formation_details_layout.count():
                    item = self.formation_details_layout.takeAt(0)
                    if item.widget():
                        item.widget().deleteLater()
                
                schema_view = self.create_schema_view("formation", entity_data, is_base_game, entity_file)
                self.formation_details_layout.addWidget(schema_view)
                
            elif entity_type == "flight_pattern":
                # Switch to Flight Patterns tab
                patterns_tab = next((i for i in range(self.tab_widget.count()) if self.tab_widget.tabText(i) == "Flight Patterns"), 0)
                self.tab_widget.setCurrentIndex(patterns_tab)
                
                # Select the pattern in the list if it exists
                for i in range(self.patterns_list.count()):
                    if self.patterns_list.item(i).text() == entity_id:
                        self.patterns_list.setCurrentRow(i)
                        break
                
                # Only clear and update the pattern panel content
                while self.pattern_details_layout.count():
                    item = self.pattern_details_layout.takeAt(0)
                    if item.widget():
                        item.widget().deleteLater()
                
                schema_view = self.create_schema_view("flight-pattern", entity_data, is_base_game, entity_file)
                self.pattern_details_layout.addWidget(schema_view)
                
            elif entity_type == "npc_reward":
                # Switch to NPC Rewards tab
                rewards_tab = next((i for i in range(self.tab_widget.count()) if self.tab_widget.tabText(i) == "NPC Rewards"), 0)
                self.tab_widget.setCurrentIndex(rewards_tab)
                
                # Select the reward in the list if it exists
                for i in range(self.rewards_list.count()):
                    if self.rewards_list.item(i).text() == entity_id:
                        self.rewards_list.setCurrentRow(i)
                        break
                
                # Only clear and update the reward panel content
                while self.reward_details_layout.count():
                    item = self.reward_details_layout.takeAt(0)
                    if item.widget():
                        item.widget().deleteLater()
                
                schema_view = self.create_schema_view("npc-reward", entity_data, is_base_game, entity_file)
                self.reward_details_layout.addWidget(schema_view)
                
            elif entity_type == "exotic":
                # Switch to Exotics tab
                exotics_tab = next((i for i in range(self.tab_widget.count()) if self.tab_widget.tabText(i) == "Exotics"), 0)
                self.tab_widget.setCurrentIndex(exotics_tab)
                
                # Select the exotic in the list if it exists
                for i in range(self.exotics_list.count()):
                    if self.exotics_list.item(i).text() == entity_id:
                        self.exotics_list.setCurrentRow(i)
                        break
                
                # Only clear and update the exotic panel content
                while self.exotic_details_layout.count():
                    item = self.exotic_details_layout.takeAt(0)
                    if item.widget():
                        item.widget().deleteLater()
                
                schema_view = self.create_schema_view("exotic", entity_data, is_base_game, entity_file)
                self.exotic_details_layout.addWidget(schema_view)
                
            elif entity_type == "uniform":
                # Switch to Uniforms tab
                uniforms_tab = next((i for i in range(self.tab_widget.count()) if self.tab_widget.tabText(i) == "Uniforms"), 0)
                self.tab_widget.setCurrentIndex(uniforms_tab)
                
                # Select the uniform in the list if it exists
                for i in range(self.uniforms_list.count()):
                    if self.uniforms_list.item(i).text() == entity_id:
                        self.uniforms_list.setCurrentRow(i)
                        break
                
                # Only clear and update the uniform panel content
                while self.uniform_details_layout.count():
                    item = self.uniform_details_layout.takeAt(0)
                    if item.widget():
                        item.widget().deleteLater()
                
                schema_view = self.create_schema_view("uniform", entity_data, is_base_game, entity_file)
                self.uniform_details_layout.addWidget(schema_view)
                
            elif entity_type == "unit":
                # Switch to Units tab
                units_tab = next((i for i in range(self.tab_widget.count()) if self.tab_widget.tabText(i) == "Units"), 0)
                self.tab_widget.setCurrentIndex(units_tab)
                
                # Select the unit in the buildable list if it exists
                found = False
                for i in range(self.units_list.count()):
                    if self.units_list.item(i).text() == entity_id:
                        self.units_list.setCurrentRow(i)
                        found = True
                        break
                
                # Check strikecraft list if not found in units list
                if not found:
                    for i in range(self.strikecraft_list.count()):
                        if self.strikecraft_list.item(i).text() == entity_id:
                            self.strikecraft_list.setCurrentRow(i)
                            found = True
                            break
                        
                # Finally check all units list
                if not found:
                    for i in range(self.all_units_list.count()):
                        if self.all_units_list.item(i).text() == entity_id:
                            self.all_units_list.setCurrentRow(i)
                            found = True
                            break
                
                # Only clear and update the unit panel content
                while self.unit_details_layout.count():
                    item = self.unit_details_layout.takeAt(0)
                    if item.widget():
                        item.widget().deleteLater()
                
                schema_view = self.create_schema_view("unit", entity_data, is_base_game, entity_file)
                self.unit_details_layout.addWidget(schema_view)
                
            elif entity_type == "research_subject":
                # Switch to Research tab
                research_tab = next((i for i in range(self.tab_widget.count()) if self.tab_widget.tabText(i) == "Research"), 0)
                self.tab_widget.setCurrentIndex(research_tab)
                
                # Load the research subject
                self.load_research_subject(entity_id)
                
            else:
                QMessageBox.warning(self, "Error", f"Unknown entity type: {entity_type}")
                logging.error(f"Unknown entity type: {entity_type}")
                return
                
        except Exception as e:
            error_msg = f"Error loading {entity_type} file {entity_id}:\n{str(e)}"
            QMessageBox.warning(self, "Error", error_msg)
            logging.error(f"Error loading {entity_type} file {entity_id}: {str(e)}")
            return
    
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

    def create_generic_schema(self, data: dict) -> dict:
        """Create a generic schema that matches any JSON structure"""
        if isinstance(data, dict):
            properties = {}
            for key, value in data.items():
                properties[key] = self.create_generic_schema(value)
            return {
                "type": "object",
                "properties": properties
            }
        elif isinstance(data, list):
            # If list is empty or has mixed types, use any type
            if not data or not all(isinstance(x, type(data[0])) for x in data):
                return {
                    "type": "array",
                    "items": {"type": "string"}  # Default to string for empty/mixed arrays
                }
            # Otherwise use the type of the first item for all items
            return {
                "type": "array",
                "items": self.create_generic_schema(data[0])
            }
        elif isinstance(data, bool):
            return {"type": "boolean"}
        elif isinstance(data, int):
            return {"type": "integer"}
        elif isinstance(data, float):
            return {"type": "number"}
        else:
            return {"type": "string"}  # Default to string for all other types

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
        if file_type == "uniform":
            # Convert from snake_case to kebab-case and append -uniforms-schema
            schema_name = file_path.stem.replace("_", "-") + "-uniforms-schema"
            logging.debug(f"Looking for uniform schema: {schema_name}")
        else:
            schema_name = f"{file_type}-schema"
            
        if schema_name not in self.schemas:
            logging.info(f"Schema not found for {schema_name}, using generic schema")
            # Create a generic schema based on the data structure
            def create_schema_for_value(value):
                if isinstance(value, dict):
                    properties = {}
                    for key, val in value.items():
                        properties[key] = create_schema_for_value(val)
                    return {
                        "type": "object",
                        "properties": properties
                    }
                elif isinstance(value, list):
                    if not value:  # Empty list
                        return {
                            "type": "array",
                            "items": {"type": "string"}  # Default to string for empty arrays
                        }
                    # Use the type of the first item for all items
                    return {
                        "type": "array",
                        "items": create_schema_for_value(value[0])
                    }
                elif isinstance(value, bool):
                    return {"type": "boolean"}
                elif isinstance(value, int):
                    return {"type": "integer"}
                elif isinstance(value, float):
                    return {"type": "number"}
                else:
                    return {"type": "string"}

            # Create the root schema
            self.current_schema = create_schema_for_value(file_data)
        else:
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
            
    def load_all_localized_strings(self) -> None:
        """Load all localized strings from both mod and base game into memory"""
        logging.info("Loading all localized strings...")
        
        # Initialize dictionaries to store all strings
        self.all_localized_strings = {
            'mod': {},  # {language: {key: text}}
            'base_game': {}  # {language: {key: text}}
        }
        
        # Load mod strings
        if self.current_folder:
            # Load .localized_text files (JSON format)
            localized_text_folder = self.current_folder / "localized_text"
            logging.debug(f"Checking mod localized_text folder: {localized_text_folder}")
            if localized_text_folder.exists():
                for text_file in localized_text_folder.glob("*.localized_text"):
                    logging.debug(f"Loading mod localized text from: {text_file}")
                    try:
                        with open(text_file, 'r', encoding='utf-8') as f:
                            json_data = json.load(f)
                            # Initialize language dictionary if needed
                            language = text_file.stem
                            if language not in self.all_localized_strings['mod']:
                                self.all_localized_strings['mod'][language] = {}
                            # Add strings for this language
                            self.all_localized_strings['mod'][language].update(json_data)
                            logging.debug(f"Loaded {len(json_data)} strings for language {language} from {text_file}")
                    except Exception as e:
                        logging.error(f"Error loading localized text file {text_file}: {str(e)}")
            else:
                logging.debug("No mod localized_text folder found")
        
        # Load base game strings
        if self.base_game_folder:
            # Load .localized_text files (JSON format)
            localized_text_folder = self.base_game_folder / "localized_text"
            logging.debug(f"Checking base game localized_text folder: {localized_text_folder}")
            if localized_text_folder.exists():
                for text_file in localized_text_folder.glob("*.localized_text"):
                    logging.debug(f"Loading base game localized text from: {text_file}")
                    try:
                        with open(text_file, 'r', encoding='utf-8') as f:
                            json_data = json.load(f)
                            # Initialize language dictionary if needed
                            language = text_file.stem
                            if language not in self.all_localized_strings['base_game']:
                                self.all_localized_strings['base_game'][language] = {}
                            # Add strings for this language
                            self.all_localized_strings['base_game'][language].update(json_data)
                            logging.debug(f"Loaded {len(json_data)} strings for language {language} from {text_file}")
                    except Exception as e:
                        logging.error(f"Error loading localized text file {text_file}: {str(e)}")
            else:
                logging.debug("No base game localized_text folder found")
                        
        # Log summary
        for source in ['mod', 'base_game']:
            for language in self.all_localized_strings[source]:
                count = len(self.all_localized_strings[source][language])
                logging.info(f"Total {source} strings for {language}: {count}")
                if count > 0:
                    # Log a few example strings
                    logging.debug(f"Example strings for {source} {language}:")
                    for i, (key, value) in enumerate(list(self.all_localized_strings[source][language].items())[:3]):
                        logging.debug(f"  {key} = {value}")
                        if i >= 2:
                            break
    
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

    def load_base_game_manifest_files(self) -> None:
        """Load manifest files from base game into memory"""
        logging.info("Loading base game manifest files...")
        
        # Clear existing base game manifest data
        self.manifest_data['base_game'] = {}
        
        if self.base_game_folder:
            logging.debug(f"Using base game folder: {self.base_game_folder}")
            entities_folder = self.base_game_folder / "entities"
            if entities_folder.exists():
                logging.debug(f"Found base game entities folder: {entities_folder}")
                for manifest_file in entities_folder.glob("*.entity_manifest"):
                    try:
                        manifest_type = manifest_file.stem  # e.g., 'player', 'weapon'
                        logging.debug(f"Loading base game manifest: {manifest_file}")
                        with open(manifest_file, 'r', encoding='utf-8') as f:
                            manifest_data = json.load(f)
                            
                        if manifest_type not in self.manifest_data['base_game']:
                            self.manifest_data['base_game'][manifest_type] = {}
                            
                        # Load each referenced entity file
                        if 'ids' in manifest_data:
                            for entity_id in manifest_data['ids']:
                                entity_file = entities_folder / f"{entity_id}.{manifest_type}"
                                if entity_file.exists():
                                    with open(entity_file, 'r', encoding='utf-8') as f:
                                        entity_data = json.load(f)
                                        self.manifest_data['base_game'][manifest_type][entity_id] = entity_data
                                        logging.debug(f"Loaded base game {manifest_type} data for {entity_id}")
                                else:
                                    logging.warning(f"Referenced base game entity file not found: {entity_file}")
                                        
                        logging.info(f"Loaded base game manifest {manifest_type} with {len(manifest_data.get('ids', []))} entries")
                    except Exception as e:
                        logging.error(f"Error loading base game manifest file {manifest_file}: {str(e)}")
            else:
                logging.warning(f"Base game entities folder not found: {entities_folder}")
        else:
            logging.warning("No base game folder configured")
                        
        # Log summary
        for manifest_type in self.manifest_data['base_game']:
            count = len(self.manifest_data['base_game'][manifest_type])
            logging.info(f"Total base game {manifest_type} entries: {count}")
            if count > 0:
                logging.debug(f"Example {manifest_type} entries: {list(self.manifest_data['base_game'][manifest_type].keys())[:3]}")

    def load_mod_manifest_files(self) -> None:
        """Load manifest files from mod folder into memory"""
        logging.info("Loading mod manifest files...")
        
        # Clear existing mod manifest data
        self.manifest_data['mod'] = {}
        
        if self.current_folder:
            logging.debug(f"Using mod folder: {self.current_folder}")
            entities_folder = self.current_folder / "entities"
            if entities_folder.exists():
                logging.debug(f"Found mod entities folder: {entities_folder}")
                for manifest_file in entities_folder.glob("*.entity_manifest"):
                    try:
                        manifest_type = manifest_file.stem  # e.g., 'player', 'weapon'
                        logging.debug(f"Loading mod manifest: {manifest_file}")
                        with open(manifest_file, 'r', encoding='utf-8') as f:
                            manifest_data = json.load(f)
                            
                        if manifest_type not in self.manifest_data['mod']:
                            self.manifest_data['mod'][manifest_type] = {}
                            
                        # Load each referenced entity file
                        if 'ids' in manifest_data:
                            for entity_id in manifest_data['ids']:
                                entity_file = entities_folder / f"{entity_id}.{manifest_type}"
                                if entity_file.exists():
                                    with open(entity_file, 'r', encoding='utf-8') as f:
                                        entity_data = json.load(f)
                                        self.manifest_data['mod'][manifest_type][entity_id] = entity_data
                                        logging.debug(f"Loaded mod {manifest_type} data for {entity_id}")
                                else:
                                    logging.warning(f"Referenced mod entity file not found: {entity_file}")
                                        
                        logging.info(f"Loaded mod manifest {manifest_type} with {len(manifest_data.get('ids', []))} entries")
                    except Exception as e:
                        logging.error(f"Error loading mod manifest file {manifest_file}: {str(e)}")
            else:
                logging.warning(f"Mod entities folder not found: {entities_folder}")
        else:
            logging.warning("No mod folder loaded")
                        
        # Log summary
        for manifest_type in self.manifest_data['mod']:
            count = len(self.manifest_data['mod'][manifest_type])
            logging.info(f"Total mod {manifest_type} entries: {count}")
            if count > 0:
                logging.debug(f"Example {manifest_type} entries: {list(self.manifest_data['mod'][manifest_type].keys())[:3]}")

    def on_item_selected(self, item):
        """Handle unit item selection from the list"""
        if not self.current_folder:
            return
            
        item_id = item.text()
        is_base_game = item.foreground().color().getRgb()[:3] == (150, 150, 150)  # Check if it's a base game item
        item_file = (self.base_game_folder if is_base_game else self.current_folder) / "entities" / f"{item_id}.unit_item"
        
        try:
            # Load from file
            item_data, _ = self.load_file(item_file, try_base_game=False)  # Don't try base game again
            if not item_data:
                logging.error(f"Item file not found: {item_file}")
                return
                
            # Clear existing details
            self.clear_layout(self.item_details_layout)
            
            # Create and add the schema view for item details
            schema_view = self.create_schema_view("unit-item", item_data, is_base_game, item_file)
            self.item_details_layout.addWidget(schema_view)
            
        except Exception as e:
            logging.error(f"Error loading item {item_id}: {str(e)}")
            error_label = QLabel(f"Error loading item: {str(e)}")
            error_label.setStyleSheet("color: red;")
            self.item_details_layout.addWidget(error_label)

    def on_ability_selected(self, item):
        """Handle ability selection from the list"""
        if not self.current_folder:
            return
            
        ability_id = item.text()
        is_base_game = item.foreground().color().getRgb()[:3] == (150, 150, 150)  # Check if it's a base game item
        ability_file = (self.base_game_folder if is_base_game else self.current_folder) / "entities" / f"{ability_id}.ability"
        
        try:
            # Load from file
            ability_data, _ = self.load_file(ability_file, try_base_game=False)  # Don't try base game again
            if not ability_data:
                logging.error(f"Ability file not found: {ability_file}")
                return
                
            # Clear existing details
            self.clear_layout(self.ability_details_layout)
            
            # Create and add the schema view for ability details
            schema_view = self.create_schema_view("ability", ability_data, is_base_game, ability_file)
            self.ability_details_layout.addWidget(schema_view)
            
        except Exception as e:
            logging.error(f"Error loading ability {ability_id}: {str(e)}")
            error_label = QLabel(f"Error loading ability: {str(e)}")
            error_label.setStyleSheet("color: red;")
            self.ability_details_layout.addWidget(error_label)

    def on_action_selected(self, item):
        """Handle action data source selection from the list"""
        if not self.current_folder:
            return
            
        action_id = item.text()
        is_base_game = item.foreground().color().getRgb()[:3] == (150, 150, 150)  # Check if it's a base game item
        action_file = (self.base_game_folder if is_base_game else self.current_folder) / "entities" / f"{action_id}.action_data_source"
        
        try:
            # Load from file
            action_data, _ = self.load_file(action_file, try_base_game=False)  # Don't try base game again
            if not action_data:
                logging.error(f"Action data source file not found: {action_file}")
                return
                
            # Clear existing details
            self.clear_layout(self.action_details_layout)
            
            # Create and add the schema view for action details
            schema_view = self.create_schema_view("action-data-source", action_data, is_base_game, action_file)
            self.action_details_layout.addWidget(schema_view)
            
        except Exception as e:
            logging.error(f"Error loading action data source {action_id}: {str(e)}")
            error_label = QLabel(f"Error loading action data source: {str(e)}")
            error_label.setStyleSheet("color: red;")
            self.action_details_layout.addWidget(error_label)

    def on_buff_selected(self, item):
        """Handle buff selection from the list"""
        if not self.current_folder:
            return
            
        buff_id = item.text()
        is_base_game = item.foreground().color().getRgb()[:3] == (150, 150, 150)  # Check if it's a base game item
        buff_file = (self.base_game_folder if is_base_game else self.current_folder) / "entities" / f"{buff_id}.buff"
        
        try:
            # Load from file
            buff_data, _ = self.load_file(buff_file, try_base_game=False)  # Don't try base game again
            if not buff_data:
                logging.error(f"Buff file not found: {buff_file}")
                return
                
            # Clear existing details
            self.clear_layout(self.buff_details_layout)
            
            # Create and add the schema view for buff details
            schema_view = self.create_schema_view("buff", buff_data, is_base_game, buff_file)
            self.buff_details_layout.addWidget(schema_view)
            
        except Exception as e:
            logging.error(f"Error loading buff {buff_id}: {str(e)}")
            error_label = QLabel(f"Error loading buff: {str(e)}")
            error_label.setStyleSheet("color: red;")
            self.buff_details_layout.addWidget(error_label)

    def on_formation_selected(self, item):
        """Handle formation selection from the list"""
        if not self.current_folder:
            return
            
        formation_id = item.text()
        is_base_game = item.foreground().color().getRgb()[:3] == (150, 150, 150)  # Check if it's a base game item
        formation_file = (self.base_game_folder if is_base_game else self.current_folder) / "entities" / f"{formation_id}.formation"
        
        try:
            # Load from file
            formation_data, _ = self.load_file(formation_file, try_base_game=False)  # Don't try base game again
            if not formation_data:
                logging.error(f"Formation file not found: {formation_file}")
                return
                
            # Clear existing details
            self.clear_layout(self.formation_details_layout)
            
            # Create and add the schema view for formation details
            schema_view = self.create_schema_view("formation", formation_data, is_base_game, formation_file)
            self.formation_details_layout.addWidget(schema_view)
            
        except Exception as e:
            logging.error(f"Error loading formation {formation_id}: {str(e)}")
            error_label = QLabel(f"Error loading formation: {str(e)}")
            error_label.setStyleSheet("color: red;")
            self.formation_details_layout.addWidget(error_label)

    def on_pattern_selected(self, item):
        """Handle flight pattern selection from the list"""
        if not self.current_folder:
            return
            
        pattern_id = item.text()
        is_base_game = item.foreground().color().getRgb()[:3] == (150, 150, 150)  # Check if it's a base game item
        pattern_file = (self.base_game_folder if is_base_game else self.current_folder) / "entities" / f"{pattern_id}.flight_pattern"
        
        try:
            # Load from file
            pattern_data, _ = self.load_file(pattern_file, try_base_game=False)  # Don't try base game again
            if not pattern_data:
                logging.error(f"Flight pattern file not found: {pattern_file}")
                return
                
            # Clear existing details
            self.clear_layout(self.pattern_details_layout)
            
            # Create and add the schema view for pattern details
            schema_view = self.create_schema_view("flight-pattern", pattern_data, is_base_game, pattern_file)
            self.pattern_details_layout.addWidget(schema_view)
            
        except Exception as e:
            logging.error(f"Error loading flight pattern {pattern_id}: {str(e)}")
            error_label = QLabel(f"Error loading flight pattern: {str(e)}")
            error_label.setStyleSheet("color: red;")
            self.pattern_details_layout.addWidget(error_label)

    def on_reward_selected(self, item):
        """Handle NPC reward selection from the list"""
        if not self.current_folder:
            return
            
        reward_id = item.text()
        is_base_game = item.foreground().color().getRgb()[:3] == (150, 150, 150)  # Check if it's a base game item
        reward_file = (self.base_game_folder if is_base_game else self.current_folder) / "entities" / f"{reward_id}.npc_reward"
        
        try:
            # Load from file
            reward_data, _ = self.load_file(reward_file, try_base_game=False)  # Don't try base game again
            if not reward_data:
                logging.error(f"NPC reward file not found: {reward_file}")
                return
                
            # Clear existing details
            self.clear_layout(self.reward_details_layout)
            
            # Create and add the schema view for reward details
            schema_view = self.create_schema_view("npc-reward", reward_data, is_base_game, reward_file)
            self.reward_details_layout.addWidget(schema_view)
            
        except Exception as e:
            logging.error(f"Error loading NPC reward {reward_id}: {str(e)}")
            error_label = QLabel(f"Error loading NPC reward: {str(e)}")
            error_label.setStyleSheet("color: red;")
            self.reward_details_layout.addWidget(error_label)

    def on_exotic_selected(self, item):
        """Handle exotic selection from the list"""
        if not self.current_folder:
            return
            
        exotic_id = item.text()
        is_base_game = item.foreground().color().getRgb()[:3] == (150, 150, 150)  # Check if it's a base game item
        exotic_file = (self.base_game_folder if is_base_game else self.current_folder) / "entities" / f"{exotic_id}.exotic"
        
        try:
            # Load from file
            exotic_data, _ = self.load_file(exotic_file, try_base_game=False)  # Don't try base game again
            if not exotic_data:
                logging.error(f"Exotic file not found: {exotic_file}")
                return
                
            # Clear existing details
            self.clear_layout(self.exotic_details_layout)
            
            # Create and add the schema view for exotic details
            schema_view = self.create_schema_view("exotic", exotic_data, is_base_game, exotic_file)
            self.exotic_details_layout.addWidget(schema_view)
            
        except Exception as e:
            logging.error(f"Error loading exotic {exotic_id}: {str(e)}")
            error_label = QLabel(f"Error loading exotic: {str(e)}")
            error_label.setStyleSheet("color: red;")
            self.exotic_details_layout.addWidget(error_label)

    def on_uniform_selected(self, item):
        """Handle uniform selection from the list"""
        if not self.current_folder:
            return
            
        uniform_id = item.text()
        is_base_game = item.foreground().color().getRgb()[:3] == (150, 150, 150)  # Check if it's a base game item
        uniform_file = (self.base_game_folder if is_base_game else self.current_folder) / "uniforms" / f"{uniform_id}.uniforms"
        
        try:
            # Load from file
            uniform_data, _ = self.load_file(uniform_file, try_base_game=False)  # Don't try base game again
            if not uniform_data:
                logging.error(f"Uniform file not found: {uniform_file}")
                return
                
            # Clear existing details
            self.clear_layout(self.uniform_details_layout)
            
            # Create and add the schema view for uniform details
            schema_view = self.create_schema_view("uniform", uniform_data, is_base_game, uniform_file)
            self.uniform_details_layout.addWidget(schema_view)
            
        except Exception as e:
            logging.error(f"Error loading uniform {uniform_id}: {str(e)}")
            error_label = QLabel(f"Error loading uniform: {str(e)}")
            error_label.setStyleSheet("color: red;")
            self.uniform_details_layout.addWidget(error_label)
