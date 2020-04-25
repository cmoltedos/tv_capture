import sys, os
import platform
import datetime, time
import PyQt5.QtWidgets as QtWidgets
import PyQt5.QtCore as QtCore
import PyQt5.QtGui as QtGui
from fbs_runtime.application_context.PyQt5 import ApplicationContext
from pdb import set_trace

import stream_capture as streamer

class DownloadStreamProgress(QtCore.QThread):
    percentChanged = QtCore.pyqtSignal(int)

    def __init__(self, stream=None):
        super(DownloadStreamProgress, self).__init__()
        self.stream = stream

    def set_stream(self, stream):
        self.stream = stream

    def run(self):
        self._isRunning = True
        for percent in self.stream:
            if not self._isRunning:
                break
            self.percentChanged.emit(percent)

    def stop(self):
        self._isRunning = False

    def waiting_function(self, minutes):
        seconds = 0
        sleep_seconds = 10
        yield 0
        while seconds/60 < minutes:
            time.sleep(sleep_seconds)
            seconds += sleep_seconds
            percentage = int(seconds/(minutes*60)*100)
            yield percentage
        yield 100


class GenericStreamWidget(QtWidgets.QVBoxLayout):
    def __init__(self, folder, status_bar):
        super(GenericStreamWidget, self).__init__()
        self.stream = None
        self.quality = None
        self.seconds = 1
        self.working_folder = folder
        self.status_bar = status_bar

    def create_layout(self):
        group = QtWidgets.QGroupBox()
        layout = QtWidgets.QFormLayout()
        quality_label = QtWidgets.QLabel('Video quality:')
        self.quality = QtWidgets.QComboBox()
        layout.addRow(quality_label, self.quality)
        group.setLayout(layout)
        self.addWidget(group)

        self.create_download_common_layout('Start button', 'Stop button')

        return "Generic Class"

    def create_download_common_layout(self, start_name, stop_name):
        grid = QtWidgets.QGridLayout()
        self.start_download_button = QtWidgets.QPushButton(start_name)
        self.start_download_button.setEnabled(False)
        self.start_download_button.clicked.connect(
            self.start_stream_download)
        grid.addWidget(self.start_download_button, 1, 1)
        self.stop_download_button = QtWidgets.QPushButton(stop_name)
        self.stop_download_button.setEnabled(False)
        self.stop_download_button.clicked.connect(
            self.finish_stream_download)
        grid.addWidget(self.stop_download_button, 1, 2)
        self.addLayout(grid)

        self.schedule_pbar = QtWidgets.QProgressBar()
        self.schedule_pbar.setGeometry(30, 40, 200, 30)
        palette = QtGui.QPalette()
        palette.setColor(QtGui.QPalette.Highlight,
                         QtGui.QColor(QtCore.Qt.green))
        self.schedule_pbar.setPalette(palette)
        self.schedule_pbar.hide()
        self.addWidget(self.schedule_pbar)

        self.pbar = QtWidgets.QProgressBar()
        self.pbar.setGeometry(30, 40, 200, 30)
        self.pbar.hide()
        self.addWidget(self.pbar)

        self.record_seconds = QtWidgets.QLabel('00:00')
        self.record_seconds.setAlignment(QtCore.Qt.AlignCenter)
        self.record_seconds.setFont(QtGui.QFont("Courier", 35, QtGui.QFont.Bold))
        self.record_seconds.hide()
        self.addWidget(self.record_seconds)
        return None

    def schedule_process(self):
        self.status_bar.showMessage('Downloading ...')
        self.pbar.show()
        return False

    def start_stream_download(self):
        self.start_download_button.setEnabled(False)
        self.stop_download_button.setEnabled(True)
        if not self.schedule_process():
            self.start_download()

    def start_download(self):
        progress = self.stream.store_n_seconds(
            seconds=self.seconds, resolution=self.quality.currentText(),
            folder=self.working_folder.text()
        )
        self.progress = DownloadStreamProgress(progress)
        self.progress.percentChanged.connect(self.onpercentChanged)
        self.progress.start()

    def finish_stream_download(self):
        self.progress.stop()
        self.start_download_button.setEnabled(True)
        self.stop_download_button.setEnabled(False)
        self.pbar.setValue(0)
        self.record_seconds.hide()
        self.status_bar.showMessage('Finish')

    def onpercentChanged(self, value):
        if self.seconds == float('inf'):
            mintutes = int(value/60)
            seconds = int(value%60)
            self.record_seconds.setText('%.2d:%.2d' % (mintutes, seconds))
        elif value >= 100:
            self.pbar.setValue(100)
            self.finish_stream_download()
        else:
            self.pbar.setValue(value)

    def onpercentChanged_schedule(self, value):
        if value >= 100:
            self.schedule_pbar.setValue(100)
            self.progress_waiting.stop()
            self.schedule_pbar.setValue(0)
            self.schedule_pbar.hide()
            self.status_bar.showMessage(f'Recording {int(self.seconds/60)} minutes...')
            self.start_download()
        else:
            self.schedule_pbar.setValue(value)

    def start_waiting_time(self, minutes):
        self.progress_waiting = DownloadStreamProgress()
        self.progress_waiting.set_stream(self.progress_waiting.waiting_function(minutes))
        self.progress_waiting.percentChanged.connect(self.onpercentChanged_schedule)
        self.status_bar.showMessage(f'Waiting {minutes} minutes to start ...')
        self.schedule_pbar.show()
        self.pbar.show()
        self.progress_waiting.start()


class ProgramStreamWidget(GenericStreamWidget):

    def create_layout(self):
        group = QtWidgets.QGroupBox("Chapter to download URL:")
        layout = QtWidgets.QFormLayout()
        self.program_url = QtWidgets.QTextEdit()
        self.program_url.textChanged.connect(self.get_available_qualities)
        layout.addRow(self.program_url)
        quality_label = QtWidgets.QLabel('Video quality:')
        self.quality = QtWidgets.QComboBox()
        layout.addRow(quality_label, self.quality)
        group.setLayout(layout)
        self.addWidget(group)

        self.create_download_common_layout('Start Download', 'Stop Download')

        return "Program Downloader"

    def get_available_qualities(self):
        link = self.program_url.toPlainText()
        try:
            self.stream = streamer.Stream(link=link)
        except IOError:
            self.start_download_button.setEnabled(False)
            return None
        qualities = self.stream.get_available_resolution()
        self.quality.clear()
        self.quality.addItems(qualities)
        self.start_download_button.setEnabled(True)


class LiveStreamWidget(GenericStreamWidget):

    def create_layout(self):
        group = QtWidgets.QGroupBox("Channel to record:")
        options_layout = QtWidgets.QHBoxLayout()
        option1 = QtWidgets.QRadioButton("13")
        option1.toggled.connect(lambda:self.get_available_qualities(option1))
        options_layout.addWidget(option1)
        option2 = QtWidgets.QRadioButton("Mega")
        option2.toggled.connect(lambda:self.get_available_qualities(option2))
        options_layout.addWidget(option2)
        option3 = QtWidgets.QRadioButton("CHV")
        option3.toggled.connect(lambda:self.get_available_qualities(option3))
        options_layout.addWidget(option3)
        option4 = QtWidgets.QRadioButton("TVN")
        option4.toggled.connect(lambda:self.get_available_qualities(option4))
        options_layout.addWidget(option4)

        quality_layout = QtWidgets.QHBoxLayout()
        quality_label = QtWidgets.QLabel('Video quality:')
        self.quality = QtWidgets.QComboBox()
        quality_layout.addWidget(quality_label)
        quality_layout.addWidget(self.quality)
        quality_layout.addStretch(1)

        schedule_box_layout = QtWidgets.QHBoxLayout()
        self.schedule_box = QtWidgets.QCheckBox("Schedule recording time")
        schedule_box_layout.addWidget(self.schedule_box)

        schedule_period_layout = QtWidgets.QHBoxLayout()
        hour_init = QtWidgets.QSpinBox()
        hour_init.setRange(0,23)
        minute_init = QtWidgets.QSpinBox()
        minute_init.setRange(0,59)
        hour_end = QtWidgets.QSpinBox()
        hour_end.setRange(0,23)
        minute_end = QtWidgets.QSpinBox()
        minute_end.setRange(0,59)
        self.time_boxes = [hour_init, minute_init, hour_end, minute_end]
        self.schedule_box.toggled.connect(self.schedule_box_option_state)
        self.schedule_box_option_state()

        schedule_period_layout.addWidget(QtWidgets.QLabel('from'))
        schedule_period_layout.addWidget(hour_init)
        schedule_period_layout.addWidget(QtWidgets.QLabel(':'))
        schedule_period_layout.addWidget(minute_init)
        schedule_period_layout.addStretch(1)
        schedule_period_layout.addWidget(QtWidgets.QLabel('to'))
        schedule_period_layout.addStretch(1)
        schedule_period_layout.addWidget(hour_end)
        schedule_period_layout.addWidget(QtWidgets.QLabel(':'))
        schedule_period_layout.addWidget(minute_end)

        layout = QtWidgets.QVBoxLayout()
        layout.addLayout(options_layout)
        layout.addLayout(quality_layout)
        layout.addLayout(schedule_box_layout)
        layout.addLayout(schedule_period_layout)
        group.setLayout(layout)
        self.addWidget(group)

        self.create_download_common_layout('Start Recording', 'Stop Recording')

        return "Live TV Recorder"

    def schedule_box_option_state(self):
        if self.schedule_box.isChecked():
            for element in self.time_boxes:
                element.setEnabled(True)
        else:
            for element in self.time_boxes:
                element.setEnabled(False)

    def schedule_process(self):
        if self.schedule_box.isChecked():
            actual_datetime = datetime.datetime.now()
            hour_to_minutes = lambda h, m: h*60 + m
            actual_time_in_minutes = hour_to_minutes(
                actual_datetime.hour, actual_datetime.minute)
            init_time_in_minutes = hour_to_minutes(
                int(self.time_boxes[0].value()),
                int(self.time_boxes[1].value())
            )
            end_time_in_minutes = hour_to_minutes(
                int(self.time_boxes[2].value()),
                int(self.time_boxes[3].value())
            )
            if init_time_in_minutes < actual_time_in_minutes:
                init_time_in_minutes = actual_time_in_minutes
            if init_time_in_minutes > end_time_in_minutes:
                end_time_in_minutes += 24*60
            self.seconds = (end_time_in_minutes - init_time_in_minutes)*60
            waiting_minutes = init_time_in_minutes - actual_time_in_minutes
            self.start_waiting_time(waiting_minutes)
            return True
        self.status_bar.showMessage('Recording ...')
        self.seconds = float('inf')
        self.record_seconds.show()
        return False

    def get_available_qualities(self, radio_button):
        if radio_button.isChecked():
            channel = radio_button.text().lower()
        else:
            channel = ''
        try:
            self.stream = streamer.Stream(channel=channel)
        except IOError:
            self.start_download_button.setEnabled(False)
            return None
        qualities = self.stream.get_available_resolution()
        self.quality.clear()
        self.quality.addItems(qualities)
        self.start_download_button.setEnabled(True)



class MyTableWidget(QtWidgets.QWidget):

    def __init__(self, parent, status_bar):
        super(MyTableWidget, self).__init__(parent)
        self.layout = QtWidgets.QVBoxLayout()

        # Common working folder
        group = QtWidgets.QGroupBox("Working folder:")
        folder_layout = QtWidgets.QFormLayout()
        self.set_folder_edit()
        folder_selector = self.set_folder_button()
        folder_layout.addRow(self.working_folder, folder_selector)
        group.setLayout(folder_layout)
        self.layout.addWidget(group)

        # Initialize tab screen
        self.tabs = QtWidgets.QTabWidget()
        self.tab1 = QtWidgets.QWidget()
        self.tab2 = QtWidgets.QWidget()
        self.tabs.resize(300, 200)

        # Create tabs
        program_element = ProgramStreamWidget(self.working_folder, status_bar)
        tab_name1 = program_element.create_layout()
        self.tab1.setLayout(program_element)

        live_element = LiveStreamWidget(self.working_folder, status_bar)
        tab_name2 = live_element.create_layout()
        self.tab2.setLayout(live_element)

        self.tabs.addTab(self.tab1, tab_name1)
        self.tabs.addTab(self.tab2, tab_name2)

        # Add tabs to widget
        self.layout.addWidget(self.tabs)
        self.setLayout(self.layout)

    def set_folder_button(self):
        toolButtonOpenDialog = QtWidgets.QToolButton(self)
        toolButtonOpenDialog.setGeometry(QtCore.QRect(210, 10, 25, 19))
        toolButtonOpenDialog.setObjectName("FolderSelector")
        toolButtonOpenDialog.setText("...")
        toolButtonOpenDialog.clicked.connect(self._open_folder_dialog)
        return toolButtonOpenDialog

    def set_folder_edit(self):
        self.working_folder = QtWidgets.QLineEdit()
        self.working_folder.setEnabled(False)
        self.working_folder.setGeometry(QtCore.QRect(10, 10, 191, 20))
        self.working_folder.setObjectName("FolderName")
        self.working_folder.setFixedWidth(400)
        if os.path.exists('working_folder.txt'):
            with open('working_folder.txt') as folder_file:
                folder = folder_file.read()
        else:
            folder = os.getcwd()
        self.working_folder.setText(folder)
        return None

    def _open_folder_dialog(self):
        directory = str(QtWidgets.QFileDialog.getExistingDirectory())
        with open('working_folder.txt', 'w') as folder_file:
            folder_file.write(directory)
        self.working_folder.setText('{}'.format(directory))


class App(ApplicationContext):

    def run(self):
        window = QtWidgets.QMainWindow()
        self.title = 'TV Consumer'
        width, height = 500, 200
        self.select_app_style(self)
        window.setWindowTitle(self.title)
        logo_route = self.get_resource('logo.png')
        self.app.setWindowIcon(QtGui.QIcon(logo_route))
        window.resize(width, height)
        self.center(window)
        status_bar = window.statusBar()

        menu = window.menuBar()
        about = menu.addMenu("About")
        about.addAction("Info")
        about.triggered[QtWidgets.QAction].connect(self.processtrigger)

        self.table_widget = MyTableWidget(window, status_bar)
        window.setCentralWidget(self.table_widget)

        window.show()
        return self.app.exec_()

    def processtrigger(self, q):
        msg = QtWidgets.QMessageBox()
        msg.setIcon(QtWidgets.QMessageBox.Information)

        msg.setText("Created by")
        msg.setInformativeText("César Moltedo\ncesar.moltedo@gmail.com\n24th of April 2020")
        about_location = self.get_resource('about.txt')
        if os.path.exists(about_location):
            with open(about_location) as about_file:
                about_detail = about_file.read()
            msg.setWindowTitle("About information")
            msg.setDetailedText(about_detail)
        msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
        msg.exec_()

    def select_app_style(self, app):
        if platform.system() == 'Windows':
            app.app.setStyle('WindowsVista')
        elif platform.system() == 'Darwin':
            app.app.setStyle('Macintosh')
        else:
            app.app.setStyle('Fusion')
        return None

    def center(self, window):
        # geometry of the main window
        qr = window.frameGeometry()
        # center point of screen
        cp = QtWidgets.QDesktopWidget().availableGeometry().center()
        # move rectangle's center point to screen's center point
        qr.moveCenter(cp)
        # top left of rectangle becomes top left of window centering it
        window.move(qr.topLeft())

if __name__ == '__main__':
    appctxt = App()  # 4. Instantiate the subclass
    exit_code = appctxt.run()  # 5. Invoke run()
    sys.exit(exit_code)