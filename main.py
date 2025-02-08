from PyQt6.QtWidgets import QApplication, QMessageBox
from entityTool import EntityToolGUI
from version_checker import VersionChecker
import sys
import logging
from pathlib import Path
import argparse

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Sins 2 Entity Tool')
    parser.add_argument('--dev', action='store_true', help='Run in development mode (disables version check)')
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    if args.dev:
        logging.info("Running in development mode")
    
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

    # Check for updates (skip in dev mode)
    version_checker = VersionChecker(dev_mode=args.dev)
    has_update, download_url, release_message, current_version, latest_version, is_frozen = version_checker.check_for_updates()
    
    # Set window title with version
    title = f'Sins 2 Entity Tool v{current_version}'
    if args.dev:
        title += ' (Dev)'
    elif not is_frozen:
        title += ' (Source)'
    window.setWindowTitle(title)
    
    if has_update:
        update_type = "executable" if is_frozen else "source code"
        message = f'A new version is available (v{current_version} → v{latest_version}).\n\nRelease Notes:\n{release_message}\n\nWould you like to download and install the updated {update_type}?'
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