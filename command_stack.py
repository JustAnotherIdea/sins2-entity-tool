from typing import Any, List, Dict, Set, Callable
from pathlib import Path
import json
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QToolButton, QListWidgetItem
from PyQt6.QtGui import QColor
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
   
class CommandStack:
    """Manages undo/redo operations"""
    def __init__(self):
        self.undo_stack: List[Command] = []
        self.redo_stack: List[Command] = []
        self.is_executing = False  # Flag to prevent recursive command execution
        self.modified_files: Set[Path] = set()  # Track files with unsaved changes
        self.file_data: Dict[Path, dict] = {}  # Store current data for each file
        self.data_change_callbacks: Dict[Path, List[Callable]] = {}  # Callbacks for data changes
        print("Initialized new CommandStack")
        
    def register_data_change_callback(self, file_path: Path, callback: Callable) -> None:
        """Register a callback to be called when data changes for a file"""
        if file_path not in self.data_change_callbacks:
            self.data_change_callbacks[file_path] = []
        self.data_change_callbacks[file_path].append(callback)
        print(f"Registered data change callback for {file_path}")
        
    def unregister_data_change_callback(self, file_path: Path, callback: Callable) -> None:
        """Unregister a data change callback"""
        if file_path in self.data_change_callbacks:
            try:
                self.data_change_callbacks[file_path].remove(callback)
                print(f"Unregistered data change callback for {file_path}")
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
                    print(f"Error in data change callback for {file_path}: {str(e)}")
        
    def update_file_data(self, file_path: Path, data: dict) -> None:
        """Update the stored data for a file"""
        print(f"Updating stored data for file: {file_path}")
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
            print("Skipping command push - already executing")
            return
        
        print(f"Pushing command for file: {command.file_path}, path: {command.data_path}, old value: {command.old_value}, new value: {command.new_value}")
        
        # Get current data for the file
        data = self.get_file_data(command.file_path)
        if data is None:
            print(f"No data found for file {command.file_path} when pushing command")
            return
            
        # Execute the command
        print("executing command")
        self.is_executing = True
        command.redo()  # Execute the command immediately
        self.is_executing = False
        
        # Update the stored data
        print("updating stored data")
        if not command.data_path:  # Root level update
            # For root level changes, use the new_value directly
            data = command.new_value.copy() if isinstance(command.new_value, dict) else command.new_value
        else:
            # For nested changes, navigate to the correct location
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
            print("No commands to undo")
            return
            
        self.is_executing = True
        command = self.undo_stack.pop()
        print(f"Undoing command for file: {command.file_path}, path: {command.data_path}")
        
        # Get current data and update it
        data = self.get_file_data(command.file_path)
        if data is not None:
            command.undo()
            
            # Update the stored data
            if not command.data_path:  # Root level update
                # For root level changes, use the old_value directly
                data = command.old_value.copy() if isinstance(command.old_value, dict) else command.old_value
            else:
                # For nested changes, navigate to the correct location
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
        print(f"Marked {command.file_path} as modified after undo")
            
        self.is_executing = False
        print(f"Modified files after undo: {self.modified_files}")
        
    def redo(self) -> None:
        """Redo the last undone command"""
        if not self.redo_stack:
            print("No commands to redo")
            return
            
        self.is_executing = True
        command = self.redo_stack.pop()
        print(f"Redoing command for file: {command.file_path}, path: {command.data_path}")
        
        # Get current data and update it
        data = self.get_file_data(command.file_path)
        if data is not None:
            command.redo()
            
            # Update the stored data
            if not command.data_path:  # Root level update
                # For root level changes, use the new_value directly
                data = command.new_value.copy() if isinstance(command.new_value, dict) else command.new_value
            else:
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
        print(f"Marked {command.file_path} as modified after redo")
        
        self.is_executing = False
        print(f"Modified files after redo: {self.modified_files}")
        
    def can_undo(self) -> bool:
        """Check if there are commands that can be undone"""
        return len(self.undo_stack) > 0
        
    def can_redo(self) -> bool:
        """Check if there are commands that can be redone"""
        return len(self.redo_stack) > 0
        
    def has_unsaved_changes(self) -> bool:
        """Check if there are any unsaved changes"""
        has_changes = len(self.modified_files) > 0
        print(f"Checking for unsaved changes: {has_changes} (modified files: {self.modified_files})")
        return has_changes
    
    def mark_all_saved(self) -> None:
        """Mark all changes as saved"""
        self.modified_files.clear()
        print("Marked all changes as saved")
        
    def get_modified_files(self) -> Set[Path]:
        """Get the set of files that have unsaved changes"""
        print(f"Getting modified files: {self.modified_files}")
        return self.modified_files.copy()
        
    def save_file(self, file_path: Path, data: dict) -> bool:
        """Save changes to a specific file"""
        try:
            print(f"Saving file: {file_path}")
            
            # Ensure parent directory exists
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Save the file
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
            
            # Remove from modified files
            self.modified_files.discard(file_path)
            print(f"Successfully saved changes to {file_path}")
            print(f"Modified files after save: {self.modified_files}")
            return True
        except Exception as e:
            print(f"Error saving file {file_path}: {str(e)}")
            return False
            
    def clear_modified_state(self, file_path: Path) -> None:
        """Clear the modified state for a file without saving"""
        self.modified_files.discard(file_path)
        
class CompositeCommand:
    """Command that combines multiple commands into one atomic operation"""
    def __init__(self, commands):
        self.commands = commands
        # For logging purposes, use the first command's attributes
        if commands and hasattr(commands[0], 'file_path'):
            try:
                self.file_path = commands[0].file_path
                self.data_path = commands[0].data_path
                self.old_value = commands[0].old_value
                self.new_value = commands[0].new_value
                self.source_widget = commands[0].source_widget if hasattr(commands[0], 'source_widget') else None
            except Exception as e:
                print(f"Error initializing composite command: {str(e)}")
        
    def redo(self):
        """Execute the command (called by command stack)"""
        try:
            # Execute transform command first to create new widget
            if len(self.commands) > 1:
                self.commands[1].execute()
            # Then update the value
            if self.commands:
                self.commands[0].redo()
        except Exception as e:
            print(f"Error executing composite command redo: {str(e)}")
        
    def undo(self):
        """Undo the command (called by command stack)"""
        try:
            # Undo in reverse order
            for cmd in reversed(self.commands):
                cmd.undo()
        except Exception as e:
            print(f"Error executing composite command undo: {str(e)}")
      
class TransformWidgetCommand:
    """Command for transforming a widget from one type to another"""
    def __init__(self, gui, widget, old_value, new_value):
        self.gui = gui
        self.old_value = old_value
        self.new_value = new_value
        
        # Store widget properties and references
        self.parent = widget.parent()
        self.parent_layout = self.parent.layout()
        if not self.parent_layout:
            self.parent_layout = QVBoxLayout(self.parent)
            self.parent_layout.setContentsMargins(0, 0, 0, 0)
            self.parent_layout.setSpacing(4)
            
        # Create a container widget to hold our transformed widgets
        self.container = QWidget(self.parent)
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(0, 0, 0, 0)
        self.container_layout.setSpacing(0)
        
        # Store original widget index and properties
        self.widget_index = self.parent_layout.indexOf(widget)
        self.data_path = widget.property("data_path")
        self.is_base_game = widget.property("is_base_game") or False
        
        # For array items, we'll add to the existing layout instead of replacing
        self.is_array_item = old_value is None and isinstance(widget, QWidget) and widget.layout() is not None
        if not self.is_array_item:
            # Move the original widget into our container
            widget.setParent(self.container)
            self.container_layout.addWidget(widget)
            
            # Add container to parent layout
            self.parent_layout.insertWidget(self.widget_index, self.container)
        else:
            # For array items, we'll use the existing widget and layout
            self.container = widget
            self.container_layout = widget.layout()
            
        # Additional properties for array items
        self.file_path = None
        self.source_widget = None
        self.schema = None
        self.array_data = None
        self.new_array = None
        self.added_widget = None
        
        # Store information for undo/redo of texture transformations
        self.is_texture = False
        self.old_container = None
        self.new_container = None
        self.parent_container = None
        self.container_index = -1
        self.preserved_index_label = None

    def replace_widget(self, new_widget):
        """Replace all widgets in container with new widget"""
        if not self.container_layout or not new_widget:
            return None
            
        if not self.is_array_item:
            # Clear all widgets from container
            while self.container_layout.count():
                item = self.container_layout.takeAt(0)
                if item.widget():
                    item.widget().hide()
                    item.widget().deleteLater()
                    
            # Add new widget to container
            self.container_layout.addWidget(new_widget)
        else:
            # For array items, just add the new widget to the existing layout
            self.container_layout.addWidget(new_widget)
            self.added_widget = new_widget  # Track the added widget for array items
            
        return new_widget
        
    def execute(self):
        """Execute the widget transformation"""
        try:
            # Get schema and create new widget
            schema = self.gui.get_schema_for_path(self.data_path)
            if not schema:
                return None
                
            # Create new widget
            new_widget = self.gui.create_widget_for_value(
                self.new_value,
                schema,
                False,  # is_base_game
                self.data_path
            )

            if new_widget:
                # Store transformation info
                self.is_texture = True  # We'll treat all transforms the same way
                self.parent_container = self.container.parent() if self.container else None
                
                # For all transformations, preserve the parent container
                if self.parent_container and self.parent_container.parent():
                    parent = self.parent_container.parent()
                    if parent and parent.layout():
                        # Find our container's index
                        index = -1
                        for i in range(parent.layout().count()):
                            if parent.layout().itemAt(i).widget() == self.parent_container:
                                index = i
                                break
                        
                        if index >= 0:
                            # Store container index for undo/redo
                            self.container_index = index
                            
                            # Create a new container to hold the index label and new widget
                            container = QWidget()
                            container_layout = QHBoxLayout(container)
                            container_layout.setContentsMargins(0, 0, 0, 0)
                            container_layout.setSpacing(4)

                            # Store old container for undo
                            self.old_container = parent.layout().itemAt(index).widget()

                            # Check if we have an index label to preserve
                            existing_index_label = None
                            if self.old_container and self.old_container.layout():
                                for i in range(self.old_container.layout().count()):
                                    widget = self.old_container.layout().itemAt(i).widget()
                                    if isinstance(widget, QLabel) and widget.text().startswith('[') and widget.text().endswith(']'):
                                        existing_index_label = widget
                                        break

                            # Store preserved index label
                            self.preserved_index_label = existing_index_label

                            # Remove old container
                            item = parent.layout().takeAt(index)
                            if item.widget():
                                # If we found an index label, remove it from old container before deletion
                                if existing_index_label:
                                    existing_index_label.setParent(None)
                                item.widget().hide()
                                # Don't delete old container yet, we need it for undo
                                self.old_container = item.widget()
                                self.old_container.hide()

                            # If we have an index label, add it to new container
                            if existing_index_label:
                                container_layout.addWidget(existing_index_label)
                            
                            # Add new widget and stretch
                            container_layout.addWidget(new_widget)
                            container_layout.addStretch()
                            
                            # Store new container for undo/redo
                            self.new_container = container
                            
                            # Add new container at same index
                            parent.layout().insertWidget(index, container)
                            return container
                
                # Fallback for cases where we can't find the parent container
                return self.replace_widget(new_widget)
                
        except Exception as e:
            print(f"Error executing transform widget command: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
        
    def undo(self):
        """Undo the transformation"""
        try:
            if self.is_texture and self.old_container and self.parent_container and self.parent_container.parent():
                parent = self.parent_container.parent()
                if parent and parent.layout():
                    # Remove new container
                    for i in range(parent.layout().count()):
                        if parent.layout().itemAt(i).widget() == self.new_container:
                            item = parent.layout().takeAt(i)
                            if item.widget():
                                # Preserve index label if it exists
                                if self.preserved_index_label:
                                    self.preserved_index_label.setParent(None)
                                item.widget().hide()
                                item.widget().deleteLater()
                            break
                    
                    # Show and restore old container
                    self.old_container.show()
                    if self.preserved_index_label:
                        # Find the right spot to add the index label back
                        if self.old_container.layout():
                            self.old_container.layout().insertWidget(0, self.preserved_index_label)
                    
                    # Add old container back at original index
                    parent.layout().insertWidget(self.container_index, self.old_container)
            else:
                # Handle non-texture undo
                new_widget = self.gui.create_widget_for_value(
                    self.old_value,
                    {"type": "string"},
                    self.is_base_game,
                    self.data_path
                )
                return self.replace_widget(new_widget)
        except Exception as e:
            print(f"Error undoing transform command: {str(e)}")
            import traceback
            traceback.print_exc()

    def redo(self):
        """Redo the transformation"""
        try:
            if self.is_texture and self.new_container and self.parent_container and self.parent_container.parent():
                parent = self.parent_container.parent()
                if parent and parent.layout():
                    # Remove old container
                    for i in range(parent.layout().count()):
                        if parent.layout().itemAt(i).widget() == self.old_container:
                            item = parent.layout().takeAt(i)
                            if item.widget():
                                if self.preserved_index_label:
                                    self.preserved_index_label.setParent(None)
                                item.widget().hide()
                            break
                    
                    # Show and restore new container
                    self.new_container.show()
                    if self.preserved_index_label:
                        # Find the right spot to add the index label back
                        if self.new_container.layout():
                            self.new_container.layout().insertWidget(0, self.preserved_index_label)
                    
                    # Add new container back at original index
                    parent.layout().insertWidget(self.container_index, self.new_container)
                    return self.new_container
            else:
                # Handle non-texture redo
                return self.execute()
        except Exception as e:
            print(f"Error redoing transform command: {str(e)}")
            import traceback
            traceback.print_exc()
            return None

class EditValueCommand(Command):
    """Command for editing a value in a data structure"""
    def __init__(self, file_path: Path, data_path: list, old_value: any, new_value: any, 
                 update_widget_func: Callable, update_data_func: Callable):
        super().__init__(file_path, data_path, old_value, new_value)
        self.update_widget_func = update_widget_func
        self.update_data_func = update_data_func
        print(f"Created EditValueCommand for {file_path} at path {data_path}")
        print(f"Old value: {old_value}, New value: {new_value}")
        
    def update_widget_safely(self, value: any):
        """Try to update widget, but don't fail if widget is gone"""
        try:
            self.update_widget_func(value)
        except RuntimeError as e:
            # Widget was deleted, just log and continue
            print(f"Widget was deleted, skipping UI update: {str(e)}")
        
    def undo(self):
        """Restore the old value"""
        print(f"Undoing EditValueCommand for {self.file_path} at path {self.data_path}")
        self.update_widget_safely(self.old_value)
        self.update_data_func(self.data_path, self.old_value)
        
    def redo(self):
        """Apply the new value"""
        print(f"Redoing EditValueCommand for {self.file_path} at path {self.data_path}")
        self.update_widget_safely(self.new_value)
        self.update_data_func(self.data_path, self.new_value)

class AddArrayItemCommand(TransformWidgetCommand):
           
    def execute(self):
        """Execute the widget transformation"""
        try:
            # Get schema and create new widget
            schema = self.gui.get_schema_for_path(self.data_path)
            if not schema:
                return None
            
            # If complex type, use create_widget_for_schema
            if schema.get("type") == "object" or schema.get("type") == "array":
                new_widget = self.gui.create_widget_for_schema(
                    self.new_value,
                    schema,
                    False,  # is_base_game
                    self.data_path
                )
            else:
                # Create new widget
                new_widget = self.gui.create_widget_for_value(
                    self.new_value,
                    schema,
                    False,  # is_base_game
                    self.data_path
                )
            
            if new_widget:
                # If this is an array item, add an index label
                if self.data_path and isinstance(self.data_path[-1], int):
                    container = QWidget()
                    container_layout = QHBoxLayout(container)
                    container_layout.setContentsMargins(0, 0, 0, 0)
                    container_layout.setSpacing(4)
                    
                    # Create updated array data that includes the new item
                    updated_array = self.array_data.copy()
                    if len(updated_array) <= self.data_path[-1]:
                        # Extend array if needed
                        while len(updated_array) <= self.data_path[-1]:
                            updated_array.append(None)
                    updated_array[self.data_path[-1]] = self.new_value
                    
                    # Store the updated array for undo
                    self.updated_array = updated_array
                    
                    # Add index label first
                    index_label = QLabel(f"[{self.data_path[-1]}]")
                    index_label.setProperty("data_path", self.data_path)
                    index_label.setProperty("array_data", updated_array)  # Use updated array data
                    index_label.setStyleSheet("QLabel { color: gray; }")
                    
                    # Add context menu to index label
                    index_label.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
                    index_label.customContextMenuRequested.connect(
                        lambda pos, w=index_label: self.gui.show_array_item_menu(w, pos)
                    )
                    
                    container_layout.addWidget(index_label)
                    
                    # Then add the new widget
                    container_layout.addWidget(new_widget)
                    container_layout.addStretch()
                    
                    # Store references to the widgets we'll need for undo
                    self.added_container = container
                    self.added_index_label = index_label
                    self.added_value_widget = new_widget
                    
                    # Try to find the array's content layout if our stored reference is invalid
                    def find_array_content_layout():
                        """Find the array's content layout in the UI"""
                        # Find the schema view first
                        schema_view = None
                        for widget in self.gui.findChildren(QWidget):
                            if (hasattr(widget, 'property') and 
                                widget.property("file_path") == str(self.file_path)):
                                schema_view = widget
                                break
                        
                        if not schema_view:
                            return None
                            
                        # Find the array's toggle button by looking for a QToolButton with matching data path
                        array_path = self.data_path[:-1]  # Remove the index
                        array_button = None
                        for widget in schema_view.findChildren(QToolButton):
                            if widget.property("data_path") == array_path:
                                array_button = widget
                                break
                        
                        if not array_button:
                            return None
                            
                        # Get the array's content widget (sibling of the button)
                        array_container = array_button.parent()
                        if not array_container or not array_container.layout():
                            return None
                            
                        content_widget = None
                        container_layout = array_container.layout()
                        for i in range(container_layout.count()):
                            widget = container_layout.itemAt(i).widget()
                            if widget != array_button:
                                content_widget = widget
                                break
                                
                        if not content_widget or not content_widget.layout():
                            return None
                            
                        return content_widget.layout()
                    
                    # Try to use the stored container first
                    try:
                        if self.container and self.container.layout():
                            self.replace_widget(container)
                            return new_widget
                    except (RuntimeError, AttributeError):
                        print("Stored container reference is invalid, trying to find layout in UI")
                        
                    # If stored container is invalid, try to find it in the UI
                    content_layout = find_array_content_layout()
                    if content_layout:
                        content_layout.addWidget(container)
                        return new_widget
                else:
                    # Just replace the widget normally
                    self.replace_widget(new_widget)
                
                return new_widget
                
        except Exception as e:
            print(f"Error executing transform widget command: {str(e)}")
            import traceback
            traceback.print_exc()
            return None

    def undo(self):
        """Undo the array item addition"""
        try:
            print("Undoing array item addition")
            print(f"Data path: {self.data_path}")
            print(f"Original array data: {self.array_data}")
            
            # Update the data first - restore original array
            if self.data_path is not None:
                array_path = self.data_path[:-1]  # Remove the index
                # Remove the item from the array by restoring the original array
                print(f"Restoring array at path {array_path} to {self.array_data}")
                self.gui.update_data_value(array_path, self.array_data)
            
            def find_widget_in_ui():
                """Find the widget in the UI by its data path"""
                try:
                    # Find the schema view first
                    schema_view = None
                    for widget in self.gui.findChildren(QWidget):
                        if (hasattr(widget, 'property') and 
                            widget.property("file_path") == str(self.file_path)):
                            schema_view = widget
                            break
                    
                    if not schema_view:
                        print("Could not find schema view")
                        return None
                        
                    # Find the array container by looking for a QToolButton with the array name
                    array_button = None
                    array_path = self.data_path[:-1]  # Remove the index
                    for widget in schema_view.findChildren(QToolButton):
                        btn_text = widget.text()
                        # Remove count suffix if present (e.g., "Planet Levels (4)" -> "Planet Levels")
                        btn_text = btn_text.split(" (")[0]
                        
                        # Try different text formats
                        possible_texts = [
                            array_path[-1],  # planet_levels
                            array_path[-1].replace("_", " "),  # planet levels
                            array_path[-1].replace("_", " ").title(),  # Planet Levels
                            array_path[-1].replace("_", " ").lower(),  # planet levels
                            array_path[-1].lower(),  # planetlevels
                            array_path[-1].title()  # PlanetLevels
                        ]
                        if any(text == btn_text for text in possible_texts):
                            array_button = widget
                            break
                            
                    if not array_button:
                        print("Could not find array button")
                        return None
                        
                    # Get the array content widget (sibling of the button)
                    array_container = array_button.parent()
                    if not array_container or not array_container.layout():
                        return None
                        
                    content_widget = None
                    container_layout = array_container.layout()
                    for i in range(container_layout.count()):
                        widget = container_layout.itemAt(i).widget()
                        if widget != array_button:
                            content_widget = widget
                            break
                            
                    if not content_widget or not content_widget.layout():
                        return None
                        
                    # Find the item widget by its index
                    content_layout = content_widget.layout()
                    item_index = self.data_path[-1]
                    if content_layout.count() > item_index:
                        return content_layout.itemAt(item_index).widget()
                        
                except Exception as e:
                    print(f"Error finding widget in UI: {str(e)}")
                return None
            
            # Try to use the stored widget reference first
            widget_to_remove = None
            try:
                if self.added_widget and self.added_widget.parent():
                    widget_to_remove = self.added_widget
            except RuntimeError:  # Widget was deleted
                print("Stored widget reference is stale, searching in UI...")
                widget_to_remove = find_widget_in_ui()
            
            # Remove the widget
            if widget_to_remove:
                if widget_to_remove.parent():
                    layout = widget_to_remove.parent().layout()
                    if layout:
                        # Find and remove our widget
                        for i in range(layout.count()):
                            if layout.itemAt(i).widget() == widget_to_remove:
                                item = layout.takeAt(i)
                                if item.widget():
                                    item.widget().hide()
                                    item.widget().deleteLater()
                                break
            
            self.added_widget = None
            
        except Exception as e:
            print(f"Error undoing array item addition: {str(e)}")
            import traceback
            traceback.print_exc()

class DeleteArrayItemCommand(Command):
    """Command for deleting an item from an array"""
    def __init__(self, gui, array_widget, array_data, item_index):
        # Store the old and new array values
        old_array = array_data.copy()
        new_array = array_data.copy()
        new_array.pop(item_index)
        
        super().__init__(None, None, old_array, new_array)  # File path and data path set later
        self.gui = gui
        self.array_widget = array_widget
        self.item_index = item_index
        
    def execute(self):
        """Execute the array item deletion"""
        try:
            # Update the data
            if self.data_path is not None:
                self.gui.update_data_value(self.data_path, self.new_value)
            
            # Get the array's content layout
            content_layout = self.array_widget.layout()
            if not content_layout:
                return
            
            # Remove the item widget at the specified index
            if content_layout.count() > self.item_index:
                item = content_layout.takeAt(self.item_index)
                if item.widget():
                    item.widget().hide()
                    item.widget().deleteLater()
            
            # Update remaining indices
            for i in range(self.item_index, content_layout.count()):
                item_container = content_layout.itemAt(i).widget()
                if item_container:
                    item_layout = item_container.layout()
                    if item_layout and item_layout.count() > 0:
                        # First widget should be the index label
                        index_label = item_layout.itemAt(0).widget()
                        if isinstance(index_label, QLabel):
                            index_label.setText(f"[{i}]")
                            # Update data path property
                            data_path = index_label.property("data_path")
                            if data_path:
                                data_path = data_path[:-1] + [i]  # Update index
                                index_label.setProperty("data_path", data_path)
            
        except Exception as e:
            print(f"Error executing delete array item command: {str(e)}")
            return None
            
    def undo(self):
        """Undo the array item deletion"""
        try:
            # Update the data
            if self.data_path is not None:
                self.gui.update_data_value(self.data_path, self.old_value)
            
            # Find the collapsible widget (parent of our array widget)
            collapsible_widget = None
            current = self.array_widget
            while current:
                # Look for a widget that has a QToolButton as its first child
                layout = current.layout()
                if layout and layout.count() > 0:
                    first_item = layout.itemAt(0)
                    if first_item.widget() and isinstance(first_item.widget(), QToolButton):
                        collapsible_widget = current
                        break
                current = current.parent()
            
            if not collapsible_widget:
                print("Could not find collapsible widget")
                return
                
            # Get the parent of the collapsible widget
            parent = collapsible_widget.parent()
            if not parent:
                return
                
            parent_layout = parent.layout()
            if not parent_layout:
                return
                
            # Find the collapsible widget's index in its parent's layout
            widget_index = -1
            for i in range(parent_layout.count()):
                if parent_layout.itemAt(i).widget() == collapsible_widget:
                    widget_index = i
                    break
                    
            if widget_index == -1:
                return
                
            # Get schema and create new array widget
            schema = self.gui.get_schema_for_path(self.data_path)
            if not schema:
                return
                
            # Create new widget for the array
            new_widget = self.gui.create_widget_for_schema(
                self.old_value,
                schema,
                False,  # is_base_game
                self.data_path
            )
            
            if new_widget:
                # First hide the old widget
                collapsible_widget.hide()
                
                # Remove it from the layout
                old_item = parent_layout.takeAt(widget_index)
                if old_item:
                    old_widget = old_item.widget()
                    if old_widget:
                        old_widget.setParent(None)
                        old_widget.deleteLater()
                
                # Add new widget at the same position
                parent_layout.insertWidget(widget_index, new_widget)
                
                # Find and click the toggle button to open the array
                new_layout = new_widget.layout()
                if new_layout and new_layout.count() > 0:
                    toggle_btn = new_layout.itemAt(0).widget()
                    if isinstance(toggle_btn, QToolButton):
                        toggle_btn.setChecked(True)  # This will trigger the toggled signal and open the array
                
                # Update our reference to point to the content widget of the new array
                if new_layout and new_layout.count() > 1:  # Should have toggle button and content
                    content_widget = new_layout.itemAt(1).widget()
                    if content_widget:
                        self.array_widget = content_widget
                
        except Exception as e:
            print(f"Error undoing delete array item command: {str(e)}")
            
    def redo(self):
        """Redo the array item deletion"""
        try:
            return self.execute()
        except Exception as e:
            print(f"Error redoing delete array item command: {str(e)}")
            return None

class AddPropertyCommand(Command):
    """Command for adding a property to an object"""
    def __init__(self, gui, widget, old_value, new_value):
        # For root properties, old_value should be the entire data structure before the property was added
        # and new_value should be the entire data structure with the property added
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
            # For root properties, update the data and refresh the schema view
            if self.data_path == []:
                # Update the command stack data first
                self.gui.command_stack.update_file_data(self.file_path, self.new_value)
                # Then update the data value (this will trigger any callbacks)
                self.gui.update_data_value(self.data_path, self.new_value)
                # Finally refresh the schema view
                self.gui.refresh_schema_view(self.file_path)
                return
                
            # For non-root properties, update the data normally
            if self.data_path is not None:
                self.gui.update_data_value(self.data_path, self.new_value)
                
            # Create and add the widget (only for non-root properties)
            if self.schema and self.prop_name and self.parent_layout:
                # Create container for the new property
                row_widget = QWidget()
                row_layout = QHBoxLayout(row_widget)
                row_layout.setContentsMargins(0, 0, 0, 0)
                row_layout.setSpacing(4)
                row_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
                
                # Get default value
                default_value = self.gui.get_default_value(self.schema)
                
                # Create appropriate widget based on schema type
                if self.schema.get("type") == "array":
                    # For arrays, use create_widget_for_schema directly (it creates its own header)
                    value_widget = self.gui.create_widget_for_schema(
                        default_value,
                        self.schema,
                        False,  # is_base_game
                        self.data_path + [self.prop_name]
                    )
                    if value_widget:
                        # No need for row_widget, just add directly to parent
                        self.parent_layout.addWidget(value_widget)
                        self.added_widget = value_widget
                elif self.schema.get("type") == "object":
                    # For objects, create a collapsible section with our own label
                    group_widget = QWidget()
                    group_layout = QVBoxLayout(group_widget)
                    group_layout.setContentsMargins(0, 0, 0, 0)
                    
                    # Create collapsible button
                    toggle_btn = QToolButton()
                    toggle_btn.setStyleSheet("QToolButton { border: none; }")
                    toggle_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
                    toggle_btn.setArrowType(Qt.ArrowType.RightArrow)
                    toggle_btn.setText(self.prop_name.replace("_", " ").title())
                    toggle_btn.setCheckable(True)
                    
                    # Make button bold if property is required
                    parent_schema = self.gui.get_schema_for_path(self.data_path)
                    if parent_schema and "required" in parent_schema:
                        if self.prop_name in parent_schema["required"]:
                            toggle_btn.setStyleSheet("QToolButton { border: none; font-weight: bold; }")
                    
                    # Store data path and value for context menu
                    toggle_btn.setProperty("data_path", self.data_path + [self.prop_name])
                    toggle_btn.setProperty("original_value", default_value)
                    
                    # Add context menu
                    toggle_btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
                    toggle_btn.customContextMenuRequested.connect(
                        lambda pos, w=toggle_btn: self.gui.show_context_menu(w, pos, default_value)
                    )
                    
                    # Create content widget
                    content = QWidget()
                    content_layout = QVBoxLayout(content)
                    content_layout.setContentsMargins(20, 0, 0, 0)
                    
                    # Create the object widget
                    value_widget = self.gui.create_widget_for_schema(
                        default_value,
                        self.schema,
                        False,  # is_base_game
                        self.data_path + [self.prop_name]
                    )
                    if value_widget:
                        content_layout.addWidget(value_widget)
                        content.setVisible(False)  # Initially collapsed
                        
                        # Connect toggle button
                        def update_arrow_state(checked):
                            toggle_btn.setArrowType(Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow)
                        
                        toggle_btn.toggled.connect(content.setVisible)
                        toggle_btn.toggled.connect(update_arrow_state)
                        
                        # Add to layout
                        group_layout.addWidget(toggle_btn)
                        group_layout.addWidget(content)
                        self.parent_layout.addWidget(group_widget)
                        self.added_widget = group_widget
                else:
                    # For simple values, use create_widget_for_value with a label
                    display_name = self.prop_name.replace("_", " ").title()
                    label = QLabel(f"{display_name}:")
                    
                    # Make label bold if property is required
                    parent_schema = self.gui.get_schema_for_path(self.data_path)
                    if parent_schema and "required" in parent_schema:
                        if self.prop_name in parent_schema["required"]:
                            label.setStyleSheet("QLabel { font-weight: bold; }")
                    
                    # Add context menu to label
                    label.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
                    label.setProperty("data_path", self.data_path + [self.prop_name])
                    label.customContextMenuRequested.connect(
                        lambda pos, w=label, v=default_value: self.gui.show_context_menu(w, pos, v)
                    )
                    
                    row_layout.addWidget(label)
                    
                    value_widget = self.gui.create_widget_for_value(
                        default_value,
                        self.schema,
                        False,  # is_base_game
                        self.data_path + [self.prop_name]
                    )
                    if value_widget:
                        row_layout.addWidget(value_widget)
                        row_layout.addStretch()
                        
                        # Add row to parent layout
                        self.parent_layout.addWidget(row_widget)
                        self.added_widget = row_widget
                
        except Exception as e:
            print(f"Error executing add property command: {str(e)}")
            return None
            
    def undo(self):
        """Undo the property addition"""
        try:
            # For root properties, update the data and refresh the schema view
            if self.data_path == []:
                # Update the command stack data first
                self.gui.command_stack.update_file_data(self.file_path, self.old_value)
                # Then update the data value (this will trigger any callbacks)
                self.gui.update_data_value([], self.old_value)
                # Finally refresh the schema view
                self.gui.refresh_schema_view(self.file_path)
                return True

            # For non-root properties, continue with normal undo
            # Update the data first
            if self.data_path is not None:
                print(f"Undoing deletion at path: {self.data_path}")
                self.gui.update_data_value(self.data_path, self.old_value)
            
            # If we have the added widget, try to remove it
            if self.added_widget:
                self.added_widget.setParent(None)
                self.added_widget = None
            
            return True
            
        except Exception as e:
            print(f"Error undoing add property command: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
            
    def redo(self):
        """Redo the property addition"""
        try:
            return self.execute()
        except Exception as e:
            print(f"Error redoing add property command: {str(e)}")
            return None

class DeletePropertyCommand(Command):
    """Command for deleting a property from an object"""
    def __init__(self, gui, property_widget, property_name, parent_data):
        # Strip off array index suffix if present (e.g., "ability_created_units_(1)" -> "ability_created_units")
        self.property_name = property_name.split("_(")[0]
        
        # Get the full data path from the widget
        data_path = property_widget.property("data_path")
        if not data_path:
            # Try parent widget if this one doesn't have the path
            parent = property_widget.parent()
            if parent:
                data_path = parent.property("data_path")
        
        print(f"Full data path from widget: {data_path}")
        print(f"Property name after stripping suffix: {self.property_name}")
        
        # Store the old and new values
        if data_path:
            # Navigate to the parent object
            current = gui.command_stack.get_file_data(gui.get_schema_view_file_path(property_widget))
            parent_path = data_path[:-1]  # All but the last element
            print(f"Parent path for data lookup: {parent_path}")
            
            for part in parent_path:
                if isinstance(current, (dict, list)):
                    current = current[part]
            
            # Now current is the parent object containing our property
            if isinstance(current, dict) and self.property_name in current:
                old_data = current.copy()
                new_data = current.copy()
                del new_data[self.property_name]
            else:
                old_data = parent_data.copy()
                new_data = parent_data.copy()
                if self.property_name in new_data:
                    del new_data[self.property_name]
        else:
            # For root properties, get the entire data structure
            file_path = gui.get_schema_view_file_path(property_widget)
            if file_path:
                old_data = gui.command_stack.get_file_data(file_path)
                if old_data:
                    old_data = old_data.copy()
                    new_data = old_data.copy()
                    if self.property_name in new_data:
                        del new_data[self.property_name]
                else:
                    old_data = parent_data.copy()
                    new_data = parent_data.copy()
                    if self.property_name in new_data:
                        del new_data[self.property_name]
            else:
                old_data = parent_data.copy()
                new_data = parent_data.copy()
                if self.property_name in new_data:
                    del new_data[self.property_name]
        
        super().__init__(gui.get_schema_view_file_path(property_widget), data_path[:-1], old_data, new_value=new_data)
        self.gui = gui
        self.property_widget = property_widget
        self.full_path = data_path  # Store the complete path including property name
        self.removed_widget = None  # Store the removed widget for undo
        
    def execute(self):
        """Execute the property deletion"""
        try:
            print(f"Executing delete property command for {self.property_name}")
            print(f"Full path: {self.full_path}")
            print(f"Parent path for update: {self.data_path}")

            # For root properties, update the data and refresh the schema view
            if not self.data_path or self.data_path == []:
                # Update the command stack data first
                self.gui.command_stack.update_file_data(self.file_path, self.new_value)
                # Then update the data value (this will trigger any callbacks)
                self.gui.update_data_value([], self.new_value)
                # Finally refresh the schema view
                self.gui.refresh_schema_view(self.file_path)
                return True

            # For non-root properties, continue with normal deletion
            # Remove the property from the data
            if self.data_path != []:
                if self.full_path[-1] in self.new_value:
                    self.new_value.pop(self.full_path[-1])
            else:
                if self.full_path[0] in self.new_value:
                    self.new_value.pop(self.full_path[0])
                
            # Update the data
            if self.data_path is not None:
                print(f"Updating data value at path: {self.data_path}")
                self.gui.update_data_value(self.data_path, self.new_value)
            
            # Find the widget to remove
            schema_view = None
            for widget in self.gui.findChildren(QWidget):
                if (hasattr(widget, 'property') and 
                    widget.property("file_path") == str(self.file_path)):
                    schema_view = widget
                    break

            if not schema_view:
                print("Could not find schema view")
                return True

            # For array properties, we need to find the array's collapsible section
            if isinstance(self.property_widget, QToolButton):
                # The property widget is already the collapsible button
                collapsible_widget = self.property_widget.parent()
            else:
                # Find the collapsible section by looking for a QToolButton with the property name
                collapsible_button = None
                for widget in schema_view.findChildren(QToolButton):
                    btn_text = widget.text()
                    # Remove count suffix if present
                    btn_text = btn_text.split(" (")[0]
                    
                    # Try different text formats
                    possible_texts = [
                        self.property_name,  # original
                        self.property_name.replace("_", " "),  # spaces
                        self.property_name.replace("_", " ").title(),  # Title Case
                        self.property_name.replace("_", " ").lower(),  # lower case
                        self.property_name.lower(),  # lowercase
                        self.property_name.title()  # Title
                    ]
                    if any(text == btn_text for text in possible_texts):
                        collapsible_button = widget
                        break
                
                if collapsible_button:
                    collapsible_widget = collapsible_button.parent()
                else:
                    # If we can't find the collapsible button, try to find the property's row widget
                    for widget in schema_view.findChildren(QWidget):
                        if (hasattr(widget, 'property') and 
                            widget.property("data_path") == self.full_path):
                            collapsible_widget = widget.parent()
                            break

            if not collapsible_widget:
                print("Could not find widget to remove")
                return True

            # Store the widget and its parent for undo
            self.removed_widget = collapsible_widget
            self.removed_parent = collapsible_widget.parent()
            self.removed_layout = self.removed_parent.layout()
            self.removed_index = self.removed_layout.indexOf(collapsible_widget)

            # Hide and remove the widget
            collapsible_widget.hide()
            collapsible_widget.setParent(None)  # Detach but don't delete
            
            return True
            
        except Exception as e:
            print(f"Error executing delete property command: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
            
    def undo(self):
        """Undo the property deletion"""
        try:
            # For root properties, update the data and refresh the schema view
            if not self.data_path or self.data_path == []:
                # Update the command stack data first
                self.gui.command_stack.update_file_data(self.file_path, self.old_value)
                # Then update the data value (this will trigger any callbacks)
                self.gui.update_data_value([], self.old_value)
                # Finally refresh the schema view
                self.gui.refresh_schema_view(self.file_path)
                return True

            # For non-root properties, continue with normal undo
            # Update the data first
            if self.data_path is not None:
                print(f"Undoing deletion at path: {self.data_path}")
                self.gui.update_data_value(self.data_path, self.old_value)
            
            # If we have the removed widget, try to restore it
            if (self.removed_widget and self.removed_parent and 
                self.removed_layout and self.removed_index >= 0):
                print("Restoring removed widget")
                self.removed_widget.setParent(self.removed_parent)
                self.removed_layout.insertWidget(self.removed_index, self.removed_widget)
                self.removed_widget.show()
            else:
                print("No stored widget to restore, recreating from schema")
                # Get schema and create new widget
                schema = self.gui.get_schema_for_path(self.data_path)
                if schema:
                    new_widget = self.gui.create_widget_for_schema(
                        self.old_value,
                        schema,
                        False,  # is_base_game
                        self.data_path
                    )
                    if new_widget:
                        # Find parent widget to add to
                        schema_view = None
                        for widget in self.gui.findChildren(QWidget):
                            if (hasattr(widget, 'property') and 
                                widget.property("file_path") == str(self.file_path)):
                                schema_view = widget
                                break
                        
                        if schema_view:
                            # Find the parent container
                            parent_path = self.data_path
                            parent_container = None
                            for widget in schema_view.findChildren(QWidget):
                                if (hasattr(widget, 'property') and 
                                    widget.property("data_path") == parent_path):
                                    parent_container = widget
                                    break
                            
                            if parent_container and parent_container.layout():
                                parent_container.layout().addWidget(new_widget)
                                new_widget.show()
            
            return True
            
        except Exception as e:
            print(f"Error undoing delete property command: {str(e)}")
            return False
            
    def redo(self):
        """Redo the property deletion"""
        return self.execute()

    def refresh_views(self):
        """Refresh any schema views affected by this command"""
        if hasattr(self, 'file_path') and self.file_path:
            self.gui.refresh_schema_view(self.file_path)

class CreateFileFromCopy(Command):
    """Command for creating a copy of a file and updating manifests"""
    def __init__(self, gui, source_file: str, source_type: str, new_name: str, overwrite: bool = False):
        super().__init__(None, None, None, None)  # We don't use the standard command values
        self.gui = gui
        self.source_file = source_file  # Original file ID (e.g. "scout_frigate")
        self.source_type = source_type  # File type (e.g. "unit", "weapon")
        self.new_name = new_name  # New file ID for the copy
        self.overwrite = overwrite  # Whether to overwrite an existing mod file
        self.old_manifest_data = None  # Store original manifest data for undo
        self.new_manifest_data = None  # Store new manifest data for redo
        self.created_file_path = None  # Store path of created file
        self.manifest_file_path = None  # Store path of manifest file
        self.source_data = None  # Store the source data for the copy
        
    def prepare(self) -> bool:
        """Prepare the command by gathering necessary data and validating the operation"""
        try:
            # Determine source and target paths
            self.source_data = None
            is_base_game = False

            # Special handling for uniforms files
            if self.source_type == "uniform":
                # Try to get source data from mod first
                mod_file = self.gui.current_folder / "uniforms" / f"{self.source_file}.uniforms"
                base_file = None if not self.gui.base_game_folder else self.gui.base_game_folder / "uniforms" / f"{self.source_file}.uniforms"

                if mod_file.exists():
                    with open(mod_file, 'r', encoding='utf-8') as f:
                        self.source_data = json.load(f)
                    is_base_game = False
                elif base_file and base_file.exists():
                    with open(base_file, 'r', encoding='utf-8') as f:
                        self.source_data = json.load(f)
                    is_base_game = True

                # Create target file path
                self.created_file_path = self.gui.current_folder / "uniforms" / f"{self.new_name}.uniforms"
                
                # No manifest file for uniforms
                self.manifest_file_path = None
            else:
                # Try to get source data from mod first
                if self.source_file in self.gui.manifest_data['mod'].get(self.source_type, {}):
                    self.source_data = self.gui.manifest_data['mod'][self.source_type][self.source_file]
                    is_base_game = False
                # Then try base game
                elif self.source_file in self.gui.manifest_data['base_game'].get(self.source_type, {}):
                    self.source_data = self.gui.manifest_data['base_game'][self.source_type][self.source_file]
                    is_base_game = True
                    
                # Create target file path
                self.created_file_path = self.gui.current_folder / "entities" / f"{self.new_name}.{self.source_type}"
                
                # Create manifest file path
                self.manifest_file_path = self.gui.current_folder / "entities" / f"{self.source_type}.entity_manifest"
                
            if not self.source_data:
                raise ValueError(f"Could not find source file {self.source_file} of type {self.source_type}")
                
            # Check if target exists and we're not overwriting
            if self.created_file_path.exists() and not self.overwrite:
                raise ValueError(f"Target file {self.created_file_path} already exists")
                
            # Load or create manifest data if needed
            if self.manifest_file_path:
                manifest_data = {"ids": []}
                if self.manifest_file_path.exists():
                    with open(self.manifest_file_path, 'r', encoding='utf-8') as f:
                        manifest_data = json.load(f)
                        
                # Store old manifest data for undo (deep copy)
                self.old_manifest_data = json.loads(json.dumps(manifest_data))
                
                # Create new manifest data (deep copy)
                self.new_manifest_data = json.loads(json.dumps(manifest_data))
                if not self.overwrite and self.new_name not in self.new_manifest_data["ids"]:
                    self.new_manifest_data["ids"].append(self.new_name)
                    self.new_manifest_data["ids"].sort()  # Keep IDs sorted
                
            return True
            
        except Exception as e:
            print(f"Error preparing file copy: {str(e)}")
            return False
        
    def execute(self):
        """Execute the file copy operation"""
        try:
            if not self.source_data:
                if not self.prepare():
                    return False
                    
            # Create parent folder if it doesn't exist
            self.created_file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write the new file
            with open(self.created_file_path, 'w', encoding='utf-8') as f:
                json.dump(self.source_data, f, indent=4)
                
            # Write the manifest file if it exists
            if self.manifest_file_path:
                with open(self.manifest_file_path, 'w', encoding='utf-8') as f:
                    json.dump(self.new_manifest_data, f, indent=4)
                
                # Update the GUI's manifest data
                if self.source_type not in self.gui.manifest_data['mod']:
                    self.gui.manifest_data['mod'][self.source_type] = {}
                self.gui.manifest_data['mod'][self.source_type][self.new_name] = self.source_data
            
            # Update the appropriate list based on file type
            self.update_list_for_type()
            
            return True
            
        except Exception as e:
            print(f"Error executing file copy: {str(e)}")
            return False
            
    def undo(self):
        """Undo the file copy operation"""
        try:
            print("Undoing file copy operation")
            # Delete the created file
            if self.created_file_path and self.created_file_path.exists():
                print(f"Deleting created file: {self.created_file_path}")
                self.created_file_path.unlink()
                
            # Restore old manifest data if it exists
            if self.manifest_file_path and self.old_manifest_data:
                print(f"Restoring old manifest data to: {self.manifest_file_path}")
                print(f"Old manifest data: {self.old_manifest_data}")
                with open(self.manifest_file_path, 'w', encoding='utf-8') as f:
                    json.dump(self.old_manifest_data, f, indent=4)
                    
                # Remove from GUI's manifest data
                if self.source_type in self.gui.manifest_data['mod']:
                    print(f"Removing {self.new_name} from GUI manifest data")
                    self.gui.manifest_data['mod'][self.source_type].pop(self.new_name, None)
                
            # Update the appropriate list based on file type
            self.update_list_for_type()
            
            # Remove from command stack's file data
            if self.created_file_path:
                print(f"Removing file data from command stack")
                self.gui.command_stack.file_data.pop(self.created_file_path, None)
            
            # Remove from modified files set
            if self.created_file_path:
                print(f"Removing from modified files set")
                self.gui.command_stack.modified_files.discard(self.created_file_path)
            
            if self.manifest_file_path:
                print(f"Removing manifest from modified files set")
                self.gui.command_stack.modified_files.discard(self.manifest_file_path)
                
                # Update command stack data for manifest file
                print(f"Updating manifest data in command stack")
                self.gui.command_stack.update_file_data(self.manifest_file_path, self.old_manifest_data)
                
            return True
            
        except Exception as e:
            print(f"Error undoing file copy: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
            
    def redo(self):
        """Redo the file copy operation"""
        try:
            return self.execute()
        except Exception as e:
            print(f"Error redoing file copy: {str(e)}")
            return False
            
    def update_list_for_type(self):
        """Update the appropriate list widget based on the file type"""
        try:
            # Special handling for uniforms
            if self.source_type == "uniform":
                self.gui.uniforms_list.clear()
                # Add mod files first
                uniforms_folder = self.gui.current_folder / "uniforms"
                if uniforms_folder.exists():
                    for file in sorted(uniforms_folder.glob("*.uniforms")):
                        item = QListWidgetItem(file.stem)
                        item.setToolTip("Mod version")
                        self.gui.uniforms_list.addItem(item)
                # Then add base game files (grayed out)
                if self.gui.base_game_folder:
                    base_uniforms_folder = self.gui.base_game_folder / "uniforms"
                    if base_uniforms_folder.exists():
                        for file in sorted(base_uniforms_folder.glob("*.uniforms")):
                            # Always add base game files, even if they exist in mod folder
                            item = QListWidgetItem(file.stem)
                            item.setForeground(QColor(150, 150, 150))
                            font = item.font()
                            font.setItalic(True)
                            item.setFont(font)
                            item.setToolTip("Base game version")
                            self.gui.uniforms_list.addItem(item)
                return

            # Special handling for units to filter by type
            if self.source_type == 'unit':
                # Update all units list first
                self.gui.all_units_list.clear()
                # Add mod files first
                for file_id in sorted(self.gui.manifest_data['mod'].get('unit', {})):
                    item = QListWidgetItem(file_id)
                    item.setToolTip("Mod version")
                    self.gui.all_units_list.addItem(item)
                # Then add base game files (grayed out)
                for file_id in sorted(self.gui.manifest_data['base_game'].get('unit', {})):
                    # Always add base game files, even if they exist in mod folder
                    item = QListWidgetItem(file_id)
                    item.setForeground(QColor(150, 150, 150))
                    font = item.font()
                    font.setItalic(True)
                    item.setFont(font)
                    item.setToolTip("Base game version")
                    self.gui.all_units_list.addItem(item)

                # Update buildable units list
                if hasattr(self.gui, 'current_data') and self.gui.current_data:
                    self.gui.units_list.clear()
                    buildable_units = self.gui.current_data.get('buildable_units', [])
                    for unit_id in sorted(buildable_units):
                        # Add mod version if it exists
                        if unit_id in self.gui.manifest_data['mod'].get('unit', {}):
                            item = QListWidgetItem(unit_id)
                            item.setToolTip("Mod version")
                            self.gui.units_list.addItem(item)
                        # Add base game version if it exists
                        if unit_id in self.gui.manifest_data['base_game'].get('unit', {}):
                            item = QListWidgetItem(unit_id)
                            item.setForeground(QColor(150, 150, 150))
                            font = item.font()
                            font.setItalic(True)
                            item.setFont(font)
                            item.setToolTip("Base game version")
                            self.gui.units_list.addItem(item)

                    # Update buildable strikecraft list
                    self.gui.strikecraft_list.clear()
                    buildable_strikecraft = self.gui.current_data.get('buildable_strikecraft', [])
                    for unit_id in sorted(buildable_strikecraft):
                        # Add mod version if it exists
                        if unit_id in self.gui.manifest_data['mod'].get('unit', {}):
                            item = QListWidgetItem(unit_id)
                            item.setToolTip("Mod version")
                            self.gui.strikecraft_list.addItem(item)
                        # Add base game version if it exists
                        if unit_id in self.gui.manifest_data['base_game'].get('unit', {}):
                            item = QListWidgetItem(unit_id)
                            item.setForeground(QColor(150, 150, 150))
                            font = item.font()
                            font.setItalic(True)
                            item.setFont(font)
                            item.setToolTip("Base game version")
                            self.gui.strikecraft_list.addItem(item)
                return

            # For other types, use the standard mapping
            type_to_list = {
                'unit_item': [self.gui.items_list],
                'ability': [self.gui.ability_list],
                'action_data_source': [self.gui.action_list],
                'buff': [self.gui.buff_list],
                'formation': [self.gui.formations_list],
                'flight_pattern': [self.gui.patterns_list],
                'npc_reward': [self.gui.rewards_list],
                'exotic': [self.gui.exotics_list]
            }
            
            # Get the list widgets to update
            list_widgets = type_to_list.get(self.source_type, [])
            if not list_widgets:
                return
                
            # Update each list widget
            for list_widget in list_widgets:
                # Clear and repopulate the list
                list_widget.clear()
                
                # Add mod files first
                for file_id in sorted(self.gui.manifest_data['mod'].get(self.source_type, {})):
                    item = QListWidgetItem(file_id)
                    item.setToolTip("Mod version")
                    list_widget.addItem(item)
                
                # Then add base game files (grayed out)
                for file_id in sorted(self.gui.manifest_data['base_game'].get(self.source_type, {})):
                    # Always add base game files, even if they exist in mod folder
                    item = QListWidgetItem(file_id)
                    item.setForeground(QColor(150, 150, 150))
                    font = item.font()
                    font.setItalic(True)
                    item.setFont(font)
                    item.setToolTip("Base game version")
                    list_widget.addItem(item)
                        
        except Exception as e:
            print(f"Error updating list for type {self.source_type}: {str(e)}")

class CreateLocalizedText(Command):
    """Command for creating a new localized text entry"""
    def __init__(self, gui, key: str, text: str, language: str):
        # Get the localized text file path
        text_file = gui.current_folder / "localized_text" / f"{language}.localized_text"
        
        # Load or create initial data
        try:
            with open(text_file, 'r', encoding='utf-8') as f:
                old_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            old_data = {}
            
        # Create new data with the added text
        new_data = old_data.copy()
        new_data[key] = text
        
        super().__init__(text_file, [], old_data, new_data)
        self.gui = gui
        self.key = key
        self.text = text
        self.language = language
        
    def execute(self):
        """Execute the command (called by command stack)"""
        try:
            # Ensure the localized_text directory exists
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Update the GUI's in-memory strings
            if self.language not in self.gui.all_localized_strings['mod']:
                self.gui.all_localized_strings['mod'][self.language] = {}
            self.gui.all_localized_strings['mod'][self.language][self.key] = self.text
            
            return True
            
        except Exception as e:
            print(f"Error executing create localized text command: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
            
    def undo(self):
        """Undo the command (called by command stack)"""
        try:
            # Remove the key from GUI's in-memory strings
            if self.language in self.gui.all_localized_strings['mod']:
                self.gui.all_localized_strings['mod'][self.language].pop(self.key, None)
            
            return True
            
        except Exception as e:
            print(f"Error undoing create localized text command: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
            
    def redo(self):
        """Redo the command (called by command stack)"""
        return self.execute()

class CreateResearchSubjectCommand(Command):
    """Command for creating a new research subject and adding it to the research tree"""
    def __init__(self, gui, source_file: str, new_name: str, subject_type: str, overwrite: bool = False,
                 domain: str = None, field: str = None, tier: int = None, field_coord: list = None):
        super().__init__(None, None, None, None)  # We'll set these later
        self.gui = gui
        self.source_file = source_file
        self.new_name = new_name
        self.subject_type = subject_type  # "faction" or "regular"
        self.overwrite = overwrite
        self.array_path = ['research', 'faction_research_subjects' if subject_type == "faction" else 'research_subjects']
        # Store research settings
        self.domain = domain
        self.field = field
        self.tier = tier
        self.field_coord = field_coord
        
    def prepare(self) -> bool:
        """Prepare the command by gathering necessary data and validating the operation"""
        try:
            # Get the player file path (where research data is stored)
            self.file_path = self.gui.current_file
            if not self.file_path:
                raise ValueError("No player file is currently loaded")

            # Get current research data
            data = self.gui.command_stack.get_file_data(self.file_path)
            if not data or 'research' not in data:
                raise ValueError("Current file has no research data")

            # Create deep copies of research data for old and new values
            self.old_value = json.loads(json.dumps(data))
            self.new_value = json.loads(json.dumps(data))
            
            # Get current array
            current_array = []
            if 'research' in self.old_value:
                array_key = self.array_path[-1]  # 'research_subjects' or 'faction_research_subjects'
                if array_key in self.old_value['research']:
                    current_array = self.old_value['research'][array_key]
                else:
                    # Initialize the array if it doesn't exist
                    self.old_value['research'][array_key] = []
                    self.new_value['research'][array_key] = []

            # Create updated array with new subject
            updated_array = current_array + [self.new_name]
            
            # Update new_value with the updated array
            current = self.new_value
            for key in self.array_path[:-1]:
                if key not in current:
                    current[key] = {}
                current = current[key]
            current[self.array_path[-1]] = updated_array

            # Create the file copy command
            self.copy_command = CreateFileFromCopy(
                self.gui,
                self.source_file,
                "research_subject",
                self.new_name,
                self.overwrite
            )

            # Prepare the copy command
            if not self.copy_command.prepare():
                raise ValueError("Failed to prepare research subject copy")

            # If we have research settings, prepare to update them
            if any(x is not None for x in [self.domain, self.field, self.tier, self.field_coord]):
                # Get the target file path
                self.subject_file = self.gui.current_folder / "entities" / f"{self.new_name}.research_subject"
                
                # Load the source data
                if self.source_file in self.gui.manifest_data['mod'].get('research_subject', {}):
                    self.source_data = self.gui.manifest_data['mod']['research_subject'][self.source_file]
                elif self.source_file in self.gui.manifest_data['base_game'].get('research_subject', {}):
                    self.source_data = self.gui.manifest_data['base_game']['research_subject'][self.source_file]
                else:
                    raise ValueError(f"Could not find source file {self.source_file}")
                
                # Create a copy of the source data
                self.subject_data = json.loads(json.dumps(self.source_data))
                
                # Update the research settings
                if self.domain is not None:
                    self.subject_data['domain'] = self.domain
                if self.field is not None:
                    self.subject_data['field'] = self.field
                if self.tier is not None:
                    self.subject_data['tier'] = self.tier
                if self.field_coord is not None:
                    self.subject_data['field_coord'] = self.field_coord

            return True

        except Exception as e:
            print(f"Error preparing create research subject command: {str(e)}")
            return False

    def execute(self):
        """Execute the command"""
        try:
            print(f"Executing CreateResearchSubjectCommand for {self.new_name}")
            print(f"Array path: {self.array_path}")
            
            # Execute the file copy first
            if not self.copy_command.execute():
                print("Failed to execute file copy command")
                return False

            # Update the research subject file with new settings if provided
            if hasattr(self, 'subject_data'):
                with open(self.subject_file, 'w', encoding='utf-8') as f:
                    json.dump(self.subject_data, f, indent=4)

            # Update only the specific research array
            self.gui.command_stack.update_file_data(self.file_path, self.new_value)
            self.gui.update_data_value(self.array_path, self.new_value['research'][self.array_path[-1]])
            # Mark player file as modified
            self.gui.command_stack.modified_files.add(self.file_path)

            # Update the save button
            self.gui.update_save_button()

            # Refresh the research view
            self.gui.refresh_research_view()
            print("Successfully executed CreateResearchSubjectCommand")
            return True

        except Exception as e:
            print(f"Error executing create research subject command: {str(e)}")
            return False

    def undo(self):
        """Undo the command"""
        try:
            # Undo the file copy first
            self.copy_command.undo()

            # Restore only the specific research array
            self.gui.command_stack.update_file_data(self.file_path, self.old_value)
            self.gui.update_data_value(self.array_path, self.old_value['research'][self.array_path[-1]])
            # Mark player file as modified
            self.gui.command_stack.modified_files.add(self.file_path)

            # Refresh the research view
            self.gui.refresh_research_view()
            return True

        except Exception as e:
            print(f"Error undoing create research subject command: {str(e)}")
            return False

    def redo(self):
        """Redo the command"""
        return self.execute()

class DeleteFileCommand(Command):
    """Command for deleting a file and optionally its manifest entry"""
    def __init__(self, gui, file_id: str, file_type: str, remove_manifest: bool = False):
        super().__init__(None, None, None, None)  # We don't use the standard command values
        self.gui = gui
        self.file_id = file_id
        self.file_type = file_type
        self.remove_manifest = remove_manifest
        self.file_path = None
        self.manifest_file_path = None
        self.old_manifest_data = None
        self.new_manifest_data = None
        self.file_data = None  # Store file contents for undo
        
    def prepare(self) -> bool:
        """Prepare the command by gathering necessary data and validating the operation"""
        try:
            # Special handling for uniforms
            if self.file_type == "uniform":
                self.file_path = self.gui.current_folder / "uniforms" / f"{self.file_id}.uniforms"
                # No manifest file for uniforms
                self.manifest_file_path = None
            else:
                self.file_path = self.gui.current_folder / "entities" / f"{self.file_id}.{self.file_type}"
                self.manifest_file_path = self.gui.current_folder / "entities" / f"{self.file_type}.entity_manifest"

            # Check if file exists
            if not self.file_path.exists():
                raise ValueError(f"File does not exist: {self.file_path}")

            # Store file contents for undo
            with open(self.file_path, 'r', encoding='utf-8') as f:
                self.file_data = json.load(f)

            # Handle manifest if needed
            if self.remove_manifest and self.manifest_file_path and self.manifest_file_path.exists():
                with open(self.manifest_file_path, 'r', encoding='utf-8') as f:
                    manifest_data = json.load(f)
                # Store old manifest data for undo (deep copy)
                self.old_manifest_data = json.loads(json.dumps(manifest_data))
                # Create new manifest data without this file (deep copy)
                self.new_manifest_data = json.loads(json.dumps(manifest_data))
                if "ids" in self.new_manifest_data and self.file_id in self.new_manifest_data["ids"]:
                    self.new_manifest_data["ids"].remove(self.file_id)

            # Store current manifest data state for undo
            if self.file_type in self.gui.manifest_data['mod']:
                # Store the current data for this specific file ID only
                if self.file_id in self.gui.manifest_data['mod'][self.file_type]:
                    self.manifest_mod_data = self.gui.manifest_data['mod'][self.file_type][self.file_id]
                else:
                    self.manifest_mod_data = None

            return True

        except Exception as e:
            print(f"Error preparing delete file command: {str(e)}")
            return False

    def execute(self):
        """Execute the file deletion"""
        try:
            # Delete the file
            if self.file_path.exists():
                self.file_path.unlink()

            # Update manifest if needed
            if self.remove_manifest and self.manifest_file_path and self.new_manifest_data:
                with open(self.manifest_file_path, 'w', encoding='utf-8') as f:
                    json.dump(self.new_manifest_data, f, indent=4)

            # Always remove from GUI's manifest data when deleting the file
            # This ensures the item is removed from the list view
            if self.file_type in self.gui.manifest_data['mod']:
                self.gui.manifest_data['mod'][self.file_type].pop(self.file_id, None)

            # Update the appropriate list
            self.update_list_for_type()

            return True

        except Exception as e:
            print(f"Error executing delete file command: {str(e)}")
            return False

    def undo(self):
        """Undo the file deletion"""
        try:
            # Restore the file
            if self.file_data:
                self.file_path.parent.mkdir(parents=True, exist_ok=True)
                with open(self.file_path, 'w', encoding='utf-8') as f:
                    json.dump(self.file_data, f, indent=4)

            # Restore manifest if needed
            if self.remove_manifest and self.manifest_file_path and self.old_manifest_data:
                with open(self.manifest_file_path, 'w', encoding='utf-8') as f:
                    json.dump(self.old_manifest_data, f, indent=4)

            # Restore GUI's manifest data
            if hasattr(self, 'manifest_mod_data') and self.manifest_mod_data is not None:
                if self.file_type not in self.gui.manifest_data['mod']:
                    self.gui.manifest_data['mod'][self.file_type] = {}
                self.gui.manifest_data['mod'][self.file_type][self.file_id] = self.manifest_mod_data

            # Update the appropriate list
            self.update_list_for_type()

            return True

        except Exception as e:
            print(f"Error undoing delete file command: {str(e)}")
            return False

    def redo(self):
        """Redo the file deletion"""
        return self.execute()

    def update_list_for_type(self):
        """Update the appropriate list widget"""
        # Special handling for uniforms
        if self.file_type == "uniform":
            self.gui.uniforms_list.clear()
            # Add mod files first
            uniforms_folder = self.gui.current_folder / "uniforms"
            if uniforms_folder.exists():
                for file in sorted(uniforms_folder.glob("*.uniforms")):
                    item = QListWidgetItem(file.stem)
                    item.setToolTip("Mod version")
                    self.gui.uniforms_list.addItem(item)
            # Then add base game files (grayed out)
            if self.gui.base_game_folder:
                base_uniforms_folder = self.gui.base_game_folder / "uniforms"
                if base_uniforms_folder.exists():
                    for file in sorted(base_uniforms_folder.glob("*.uniforms")):
                        # Always add base game files, even if they exist in mod folder
                        item = QListWidgetItem(file.stem)
                        item.setForeground(QColor(150, 150, 150))
                        font = item.font()
                        font.setItalic(True)
                        item.setFont(font)
                        item.setToolTip("Base game version")
                        self.gui.uniforms_list.addItem(item)
            return

        # For other types, use the standard mapping
        type_to_list = {
            'unit': [self.gui.all_units_list, self.gui.units_list, self.gui.strikecraft_list],
            'unit_item': [self.gui.items_list],
            'ability': [self.gui.ability_list],
            'action_data_source': [self.gui.action_list],
            'buff': [self.gui.buff_list],
            'formation': [self.gui.formations_list],
            'flight_pattern': [self.gui.patterns_list],
            'npc_reward': [self.gui.rewards_list],
            'exotic': [self.gui.exotics_list]
        }
        
        # Get the list widgets to update
        list_widgets = type_to_list.get(self.file_type, [])
        if not list_widgets:
            return
            
        # Update each list widget
        for list_widget in list_widgets:
            # Clear and repopulate the list
            list_widget.clear()
            
            # Add mod files first
            for file_id in sorted(self.gui.manifest_data['mod'].get(self.file_type, {})):
                item = QListWidgetItem(file_id)
                item.setToolTip("Mod version")
                list_widget.addItem(item)
            
            # Then add base game files (grayed out)
            for file_id in sorted(self.gui.manifest_data['base_game'].get(self.file_type, {})):
                # Always add base game files, even if they exist in mod folder
                item = QListWidgetItem(file_id)
                item.setForeground(QColor(150, 150, 150))
                font = item.font()
                font.setItalic(True)
                item.setFont(font)
                item.setToolTip("Base game version")
                list_widget.addItem(item)

class DeleteResearchSubjectCommand(Command):
    """Command for deleting a research subject from the research tree and optionally the file system"""
    def __init__(self, gui, subject_id: str, array_path: list, full_delete: bool = True):
        super().__init__(None, None, None, None)  # We'll set these later
        self.gui = gui
        self.subject_id = subject_id
        self.array_path = array_path
        self.full_delete = full_delete
        self.subject_file = gui.current_folder / "entities" / f"{subject_id}.research_subject"
        self.manifest_file = gui.current_folder / "entities" / "research_subject.entity_manifest"
        self.manifest_data = None
        self.subject_data = None
        
    def prepare(self) -> bool:
        """Prepare the command by gathering necessary data and validating the operation"""
        try:
            # Get the player file path
            self.file_path = self.gui.current_file
            if not self.file_path:
                raise ValueError("No player file is currently loaded")

            # Get current research data
            data = self.gui.command_stack.get_file_data(self.file_path)
            if not data or 'research' not in data:
                raise ValueError("Current file has no research data")

            # Create deep copies of research data for old and new values
            self.old_value = json.loads(json.dumps(data))
            self.new_value = json.loads(json.dumps(data))
            
            # Get current array
            current = self.new_value
            for key in self.array_path[:-1]:
                if key not in current:
                    current[key] = {}
                current = current[key]
            
            array_key = self.array_path[-1]
            if array_key not in current:
                raise ValueError(f"Research array {array_key} not found")
                
            current_array = current[array_key]
            if self.subject_id not in current_array:
                raise ValueError(f"Subject {self.subject_id} not found in research array")

            # Create updated array without the subject
            updated_array = [x for x in current_array if x != self.subject_id]
            current[array_key] = updated_array

            if self.full_delete:
                # Store subject data for undo
                if self.subject_file.exists():
                    with open(self.subject_file, 'r', encoding='utf-8') as f:
                        self.subject_data = json.load(f)

                # Store manifest data for undo
                if self.manifest_file.exists():
                    with open(self.manifest_file, 'r', encoding='utf-8') as f:
                        self.manifest_data = json.load(f)

            return True

        except Exception as e:
            print(f"Error preparing delete research subject command: {str(e)}")
            return False

    def execute(self):
        """Execute the command"""
        try:
            print(f"Executing DeleteResearchSubjectCommand for {self.subject_id}")
            
            # Update command stack data first
            self.gui.command_stack.update_file_data(self.file_path, self.new_value)
            self.gui.command_stack.modified_files.add(self.file_path)

            if self.full_delete:
                # Delete the subject file
                if self.subject_file.exists():
                    self.subject_file.unlink()

                # Update the manifest file
                if self.manifest_file.exists() and self.manifest_data:
                    manifest_data = json.loads(json.dumps(self.manifest_data))  # Deep copy
                    if "ids" in manifest_data and self.subject_id in manifest_data["ids"]:
                        manifest_data["ids"].remove(self.subject_id)
                        # Update command stack's file data for manifest
                        self.gui.command_stack.update_file_data(self.manifest_file, manifest_data)
                        self.gui.command_stack.modified_files.add(self.manifest_file)
                        
                        # Write to file
                        with open(self.manifest_file, 'w', encoding='utf-8') as f:
                            json.dump(manifest_data, f, indent=4)

                    # Remove from GUI's manifest data
                    if 'research_subject' in self.gui.manifest_data['mod']:
                        self.gui.manifest_data['mod']['research_subject'].pop(self.subject_id, None)

            # Now do UI updates
            self.gui.update_data_value(self.array_path, self.new_value['research'][self.array_path[-1]])
            self.gui.update_save_button()
            self.gui.refresh_research_view()
            
            print("Successfully executed DeleteResearchSubjectCommand")
            return True

        except Exception as e:
            print(f"Error executing delete research subject command: {str(e)}")
            return False

    def undo(self):
        """Undo the command"""
        try:
            # Update command stack data first
            self.gui.command_stack.update_file_data(self.file_path, self.old_value)
            self.gui.command_stack.modified_files.add(self.file_path)

            if self.full_delete:
                # Restore the subject file
                if self.subject_data:
                    self.subject_file.parent.mkdir(parents=True, exist_ok=True)
                    with open(self.subject_file, 'w', encoding='utf-8') as f:
                        json.dump(self.subject_data, f, indent=4)

                # Restore the manifest file
                if self.manifest_data:
                    # Update command stack's file data for manifest
                    self.gui.command_stack.update_file_data(self.manifest_file, self.manifest_data)
                    self.gui.command_stack.modified_files.add(self.manifest_file)
                    
                    # Write to file
                    with open(self.manifest_file, 'w', encoding='utf-8') as f:
                        json.dump(self.manifest_data, f, indent=4)

                    # Restore GUI's manifest data
                    if self.subject_data:
                        if 'research_subject' not in self.gui.manifest_data['mod']:
                            self.gui.manifest_data['mod']['research_subject'] = {}
                        self.gui.manifest_data['mod']['research_subject'][self.subject_id] = self.subject_data

            # Now do UI updates
            self.gui.update_data_value(self.array_path, self.old_value['research'][self.array_path[-1]])
            self.gui.refresh_research_view()
            
            return True

        except Exception as e:
            print(f"Error undoing delete research subject command: {str(e)}")
            return False

    def redo(self):
        """Redo the command"""
        return self.execute()
