# --- Standard Library Imports ---
import json
import os
import sys

# --- PyQt5 Imports ---
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QMessageBox, QAbstractItemView, QLabel
)

# --- Local Application Imports ---
from ...i18n.translator import get_translation
from ..main_window import get_app_icon_object
from ...utils.resolution import get_dark_theme

class UpdateCheckDialog(QDialog):
    """
    A dialog that lists all creator .json profiles with checkboxes
    and allows the user to select multiple to check for updates.
    """
    
    def __init__(self, user_data_path, parent_app_ref, parent=None):
        super().__init__(parent)
        self.parent_app = parent_app_ref
        self.user_data_path = user_data_path
        self.selected_profiles_list = [] # Will store a list of {'name': ..., 'data': ...}

        self._init_ui()
        self._load_profiles()
        self._retranslate_ui()

        # Apply theme from parent
        if self.parent_app and self.parent_app.current_theme == "dark":
            scale = getattr(self.parent_app, 'scale_factor', 1)
            self.setStyleSheet(get_dark_theme(scale))
        else:
            self.setStyleSheet("")

    def _init_ui(self):
        """Initializes the UI components."""
        self.setWindowTitle("Check for Updates")
        self.setMinimumSize(400, 450)
        
        app_icon = get_app_icon_object()
        if app_icon and not app_icon.isNull():
            self.setWindowIcon(app_icon)

        layout = QVBoxLayout(self)

        self.info_label = QLabel("Select creator profiles to check for updates:")
        layout.addWidget(self.info_label)
        
        # --- List Widget with Checkboxes ---
        self.list_widget = QListWidget()
        # No selection mode, we only care about checkboxes
        self.list_widget.setSelectionMode(QAbstractItemView.NoSelection)
        layout.addWidget(self.list_widget)

        # --- All Buttons in One Horizontal Layout ---
        button_layout = QHBoxLayout()
        button_layout.setSpacing(6)  # small even spacing between all buttons

        self.select_all_button = QPushButton("Select All")
        self.select_all_button.clicked.connect(self._toggle_all_checkboxes)

        self.deselect_all_button = QPushButton("Deselect All")
        self.deselect_all_button.clicked.connect(self._toggle_all_checkboxes)

        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.reject)

        self.check_button = QPushButton("Check Selected")
        self.check_button.clicked.connect(self.on_check_selected)
        self.check_button.setDefault(True)

        # Add buttons without a stretch (so no large gap)
        button_layout.addWidget(self.select_all_button)
        button_layout.addWidget(self.deselect_all_button)
        button_layout.addWidget(self.close_button)
        button_layout.addWidget(self.check_button)

        layout.addLayout(button_layout)

    def _tr(self, key, default_text=""):
        """Helper to get translation based on current app language."""
        if callable(get_translation) and self.parent_app:
            return get_translation(self.parent_app.current_selected_language, key, default_text)
        return default_text

    def _retranslate_ui(self):
        """Translates the UI elements."""
        self.setWindowTitle(self._tr("update_check_dialog_title", "Check for Updates"))
        self.info_label.setText(self._tr("update_check_dialog_info_multiple", "Select creator profiles to check for updates:"))
        self.select_all_button.setText(self._tr("select_all_button_text", "Select All"))
        self.deselect_all_button.setText(self._tr("deselect_all_button_text", "Deselect All"))
        self.check_button.setText(self._tr("update_check_dialog_check_button", "Check Selected"))
        self.close_button.setText(self._tr("update_check_dialog_close_button", "Close"))

    def _load_profiles(self):
        """Loads all .json files from the creator_profiles directory as checkable items."""
        appdata_dir = self.user_data_path
        profiles_dir = os.path.join(appdata_dir, "creator_profiles")

        if not os.path.isdir(profiles_dir):
            QMessageBox.warning(self, 
                self._tr("update_check_dir_not_found_title", "Directory Not Found"),
                self._tr("update_check_dir_not_found_msg", 
                         "The creator profiles directory does not exist yet.\n\nPath: {path}")
                         .format(path=profiles_dir))
            return

        profiles_found = []
        for filename in os.listdir(profiles_dir):
            if filename.endswith(".json"):
                filepath = os.path.join(profiles_dir, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    # Basic validation to ensure it's a valid profile
                    if 'creator_url' in data and 'processed_post_ids' in data:
                        creator_name = os.path.splitext(filename)[0]
                        profiles_found.append({'name': creator_name, 'data': data})
                    else:
                        print(f"Skipping invalid profile: {filename}")
                except Exception as e:
                    print(f"Failed to load profile {filename}: {e}")

        profiles_found.sort(key=lambda x: x['name'].lower())

        for profile_info in profiles_found:
            item = QListWidgetItem(profile_info['name'])
            item.setData(Qt.UserRole, profile_info)
            # --- Make item checkable ---
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            self.list_widget.addItem(item)
            
        if not profiles_found:
            self.list_widget.addItem(self._tr("update_check_no_profiles", "No creator profiles found."))
            self.list_widget.setEnabled(False)
            self.check_button.setEnabled(False)
            self.select_all_button.setEnabled(False)
            self.deselect_all_button.setEnabled(False)

    def _toggle_all_checkboxes(self):
        """Handles Select All and Deselect All button clicks."""
        sender = self.sender()
        check_state = Qt.Checked if sender == self.select_all_button else Qt.Unchecked
        
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.flags() & Qt.ItemIsUserCheckable:
                item.setCheckState(check_state)

    def on_check_selected(self):
        """Handles the 'Check Selected' button click."""
        self.selected_profiles_list = []
        
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.checkState() == Qt.Checked:
                profile_info = item.data(Qt.UserRole)
                if profile_info:
                    self.selected_profiles_list.append(profile_info)
        
        if not self.selected_profiles_list:
            QMessageBox.warning(self, 
                self._tr("update_check_no_selection_title", "No Selection"),
                self._tr("update_check_no_selection_msg", "Please select at least one creator to check."))
            return
        
        self.accept()

    def get_selected_profiles(self):
        """Returns the list of profile data selected by the user."""
        return self.selected_profiles_list