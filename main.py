from PyQt6.QtWidgets import QApplication
from entityTool import EntityToolGUI
import sys
import logging

def main():
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    app = QApplication(sys.argv)
    
    # Create and show main window
    window = EntityToolGUI()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main() 