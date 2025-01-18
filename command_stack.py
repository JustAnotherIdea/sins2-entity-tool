from typing import Any, List, Dict, Set
from pathlib import Path
import json
import logging

class Command:
    """Base class for all commands"""
    def __init__(self, file_path: Path, data_path: List[str | int], old_value: Any, new_value: Any):
        self.file_path = file_path
        self.data_path = data_path
        self.old_value = old_value
        self.new_value = new_value
        
    def undo(self) -> None:
        raise NotImplementedError
        
    def redo(self) -> None:
        raise NotImplementedError
        
class EditValueCommand(Command):
    """Command for editing a value in a schema"""
    def __init__(self, file_path: Path, data_path: List[str | int], old_value: Any, new_value: Any, 
                 update_widget_callback=None, update_data_callback=None):
        super().__init__(file_path, data_path, old_value, new_value)
        self.update_widget = update_widget_callback
        self.update_data = update_data_callback
        logging.debug(f"Created EditValueCommand for {file_path} at path {data_path}")
        logging.debug(f"Old value: {old_value}, New value: {new_value}")
        
    def undo(self) -> None:
        logging.info(f"Undoing EditValueCommand for {self.file_path} at path {self.data_path}")
        logging.debug(f"Restoring value from {self.new_value} to {self.old_value}")
        if self.update_widget:
            self.update_widget(self.old_value)
        if self.update_data:
            self.update_data(self.data_path, self.old_value)
            
    def redo(self) -> None:
        logging.info(f"Redoing EditValueCommand for {self.file_path} at path {self.data_path}")
        logging.debug(f"Changing value from {self.old_value} to {self.new_value}")
        if self.update_widget:
            self.update_widget(self.new_value)
        if self.update_data:
            self.update_data(self.data_path, self.new_value)

class CommandStack:
    """Manages undo/redo operations"""
    def __init__(self):
        self.undo_stack: List[Command] = []
        self.redo_stack: List[Command] = []
        self.is_executing = False  # Flag to prevent recursive command execution
        self.modified_files: Set[Path] = set()  # Track files with unsaved changes
        logging.info("Initialized new CommandStack")
        
    def push(self, command: Command) -> None:
        """Add a new command to the stack"""
        if self.is_executing:
            logging.debug("Skipping command push - already executing")
            return
        
        logging.info(f"Pushing command for file: {command.file_path}, path: {command.data_path}, old value: {command.old_value}, new value: {command.new_value}")
        self.is_executing = True
        command.redo()  # Execute the command immediately
        self.is_executing = False
        self.undo_stack.append(command)
        self.redo_stack.clear()  # Clear redo stack when new command is added
        self.modified_files.add(command.file_path)  # Track modified file
        logging.debug(f"Modified files after push: {self.modified_files}")
        
    def undo(self) -> None:
        """Undo the last command"""
        if not self.undo_stack:
            logging.debug("No commands to undo")
            return
            
        self.is_executing = True
        command = self.undo_stack.pop()
        logging.info(f"Undoing command for file: {command.file_path}, path: {command.data_path}")
        command.undo()
        self.redo_stack.append(command)
        
        # Update modified files tracking
        if not any(cmd.file_path == command.file_path for cmd in self.undo_stack):
            logging.info(f"Removing {command.file_path} from modified files - no more changes")
            self.modified_files.discard(command.file_path)
            
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
        command.redo()
        self.undo_stack.append(command)
        self.modified_files.add(command.file_path)  # Track modified file
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