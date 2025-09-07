# --- PyQt5 Imports ---
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtWidgets import (
    QApplication, QDialog, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QMessageBox, QPushButton, QVBoxLayout, QAbstractItemView, QFileDialog
)

# --- Local Application Imports ---
from ...i18n.translator import get_translation
from ..assets import get_app_icon_object
# Corrected Import: The filename uses PascalCase.
from .ExportOptionsDialog import ExportOptionsDialog
from ...utils.resolution import get_dark_theme

class ErrorFilesDialog(QDialog):
    """
    Dialog to display files that were skipped due to errors and
    allows the user to retry downloading them or export the list of URLs.
    """

    # Signal emitted with a list of file info dictionaries to retry
    retry_selected_signal = pyqtSignal(list)

    def __init__(self, error_files_info_list, parent_app, parent=None):
        """
        Initializes the dialog.

        Args:
            error_files_info_list (list): A list of dictionaries, each containing
                                          info about a failed file.
            parent_app (DownloaderApp): A reference to the main application window
                                      for theming and translations.
            parent (QWidget, optional): The parent widget. Defaults to None.
        """
        super().__init__(parent)
        self.parent_app = parent_app
        self.setModal(True)
        self.error_files = error_files_info_list

        # --- Basic Window Setup ---
        app_icon = get_app_icon_object()
        if app_icon and not app_icon.isNull():
            self.setWindowIcon(app_icon)

        # --- START OF FIX ---
        # Get the user-defined scale factor from the parent application.
        scale_factor = getattr(self.parent_app, 'scale_factor', 1.0)

        # Define base dimensions and apply the correct scale factor.
        base_width, base_height = 550, 400
        self.setMinimumSize(int(base_width * scale_factor), int(base_height * scale_factor))
        self.resize(int(base_width * scale_factor * 1.1), int(base_height * scale_factor * 1.1))
        # --- END OF FIX ---

        # --- Initialize UI and Apply Theming ---
        self._init_ui()
        self._retranslate_ui()
        self._apply_theme()

    def _init_ui(self):
        """Initializes all UI components and layouts for the dialog."""
        main_layout = QVBoxLayout(self)

        self.info_label = QLabel()
        self.info_label.setWordWrap(True)
        main_layout.addWidget(self.info_label)

        if self.error_files:
            self.files_list_widget = QListWidget()
            self.files_list_widget.setSelectionMode(QAbstractItemView.NoSelection)
            self._populate_list()
            main_layout.addWidget(self.files_list_widget)

        # --- Control Buttons ---
        buttons_layout = QHBoxLayout()
        self.select_all_button = QPushButton()
        self.select_all_button.clicked.connect(self._select_all_items)
        buttons_layout.addWidget(self.select_all_button)

        self.retry_button = QPushButton()
        self.retry_button.clicked.connect(self._handle_retry_selected)
        buttons_layout.addWidget(self.retry_button)

        self.export_button = QPushButton()
        self.export_button.clicked.connect(self._handle_export_errors_to_txt)
        buttons_layout.addWidget(self.export_button)
        buttons_layout.addStretch(1)

        self.ok_button = QPushButton()
        self.ok_button.clicked.connect(self.accept)
        self.ok_button.setDefault(True)
        buttons_layout.addWidget(self.ok_button)
        main_layout.addLayout(buttons_layout)

        # Enable/disable buttons based on whether there are errors
        has_errors = bool(self.error_files)
        self.select_all_button.setEnabled(has_errors)
        self.retry_button.setEnabled(has_errors)
        self.export_button.setEnabled(has_errors)

    def _populate_list(self):
        """Populates the list widget with details of the failed files."""
        for error_info in self.error_files:
            filename = error_info.get('forced_filename_override',
                                      error_info.get('file_info', {}).get('name', 'Unknown Filename'))
            post_title = error_info.get('post_title', 'Unknown Post')
            post_id = error_info.get('original_post_id_for_log', 'N/A')

            creator_name = "Unknown Creator"
            service = error_info.get('service')
            user_id = error_info.get('user_id')
            
            # Check if we have the necessary info and access to the cache
            if service and user_id and hasattr(self.parent_app, 'creator_name_cache'):
                creator_key = (service.lower(), str(user_id))
                # Look up the name, fall back to the user_id if not found
                creator_name = self.parent_app.creator_name_cache.get(creator_key, user_id)

            item_text = f"File: {filename}\nCreator: {creator_name} - Post: '{post_title}' (ID: {post_id})"
            list_item = QListWidgetItem(item_text)
            list_item.setData(Qt.UserRole, error_info)
            list_item.setFlags(list_item.flags() | Qt.ItemIsUserCheckable)
            list_item.setCheckState(Qt.Unchecked)
            self.files_list_widget.addItem(list_item)

    def _tr(self, key, default_text=""):
        """Helper to get translation based on the main application's current language."""
        if callable(get_translation) and self.parent_app:
            return get_translation(self.parent_app.current_selected_language, key, default_text)
        return default_text

    def _retranslate_ui(self):
        """Sets the text for all translatable UI elements."""
        self.setWindowTitle(self._tr("error_files_dialog_title", "Files Skipped Due to Errors"))
        if not self.error_files:
            self.info_label.setText(self._tr("error_files_no_errors_label", "No files were recorded as skipped..."))
        else:
            self.info_label.setText(self._tr("error_files_found_label", "The following {count} file(s)...").format(count=len(self.error_files)))

        self.select_all_button.setText(self._tr("error_files_select_all_button", "Select All"))
        self.retry_button.setText(self._tr("error_files_retry_selected_button", "Retry Selected"))
        self.export_button.setText(self._tr("error_files_export_urls_button", "Export URLs to .txt"))
        self.ok_button.setText(self._tr("ok_button", "OK"))

    def _apply_theme(self):
        """Applies the current theme from the parent application."""
        if self.parent_app and self.parent_app.current_theme == "dark":
            # Get the scale factor from the parent app
            scale = getattr(self.parent_app, 'scale_factor', 1)
            # Call the imported function with the correct scale
            self.setStyleSheet(get_dark_theme(scale))
        else:
            # Explicitly set a blank stylesheet for light mode
            self.setStyleSheet("")

    def _select_all_items(self):
        """Checks all items in the list."""
        if hasattr(self, 'files_list_widget'):
            for i in range(self.files_list_widget.count()):
                self.files_list_widget.item(i).setCheckState(Qt.Checked)

    def _handle_retry_selected(self):
        """Gathers selected files and emits the retry signal."""
        if not hasattr(self, 'files_list_widget'):
            return

        selected_files_for_retry = [
            self.files_list_widget.item(i).data(Qt.UserRole)
            for i in range(self.files_list_widget.count())
            if self.files_list_widget.item(i).checkState() == Qt.Checked
        ]

        if selected_files_for_retry:
            self.retry_selected_signal.emit(selected_files_for_retry)
            self.accept()
        else:
            QMessageBox.information(
                self,
                self._tr("fav_artists_no_selection_title", "No Selection"),
                self._tr("error_files_no_selection_retry_message", "Please select at least one file to retry.")
            )

    def _handle_export_errors_to_txt(self):
        """Exports the URLs of failed files to a text file."""
        if not self.error_files:
            QMessageBox.information(
                self,
                self._tr("error_files_no_errors_export_title", "No Errors"),
                self._tr("error_files_no_errors_export_message", "There are no error file URLs to export.")
            )
            return

        options_dialog = ExportOptionsDialog(parent_app=self.parent_app, parent=self)
        if not options_dialog.exec_() == QDialog.Accepted:
            return

        export_option = options_dialog.get_selected_option()

        lines_to_export = []
        for error_item in self.error_files:
            file_info = error_item.get('file_info', {})
            url = file_info.get('url')

            if url:
                if export_option == ExportOptionsDialog.EXPORT_MODE_WITH_DETAILS:
                    original_filename = file_info.get('name', 'Unknown Filename')
                    post_title = error_item.get('post_title', 'Unknown Post')
                    post_id = error_item.get('original_post_id_for_log', 'N/A')
                    details_string = f" [Post: '{post_title}' (ID: {post_id}), File: '{original_filename}']"
                    lines_to_export.append(f"{url}{details_string}")
                else:
                    lines_to_export.append(url)

        if not lines_to_export:
            QMessageBox.information(
                self,
                self._tr("error_files_no_urls_found_export_title", "No URLs Found"),
                self._tr("error_files_no_urls_found_export_message", "Could not extract any URLs...")
            )
            return

        default_filename = "error_file_links.txt"
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            self._tr("error_files_save_dialog_title", "Save Error File URLs"),
            default_filename,
            "Text Files (*.txt);;All Files (*)"
        )

        if filepath:
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    for line in lines_to_export:
                        f.write(f"{line}\n")
                QMessageBox.information(
                    self,
                    self._tr("error_files_export_success_title", "Export Successful"),
                    self._tr("error_files_export_success_message", "Successfully exported...").format(
                        count=len(lines_to_export), filepath=filepath
                    )
                )
            except Exception as e:
                QMessageBox.critical(
                    self,
                    self._tr("error_files_export_error_title", "Export Error"),
                    self._tr("error_files_export_error_message", "Could not export...").format(error=str(e))
                )