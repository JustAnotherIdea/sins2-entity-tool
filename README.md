# Sins 2 Entity Tool

A powerful GUI tool for modding Sins of a Solar Empire II entities, research, and other game data.

This is not an official tool. For the official tools go to [https://github.com/StardockCorp/sins2modtools](https://github.com/StardockCorp/sins2modtools), or download them from steam.

## NOTE: This is a Beta release

Backup your data before use!

This is a beta release, and as such, there are no guarantees that it will work as expected 100% of the time.

Create a copy of your mod folder before using this tool, and save your changes often.

## [Demo Video](https://youtu.be/2VGNgComdik?si=5GnYF6CmZ_XoJkFS)

## Features

- 🎮 Edit game entities, research trees, and other game data with a user-friendly interface
- 🔄 Real-time preview of changes
- 🎨 Visual texture and icon selection
- 🔊 Sound file preview and selection
- 📝 Built-in localization text editor
- ↩️ Undo/Redo functionality for *most* changes
- 🔍 Smart search and filtering capabilities
- 🔄 Automatic updates
- 📊 Base game file and schema reference support

### Setup

1. Download the latest release from [Latest Release](https://github.com/JustAnotherIdea/sins2-entity-tool/releases/latest)
   - For Windows users: Download the `.exe` file, place it in a folder, and run it.
   - For other platforms: Download the source code and follow the manual installation steps


#### Manual Installation

1. Clone the repository:
```bash
git clone https://github.com/JustAnotherIdea/sins2-entity-tool.git
cd sins2-entity-tool
```

2. Create and activate a virtual environment (recommended):
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

1. Launch the application:
    - If using the installer version, run the installed application
    - If using source code: `python main.py`

2. First-time Setup:
    - Set your base game folder path in the settings
    - Set your mod folder path

3. Basic Operations:
    - Open mod folder by clicking the "Open Mod Folder" button or dragging and dropping the mod folder onto the application
        - If you are starting a fresh mod, or are new to modding, you can use another mod as a template.
    - Make changes using the intuitive form interface
    - Save changes using the Save button or Ctrl+S
    - Undo/Redo using Ctrl+Z and Ctrl+Y or the buttons in the toolbar
    - Select the player faction using the dropdown in the top right corner

    - Create or delete a player faction by clicking the "+/-" button
    - Refresh any view with the refresh button in the corner (this is needed when making changes to the research tree, and can help fix some issues).

4. Features:
    - Things are styled bold if they are required, italic if they are from the base game, and greyed out if they are non-editable.
    - Right click for context menus.
    - Right click anywhere inside the entity data to add a "root" property (this refresh may take a second, so be patient).
    - Each property and array has a context menu to delete it, or add to it.
    - Each "string" value is displayed as the "type" it is.
        - References to other entities are shown as buttons.
        - References to localized text are shown as two seperate text fields (one for the key, one for the value).
        - References to textures are shown as a text field with a preview of the texture.
    - Each string has a context menu to select from various options.
        - File: Select any file from the mod or base game, and optionally create a copy of it.
            - When createing a copy from the base game you will be given the option to override the file by keeping the same name and not adding it to the manifest.
            - Otherwise it will be added to the manifest and the mod folder with a new name.
        - Uniforms: Select any value from uniforms from the mod or base game.
        - Localized Text: Select any localized text from the mod or base game.
        - Texture: Select any texture from the mod or base game, and see a preview of it.
        - Sound: Select any sound from the mod or base game, and hear a preview of it.
    - View and edit the research tree using the "Research" tab.
        - Change domains with the buttons on the top.
        - Click on a research subject to edit it.
        - Right click anywhere to create a new research subject (copying one from the base game or mod, this cannot be undone).
        - Right click on a research subject to delete it (this cannot be undone).
    - Other tabs are mostly self explanatory.
        - Click on an entity to view its properties in the appropriate panel and edit them there.
        - Refresh any time you feel like the view has not updated correctly.
        - Note that larger entities may take a second or two to load, and adding/removing root properties causes a full refresh.

## Known Issues

- Sometimes the context menu does not appear (or does not show the correct options). If this happens, try refreshing the view.
- Adding or removing a root property to a large entity may take a second or two.
- Strings may become a button to an exotic file when that doesn't make sense.
- Multiple undo/redo operations may cause the application to not show the correct view. If this happens, refresh the view.
- It is possible to undo/redo past what you should be able to do. If this happens, the application may crash.
- Invalid properties will not be shown in the view at all (in the future they will be shown in a different color).
- Player icons, portrait files, and sound files are not yet supported.

## Development

### Project Structure

- `main.py` - Application entry point (use --dev to disable version checking)
- `entityTool.py` - Main application logic and GUI (this file is way too long, I apologize in advance)
- `research_view.py` - Research tree visualization and editing
- `command_stack.py` - Undo/redo functionality implementation
- `version_checker.py` - Update checking and management
- `style.qss` - Application styling
- `config.json` - User configuration storage

### Building from Source

To create an executable:

1. Install PyInstaller:
```bash
pip install pyinstaller
```

2. Build the executable:
```bash
python -m PyInstaller entity-tool.spec
```

The executable will be created in the `dist` directory.

## Configuration

The application stores its configuration in `config.json`, which includes:
- Base game folder path
- Mod folder path

## Acknowledgments

- Sins of a Solar Empire II developers for the amazing game and the tools they have provided
- All the modders who created the mods that I have used in testing
- PyQt6 framework
- Pygame (for the sound preview)

## Support

For support, please:
1. Check the existing issues on GitHub
2. Create a new issue if your problem hasn't been reported (I will be adding known issues as they are found)
3. Join the [Discord server](https://discord.com/invite/sinsofasolarempire) and head over to the [Entity Tool Thread](https://discord.com/channels/266693357093257216/1329849082675462144) in the sins2-modders-showcase channel.


## Roadmap

Check the [GitHub Issues](https://github.com/JustAnotherIdea/sins2-entity-tool/issues) and [project board](https://github.com/users/JustAnotherIdea/projects/6) for the latest updates.
