from typing import Any, List, Dict, Set, Callable
from pathlib import Path
import json
import logging
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QToolButton, QGroupBox
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
            # Update the data
            if self.data_path is not None:
                self.gui.update_data_value(self.data_path, self.old_value)
                
            # Remove the widget
            if self.added_widget:
                self.added_widget.setParent(None)
                self.added_widget.deleteLater()
                self.added_widget = None
                
        except Exception as e:
            print(f"Error undoing add property command: {str(e)}")
            
    def redo(self):
        """Redo the property addition"""
        try:
            return self.execute()
        except Exception as e:
            print(f"Error redoing add property command: {str(e)}")
            return None

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

class DeletePropertyCommand(Command):
    """Command for deleting a property from an object"""
    def __init__(self, gui, property_widget, property_name, parent_data):
        # Get the full data path from the widget
        data_path = property_widget.property("data_path")
        if not data_path:
            # Try parent widget if this one doesn't have the path
            parent = property_widget.parent()
            if parent:
                data_path = parent.property("data_path")
        
        print(f"Full data path from widget: {data_path}")
        
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
            if isinstance(current, dict) and property_name in current:
                old_data = current.copy()
                new_data = current.copy()
                del new_data[property_name]
            else:
                old_data = parent_data.copy()
                new_data = parent_data.copy()
                if property_name in new_data:
                    del new_data[property_name]
        else:
            # For root properties, get the entire data structure
            file_path = gui.get_schema_view_file_path(property_widget)
            if file_path:
                old_data = gui.command_stack.get_file_data(file_path)
                if old_data:
                    old_data = old_data.copy()
                    new_data = old_data.copy()
                    if property_name in new_data:
                        del new_data[property_name]
                else:
                    old_data = parent_data.copy()
                    new_data = parent_data.copy()
                    if property_name in new_data:
                        del new_data[property_name]
            else:
                old_data = parent_data.copy()
                new_data = parent_data.copy()
                if property_name in new_data:
                    del new_data[property_name]
        
        super().__init__(gui.get_schema_view_file_path(property_widget), data_path[:-1], old_data, new_value=new_data)
        self.gui = gui
        self.property_widget = property_widget
        self.property_name = property_name
        self.full_path = data_path  # Store the complete path including property name
        
    def execute(self):
        """Execute the property deletion"""
        try:
            print(f"Executing delete property command for {self.property_name}")
            print(f"Full path: {self.full_path}")
            print(f"Parent path for update: {self.data_path}")
            print(f"Property widget: {self.property_widget}")
            
            # Update the data
            if self.data_path is not None:
                print(f"Updating data value at path: {self.data_path}")
                self.gui.update_data_value(self.data_path, self.new_value)
            
            # Remove the widget
            if self.property_widget:
                print("Removing widget")
                parent = self.property_widget.parent()
                if parent:
                    print(f"Found parent widget: {parent}")
                    parent.hide()
                    parent.setParent(None)
                    parent.deleteLater()
                else:
                    print("No parent widget found")
            else:
                print("No property widget to remove")
            
        except Exception as e:
            print(f"Error executing delete property command: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
            
    def undo(self):
        """Undo the property deletion"""
        try:
            # Update the data first
            if self.data_path != []:
                print(f"Undoing deletion at path: {self.data_path}")
                self.gui.update_data_value(self.data_path, self.old_value)
            else:
                print("Undoing root property deletion")
                self.gui.command_stack.update_file_data(self.file_path, self.old_value)
            
            # For root properties, we need to force a schema view update first
            if not self.data_path:
                print("Root property deletion - forcing schema view update")
                # TODO: Force a refresh of the schema view
                self.refresh_views()
                return
            
            # Find the schema view by searching all widgets
            schema_view = None
            for widget in self.gui.findChildren(QWidget):
                if (hasattr(widget, 'property') and 
                    widget.property("file_path") == str(self.file_path)):
                    schema_view = widget
                    break

            if not schema_view:
                print("Could not find schema view")
                return

            # Then check for array items
            if isinstance(self.data_path[-1], int):
                array_path = self.data_path[:-1]  # ['planet_levels']
                print(f"Looking for array widget with path: {array_path}")
                
                # Find the array's collapsible section by looking for a QToolButton with the array name
                array_button = None
                for widget in schema_view.findChildren(QToolButton):
                    btn_text = widget.text()
                    print(f"Found button with text: {btn_text}")
                    
                    # Remove count suffix if present (e.g., "Planet Levels (4)" -> "Planet Levels")
                    btn_text = btn_text.split(" (")[0]
                    
                    # Try different text formats
                    possible_texts = [
                        array_path[0],  # planet_levels
                        array_path[0].replace("_", " "),  # planet levels
                        array_path[0].replace("_", " ").title(),  # Planet Levels
                        array_path[0].replace("_", " ").lower(),  # planet levels
                        array_path[0].lower(),  # planetlevels
                        array_path[0].title()  # PlanetLevels
                    ]
                    if any(text == btn_text for text in possible_texts):
                        print(f"Found array button: {btn_text}")
                        array_button = widget
                        break
                
                if not array_button:
                    print("Could not find array button")
                    print("Available buttons:")
                    for widget in schema_view.findChildren(QToolButton):
                        print(f"  {widget.text()}")
                    return
                
                # Get the collapsible widget (parent of the array button)
                collapsible_widget = array_button.parent()
                if not collapsible_widget:
                    print("Could not find collapsible widget")
                    return
                
                # Get the parent of the collapsible widget
                parent = collapsible_widget.parent()
                if not parent:
                    print("Could not find parent of collapsible widget")
                    return
                
                parent_layout = parent.layout()
                if not parent_layout:
                    print("Could not find parent layout")
                    return
                
                # Find the collapsible widget's index in its parent's layout
                widget_index = -1
                for i in range(parent_layout.count()):
                    if parent_layout.itemAt(i).widget() == collapsible_widget:
                        widget_index = i
                        break
                
                if widget_index == -1:
                    print("Could not find widget index")
                    return
                
                # Get schema and create new array widget
                array_schema = self.gui.get_schema_for_path(array_path)
                if not array_schema:
                    print("Could not find array schema")
                    return
                
                # Get the current array data from the command stack
                current_data = self.gui.command_stack.get_file_data(self.file_path)
                if not current_data:
                    print("Could not get current data")
                    return
                
                # Navigate to the array
                array_data = current_data
                for part in array_path:
                    if isinstance(array_data, (dict, list)):
                        array_data = array_data[part]
                
                print(f"Array data for widget creation: {array_data}")
                
                # Create new widget for the array
                new_widget = self.gui.create_widget_for_schema(
                    array_data,  # Use the full array data
                    array_schema,
                    False,  # is_base_game
                    array_path
                )
                
                if new_widget:
                    print("Created new array widget")
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
                    
                    # Find and click the toggle button to expand the array
                    new_layout = new_widget.layout()
                    if new_layout and new_layout.count() > 0:
                        toggle_btn = new_layout.itemAt(0).widget()
                        if isinstance(toggle_btn, QToolButton):
                            toggle_btn.setChecked(True)  # This will expand the array
                            print("Expanded array section")
            else:
                # For regular nested properties, find a widget with matching data path
                parent_widget = None
                for widget in schema_view.findChildren(QWidget):
                    if (hasattr(widget, 'property') and 
                        widget.property("data_path") == self.data_path):
                        parent_widget = widget
                        if parent_widget.layout():
                            break

                if not parent_widget or not parent_widget.layout():
                    print("Could not find parent widget with layout")
                    return
                    
                # Get the schema for this property
                schema = self.gui.get_schema_for_path(self.data_path)
                if not schema:
                    print("Could not find schema for path")
                    return
                
                if "properties" not in schema or self.property_name not in schema["properties"]:
                    print("Could not find schema for property")
                    print(f"Schema: {schema}")
                    print(f"Property name: {self.property_name}")
                    return
                    
                prop_schema = schema["properties"][self.property_name]
                prop_value = self.old_value[self.property_name] if self.property_name in self.old_value else None
                
                print(f"Creating widget for property {self.property_name} with value {prop_value}")
                print(f"Parent widget: {parent_widget}")
                print(f"Schema: {prop_schema}")
                
                # Create new widget for the property
                row_widget = QWidget()
                row_layout = QHBoxLayout(row_widget)
                row_layout.setContentsMargins(0, 2, 0, 2)
                
                # Create label
                display_name = self.property_name.replace("_", " ").title()
                label = QLabel(f"{display_name}:")
                
                # Make label bold if property is required
                if "required" in schema and self.property_name in schema["required"]:
                    label.setStyleSheet("QLabel { font-weight: bold; }")
                
                # Add context menu to label
                label.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
                label.setProperty("data_path", self.full_path)  # Use full path including property name
                label.customContextMenuRequested.connect(
                    lambda pos, w=label, v=prop_value: self.gui.show_context_menu(w, pos, v)
                )
                
                row_layout.addWidget(label)
                
                # Create value widget
                value_widget = self.gui.create_widget_for_value(
                    prop_value,
                    prop_schema,
                    False,  # is_base_game
                    self.full_path  # Use full path including property name
                )
                
                if value_widget:
                    row_layout.addWidget(value_widget)
                    row_layout.addStretch()
                    
                    print("Adding new widget to parent layout")
                    parent_widget.layout().addWidget(row_widget)
                    self.property_widget = row_widget
                
        except Exception as e:
            print(f"Error undoing delete property command: {str(e)}")
            import traceback
            traceback.print_exc()
            
    def redo(self):
        """Redo the property deletion"""
        try:
            # Update the data first
            if self.data_path != []:
                print(f"Redoing deletion at path: {self.data_path}")
                self.gui.update_data_value(self.data_path, self.new_value)
            else:
                print("Redoing root property deletion")
                self.gui.command_stack.update_file_data(self.file_path, self.new_value)
                
                # Find the widget for the root property
                schema_view = None
                for widget in self.gui.findChildren(QWidget):
                    if (hasattr(widget, 'property') and 
                        widget.property("file_path") == str(self.file_path)):
                        schema_view = widget
                        break
                    
                if schema_view:
                    # Find widget with matching property name
                    for widget in schema_view.findChildren(QWidget):
                        if (hasattr(widget, 'property') and 
                            widget.property("data_path") and 
                            widget.property("data_path")[-1] == self.property_name):
                            parent = widget.parent()
                            if parent:
                                parent.hide()
                                parent.setParent(None)
                                parent.deleteLater()
                            break
                return True
            
            # For root properties and regular nested properties, just execute normally
            if not self.data_path or not isinstance(self.data_path[-1], int):
                return self.execute()
            
            # For array items, we need to replace the entire array widget
            # Find the schema view by searching all widgets
            schema_view = None
            for widget in self.gui.findChildren(QWidget):
                if (hasattr(widget, 'property') and 
                    widget.property("file_path") == str(self.file_path)):
                    schema_view = widget
                    break

            if not schema_view:
                print("Could not find schema view")
                return

            array_path = self.data_path[:-1]  # ['planet_levels']
            print(f"Looking for array widget with path: {array_path}")
            
            # Find the array's collapsible section by looking for a QToolButton with the array name
            array_button = None
            for widget in schema_view.findChildren(QToolButton):
                btn_text = widget.text()
                print(f"Found button with text: {btn_text}")
                
                # Remove count suffix if present (e.g., "Planet Levels (4)" -> "Planet Levels")
                btn_text = btn_text.split(" (")[0]
                
                # Try different text formats
                possible_texts = [
                    array_path[0],  # planet_levels
                    array_path[0].replace("_", " "),  # planet levels
                    array_path[0].replace("_", " ").title(),  # Planet Levels
                    array_path[0].replace("_", " ").lower(),  # planet levels
                    array_path[0].lower(),  # planetlevels
                    array_path[0].title()  # PlanetLevels
                ]
                if any(text == btn_text for text in possible_texts):
                    print(f"Found array button: {btn_text}")
                    array_button = widget
                    break
            
            if not array_button:
                print("Could not find array button")
                print("Available buttons:")
                for widget in schema_view.findChildren(QToolButton):
                    print(f"  {widget.text()}")
                return
            
            # Get the collapsible widget (parent of the array button)
            collapsible_widget = array_button.parent()
            if not collapsible_widget:
                print("Could not find collapsible widget")
                return
            
            # Get the parent of the collapsible widget
            parent = collapsible_widget.parent()
            if not parent:
                print("Could not find parent of collapsible widget")
                return
            
            parent_layout = parent.layout()
            if not parent_layout:
                print("Could not find parent layout")
                return
            
            # Find the collapsible widget's index in its parent's layout
            widget_index = -1
            for i in range(parent_layout.count()):
                if parent_layout.itemAt(i).widget() == collapsible_widget:
                    widget_index = i
                    break
            
            if widget_index == -1:
                print("Could not find widget index")
                return
            
            # Get schema and create new array widget
            array_schema = self.gui.get_schema_for_path(array_path)
            if not array_schema:
                print("Could not find array schema")
                return
            
            # Get the current array data from the command stack
            current_data = self.gui.command_stack.get_file_data(self.file_path)
            if not current_data:
                print("Could not get current data")
                return
            
            # Navigate to the array
            array_data = current_data
            for part in array_path:
                if isinstance(array_data, (dict, list)):
                    array_data = array_data[part]
            
            print(f"Array data for widget creation: {array_data}")
            
            # Create new widget for the array
            new_widget = self.gui.create_widget_for_schema(
                array_data,  # Use the full array data
                array_schema,
                False,  # is_base_game
                array_path
            )
            
            if new_widget:
                print("Created new array widget")
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
                
                # Find and click the toggle button to expand the array
                new_layout = new_widget.layout()
                if new_layout and new_layout.count() > 0:
                    toggle_btn = new_layout.itemAt(0).widget()
                    if isinstance(toggle_btn, QToolButton):
                        toggle_btn.setChecked(True)  # This will expand the array
                        print("Expanded array section")
                
        except Exception as e:
            print(f"Error redoing delete property command: {str(e)}")
            import traceback
            traceback.print_exc()
            return None 
        
    def refresh_views(self):
        """Refresh any schema views affected by this command"""
        if hasattr(self, 'file_path') and self.file_path:
            self.gui.refresh_schema_view(self.file_path)
