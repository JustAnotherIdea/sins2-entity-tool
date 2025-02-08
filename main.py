from PyQt6.QtWidgets import QApplication, QMessageBox
from entityTool import EntityToolGUI
from version_checker import VersionChecker
import sys
import logging
from pathlib import Path

def main():
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    app = QApplication(sys.argv)
    
    # Load and apply stylesheet
    style_path = Path(__file__).parent / 'style.qss'
    if style_path.exists():
        with open(style_path, 'r') as f:
            app.setStyleSheet(f.read())
            logging.info("Loaded stylesheet")
    else:
        print(f"Stylesheet not found at {style_path}")
    
    # Create and show main window
    window = EntityToolGUI()
    window.show()

    # Check for updates
    version_checker = VersionChecker()
    has_update, download_url, release_message = version_checker.check_for_updates()
    if has_update:
        message = 'A new version is available.\n\nRelease Notes:\n' + release_message + '\n\nWould you like to download and install it?'
        reply = QMessageBox.question(
            window,
            'Update Available',
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )
        if reply == QMessageBox.StandardButton.Yes:
            version_checker.download_update(download_url)
    
    sys.exit(app.exec())

if __name__ == '__main__':
    main() 