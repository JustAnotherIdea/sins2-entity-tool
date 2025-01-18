from typing import Any, List, Dict
from pathlib import Path

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
        
    def undo(self) -> None:
        if self.update_widget:
            self.update_widget(self.old_value)
        if self.update_data:
            self.update_data(self.data_path, self.old_value)
            
    def redo(self) -> None:
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
        
    def push(self, command: Command) -> None:
        """Add a new command to the stack"""
        if self.is_executing:
            return
            
        self.undo_stack.append(command)
        self.redo_stack.clear()  # Clear redo stack when new command is added
        
    def undo(self) -> None:
        """Undo the last command"""
        if not self.undo_stack:
            return
            
        self.is_executing = True
        command = self.undo_stack.pop()
        command.undo()
        self.redo_stack.append(command)
        self.is_executing = False
        
    def redo(self) -> None:
        """Redo the last undone command"""
        if not self.redo_stack:
            return
            
        self.is_executing = True
        command = self.redo_stack.pop()
        command.redo()
        self.undo_stack.append(command)
        self.is_executing = False
        
    def can_undo(self) -> bool:
        """Check if there are commands that can be undone"""
        return len(self.undo_stack) > 0
        
    def can_redo(self) -> bool:
        """Check if there are commands that can be redone"""
        return len(self.redo_stack) > 0 