from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                            QGraphicsScene, QGraphicsView, QGraphicsItem, QGraphicsPathItem, 
                            QGraphicsTextItem, QGraphicsPixmapItem, QGraphicsRectItem, QMenu)
from PyQt6.QtCore import Qt, QRectF, QPointF, pyqtSignal, QRect, QPoint
from PyQt6.QtGui import (QPixmap, QPainter, QPen, QColor, QBrush, 
                        QPainterPath, QLinearGradient)

class ResearchNode(QGraphicsItem):
    def __init__(self, name: str, subject_id: str, icon: QPixmap = None, is_base_game: bool = False):
        super().__init__()
        self.name = name
        self.subject_id = subject_id
        self.icon = icon
        self.is_base_game = is_base_game
        self.connections = []  # List of connected nodes
        self.setAcceptHoverEvents(True)
        self.hovered = False
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        
        # Size and style
        self.width = 120
        self.height = 80
        self.border_radius = 10
        
    def boundingRect(self):
        return QRectF(-self.width/2, -self.height/2, self.width, self.height)
        
    def paint(self, painter: QPainter, option, widget):
        # Draw node background
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Create gradient background
        gradient = QLinearGradient(self.boundingRect().topLeft(), self.boundingRect().bottomRight())
        if self.isSelected():
            gradient.setColorAt(0, QColor(0, 150, 200))
            gradient.setColorAt(1, QColor(0, 100, 150))
        elif self.hovered:
            gradient.setColorAt(0, QColor(0, 100, 150))
            gradient.setColorAt(1, QColor(0, 70, 100))
        else:
            gradient.setColorAt(0, QColor(0, 70, 100))
            gradient.setColorAt(1, QColor(0, 40, 60))
        
        # Create rounded rect path for clipping
        path = QPainterPath()
        path.addRoundedRect(self.boundingRect(), self.border_radius, self.border_radius)
        
        # Set clipping path for icon
        painter.setClipPath(path)
        
        # Draw icon if available, filling the entire node
        if self.icon and not self.icon.isNull():
            # Scale icon to fill the node while maintaining aspect ratio
            scaled_icon = self.icon.scaled(self.width, self.height, 
                                         Qt.AspectRatioMode.KeepAspectRatio,
                                         Qt.TransformationMode.SmoothTransformation)
            
            # Calculate position to center the scaled icon
            icon_x = int(-scaled_icon.width() / 2)
            icon_y = int(-scaled_icon.height() / 2)
            icon_rect = QRect(icon_x, icon_y, scaled_icon.width(), scaled_icon.height())
            painter.drawPixmap(icon_rect, scaled_icon)
        else:
            # If no icon, fill with gradient
            painter.fillPath(path, QBrush(gradient))
        
        # Reset clipping
        painter.setClipping(False)
        
        # Draw border
        border_color = QColor(0, 200, 255) if self.isSelected() or self.hovered else QColor(0, 100, 150)
        painter.setPen(QPen(border_color, 2))
        painter.drawPath(path)
        
        # Draw text
        font = painter.font()
        font.setBold(True)
        font.setPointSize(8)  # Set smaller font size for better fit
        painter.setFont(font)

        # Position text at bottom of node
        text_rect = self.boundingRect().adjusted(2, self.height/2 - 18, -2, -2)

        # Draw text outline by drawing text multiple times with slight offsets
        painter.setPen(QPen(QColor(0, 0, 0), 1))
        for dx, dy in [(-1, -1), (-1, 1), (1, -1), (1, 1)]:
            offset_rect = text_rect.translated(dx, dy)
            painter.drawText(offset_rect, Qt.AlignmentFlag.AlignCenter, self.name)
        
        # Draw main text
        if self.is_base_game:
            painter.setPen(QPen(QColor(150, 150, 150)))
            painter.setFont(font)
        else:
            painter.setPen(QPen(Qt.GlobalColor.white))
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, self.name)
    
    def hoverEnterEvent(self, event):
        self.hovered = True
        self.update()
        super().hoverEnterEvent(event)
    
    def hoverLeaveEvent(self, event):
        self.hovered = False
        self.update()
        super().hoverLeaveEvent(event)
    
    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        if event.button() == Qt.MouseButton.LeftButton:
            self.scene().views()[0].node_clicked.emit(self.subject_id)
        elif event.button() == Qt.MouseButton.RightButton and not self.is_base_game:
            # Only show context menu for mod subjects
            self.scene().views()[0].show_node_context_menu(self, event.screenPos())

class ResearchTreeView(QGraphicsView):
    node_clicked = pyqtSignal(str)  # Signal emitted when a node is clicked, passes subject_id
    node_delete_requested = pyqtSignal(str)  # Signal emitted when node deletion is requested
    add_subject_requested = pyqtSignal(str)  # Signal emitted when adding a subject is requested, passes faction type
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        
        # Store viewport center for preserving scroll position
        self.last_viewport_center = None
        
        # Style settings
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.setBackgroundBrush(QBrush(QColor(0, 20, 30)))
        
        # Enable mouse tracking for zoom
        self.setMouseTracking(True)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        
        # Zoom settings
        self.zoom_factor = 1.15
        self.min_zoom = 0.1
        self.max_zoom = 3.0
        self.current_zoom = 0.4  # Default zoom level (40%)
        
        # Node layout settings
        self.field_width = 400  # Width for field background/label area
        self.horizontal_spacing = 150  # Spacing between columns (reduced since we have 10 columns)
        self.vertical_spacing = 1400  # Increased spacing between fields for more room
        self.node_vertical_spacing = 100  # Spacing between rows
        self.top_margin = 150  # Increased space from top of scene to first field
        self.nodes = {}  # Store nodes by subject_id
        self.current_domain = None
        self.domains = set()  # Track available domains
        self.fields_by_domain = {}  # Track fields per domain {domain: {field: y_pos}}
        self.field_backgrounds = {}  # Store field background images {field: QPixmap}
        self.nodes_by_field = {}  # Track nodes in each field {field: [nodes]}
        self.field_max_rows = {}  # Track max row index for each field
        
        # Add tier headers
        self.add_tier_headers()
        
        # Set initial zoom level
        self.scale(self.current_zoom, self.current_zoom)
    
    def add_tier_headers(self):
        """Add tier headers to the scene"""
        for i in range(5):  # 0-4 for tiers
            # Create header for the tier (spans two columns)
            text = QGraphicsTextItem(f"Tier {i + 1}")
            text.setDefaultTextColor(QColor(0, 200, 255))
            font = text.font()
            font.setPointSize(12)
            font.setBold(True)
            text.setFont(font)
            
            # Position header above the tier's two columns
            # Calculate center position between the two columns of this tier
            x = self.field_width + (i * 2 * self.horizontal_spacing) + self.horizontal_spacing
            y = self.top_margin - 100  # Position above the first field
            text.setPos(x - text.boundingRect().width() / 2, y)
            self.scene.addItem(text)
            
            # Add vertical grid lines for this tier's columns
            for col in range(2):
                line = QGraphicsPathItem()
                path = QPainterPath()
                x_pos = self.field_width + ((i * 2 + col) * self.horizontal_spacing)
                path.moveTo(x_pos, self.top_margin - 50)  # Start below headers
                path.lineTo(x_pos, 5000)  # Long enough to cover all fields
                line.setPath(path)
                line.setPen(QPen(QColor(0, 100, 150, 50), 1, Qt.PenStyle.DashLine))  # Semi-transparent, dashed line
                line.setZValue(-3)  # Behind everything else
                self.scene.addItem(line)
    
    def set_field_backgrounds(self, field_data: dict):
        """Set background images for research fields"""
        self.field_backgrounds = field_data
        self.update_field_backgrounds()
    
    def update_field_backgrounds(self):
        """Update field background images for current domain"""
        # Clear existing backgrounds
        for item in self.scene.items():
            if isinstance(item, QGraphicsPixmapItem) and hasattr(item, 'is_field_background'):
                self.scene.removeItem(item)
        
        if self.current_domain not in self.fields_by_domain:
            return
            
        # Add new backgrounds
        for field, field_center in self.fields_by_domain[self.current_domain].items():
            if field in self.field_backgrounds:
                background = self.field_backgrounds[field]
                if background and not background.isNull():
                    # Create background item
                    item = QGraphicsPixmapItem(background)
                    item.is_field_background = True
                    item.setZValue(-2)  # Behind connections
                    
                    # Scale to maintain 810x450 aspect ratio while fitting the field width
                    target_width = 810
                    target_height = 450
                    scale = min(self.field_width / target_width, 1.0)  # Don't scale up, only down if needed
                    scaled_height = target_height * scale
                    
                    # Position background on the left side, centered on field's center position
                    item.setPos(0, field_center - scaled_height/2)
                    item.setScale(scale)
                    
                    self.scene.addItem(item)
    
    def add_field_labels(self):
        """Add field labels for the current domain"""
        # Clear existing field labels and field separators
        for item in self.scene.items():
            if (isinstance(item, QGraphicsTextItem) and hasattr(item, 'is_field_label')) or \
               (isinstance(item, QGraphicsPathItem) and hasattr(item, 'is_field_separator')):
                self.scene.removeItem(item)
        
        if self.current_domain not in self.fields_by_domain:
            return
            
        for field, y_pos in sorted(self.fields_by_domain[self.current_domain].items()):
            # Add field label
            text = QGraphicsTextItem(field)
            text.setDefaultTextColor(QColor(0, 200, 255))
            font = text.font()
            font.setPointSize(14)
            font.setBold(True)
            text.setFont(font)
            text.is_field_label = True
            
            # Position label on the left side
            x = 20
            y = y_pos - text.boundingRect().height() / 2
            text.setPos(x, y)
            self.scene.addItem(text)
            
            # Add horizontal separator line above field
            separator = QGraphicsPathItem()
            separator.is_field_separator = True
            path = QPainterPath()
            path.moveTo(0, y_pos - self.vertical_spacing/2)
            path.lineTo(2000, y_pos - self.vertical_spacing/2)  # Wide enough to cover all columns
            separator.setPath(path)
            separator.setPen(QPen(QColor(0, 100, 150, 50), 1, Qt.PenStyle.DashLine))  # Semi-transparent, dashed line
            separator.setZValue(-3)  # Behind everything else
            self.scene.addItem(separator)
    
    def set_domain(self, domain: str):
        """Switch to displaying a different domain"""
        # Store current viewport center
        self.last_viewport_center = self.mapToScene(self.viewport().rect().center())
        
        self.current_domain = domain
        
        # Hide nodes from other domains
        for node in self.nodes.values():
            node.setVisible(node.domain == domain)
            # Hide connections if either end is hidden
            for conn in node.connections:
                conn.setVisible(all(n.isVisible() for n in [conn.from_node, conn.to_node]))
        
        # Update field labels and backgrounds
        self.add_field_labels()
        self.update_field_backgrounds()
        
        # Update scene rect
        visible_items = [item for item in self.scene.items() if item.isVisible()]
        if visible_items:
            rect = self.scene.itemsBoundingRect()
            self.scene.setSceneRect(rect.adjusted(-150, -200, 150, 100))
            
        # Restore viewport center if we have one
        if self.last_viewport_center:
            self.centerOn(self.last_viewport_center)
            self.last_viewport_center = None
    
    def add_research_subject(self, subject_id: str, name: str, icon: QPixmap, 
                           domain: str, field: str, tier: int, is_base_game: bool,
                           field_coord=None, prerequisites: list = None):
        # Create node
        node = ResearchNode(name, subject_id, icon, is_base_game)
        node.domain = domain  # Store domain for filtering
        self.nodes[subject_id] = node
        
        # Track domain and fields
        self.domains.add(domain)
        if domain not in self.fields_by_domain:
            self.fields_by_domain[domain] = {}
            self.nodes_by_field[domain] = {}
            self.field_max_rows[domain] = {}
        
        # Initialize nodes list for this field if not exists
        if field not in self.nodes_by_field[domain]:
            self.nodes_by_field[domain][field] = []
            self.field_max_rows[domain][field] = 0
        
        # Update max row for this field if needed
        if field_coord and len(field_coord) >= 2:
            current_max = self.field_max_rows[domain][field]
            self.field_max_rows[domain][field] = max(current_max, field_coord[1])
        
        # Calculate field position
        if field not in self.fields_by_domain[domain]:
            # Calculate new field position based on number of existing fields
            field_index = len(self.fields_by_domain[domain])
            field_center = self.top_margin + field_index * (self.vertical_spacing)
            self.fields_by_domain[domain][field] = field_center
        
        # Get field center position
        field_center = self.fields_by_domain[domain][field]
        
        # Calculate grid position
        # Each tier has 2 columns (10 columns total for 5 tiers)
        # field_coord[0] determines which column within the tier
        if field_coord and len(field_coord) >= 2:
            # Calculate column (2 columns per tier)
            column = (tier * 2) + (field_coord[0] % 2)
            # Calculate x position based on column
            x = self.field_width + (column * self.horizontal_spacing)
            # Calculate y position based on row (field_coord[1])
            y = field_center + (field_coord[1] * self.node_vertical_spacing)
        else:
            # Default to first column of tier if no field_coord
            x = self.field_width + (tier * 2 * self.horizontal_spacing)
            y = field_center
        
        node.setPos(x, y)
        self.scene.addItem(node)
        
        # Add node to field's node list
        self.nodes_by_field[domain][field].append(node)
        
        # Set initial domain if not set
        if self.current_domain is None:
            self.current_domain = domain
        
        # Set visibility based on current domain
        node.setVisible(domain == self.current_domain)
        
        # Add connections to prerequisites
        if prerequisites:
            for prereq_list in prerequisites:
                for prereq_id in prereq_list:
                    if prereq_id in self.nodes:
                        self.add_connection(self.nodes[prereq_id], node)
        
        # Update scene rect to include field area and ensure enough space at top
        self.scene.setSceneRect(self.scene.itemsBoundingRect().adjusted(-20, -150, 150, 100))
        
        # Update field backgrounds
        self.update_field_backgrounds()
    
    def add_connection(self, from_node: ResearchNode, to_node: ResearchNode):
        # Create arrow connection
        path = QPainterPath()
        start = from_node.pos()
        end = to_node.pos()
        
        # Calculate control points for curved line
        dx = end.x() - start.x()
        dy = end.y() - start.y()
        
        # Adjust control points based on vertical distance
        ctrl1 = QPointF(start.x() + dx * 0.5, start.y())
        ctrl2 = QPointF(end.x() - dx * 0.5, end.y())
        
        path.moveTo(start)
        path.cubicTo(ctrl1, ctrl2, end)
        
        # Create path item
        connection = QGraphicsPathItem(path)
        connection.setPen(QPen(QColor(0, 100, 150), 2, Qt.PenStyle.SolidLine))
        connection.setZValue(-1)  # Draw connections behind nodes
        connection.from_node = from_node  # Store nodes for visibility checks
        connection.to_node = to_node
        self.scene.addItem(connection)
        
        # Store connection
        from_node.connections.append(connection)
        to_node.connections.append(connection)
    
    def wheelEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            # Calculate zoom factor
            if event.angleDelta().y() > 0:
                factor = self.zoom_factor
            else:
                factor = 1 / self.zoom_factor
            
            # Calculate new zoom level
            new_zoom = self.transform().m11() * factor
            
            # Check zoom bounds
            if self.min_zoom <= new_zoom <= self.max_zoom:
                self.scale(factor, factor)
                self.current_zoom = new_zoom
        else:
            super().wheelEvent(event)
    
    def showEvent(self, event):
        super().showEvent(event)
        # Fit the view to the scene when first shown
        self.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        # Then apply the default zoom
        self.scale(self.current_zoom / self.transform().m11(), self.current_zoom / self.transform().m11())
    
    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Maintain zoom level when resizing
        current_zoom = self.transform().m11()
        self.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        self.scale(current_zoom / self.transform().m11(), current_zoom / self.transform().m11())
    
    def mousePressEvent(self, event):
        """Handle mouse press events"""
        super().mousePressEvent(event)
        if event.button() == Qt.MouseButton.RightButton:
            # Only show context menu if we didn't click on a node
            item = self.scene.itemAt(self.mapToScene(event.pos()), self.transform())
            if not item or not isinstance(item, ResearchNode):
                self.show_view_context_menu(event.globalPosition().toPoint())

    def show_node_context_menu(self, node: ResearchNode, pos: QPoint):
        """Show context menu for a research node"""
        menu = QMenu(self)  # Create menu with parent
        delete_action = menu.addAction("Delete")
        delete_action.triggered.connect(lambda: self.node_delete_requested.emit(node.subject_id))
        menu.exec(pos)

    def show_view_context_menu(self, pos: QPoint):
        """Show context menu for the view itself"""
        menu = QMenu(self)  # Create menu with parent
        
        # Add submenu for different research types
        add_menu = menu.addMenu("Add Research Subject")
        
        # Add options for faction and regular research
        faction_action = add_menu.addAction("Add Faction Research")
        faction_action.triggered.connect(lambda: self.add_subject_requested.emit("faction"))
        
        regular_action = add_menu.addAction("Add Regular Research")
        regular_action.triggered.connect(lambda: self.add_subject_requested.emit("regular"))
        
        menu.exec(pos) 