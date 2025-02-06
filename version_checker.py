import requests
from pathlib import Path
import sys
import os
import logging
from packaging import version

class VersionChecker:
    def __init__(self):
        self.github_api = "https://api.github.com/repos/JustAnotherIdea/sins2-entity-tool/releases/latest"
        self.current_version = "0.0.1"  # This will be updated during build
        self.app_dir = self._get_app_directory()
        
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

    def check_for_updates(self):
        try:
            response = requests.get(self.github_api)
            response.raise_for_status()
            latest = response.json()
            
            latest_version = ''.join(c for c in latest['tag_name'] if c.isdigit() or c == '.')
            current_version = ''.join(c for c in self.current_version if c.isdigit() or c == '.')
            
            if version.parse(latest_version) > version.parse(current_version):
                return True, latest['assets'][0]['browser_download_url']
            return False, None
            
        except Exception as e:
            logging.error(f"Failed to check for updates: {e}")
            return False, None

    def download_update(self, url):
        try:
            response = requests.get(url, stream=True)
            response.raise_for_status()
            
            # Create temp directory in app directory
            temp_dir = Path(self.app_dir) / "temp"
            temp_dir.mkdir(exist_ok=True)
            
            # Download to a temporary file first
            temp_update = temp_dir / "update.exe.tmp"
            with open(temp_update, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            # Get the path to the current executable
            if getattr(sys, 'frozen', False):
                current_exe = Path(sys.executable)
                new_exe = temp_dir / "update.exe"
                
                # Rename the downloaded file to its final name
                if new_exe.exists():
                    new_exe.unlink()
                temp_update.rename(new_exe)
                
                # Create a batch file to:
                # 1. Wait for our process to exit
                # 2. Delete the old exe
                # 3. Move the new exe
                # 4. Start the new exe
                # 5. Delete itself
                batch_file = temp_dir / "update.bat"
                batch_contents = f'''@echo off
timeout /t 1 /nobreak >nul
del /f "{current_exe}"
move "{new_exe}" "{current_exe}"
start "" "{current_exe}"
del "%~f0"
'''
                batch_file.write_text(batch_contents)
                
                # Run the batch file and exit
                os.startfile(str(batch_file))
                sys.exit(0)
            
        except Exception as e:
            logging.error(f"Failed to download update: {e}")
            return False 