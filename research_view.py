from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                            QGraphicsScene, QGraphicsView, QGraphicsItem, QGraphicsPathItem, 
                            QGraphicsTextItem, QGraphicsPixmapItem, QGraphicsRectItem)
from PyQt6.QtCore import Qt, QRectF, QPointF, pyqtSignal, QRect
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
        
        # Draw background
        path = QPainterPath()
        path.addRoundedRect(self.boundingRect(), self.border_radius, self.border_radius)
        painter.fillPath(path, QBrush(gradient))
        
        # Draw border
        border_color = QColor(0, 200, 255) if self.isSelected() or self.hovered else QColor(0, 100, 150)
        painter.setPen(QPen(border_color, 2))
        painter.drawPath(path)
        
        # Draw icon if available
        if self.icon and not self.icon.isNull():
            # Scale icon to fit while maintaining aspect ratio
            icon_size = min(40, self.height - 20)  # Maximum icon size
            scaled_icon = self.icon.scaled(icon_size, icon_size, 
                                         Qt.AspectRatioMode.KeepAspectRatio,
                                         Qt.TransformationMode.SmoothTransformation)
            
            # Create a QRect for the icon position and size
            icon_x = int(-scaled_icon.width() / 2)
            icon_y = int(-self.height/2 + 10)
            icon_rect = QRect(icon_x, icon_y, scaled_icon.width(), scaled_icon.height())
            painter.drawPixmap(icon_rect, scaled_icon)
        
        # Draw text
        if self.is_base_game:
            painter.setPen(QPen(QColor(150, 150, 150)))
            font = painter.font()
            font.setItalic(True)
            painter.setFont(font)
        else:
            painter.setPen(QPen(Qt.GlobalColor.white))
        
        text_rect = self.boundingRect().adjusted(0, self.height/2 - 30, 0, -5)
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

class ResearchTreeView(QGraphicsView):
    node_clicked = pyqtSignal(str)  # Signal emitted when a node is clicked, passes subject_id
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        
        # Style settings
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.setBackgroundBrush(QBrush(QColor(0, 20, 30)))
        
        # Node layout settings
        self.field_width = 400  # Width for field background/label area
        self.horizontal_spacing = 300  # Spacing between tiers
        self.vertical_spacing = 180  # Spacing between fields
        self.node_vertical_spacing = 25  # Spacing between nodes in the same field
        self.top_margin = 50  # Space from top of scene to first field
        self.base_field_height = 120  # Base height for fields with single row
        self.row_height = 40  # Height per row in a field
        self.nodes = {}  # Store nodes by subject_id
        self.current_domain = None
        self.domains = set()  # Track available domains
        self.fields_by_domain = {}  # Track fields per domain {domain: {field: y_pos}}
        self.field_backgrounds = {}  # Store field background images {field: QPixmap}
        self.nodes_by_field = {}  # Track nodes in each field {field: [nodes]}
        self.field_max_rows = {}  # Track maximum row number for each field {domain: {field: max_row}}
        
        # Add tier headers
        self.add_tier_headers()
    
    def add_tier_headers(self):
        """Add tier headers to the scene"""
        for i in range(1, 6):
            text = QGraphicsTextItem(f"Tier {i}")
            text.setDefaultTextColor(QColor(0, 200, 255))
            font = text.font()
            font.setPointSize(12)
            font.setBold(True)
            text.setFont(font)
            
            # Position header above the tier's nodes, offset by field area width
            x = self.field_width + i * self.horizontal_spacing - text.boundingRect().width() / 2
            y = -100  # Increased margin above nodes
            text.setPos(x, y)
            self.scene.addItem(text)
    
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
        # Clear existing field labels
        for item in self.scene.items():
            if isinstance(item, QGraphicsTextItem) and hasattr(item, 'is_field_label'):
                self.scene.removeItem(item)
        
        if self.current_domain not in self.fields_by_domain:
            return
            
        for field, y_pos in sorted(self.fields_by_domain[self.current_domain].items()):
            text = QGraphicsTextItem(field)
            text.setDefaultTextColor(QColor(0, 200, 255))
            font = text.font()
            font.setPointSize(14)  # Increased font size
            font.setBold(True)
            text.setFont(font)
            text.is_field_label = True  # Mark as field label
            
            # Position label on the left side
            x = 20  # Small margin from left edge
            y = y_pos - text.boundingRect().height() / 2
            text.setPos(x, y)
            self.scene.addItem(text)
    
    def set_domain(self, domain: str):
        """Switch to displaying a different domain"""
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
        
        # Adjust tier (tier 0 in file = tier 1 in display)
        display_tier = tier + 1
        
        # Calculate position based on tier and field_coord
        tier_x = self.field_width + display_tier * self.horizontal_spacing
        
        # Each tier has two columns. field_coord[0] determines which column (0,1,2 = left, 3,4,5 = right)
        if field_coord and len(field_coord) >= 2:
            is_right_column = field_coord[0] >= 3
            x = tier_x + (self.horizontal_spacing/2 if is_right_column else 0)
        else:
            # Default to left column if no field_coord
            x = tier_x
        
        # Use field for vertical positioning
        if field not in self.fields_by_domain[domain]:
            # Calculate new field position based on number of existing fields
            field_index = len(self.fields_by_domain[domain])
            # Calculate total height of previous fields
            total_previous_height = 0
            for prev_field in list(self.fields_by_domain[domain].keys()):
                max_row = self.field_max_rows[domain][prev_field]
                field_height = max(self.base_field_height, (max_row + 1) * self.row_height)
                total_previous_height += field_height + self.vertical_spacing
            
            field_height = max(self.base_field_height, (self.field_max_rows[domain][field] + 1) * self.row_height)
            field_center = self.top_margin + total_previous_height + field_height/2
            self.fields_by_domain[domain][field] = field_center
        
        # Get field center position and calculate field height
        field_center = self.fields_by_domain[domain][field]
        field_height = max(self.base_field_height, (self.field_max_rows[domain][field] + 1) * self.row_height)
        
        # Calculate y position using field_coord
        if field_coord and len(field_coord) >= 2:
            # Calculate position based on row number
            row_spacing = field_height / (self.field_max_rows[domain][field] + 1)
            y = field_center - field_height/2 + (field_coord[1] + 0.5) * row_spacing
        else:
            # If no field_coord, center the node in its field
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
    
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        
    def wheelEvent(self, event):
        # Handle zoom with mouse wheel
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            factor = 1.2
            if event.angleDelta().y() < 0:
                factor = 1.0 / factor
            self.scale(factor, factor)
        else:
            super().wheelEvent(event) 