import requests
from PyQt6.QtWidgets import QMessageBox
from pathlib import Path
import sys
import os
import logging
from packaging import version
import markdown

class VersionChecker:
    def __init__(self, dev_mode=False):
        self.github_api = "https://api.github.com/repos/JustAnotherIdea/sins2-entity-tool/releases/latest"
        self.current_version = "0.0.1"  # This will be updated during build
        self.app_dir = self._get_app_directory()
        self.dev_mode = dev_mode
        
    def _get_app_directory(self):
        """Get the appropriate app directory based on whether we're frozen"""
        if getattr(sys, 'frozen', False):
            return Path(sys.executable).parent
        return Path(__file__).parent

    def _get_resource_path(self, resource_name: str) -> Path:
        """Get the appropriate path for a resource file"""
        if getattr(sys, 'frozen', False):
            return Path(sys._MEIPASS) / resource_name
        return Path(__file__).parent / resource_name

    def _process_markdown(self, text):
        """Convert markdown to HTML with GitHub-style formatting"""
        # Configure markdown extensions for GitHub-style formatting
        md = markdown.Markdown(extensions=['extra', 'nl2br', 'sane_lists'])
        return md.convert(text)

    def check_for_updates(self):
        # Skip update check in dev mode
        if self.dev_mode:
            logging.info("Skipping update check (dev mode)")
            return False, None, None, self.current_version, None, getattr(sys, 'frozen', False)
        try:
            response = requests.get(self.github_api)
            response.raise_for_status()
            latest = response.json()
            
            latest_version = ''.join(c for c in latest['tag_name'] if c.isdigit() or c == '.')
            current_version = ''.join(c for c in self.current_version if c.isdigit() or c == '.')
            
            if version.parse(latest_version) > version.parse(current_version):
                # Find the appropriate download URL based on installation type
                download_url = None
                is_frozen = getattr(sys, 'frozen', False)
                
                for asset in latest['assets']:
                    if is_frozen and asset['name'].endswith('.exe'):
                        download_url = asset['browser_download_url']
                        break
                    elif not is_frozen and asset['name'].endswith('.zip'):
                        download_url = asset['browser_download_url']
                        break
                
                if not download_url:
                    # Fallback to zipball if no specific asset found
                    download_url = latest['zipball_url']
                
                # Convert release notes from markdown to HTML
                release_notes_html = self._process_markdown(latest['body'])
                
                return True, download_url, release_notes_html, current_version, latest_version, is_frozen
            return False, None, None, current_version, latest_version, getattr(sys, 'frozen', False)
            
        except Exception as e:
            logging.error(f"Failed to check for updates: {e}")
            return False, None, None, self.current_version, None, getattr(sys, 'frozen', False)

    def download_update(self, url):
        is_frozen = getattr(sys, 'frozen', False)
        
        try:
            response = requests.get(url, stream=True)
            response.raise_for_status()
            
            if is_frozen:
                return self._update_executable(response)
            else:
                return self._update_source(response, url)
    
        except Exception as e:
            logging.error(f"Failed to download update: {e}")
            return False
            
    def _update_executable(self, response):
        """Handle updating the frozen executable"""
        try:
            current_exe = Path(sys.executable)
            temp_update = current_exe.with_name('update.exe.tmp')
            
            # Download to a temporary file
            with open(temp_update, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            # Create batch file in the same directory
            batch_file = current_exe.with_name('update.bat')
            batch_contents = f'''@echo off
:wait
timeout /t 1 /nobreak >nul
tasklist /FI "IMAGENAME eq {current_exe.name}" 2>NUL | find /I /N "{current_exe.name}">NUL
if "%ERRORLEVEL%"=="0" goto wait
del /f "{current_exe}"
move "{temp_update}" "{current_exe}"
del "%~f0"
'''
            batch_file.write_text(batch_contents)
            
            # Run the batch file and exit
            os.startfile(str(batch_file))
            sys.exit(0)
            
        except Exception as e:
            logging.error(f"Failed to update executable: {e}")
            if 'temp_update' in locals() and temp_update.exists():
                try:
                    temp_update.unlink()
                except:
                    pass
            return False
            
    def _update_source(self, response, url):
        """Handle updating source installation"""
        try:
            import zipfile
            import io
            import shutil
            
            # Create a temporary directory for the update
            temp_dir = self.app_dir / 'update_temp'
            if temp_dir.exists():
                shutil.rmtree(temp_dir)
            temp_dir.mkdir()
            
            # Download and extract the zip
            zip_data = io.BytesIO()
            for chunk in response.iter_content(chunk_size=8192):
                zip_data.write(chunk)
            
            zip_data.seek(0)
            with zipfile.ZipFile(zip_data) as zip_ref:
                # Get the root directory name in the zip
                root_dir = zip_ref.namelist()[0].split('/')[0]
                # Extract everything
                zip_ref.extractall(temp_dir)
            
            # Move files from the extracted directory to the app directory
            extracted_dir = temp_dir / root_dir
            
            # Copy all files except those that should be preserved
            preserve_files = {'.git', '.github', '.gitignore', 'config.json', 'venv', '__pycache__'}
            
            for item in extracted_dir.iterdir():
                if item.name not in preserve_files:
                    target = self.app_dir / item.name
                    if target.exists():
                        if target.is_dir():
                            shutil.rmtree(target)
                        else:
                            target.unlink()
                    if item.is_dir():
                        shutil.copytree(item, target)
                    else:
                        shutil.copy2(item, target)
            
            # Clean up
            shutil.rmtree(temp_dir)
            
            # Show success message and prompt for restart
            QMessageBox.information(None, "Update Successful", 
                "The update has been downloaded and installed. Please restart the application for the changes to take effect.")
            
            return True
            
        except Exception as e:
            logging.error(f"Failed to update source: {e}")
            if 'temp_dir' in locals() and temp_dir.exists():
                try:
                    shutil.rmtree(temp_dir)
                except:
                    pass
            return False 