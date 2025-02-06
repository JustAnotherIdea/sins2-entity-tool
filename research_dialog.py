from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QButtonGroup, QRadioButton, QComboBox, QLineEdit, QSpinBox, QLabel, QDialogButtonBox, QMessageBox
from command_stack import CreateResearchSubjectCommand

class ResearchDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.gui = parent
        self.setWindowTitle("Research Subject Management")
        self.setModal(True)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()

        # Create group box for research subject selection
        selection_group = QGroupBox("Research Subject Selection")
        selection_layout = QVBoxLayout()

        # Add radio buttons for subject type
        self.type_group = QButtonGroup()
        self.regular_radio = QRadioButton("Regular Research Subject")
        self.faction_radio = QRadioButton("Faction Research Subject")
        self.regular_radio.setChecked(True)
        self.type_group.addButton(self.regular_radio)
        self.type_group.addButton(self.faction_radio)
        selection_layout.addWidget(self.regular_radio)
        selection_layout.addWidget(self.faction_radio)

        # Add source subject selection
        source_layout = QHBoxLayout()
        source_layout.addWidget(QLabel("Source Subject:"))
        self.source_combo = QComboBox()
        source_layout.addWidget(self.source_combo)
        selection_layout.addLayout(source_layout)

        # Add new name input
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("New Name:"))
        self.name_edit = QLineEdit()
        name_layout.addWidget(self.name_edit)
        selection_layout.addLayout(name_layout)

        selection_group.setLayout(selection_layout)
        layout.addWidget(selection_group)

        # Create group box for research settings
        settings_group = QGroupBox("Research Settings")
        settings_layout = QVBoxLayout()

        # Domain selection
        domain_layout = QHBoxLayout()
        domain_layout.addWidget(QLabel("Domain:"))
        self.domain_combo = QComboBox()
        self.domain_combo.addItems(["military", "civilian"])
        domain_layout.addWidget(self.domain_combo)
        settings_layout.addLayout(domain_layout)

        # Field selection
        field_layout = QHBoxLayout()
        field_layout.addWidget(QLabel("Field:"))
        self.field_combo = QComboBox()
        # Add field paths here - you'll need to populate this with actual paths
        self.field_combo.addItems(["path1", "path2", "path3"])  # Replace with actual paths
        field_layout.addWidget(self.field_combo)
        settings_layout.addLayout(field_layout)

        # Tier input
        tier_layout = QHBoxLayout()
        tier_layout.addWidget(QLabel("Tier:"))
        self.tier_spin = QSpinBox()
        self.tier_spin.setMinimum(1)
        self.tier_spin.setMaximum(10)  # Adjust max tier as needed
        tier_layout.addWidget(self.tier_spin)
        settings_layout.addLayout(tier_layout)

        # Field coordinates input
        coord_layout = QHBoxLayout()
        coord_layout.addWidget(QLabel("Field Coordinates:"))
        self.coord_x_spin = QSpinBox()
        self.coord_y_spin = QSpinBox()
        self.coord_x_spin.setMinimum(-100)  # Adjust range as needed
        self.coord_x_spin.setMaximum(100)
        self.coord_y_spin.setMinimum(-100)
        self.coord_y_spin.setMaximum(100)
        coord_layout.addWidget(self.coord_x_spin)
        coord_layout.addWidget(self.coord_y_spin)
        settings_layout.addLayout(coord_layout)

        settings_group.setLayout(settings_layout)
        layout.addWidget(settings_group)

        # Add buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self.setLayout(layout)

    def get_subject_type(self):
        return "faction" if self.faction_radio.isChecked() else "regular"

    def get_research_settings(self):
        return {
            'domain': self.domain_combo.currentText(),
            'field': self.field_combo.currentText(),
            'tier': self.tier_spin.value(),
            'field_coord': [self.coord_x_spin.value(), self.coord_y_spin.value()]
        }

    def accept(self):
        if not self.name_edit.text():
            QMessageBox.warning(self, "Error", "Please enter a name for the new research subject.")
            return
        if not self.source_combo.currentText():
            QMessageBox.warning(self, "Error", "Please select a source research subject.")
            return

        # Create the command with research settings
        settings = self.get_research_settings()
        command = CreateResearchSubjectCommand(
            self.gui,
            self.source_combo.currentText(),
            self.name_edit.text(),
            self.get_subject_type(),
            False,  # overwrite
            domain=settings['domain'],
            field=settings['field'],
            tier=settings['tier'],
            field_coord=settings['field_coord']
        )

        # Execute the command directly (no undo/redo)
        if command.prepare() and command.execute():
            super().accept()
        else:
            QMessageBox.warning(self, "Error", "Failed to create research subject.")

    def populate_source_subjects(self, subjects):
        self.source_combo.clear()
        self.source_combo.addItems(subjects)

    def populate_fields(self, fields):
        self.field_combo.clear()
        self.field_combo.addItems(fields) 