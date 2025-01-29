from typing import Any, List, Dict, Set, Callable
from pathlib import Path
import json
import logging
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel
from PyQt6.QtCore import Qt

class Command:
    """Base class for all commands"""
    def __init__(self, file_path: Path, data_path: List[str | int], old_value: Any, new_value: Any):
        self.file_path = file_path
        self.data_path = data_path
        self.old_value = old_value
        self.new_value = new_value
        self.source_widget = None  # Track which widget initiated the change
        
    def undo(self) -> None:
        raise NotImplementedError
        
    def redo(self) -> None:
        raise NotImplementedError
        
class EditValueCommand(Command):
    """Command for editing a value in a data structure"""
    def __init__(self, file_path: Path, data_path: list, old_value: any, new_value: any, 
                 update_widget_func: Callable, update_data_func: Callable):
        super().__init__(file_path, data_path, old_value, new_value)
        self.update_widget_func = update_widget_func
        self.update_data_func = update_data_func
        logging.debug(f"Created EditValueCommand for {file_path} at path {data_path}")
        logging.debug(f"Old value: {old_value}, New value: {new_value}")
        
    def update_widget_safely(self, value: any):
        """Try to update widget, but don't fail if widget is gone"""
        try:
            self.update_widget_func(value)
        except RuntimeError as e:
            # Widget was deleted, just log and continue
            logging.debug(f"Widget was deleted, skipping UI update: {str(e)}")
        
    def undo(self):
        """Restore the old value"""
        logging.info(f"Undoing EditValueCommand for {self.file_path} at path {self.data_path}")
        self.update_widget_safely(self.old_value)
        self.update_data_func(self.data_path, self.old_value)
        
    def redo(self):
        """Apply the new value"""
        logging.info(f"Redoing EditValueCommand for {self.file_path} at path {self.data_path}")
        self.update_widget_safely(self.new_value)
        self.update_data_func(self.data_path, self.new_value)

class CommandStack:
    """Manages undo/redo operations"""
    def __init__(self):
        self.undo_stack: List[Command] = []
        self.redo_stack: List[Command] = []
        self.is_executing = False  # Flag to prevent recursive command execution
        self.modified_files: Set[Path] = set()  # Track files with unsaved changes
        self.file_data: Dict[Path, dict] = {}  # Store current data for each file
        self.data_change_callbacks: Dict[Path, List[Callable]] = {}  # Callbacks for data changes
        logging.info("Initialized new CommandStack")
        
    def register_data_change_callback(self, file_path: Path, callback: Callable) -> None:
        """Register a callback to be called when data changes for a file"""
        if file_path not in self.data_change_callbacks:
            self.data_change_callbacks[file_path] = []
        self.data_change_callbacks[file_path].append(callback)
        logging.debug(f"Registered data change callback for {file_path}")
        
    def unregister_data_change_callback(self, file_path: Path, callback: Callable) -> None:
        """Unregister a data change callback"""
        if file_path in self.data_change_callbacks:
            try:
                self.data_change_callbacks[file_path].remove(callback)
                logging.debug(f"Unregistered data change callback for {file_path}")
            except ValueError:
                pass
            
    def notify_data_change(self, file_path: Path, data_path: List = None, value: Any = None, source_widget = None) -> None:
        """Notify all registered callbacks that data has changed for a file"""
        if file_path in self.data_change_callbacks:
            for callback in self.data_change_callbacks[file_path]:
                try:
                    if data_path is not None:
                        # Partial update with path and value
                        print("calling data change callback")
                        callback(self.get_file_data(file_path), data_path, value, source_widget)
                    else:
                        # Full update with just data
                        callback(self.get_file_data(file_path), None, None, None)
                except Exception as e:
                    logging.error(f"Error in data change callback for {file_path}: {str(e)}")
        
    def update_file_data(self, file_path: Path, data: dict) -> None:
        """Update the stored data for a file"""
        logging.info(f"Updating stored data for file: {file_path}")
        self.file_data[file_path] = data.copy()  # Store a copy to prevent reference issues
        
    def get_file_data(self, file_path: Path) -> dict:
        """Get the current data for a file"""
        if file_path not in self.file_data:
            print(f"No data found for file: {file_path}")
            return None
        print(f"Retrieving stored data for file: {file_path}")
        return self.file_data[file_path].copy()  # Return a copy to prevent reference issues
        
    def push(self, command: Command) -> None:
        """Add a new command to the stack"""
        if self.is_executing:
            logging.debug("Skipping command push - already executing")
            return
        
        print(f"Pushing command for file: {command.file_path}, path: {command.data_path}, old value: {command.old_value}, new value: {command.new_value}")
        
        # Get current data for the file
        data = self.get_file_data(command.file_path)
        if data is None:
            logging.error(f"No data found for file {command.file_path} when pushing command")
            return
            
        # Execute the command
        print("executing command")
        self.is_executing = True
        command.redo()  # Execute the command immediately
        self.is_executing = False
        
        # Update the stored data
        print("updating stored data")
        current = data
        for i, key in enumerate(command.data_path[:-1]):
            if isinstance(current, dict):
                if key not in current:
                    current[key] = {} if isinstance(command.data_path[i + 1], str) else []
                current = current[key]
            elif isinstance(current, list):
                while len(current) <= key:
                    current.append({} if isinstance(command.data_path[i + 1], str) else [])
                current = current[key]
        
        print("updating stored data")
        if command.data_path:
            if isinstance(current, dict):
                current[command.data_path[-1]] = command.new_value
            elif isinstance(current, list):
                while len(current) <= command.data_path[-1]:
                    current.append(None)
                current[command.data_path[-1]] = command.new_value
                
        # Store updated data and notify listeners
        print("storing updated data")
        self.update_file_data(command.file_path, data)
        print("notifying data change")
        self.notify_data_change(command.file_path, command.data_path, command.new_value, command.source_widget)
        
        print("appending command to undo stack")
        self.undo_stack.append(command)
        print("clearing redo stack")
        self.redo_stack.clear()  # Clear redo stack when new command is added
        print("adding file path to modified files")
        self.modified_files.add(command.file_path)  # Track modified file
        print(f"Modified files after push: {self.modified_files}")
        
    def undo(self) -> None:
        """Undo the last command"""
        if not self.undo_stack:
            logging.debug("No commands to undo")
            return
            
        self.is_executing = True
        command = self.undo_stack.pop()
        logging.info(f"Undoing command for file: {command.file_path}, path: {command.data_path}")
        
        # Get current data and update it
        data = self.get_file_data(command.file_path)
        if data is not None:
            command.undo()
            
            # Update the stored data
            current = data
            for i, key in enumerate(command.data_path[:-1]):
                if isinstance(current, dict):
                    if key not in current:
                        current[key] = {} if isinstance(command.data_path[i + 1], str) else []
                    current = current[key]
                elif isinstance(current, list):
                    while len(current) <= key:
                        current.append({} if isinstance(command.data_path[i + 1], str) else [])
                    current = current[key]
            
            if command.data_path:
                if isinstance(current, dict):
                    current[command.data_path[-1]] = command.old_value
                elif isinstance(current, list):
                    while len(current) <= command.data_path[-1]:
                        current.append(None)
                    current[command.data_path[-1]] = command.old_value
                    
            # Store updated data and notify listeners
            self.update_file_data(command.file_path, data)
            self.notify_data_change(command.file_path, command.data_path, command.old_value, command.source_widget)
            
        self.redo_stack.append(command)
        
        # Mark file as modified since we changed its data
        self.modified_files.add(command.file_path)
        logging.info(f"Marked {command.file_path} as modified after undo")
            
        self.is_executing = False
        logging.debug(f"Modified files after undo: {self.modified_files}")
        
    def redo(self) -> None:
        """Redo the last undone command"""
        if not self.redo_stack:
            logging.debug("No commands to redo")
            return
            
        self.is_executing = True
        command = self.redo_stack.pop()
        logging.info(f"Redoing command for file: {command.file_path}, path: {command.data_path}")
        
        # Get current data and update it
        data = self.get_file_data(command.file_path)
        if data is not None:
            command.redo()
            
            # Update the stored data
            current = data
            for i, key in enumerate(command.data_path[:-1]):
                if isinstance(current, dict):
                    if key not in current:
                        current[key] = {} if isinstance(command.data_path[i + 1], str) else []
                    current = current[key]
                elif isinstance(current, list):
                    while len(current) <= key:
                        current.append({} if isinstance(command.data_path[i + 1], str) else [])
                    current = current[key]
            
            if command.data_path:
                if isinstance(current, dict):
                    current[command.data_path[-1]] = command.new_value
                elif isinstance(current, list):
                    while len(current) <= command.data_path[-1]:
                        current.append(None)
                    current[command.data_path[-1]] = command.new_value
                    
            # Store updated data and notify listeners
            self.update_file_data(command.file_path, data)
            self.notify_data_change(command.file_path, command.data_path, command.new_value, command.source_widget)
            
        self.undo_stack.append(command)
        
        # Mark file as modified since we changed its data
        self.modified_files.add(command.file_path)
        logging.info(f"Marked {command.file_path} as modified after redo")
        
        self.is_executing = False
        logging.debug(f"Modified files after redo: {self.modified_files}")
        
    def can_undo(self) -> bool:
        """Check if there are commands that can be undone"""
        return len(self.undo_stack) > 0
        
    def can_redo(self) -> bool:
        """Check if there are commands that can be redone"""
        return len(self.redo_stack) > 0
        
    def has_unsaved_changes(self) -> bool:
        """Check if there are any unsaved changes"""
        has_changes = len(self.modified_files) > 0
        logging.debug(f"Checking for unsaved changes: {has_changes} (modified files: {self.modified_files})")
        return has_changes
    
    def mark_all_saved(self) -> None:
        """Mark all changes as saved"""
        self.modified_files.clear()
        logging.info("Marked all changes as saved")
        
    def get_modified_files(self) -> Set[Path]:
        """Get the set of files that have unsaved changes"""
        logging.debug(f"Getting modified files: {self.modified_files}")
        return self.modified_files.copy()
        
    def save_file(self, file_path: Path, data: dict) -> bool:
        """Save changes to a specific file"""
        try:
            logging.info(f"Saving file: {file_path}")
            logging.debug(f"Data to save: {data}")
            
            # Ensure parent directory exists
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Save the file
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
            
            # Remove from modified files
            self.modified_files.discard(file_path)
            logging.info(f"Successfully saved changes to {file_path}")
            logging.debug(f"Modified files after save: {self.modified_files}")
            return True
        except Exception as e:
            logging.error(f"Error saving file {file_path}: {str(e)}")
            return False
            
    def clear_modified_state(self, file_path: Path) -> None:
        """Clear the modified state for a file without saving"""
        self.modified_files.discard(file_path)

class AddPropertyCommand(Command):
    """Command for adding a property to an object"""
    def __init__(self, gui, widget, old_value, new_value):
        super().__init__(None, None, old_value, new_value)  # File path and data path set later
        self.gui = gui
        
        # Store widget properties and references
        self.parent = widget
        self.parent_layout = self.parent.layout()
        if not self.parent_layout:
            self.parent_layout = QVBoxLayout(self.parent)
            self.parent_layout.setContentsMargins(0, 0, 0, 0)
            self.parent_layout.setSpacing(4)
        
        # Additional properties for property addition
        self.source_widget = None
        self.schema = None
        self.prop_name = None
        self.added_widget = None
        
    def execute(self):
        """Execute the property addition"""
        try:
            # Update the data
            if self.data_path is not None:
                self.gui.update_data_value(self.data_path, self.new_value)
                
            # Create and add the widget
            if self.schema and self.prop_name and self.parent_layout:
                # Create container for the new property
                row_widget = QWidget()
                row_layout = QHBoxLayout(row_widget)
                row_layout.setContentsMargins(0, 0, 0, 0)
                row_layout.setSpacing(4)
                row_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
                
                # Add label for the property name (capitalized)
                display_name = self.prop_name.replace("_", " ").title()
                label = QLabel(f"{display_name}:")
                row_layout.addWidget(label)
                
                # Get default value
                default_value = self.gui.get_default_value(self.schema)
                
                # Create appropriate widget based on schema type
                if self.schema.get("type") in ["object", "array"]:
                    # For objects and arrays, use create_widget_for_schema
                    value_widget = self.gui.create_widget_for_schema(
                        default_value,
                        self.schema,
                        False,  # is_base_game
                        self.data_path + [self.prop_name]
                    )
                else:
                    # For simple values, use create_widget_for_value
                    value_widget = self.gui.create_widget_for_value(
                        default_value,
                        self.schema,
                        False,  # is_base_game
                        self.data_path + [self.prop_name]
                    )
                
                if value_widget:
                    row_layout.addWidget(value_widget)
                    row_layout.addStretch()
                    
                    # Add to the parent layout
                    self.parent_layout.addWidget(row_widget)
                    self.added_widget = row_widget
                
        except Exception as e:
            logging.error(f"Error executing add property command: {str(e)}")
            return None
            
    def undo(self):
        """Undo the property addition"""
        try:
            # Update the data
            if self.data_path is not None:
                self.gui.update_data_value(self.data_path, self.old_value)
                
            # Remove the widget
            if self.added_widget:
                self.added_widget.setParent(None)
                self.added_widget.deleteLater()
                self.added_widget = None
                
        except Exception as e:
            logging.error(f"Error undoing add property command: {str(e)}")
            
    def redo(self):
        """Redo the property addition"""
        try:
            return self.execute()
        except Exception as e:
            logging.error(f"Error redoing add property command: {str(e)}")
            return None 