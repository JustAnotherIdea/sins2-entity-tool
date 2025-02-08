from PyQt6.QtWidgets import QApplication, QMessageBox, QDialog, QVBoxLayout, QTextBrowser
from entityTool import EntityToolGUI
from version_checker import VersionChecker
import sys
import logging
from pathlib import Path
import argparse
import markdown

class UpdateDialog(QDialog):
    def __init__(self, current_version, latest_version, release_notes, update_type, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Update Available')
        self.setMinimumWidth(600)
        self.setMinimumHeight(400)
        
        layout = QVBoxLayout(self)
        
        # Create text browser for rich text display
        text_browser = QTextBrowser()
        text_browser.setOpenExternalLinks(True)  # Allow clicking links
        
        # Convert markdown to HTML
        md = markdown.Markdown(extensions=['extra'])
        html_content = f'''
            <h2>Update Available</h2>
            <p>A new version is available (v{current_version} → v{latest_version})</p>
            <h3>Release Notes:</h3>
            {md.convert(release_notes)}
            <p>Would you like to download and install the updated {update_type}?</p>
        '''
        text_browser.setHtml(html_content)
        
        layout.addWidget(text_browser)
        
        # Add standard buttons
        from PyQt6.QtWidgets import QDialogButtonBox
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Yes | QDialogButtonBox.StandardButton.No
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

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

    # Check for updates
    version_checker = VersionChecker(args.dev)
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
        dialog = UpdateDialog(current_version, latest_version, release_message, update_type, window)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            version_checker.download_update(download_url)
    
    sys.exit(app.exec())

if __name__ == '__main__':
    main() 