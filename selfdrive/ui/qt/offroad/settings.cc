#include "selfdrive/ui/qt/offroad/settings.h"

#include <cassert>
#include <cmath>
#include <string>

#include <QDebug>

#ifndef QCOM
#include "selfdrive/ui/qt/offroad/networking.h"
#endif

#ifdef ENABLE_MAPS
#include "selfdrive/ui/qt/maps/map_settings.h"
#endif

#include "selfdrive/common/params.h"
#include "selfdrive/common/util.h"
#include "selfdrive/hardware/hw.h"
#include "selfdrive/ui/qt/widgets/controls.h"
#include "selfdrive/ui/qt/widgets/input.h"
#include "selfdrive/ui/qt/widgets/scrollview.h"
#include "selfdrive/ui/qt/widgets/ssh_keys.h"
#include "selfdrive/ui/qt/widgets/toggle.h"
#include "selfdrive/ui/ui.h"
#include "selfdrive/ui/qt/util.h"
#include "selfdrive/ui/qt/qt_window.h"

#include <QComboBox>
#include <QAbstractItemView>
#include <QScroller>
#include <QListView>
#include <QListWidget>

TogglesPanel::TogglesPanel(SettingsWindow *parent) : ListWidget(parent) {
  // param, title, desc, icon
  std::vector<std::tuple<QString, QString, QString, QString>> toggles{
    {
      "OpenpilotEnabledToggle",
      //"Enable openpilot",
      //"Use the openpilot system for adaptive cruise control and lane keep driver assistance. Your attention is required at all times to use this feature. Changing this setting takes effect when the car is powered off.",
      "오픈파일럿 사용",
      "오픈파일럿을 사용하여 조향 보조 기능을 사용합니다. 항상 핸들을 잡고 도로를 주시하세요.",
      "../assets/offroad/icon_openpilot.png",
    },
    {
      "IsLdwEnabled",
      //"Enable Lane Departure Warnings",
      //"Receive alerts to steer back into the lane when your vehicle drifts over a detected lane line without a turn signal activated while driving over 31 mph (50 km/h).",
      "차선 이탈 경고 사용",
      "50km/h 이상 운전하는 동안 방향 지시등을 켜지 않은 상태에서 차선을 넘어갈 때 조향하라는 알림을 받습니다.",
      "../assets/offroad/icon_warning.png",
    },
    {
      "IsRHD",
      //"Enable Right-Hand Drive",
      //"Allow openpilot to obey left-hand traffic conventions and perform driver monitoring on right driver seat.",
      "오른쪽 운전자",
	  "운전석이 오른쪽에 있는 운전자 모니터링을 수행합니다.",
      "../assets/offroad/icon_openpilot_mirrored.png",
    },
    {
      "IsMetric",
      //"Use Metric System",
      //"Display speed in km/h instead of mph.",
      "미터법 사용",
      "주행속도 단위를 ㎞/h로 변경합니다",
      "../assets/offroad/icon_metric.png",
    },
    {
      "RecordFront",
      //"Record and Upload Driver Camera",
      //"Upload data from the driver facing camera and help improve the driver monitoring algorithm.",
	  "드라이버 및 주행화면 녹화 업로드",
	  "오픈파일럿을 사용하는 동안 주행 데이터를 업로드합니다.",
      "../assets/offroad/icon_monitoring.png",
    },
    {
      "EndToEndToggle",
      //"\U0001f96c Disable use of lanelines (Alpha) \U0001f96c",
      //"In this mode openpilot will ignore lanelines and just drive how it thinks a human would.",
	  "차선 인식 모델을 사용하지 않음(알파버전)",
	  "차선 인식 모델을 사용하지 않고, 운전자가 조작하는 것처럼 주행합니다.",
      "../assets/offroad/icon_road.png",
    },
    {
      "DisengageOnAccelerator",
      //"Disengage On Accelerator Pedal",
      //"When enabled, pressing the accelerator pedal will disengage openpilot.",
      "가속 페달 조작 시 오픈파일럿 해제",
      "활성화하면 경우 가속 페달을 누르면 오픈파일럿이 해제됩니다.",
      "../assets/offroad/icon_disengage_on_accelerator.svg",
    },
#ifdef ENABLE_MAPS
    {
      "NavSettingTime24h",
      "Show ETA in 24h format",
      "Use 24h format instead of am/pm",
      "../assets/offroad/icon_metric.png",
    },
#endif

  };

  Params params;

  if (params.getBool("DisableRadar_Allow")) {
    toggles.push_back({
      "DisableRadar",
      "openpilot Longitudinal Control",
      "openpilot will disable the car's radar and will take over control of gas and brakes. Warning: this disables AEB!",
      "../assets/offroad/icon_speed_limit.png",
    });
  }

  for (auto &[param, title, desc, icon] : toggles) {
    auto toggle = new ParamControl(param, title, desc, icon, this);
    bool locked = params.getBool((param + "Lock").toStdString());
    toggle->setEnabled(!locked);
    //if (!locked) {
    //  connect(uiState(), &UIState::offroadTransition, toggle, &ParamControl::setEnabled);
    //}
    addItem(toggle);
  }
}

DevicePanel::DevicePanel(SettingsWindow *parent) : ListWidget(parent) {
  setSpacing(50);
  addItem(new LabelControl("동글ID", getDongleId().value_or("N/A")));
  addItem(new LabelControl("일련번호", params.get("HardwareSerial").c_str()));

  QHBoxLayout *reset_layout = new QHBoxLayout();
  reset_layout->setSpacing(30);

  // reset calibration button
  QPushButton *restart_openpilot_btn = new QPushButton("프로세서 재시작");
  restart_openpilot_btn->setStyleSheet("height: 120px;border-radius: 15px;background-color: #393939;");
  reset_layout->addWidget(restart_openpilot_btn);
  QObject::connect(restart_openpilot_btn, &QPushButton::released, [=]() {
    emit closeSettings();
    QTimer::singleShot(1000, []() {
      Params().putBool("SoftRestartTriggered", true);
    });
  });

  // reset calibration button
  QPushButton *reset_calib_btn = new QPushButton("캘리브레이션 초기화");
  reset_calib_btn->setStyleSheet("height: 120px;border-radius: 15px;background-color: #393939;");
  reset_layout->addWidget(reset_calib_btn);
  QObject::connect(reset_calib_btn, &QPushButton::released, [=]() {
    if (ConfirmationDialog::confirm("캘리브레이션을 초기화하시겠습니까?", this)) {
      Params().remove("CalibrationParams");
      Params().remove("LiveParameters");
      emit closeSettings();
      QTimer::singleShot(1000, []() {
        Params().putBool("SoftRestartTriggered", true);
      });
    }
  });

  addItem(reset_layout);

  // offroad-only buttons

  //auto dcamBtn = new ButtonControl("Driver Camera", "PREVIEW",
  //                                 "Preview the driver facing camera to help optimize device mounting position for best driver monitoring experience. (vehicle must be off)");
  auto dcamBtn = new ButtonControl("운전자 카메라", "미리보기",
                                   "운전자 모니터링 카메라를 미리 보고 최적의 장착 위치를 찾아보세요.");
  connect(dcamBtn, &ButtonControl::clicked, [=]() { emit showDriverView(); });
  addItem(dcamBtn);

  //auto resetCalibBtn = new ButtonControl("Reset Calibration", "RESET", " ");
  auto resetCalibBtn = new ButtonControl("캘리브레이션 초기화", "시작", " ");
  connect(resetCalibBtn, &ButtonControl::showDescription, this, &DevicePanel::updateCalibDescription);
  connect(resetCalibBtn, &ButtonControl::clicked, [&]() {
    //if (ConfirmationDialog::confirm("Are you sure you want to reset calibration?", this)) {
    if (ConfirmationDialog::confirm("캘리브레이션을 초기화하시겠습니까?", this)) {
      params.remove("CalibrationParams");
    }
  });
  addItem(resetCalibBtn);

  if (!params.getBool("Passive")) {
    //auto retrainingBtn = new ButtonControl("Review Training Guide", "REVIEW", "Review the rules, features, and limitations of openpilot");
    auto retrainingBtn = new ButtonControl("트레이닝 가이드", "보기", "오픈파일럿의 규칙, 기능 및 제한 사항을 확인할 수 있습니다.");
    connect(retrainingBtn, &ButtonControl::clicked, [=]() {
      //if (ConfirmationDialog::confirm("Are you sure you want to review the training guide?", this)) {
      if (ConfirmationDialog::confirm("트레이닝 가이드를 확인하시겠습니까?", this)) {
        emit reviewTrainingGuide();
      }
    });
    addItem(retrainingBtn);
  }

  if (Hardware::TICI()) {
    //auto regulatoryBtn = new ButtonControl("Regulatory", "VIEW", "");
    auto regulatoryBtn = new ButtonControl("규제", "보기", "");
    connect(regulatoryBtn, &ButtonControl::clicked, [=]() {
      const std::string txt = util::read_file("../assets/offroad/fcc.html");
      RichTextDialog::alert(QString::fromStdString(txt), this);
    });
    addItem(regulatoryBtn);
  }

  /*QObject::connect(uiState(), &UIState::offroadTransition, [=](bool offroad) {
    for (auto btn : findChildren<ButtonControl *>()) {
      btn->setEnabled(offroad);
    }
  });*/

  // power buttons
  QHBoxLayout *power_layout = new QHBoxLayout();
  power_layout->setSpacing(30);

  //QPushButton *reboot_btn = new QPushButton("Reboot");
  QPushButton *reboot_btn = new QPushButton("재부팅");
  reboot_btn->setObjectName("reboot_btn");
  power_layout->addWidget(reboot_btn);
  QObject::connect(reboot_btn, &QPushButton::clicked, this, &DevicePanel::reboot);

  //QPushButton *rebuild_btn = new QPushButton("Rebuild");
  QPushButton *rebuild_btn = new QPushButton("전체 재빌드");
  rebuild_btn->setObjectName("rebuild_btn");
  power_layout->addWidget(rebuild_btn);
  QObject::connect(rebuild_btn, &QPushButton::clicked, [=]() {

    //if (ConfirmationDialog::confirm("Are you sure you want to rebuild?", this)) {
    if (ConfirmationDialog::confirm("전체 재빌드를 실행하시겠습니까?", this)) {
      std::system("cd /data/openpilot && scons -c");
      std::system("rm /data/openpilot/.sconsign.dblite");
      std::system("rm /data/openpilot/prebuilt");
      std::system("rm -rf /tmp/scons_cache");
      if (Hardware::TICI())
        std::system("sudo reboot");
      else
        std::system("reboot");
    }
  });

  //QPushButton *poweroff_btn = new QPushButton("Power Off");
  QPushButton *poweroff_btn = new QPushButton("시스템 종료");
  poweroff_btn->setObjectName("poweroff_btn");
  power_layout->addWidget(poweroff_btn);
  QObject::connect(poweroff_btn, &QPushButton::clicked, this, &DevicePanel::poweroff);

  if (Hardware::TICI()) {
    connect(uiState(), &UIState::offroadTransition, poweroff_btn, &QPushButton::setVisible);
  }

  setStyleSheet(R"(
    #reboot_btn { height: 120px; border-radius: 15px; background-color: #393939; }
    #reboot_btn:pressed { background-color: #4a4a4a; }
    #rebuild_btn { height: 120px; border-radius: 15px; background-color: #393939; }
    #rebuild_btn:pressed { background-color: #4a4a4a; }
    #poweroff_btn { height: 120px; border-radius: 15px; background-color: #E22C2C; }
    #poweroff_btn:pressed { background-color: #FF2424; }
  )");
  addItem(power_layout);
}

void DevicePanel::updateCalibDescription() {
  QString desc =
      //"openpilot requires the device to be mounted within 4° left or right and "
      //"within 5° up or 8° down. openpilot is continuously calibrating, resetting is rarely required.";
      "오픈파일럿 장치가 왼쪽 또는 오른쪽으로 4° 이내에 장착되어야 하며,"
      "위로 5°, 아래로 8° 장착되어야 합니다. 오픈파일럿이 지속적으로 보정하므로 정확히 장착할 필요 없습니다.";
  std::string calib_bytes = Params().get("CalibrationParams");
  if (!calib_bytes.empty()) {
    try {
      AlignedBuffer aligned_buf;
      capnp::FlatArrayMessageReader cmsg(aligned_buf.align(calib_bytes.data(), calib_bytes.size()));
      auto calib = cmsg.getRoot<cereal::Event>().getLiveCalibration();
      if (calib.getCalStatus() != 0) {
        double pitch = calib.getRpyCalib()[1] * (180 / M_PI);
        double yaw = calib.getRpyCalib()[2] * (180 / M_PI);
        //desc += QString(" Your device is pointed %1° %2 and %3° %4.")
                    //.arg(QString::number(std::abs(pitch), 'g', 1), pitch > 0 ? "down" : "up",
                         //QString::number(std::abs(yaw), 'g', 1), yaw > 0 ? "left" : "right");
        desc += QString(" 장치의 위치가 [%1° %2 그리고 %3° %4] 입니다.")
                    .arg(QString::number(std::abs(pitch), 'g', 1), pitch > 0 ? "아래로" : "위로",
                         QString::number(std::abs(yaw), 'g', 1), yaw > 0 ? "왼쪽으로" : "오른쪽으로");
      }
    } catch (kj::Exception) {
      //qInfo() << "invalid CalibrationParams";
      qInfo() << "캘리브레이션이 잘못되었습니다. 다시 실행해 주세요.";
    }
  }
  qobject_cast<ButtonControl *>(sender())->setDescription(desc);
}

void DevicePanel::reboot() {
  if (!uiState()->engaged()) {
    //if (ConfirmationDialog::confirm("Are you sure you want to reboot?", this)) {
    if (ConfirmationDialog::confirm("시스템을 재부팅 하시겠습니까?", this)) {
      // Check engaged again in case it changed while the dialog was open
      if (!uiState()->engaged()) {
        Params().putBool("DoReboot", true);
      }
    }
  } else {
    ConfirmationDialog::alert("Disengage to Reboot", this);
  }
}

void DevicePanel::poweroff() {
  if (!uiState()->engaged()) {
    //if (ConfirmationDialog::confirm("Are you sure you want to power off?", this)) {
    if (ConfirmationDialog::confirm("시스템을 종료하시겠습니까?", this)) {
      // Check engaged again in case it changed while the dialog was open
      if (!uiState()->engaged()) {
        Params().putBool("DoShutdown", true);
      }
    }
  } else {
    ConfirmationDialog::alert("Disengage to Power Off", this);
  }
}

SoftwarePanel::SoftwarePanel(QWidget* parent) : ListWidget(parent) {
  gitBranchLbl = new LabelControl("브랜치 이름");
  gitCommitLbl = new LabelControl("브랜치 커밋");
  osVersionLbl = new LabelControl("운영체제 버전");
  versionLbl = new LabelControl("Version", "", QString::fromStdString(params.get("ReleaseNotes")).trimmed());
  lastUpdateLbl = new LabelControl("마지막 업데이트", "", "오픈파일럿 업데이트를 성공적으로 확인했습니다. 업데이트는 차량 시동이 꺼져 있는 동안만 실행됩니다.");
  updateBtn = new ButtonControl("최신 업데이트", "");
  connect(updateBtn, &ButtonControl::clicked, [=]() {
    if (params.getBool("IsOffroad")) {
      fs_watch->addPath(QString::fromStdString(params.getParamPath("LastUpdateTime")));
      fs_watch->addPath(QString::fromStdString(params.getParamPath("UpdateFailedCount")));
      updateBtn->setText("확인하기");
      updateBtn->setEnabled(false);
    }
    std::system("pkill -1 -f selfdrive.updated");
  });


  auto uninstallBtn = new ButtonControl(getBrand() + "삭제", "삭제하기");
  connect(uninstallBtn, &ButtonControl::clicked, [&]() {
    if (ConfirmationDialog::confirm("오픈파일럿을 삭제하시겠습니까?", this)) {
      params.putBool("DoUninstall", true);
    }
  });
  connect(uiState(), &UIState::offroadTransition, uninstallBtn, &QPushButton::setEnabled);

  QWidget *widgets[] = {versionLbl, lastUpdateLbl, updateBtn, gitBranchLbl, gitCommitLbl, osVersionLbl, uninstallBtn};
  for (QWidget* w : widgets) {
    addItem(w);
  }

  fs_watch = new QFileSystemWatcher(this);
  QObject::connect(fs_watch, &QFileSystemWatcher::fileChanged, [=](const QString path) {
    if (path.contains("UpdateFailedCount") && std::atoi(params.get("UpdateFailedCount").c_str()) > 0) {
      lastUpdateLbl->setText("failed to fetch update");
      updateBtn->setText("확인하기");
      updateBtn->setEnabled(true);
    } else if (path.contains("LastUpdateTime")) {
      updateLabels();
    }
  });
}

void SoftwarePanel::showEvent(QShowEvent *event) {
  updateLabels();
}

void SoftwarePanel::updateLabels() {
  QString lastUpdate = "";
  auto tm = params.get("LastUpdateTime");
  if (!tm.empty()) {
    lastUpdate = timeAgo(QDateTime::fromString(QString::fromStdString(tm + "Z"), Qt::ISODate));
  }

  versionLbl->setText(getBrandVersion());
  lastUpdateLbl->setText(lastUpdate);
  updateBtn->setText("확인하기");
  updateBtn->setEnabled(true);
  gitBranchLbl->setText(QString::fromStdString(params.get("GitBranch")));
  gitCommitLbl->setText(QString::fromStdString(params.get("GitCommit")).left(10));
  osVersionLbl->setText(QString::fromStdString(Hardware::get_os_version()).trimmed());
}

C2NetworkPanel::C2NetworkPanel(QWidget *parent) : QWidget(parent) {
  QVBoxLayout *layout = new QVBoxLayout(this);
  layout->setContentsMargins(50, 0, 50, 0);

  ListWidget *list = new ListWidget();
  list->setSpacing(30);
  // wifi + tethering buttons
#ifdef QCOM
  auto wifiBtn = new ButtonControl("와이파이 설정", "열기");
  QObject::connect(wifiBtn, &ButtonControl::clicked, [=]() { HardwareEon::launch_wifi(); });
  list->addItem(wifiBtn);

  auto tetheringBtn = new ButtonControl("테더링 설정", "열기");
  QObject::connect(tetheringBtn, &ButtonControl::clicked, [=]() { HardwareEon::launch_tethering(); });
  list->addItem(tetheringBtn);
#endif
  ipaddress = new LabelControl("IP 주소", "");
  list->addItem(ipaddress);

  // SSH key management
  list->addItem(new SshToggle());
  list->addItem(new SshControl());
  layout->addWidget(list);
  layout->addStretch(1);
}

void C2NetworkPanel::showEvent(QShowEvent *event) {
  ipaddress->setText(getIPAddress());
}

QString C2NetworkPanel::getIPAddress() {
  std::string result = util::check_output("ifconfig wlan0");
  if (result.empty()) return "";

  const std::string inetaddrr = "inet addr:";
  std::string::size_type begin = result.find(inetaddrr);
  if (begin == std::string::npos) return "";

  begin += inetaddrr.length();
  std::string::size_type end = result.find(' ', begin);
  if (end == std::string::npos) return "";

  return result.substr(begin, end - begin).c_str();
}

QWidget *network_panel(QWidget *parent) {
#ifdef QCOM
  return new C2NetworkPanel(parent);
#else
  return new Networking(parent);
#endif
}

static QStringList get_list(const char* path)
{
  QStringList stringList;
  QFile textFile(path);
  if(textFile.open(QIODevice::ReadOnly))
  {
      QTextStream textStream(&textFile);
      while (true)
      {
        QString line = textStream.readLine();
        if (line.isNull())
            break;
        else
            stringList.append(line);
      }
  }

  return stringList;
}

void SettingsWindow::showEvent(QShowEvent *event) {
  panel_widget->setCurrentIndex(0);
  nav_btns->buttons()[0]->setChecked(true);
}

SettingsWindow::SettingsWindow(QWidget *parent) : QFrame(parent) {

  // setup two main layouts
  sidebar_widget = new QWidget;
  QVBoxLayout *sidebar_layout = new QVBoxLayout(sidebar_widget);
  sidebar_layout->setMargin(0);
  panel_widget = new QStackedWidget();
  panel_widget->setStyleSheet(R"(
    border-radius: 30px;
    background-color: #292929;
  )");

  // close button
  QPushButton *close_btn = new QPushButton("← 뒤로");
  close_btn->setStyleSheet(R"(
    QPushButton {
      font-size: 50px;
      font-weight: bold;
      margin: 0px;
      padding: 15px;
      border-width: 0;
      border-radius: 30px;
      color: #dddddd;
      background-color: #444444;
    }
    QPushButton:pressed {
      background-color: #3B3B3B;
    }
  )");
  close_btn->setFixedSize(300, 110);
  sidebar_layout->addSpacing(10);
  sidebar_layout->addWidget(close_btn, 0, Qt::AlignRight);
  sidebar_layout->addSpacing(10);
  QObject::connect(close_btn, &QPushButton::clicked, this, &SettingsWindow::closeSettings);

  // setup panels
  DevicePanel *device = new DevicePanel(this);
  QObject::connect(device, &DevicePanel::reviewTrainingGuide, this, &SettingsWindow::reviewTrainingGuide);
  QObject::connect(device, &DevicePanel::showDriverView, this, &SettingsWindow::showDriverView);
  QObject::connect(device, &DevicePanel::closeSettings, this, &SettingsWindow::closeSettings);

  QList<QPair<QString, QWidget *>> panels = {
    //{"Device", device},
    //{"Network", network_panel(this)},
    //{"Toggles", new TogglesPanel(this)},
    //{"Software", new SoftwarePanel(this)},
    //{"Community", new CommunityPanel(this)},
    {"장치", device},
    {"네트워크", network_panel(this)},
    {"토글", new TogglesPanel(this)},
    {"정보", new SoftwarePanel(this)},
    {"커뮤니티", new CommunityPanel(this)},
  };

#ifdef ENABLE_MAPS
  auto map_panel = new MapPanel(this);
  panels.push_back({"네비게이션", map_panel});
  QObject::connect(map_panel, &MapPanel::closeSettings, this, &SettingsWindow::closeSettings);
#endif

  const int padding = panels.size() > 3 ? 25 : 35;

  nav_btns = new QButtonGroup(this);
  for (auto &[name, panel] : panels) {
    QPushButton *btn = new QPushButton(name);
    btn->setCheckable(true);
    btn->setChecked(nav_btns->buttons().size() == 0);
    btn->setStyleSheet(QString(R"(
      QPushButton {
        color: grey;
        border: none;
        background: none;
        font-size: 60px;
        font-weight: 500;
        padding-top: %1px;
        padding-bottom: %1px;
      }
      QPushButton:checked {
        color: white;
      }
      QPushButton:pressed {
        color: #ADADAD;
      }
    )").arg(padding));

    nav_btns->addButton(btn);
    sidebar_layout->addWidget(btn, 0, Qt::AlignRight);

    const int lr_margin = name != "네트워크" ? 50 : 0;  // Network panel handles its own margins
    panel->setContentsMargins(lr_margin, 25, lr_margin, 25);

    ScrollView *panel_frame = new ScrollView(panel, this);
    panel_widget->addWidget(panel_frame);

    QObject::connect(btn, &QPushButton::clicked, [=, w = panel_frame]() {
      btn->setChecked(true);
      panel_widget->setCurrentWidget(w);
    });
  }
  sidebar_layout->setContentsMargins(50, 50, 100, 50);

  // main settings layout, sidebar + main panel
  QHBoxLayout *main_layout = new QHBoxLayout(this);

  sidebar_widget->setFixedWidth(500);
  main_layout->addWidget(sidebar_widget);
  main_layout->addWidget(panel_widget);

  setStyleSheet(R"(
    * {
      color: white;
      font-size: 50px;
    }
    SettingsWindow {
      background-color: black;
    }
  )");
}

void SettingsWindow::hideEvent(QHideEvent *event) {
#ifdef QCOM
  HardwareEon::close_activities();
#endif
}


/////////////////////////////////////////////////////////////////////////

CommunityPanel::CommunityPanel(QWidget* parent) : QWidget(parent) {

  main_layout = new QStackedLayout(this);

  homeScreen = new QWidget(this);
  QVBoxLayout* vlayout = new QVBoxLayout(homeScreen);
  vlayout->setContentsMargins(0, 20, 0, 20);

  QString selected = QString::fromStdString(Params().get("차량 선택"));

  QPushButton* selectCarBtn = new QPushButton(selected.length() ? selected : "차량을 선택하세요");
  selectCarBtn->setObjectName("selectCarBtn");
  //selectCarBtn->setStyleSheet("margin-right: 30px;");
  //selectCarBtn->setFixedSize(350, 100);
  connect(selectCarBtn, &QPushButton::clicked, [=]() { main_layout->setCurrentWidget(selectCar); });

  homeWidget = new QWidget(this);
  QVBoxLayout* toggleLayout = new QVBoxLayout(homeWidget);
  homeWidget->setObjectName("homeWidget");

  ScrollView *scroller = new ScrollView(homeWidget, this);
  scroller->setVerticalScrollBarPolicy(Qt::ScrollBarAsNeeded);

  main_layout->addWidget(homeScreen);

  selectCar = new SelectCar(this);
  connect(selectCar, &SelectCar::backPress, [=]() { main_layout->setCurrentWidget(homeScreen); });
  connect(selectCar, &SelectCar::selectedCar, [=]() {

     QString selected = QString::fromStdString(Params().get("SelectedCar"));
     selectCarBtn->setText(selected.length() ? selected : "차량을 선택하세요");
     main_layout->setCurrentWidget(homeScreen);
  });
  main_layout->addWidget(selectCar);


  QString lateral_control = QString::fromStdString(Params().get("LateralControl"));
  if(lateral_control.length() == 0)
    lateral_control = "TORQUE";

  QPushButton* lateralControlBtn = new QPushButton(lateral_control);
  lateralControlBtn->setObjectName("lateralControlBtn");
  //lateralControlBtn->setStyleSheet("margin-right: 30px;");
  //lateralControlBtn->setFixedSize(350, 100);
  connect(lateralControlBtn, &QPushButton::clicked, [=]() { main_layout->setCurrentWidget(lateralControl); });


  lateralControl = new LateralControl(this);
  connect(lateralControl, &LateralControl::backPress, [=]() { main_layout->setCurrentWidget(homeScreen); });
  connect(lateralControl, &LateralControl::selected, [=]() {

     QString lateral_control = QString::fromStdString(Params().get("LateralControl"));
     if(lateral_control.length() == 0)
       lateral_control = "TORQUE";
     lateralControlBtn->setText(lateral_control);
     main_layout->setCurrentWidget(homeScreen);
  });
  main_layout->addWidget(lateralControl);

  QHBoxLayout* layoutBtn = new QHBoxLayout(homeWidget);

  layoutBtn->addWidget(lateralControlBtn);
  layoutBtn->addSpacing(10);
  layoutBtn->addWidget(selectCarBtn);

  vlayout->addSpacing(10);
  vlayout->addLayout(layoutBtn, 0);
  vlayout->addSpacing(10);
  vlayout->addWidget(scroller, 1);

  QPalette pal = palette();
  pal.setColor(QPalette::Background, QColor(0x29, 0x29, 0x29));
  setAutoFillBackground(true);
  setPalette(pal);

  setStyleSheet(R"(
    #back_btn, #selectCarBtn, #lateralControlBtn {
      font-size: 50px;
      margin: 0px;
      padding: 20px;
      border-width: 0;
      border-radius: 30px;
      color: #dddddd;
      background-color: #444444;
    }
  )");

  QList<ParamControl*> toggles;

  toggles.append(new ParamControl("UseClusterSpeed",
                                            "계기판 속도 사용",
                                            "차량 계기판 속도를 사용합니다.",
                                            "../assets/offroad/icon_road.png",
                                            this));

  toggles.append(new ParamControl("LongControlEnabled",
                                            "롱 컨트롤 사용",
                                            "SCC 배선 개조 차량만 사용하세요.",
                                            "../assets/offroad/icon_road.png",
                                            this));

  toggles.append(new ParamControl("MadModeEnabled",
                                            "MAD 모드 사용",
                                            "0km/h 오픈파일럿을 사용할 수 있고, 브레이크를 밟아도 오픈파일럿이 계속 유지됩니다.",
                                            "../assets/offroad/icon_openpilot.png",
                                            this));

  toggles.append(new ParamControl("IsLdwsCar",
                                            "LDWS 차량",
                                            "LDWS 차량에서 활성화 하세요.",
                                            "../assets/offroad/icon_openpilot.png",
                                            this));

  toggles.append(new ParamControl("LaneChangeEnabled",
                                            "차선 변경 사용",
                                            "방향 지시등을 켠 후 차선변경 방향으로 핸들을 살짝 돌리면 자동으로 차선을 변경합니다.",
                                            "../assets/offroad/icon_road.png",
                                            this));

  toggles.append(new ParamControl("AutoLaneChangeEnabled",
                                            "자동 차선 변경",
                                            "차선을 변경하고자 하는 방향으로 방향지시등을 켜면 자동으로 차선이 변경됩니다. 쥐의해서 사용하세요. BSD가 작동 중이면 차선을 변경하지 않습니다.",
                                            "../assets/offroad/icon_road.png",
                                            this));

  toggles.append(new ParamControl("SccSmootherSlowOnCurves",
                                            "커브 구간 자동 속도 줄임",
                                            "도로 커브 구간에서 자동으로 속도를 줄입니다.",
                                            "../assets/offroad/icon_road.png",
                                            this));

  toggles.append(new ParamControl("SccSmootherSyncGasPressed",
                                            "크루즈 속도 동기화",
                                            "크루즈로 주행 중 가속 페달을 밟으면 그 속도로 크루즈가 설정됩니다.",
                                            "../assets/offroad/icon_road.png",
                                            this));

  toggles.append(new ParamControl("StockNaviDecelEnabled",
                                            "순정 내비게이션 사용 감속",
                                            "롱 컨트롤 활성화 시 고속도로에서 순정 내비게이션을 이용하여 가속 감속합니다.",
                                            "../assets/offroad/icon_road.png",
                                            this));

  toggles.append(new ParamControl("KeepSteeringTurnSignals",
                                            "방향지시등 사용 중 오픈파일럿 유지",
                                            "방향지시등을 켰을 때도 오픈파일럿 사용이 계속 유지됩니다.",
                                            "../assets/offroad/icon_openpilot.png",
                                            this));
  toggles.append(new ParamControl("HapticFeedbackWhenSpeedCamera",
                                            "햅틱(Heptic) 기능 사용",
                                            "과속 단속 카메라 감지 시 햅틱(Heptic) 활성화. 햅틱기술? 차선이탈, 후측방 경보 작동 시 진동으로 알려주는 기능.",
                                            "../assets/offroad/icon_openpilot.png",
                                            this));

  /*toggles.append(new ParamControl("NewRadarInterface",
                                            "Use new radar interface",
                                            "",
                                            "../assets/offroad/icon_road.png",
                                            this));*/

  toggles.append(new ParamControl("DisableOpFcw",
                                            "오픈파일럿 FCW 사용",
                                            "오픈파일럿 비전 기술을 이용하여 전방충돌경보 기능을 사용합니다.",
                                            "../assets/offroad/icon_shell.png",
                                            this));

  toggles.append(new ParamControl("ShowDebugUI",
                                            "디버그 정보 표시",
                                            "오픈파일럿 화면에 디버그 정보를 표시합니다.",
                                            "../assets/offroad/icon_shell.png",
                                            this));

  /*toggles.append(new ParamControl("CustomLeadMark",
                                            "Use custom lead mark",
                                            "",
                                            "../assets/offroad/icon_road.png",
                                            this));*/

  for(ParamControl *toggle : toggles) {
    if(main_layout->count() != 0) {
      toggleLayout->addWidget(horizontal_line());
    }
    toggleLayout->addWidget(toggle);
  }
}

SelectCar::SelectCar(QWidget* parent): QWidget(parent) {

  QVBoxLayout* main_layout = new QVBoxLayout(this);
  main_layout->setMargin(20);
  main_layout->setSpacing(20);

  // Back button
  QPushButton* back = new QPushButton("뒤로");
  back->setObjectName("back_btn");
  back->setFixedSize(500, 100);
  connect(back, &QPushButton::clicked, [=]() { emit backPress(); });
  main_layout->addWidget(back, 0, Qt::AlignLeft);

  QListWidget* list = new QListWidget(this);
  list->setStyleSheet("QListView {padding: 40px; background-color: #393939; border-radius: 15px; height: 140px;} QListView::item{height: 100px}");
  //list->setAttribute(Qt::WA_AcceptTouchEvents, true);
  QScroller::grabGesture(list->viewport(), QScroller::LeftMouseButtonGesture);
  list->setVerticalScrollMode(QAbstractItemView::ScrollPerPixel);

  list->addItem("[ 차량을 선택하세요 ]");

  QStringList items = get_list("/data/params/d/SupportedCars");
  list->addItems(items);
  list->setCurrentRow(0);

  QString selected = QString::fromStdString(Params().get("SelectedCar"));

  int index = 0;
  for(QString item : items) {
    if(selected == item) {
        list->setCurrentRow(index + 1);
        break;
    }
    index++;
  }

  QObject::connect(list, QOverload<QListWidgetItem*>::of(&QListWidget::itemClicked),
    [=](QListWidgetItem* item){

    if(list->currentRow() == 0)
        Params().remove("SelectedCar");
    else
        Params().put("SelectedCar", list->currentItem()->text().toStdString());

    emit selectedCar();
    });

  main_layout->addWidget(list);
}

LateralControl::LateralControl(QWidget* parent): QWidget(parent) {

  QVBoxLayout* main_layout = new QVBoxLayout(this);
  main_layout->setMargin(20);
  main_layout->setSpacing(20);

  // Back button
  QPushButton* back = new QPushButton("뒤로");
  back->setObjectName("back_btn");
  back->setFixedSize(500, 100);
  connect(back, &QPushButton::clicked, [=]() { emit backPress(); });
  main_layout->addWidget(back, 0, Qt::AlignLeft);

  QListWidget* list = new QListWidget(this);
  list->setStyleSheet("QListView {padding: 40px; background-color: #393939; border-radius: 15px; height: 140px;} QListView::item{height: 100px}");
  //list->setAttribute(Qt::WA_AcceptTouchEvents, true);
  QScroller::grabGesture(list->viewport(), QScroller::LeftMouseButtonGesture);
  list->setVerticalScrollMode(QAbstractItemView::ScrollPerPixel);

  QStringList items = {"TORQUE", "LQR", "INDI"};
  list->addItems(items);
  list->setCurrentRow(0);

  QString selectedControl = QString::fromStdString(Params().get("LateralControl"));

  int index = 0;
  for(QString item : items) {
    if(selectedControl == item) {
        list->setCurrentRow(index);
        break;
    }
    index++;
  }

  QObject::connect(list, QOverload<QListWidgetItem*>::of(&QListWidget::itemClicked),
    [=](QListWidgetItem* item){

    Params().put("LateralControl", list->currentItem()->text().toStdString());
    emit selected();

    QTimer::singleShot(1000, []() {
        Params().putBool("SoftRestartTriggered", true);
      });

    });

  main_layout->addWidget(list);
}
