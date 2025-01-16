from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                            QGraphicsScene, QGraphicsView, QGraphicsItem, QGraphicsPathItem)
from PyQt6.QtCore import Qt, QRectF, QPointF, pyqtSignal
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
            icon_rect = QRectF(-20, -self.height/2 + 10, 40, 40)
            source_rect = QRectF(0, 0, self.icon.width(), self.icon.height())
            painter.drawPixmap(icon_rect, self.icon, source_rect)
        
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
        self.horizontal_spacing = 250  # Increased spacing between tiers
        self.vertical_spacing = 100    # Spacing between nodes in the same tier
        self.nodes = {}  # Store nodes by subject_id
        self.field_positions = {}  # Track used field positions
        
    def add_research_subject(self, subject_id: str, name: str, icon: QPixmap, 
                           domain: str, field: str, tier: int, is_base_game: bool,
                           field_coord=None, prerequisites: list = None):
        # Create node
        node = ResearchNode(name, subject_id, icon, is_base_game)
        self.nodes[subject_id] = node
        
        # Calculate position based on tier and field coordinates
        x = tier * self.horizontal_spacing
        
        if field_coord:
            # Use provided field coordinates
            y = field_coord[1] * self.vertical_spacing
            field_key = (field, field_coord[1])
        else:
            # If no field coordinates, generate a position
            if field not in self.field_positions:
                self.field_positions[field] = len(self.field_positions)
            y = self.field_positions[field] * self.vertical_spacing
            field_key = (field, self.field_positions[field])
        
        node.setPos(x, y)
        self.scene.addItem(node)
        
        # Add connections to prerequisites
        if prerequisites:
            for prereq_list in prerequisites:
                for prereq_id in prereq_list:
                    if prereq_id in self.nodes:
                        self.add_connection(self.nodes[prereq_id], node)
        
        # Update scene rect to ensure all nodes are visible
        self.scene.setSceneRect(self.scene.itemsBoundingRect().adjusted(-100, -100, 100, 100))
    
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