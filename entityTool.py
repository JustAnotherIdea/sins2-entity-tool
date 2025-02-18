from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, 
                            QPushButton, QLabel, QFileDialog, QHBoxLayout, 
                            QLineEdit, QListWidget, QComboBox, QTabWidget, QScrollArea, QGroupBox, QDialog, QSplitter, QToolButton,
                            QSpinBox, QDoubleSpinBox, QCheckBox, QMessageBox, QListWidgetItem, QMenu, QTreeWidget, QTreeWidgetItem, QPlainTextEdit, QProgressBar, QApplication, QFormLayout, QInputDialog)
from PyQt6.QtCore import (Qt, QTimer, QObject, QEvent, QPoint)
from PyQt6.QtGui import (QDragEnterEvent, QDropEvent, QPixmap, QIcon, QKeySequence,
                        QColor, QShortcut, QFont)
import json
import logging
from pathlib import Path
from research_view import ResearchTreeView
import os
from command_stack import CommandStack, EditValueCommand, AddPropertyCommand, DeleteArrayItemCommand, DeletePropertyCommand, CompositeCommand, TransformWidgetCommand, AddArrayItemCommand, CreateFileFromCopy, CreateLocalizedText, CreateResearchSubjectCommand, DeleteResearchSubjectCommand, DeleteFileCommand
from typing import List, Any
import threading
import pygame.mixer


# add debug logging
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

class LoadingDialog(QDialog):
    """Loading screen dialog shown during program initialization"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Loading Entity Tool")
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setFixedSize(300, 100)
        
        # Center on screen
        screen = QApplication.primaryScreen().geometry()
        self.move(screen.center() - self.rect().center())
        
        # Create layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Add loading text
        self.status_label = QLabel("Initializing...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)
        
        # Add progress bar
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setRange(0, 0)  # Indeterminate progress
        layout.addWidget(self.progress)
        
    def set_status(self, text: str):
        """Update the status text"""
        self.status_label.setText(text)
        QApplication.processEvents()  # Force UI update

class EntityToolGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Create event filter for spinboxes and comboboxes
        class WheelEventFilter(QObject):
            def eventFilter(self, obj, event):
                if event.type() == QEvent.Type.Wheel:
                        return True  # Block wheel events when widget doesn't have focus
                return False  # Let other events pass through
                
        self.wheel_filter = WheelEventFilter()
        
        # Show loading screen
        self.loading = LoadingDialog(self)
        self.loading.show()
        QApplication.processEvents()  # Ensure loading screen is displayed
        
        try:
            # Initialize variables
            self.loading.set_status("Initializing variables...")
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
            self.all_texture_files = {'mod': set(), 'base_game': set()}
            self.all_localized_strings = {
                'mod': {},
                'base_game': {}
            }
            self.text_edit_timer = QTimer()
            self.text_edit_timer.setInterval(300)
            self.text_edit_timer.setSingleShot(True)
            self.text_edit_timer.timeout.connect(self.on_text_edit_timer_timeout)
            self.current_text_edit = None
            
            # Initialize UI components
            self.loading.set_status("Initializing UI...")
            self.init_ui()
            
            # Setup logging first
            self.loading.set_status("Setting up logging...")
            self.setup_logging()
            
            # Setup timers
            self.text_edit_timer = QTimer()
            self.text_edit_timer.setInterval(300)
            self.text_edit_timer.setSingleShot(True)
            self.text_edit_timer.timeout.connect(self.on_text_edit_timer_timeout)
            self.current_text_edit = None
            
            # Initialize command stack
            self.loading.set_status("Initializing command system...")
            self.command_stack = CommandStack()
            
            # Load or create config
            self.loading.set_status("Loading configuration...")
            try:
                with open('config.json', 'r') as f:
                    self.config = json.load(f)
                    if "base_game_folder" in self.config:
                        self.base_game_folder = Path(self.config["base_game_folder"])
                        print(f"Loaded base game folder from config: {self.base_game_folder}")
            except FileNotFoundError:
                logging.info("No config.json found, creating default")
                self.create_default_config()
            except json.JSONDecodeError:
                logging.error("Error parsing config.json, creating default")
                self.create_default_config()
            
            # Load schemas
            self.loading.set_status("Loading schemas...")
            self.load_schemas()
            
            # Load base game manifest files
            self.loading.set_status("Loading base game manifests...")
            self.load_base_game_manifest_files()
            
            # Apply stylesheet
            self.loading.set_status("Applying visual styles...")
            self.load_stylesheet()
            
            # Setup shortcuts
            self.loading.set_status("Setting up shortcuts...")
            self.setup_shortcuts()
            
            # Show window
            self.showMaximized()
            
            # Close loading screen
            self.loading.close()
            self.loading = None
            
        except Exception as e:
            # Show error and close loading screen
            QMessageBox.critical(self, "Initialization Error", f"Failed to initialize: {str(e)}")
            if self.loading:
                self.loading.close()
                self.loading = None
            raise  # Re-raise the exception for proper error handling
        
    def setup_logging(self):
        """Setup logging configuration"""
        # Create log list widget if not already created in init_ui
        if not hasattr(self, 'log_widget'):
            self.log_widget = QListWidget()
            self.log_widget.setMaximumHeight(100)
            
        # Create and configure the log handler
        handler = GUILogHandler(self.log_widget)
        handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        
        # Get the root logger and add our handler
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        
        # Remove any existing handlers to avoid duplicates
        for existing_handler in root_logger.handlers[:]:
            root_logger.removeHandler(existing_handler)
            
        root_logger.addHandler(handler)
        logging.info("Logging system initialized")

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

        # Add/Delete Player button
        add_player_btn = QPushButton()
        add_player_btn.setIcon(QIcon(str(Path(__file__).parent / "icons" / "add_delete.png")))
        add_player_btn.setToolTip('Add/Delete Player')
        add_player_btn.setFixedSize(20, 20)
        add_player_btn.clicked.connect(self.show_add_player_dialog)
        toolbar_layout.addWidget(add_player_btn)
        
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
        self.setup_list_context_menu(self.units_list, "unit")
        units_list_layout.addWidget(self.units_list)
        units_list_group.setLayout(units_list_layout)
        lists_layout.addWidget(units_list_group)
        
        # Strikecraft
        strikecraft_list_group = QGroupBox("Buildable Strikecraft")
        strikecraft_list_layout = QVBoxLayout()
        self.strikecraft_list = QListWidget()
        self.strikecraft_list.itemClicked.connect(self.on_unit_selected)
        self.setup_list_context_menu(self.strikecraft_list, "unit")
        strikecraft_list_layout.addWidget(self.strikecraft_list)
        strikecraft_list_group.setLayout(strikecraft_list_layout)
        lists_layout.addWidget(strikecraft_list_group)
        
        # All Units
        all_units_group = QGroupBox("All Units")
        all_units_layout = QVBoxLayout()
        self.all_units_list = QListWidget()
        self.all_units_list.itemClicked.connect(self.on_unit_selected)
        self.setup_list_context_menu(self.all_units_list, "unit")
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
        right_layout.setSpacing(10)  # Add some spacing between panels
        
        # Unit Skin panel
        skin_details_group = QGroupBox("Unit Skin")
        skin_details_group.setMinimumHeight(400)  # Increased height
        self.skin_details_layout = QVBoxLayout(skin_details_group)
        right_layout.addWidget(skin_details_group, 1)  # 1:1 ratio with weapon
        
        # Weapon panel
        weapon_details_group = QGroupBox("Weapon")
        weapon_details_group.setMinimumHeight(400)  # Increased height
        self.weapon_details_layout = QVBoxLayout(weapon_details_group)
        right_layout.addWidget(weapon_details_group, 1)  # 1:1 ratio with skin
        
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
        self.setup_list_context_menu(self.items_list, "unit_item")
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
        self.setup_list_context_menu(self.ability_list, "ability")
        ability_layout.addWidget(self.ability_list)
        ability_group.setLayout(ability_layout)
        left_layout.addWidget(ability_group)
        
        # Action Data Source selection
        action_group = QGroupBox("Action Data Sources")
        action_layout = QVBoxLayout()
        self.action_list = QListWidget()
        self.action_list.itemClicked.connect(self.on_action_selected)
        self.setup_list_context_menu(self.action_list, "action_data_source")
        action_layout.addWidget(self.action_list)
        action_group.setLayout(action_layout)
        left_layout.addWidget(action_group)
        
        # Buff selection
        buff_group = QGroupBox("Buffs")
        buff_layout = QVBoxLayout()
        self.buff_list = QListWidget()
        self.buff_list.itemClicked.connect(self.on_buff_selected)
        self.setup_list_context_menu(self.buff_list, "buff")
        buff_layout.addWidget(self.buff_list)
        buff_group.setLayout(buff_layout)
        left_layout.addWidget(buff_group)
        
        abilities_split.addWidget(left_panel)
        
        # Right side - Schema views
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)  # Add some spacing between panels
        
        # Ability details
        ability_details_group = QGroupBox("Ability Details")
        ability_details_group.setMinimumHeight(250)  # Adjusted for 1/3 height
        self.ability_details_layout = QVBoxLayout(ability_details_group)
        right_layout.addWidget(ability_details_group, 1)  # Equal ratio
        
        # Action Data Source details
        action_details_group = QGroupBox("Action Data Source Details")
        action_details_group.setMinimumHeight(250)  # Adjusted for 1/3 height
        self.action_details_layout = QVBoxLayout(action_details_group)
        right_layout.addWidget(action_details_group, 1)  # Equal ratio
        
        # Buff details
        buff_details_group = QGroupBox("Buff Details")
        buff_details_group.setMinimumHeight(250)  # Adjusted for 1/3 height
        self.buff_details_layout = QVBoxLayout(buff_details_group)
        right_layout.addWidget(buff_details_group, 1)  # Equal ratio
        
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
        self.setup_list_context_menu(self.formations_list, "formation")
        formations_list_layout.addWidget(self.formations_list)
        formations_group.setLayout(formations_list_layout)
        formations_left_layout.addWidget(formations_group)
        
        # Flight Patterns selection
        patterns_group = QGroupBox("Flight Patterns")
        patterns_list_layout = QVBoxLayout()
        self.patterns_list = QListWidget()
        self.patterns_list.itemClicked.connect(self.on_pattern_selected)
        self.setup_list_context_menu(self.patterns_list, "flight_pattern")
        patterns_list_layout.addWidget(self.patterns_list)
        patterns_group.setLayout(patterns_list_layout)
        formations_left_layout.addWidget(patterns_group)
        
        formations_split.addWidget(formations_left)
        
        # Right side - Schema views
        formations_right = QWidget()
        formations_right_layout = QVBoxLayout(formations_right)
        formations_right_layout.setContentsMargins(0, 0, 0, 0)
        formations_right_layout.setSpacing(10)  # Add spacing between panels
        
        # Formation details
        formation_details_group = QGroupBox("Formation Details")
        formation_details_group.setMinimumHeight(400)  # Set minimum height
        self.formation_details_layout = QVBoxLayout(formation_details_group)
        formations_right_layout.addWidget(formation_details_group, 1)  # Equal ratio
        
        # Flight Pattern details
        pattern_details_group = QGroupBox("Flight Pattern Details")
        pattern_details_group.setMinimumHeight(400)  # Set minimum height
        self.pattern_details_layout = QVBoxLayout(pattern_details_group)
        formations_right_layout.addWidget(pattern_details_group, 1)  # Equal ratio
        
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
        self.setup_list_context_menu(self.rewards_list, "npc_reward")
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
        self.setup_list_context_menu(self.exotics_list, "exotic")
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
        self.setup_list_context_menu(self.uniforms_list, "uniform")
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
            
    def setup_shortcuts(self):
        """Setup keyboard shortcuts"""
        # Save shortcut (Ctrl+S)
        save_shortcut = QShortcut(QKeySequence.StandardKey.Save, self)
        save_shortcut.activated.connect(self.save_changes)
        
        # Undo shortcut (Ctrl+Z)
        undo_shortcut = QShortcut(QKeySequence.StandardKey.Undo, self)
        undo_shortcut.activated.connect(self.undo)
        
        # Redo shortcut (Ctrl+Y or Ctrl+Shift+Z)
        redo_shortcut = QShortcut(QKeySequence.StandardKey.Redo, self)
        redo_shortcut.activated.connect(self.redo)
    
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
            print(f"Error loading stylesheet: {str(e)}")
    
    def load_schemas(self):
        """Load schema files from the schema folder"""
        schema_folder = self.config.get("schema_folder")
        if not schema_folder:
            logging.warning("No schema folder configured")
            return
            
        schema_path = Path(schema_folder)
        if not schema_path.exists():
            print(f"Schema folder does not exist: {schema_path}")
            return
            
        try:
            # Clear existing extensions and schemas
            self.schema_extensions = set()
            self.schemas = {}
            
            # Process each schema file
            schema_files = list(schema_path.glob("*-schema.json"))  # Changed pattern to match actual filenames
            print(f"Found {len(schema_files)} schema files")
            
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
                        
                    print(f"Loaded schema: {schema_name}")
                except Exception as e:
                    print(f"Error loading schema {file_path}: {str(e)}")
            
            print(f"Successfully loaded {len(self.schemas)} schemas")
            
        except Exception as e:
            print(f"Error loading schemas: {str(e)}")
    
    def load_folder(self, folder_path: Path):
        """Load all files from the mod folder"""
        # Show loading screen
        loading = LoadingDialog(self)
        loading.setWindowTitle("Loading Mod Folder")
        loading.show()
        QApplication.processEvents()
        
        try:
            loading.set_status("Initializing...")
            self.current_folder = folder_path.resolve()  # Get absolute path
            self.files_by_type.clear()
            self.manifest_files.clear()
            self.player_selector.clear()
            
            # Load all data into memory
            loading.set_status("Loading localized strings...")
            self.load_all_localized_strings()
            
            loading.set_status("Loading texture files...")
            self.load_all_texture_files()
            
            loading.set_status("Loading manifest files...")
            self.load_mod_manifest_files()
            
            # Clear all lists
            loading.set_status("Preparing interface...")
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
            loading.set_status("Loading entities...")
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
                loading.set_status("Loading units...")
                # Load all units first
                self.all_units_list.clear()
                add_items_to_list(self.all_units_list, "*.unit", entities_folder)
                if base_entities_folder:
                    add_items_to_list(self.all_units_list, "*.unit", base_entities_folder, True)
                
                loading.set_status("Loading unit items...")
                # Load unit items
                add_items_to_list(self.items_list, "*.unit_item", entities_folder)
                if base_entities_folder:
                    add_items_to_list(self.items_list, "*.unit_item", base_entities_folder, True)
                
                loading.set_status("Loading abilities...")
                # Load abilities
                add_items_to_list(self.ability_list, "*.ability", entities_folder)
                if base_entities_folder:
                    add_items_to_list(self.ability_list, "*.ability", base_entities_folder, True)
                
                loading.set_status("Loading actions...")
                # Load action data sources
                add_items_to_list(self.action_list, "*.action_data_source", entities_folder)
                if base_entities_folder:
                    add_items_to_list(self.action_list, "*.action_data_source", base_entities_folder, True)
                
                loading.set_status("Loading buffs...")
                # Load buffs
                add_items_to_list(self.buff_list, "*.buff", entities_folder)
                if base_entities_folder:
                    add_items_to_list(self.buff_list, "*.buff", base_entities_folder, True)
                
                loading.set_status("Loading formations...")
                # Load formations
                add_items_to_list(self.formations_list, "*.formation", entities_folder)
                if base_entities_folder:
                    add_items_to_list(self.formations_list, "*.formation", base_entities_folder, True)
                
                loading.set_status("Loading flight patterns...")
                # Load flight patterns
                add_items_to_list(self.patterns_list, "*.flight_pattern", entities_folder)
                if base_entities_folder:
                    add_items_to_list(self.patterns_list, "*.flight_pattern", base_entities_folder, True)
                
                loading.set_status("Loading NPC rewards...")
                # Load NPC rewards
                add_items_to_list(self.rewards_list, "*.npc_reward", entities_folder)
                if base_entities_folder:
                    add_items_to_list(self.rewards_list, "*.npc_reward", base_entities_folder, True)
                
                loading.set_status("Loading exotics...")
                # Load exotics
                add_items_to_list(self.exotics_list, "*.exotic", entities_folder)
                if base_entities_folder:
                    add_items_to_list(self.exotics_list, "*.exotic", base_entities_folder, True)

            loading.set_status("Loading uniforms...")
            # Load uniforms from uniforms folder
            uniforms_folder = self.current_folder / "uniforms"
            base_uniforms_folder = None if not self.base_game_folder else self.base_game_folder / "uniforms"
            add_items_to_list(self.uniforms_list, "*.uniforms", uniforms_folder)
            if base_uniforms_folder and base_uniforms_folder.exists():
                add_items_to_list(self.uniforms_list, "*.uniforms", base_uniforms_folder, True)
            
            loading.set_status("Loading mod metadata...")
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
                    print(f"Error loading mod meta data: {str(e)}")
            
            loading.set_status("Updating player selector...")
            # Update player selector from manifest data
            if 'player' in self.manifest_data['mod']:
                player_ids = sorted(self.manifest_data['mod']['player'].keys())
                self.player_selector.addItems(player_ids)
                print(f"Added {len(player_ids)} players to selector")
            
            loading.close()
            print(f"Successfully loaded folder: {self.current_folder}")
            
        except Exception as e:
            print(f"Error loading folder: {str(e)}")
            self.current_folder = None
            loading.close()
            QMessageBox.critical(self, "Error", f"Failed to load folder: {str(e)}")
    
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
            print(f"Error loading file {file_path}: {str(e)}")
            return None, False
         
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
 
    def load_base_game_manifest_files(self) -> None:
        """Load manifest files from base game into memory"""
        logging.info("Loading base game manifest files...")
        
        # Clear existing base game manifest data
        self.manifest_data['base_game'] = {}
        
        if self.base_game_folder:
            print(f"Using base game folder: {self.base_game_folder}")
            entities_folder = self.base_game_folder / "entities"
            if entities_folder.exists():
                print(f"Found base game entities folder: {entities_folder}")
                for manifest_file in entities_folder.glob("*.entity_manifest"):
                    try:
                        manifest_type = manifest_file.stem  # e.g., 'player', 'weapon'
                        print(f"Loading base game manifest: {manifest_file}")
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
                                else:
                                    print(f"Referenced base game entity file not found: {entity_file}")
                                        
                        print(f"Loaded base game manifest {manifest_type} with {len(manifest_data.get('ids', []))} entries")
                    except Exception as e:
                        print(f"Error loading base game manifest file {manifest_file}: {str(e)}")
            else:
                print(f"Base game entities folder not found: {entities_folder}")
        else:
            logging.warning("No base game folder configured")
                        
        # Log summary
        for manifest_type in self.manifest_data['base_game']:
            count = len(self.manifest_data['base_game'][manifest_type])
            print(f"Total base game {manifest_type} entries: {count}")
            if count > 0:
                print(f"Example {manifest_type} entries: {list(self.manifest_data['base_game'][manifest_type].keys())[:3]}")
                   
    def load_mod_manifest_files(self) -> None:
        """Load manifest files from mod folder into memory"""
        logging.info("Loading mod manifest files...")
        
        # Clear existing mod manifest data
        self.manifest_data['mod'] = {}
        
        if self.current_folder:
            print(f"Using mod folder: {self.current_folder}")
            entities_folder = self.current_folder / "entities"
            if entities_folder.exists():
                print(f"Found mod entities folder: {entities_folder}")
                for manifest_file in entities_folder.glob("*.entity_manifest"):
                    try:
                        manifest_type = manifest_file.stem  # e.g., 'player', 'weapon'
                        print(f"Loading mod manifest: {manifest_file}")
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
                                        print(f"Loaded mod {manifest_type} data for {entity_id}")
                                else:
                                    print(f"Referenced mod entity file not found: {entity_file}")
                                        
                        print(f"Loaded mod manifest {manifest_type} with {len(manifest_data.get('ids', []))} entries")
                    except Exception as e:
                        print(f"Error loading mod manifest file {manifest_file}: {str(e)}")
            else:
                print(f"Mod entities folder not found: {entities_folder}")
        else:
            logging.warning("No mod folder loaded")
                        
        # Log summary
        for manifest_type in self.manifest_data['mod']:
            count = len(self.manifest_data['mod'][manifest_type])
            print(f"Total mod {manifest_type} entries: {count}")
            if count > 0:
                print(f"Example {manifest_type} entries: {list(self.manifest_data['mod'][manifest_type].keys())[:3]}")
                         
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
            print(f"Checking mod localized_text folder: {localized_text_folder}")
            if localized_text_folder.exists():
                for text_file in localized_text_folder.glob("*.localized_text"):
                    print(f"Loading mod localized text from: {text_file}")
                    try:
                        with open(text_file, 'r', encoding='utf-8') as f:
                            json_data = json.load(f)
                            # Initialize language dictionary if needed
                            language = text_file.stem
                            if language not in self.all_localized_strings['mod']:
                                self.all_localized_strings['mod'][language] = {}
                            # Add strings for this language
                            self.all_localized_strings['mod'][language].update(json_data)
                            # Initialize command stack with this data
                            self.command_stack.update_file_data(text_file, json_data)
                            print(f"Loaded {len(json_data)} strings for language {language} from {text_file}")
                    except Exception as e:
                        print(f"Error loading localized text file {text_file}: {str(e)}")
                        # Initialize with empty data on error
                        self.command_stack.update_file_data(text_file, {})
            else:
                logging.debug("No mod localized_text folder found")
                # Create the folder
                localized_text_folder.mkdir(parents=True, exist_ok=True)
                # Initialize empty files for current language and English
                for lang in [self.current_language, "en"]:
                    text_file = localized_text_folder / f"{lang}.localized_text"
                    self.command_stack.update_file_data(text_file, {})
        
        # Load base game strings
        if self.base_game_folder:
            # Load .localized_text files (JSON format)
            localized_text_folder = self.base_game_folder / "localized_text"
            print(f"Checking base game localized_text folder: {localized_text_folder}")
            if localized_text_folder.exists():
                for text_file in localized_text_folder.glob("*.localized_text"):
                    print(f"Loading base game localized text from: {text_file}")
                    try:
                        with open(text_file, 'r', encoding='utf-8') as f:
                            json_data = json.load(f)
                            # Initialize language dictionary if needed
                            language = text_file.stem
                            if language not in self.all_localized_strings['base_game']:
                                self.all_localized_strings['base_game'][language] = {}
                            # Add strings for this language
                            self.all_localized_strings['base_game'][language].update(json_data)
                            print(f"Loaded {len(json_data)} strings for language {language} from {text_file}")
                    except Exception as e:
                        print(f"Error loading localized text file {text_file}: {str(e)}")
            else:
                logging.debug("No base game localized_text folder found")
                        
        # Log summary
        for source in ['mod', 'base_game']:
            for language in self.all_localized_strings[source]:
                count = len(self.all_localized_strings[source][language])
                print(f"Total {source} strings for {language}: {count}")
                if count > 0:
                    # Log a few example strings
                    print(f"Example strings for {source} {language}:")
                    for i, (key, value) in enumerate(list(self.all_localized_strings[source][language].items())[:3]):
                        print(f"  {key} = {value}")
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
                print(f"Found {len(self.all_texture_files['mod'])} texture files in mod")
        
        # Load base game textures
        if self.base_game_folder:
            textures_folder = self.base_game_folder / "textures"
            if textures_folder.exists():
                for texture_file in textures_folder.glob("*.*"):
                    if texture_file.suffix.lower() in ['.png', '.dds']:
                        self.all_texture_files['base_game'].add(texture_file.stem)
                print(f"Found {len(self.all_texture_files['base_game'])} texture files in base game")

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
            print(f"Successfully loaded: {file_path}")
            print(f"Data type: {type(self.current_data)}")
            if isinstance(self.current_data, dict):
                print(f"Top-level keys: {list(self.current_data.keys())}")
                
        except Exception as e:
            print(f"Error loading file {file_path}: {str(e)}")
            self.current_file = None
            self.current_data = None
          
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
    
    def closeEvent(self, event):
        """Handle window close event"""
        if self.command_stack.has_unsaved_changes():
            reply = QMessageBox.question(
                self,
                'Unsaved Changes',
                'You have unsaved changes. Do you want to save before closing?',
                QMessageBox.StandardButton.Save | 
                QMessageBox.StandardButton.Discard | 
                QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Save
            )
            
            if reply == QMessageBox.StandardButton.Save:
                # Try to save changes
                if self.save_changes():
                    event.accept()
                else:
                    # If save failed, ask if they want to discard or cancel
                    reply = QMessageBox.question(
                        self,
                        'Save Failed',
                        'Failed to save changes. Do you want to discard changes and close anyway?',
                        QMessageBox.StandardButton.Discard | 
                        QMessageBox.StandardButton.Cancel,
                        QMessageBox.StandardButton.Cancel
                    )
                    if reply == QMessageBox.StandardButton.Discard:
                        event.accept()
                    else:
                        event.ignore()
            elif reply == QMessageBox.StandardButton.Discard:
                event.accept()
            else:  # Cancel
                event.ignore()
        else:
            event.accept()

    def open_folder_dialog(self):
        """Open directory dialog to select mod folder"""
        dir_path = QFileDialog.getExistingDirectory(
            self,
            "Select Mod Folder",
            str(self.current_folder) if self.current_folder else ""
        )
        if dir_path:
            self.load_folder(Path(dir_path))

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
                
    def save_config(self):
        """Save current configuration to config.json"""
        try:
            config_to_save = {
                "base_game_folder": str(self.base_game_folder) if self.base_game_folder else "",
                "schema_folder": str(self.config.get("schema_folder", ""))
            }
            with open('config.json', 'w') as f:
                json.dump(config_to_save, f, indent=4)
            logging.info("Configuration saved successfully")
        except Exception as e:
            logging.error(f"Failed to save config.json: {e}")
            QMessageBox.warning(self, "Error", f"Failed to save configuration: {str(e)}")

    def show_context_menu(self, widget, position, current_value):
        """Show the context menu at the given position"""
        print(f"show_context_menu called for widget: {widget}, position: {position}")
        menu = self.create_context_menu(widget, current_value)
        if menu:
            logging.debug("Menu created, about to show")
            menu.exec(widget.mapToGlobal(position))
        else:
            logging.debug("No menu was created")

    def create_context_menu(self, widget, current_value):
        """Create a context menu for text fields and buttons"""
        menu = QMenu(self)
        
        # Get schema and data path from widget or its container
        schema = None
        data_path = widget.property("data_path")
        print(f"Creating context menu for path: {data_path}")
            
        if data_path is not None:  # Changed from 'if data_path:' to handle empty lists
            # Find the schema for this path
            schema = self.get_schema_for_path(data_path)
            print(f"Got schema for path {data_path}: {schema}")
            
            # For top-level objects, we need to resolve references in the schema itself
            if not data_path and schema and "$ref" in schema:
                schema = self.resolve_schema_references(schema)
                print(f"Resolved top-level schema reference: {schema}")
        
        # Check if this is a property label/header for later use
        property_name = None
        is_property_label = (isinstance(widget, (QLabel, QToolButton)) and 
                           not isinstance(widget.parent(), QHBoxLayout) and
                           not widget.property("is_array_index"))
        
        if is_property_label:
            # Try to find property name from various widget types
            if isinstance(widget, QLabel):
                property_name = widget.text().replace(":", "").replace(" ", "_").lower()
            elif isinstance(widget, QToolButton):
                property_name = widget.text().replace(" ", "_").lower()
                
        # Add property/item menu if this is an object or array
        if schema and isinstance(current_value, (dict, list)):
            add_menu = menu.addMenu("Add..." if isinstance(current_value, dict) else "Add Item")
            
            if isinstance(current_value, dict):
                # Resolve schema references before checking properties
                schema = self.resolve_schema_references(schema)
                print(f"Resolved schema for properties: {schema}")

                # Get available properties from schema
                properties = schema.get("properties", {})
                required = schema.get("required", [])
                # Get currently used properties
                used_props = set(current_value.keys())
                print(f"Used properties: {used_props}")
                print(f"Available properties: {properties.keys()}")
                
                # Add menu items for each available property
                has_available_props = False
                for prop_name, prop_schema in sorted(properties.items()):
                    if prop_name not in used_props:
                        has_available_props = True
                        action = add_menu.addAction(prop_name)
                        is_required = prop_name in required
                        if is_required:
                            action.setText(f"{prop_name} (required)")
                        action.triggered.connect(
                            lambda checked, n=prop_name, s=prop_schema: 
                            self.add_property(widget, n, s)
                        )
                    
                # If no available properties, add a disabled message
                if not has_available_props:
                    print("No available properties found")
                    action = add_menu.addAction("No available properties")
                    action.setEnabled(False)
        
            elif isinstance(current_value, list):
                # Get item schema and resolve references
                items_schema = schema.get("items", {})
                if items_schema:
                    items_schema = self.resolve_schema_references(items_schema)
                    action = add_menu.addAction("New Item")
                    action.triggered.connect(
                        lambda checked: self.add_array_item(widget, items_schema)
                    )
                    
        # Only add selection menu for non-container values (not objects or arrays)
        if not isinstance(current_value, (dict, list)):
            select_menu = menu.addMenu("Select from...")
            
            # File selection action
            file_action = select_menu.addAction("File...")
            file_action.triggered.connect(lambda: self.show_file_selector(widget))
            
            # Uniforms selection action
            uniforms_action = select_menu.addAction("Uniforms...")
            uniforms_action.triggered.connect(lambda: self.show_uniforms_selector(widget))
            
            # Localized text selection action
            text_action = select_menu.addAction("Localized Text...")
            text_action.triggered.connect(lambda: self.show_localized_text_selector(widget))
            
            # Texture selection action
            texture_action = select_menu.addAction("Texture...")
            texture_action.triggered.connect(lambda: self.show_texture_selector(widget))
            
            # Sound selection action
            sound_action = select_menu.addAction("Sounds...")
            sound_action.triggered.connect(lambda: self.show_sound_selector(widget))
            
        # Add Delete Property option at the end if this is a property label/header
        if is_property_label and property_name and data_path:
            # Don't allow deletion of required properties
            parent_schema = self.get_schema_for_path(data_path[:-1])  # Get parent object's schema
            if not parent_schema or "required" not in parent_schema or property_name not in parent_schema["required"]:
                if len(menu.actions()) > 0:
                    menu.addSeparator()
                action = menu.addAction("Delete Property")
                action.triggered.connect(
                    lambda checked, w=widget, n=property_name: self.delete_property(w, n)
                )
            
        return menu

    def show_file_selector(self, target_widget):
        """Show a dialog to select a file from mod or base game"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Select File")
        dialog.resize(800, 600)  # Make the dialog larger
        layout = QVBoxLayout(dialog)
        
        # File type selector
        type_layout = QHBoxLayout()
        type_label = QLabel("File Type:")
        type_combo = QComboBox()
        type_combo.addItems(sorted(set(self.manifest_data['mod'].keys()) | 
                                 set(self.manifest_data['base_game'].keys())))
        type_layout.addWidget(type_label)
        type_layout.addWidget(type_combo)
        layout.addLayout(type_layout)
        
        # Add search box
        search_box = QLineEdit()
        search_box.setPlaceholderText("Search files...")
        layout.addWidget(search_box)
        
        # File list
        file_list = QListWidget()
        layout.addWidget(file_list)
        
        def update_file_list():
            file_list.clear()
            file_type = type_combo.currentText()
            search_text = search_box.text().lower()
            
            # Add mod files first
            for file_id in sorted(self.manifest_data['mod'].get(file_type, {})):
                if search_text in file_id.lower():
                    item = QListWidgetItem(file_id)
                    file_list.addItem(item)
                    
            # Then add base game files (grayed out)
            for file_id in sorted(self.manifest_data['base_game'].get(file_type, {})):
                if (file_id not in self.manifest_data['mod'].get(file_type, {}) and 
                    search_text in file_id.lower()):
                    item = QListWidgetItem(file_id)
                    item.setForeground(QColor(150, 150, 150))
                    font = item.font()
                    font.setItalic(True)
                    item.setFont(font)
                    file_list.addItem(item)
        
        type_combo.currentTextChanged.connect(update_file_list)
        search_box.textChanged.connect(update_file_list)
        update_file_list()  # Initial population
        
        # Buttons
        button_box = QHBoxLayout()
        select_btn = QPushButton("Select")
        select_btn.setEnabled(False)  # Disabled until an item is selected
        copy_btn = QPushButton("Copy...")
        cancel_btn = QPushButton("Cancel")
        button_box.addStretch()
        button_box.addWidget(select_btn)
        button_box.addWidget(copy_btn)
        button_box.addWidget(cancel_btn)
        layout.addLayout(button_box)
        
        def on_select():
            if file_list.currentItem():
                new_value = file_list.currentItem().text()
                self.on_select_value(target_widget, new_value)
                dialog.accept()
                
        def on_copy():
            if not file_list.currentItem():
                return
                
            source_file = file_list.currentItem().text()
            file_type = type_combo.currentText()
            is_base_game = file_list.currentItem().foreground().color().getRgb()[:3] == (150, 150, 150)
            
            # Show copy dialog
            copy_dialog = QDialog(dialog)
            copy_dialog.setWindowTitle("Copy File")
            copy_layout = QVBoxLayout(copy_dialog)
            
            # Add option to overwrite if it's a base game file
            overwrite = False
            if is_base_game:
                overwrite_check = QCheckBox("Overwrite in mod (keep same name)")
                copy_layout.addWidget(overwrite_check)
                
                def on_overwrite_changed(state):
                    nonlocal overwrite
                    overwrite = state == Qt.CheckState.Checked.value
                    name_edit.setEnabled(not overwrite)
                    name_edit.setText(source_file if overwrite else "")
                    
                overwrite_check.stateChanged.connect(on_overwrite_changed)
            
            # Add name input
            name_layout = QHBoxLayout()
            name_layout.addWidget(QLabel("New Name:"))
            name_edit = QLineEdit()
            name_layout.addWidget(name_edit)
            copy_layout.addLayout(name_layout)
            
            # Add copy/cancel buttons
            copy_buttons = QHBoxLayout()
            copy_ok = QPushButton("Copy")
            copy_cancel = QPushButton("Cancel")
            copy_buttons.addWidget(copy_ok)
            copy_buttons.addWidget(copy_cancel)
            copy_layout.addLayout(copy_buttons)
            
            def do_copy():
                new_name = name_edit.text().strip()
                if not new_name:
                    QMessageBox.warning(copy_dialog, "Error", "Please enter a name for the copy")
                    return
                    
                try:
                    # Get the file path and data path from the target widget
                    file_path = self.get_schema_view_file_path(target_widget)
                    data_path = target_widget.property("data_path")
                    
                    # Create the copy command
                    copy_command = CreateFileFromCopy(
                        self,
                        source_file,
                        file_type,
                        new_name,
                        overwrite
                    )
                    
                    # Prepare and validate the command
                    if not copy_command.prepare():
                        QMessageBox.warning(copy_dialog, "Error", "Failed to prepare file copy")
                        return
                        
                    # Execute the copy command first to create the file
                    if not copy_command.execute():
                        QMessageBox.warning(copy_dialog, "Error", "Failed to create file copy")
                        return
                        
                    # Create transform command for the widget
                    transform_cmd = TransformWidgetCommand(self, target_widget, source_file, new_name)
                    transform_cmd.file_path = file_path
                    transform_cmd.data_path = data_path
                    
                    # Create composite command with both operations in the correct order
                    composite_cmd = CompositeCommand([copy_command, transform_cmd])
                    composite_cmd.file_path = file_path
                    composite_cmd.data_path = data_path
                    
                    # Close both dialogs before adding to command stack
                    copy_dialog.accept()
                    dialog.accept()
                    
                    # Add command to stack for undo/redo
                    self.command_stack.push(composite_cmd)
                    
                    # Update the file list
                    update_file_list()
                    
                    # Select the new file
                    for i in range(file_list.count()):
                        if file_list.item(i).text() == new_name:
                            file_list.setCurrentRow(i)
                            break
                        
                except Exception as e:
                    QMessageBox.warning(copy_dialog, "Error", str(e))
            
            copy_ok.clicked.connect(do_copy)
            copy_cancel.clicked.connect(copy_dialog.reject)
            
            copy_dialog.exec()
        
        def on_current_item_changed(current, previous):
            select_btn.setEnabled(current is not None)
        
        select_btn.clicked.connect(on_select)
        copy_btn.clicked.connect(on_copy)
        cancel_btn.clicked.connect(dialog.reject)
        file_list.itemDoubleClicked.connect(on_select)
        file_list.currentItemChanged.connect(on_current_item_changed)
        
        dialog.exec()

    def show_uniforms_selector(self, target_widget):
        """Show a dialog to select a uniform value"""
        # Set the is_uniform property on the target widget
        target_widget.setProperty("is_uniform", True)
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Select Uniform Value")
        dialog.resize(800, 600)
        layout = QVBoxLayout(dialog)
        
        # Uniforms file selector
        file_layout = QHBoxLayout()
        file_label = QLabel("Uniforms File:")
        file_combo = QComboBox()
        
        # Get all available uniform files from both mod and base game
        mod_uniforms = set()
        base_uniforms = set()
        
        # Get mod uniforms
        if self.current_folder:
            mod_uniforms_dir = self.current_folder / "uniforms"
            if mod_uniforms_dir.exists():
                for file_path in mod_uniforms_dir.glob("*.uniforms"):
                    mod_uniforms.add(file_path.stem)
        
        # Get base game uniforms
        if self.base_game_folder:
            base_uniforms_dir = self.base_game_folder / "uniforms"
            if base_uniforms_dir.exists():
                for file_path in base_uniforms_dir.glob("*.uniforms"):
                    base_uniforms.add(file_path.stem)
        
        # Add all files to combo box, marking their source
        all_files = sorted(mod_uniforms | base_uniforms)
        for file_id in all_files:
            # Add mod version if it exists
            if file_id in mod_uniforms:
                file_combo.addItem(f"{file_id} (Mod)")
            
            # Add base game version if it exists
            if file_id in base_uniforms:
                file_combo.addItem(file_id)
                # Style base game items
                index = file_combo.count() - 1
                file_combo.setItemData(index, QColor(150, 150, 150), Qt.ItemDataRole.ForegroundRole)
                font = file_combo.itemData(index, Qt.ItemDataRole.FontRole) or QFont()
                font.setItalic(True)
                file_combo.setItemData(index, font, Qt.ItemDataRole.FontRole)
        
        file_layout.addWidget(file_label)
        file_layout.addWidget(file_combo)
        layout.addLayout(file_layout)
        
        # Tree widget for nested data
        tree = QTreeWidget()
        tree.setHeaderLabels(["Key", "Value"])
        tree.setColumnWidth(0, 300)  # Give more space to the key column
        layout.addWidget(tree)
        
        def add_item(parent, key, value, full_path=""):
            """Recursively add items to the tree"""
            if full_path:
                new_path = f"{full_path}.{key}" if isinstance(key, str) else f"{full_path}[{key}]"
            else:
                new_path = str(key)
                
            item = QTreeWidgetItem(parent)
            item.setText(0, str(key))
            
            if isinstance(value, dict):
                item.setText(1, "{...}")
                for k, v in sorted(value.items()):
                    add_item(item, k, v, new_path)
            elif isinstance(value, list):
                item.setText(1, f"[{len(value)} items]")
                for i, v in enumerate(value):
                    add_item(item, i, v, new_path)
            else:
                item.setText(1, str(value))
                # Store the full path and value for selection
                item.setData(0, Qt.ItemDataRole.UserRole, (new_path, value))
        
        def update_tree():
            tree.clear()
            selected_text = file_combo.currentText()
            if not selected_text:
                return
                
            # Determine if this is a mod or base game file
            is_base_game = not selected_text.endswith(" (Mod)")
            file_id = selected_text.replace(" (Mod)", "") if not is_base_game else selected_text
                
            try:
                # Load the appropriate file based on selection
                if is_base_game:
                    file_path = self.base_game_folder / "uniforms" / f"{file_id}.uniforms"
                else:
                    file_path = self.current_folder / "uniforms" / f"{file_id}.uniforms"
                
                if file_path and file_path.exists():
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        for key, value in sorted(data.items()):
                            add_item(tree, key, value)
                            
                    tree.expandToDepth(0)  # Expand first level by default
                    
                    # Style items if base game
                    if is_base_game:
                        def style_items(item):
                            item.setForeground(0, QColor(150, 150, 150))
                            item.setForeground(1, QColor(150, 150, 150))
                            font = item.font(0)
                            font.setItalic(True)
                            item.setFont(0, font)
                            item.setFont(1, font)
                            for i in range(item.childCount()):
                                style_items(item.child(i))
                                
                        for i in range(tree.topLevelItemCount()):
                            style_items(tree.topLevelItem(i))
                            
            except Exception as e:
                print(f"Error loading uniforms file: {str(e)}")
        
        def on_item_selected():
            item = tree.currentItem()
            if not item:
                return
                
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if data:  # Only leaf nodes have data
                path, value = data
                new_value = str(value) if not isinstance(value, (dict, list)) else path
                self.on_select_value(target_widget, new_value)
                dialog.accept()
        
        def on_item_double_clicked(item, column):
            on_item_selected()
        
        file_combo.currentTextChanged.connect(update_tree)
        tree.itemDoubleClicked.connect(on_item_double_clicked)
        update_tree()  # Initial population
        
        # Buttons
        button_box = QHBoxLayout()
        select_btn = QPushButton("Select")
        select_btn.setEnabled(False)  # Disabled until an item is selected
        cancel_btn = QPushButton("Cancel")
        button_box.addStretch()
        button_box.addWidget(select_btn)
        button_box.addWidget(cancel_btn)
        layout.addLayout(button_box)
        
        # Enable select button when an item is selected
        def on_current_item_changed(current, previous):
            select_btn.setEnabled(current is not None and current.data(0, Qt.ItemDataRole.UserRole) is not None)
        
        tree.currentItemChanged.connect(on_current_item_changed)
        select_btn.clicked.connect(on_item_selected)
        cancel_btn.clicked.connect(dialog.reject)
        
        dialog.exec()

    def show_localized_text_selector(self, target_widget):
        """Show a dialog to select localized text"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Select Localized Text")
        dialog.resize(800, 600)  # Make the dialog larger
        layout = QVBoxLayout(dialog)
        
        # Language selector
        lang_layout = QHBoxLayout()
        lang_label = QLabel("Language:")
        lang_combo = QComboBox()
        
        # Get all available languages
        all_languages = set()
        for source in ['mod', 'base_game']:
            all_languages.update(self.all_localized_strings[source].keys())
        
        lang_combo.addItems(sorted(all_languages))
        # Set current language if available, otherwise default to English
        current_index = lang_combo.findText(self.current_language)
        if current_index >= 0:
            lang_combo.setCurrentIndex(current_index)
        elif lang_combo.findText("en") >= 0:
            lang_combo.setCurrentIndex(lang_combo.findText("en"))
            
        lang_layout.addWidget(lang_label)
        lang_layout.addWidget(lang_combo)
        layout.addLayout(lang_layout)
        
        # Search box
        search_box = QLineEdit()
        search_box.setPlaceholderText("Search...")
        layout.addWidget(search_box)
        
        # Text list
        text_list = QListWidget()
        layout.addWidget(text_list)
        
        def update_text_list(search=""):
            text_list.clear()
            search = search.lower()
            current_lang = lang_combo.currentText()
            
            # Helper to add items with proper styling
            def add_items(items, is_base_game=False):
                for key, value in sorted(items.items()):
                    if search in key.lower() or search in str(value).lower():
                        item = QListWidgetItem(f"{key}: {value}")
                        item.setData(Qt.ItemDataRole.UserRole, key)  # Store just the key
                        if is_base_game:
                            item.setForeground(QColor(150, 150, 150))
                            font = item.font()
                            font.setItalic(True)
                            item.setFont(font)
                        text_list.addItem(item)
            
            # Add mod texts first
            if current_lang in self.all_localized_strings['mod']:
                add_items(self.all_localized_strings['mod'][current_lang])
            
            # Then add base game texts
            if current_lang in self.all_localized_strings['base_game']:
                add_items(self.all_localized_strings['base_game'][current_lang], True)
        
        search_box.textChanged.connect(update_text_list)
        lang_combo.currentTextChanged.connect(lambda: update_text_list(search_box.text()))
        update_text_list()  # Initial population
        
        # Buttons
        button_box = QHBoxLayout()
        select_btn = QPushButton("Select")
        select_btn.setEnabled(False)  # Disabled until an item is selected
        create_btn = QPushButton("Create New...")
        cancel_btn = QPushButton("Cancel")
        button_box.addStretch()
        button_box.addWidget(create_btn)
        button_box.addWidget(select_btn)
        button_box.addWidget(cancel_btn)
        layout.addLayout(button_box)
        
        def show_create_dialog():
            create_dialog = QDialog(dialog)
            create_dialog.setWindowTitle("Create New Localized Text")
            create_layout = QVBoxLayout(create_dialog)
            
            # Key input
            key_layout = QHBoxLayout()
            key_label = QLabel("Key:")
            key_edit = QLineEdit()
            key_layout.addWidget(key_label)
            key_layout.addWidget(key_edit)
            create_layout.addLayout(key_layout)
            
            # Text input
            text_layout = QVBoxLayout()
            text_label = QLabel("Text:")
            text_edit = QPlainTextEdit()
            text_edit.setFixedHeight(100)  # Set a reasonable height for the text input
            text_layout.addWidget(text_label)
            text_layout.addWidget(text_edit)
            create_layout.addLayout(text_layout)
            
            # Create/Cancel buttons
            create_buttons = QHBoxLayout()
            create_ok = QPushButton("Create")
            create_cancel = QPushButton("Cancel")
            create_buttons.addStretch()
            create_buttons.addWidget(create_ok)
            create_buttons.addWidget(create_cancel)
            create_layout.addLayout(create_buttons)
            
            def on_create():
                key = key_edit.text().strip()
                text = text_edit.toPlainText().strip()
                
                if not key:
                    QMessageBox.warning(create_dialog, "Error", "Please enter a key")
                    return
                    
                if not text:
                    QMessageBox.warning(create_dialog, "Error", "Please enter text")
                    return
                    
                # Check if key already exists
                current_lang = lang_combo.currentText()
                if (current_lang in self.all_localized_strings['mod'] and 
                    key in self.all_localized_strings['mod'][current_lang]):
                    QMessageBox.warning(create_dialog, "Error", "Key already exists in mod")
                    return
                    
                if (current_lang in self.all_localized_strings['base_game'] and 
                    key in self.all_localized_strings['base_game'][current_lang]):
                    reply = QMessageBox.question(
                        create_dialog,
                        "Key Exists in Base Game",
                        "This key exists in the base game. Do you want to override it?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.No
                    )
                    if reply != QMessageBox.StandardButton.Yes:
                        return
                
                # Create the command
                command = CreateLocalizedText(self, key, text, current_lang)
                self.command_stack.push(command)
                
                # Update the list and select the new item
                update_text_list()
                for i in range(text_list.count()):
                    item = text_list.item(i)
                    if item.data(Qt.ItemDataRole.UserRole) == key:
                        text_list.setCurrentItem(item)
                        break
                
                create_dialog.accept()
            
            create_ok.clicked.connect(on_create)
            create_cancel.clicked.connect(create_dialog.reject)
            
            create_dialog.exec()
        
        def on_item_selected():
            item = text_list.currentItem()
            if item:
                new_value = item.data(Qt.ItemDataRole.UserRole)
                self.on_select_value(target_widget, new_value)
                dialog.accept()
        
        def on_item_double_clicked(item):
            on_item_selected()
        
        # Enable select button when an item is selected
        def on_current_item_changed(current, previous):
            select_btn.setEnabled(current is not None)
        
        text_list.currentItemChanged.connect(on_current_item_changed)
        text_list.itemDoubleClicked.connect(on_item_double_clicked)
        select_btn.clicked.connect(on_item_selected)
        create_btn.clicked.connect(show_create_dialog)
        cancel_btn.clicked.connect(dialog.reject)
        
        dialog.exec()

    def show_array_item_menu(self, widget: QWidget, pos):
        """Show context menu for array item indices"""
        print("Showing array item menu")
        menu = QMenu()
        
        # Get data path and array data
        data_path = widget.property("data_path")
        array_data = widget.property("array_data")
        
        if data_path and array_data and len(array_data) > 1:
            # Add delete action
            delete_action = menu.addAction("Delete Item")
            delete_action.triggered.connect(
                lambda: self.delete_array_item(widget, data_path)
            )
        
        menu.exec(widget.mapToGlobal(pos))
        
    def show_texture_selector(self, target_widget):
        """Show a dialog to select a texture"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Select Texture")
        dialog.resize(1000, 600)
        layout = QHBoxLayout(dialog)
        
        # Left side with list
        left_side = QWidget()
        left_layout = QVBoxLayout(left_side)
        layout.addWidget(left_side)
        
        # Add search box
        search_box = QLineEdit()
        search_box.setPlaceholderText("Search textures...")
        left_layout.addWidget(search_box)
        
        # Create list widget for textures
        texture_list = QListWidget()
        left_layout.addWidget(texture_list)
        
        # Right side with preview
        right_side = QWidget()
        right_layout = QVBoxLayout(right_side)
        layout.addWidget(right_side)
        
        # Preview label
        preview_label = QLabel()
        preview_label.setMinimumSize(300, 300)
        preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        right_layout.addWidget(preview_label)
        right_layout.addStretch()
        
        def update_texture_list(search=""):
            texture_list.clear()
            search = search.lower()
            
            def add_textures(textures, is_base_game=False):
                for texture in sorted(textures):
                    if search in texture.lower():
                        item = QListWidgetItem(texture)
                        if is_base_game:
                            item.setForeground(QColor(150, 150, 150))
                            font = item.font()
                            font.setItalic(True)
                            item.setFont(font)
                        texture_list.addItem(item)
            
            # Add mod textures first
            add_textures(self.all_texture_files['mod'])
            # Then add base game textures
            add_textures(self.all_texture_files['base_game'], True)
        
        # Connect search box
        search_box.textChanged.connect(update_texture_list)
        
        # Buttons
        button_box = QHBoxLayout()
        select_btn = QPushButton("Select")
        select_btn.setEnabled(False)
        cancel_btn = QPushButton("Cancel")
        button_box.addStretch()
        button_box.addWidget(select_btn)
        button_box.addWidget(cancel_btn)
        left_layout.addLayout(button_box)
        
        def on_item_selected():
            if texture_list.currentItem():
                new_value = texture_list.currentItem().text()
                self.on_select_value(target_widget, new_value)
                dialog.accept()
        
        def on_item_double_clicked(item):
            on_item_selected()
        
        def on_current_item_changed(current, previous):
            select_btn.setEnabled(current is not None)
            if current:
                # Update preview
                texture_name = current.text()
                pixmap, _ = self.load_texture(texture_name)
                if pixmap:
                    # Scale pixmap to fit preview area while maintaining aspect ratio
                    scaled_pixmap = pixmap.scaled(300, 300, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    preview_label.setPixmap(scaled_pixmap)
                else:
                    preview_label.setText("No preview available")
            else:
                preview_label.clear()
        
        texture_list.currentItemChanged.connect(on_current_item_changed)
        texture_list.itemDoubleClicked.connect(on_item_double_clicked)
        select_btn.clicked.connect(on_item_selected)
        cancel_btn.clicked.connect(dialog.reject)
        
        # Initial population
        update_texture_list()
        dialog.exec()

    def show_sound_selector(self, target_widget):
        """Show a dialog to select a sound file"""
        # Initialize pygame mixer
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Select Sound")
        dialog.resize(800, 500)
        layout = QVBoxLayout(dialog)
        
        # Search box
        search_box = QLineEdit()
        search_box.setPlaceholderText("Search sounds...")
        layout.addWidget(search_box)
        
        # Sound list
        sound_list = QListWidget()
        layout.addWidget(sound_list)
        
        # Playback controls
        controls_layout = QHBoxLayout()
        play_button = QPushButton("Play")
        stop_button = QPushButton("Stop")
        stop_button.setEnabled(False)
        controls_layout.addWidget(play_button)
        controls_layout.addWidget(stop_button)
        layout.addLayout(controls_layout)
        
        # Audio playback state
        audio_state = {
            'playing': False,
            'sound': None
        }
        
        def get_sound_files():
            """Get all .ogg files from mod and base game"""
            sound_files = {'mod': set(), 'base_game': set()}
            
            # Get mod sounds
            if self.current_folder:
                sound_dir = self.current_folder / "sounds"
                if sound_dir.exists():
                    for file_path in sound_dir.rglob("*.ogg"):
                        rel_path = file_path.relative_to(sound_dir)
                        sound_files['mod'].add(str(rel_path).replace('\\', '/'))
            
            # Get base game sounds
            if self.base_game_folder:
                sound_dir = self.base_game_folder / "sounds"
                if sound_dir.exists():
                    for file_path in sound_dir.rglob("*.ogg"):
                        rel_path = file_path.relative_to(sound_dir)
                        rel_path_str = str(rel_path).replace('\\', '/')
                        if rel_path_str not in sound_files['mod']:
                            sound_files['base_game'].add(rel_path_str)
            
            return sound_files
            
        def update_sound_list(search=""):
            sound_list.clear()
            search = search.lower()
            sound_files = get_sound_files()
            
            # Add mod sounds first
            for sound in sorted(sound_files['mod']):
                if search in sound.lower():
                    # Strip .ogg extension for display
                    display_name = str(Path(sound).with_suffix(''))
                    item = QListWidgetItem(display_name)
                    # Store full path with extension as data
                    item.setData(Qt.ItemDataRole.UserRole, sound)
                    sound_list.addItem(item)
            
            # Then add base game sounds
            for sound in sorted(sound_files['base_game']):
                if search in sound.lower():
                    # Strip .ogg extension for display
                    display_name = str(Path(sound).with_suffix(''))
                    item = QListWidgetItem(display_name)
                    # Store full path with extension as data
                    item.setData(Qt.ItemDataRole.UserRole, sound)
                    item.setForeground(QColor(150, 150, 150))
                    font = item.font()
                    font.setItalic(True)
                    item.setFont(font)
                    sound_list.addItem(item)
        
        def play_sound():
            if not sound_list.currentItem():
                return
                
            # Get full path with extension from item data
            sound_path = sound_list.currentItem().data(Qt.ItemDataRole.UserRole)
            is_base_game = sound_list.currentItem().foreground().color().getRgb()[:3] == (150, 150, 150)
            
            # Get full path
            base_dir = self.base_game_folder if is_base_game else self.current_folder
            full_path = base_dir / "sounds" / sound_path
            
            if full_path.exists():
                try:
                    # Stop any existing playback
                    stop_sound()
                    
                    # Load and play the sound
                    audio_state['sound'] = pygame.mixer.Sound(str(full_path))
                    audio_state['sound'].play()
                    audio_state['playing'] = True
                    
                    play_button.setEnabled(False)
                    stop_button.setEnabled(True)
                    
                    # Start a timer to check when playback is done
                    def check_playback():
                        while audio_state['playing'] and pygame.mixer.get_busy():
                            pygame.time.wait(100)
                        if audio_state['playing']:  # If not stopped manually
                            audio_state['playing'] = False
                            play_button.setEnabled(True)
                            stop_button.setEnabled(False)
                    
                    threading.Thread(target=check_playback, daemon=True).start()
                    
                except Exception as e:
                    print(f"Error playing sound: {str(e)}")
                    audio_state['playing'] = False
                    play_button.setEnabled(True)
                    stop_button.setEnabled(False)
        
        def stop_sound():
            if audio_state['sound']:
                audio_state['sound'].stop()
            audio_state['playing'] = False
            audio_state['sound'] = None
            play_button.setEnabled(True)
            stop_button.setEnabled(False)
        
        # Connect signals
        search_box.textChanged.connect(update_sound_list)
        play_button.clicked.connect(play_sound)
        stop_button.clicked.connect(stop_sound)
        
        # Selection buttons
        button_box = QHBoxLayout()
        select_btn = QPushButton("Select")
        select_btn.setEnabled(False)
        cancel_btn = QPushButton("Cancel")
        button_box.addStretch()
        button_box.addWidget(select_btn)
        button_box.addWidget(cancel_btn)
        layout.addLayout(button_box)
        
        def on_item_selected():
            if sound_list.currentItem():
                stop_sound()  # Stop any playing sound
                # Use display name (without extension) for selection
                new_value = sound_list.currentItem().text()
                self.on_select_value(target_widget, new_value)
                dialog.accept()
        
        def on_item_double_clicked(item):
            on_item_selected()
        
        def on_current_item_changed(current, previous):
            select_btn.setEnabled(current is not None)
            play_button.setEnabled(current is not None)
        
        # Connect selection signals
        sound_list.currentItemChanged.connect(on_current_item_changed)
        sound_list.itemDoubleClicked.connect(on_item_double_clicked)
        select_btn.clicked.connect(on_item_selected)
        cancel_btn.clicked.connect(dialog.reject)
        
        # Clean up on close
        dialog.finished.connect(stop_sound)
        
        # Initial population
        update_sound_list()
        dialog.exec()
        
        # Clean up pygame mixer
        pygame.mixer.quit()

    def show_add_player_dialog(self):
        """Show dialog to create a new player by copying an existing one"""
        if not self.current_folder:
            QMessageBox.warning(self, "Error", "Please open a mod folder first")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Add/Delete Player")
        dialog.resize(800, 600)  # Make the dialog larger
        layout = QVBoxLayout(dialog)

        # Add search box
        search_box = QLineEdit()
        search_box.setPlaceholderText("Search players...")
        layout.addWidget(search_box)

        # Player list
        player_list = QListWidget()
        layout.addWidget(player_list)

        def update_player_list(search=""):
            player_list.clear()
            search = search.lower()

            # Add mod players first
            for player_id in sorted(self.manifest_data['mod'].get('player', {})):
                if search in player_id.lower():
                    item = QListWidgetItem(player_id)
                    player_list.addItem(item)

            # Then add base game players
            for player_id in sorted(self.manifest_data['base_game'].get('player', {})):
                if (player_id not in self.manifest_data['mod'].get('player', {}) and 
                    search in player_id.lower()):
                    item = QListWidgetItem(player_id)
                    item.setForeground(QColor(150, 150, 150))
                    font = item.font()
                    font.setItalic(True)
                    item.setFont(font)
                    player_list.addItem(item)

        search_box.textChanged.connect(update_player_list)
        update_player_list()  # Initial population

        # Buttons
        button_box = QHBoxLayout()
        delete_btn = QPushButton("Delete")
        delete_btn.setEnabled(False)  # Initially disabled
        button_box.addWidget(delete_btn)
        copy_btn = QPushButton("Copy...")
        cancel_btn = QPushButton("Cancel")
        button_box.addStretch()

        button_box.addWidget(copy_btn)
        button_box.addWidget(cancel_btn)
        layout.addLayout(button_box)

        def on_copy():
            if not player_list.currentItem():
                return

            source_file = player_list.currentItem().text()
            is_base_game = player_list.currentItem().foreground().color().getRgb()[:3] == (150, 150, 150)

            # Show copy dialog
            copy_dialog = QDialog(dialog)
            copy_dialog.setWindowTitle("Copy Player")
            copy_layout = QVBoxLayout(copy_dialog)

            # Add option to overwrite if it's a base game file
            overwrite = False
            if is_base_game:
                overwrite_check = QCheckBox("Overwrite in mod (keep same name)")
                copy_layout.addWidget(overwrite_check)

                def on_overwrite_changed(state):
                    nonlocal overwrite
                    overwrite = state == Qt.CheckState.Checked.value
                    name_edit.setEnabled(not overwrite)
                    name_edit.setText(source_file if overwrite else "")

                overwrite_check.stateChanged.connect(on_overwrite_changed)

            # Add name input
            name_layout = QHBoxLayout()
            name_layout.addWidget(QLabel("New Name:"))
            name_edit = QLineEdit()
            name_layout.addWidget(name_edit)
            copy_layout.addLayout(name_layout)

            # Add copy/cancel buttons
            copy_buttons = QHBoxLayout()
            copy_ok = QPushButton("Copy")
            copy_cancel = QPushButton("Cancel")
            copy_buttons.addWidget(copy_ok)
            copy_buttons.addWidget(copy_cancel)
            copy_layout.addLayout(copy_buttons)

            def do_copy():
                new_name = name_edit.text().strip()
                if not new_name:
                    QMessageBox.warning(copy_dialog, "Error", "Please enter a name for the copy")
                    return

                try:
                    # Create the copy command
                    copy_command = CreateFileFromCopy(
                        self,
                        source_file,
                        "player",
                        new_name,
                        overwrite
                    )

                    # Prepare and validate the command
                    if not copy_command.prepare():
                        QMessageBox.warning(copy_dialog, "Error", "Failed to prepare player copy")
                        return

                    # Execute the copy command
                    if not copy_command.execute():
                        QMessageBox.warning(copy_dialog, "Error", "Failed to create player copy")
                        return

                    # Add command to stack for undo/redo
                    self.command_stack.push(copy_command)

                    # Close both dialogs
                    copy_dialog.accept()
                    dialog.accept()

                    # Update the player selector and select the new player
                    self.player_selector.addItem(new_name)
                    self.player_selector.setCurrentText(new_name)
                    self.on_player_selected(new_name)

                except Exception as e:
                    QMessageBox.warning(copy_dialog, "Error", str(e))

            copy_ok.clicked.connect(do_copy)
            copy_cancel.clicked.connect(copy_dialog.reject)

            copy_dialog.exec()

        def on_delete():
            if not player_list.currentItem():
                return

            player_id = player_list.currentItem().text()
            is_base_game = player_list.currentItem().foreground().color().getRgb()[:3] == (150, 150, 150)

            if is_base_game:
                QMessageBox.warning(dialog, "Error", "Cannot delete base game players")
                return

            reply = QMessageBox.question(
                dialog,
                "Confirm Delete",
                f"Are you sure you want to delete player '{player_id}'?\nThis cannot be undone.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )

            if reply != QMessageBox.StandardButton.Yes:
                return

            try:
                # Delete the player file
                player_file = self.current_folder / "entities" / f"{player_id}.player"
                if player_file.exists():
                    player_file.unlink()

                # Update the manifest file
                manifest_file = self.current_folder / "entities" / "player.entity_manifest"
                if manifest_file.exists():
                    with open(manifest_file, 'r', encoding='utf-8') as f:
                        manifest_data = json.load(f)
                    if "ids" in manifest_data and player_id in manifest_data["ids"]:
                        manifest_data["ids"].remove(player_id)
                        with open(manifest_file, 'w', encoding='utf-8') as f:
                            json.dump(manifest_data, f, indent=4)

                # Remove from GUI's manifest data
                if 'player' in self.manifest_data['mod']:
                    self.manifest_data['mod']['player'].pop(player_id, None)

                # Remove from player selector
                index = self.player_selector.findText(player_id)
                if index >= 0:
                    self.player_selector.removeItem(index)

                # Remove from list and select another item
                row = player_list.row(player_list.currentItem())
                player_list.takeItem(row)
                if player_list.count() > 0:
                    player_list.setCurrentRow(min(row, player_list.count() - 1))

                # Close dialog
                dialog.accept()

            except Exception as e:
                QMessageBox.warning(dialog, "Error", f"Failed to delete player: {str(e)}")

        def on_current_item_changed(current, previous):
            if current:
                is_base_game = current.foreground().color().getRgb()[:3] == (150, 150, 150)
                delete_btn.setEnabled(not is_base_game)

        player_list.currentItemChanged.connect(on_current_item_changed)
        delete_btn.clicked.connect(on_delete)
        copy_btn.clicked.connect(on_copy)
        cancel_btn.clicked.connect(dialog.reject)

        dialog.exec()

    def undo(self):
        """Undo the last command"""
        self.command_stack.undo()
        self.update_save_button()  # Update button states
    
    def redo(self):
        """Redo the last undone command"""
        self.command_stack.redo()
        self.update_save_button()  # Update button states
    
    def get_current_value_from_command_stack(self, file_path: Path, path: list, default_value: any) -> any:
        """Get the current value from command stack if available, otherwise return default"""
        if not file_path or not path:
            return default_value
            
        data = self.command_stack.get_file_data(file_path)
        if not data:
            return default_value
            
        # Navigate through the path to get the value
        current = data
        try:
            for key in path[:-1]:
                if isinstance(current, dict):
                    current = current.get(key, {})
                elif isinstance(current, list) and isinstance(key, int) and key < len(current):
                    current = current[key]
                else:
                    return default_value
                    
            if isinstance(current, dict):
                return current.get(path[-1], default_value)
            elif isinstance(current, list) and isinstance(path[-1], int) and path[-1] < len(current):
                return current[path[-1]]
            return default_value
        except Exception:
            return default_value

    def save_changes(self):
        """Save all changes and return True if successful"""
        if not self.command_stack.has_unsaved_changes():
            logging.info("No unsaved changes to save")
            return True
            
        # Get all modified files
        modified_files = self.command_stack.get_modified_files()
        print(f"Found {len(modified_files)} modified files to save")
        print(f"Modified files list: {modified_files}")
        
        success = True
        for file_path in modified_files:
            print(f"Processing file for save: {file_path}")
            
            # Get the latest data from the command stack
            data = self.command_stack.get_file_data(file_path)
            
            if not data:
                print(f"No data found in command stack for file: {file_path}")
                success = False
                continue
                    
            # Save the file
            print(f"Attempting to save file: {file_path}")
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=4)
                print(f"Successfully saved file: {file_path}")
            except Exception as e:
                print(f"Failed to save file {file_path}: {str(e)}")
                success = False
                continue
                
        # Update UI and command stack state
        if success:
            self.status_label.setText("All changes saved")
            self.status_label.setProperty("status", "success")
            logging.info("All files saved successfully")
            # Mark all changes as saved in command stack
            self.command_stack.mark_all_saved()
        else:
            self.status_label.setText("Error saving some changes")
            self.status_label.setProperty("status", "error")
            logging.error("Some files failed to save")
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)
        
        # Update save button state
        self.update_save_button()
        print(f"Save button enabled: {self.command_stack.has_unsaved_changes()}")

        return success
        
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

    def update_data_value(self, data_path: list, new_value: any):
        """Update a value in the data structure using its path"""
        print(f"Updating data value at path {data_path} to {new_value}")

        if not data_path:
            # Empty path - replace entire data structure
            self.current_data = new_value
            print(f"Replaced entire data structure with new value")
            return
        
        if len(data_path) == 1:
            # Single path element - modify root property
            if isinstance(self.current_data, dict):
                if new_value is None:
                    # Remove property if new_value is None
                    if data_path[0] in self.current_data:
                        del self.current_data[data_path[0]]
                        print(f"Removed root property {data_path[0]}")
                else:
                    # Add or update property
                    self.current_data[data_path[0]] = new_value
                    print(f"Updated root property {data_path[0]} to {new_value}")
            return
        
        current = self.current_data
        for i, key in enumerate(data_path[:-1]):
            print(f"Traversing path element {i}: {key}")
            if isinstance(current, dict):
                if key not in current:
                    current[key] = {} if isinstance(data_path[i + 1], str) else []
                    print(f"Created new dict/list for key {key}")
                current = current[key]
            elif isinstance(current, list):
                while len(current) <= key:
                    current.append({} if isinstance(data_path[i + 1], str) else [])
                    print(f"Extended list to accommodate index {key}")
                current = current[key]
        
        if data_path:
            if isinstance(current, dict):
                print(f"Setting dict key {data_path[-1]} to {new_value}")
                current[data_path[-1]] = new_value
            elif isinstance(current, list):
                while len(current) <= data_path[-1]:
                    current.append(None)
                    print(f"Extended list to accommodate final index {data_path[-1]}")
                print(f"Setting list index {data_path[-1]} to {new_value}")
                current[data_path[-1]] = new_value

    def on_player_selected(self, player_name: str):
        """Handle player selection from dropdown"""
        if not player_name or not self.current_folder:
            return
            
        # Find and load the selected player file
        player_file = self.current_folder / "entities" / f"{player_name}.player"
        self.load_player_file(player_file) 

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

    def create_research_view(self, research_data: dict) -> QWidget:
        """Create a custom research view that mimics the game's UI"""
        container = QWidget()
        layout = QVBoxLayout(container)
        
        # Create domain selector
        domain_widget = QWidget()
        domain_layout = QHBoxLayout(domain_widget)
        domain_layout.setContentsMargins(0, 0, 0, 10)  # Add some bottom margin

        # Add refresh button on the right side
        refresh_btn = QPushButton()
        refresh_btn.setIcon(QIcon(str(Path(__file__).parent / "icons" / "refresh.png")))
        refresh_btn.setToolTip('Refresh Research View')
        refresh_btn.setFixedSize(18, 18)
        refresh_btn.clicked.connect(lambda: self.refresh_research_view())
        domain_layout.addWidget(refresh_btn)

        # Create research tree view
        tree_view = ResearchTreeView()
        tree_view.node_clicked.connect(self.load_research_subject)
        tree_view.node_delete_requested.connect(lambda subject_id: self.delete_research_subject(subject_id))
        tree_view.add_subject_requested.connect(lambda subject_type: self.add_research_subject(subject_type))
        
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
                                print(f"Loaded background for field {field_id}: {picture}")
        
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
                    elif "hud_icon" in subject_data:
                        pixmap, _ = self.load_texture(subject_data["hud_icon"])
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
                    print(f"Research subject file not found: {subject_file}")
                    return
                    
                # Store initial data in command stack
                self.command_stack.update_file_data(subject_file, subject_data)
            else:
                print(f"Using data from command stack for {subject_file}")
            
            # Clear any existing details
            while self.research_details_layout.count():
                item = self.research_details_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            
            # Create and add the schema view
            schema_view = self.create_schema_view("research-subject", subject_data, is_base_game, subject_file)
            self.research_details_layout.addWidget(schema_view)
            
        except Exception as e:
            print(f"Error loading research subject {subject_id}: {str(e)}")

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
                    print(f"Unit file not found: {unit_file}")
                    return
                    
                # Store initial data in command stack
                self.command_stack.update_file_data(unit_file, unit_data)
            else:
                print(f"Using data from command stack for {unit_file}")
                
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
            print(f"Error loading unit {unit_id}: {str(e)}")
            error_label = QLabel(f"Error loading unit: {str(e)}")
            error_label.setStyleSheet("color: red;")
            self.unit_details_layout.addWidget(error_label)

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
                print(f"Item file not found: {item_file}")
                return
                
            # Clear existing details
            self.clear_layout(self.item_details_layout)
            
            # Create and add the schema view for item details
            schema_view = self.create_schema_view("unit-item", item_data, is_base_game, item_file)
            self.item_details_layout.addWidget(schema_view)
            
        except Exception as e:
            print(f"Error loading item {item_id}: {str(e)}")
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
                print(f"Ability file not found: {ability_file}")
                return
                
            # Clear existing details
            self.clear_layout(self.ability_details_layout)
            
            # Create and add the schema view for ability details
            schema_view = self.create_schema_view("ability", ability_data, is_base_game, ability_file)
            self.ability_details_layout.addWidget(schema_view)
            
        except Exception as e:
            print(f"Error loading ability {ability_id}: {str(e)}")
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
                print(f"Action data source file not found: {action_file}")
                return
                
            # Clear existing details
            self.clear_layout(self.action_details_layout)
            
            # Create and add the schema view for action details
            schema_view = self.create_schema_view("action-data-source", action_data, is_base_game, action_file)
            self.action_details_layout.addWidget(schema_view)
            
        except Exception as e:
            print(f"Error loading action data source {action_id}: {str(e)}")
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
                print(f"Buff file not found: {buff_file}")
                return
                
            # Clear existing details
            self.clear_layout(self.buff_details_layout)
            
            # Create and add the schema view for buff details
            schema_view = self.create_schema_view("buff", buff_data, is_base_game, buff_file)
            self.buff_details_layout.addWidget(schema_view)
            
        except Exception as e:
            print(f"Error loading buff {buff_id}: {str(e)}")
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
                print(f"Formation file not found: {formation_file}")
                return
                
            # Clear existing details
            self.clear_layout(self.formation_details_layout)
            
            # Create and add the schema view for formation details
            schema_view = self.create_schema_view("formation", formation_data, is_base_game, formation_file)
            self.formation_details_layout.addWidget(schema_view)
            
        except Exception as e:
            print(f"Error loading formation {formation_id}: {str(e)}")
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
                print(f"Flight pattern file not found: {pattern_file}")
                return
                
            # Clear existing details
            self.clear_layout(self.pattern_details_layout)
            
            # Create and add the schema view for pattern details
            schema_view = self.create_schema_view("flight-pattern", pattern_data, is_base_game, pattern_file)
            self.pattern_details_layout.addWidget(schema_view)
            
        except Exception as e:
            print(f"Error loading flight pattern {pattern_id}: {str(e)}")
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
                print(f"NPC reward file not found: {reward_file}")
                return
                
            # Clear existing details
            self.clear_layout(self.reward_details_layout)
            
            # Create and add the schema view for reward details
            schema_view = self.create_schema_view("npc-reward", reward_data, is_base_game, reward_file)
            self.reward_details_layout.addWidget(schema_view)
            
        except Exception as e:
            print(f"Error loading NPC reward {reward_id}: {str(e)}")
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
                print(f"Exotic file not found: {exotic_file}")
                return
                
            # Clear existing details
            self.clear_layout(self.exotic_details_layout)
            
            # Create and add the schema view for exotic details
            schema_view = self.create_schema_view("exotic", exotic_data, is_base_game, exotic_file)
            self.exotic_details_layout.addWidget(schema_view)
            
        except Exception as e:
            print(f"Error loading exotic {exotic_id}: {str(e)}")
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
                print(f"Uniform file not found: {uniform_file}")
                return
                
            # Clear existing details
            self.clear_layout(self.uniform_details_layout)
            
            # Create and add the schema view for uniform details
            schema_view = self.create_schema_view("uniform", uniform_data, is_base_game, uniform_file)
            self.uniform_details_layout.addWidget(schema_view)
            
        except Exception as e:
            print(f"Error loading uniform {uniform_id}: {str(e)}")
            error_label = QLabel(f"Error loading uniform: {str(e)}")
            error_label.setStyleSheet("color: red;")
            self.uniform_details_layout.addWidget(error_label)

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
        print(f"Creating schema view for {file_type}")
        print(f"Is base game: {is_base_game}")
        print(f"File path: {file_path}")
        
        # Only initialize command stack data if it doesn't exist
        if file_path is not None and not self.command_stack.get_file_data(file_path):
            self.command_stack.update_file_data(file_path, file_data)
            print(f"Initialized command stack data for {file_path}")
        
        # Get the current data from command stack if available
        display_data = self.command_stack.get_file_data(file_path) if file_path else file_data
        
        # Get the schema name
        if file_type == "uniform":
            # For uniforms, use the file name to determine the schema
            if file_path:
                # Convert from snake_case to kebab-case and append -uniforms-schema
                schema_name = file_path.stem.replace("_", "-") + "-uniforms-schema"
                print(f"Looking for uniform schema: {schema_name}")
            else:
                schema_name = "uniforms-schema"  # Default schema if no file path
        else:
            # Convert from snake_case to kebab-case for schema lookup
            schema_name = file_type.replace("_", "-") + "-schema"
            print(f"Looking for schema: {schema_name}")
            
        if schema_name not in self.schemas:
            print(f"Schema not found for {schema_name}, using generic schema")
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
            self.current_schema = create_schema_for_value(display_data)
        else:
            print(f"Found schema: {schema_name}")
            # Get the schema and resolve any top-level references
            schema = self.schemas[schema_name]
            if isinstance(schema, dict) and "$ref" in schema:
                schema = self.resolve_schema_references(schema)
            self.current_schema = schema
        
        # Create scrollable area for the content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setProperty("file_path", str(file_path) if file_path else None)
        scroll.setProperty("file_type", file_type)
        
        # Create content widget
        content = QWidget()
        main_layout = QVBoxLayout(content)
        main_layout.setSpacing(10)
        
        def update_content(new_data: dict, data_path: List[str] = None, value: Any = None, source_widget = None):
            """Update the content widget with new data"""
            print(f"Updating schema view content for {file_path}")
            print(f"Data path: {data_path}, Source widget: {source_widget}")
            
            # Check if this is an array update by looking at the data at the path
            is_array_update = False
            if data_path:
                # Only treat it as an array update if we're updating the array itself, not an item within it
                if len(data_path) == 1:
                    # For top-level arrays, check if the value is a list
                    is_array_update = isinstance(value, list)
                else:
                    # For nested arrays, check if the parent is a list and we're not updating an item
                    current = new_data
                    for i, key in enumerate(data_path[:-1]):
                        if isinstance(current, dict) and key in current:
                            current = current[key]
                    is_array_update = isinstance(current, list) and isinstance(value, list)

            print(f"Is array update: {is_array_update}")
            
            # Only do a full refresh if we have no data path AND it's not an array update
            should_full_refresh = data_path is None and not is_array_update
            
            if should_full_refresh:
                print("Full refresh")
                # Full update - recreate entire view
                logging.debug("Performing full update")
                
                # Clear existing content
                while main_layout.count():
                    item = main_layout.takeAt(0)
                    if item.widget():
                        item.widget().deleteLater()
                
                # Create the main details widget using the schema
                title = f"{file_type.replace('-', ' ').title()} Details (Base Game)" if is_base_game else f"{file_type.replace('-', ' ').title()} Details"
                print(f"Creating details group with title: {title}")
                details_group = QGroupBox(title)
                if is_base_game:
                    details_group.setStyleSheet("QGroupBox { color: #666666; font-style: italic; }")

                # Create title layout with refresh button
                if file_path:
                    title_layout = QHBoxLayout()
                    title_layout.setContentsMargins(0, 0, 0, 0)
                    title_layout.addStretch()
                    
                    refresh_btn = QPushButton()
                    refresh_btn.setIcon(QIcon(str(Path(__file__).parent / "icons" / "refresh.png")))
                    refresh_btn.setToolTip('Refresh View')
                    refresh_btn.setFixedSize(18, 18)
                    refresh_btn.clicked.connect(lambda: self.refresh_schema_view(file_path))
                    title_layout.addWidget(refresh_btn)
                
                # Create the content widget using the schema, passing an empty path to start tracking
                logging.debug("Creating schema content widget")
                details_widget = self.create_widget_for_schema(new_data, self.current_schema, is_base_game, [])
                details_layout = QVBoxLayout()
                if file_path:
                    details_layout.addLayout(title_layout)
                details_layout.addWidget(details_widget)
                details_group.setLayout(details_layout)
                main_layout.addWidget(details_group)
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
                
                if is_array_update:
                    # Find the array's toggle button
                    array_path = data_path[:-1] if len(data_path) > 1 else data_path
                    array_widget = find_widget_by_path(content, array_path)
                    
                    if array_widget and isinstance(array_widget, QToolButton):
                        # Update the array count in the toggle button
                        array_data = value if len(data_path) == 1 else current
                        prop_name = data_path[-2] if len(data_path) >= 2 else data_path[0]
                        prop_name = prop_name if isinstance(prop_name, str) else f"Item {prop_name}"
                        display_name = f"{prop_name.replace('_', ' ').title()} ({len(array_data)})"
                        array_widget.setText(display_name)
                        
                        # Find the array's content widget (it's the next widget after the button)
                        array_container = array_widget.parent()
                        if array_container:
                            array_layout = array_container.layout()
                            for i in range(array_layout.count()):
                                widget = array_layout.itemAt(i).widget()
                                if widget and widget != array_widget:
                                    # This is the content widget
                                    array_content = widget
                                    array_content_layout = array_content.layout()
                                    if array_content_layout:
                                        return
                                        # Skip widget creation if flag is set
                                        if array_content.property("skip_widget_creation"):
                                            print("Skipping widget creation")

                                            continue
                                        
                                        # Create widget for the new array item
                                        # Get the schema for array items by traversing the schema structure
                                        current_schema = self.current_schema
                                        if len(data_path) == 1:
                                            # For top-level arrays, get the items schema directly
                                            current_schema = current_schema.get("properties", {}).get(data_path[0], {})
                                        else:
                                            # For nested arrays, traverse the schema structure
                                            for key in data_path[:-1]:
                                                if isinstance(current_schema, dict):
                                                    if "properties" in current_schema:
                                                        current_schema = current_schema["properties"].get(key, {})
                                                    elif "items" in current_schema:
                                                        current_schema = current_schema["items"]
                                        
                                        items_schema = current_schema.get("items", {})
                                        if isinstance(items_schema, dict):
                                            # Create widget for the new value
                                            item_path = data_path[:-1] if len(data_path) > 1 else data_path
                                            item_path = item_path + [len(array_data) - 1]  # Add index of new item
                                            new_widget = self.create_widget_for_value(value[-1], items_schema, is_base_game, item_path)
                                            if new_widget:
                                                array_content_layout.addWidget(new_widget)
                                    break
                elif data_path:  # Only do regular value update if we have a data path and it's not an array update
                    # Regular value update
                    target_widget = find_widget_by_path(content, data_path)
                    if target_widget is not None and target_widget is not source_widget:
                        print(f"Found widget to update: {target_widget}")
                        # Update widget value based on its type
                        if isinstance(target_widget, QLineEdit):
                            print(f"Updating QLineEdit with value: {value}")
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
        
        # Initial content update with command stack data
        update_content(display_data)
        
        # Register for data changes if file path is provided
        if file_path is not None:
            self.command_stack.register_data_change_callback(file_path, update_content)
            
            def cleanup():
                self.command_stack.unregister_data_change_callback(file_path, update_content)
            scroll.destroyed.connect(cleanup)
        
        scroll.setWidget(content)
        logging.debug("Finished creating schema view")
        return scroll
    
    def create_widget_for_schema(self, data: dict, schema: dict, is_base_game: bool = False, path: list = None) -> QWidget:
        """Create a widget to display data according to a JSON schema"""
        if path is None:
            path = []
            
        if not schema:
            return QLabel("Invalid schema")
            
        # Handle schema references
        original_schema = schema
        if "$ref" in schema:
            ref_path = schema["$ref"].split("/")[1:]  # Skip the '#'
            current = self.current_schema
            for part in ref_path:
                if part in current:
                    current = current[part]
                else:
                    return QLabel(f"Invalid reference: {schema['$ref']}")
            schema = current
            
        schema_type = schema.get("type")
        if not schema_type:
            return QLabel("Schema missing type")
            
        if schema_type == "object":
            # Create container for object properties
            container = QWidget()
            container_layout = QVBoxLayout(container)
            container_layout.setContentsMargins(0, 0, 0, 0)
            container_layout.setSpacing(0)
            
            # If data is None, create an empty dict with required properties
            if data is None:
                data = self.get_default_value(schema)
            
            # Sort properties alphabetically but prioritize common fields
            priority_fields = ["name", "description", "id", "type", "version"]
            properties = schema.get("properties", {}).items()
            sorted_properties = sorted(properties, 
                                    key=lambda x: (x[0] not in priority_fields, x[0].lower()))
            
            # Add required properties first if they don't exist in data
            required_props = schema.get("required", [])
            for prop_name in required_props:
                if prop_name not in data and prop_name in schema.get("properties", {}):
                    data[prop_name] = self.get_default_value(schema["properties"][prop_name])
            
            for prop_name, prop_schema in sorted_properties:
                # For new objects, show all required properties and existing properties
                if prop_name in data or prop_name in required_props:
                    value = data.get(prop_name, self.get_default_value(prop_schema))
                    
                    # Check if this is a simple value or array of simple values
                    is_simple_value = isinstance(value, (str, int, float, bool))
                    # Update path for this property
                    prop_path = path + [prop_name]
                    
                    # Create widget for the property with updated path
                    widget = self.create_widget_for_property(
                        prop_name, value, prop_schema, is_base_game, prop_path
                    )
                    if widget:
                        if is_simple_value:
                            # Create simple label and value layout for primitive types
                            row_widget = QWidget()
                            row_layout = QHBoxLayout(row_widget)
                            row_layout.setContentsMargins(0, 2, 0, 2)  # Add small vertical spacing
                            
                            label = QLabel(prop_name.replace("_", " ").title() + ":")
                            # Make label bold if property is required
                            if prop_name in required_props:
                                label.setStyleSheet("QLabel { font-weight: bold; }")
                            
                            # Add context menu to label
                            label.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
                            label.setProperty("data_path", prop_path)
                            label.customContextMenuRequested.connect(
                                lambda pos, w=label, v=value: self.show_context_menu(w, pos, v)
                            )
                            
                            row_layout.addWidget(label)
                            row_layout.addWidget(widget)
                            row_layout.addStretch()
                            
                            container_layout.addWidget(row_widget)
                        elif isinstance(value, list):
                            # For arrays, just add the widget directly (it will create its own header)
                            container_layout.addWidget(widget)
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
                            
                            # Make button bold if property is required
                            if prop_name in required_props:
                                toggle_btn.setStyleSheet("QToolButton { border: none; font-weight: bold; }")
                            
                            # Store object data and path for context menu
                            toggle_btn.setProperty("data_path", prop_path)
                            toggle_btn.setProperty("original_value", value)
                            
                            # Add context menu to the button
                            toggle_btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
                            toggle_btn.customContextMenuRequested.connect(
                                lambda pos, w=toggle_btn, v=value: self.show_context_menu(w, pos, v)
                            )
                            
                            # Create content widget
                            content = QWidget()
                            content_layout = QVBoxLayout(content)
                            content_layout.setContentsMargins(20, 0, 0, 0)
                            content_layout.addWidget(widget)
                            
                            content.setVisible(False)  # Initially collapsed
                            
                            def update_arrow_state(checked, btn=toggle_btn):
                                btn.setArrowType(Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow)
                            
                            toggle_btn.toggled.connect(content.setVisible)
                            toggle_btn.toggled.connect(update_arrow_state)
                            
                            group_layout.addWidget(toggle_btn)
                            group_layout.addWidget(content)
                            container_layout.addWidget(group_widget)
            
            # For top-level objects, add context menu to the container itself
            if not path:
                container.setProperty("data_path", path)
                container.setProperty("original_value", data)
                container.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
                container.customContextMenuRequested.connect(
                    lambda pos, w=container, v=data: self.show_context_menu(w, pos, v)
                )
            
            return container
            
        elif schema_type == "array":
            # Create collapsible container for the entire array
            container = QWidget()
            container_layout = QVBoxLayout(container)
            container_layout.setContentsMargins(0, 0, 0, 0)
            container_layout.setSpacing(0)
            
            # Create collapsible button for the array
            toggle_btn = QToolButton()
            toggle_btn.setStyleSheet("QToolButton { border: none; }")
            toggle_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            toggle_btn.setArrowType(Qt.ArrowType.RightArrow)
            # Get property name from path
            prop_name = path[-1] if path else "Items"
            # Format as "Property Name (X)"
            if isinstance(prop_name, str):
                display_name = f"{prop_name.replace('_', ' ').title()} ({len(data)})"
            else:
                display_name = f"Item {prop_name} ({len(data)})"
            toggle_btn.setText(display_name)
            toggle_btn.setCheckable(True)
            
            # Store array data and path for context menu
            toggle_btn.setProperty("data_path", path)
            toggle_btn.setProperty("original_value", data)

            # Add context menu to the button
            toggle_btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            toggle_btn.customContextMenuRequested.connect(
                lambda pos, w=toggle_btn: self.show_context_menu(w, pos, data)
            )
            
            container_layout.addWidget(toggle_btn)
            
            # Create content widget for array items
            content = QWidget()
            content_layout = QVBoxLayout(content)
            content_layout.setContentsMargins(20, 0, 0, 0)  # Add left margin for indentation
            content_layout.setSpacing(0)
            content_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)  # Align content to the left and top
            content.setVisible(False)  # Initially collapsed
            
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
                        
                        # Add index label before each item
                        item_container = QWidget()
                        item_layout = QHBoxLayout(item_container)
                        item_layout.setContentsMargins(0, 0, 0, 0)
                        item_layout.setSpacing(4)
                        item_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)  # Align items to the left
                        
                        # Add index label with context menu
                        index_label = QLabel(f"[{i}]")
                        index_label.setStyleSheet("QLabel { color: gray; }")
                        index_label.setProperty("data_path", item_path)
                        index_label.setProperty("array_data", data)
                        
                        # Only add context menu if there's more than one item
                        if len(data) > 1:
                            index_label.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
                            index_label.customContextMenuRequested.connect(
                                lambda pos, w=index_label: self.show_array_item_menu(w, pos)
                            )
                        
                        item_layout.addWidget(index_label)
                        item_layout.addWidget(widget)
                        content_layout.addWidget(item_container)
                else:
                    # For complex arrays, show each item with its index
                    for i, item in enumerate(data):
                        # Update path for this array item
                        item_path = path + [i]
                        widget = self.create_widget_for_schema(
                            item, items_schema, is_base_game, item_path
                        )
                        if widget:
                            # Add index label before each item
                            item_container = QWidget()
                            item_layout = QHBoxLayout(item_container)
                            item_layout.setContentsMargins(0, 0, 0, 0)
                            item_layout.setSpacing(4)
                            item_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)  # Align items to the left
                            
                            # Add index label with context menu
                            index_label = QLabel(f"[{i}]")
                            index_label.setStyleSheet("QLabel { color: gray; }")
                            index_label.setProperty("data_path", item_path)
                            index_label.setProperty("array_data", data)
                            
                            # Only add context menu if there's more than one item
                            if len(data) > 1:
                                index_label.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
                                index_label.customContextMenuRequested.connect(
                                    lambda pos, w=index_label: self.show_array_item_menu(w, pos)
                                )
                            
                            item_layout.addWidget(index_label)
                            item_layout.addWidget(widget)
                            content_layout.addWidget(item_container)
            
            def update_arrow_state(checked):
                toggle_btn.setArrowType(Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow)
            
            toggle_btn.toggled.connect(content.setVisible)
            toggle_btn.toggled.connect(update_arrow_state)
            
            container_layout.addWidget(content)
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
        elif not isinstance(path, (list, tuple)):
            path = [path]
        path = list(path)  # Convert to list if it's a tuple
            
        print(f"create_widget_for_value called with:")
        print(f"  value: {value}")
        print(f"  schema: {schema}")
        print(f"  path: {path}")
        
        # Get the current file path from the parent schema view
        file_path = None
        parent_view = self.find_parent_schema_view(self)
        if parent_view:
            file_path = getattr(parent_view, 'file_path', None)
            
        # Get current value from command stack if available
        current_value = self.get_current_value_from_command_stack(file_path, path, value)

        # Handle different schema types
        schema_type = schema.get("type")
        
        if schema_type == "string":
            # Convert value to string if it's not already
            value_str = str(current_value) if current_value is not None else "ERROR: No value"

            # Get property name from the path - use the last string in the path
            property_name = next((p for p in reversed(path) if isinstance(p, str)), "").lower()
            print(f"Extracted property_name from path: {property_name}")
            
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
                "item": "unit_item",
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
                
                print(f"Processing array with schema: {schema}")
                
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
                                        
                                    print(f"Creating widget for array item with key: {key}")
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
                        print(f"Creating widget for simple array item with parent property: {parent_property}")
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
            print(f"Checking for {value_str} in manifest type {property_name}")
            
            # Check if the property name maps to a known entity type
            if property_name in manifest_type_map:
                print(f"Found manifest type mapping: {property_name} -> {manifest_type_map[property_name]}")
                expected_type = manifest_type_map[property_name]
                print(f"Checking for {value_str} in manifest type {expected_type}")
                # Only check the expected type based on property name
                if (value_str in self.manifest_data['mod'].get(expected_type, {}) or 
                    value_str in self.manifest_data['base_game'].get(expected_type, {})):
                    entity_type = expected_type
                    print(f"Found {value_str} in manifest {expected_type}")
                else:
                    # If not found in the expected type, log a warning
                    print(f"Referenced {expected_type} not found: {value_str}")
                    # Don't search other manifests if we have a specific type
                    return QLabel(value_str)
            else:
                # Only search all manifests if no specific type is mapped
                print(f"Checking all manifests for {value_str}")
                for manifest_type, manifest_data in self.manifest_data['mod'].items():
                    if value_str in manifest_data:
                        print(f"Found {value_str} in mod manifest {manifest_type}")
                        entity_type = manifest_type
                        break
                if not entity_type:
                    for manifest_type, manifest_data in self.manifest_data['base_game'].items():
                        if value_str in manifest_data:
                            print(f"Found {value_str} in base game manifest {manifest_type}")
                            entity_type = manifest_type
                            break
            
            if entity_type:
                print(f"Creating button for {value_str} of type {entity_type}")
                btn = QPushButton(value_str)
                btn.setStyleSheet("text-align: left; padding: 2px;")

                # Add context menu
                btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
                btn.customContextMenuRequested.connect(
                    lambda pos, w=btn, v=value_str: self.show_context_menu(w, pos, v)
                )

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

                btn.setStyleSheet("font-style: italic;")
                
                if is_base_game:
                    btn.setStyleSheet(btn.styleSheet() + "; color: #666666;")
                
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
                print(f"Found localized text in mod {self.current_language}: {localized_text}")
            elif "en" in self.all_localized_strings['mod'] and value_str in self.all_localized_strings['mod']["en"]:
                is_localized_key = True
                localized_text = self.all_localized_strings['mod']["en"][value_str]
                is_base = False
                print(f"Found localized text in mod en: {localized_text}")
            # Try base game strings
            elif self.current_language in self.all_localized_strings['base_game'] and value_str in self.all_localized_strings['base_game'][self.current_language]:
                is_localized_key = True
                localized_text = self.all_localized_strings['base_game'][self.current_language][value_str]
                is_base = True
                print(f"Found localized text in base game {self.current_language}: {localized_text}")
            elif "en" in self.all_localized_strings['base_game'] and value_str in self.all_localized_strings['base_game']["en"]:
                is_localized_key = True
                localized_text = self.all_localized_strings['base_game']["en"][value_str]
                is_base = True
                print(f"Found localized text in base game en: {localized_text}")
            
            if is_localized_key:
                print(f"Creating localized text widget for key: {value_str}")
                # Create a container with both localized text and editable fields
                container = QWidget()
                layout = QVBoxLayout(container)
                layout.setContentsMargins(0, 0, 0, 0)
                layout.setSpacing(4)
                
                # Add editable field for the key
                print(f"Creating key edit for: {value_str}")
                key_edit = QLineEdit(value_str)
                key_edit.textChanged.connect(lambda text: self.on_text_changed(key_edit, text))
                key_edit.setProperty("data_path", path)
                key_edit.setProperty("original_value", value)
                key_edit.setStyleSheet("font-style: italic;")
                layout.addWidget(key_edit)

                # Add context menu
                key_edit.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
                key_edit.customContextMenuRequested.connect(
                    lambda pos, w=key_edit, v=value_str: self.show_context_menu(w, pos, v)
                )
                # Style key if from base game
                if is_base:
                    key_edit.setStyleSheet("font-style: italic;")

                # Make key non-editable if base game
                if is_base_game:
                    key_edit.setReadOnly(True)
                    key_edit.setStyleSheet("color: #666666;")
                
                # Get the current value from command stack if available
                text_file = self.current_folder / "localized_text" / f"{self.current_language}.localized_text"
                current_text = localized_text
                if self.command_stack.get_file_data(text_file):

                    current_text = self.command_stack.get_file_data(text_file).get(value_str, localized_text)
                
                # Add editable field for the text
                text_edit = QPlainTextEdit()
                text_edit.setPlainText(current_text)
                text_edit.setPlaceholderText("Enter translation...")
                text_edit.setProperty("localized_key", value_str)
                text_edit.setProperty("language", self.current_language)
                text_edit.setProperty("original_value", current_text)
                text_edit.setProperty("is_updating", False)
                
                def on_text_changed():
                    if not text_edit.property("is_updating"):
                        self.current_text_edit = text_edit
                        self.text_edit_timer.start()
                
                text_edit.textChanged.connect(on_text_changed)
                
                # Set a fixed height of 3 lines to make it compact but still show multiple lines
                font_metrics = text_edit.fontMetrics()
                line_spacing = font_metrics.lineSpacing()
                text_edit.setFixedHeight(line_spacing * 3 + 10)  # 3 lines + some padding
                
                layout.addWidget(text_edit)

                # Make text non-editable if base game
                if is_base:
                    text_edit.setStyleSheet("color: #666666")
                    text_edit.setReadOnly(True)
                
                # Store the text file path in the container for updates
                container.setProperty("text_file_path", str(text_file))
                container.setProperty("data_path", path)
                container.setProperty("original_value", value)
                
                # Register for command stack updates
                if not is_base and text_file is not None:
                    def update_text(new_data: dict, data_path: List[str] = None, value: Any = None, source_widget = None):
                        if source_widget != text_edit:  # Only update if change came from another widget
                            current_key = text_edit.property("localized_key")
                            if current_key in new_data:
                                self.update_text_preserve_cursor(text_edit, new_data[current_key])
                    
                    self.command_stack.register_data_change_callback(text_file, update_text)
                    container.destroyed.connect(
                        lambda: self.command_stack.unregister_data_change_callback(text_file, update_text)
                    )
                
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
                    print(f"Creating texture edit for: {value_str}")
                    edit = QLineEdit(value_str)
                    edit.textChanged.connect(lambda text: self.on_text_changed(edit, text))
                    edit.setProperty("data_path", path)
                    edit.setProperty("original_value", value)
                    edit.setStyleSheet("font-style: italic;")
                    layout.addWidget(edit)
                
                    # Add context menu
                    edit.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
                    edit.customContextMenuRequested.connect(
                        lambda pos, w=edit, v=value_str: self.show_context_menu(w, pos, v)
                    )
                
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
                
                # Install wheel event filter
                combo.installEventFilter(self.wheel_filter)
                
                # Store path and original value
                combo.setProperty("data_path", path)
                combo.setProperty("original_value", value)
                return combo

            # Handle all other values
            else:
                print(f"Creating edit for: {value_str}")
                edit = QLineEdit(value_str)
                if is_base_game:
                    edit.setStyleSheet("color: #666666; font-style: italic;")
                    edit.setReadOnly(True)
                else:
                    # Connect text changed signal to command creation
                    edit.textChanged.connect(lambda text: self.on_text_changed(edit, text))
                    
                    # Add context menu
                    edit.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
                    edit.customContextMenuRequested.connect(
                        lambda pos, w=edit, v=value_str: self.show_context_menu(w, pos, v)
                    )
                
                # Store path and original value
                edit.setProperty("data_path", path)
                edit.setProperty("original_value", value)
                return edit
                
        elif schema_type == "integer":
            spin = QSpinBox()
            spin.setValue(int(current_value) if current_value is not None else 0)
            
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
            
            # Install wheel event filter
            spin.installEventFilter(self.wheel_filter)
            
            # Store path and original value
            spin.setProperty("data_path", path)
            spin.setProperty("original_value", current_value)
            return spin
            
        elif schema_type == "number":
            spin = QDoubleSpinBox()
            
            # Convert value to float, handling scientific notation
            try:
                float_value = float(current_value) if current_value is not None else 0.0
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
            
            # Install wheel event filter
            spin.installEventFilter(self.wheel_filter)
            
            # Store path and original value
            spin.setProperty("data_path", path)
            spin.setProperty("original_value", current_value)
            return spin
            
        elif schema_type == "boolean":
            checkbox = QCheckBox()
            checkbox.setChecked(bool(current_value))
            if is_base_game:
                checkbox.setStyleSheet("color: #666666; font-style: italic;")
                checkbox.setEnabled(False)  # Disable checkbox for base game content
            else:
                # Connect stateChanged signal to command creation
                checkbox.stateChanged.connect(lambda state: self.on_checkbox_changed(checkbox, state))
            
            # Store path and original value
            checkbox.setProperty("data_path", path)
            checkbox.setProperty("original_value", current_value)
            return checkbox
            
        elif schema_type == "object":
            # For objects, create a widget that shows the object's structure
            group = QGroupBox()
            layout = QVBoxLayout()
            for key, val in current_value.items():
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
            group.setProperty("original_value", current_value)
            return group
            
        else:
            return None
            # Fallback for unknown types
            print(f"Creating edit for unknown type: {value}")
            edit = QLineEdit(str(value))
            if is_base_game:
                edit.setStyleSheet("color: #666666; font-style: italic;")
                edit.setReadOnly(True)
            
            # Store path and original value
            edit.setProperty("data_path", path)
            edit.setProperty("original_value", value)

            # Add context menu
            edit.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            edit.customContextMenuRequested.connect(
                lambda pos, w=edit, v=value: self.show_context_menu(w, pos, v)
            )
            
            return edit

    def load_referenced_entity(self, entity_id: str, entity_type: str):
        """Load a referenced entity file and display it in the appropriate panel"""
        if not isinstance(entity_id, str):
            print(f"Invalid entity_id type: {type(entity_id)}. Expected string.")
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
                print(f"Using data from command stack for {entity_file}")
                is_base_game = False
            else:
                # Try mod folder first
                if entity_file.exists():
                    print(f"Loading referenced entity from mod folder: {entity_file}")
                    with open(entity_file, 'r', encoding='utf-8') as f:
                        entity_data = json.load(f)
                        is_base_game = False
                    print(f"Successfully loaded data for {entity_file}")
                    print(f"Initial data for {entity_file}: {entity_data}")
                
                # Try base game folder if not found in mod folder
                elif self.base_game_folder:
                    base_game_file = self.base_game_folder / "entities" / f"{entity_id}.{entity_type}"
                    if base_game_file.exists():
                        print(f"Loading referenced entity from base game: {base_game_file}")
                        with open(base_game_file, 'r', encoding='utf-8') as f:
                            entity_data = json.load(f)
                            is_base_game = True
                        entity_file = base_game_file
                        print(f"Successfully loaded base game data for {entity_file}")
                        print(f"Initial base game data for {entity_file}: {entity_data}")
                
            if not entity_data:
                error_msg = f"Could not find {entity_type} file: {entity_id}\n\n"
                if not self.base_game_folder:
                    error_msg += "Note: Base game folder is not configured. Some references may not be found."
                else:
                    error_msg += f"Looked in:\n- {entity_file}\n- {self.base_game_folder}/entities/{entity_id}.{entity_type}"
                QMessageBox.warning(self, "Error", error_msg)
                print(f"{entity_type} file not found: {entity_id}")
                return
                
            # Store data in command stack if it wasn't already there
            if entity_file not in self.command_stack.file_data:
                print(f"Storing initial data in command stack for {entity_file}")
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
                print(f"Created weapon schema view for {entity_file}")

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
                print(f"Created unit skin schema view for {entity_file}")
                
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
                print(f"Created ability schema view for {entity_file}")
                
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
                print(f"Unknown entity type: {entity_type}")
                return
                
        except Exception as e:
            error_msg = f"Error loading {entity_type} file {entity_id}:\n{str(e)}"
            QMessageBox.warning(self, "Error", error_msg)
            print(f"Error loading {entity_type} file {entity_id}: {str(e)}")
            return
    
    def get_schema_for_path(self, path: list) -> dict:
        """Get the schema for a specific data path"""
        if not self.current_schema:
            print("No current schema available")
            return None
            
        # For empty path (top-level object), return the current schema
        if not path:
            return self.current_schema
            
        schema = self.current_schema
        for part in path:
            if not schema:
                print(f"Schema is None while processing path part: {part}")
                return None
                
            # Resolve any references in the current schema
            if isinstance(schema, dict):
                if "$ref" in schema:
                    # Resolve reference
                    ref_path = schema["$ref"].split("/")[1:]
                    current = self.current_schema
                    for ref_part in ref_path:
                        if ref_part in current:
                            current = current[ref_part]
                        else:
                            return None
                    schema = current
                
                if isinstance(part, str):
                    # Object property
                    if "properties" in schema and part in schema["properties"]:
                        schema = schema["properties"][part]
                    else:
                        return None
                elif isinstance(part, int):
                    # Array index - get the items schema
                    if "items" in schema:
                        schema = schema["items"]
                        # Resolve any references in the items schema
                        if isinstance(schema, dict) and "$ref" in schema:
                            ref_path = schema["$ref"].split("/")[1:]
                            current = self.current_schema
                            for ref_part in ref_path:
                                if ref_part in current:
                                    current = current[ref_part]
                                else:
                                    return None
                            schema = current
                    else:
                        return None
                        
        return schema

    def get_default_value(self, schema: dict) -> any:
        """Get a default value for a schema"""
        # Resolve any references first
        schema = self.resolve_schema_references(schema)
        
        if not schema:
            return None
            
        schema_type = schema.get("type")
        
        if schema_type == "string":
            if "enum" in schema:
                return schema["enum"][0]  # Return first enum value
            return ""
            
        elif schema_type == "number":
            if "minimum" in schema:
                return schema["minimum"]
            return 0.0
            
        elif schema_type == "integer":
            if "minimum" in schema:
                return schema["minimum"]
            return 0
            
        elif schema_type == "boolean":
            return False
            
        elif schema_type == "array":
            # Get the schema for array items
            items_schema = schema.get("items", {})
            min_items = schema.get("minItems", 1)  # Default to 1 item if not specified
            max_items = schema.get("maxItems", None)  # No max by default
            
            if items_schema:
                # Create the minimum required number of items
                default_items = []
                for _ in range(min_items):
                    default_item = self.get_default_value(items_schema)
                    default_items.append(default_item)
                return default_items
            return [""]  # Fallback for arrays with no items schema
            
        elif schema_type == "object":
            # Create object with all required properties
            result = {}
            properties = schema.get("properties", {})
            required = schema.get("required", [])
            
            # Add all required properties with their default values
            for prop_name in required:
                if prop_name in properties:
                    prop_schema = self.resolve_schema_references(properties[prop_name])
                    result[prop_name] = self.get_default_value(prop_schema)
            
            # If unevaluatedProperties is false, add all optional properties too
            if schema.get("unevaluatedProperties") is False:
                for prop_name, prop_schema in properties.items():
                    if prop_name not in result:
                        prop_schema = self.resolve_schema_references(prop_schema)
                        result[prop_name] = self.get_default_value(prop_schema)
            
            return result
            
        return None

    def resolve_schema_references(self, schema: dict) -> dict:
        """Resolve schema references recursively"""
        if not schema:
            return schema
            
        if "$ref" in schema:
            ref_path = schema["$ref"].split("/")[1:]  # Skip the first '#' element
            # Find the referenced schema in the loaded schemas
            for loaded_schema in self.schemas.values():
                try:
                    resolved = loaded_schema
                    for part in ref_path:
                        resolved = resolved[part]
                    # Merge any additional properties from the original schema
                    resolved = {**resolved, **{k: v for k, v in schema.items() if k != "$ref"}}
                    return resolved
                except (KeyError, TypeError):
                    continue
            # If we get here, we couldn't resolve the reference
            print(f"Warning: Could not resolve schema reference: {schema['$ref']}")
            return schema
            
        # Handle nested objects
        if "properties" in schema:
            resolved_props = {}
            for prop_name, prop_schema in schema["properties"].items():
                resolved_props[prop_name] = self.resolve_schema_references(prop_schema)
            schema["properties"] = resolved_props
            
        # Handle arrays
        if "items" in schema:
            schema["items"] = self.resolve_schema_references(schema["items"])
            
        return schema

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

    def find_parent_schema_view(self, widget: QWidget) -> QWidget:
        """Find the parent schema view widget that contains the file path"""
        current = widget
        while current:
            if hasattr(current, 'file_path'):
                return current
            current = current.parent()
        return None

    def refresh_schema_view(self, file_path: Path):
        """Refresh the schema view for a file"""
        # Get the current data
        data = self.command_stack.get_file_data(file_path)
        if isinstance(data, (Path, str)):  # If data is a path (like for root properties), load the actual data
            data = self.old_value  # Use the backed up data from the command

        if not data:
            return
            
        # Find the schema view widget
        schema_view = None
        for widget in self.findChildren(QWidget):
            if (hasattr(widget, 'property') and 
                widget.property("file_path") == str(file_path)):
                schema_view = widget
                break
        
        if schema_view and schema_view.parent() and schema_view.parent().layout():
            # Get the schema type from the file extension
            schema_type = file_path.suffix[1:]  # Remove the dot
            
            # Create new schema view
            new_view = self.create_schema_view(
                schema_type,
                data,
                False,  # is_base_game
                file_path
            )
            
            # Replace old view with new one
            parent = schema_view.parent()
            layout = parent.layout()
            layout.replaceWidget(schema_view, new_view)
            schema_view.deleteLater()

    def refresh_research_view(self):
        """Refresh the research view with current data"""
        if not self.current_folder or not self.current_data or "research" not in self.current_data:
            return
            
        # Find the current research view
        current_view = None
        if self.research_layout.count() > 0:
            container = self.research_layout.itemAt(0).widget()
            # Find the ResearchTreeView within the container
            for child in container.findChildren(ResearchTreeView):
                current_view = child
                break
                
        if not current_view:
            return
            
        # Store current view state
        viewport_center = current_view.mapToScene(current_view.viewport().rect().center())
        current_zoom = current_view.transform().m11()
        current_domain = current_view.current_domain
        
        # Clear existing nodes but keep the view
        for node in list(current_view.nodes.values()):
            current_view.scene.removeItem(node)
        current_view.nodes.clear()
        current_view.nodes_by_field.clear()
        current_view.field_max_rows.clear()
        current_view.domains.clear()
        current_view.fields_by_domain.clear()
        
        # Clear all scene items (nodes, lines, text, etc.)
        for item in list(current_view.scene.items()):
            current_view.scene.removeItem(item)
            
        # Re-add tier headers and grid lines
        current_view.add_tier_headers()
        
        # Load field backgrounds from research data
        field_backgrounds = {}
        if "research_domains" in self.current_data["research"]:
            for domain_name, domain_data in self.current_data["research"]["research_domains"].items():
                if "research_fields" in domain_data:
                    for field_data in domain_data["research_fields"]:
                        field_id = field_data.get("id")
                        picture = field_data.get("picture")
                        if field_id and picture:
                            pixmap, is_base_game = self.load_texture(picture)
                            if not pixmap.isNull():
                                field_backgrounds[field_id] = pixmap
        
        # Set field backgrounds in tree view
        current_view.set_field_backgrounds(field_backgrounds)
        
        # Add research subjects to the view
        if "research_subjects" in self.current_data["research"]:
            # First pass: collect all subjects and sort by tier
            subjects_by_tier = {}
            for subject_id in self.current_data["research"]["research_subjects"]:
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
                    elif "hud_icon" in subject_data:
                        pixmap, _ = self.load_texture(subject_data["hud_icon"])
                        if not pixmap.isNull():
                            icon = pixmap
                    
                    field = subject_data.get("field", "")
                    field_coord = subject_data.get("field_coord")
                    
                    current_view.add_research_subject(
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
        
        # Restore view state
        if current_domain in current_view.domains:
            current_view.last_viewport_center = viewport_center
            current_view.set_domain(current_domain)
            current_view.scale(current_zoom / current_view.transform().m11(), current_zoom / current_view.transform().m11())

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

        def set_text_and_preserve_cursor(widget: QLineEdit, value: str):
            cursor_pos = widget.cursorPosition()
            widget.setText(str(value) if value is not None else "")
            widget.setCursorPosition(cursor_pos)
        
        print(f"data_path: {data_path}, old_value_str: {old_value_str}, new_text: {new_text}")
        if data_path is not None and old_value_str != new_text:

            command = EditValueCommand(
                file_path,
                data_path,
                old_value,
                new_text,
                lambda value: set_text_and_preserve_cursor(widget, value),
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
        
        # Simplify the number if possible
        if isinstance(new_value, (int, float)):
            new_value = self.simplify_number(new_value)
        
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

    def on_text_edit_timer_timeout(self):
        if self.current_text_edit and not self.current_text_edit.property("is_updating"):
            self.on_localized_text_changed(self.current_text_edit, self.current_text_edit.toPlainText())

    def on_select_value(self, target_widget, new_value):
        """Handle selection from any selector dialog"""
        data_path = target_widget.property("data_path")
        old_value = target_widget.property("original_value")
        file_path = self.get_schema_view_file_path(target_widget)
        
        if data_path is not None and old_value != new_value and file_path:
            # Create value update command
            value_cmd = EditValueCommand(
                file_path,
                data_path,
                old_value,
                new_value,
                lambda v: self.update_text_preserve_cursor(target_widget, str(v)) if isinstance(target_widget, QPlainTextEdit) else target_widget.setText(str(v)),
                self.update_data_value
            )
            value_cmd.source_widget = target_widget
            
            # For uniforms, we only need to update the value
            if isinstance(target_widget, QLineEdit) and target_widget.property("is_uniform"):
                self.command_stack.push(value_cmd)
            else:
                # For other types, we need to transform the widget
                transform_cmd = TransformWidgetCommand(self, target_widget, old_value, new_value)
                composite_cmd = CompositeCommand([value_cmd, transform_cmd])
                self.command_stack.push(composite_cmd)
            
            self.update_save_button()

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

    def on_localized_text_changed(self, edit: QPlainTextEdit, text: str):
        """Handle changes to localized text values"""
        if not self.current_folder:
            return
            
        # Get the key and language from the widget's properties
        key = edit.property("localized_key")
        language = edit.property("language")
        if not key or not language:
            return
            
        # Get the localized text file path
        text_file = self.current_folder / "localized_text" / f"{language}.localized_text"
        
        # Get the current data from the file
        try:
            with open(text_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception:
            data = {}
            
        # Initialize command stack data if needed
        if not self.command_stack.get_file_data(text_file):
            self.command_stack.update_file_data(text_file, data)
        
        # Create a command to update the text
        old_value = data.get(key, "")
        if old_value != text:
            command = EditValueCommand(
                text_file,
                [key],  # The path is just the key since it's a flat dictionary
                old_value,
                text,
                lambda value: self.update_text_preserve_cursor(edit, value),
                lambda path, value: self.update_localized_text_in_memory(text_file, path[0], value)
            )
            command.source_widget = edit
            self.command_stack.push(command)
            self.update_save_button()
            
            # Update the in-memory strings
            if language not in self.all_localized_strings['mod']:
                self.all_localized_strings['mod'][language] = {}
            self.all_localized_strings['mod'][language][key] = text
            
    def update_text_preserve_cursor(self, edit: QPlainTextEdit, value: str):
        """Update text in QPlainTextEdit while preserving cursor position and selection"""
        edit.setProperty("is_updating", True)  # Set flag before update
        cursor = edit.textCursor()
        position = cursor.position()
        anchor = cursor.anchor()
        
        # Block signals to prevent recursive updates
        edit.blockSignals(True)
        edit.setPlainText(value)
        edit.blockSignals(False)
        
        # Restore cursor and selection
        cursor = edit.textCursor()
        cursor.setPosition(anchor)
        if anchor != position:
            cursor.setPosition(position, cursor.MoveMode.KeepAnchor)
        edit.setTextCursor(cursor)
        edit.setProperty("is_updating", False)  # Clear flag after update

    def update_localized_text_in_memory(self, file_path: Path, key: str, value: str):
        """Update a value in memory only, actual file write happens during save"""
        try:
            # Get current data from command stack
            data = self.command_stack.get_file_data(file_path)
            if not data:
                # If no data in command stack, read from file
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                except Exception:
                    data = {}
                self.command_stack.update_file_data(file_path, data)
            
            # Update the value in memory only
            data[key] = value
            self.command_stack.update_file_data(file_path, data)
            
            print(f"Updated localized text {key} in memory")
            print(f"New value: {value}")
        except Exception as e:
            print(f"Error updating localized text in memory: {str(e)}")

    def add_property(self, widget: QWidget, prop_name: str, prop_schema: dict):
        """Add a new property to an object"""
        # Get file path from parent schema view
        file_path = self.get_schema_view_file_path(widget)
        if not file_path:
            return
            
        data_path = widget.property("data_path")
        if data_path is None:
            data_path = []  # Empty list for root properties
            
        # Get current data from command stack
        current_data = self.command_stack.get_file_data(file_path)
        if not current_data:
            with open(file_path, 'r', encoding='utf-8') as f:
                current_data = json.load(f)
                
        # Navigate to the target object
        target = current_data
        if data_path:  # Only navigate if we have a path
            for part in data_path:
                target = target[part]
            
        if not isinstance(target, dict):
            return
            
        # Schema references are already resolved when passed in from create_context_menu
        # Create default value for the new property
        default_value = self.get_default_value(prop_schema)
        
        # Create old and new values for the object
        if not data_path:
            # For root properties, we need to store the entire data structure
            old_value = current_data.copy()  # Store the data before adding the property
            new_value = current_data.copy()  # Make a new copy for the modified data
            new_value[prop_name] = default_value  # Add the new property
        else:
            # For nested properties, we only need to store the target object
            old_value = target.copy()  # Store the object before adding the property
            new_value = target.copy()  # Make a new copy for the modified data
            new_value[prop_name] = default_value  # Add the new property
        
        # Find the content widget (next widget after the toggle button)
        container = widget.parent()
        content_widget = None
        if container:
            container_layout = container.layout()
            for i in range(container_layout.count()):
                item_widget = container_layout.itemAt(i).widget()
                if item_widget and item_widget != widget:
                    content_widget = item_widget
                    break
                    
        # If we can't find the content widget through normal means (like for root properties)
        # use the widget itself as the content widget
        if not content_widget:
            content_widget = widget
        
        if content_widget and (content_widget.layout() or content_widget == widget):
            # Create transform command for the new property
            transform_cmd = AddPropertyCommand(
                self,
                content_widget,  # Pass content_widget instead of widget
                old_value,
                new_value
            )
            # Add required attributes to transform command
            transform_cmd.file_path = file_path
            transform_cmd.data_path = data_path
            transform_cmd.source_widget = widget
            transform_cmd.schema = prop_schema
            transform_cmd.prop_name = prop_name
            
            self.command_stack.push(transform_cmd)
            self.update_save_button()
            
            # # For root properties, refresh the entire schema view
            # if not data_path:
            #     self.refresh_schema_view(file_path)

    def delete_property(self, widget: QWidget, property_name: str):
        """Delete a property from an object"""
        try:
            print(f"Starting delete_property for {property_name}")
            # Get the data path
            data_path = widget.property("data_path")
            print(f"Data path from widget: {data_path}")
            if data_path is None:  # Changed from 'if not data_path:' to handle empty lists
                print("No data path found on widget")
                return
                
            # Get the parent widget (where we'll remove this property from)
            parent_widget = None
            if isinstance(widget, QToolButton):
                # For collapsible sections, widget is the toggle button
                parent_widget = widget.parent()
                print("Widget is a QToolButton, using parent")
            else:
                # For simple properties, widget is the value widget
                parent_widget = widget.parent()
                print("Widget is not a QToolButton, using parent")
            
            if not parent_widget:
                print("No parent widget found")
                return
                
            # Get the current data
            file_path = self.get_schema_view_file_path(widget)
            print(f"File path: {file_path}")
            if not file_path:
                print("No file path found")
                return
                
            parent_data = self.command_stack.get_file_data(file_path)
            print(f"Got parent data: {parent_data is not None}")
            if not parent_data:
                print("No parent data found")
                return
                
            # Navigate to the parent object
            current = parent_data
            if len(data_path) > 1:  # If not a root property
                print(f"Navigating to parent object through path: {data_path[:-1]}")
                for key in data_path[:-1]:  # Exclude property name
                    if isinstance(current, dict):
                        current = current.get(key, {})
                    elif isinstance(current, list):
                        current = current[key] if 0 <= key < len(current) else {}
                    print(f"Current object after key {key}: {current}")
            
            # Create and execute the delete command
            print("Creating DeletePropertyCommand")
            command = DeletePropertyCommand(self, widget, property_name, current)
            command.file_path = file_path
            command.data_path = data_path[:-1] if len(data_path) > 0 else []  # Empty list for root properties
            print(f"Command created with file_path: {command.file_path}, data_path: {command.data_path}")
            
            self.command_stack.push(command)
            print("Command pushed to stack")
            
            # Update UI state
            self.update_save_button()  # Update save/undo/redo button states
            
        except Exception as e:
            print(f"Error deleting property: {str(e)}")
            import traceback
            traceback.print_exc()

    def add_array_item(self, widget: QWidget, item_schema: dict):
        """Add a new item to an array"""
        # Get file path from parent schema view
        file_path = self.get_schema_view_file_path(widget)
        if not file_path:
            return
            
        data_path = widget.property("data_path")
        if data_path is None:
            return
            
        # Get current data from command stack
        current_data = self.command_stack.get_file_data(file_path)
        if not current_data:
            with open(file_path, 'r', encoding='utf-8') as f:
                current_data = json.load(f)
                
        # Navigate to the target array
        array_data = current_data
        for part in data_path:
            array_data = array_data[part]
            
        if not isinstance(array_data, list):
            array_data = []
            
        # Resolve schema references and get the full schema
        resolved_schema = self.resolve_schema_references(item_schema)
        
        # Create new item with default value based on schema
        new_item = self.get_default_value(resolved_schema)
        
        # For objects, ensure all required properties are present with proper default values
        if isinstance(new_item, dict):
            # Get required properties from schema
            required_props = resolved_schema.get("required", [])
            properties = resolved_schema.get("properties", {})
            
            # Add all required properties
            for prop_name in required_props:
                if prop_name not in new_item and prop_name in properties:
                    prop_schema = self.resolve_schema_references(properties[prop_name])
                    new_item[prop_name] = self.get_default_value(prop_schema)
                    
            # If schema has unevaluatedProperties set to false, add all optional properties too
            if resolved_schema.get("unevaluatedProperties") is False:
                for prop_name, prop_schema in properties.items():
                    if prop_name not in new_item:
                        prop_schema = self.resolve_schema_references(prop_schema)
                        new_item[prop_name] = self.get_default_value(prop_schema)
                    
        new_array = array_data + [new_item]
        
        # Find the array's content widget (next widget after the toggle button)
        array_container = widget.parent()
        content_widget = None
        if array_container:
            array_layout = array_container.layout()
            for i in range(array_layout.count()):
                item_widget = array_layout.itemAt(i).widget()
                if item_widget and item_widget != widget:
                    content_widget = item_widget
                    break
        
        if content_widget and content_widget.layout():
            # Create transform command for the new widget
            transform_cmd = AddArrayItemCommand(
                self,
                content_widget,
                None,  # No old value since we're adding a new widget
                new_item
            )
            # Add required attributes to transform command
            transform_cmd.file_path = file_path
            transform_cmd.data_path = data_path + [len(array_data)]  # Path to the new item
            transform_cmd.source_widget = widget
            transform_cmd.schema = resolved_schema  # Pass the schema to the transform command
            transform_cmd.array_data = array_data  # Pass current array data
            transform_cmd.new_array = new_array  # Pass new array data
            
            self.command_stack.push(transform_cmd)
            self.update_save_button()

    def delete_array_item(self, widget: QWidget, item_path: list):
        """Delete an item from an array"""
        # Get file path from parent schema view
        file_path = self.get_schema_view_file_path(widget)
        if not file_path:
            return
            
        # Get current data from command stack
        current_data = self.command_stack.get_file_data(file_path)
        if not current_data:
            with open(file_path, 'r', encoding='utf-8') as f:
                current_data = json.load(f)
        
        # Get array path (everything except the last index)
        array_path = item_path[:-1]
        item_index = item_path[-1]
        
        # Navigate to the array
        array_data = current_data
        for part in array_path:
            array_data = array_data[part]
            
        if not isinstance(array_data, list):
            return
            
        # Find the array's content widget (where the items are stored)
        content_widget = widget.parent().parent()
        if not content_widget:
            return
        
        # Create and execute command
        command = DeleteArrayItemCommand(
            self,
            content_widget,
            array_data,
            item_index
        )
        # Add required attributes to transform command
        command.file_path = file_path
        command.data_path = array_path
        command.source_widget = widget
        
        self.command_stack.push(command)
        self.update_save_button()

    def add_research_subject(self, subject_type: str):
        """Add a new research subject"""
        if not self.current_folder:
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Add Research Subject")
        dialog.setModal(True)
        dialog.resize(800, 600)

        layout = QVBoxLayout(dialog)

        # Add note about undo/redo
        note_label = QLabel("Note: This operation cannot be undone.")
        note_label.setStyleSheet("QLabel { color: #FFA500; }")  # Orange color for warning
        layout.addWidget(note_label)

        # Rest of the dialog setup...
        search_box = QLineEdit()
        search_box.setPlaceholderText("Search subjects...")
        layout.addWidget(search_box)

        list_widget = QListWidget()
        layout.addWidget(list_widget)

        # Add buttons
        button_layout = QHBoxLayout()
        copy_btn = QPushButton("Copy Selected")
        copy_btn.setEnabled(False)
        button_layout.addWidget(copy_btn)

        cancel_btn = QPushButton("Cancel")
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)

        def update_subject_list(search=""):
            list_widget.clear()
            
            # Add mod subjects first
            for subject_id in sorted(self.manifest_data['mod'].get('research_subject', {})):
                if search.lower() in subject_id.lower():
                    item = QListWidgetItem(subject_id)
                    list_widget.addItem(item)
            
            # Then add base game subjects
            for subject_id in sorted(self.manifest_data['base_game'].get('research_subject', {})):
                if search.lower() in subject_id.lower() and subject_id not in self.manifest_data['mod'].get('research_subject', {}):
                    item = QListWidgetItem(subject_id)
                    item.setForeground(QColor(150, 150, 150))
                    font = item.font()
                    font.setItalic(True)
                    item.setFont(font)
                    list_widget.addItem(item)

        def get_research_fields():
            """Get available research fields from the current player file"""
            fields = {'military': [], 'civilian': []}
            print("Getting research fields from current data...")
            if not self.current_data:
                print("No current data available")
                return fields
                
            if 'research' not in self.current_data:
                print("No research data in current data")
                return fields
                
            research_data = self.current_data['research']
            if 'research_domains' not in research_data:
                print("No research_domains in research data")
                return fields
                
            domains = research_data['research_domains']
            print(f"Found domains: {list(domains.keys())}")
            
            for domain in ['military', 'civilian']:
                if domain in domains:
                    domain_data = domains[domain]
                    print(f"Processing domain {domain}...")
                    if 'research_fields' in domain_data:
                        research_fields = domain_data['research_fields']
                        print(f"Found {len(research_fields)} fields in {domain}")
                        for field in research_fields:
                            if isinstance(field, dict) and 'id' in field:
                                fields[domain].append(field['id'])
                                print(f"Added field {field['id']} to {domain}")
            
            print(f"Final fields structure: {fields}")
            return fields

        def on_selection_changed():
            """Enable/disable copy button based on selection"""
            copy_btn.setEnabled(bool(list_widget.selectedItems()))

        def on_copy():
            selected_items = list_widget.selectedItems()
            if not selected_items:
                return
                
            source_id = selected_items[0].text()
            
            # Get new name
            new_name, ok = QInputDialog.getText(
                dialog,
                "New Subject Name",
                "Enter name for new subject:",
                text=source_id + "_copy"
            )
            
            if not ok or not new_name:
                return

            # Create dialog for research settings
            settings_dialog = QDialog(dialog)
            settings_dialog.setWindowTitle("Research Subject Settings")
            settings_layout = QFormLayout(settings_dialog)

            # Domain selection
            domain_combo = QComboBox()
            domain_combo.addItems(['military', 'civilian'])
            settings_layout.addRow("Domain:", domain_combo)

            # Get available fields
            fields = get_research_fields()
            field_combo = QComboBox()
            
            def update_fields():
                field_combo.clear()
                current_domain = domain_combo.currentText()
                field_combo.addItems(fields[current_domain])
            
            domain_combo.currentTextChanged.connect(update_fields)
            update_fields()  # Initial population
            settings_layout.addRow("Field:", field_combo)

            # Tier selection (0-4)
            tier_spin = QSpinBox()
            tier_spin.setRange(0, 4)
            settings_layout.addRow("Tier:", tier_spin)

            # Field coordinates
            coord_widget = QWidget()
            coord_layout = QHBoxLayout(coord_widget)
            coord_x = QSpinBox()
            coord_y = QSpinBox()
            coord_x.setRange(0, 20)  # Reasonable range for coordinates
            coord_y.setRange(0, 20)
            coord_layout.addWidget(QLabel("X:"))
            coord_layout.addWidget(coord_x)
            coord_layout.addWidget(QLabel("Y:"))
            coord_layout.addWidget(coord_y)
            settings_layout.addRow("Field Coordinates:", coord_widget)

            # Buttons
            button_box = QHBoxLayout()
            ok_btn = QPushButton("OK")
            cancel_btn = QPushButton("Cancel")
            button_box.addWidget(ok_btn)
            button_box.addWidget(cancel_btn)
            settings_layout.addRow(button_box)

            ok_btn.clicked.connect(settings_dialog.accept)
            cancel_btn.clicked.connect(settings_dialog.reject)

            if settings_dialog.exec() != QDialog.DialogCode.Accepted:
                return

            # Get the settings
            domain = domain_combo.currentText()
            field = field_combo.currentText()
            tier = tier_spin.value()
            field_coord = [coord_x.value(), coord_y.value()]
                
            # Check if subject already exists
            target_file = self.current_folder / "entities" / f"{new_name}.research_subject"
            if target_file.exists():
                # Show overwrite dialog
                msg_box = QMessageBox(dialog)
                msg_box.setWindowTitle("Subject Exists")
                msg_box.setText(f"A subject named '{new_name}' already exists.")
                msg_box.setInformativeText("Do you want to overwrite it?")
                msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                msg_box.setDefaultButton(QMessageBox.StandardButton.No)
                
                # Add checkbox for overwriting in tree
                overwrite_box = QCheckBox("Also overwrite in research tree", msg_box)
                msg_box.setCheckBox(overwrite_box)
                
                def on_overwrite_changed(state):
                    # Enable/disable Yes button based on checkbox
                    buttons = msg_box.standardButtons()
                    yes_button = msg_box.button(QMessageBox.StandardButton.Yes)
                    if yes_button:
                        yes_button.setEnabled(state == Qt.CheckState.Checked)
                
                overwrite_box.stateChanged.connect(on_overwrite_changed)
                overwrite_box.setChecked(False)  # Start unchecked
                
                if msg_box.exec() != QMessageBox.StandardButton.Yes:
                    return
                    
                overwrite = True
            else:
                overwrite = False
            
            # Create and execute the command
            command = CreateResearchSubjectCommand(
                self,
                source_id,
                new_name,
                subject_type,
                overwrite,
                domain=domain,
                field=field,
                tier=tier,
                field_coord=field_coord
            )
            
            # Prepare and execute the command
            if not command.prepare():
                QMessageBox.warning(self, "Error", "Failed to prepare research subject creation")
                return
                
            if not command.execute():
                QMessageBox.warning(self, "Error", "Failed to create research subject")
                return
                
            # Do NOT add command to stack for undo/redo
            # self.command_stack.push(command)
            
            dialog.accept()

        # Connect signals
        search_box.textChanged.connect(update_subject_list)
        list_widget.itemSelectionChanged.connect(on_selection_changed)
        copy_btn.clicked.connect(on_copy)
        cancel_btn.clicked.connect(dialog.reject)
        
        # Initial population
        update_subject_list()
        
        dialog.exec()

    def delete_research_subject(self, subject_id: str):
        """Delete a research subject"""
        if not self.current_folder:
            return

        # Check if subject exists in mod folder
        subject_file = self.current_folder / "entities" / f"{subject_id}.research_subject"
        if not subject_file.exists():
            QMessageBox.warning(self, "Error", "Cannot delete base game research subjects")
            return

        # Ask user what they want to delete
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Delete Research Subject")
        msg_box.setText(f"How would you like to delete research subject '{subject_id}'?\n\nNote: This operation cannot be undone.")
        msg_box.setIcon(QMessageBox.Icon.Warning)
        
        # Add custom buttons
        full_delete_btn = msg_box.addButton("Full Delete", QMessageBox.ButtonRole.ActionRole)
        full_delete_btn.setToolTip("Delete file, remove from manifest, and remove from research tree")
        
        tree_only_btn = msg_box.addButton("Remove from Tree Only", QMessageBox.ButtonRole.ActionRole) 
        tree_only_btn.setToolTip("Only remove from research tree, keep the file and manifest entry")
        
        cancel_btn = msg_box.addButton(QMessageBox.StandardButton.Cancel)
        
        msg_box.exec()
        clicked_button = msg_box.clickedButton()

        if clicked_button == cancel_btn:
            return

        try:
            # Find which array contains the subject
            array_path = None
            if 'research' in self.current_data:
                if 'research_subjects' in self.current_data['research'] and subject_id in self.current_data['research']['research_subjects']:
                    array_path = ['research', 'research_subjects']
                elif 'faction_research_subjects' in self.current_data['research'] and subject_id in self.current_data['research']['faction_research_subjects']:
                    array_path = ['research', 'faction_research_subjects']

            if not array_path:
                QMessageBox.warning(self, "Error", "Research subject not found in research tree")
                return

            # Create and execute the delete command
            command = DeleteResearchSubjectCommand(
                self,
                subject_id,
                array_path,
                clicked_button == full_delete_btn  # True for full delete, False for tree-only
            )

            # Prepare and execute the command
            if not command.prepare():
                QMessageBox.warning(self, "Error", "Failed to prepare research subject deletion")
                return

            if not command.execute():
                QMessageBox.warning(self, "Error", "Failed to delete research subject")
                return

            # Do NOT add command to stack for undo/redo
            # self.command_stack.push(command)

        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to delete research subject: {str(e)}")

    def create_default_config(self):
        """Create a default config file if it doesn't exist"""
        default_config = {
            "base_game_folder": "",
            "schema_folder": ""
        }
        try:
            with open('config.json', 'w') as f:
                json.dump(default_config, f, indent=4)
            self.config = default_config
            logging.info("Created default config.json")
        except Exception as e:
            logging.error(f"Failed to create default config.json: {e}")
            self.config = default_config

    def simplify_number(self, value: float | int) -> float | int:
        """Simplify a number to an integer if possible without loss of precision"""
        try:
            # Convert to float first to handle string inputs
            float_val = float(value)
            # Check if it can be converted to int without loss
            if float_val.is_integer():
                return int(float_val)
            return float_val
        except (ValueError, TypeError):
            return value

    def setup_list_context_menu(self, list_widget: QListWidget, file_type: str):
        """Add context menu support to a list widget"""
        list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        list_widget.customContextMenuRequested.connect(
            lambda pos, w=list_widget, t=file_type: self.show_list_context_menu(w, pos, t)
        )

    def show_list_context_menu(self, list_widget: QListWidget, position: QPoint, file_type: str):
        """Show context menu for list widgets"""
        menu = QMenu()
        
        # Only show options if an item is selected
        if list_widget.currentItem():
            file_id = list_widget.currentItem().text()
            is_mod_version = not list_widget.currentItem().font().italic()
            has_base_game_version = False

            # Check if there's a base game version
            if file_type == "uniform":
                base_file = None if not self.base_game_folder else self.base_game_folder / "uniforms" / f"{file_id}.uniforms"
                has_base_game_version = base_file and base_file.exists()
            else:
                has_base_game_version = file_id in self.manifest_data['base_game'].get(file_type, {})

            # Add copy option
            copy_action = menu.addAction("Create Copy...")
            copy_action.triggered.connect(
                lambda: self.show_copy_dialog(file_id, file_type)
            )

            # Only show delete options for mod files
            if is_mod_version:
                menu.addSeparator()
                # If this file doesn't have a base game version, show option to remove from manifest
                if not has_base_game_version:
                    delete_with_manifest = menu.addAction("Delete File and Remove from Manifest")
                    delete_with_manifest.triggered.connect(
                        lambda: self.delete_file(file_id, file_type, True)
                    )
                    menu.addSeparator()
                else:
                    delete_file = menu.addAction("Delete File Only")
                    delete_file.triggered.connect(
                        lambda: self.delete_file(file_id, file_type, False)
                    )

            
        menu.exec(list_widget.mapToGlobal(position))

    def delete_file(self, file_id: str, file_type: str, remove_manifest: bool):
        """Delete a file and optionally its manifest entry"""
        # Ask for confirmation
        msg = "Are you sure you want to delete this file?"
        if remove_manifest:
            msg += "\nThis will also remove it from the manifest."
        msg += "\nNote: This operation cannot be undone."
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            # Create and execute the delete command
            command = DeleteFileCommand(self, file_id, file_type, remove_manifest)
            
            # Prepare and validate the command
            if not command.prepare():
                QMessageBox.warning(self, "Error", "Failed to prepare file deletion")
                return
                
            # Execute the delete command
            if not command.execute():
                QMessageBox.warning(self, "Error", "Failed to delete file")
                return
                
            # Add command to stack for undo/redo
            # self.command_stack.push(command)

            # Update the buttons
            self.update_save_button()
            
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))

    def show_copy_dialog(self, source_file: str, file_type: str):
        """Show dialog to create a copy of a file"""
        if not self.current_folder:
            QMessageBox.warning(self, "Error", "Please open a mod folder first")
            return
            
        # Check if source file is from base game
        if file_type == "uniform":
            # For uniforms, check if file exists in mod folder
            mod_file = self.current_folder / "uniforms" / f"{source_file}.uniforms"
            base_file = None if not self.base_game_folder else self.base_game_folder / "uniforms" / f"{source_file}.uniforms"
            is_base_game = not mod_file.exists() and base_file and base_file.exists()
        else:
            is_base_game = (source_file not in self.manifest_data['mod'].get(file_type, {}) and 
                          source_file in self.manifest_data['base_game'].get(file_type, {}))
        
        # Show copy dialog
        copy_dialog = QDialog(self)
        copy_dialog.setWindowTitle("Copy File")
        copy_layout = QVBoxLayout(copy_dialog)
        
        # For uniforms, we only allow overwriting base game files
        if file_type == "uniform":
            if not is_base_game:
                QMessageBox.warning(self, "Error", "Uniforms files can only be copied from base game")
                return
            overwrite = True
            name_edit = QLineEdit(source_file)  # Use source name for uniforms
            name_edit.setEnabled(False)  # Disable name editing for uniforms
        else:
            # Add option to overwrite if it's a base game file
            overwrite = False
            if is_base_game:
                overwrite_check = QCheckBox("Overwrite in mod (keep same name)")
                copy_layout.addWidget(overwrite_check)
                
                def on_overwrite_changed(state):
                    nonlocal overwrite
                    overwrite = state == Qt.CheckState.Checked.value
                    name_edit.setEnabled(not overwrite)
                    name_edit.setText(source_file if overwrite else "")
                    
                overwrite_check.stateChanged.connect(on_overwrite_changed)
            
            # Add name input
            name_layout = QHBoxLayout()
            name_layout.addWidget(QLabel("New Name:"))
            name_edit = QLineEdit()
            name_layout.addWidget(name_edit)
            copy_layout.addLayout(name_layout)
        
        # Add copy/cancel buttons
        copy_buttons = QHBoxLayout()
        copy_ok = QPushButton("Copy")
        copy_cancel = QPushButton("Cancel")
        copy_buttons.addWidget(copy_ok)
        copy_buttons.addWidget(copy_cancel)
        copy_layout.addLayout(copy_buttons)
        
        def do_copy():
            new_name = name_edit.text().strip()
            if not new_name:
                QMessageBox.warning(copy_dialog, "Error", "Please enter a name for the copy")
                return
                
            try:
                # Create copy command
                copy_command = CreateFileFromCopy(
                    self,
                    source_file,
                    file_type,
                    new_name,
                    overwrite
                )
                
                # Prepare and validate the command
                if not copy_command.prepare():
                    QMessageBox.warning(copy_dialog, "Error", "Failed to prepare file copy")
                    return
                    
                # Execute the copy command
                if not copy_command.execute():
                    QMessageBox.warning(copy_dialog, "Error", "Failed to create file copy")
                    return
                    
                # Add command to stack for undo/redo
                # self.command_stack.push(copy_command)
                
                copy_dialog.accept()
                
            except Exception as e:
                QMessageBox.warning(copy_dialog, "Error", str(e))
        
        copy_ok.clicked.connect(do_copy)
        copy_cancel.clicked.connect(copy_dialog.reject)
        
        copy_dialog.exec()
