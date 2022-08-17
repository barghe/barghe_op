import os
from enum import IntEnum
from typing import Dict, Union, Callable, List, Optional

from cereal import log, car
import cereal.messaging as messaging
from common.conversions import Conversions as CV
from common.realtime import DT_CTRL
from selfdrive.locationd.calibrationd import MIN_SPEED_FILTER
from selfdrive.version import get_short_branch

AlertSize = log.ControlsState.AlertSize
AlertStatus = log.ControlsState.AlertStatus
VisualAlert = car.CarControl.HUDControl.VisualAlert
AudibleAlert = car.CarControl.HUDControl.AudibleAlert
EventName = car.CarEvent.EventName


# Alert priorities
class Priority(IntEnum):
  LOWEST = 0
  LOWER = 1
  LOW = 2
  MID = 3
  HIGH = 4
  HIGHEST = 5


# Event types
class ET:
  ENABLE = 'enable'
  PRE_ENABLE = 'preEnable'
  OVERRIDE = 'override'
  NO_ENTRY = 'noEntry'
  WARNING = 'warning'
  USER_DISABLE = 'userDisable'
  SOFT_DISABLE = 'softDisable'
  IMMEDIATE_DISABLE = 'immediateDisable'
  PERMANENT = 'permanent'


# get event name from enum
EVENT_NAME = {v: k for k, v in EventName.schema.enumerants.items()}


class Events:
  def __init__(self):
    self.events: List[int] = []
    self.static_events: List[int] = []
    self.events_prev = dict.fromkeys(EVENTS.keys(), 0)

  @property
  def names(self) -> List[int]:
    return self.events

  def __len__(self) -> int:
    return len(self.events)

  def add(self, event_name: int, static: bool=False) -> None:
    if static:
      self.static_events.append(event_name)
    self.events.append(event_name)

  def clear(self) -> None:
    self.events_prev = {k: (v + 1 if k in self.events else 0) for k, v in self.events_prev.items()}
    self.events = self.static_events.copy()

  def any(self, event_type: str) -> bool:
    return any(event_type in EVENTS.get(e, {}) for e in self.events)

  def create_alerts(self, event_types: List[str], callback_args=None):
    if callback_args is None:
      callback_args = []

    ret = []
    for e in self.events:
      types = EVENTS[e].keys()
      for et in event_types:
        if et in types:
          alert = EVENTS[e][et]
          if not isinstance(alert, Alert):
            alert = alert(*callback_args)

          if DT_CTRL * (self.events_prev[e] + 1) >= alert.creation_delay:
            alert.alert_type = f"{EVENT_NAME[e]}/{et}"
            alert.event_type = et
            ret.append(alert)
    return ret

  def add_from_msg(self, events):
    for e in events:
      self.events.append(e.name.raw)

  def to_msg(self):
    ret = []
    for event_name in self.events:
      event = car.CarEvent.new_message()
      event.name = event_name
      for event_type in EVENTS.get(event_name, {}):
        setattr(event, event_type, True)
      ret.append(event)
    return ret

# 한글화: 바르게(BARGHE) 유튜브 https://www.youtube.com/channel/UCEReN-QmFazgLnEnMJd3ljA

class Alert:
  def __init__(self,
               alert_text_1: str,
               alert_text_2: str,
               alert_status: log.ControlsState.AlertStatus,
               alert_size: log.ControlsState.AlertSize,
               priority: Priority,
               visual_alert: car.CarControl.HUDControl.VisualAlert,
               audible_alert: car.CarControl.HUDControl.AudibleAlert,
               duration: float,
               alert_rate: float = 0.,
               creation_delay: float = 0.):

    self.alert_text_1 = alert_text_1
    self.alert_text_2 = alert_text_2
    self.alert_status = alert_status
    self.alert_size = alert_size
    self.priority = priority
    self.visual_alert = visual_alert
    self.audible_alert = audible_alert

    self.duration = int(duration / DT_CTRL)

    self.alert_rate = alert_rate
    self.creation_delay = creation_delay

    self.alert_type = ""
    self.event_type: Optional[str] = None

  def __str__(self) -> str:
    return f"{self.alert_text_1}/{self.alert_text_2} {self.priority} {self.visual_alert} {self.audible_alert}"

  def __gt__(self, alert2) -> bool:
    return self.priority > alert2.priority


class NoEntryAlert(Alert):
  def __init__(self, alert_text_2: str, visual_alert: car.CarControl.HUDControl.VisualAlert=VisualAlert.none):
    #super().__init__("openpilot Unavailable", alert_text_2, AlertStatus.normal,
    super().__init__("오픈파일럿 사용 불가", alert_text_2, AlertStatus.normal,
                     AlertSize.mid, Priority.LOW, visual_alert,
                     AudibleAlert.refuse, 3.)


class SoftDisableAlert(Alert):
  def __init__(self, alert_text_2: str):
    #super().__init__("TAKE CONTROL IMMEDIATELY", alert_text_2,
    super().__init__("핸들을 즉시 잡아주세요", alert_text_2,
                     AlertStatus.userPrompt, AlertSize.full,
                     Priority.MID, VisualAlert.steerRequired,
                     AudibleAlert.warningSoft, 2.),


# less harsh version of SoftDisable, where the condition is user-triggered
class UserSoftDisableAlert(SoftDisableAlert):
  def __init__(self, alert_text_2: str):
    super().__init__(alert_text_2),
    #self.alert_text_1 = "openpilot will disengage"
    self.alert_text_1 = "오픈파일럿이 해제됩니다"


class ImmediateDisableAlert(Alert):
  def __init__(self, alert_text_2: str):
    #super().__init__("TAKE CONTROL IMMEDIATELY", alert_text_2,
    super().__init__("핸들을 즉시 잡아주세요", alert_text_2,
                     AlertStatus.critical, AlertSize.full,
                     Priority.HIGHEST, VisualAlert.steerRequired,
                     AudibleAlert.warningImmediate, 4.),


class EngagementAlert(Alert):
  def __init__(self, audible_alert: car.CarControl.HUDControl.AudibleAlert):
    super().__init__("", "",
                     AlertStatus.normal, AlertSize.none,
                     Priority.MID, VisualAlert.none,
                     audible_alert, .2),


class NormalPermanentAlert(Alert):
  def __init__(self, alert_text_1: str, alert_text_2: str = "", duration: float = 0.2, priority: Priority = Priority.LOWER, creation_delay: float = 0.):
    super().__init__(alert_text_1, alert_text_2,
                     AlertStatus.normal, AlertSize.mid if len(alert_text_2) else AlertSize.small,
                     priority, VisualAlert.none, AudibleAlert.none, duration, creation_delay=creation_delay),


class StartupAlert(Alert):
  #def __init__(self, alert_text_1: str, alert_text_2: str = "Always keep hands on wheel and eyes on road", alert_status=AlertStatus.normal):
  def __init__(self, alert_text_1: str, alert_text_2: str = "항상 핸들을 잡고 도로를 주시하세요", alert_status=AlertStatus.normal):
    super().__init__(alert_text_1, alert_text_2,
                     alert_status, AlertSize.mid,
                     Priority.LOWER, VisualAlert.none, AudibleAlert.none, 5.),


# ********** helper functions **********
def get_display_speed(speed_ms: float, metric: bool) -> str:
  speed = int(round(speed_ms * (CV.MS_TO_KPH if metric else CV.MS_TO_MPH)))
  unit = 'km/h' if metric else 'mph'
  return f"{speed} {unit}"


# ********** alert callback functions **********

AlertCallbackType = Callable[[car.CarParams, messaging.SubMaster, bool, int], Alert]


def soft_disable_alert(alert_text_2: str) -> AlertCallbackType:
  def func(CP: car.CarParams, sm: messaging.SubMaster, metric: bool, soft_disable_time: int) -> Alert:
    #if soft_disable_time < int(0.5 / DT_CTRL):
    #  return ImmediateDisableAlert(alert_text_2)
    return SoftDisableAlert(alert_text_2)
  return func

def user_soft_disable_alert(alert_text_2: str) -> AlertCallbackType:
  def func(CP: car.CarParams, sm: messaging.SubMaster, metric: bool, soft_disable_time: int) -> Alert:
    #if soft_disable_time < int(0.5 / DT_CTRL):
    #  return ImmediateDisableAlert(alert_text_2)
    return UserSoftDisableAlert(alert_text_2)
  return func

def startup_master_alert(CP: car.CarParams, sm: messaging.SubMaster, metric: bool, soft_disable_time: int) -> Alert:
  branch = get_short_branch("")
  if "REPLAY" in os.environ:
    branch = "replay"

  return StartupAlert("경고!:이 브랜치는 테스트되지 않았습니다", branch, alert_status=AlertStatus.userPrompt)

def below_engage_speed_alert(CP: car.CarParams, sm: messaging.SubMaster, metric: bool, soft_disable_time: int) -> Alert:
  return NoEntryAlert(f"Speed Below {get_display_speed(CP.minEnableSpeed, metric)}")


def below_steer_speed_alert(CP: car.CarParams, sm: messaging.SubMaster, metric: bool, soft_disable_time: int) -> Alert:
  return Alert(
    #f"Steer Unavailable Below {get_display_speed(CP.minSteerSpeed, metric)}",
    #"",
    f"{get_display_speed(CP.minSteerSpeed, metric)} 이상의 속도에서 조향제어가 가능합니다",
    "",
    AlertStatus.userPrompt, AlertSize.small,
    Priority.MID, VisualAlert.steerRequired, AudibleAlert.prompt, 0.4)


def calibration_incomplete_alert(CP: car.CarParams, sm: messaging.SubMaster, metric: bool, soft_disable_time: int) -> Alert:
  return Alert(
    #"Calibration in Progress: %d%%" % sm['liveCalibration'].calPerc,
    #f"Drive Above {get_display_speed(MIN_SPEED_FILTER, metric)}",
    "캘리브레이션 진행중: %d%%" % sm['liveCalibration'].calPerc,
    f"속도를 {get_display_speed(MIN_SPEED_FILTER, metric)}이상으로 주행하세요",
    AlertStatus.normal, AlertSize.mid,
    Priority.LOWEST, VisualAlert.none, AudibleAlert.none, .2)


def no_gps_alert(CP: car.CarParams, sm: messaging.SubMaster, metric: bool, soft_disable_time: int) -> Alert:
  gps_integrated = sm['peripheralState'].pandaType in (log.PandaState.PandaType.uno, log.PandaState.PandaType.dos)
  return Alert(
    #"Poor GPS reception",
    #"Hardware malfunctioning if sky is visible" if gps_integrated else "Check GPS antenna placement",
    "GPS 수신 불량",
    "GPS 연결 상태 및 안테나를 점검하세요" if gps_integrated else "GPS 안테나를 점검하세요",
    AlertStatus.normal, AlertSize.mid,
    Priority.LOWER, VisualAlert.none, AudibleAlert.none, .2, creation_delay=300.)


def wrong_car_mode_alert(CP: car.CarParams, sm: messaging.SubMaster, metric: bool, soft_disable_time: int) -> Alert:
  #text = "Cruise Mode Disabled"
  text = "크루즈 모드 비활성화"
  if CP.carName == "honda":
    #text = "Main Switch Off"
    text = "메인 스위치 꺼짐"
  return NoEntryAlert(text)


def joystick_alert(CP: car.CarParams, sm: messaging.SubMaster, metric: bool, soft_disable_time: int) -> Alert:
  axes = sm['testJoystick'].axes
  gb, steer = list(axes)[:2] if len(axes) else (0., 0.)
  vals = f"Gas: {round(gb * 100.)}%, Steer: {round(steer * 100.)}%"
  #return NormalPermanentAlert("Joystick Mode", vals)
  return NormalPermanentAlert("조이스틱 모드", vals)

def auto_lane_change_alert(CP: car.CarParams, sm: messaging.SubMaster, metric: bool, soft_disable_time: int) -> Alert:
  alc_timer = sm['lateralPlan'].autoLaneChangeTimer
  return Alert(
    #"Auto Lane Change starts in (%d)" % alc_timer,
    #"Monitor Other Vehicles",
    "차선 변경이 (%d) 초 뒤 시작됩니다" % alc_timer,
    "차선 변경 중 다른 차량에 주의하세요",
    AlertStatus.normal, AlertSize.mid,
    Priority.LOWER, VisualAlert.steerRequired, AudibleAlert.none, .1, alert_rate=0.75)



EVENTS: Dict[int, Dict[str, Union[Alert, AlertCallbackType]]] = {
  # ********** events with no alerts **********

  EventName.stockFcw: {},

  # ********** events only containing alerts displayed in all states **********

  EventName.joystickDebug: {
    ET.WARNING: joystick_alert,
    #ET.PERMANENT: NormalPermanentAlert("Joystick Mode"),
    ET.PERMANENT: NormalPermanentAlert("조이스틱 모드"),
  },

  EventName.controlsInitializing: {
    #ET.NO_ENTRY: NoEntryAlert("System Initializing"),
    ET.NO_ENTRY: NoEntryAlert("시스템 초기화 중입니다"),
  },

  EventName.startup: {
    #ET.PERMANENT: StartupAlert("Be ready to take over at any time")
    ET.PERMANENT: StartupAlert("오픈파일럿 사용 준비 완료")
  },

  EventName.startupMaster: {
    ET.PERMANENT: startup_master_alert,
  },

  # Car is recognized, but marked as dashcam only
  EventName.startupNoControl: {
    #ET.PERMANENT: StartupAlert("Dashcam mode"),
    ET.PERMANENT: StartupAlert("대시캠 모드"),
  },

  # Car is not recognized
  EventName.startupNoCar: {
    #ET.PERMANENT: StartupAlert("Dashcam mode for unsupported car"),
    ET.PERMANENT: StartupAlert("대시캠 모드: 차량이 호환되지 않습니다"),
  },

  EventName.startupNoFw: {
    #ET.PERMANENT: StartupAlert("Car Unrecognized",
                               #"Check comma power connections",
    ET.PERMANENT: StartupAlert("차량이 인식되지 않았습니다",
                               "배선 및 연결 상태를 확인하세요",
                               alert_status=AlertStatus.userPrompt),
  },

  EventName.dashcamMode: {
    #ET.PERMANENT: NormalPermanentAlert("Dashcam Mode",
    ET.PERMANENT: NormalPermanentAlert("대시캠 모드",
                                       priority=Priority.LOWEST),
  },

  EventName.invalidLkasSetting: {
    #ET.PERMANENT: NormalPermanentAlert("Stock LKAS is on",
                                       #"Turn off stock LKAS to engage"),
    ET.PERMANENT: NormalPermanentAlert("LKAS 버튼 확인",
                                       "오픈파일럿을 활성화하려면 차량에서 LKAS 버튼을 끄세요"),
  },

  EventName.cruiseMismatch: {
    #ET.PERMANENT: ImmediateDisableAlert("openpilot failed to cancel cruise"),
  },

  # openpilot doesn't recognize the car. This switches openpilot into a
  # read-only mode. This can be solved by adding your fingerprint.
  # See https://github.com/commaai/openpilot/wiki/Fingerprinting for more information
  EventName.carUnrecognized: {
    #ET.PERMANENT: NormalPermanentAlert("Dashcam Mode",
                                       #"Car Unrecognized",
    ET.PERMANENT: NormalPermanentAlert("대시캠 모드",
                                       "배선 연결 상태를 확인하세요",
                                       priority=Priority.LOWEST),
  },

  EventName.stockAeb: {
    ET.PERMANENT: Alert(
      #"BRAKE!",
      #"Stock AEB: Risk of Collision",
      "브레이크!",
      "추돌 주의",
      AlertStatus.critical, AlertSize.full,
      Priority.HIGHEST, VisualAlert.fcw, AudibleAlert.none, 2.),
    #ET.NO_ENTRY: NoEntryAlert("Stock AEB: Risk of Collision"),
    ET.NO_ENTRY: NoEntryAlert("전방 추돌 주의: 추돌 위험"),
  },

  EventName.fcw: {
    ET.PERMANENT: Alert(
      #"BRAKE!",
      #"Risk of Collision",
      "브레이크!",
      "추돌 주의",
      AlertStatus.critical, AlertSize.full,
      Priority.HIGHEST, VisualAlert.fcw, AudibleAlert.warningSoft, 2.),
  },

  EventName.ldw: {
    ET.PERMANENT: Alert(
      #"Lane Departure Detected",
      #"",
      "핸들을 잡아주세요",
      "차선이탈 감지",
      AlertStatus.userPrompt, AlertSize.small,
      Priority.LOW, VisualAlert.ldw, AudibleAlert.prompt, 3.),
  },

  # ********** events only containing alerts that display while engaged **********

  # openpilot tries to learn certain parameters about your car by observing
  # how the car behaves to steering inputs from both human and openpilot driving.
  # This includes:
  # - steer ratio: gear ratio of the steering rack. Steering angle divided by tire angle
  # - tire stiffness: how much grip your tires have
  # - angle offset: most steering angle sensors are offset and measure a non zero angle when driving straight
  # This alert is thrown when any of these values exceed a sanity check. This can be caused by
  # bad alignment or bad sensor data. If this happens consistently consider creating an issue on GitHub
  EventName.vehicleModelInvalid: {
    #ET.NO_ENTRY: NoEntryAlert("Vehicle Parameter Identification Failed"),
    #ET.SOFT_DISABLE: soft_disable_alert("Vehicle Parameter Identification Failed"),
    ET.NO_ENTRY: NoEntryAlert("차량 정보 인식 실패"),
    ET.SOFT_DISABLE: soft_disable_alert("차량 정보 인식 실패"),
  },

  EventName.steerTempUnavailableSilent: {
    ET.WARNING: Alert(
      #"Steering Temporarily Unavailable",
      #"",
      "조향 제어를 일시적으로 사용할 수 없습니다",
      "",
      AlertStatus.userPrompt, AlertSize.small,
      Priority.LOW, VisualAlert.steerRequired, AudibleAlert.prompt, 1.),
  },

  EventName.preDriverDistracted: {
    ET.WARNING: Alert(
      #"Pay Attention",
      #"",
      "도로를 주시하세요",
      "",
      AlertStatus.normal, AlertSize.small,
      Priority.LOW, VisualAlert.none, AudibleAlert.none, .1),
  },

  EventName.promptDriverDistracted: {
    ET.WARNING: Alert(
      #"Pay Attention",
      #"Driver Distracted",
      "도로를 주시하세요",
      "운전자 도로 주시 불안",
      AlertStatus.userPrompt, AlertSize.mid,
      Priority.MID, VisualAlert.steerRequired, AudibleAlert.promptDistracted, .1),
  },

  EventName.driverDistracted: {
    ET.WARNING: Alert(
      #"DISENGAGE IMMEDIATELY",
      #"Driver Distracted",
      "조향 제어가 해제됩니다",
      "운전자 도로 주시 불안",
      AlertStatus.critical, AlertSize.full,
      Priority.HIGH, VisualAlert.steerRequired, AudibleAlert.warningImmediate, .1),
  },

  EventName.preDriverUnresponsive: {
    ET.WARNING: Alert(
      #"Touch Steering Wheel: No Face Detected",
      #"",
      "핸들을 잡아주세요: 운전자 인식 불가",
      "",
      AlertStatus.normal, AlertSize.small,
      Priority.LOW, VisualAlert.steerRequired, AudibleAlert.none, .1, alert_rate=0.75),
  },

  EventName.promptDriverUnresponsive: {
    ET.WARNING: Alert(
      #"Touch Steering Wheel",
      #"Driver Unresponsive",
      "핸들을 잡아주세요",
      "운전자가 응답하지 않습니다",
      AlertStatus.userPrompt, AlertSize.mid,
      Priority.MID, VisualAlert.steerRequired, AudibleAlert.promptDistracted, .1),
  },

  EventName.driverUnresponsive: {
    ET.WARNING: Alert(
      #"DISENGAGE IMMEDIATELY",
      #"Driver Unresponsive",
      "조향 제어가 해제됩니다",
      "운전자가 응답하지 않습니다",
      AlertStatus.critical, AlertSize.full,
      Priority.HIGH, VisualAlert.steerRequired, AudibleAlert.warningImmediate, .1),
  },

  EventName.manualRestart: {
    ET.WARNING: Alert(
      #"TAKE CONTROL",
      #"Resume Driving Manually",
      "핸들을 잡아주세요",
      "운전자가 직접 제어하세요",
      AlertStatus.userPrompt, AlertSize.mid,
      Priority.LOW, VisualAlert.none, AudibleAlert.none, .2),
  },

  EventName.resumeRequired: {
    ET.WARNING: Alert(
      #"STOPPED",
      #"Press Resume to Go",
      "앞 차량 멈춤",
      "출발하려면 +버튼을 위로 올리세요",
      AlertStatus.userPrompt, AlertSize.mid,
      Priority.LOW, VisualAlert.none, AudibleAlert.none, .2),
  },

  EventName.belowSteerSpeed: {
    ET.WARNING: below_steer_speed_alert,
  },

  EventName.preLaneChangeLeft: {
    ET.WARNING: Alert(
      #"Steer Left to Start Lane Change Once Safe",
      #"",
      "왼쪽 차선으로 차선을 변경합니다",
      "",
      AlertStatus.normal, AlertSize.small,
      Priority.LOW, VisualAlert.none, AudibleAlert.none, .1, alert_rate=0.75),
  },

  EventName.preLaneChangeRight: {
    ET.WARNING: Alert(
      #"Steer Right to Start Lane Change Once Safe",
      #"",
      "오른쪽 차선으로 차선을 변경합니다",
      "",
      AlertStatus.normal, AlertSize.small,
      Priority.LOW, VisualAlert.none, AudibleAlert.none, .1, alert_rate=0.75),
  },

  EventName.laneChangeBlocked: {
    ET.WARNING: Alert(
      #"Car Detected in Blindspot",
      #"",
      "차량 감지: 주의하세요",
      "",
      AlertStatus.userPrompt, AlertSize.small,
      Priority.LOW, VisualAlert.none, AudibleAlert.prompt, .1),
  },

  EventName.laneChange: {
    ET.WARNING: Alert(
      #"Changing Lanes",
      #"",
      "차선을 변경합니다",
      "",
      AlertStatus.normal, AlertSize.small,
      Priority.LOW, VisualAlert.none, AudibleAlert.none, .1),
  },

  EventName.steerSaturated: {
    ET.WARNING: Alert(
      #"Take Control",
      #"Turn Exceeds Steering Limit",
      "핸들을 잡아주세요",
      "조향 제어 값을 초과하였습니다",
      AlertStatus.userPrompt, AlertSize.mid,
      Priority.LOW, VisualAlert.steerRequired, AudibleAlert.promptRepeat, 1.),
  },

  # Thrown when the fan is driven at >50% but is not rotating
  EventName.fanMalfunction: {
    #ET.PERMANENT: NormalPermanentAlert("Fan Malfunction", "Likely Hardware Issue"),
    ET.PERMANENT: NormalPermanentAlert("팬 오작동", "장치를 점검하세요"),
  },

  # Camera is not outputting frames
  EventName.cameraMalfunction: {
    #ET.PERMANENT: NormalPermanentAlert("Camera Malfunction", "Likely Hardware Issue"),
    ET.PERMANENT: NormalPermanentAlert("카메라 오작동", "장치를 점검하세요"),
  },
  # Camera framerate too low
  EventName.cameraFrameRate: {
    #ET.PERMANENT: NormalPermanentAlert("카메라 오작동", "시스템을 재부팅 하세요"),
    ET.PERMANENT: NormalPermanentAlert("Camera Frame Rate Low", "Reboot your Device"),
  },

  # Unused
  EventName.gpsMalfunction: {
    #ET.PERMANENT: NormalPermanentAlert("GPS Malfunction", "Likely Hardware Issue"),
    ET.PERMANENT: NormalPermanentAlert("GPS 오작동", "장치를 점검하세요"),
  },

  # When the GPS position and localizer diverge the localizer is reset to the
  # current GPS position. This alert is thrown when the localizer is reset
  # more often than expected.
  EventName.localizerMalfunction: {
    # ET.PERMANENT: NormalPermanentAlert("Sensor Malfunction", "Hardware Malfunction"),
  },

  # ********** events that affect controls state transitions **********

  EventName.pcmEnable: {
    ET.ENABLE: EngagementAlert(AudibleAlert.engage),
  },

  EventName.buttonEnable: {
    ET.ENABLE: EngagementAlert(AudibleAlert.engage),
  },

  EventName.pcmDisable: {
    ET.USER_DISABLE: EngagementAlert(AudibleAlert.disengage),
  },

  EventName.buttonCancel: {
    ET.USER_DISABLE: EngagementAlert(AudibleAlert.disengage),
  },

  EventName.brakeHold: {
    ET.USER_DISABLE: EngagementAlert(AudibleAlert.disengage),
    #ET.NO_ENTRY: NoEntryAlert("Brake Hold Active"),
    ET.NO_ENTRY: NoEntryAlert("주차 브레이크가 활성화되었습니다"),
  },

  EventName.parkBrake: {
    ET.USER_DISABLE: EngagementAlert(AudibleAlert.disengage),
    #ET.NO_ENTRY: NoEntryAlert("Parking Brake Engaged"),
    ET.NO_ENTRY: NoEntryAlert("주차 브레이크를 해제하세요"),
  },

  EventName.pedalPressed: {
    ET.USER_DISABLE: EngagementAlert(AudibleAlert.disengage),
    #ET.NO_ENTRY: NoEntryAlert("Pedal Pressed",
    ET.NO_ENTRY: NoEntryAlert("가속페달을 밟았습니다",
                              visual_alert=VisualAlert.brakePressed),
  },

  EventName.pedalPressedPreEnable: {
    ET.PRE_ENABLE: Alert(
      #"Release Pedal to Engage",
      #"",
      "오픈파일럿을 사용하려면 가속페달에서 발을 떼세요",
      "",
      AlertStatus.normal, AlertSize.small,
      Priority.LOWEST, VisualAlert.none, AudibleAlert.none, .1, creation_delay=1.),
  },

  EventName.gasPressedOverride: {
    ET.OVERRIDE: Alert(
      "",
      "",
      AlertStatus.normal, AlertSize.none,
      Priority.LOWEST, VisualAlert.none, AudibleAlert.none, .1),
  },

  EventName.wrongCarMode: {
    ET.USER_DISABLE: EngagementAlert(AudibleAlert.disengage),
    ET.NO_ENTRY: wrong_car_mode_alert,
  },

  EventName.wrongCruiseMode: {
    ET.USER_DISABLE: EngagementAlert(AudibleAlert.disengage),
    #ET.NO_ENTRY: NoEntryAlert("Adaptive Cruise Disabled"),
    ET.NO_ENTRY: NoEntryAlert("어댑티브크루즈를 활성화하세요"),
  },

  EventName.steerTempUnavailable: {
    #ET.SOFT_DISABLE: soft_disable_alert("Steering Temporarily Unavailable"),
    #ET.NO_ENTRY: NoEntryAlert("Steering Temporarily Unavailable"),
    ET.SOFT_DISABLE: soft_disable_alert("조향 제어를 일시적으로 사용할 수 없습니다"),
    ET.NO_ENTRY: NoEntryAlert("조향 제어를 일시적으로 사용할 수 없습니다"),
  },

  EventName.outOfSpace: {
    #ET.PERMANENT: NormalPermanentAlert("Out of Storage"),
    #ET.NO_ENTRY: NoEntryAlert("Out of Storage"),
    ET.PERMANENT: NormalPermanentAlert("저장 공간이 부족합니다"),
    ET.NO_ENTRY: NoEntryAlert("저장 공간이 부족합니다"),
  },

  EventName.belowEngageSpeed: {
    ET.NO_ENTRY: below_engage_speed_alert,
  },

  EventName.sensorDataInvalid: {
    ET.PERMANENT: Alert(
      #"No Data from Device Sensors",
      #"Reboot your Device",
      "장치 센서 오류",
      "장치를 점검하세요",
      AlertStatus.normal, AlertSize.mid,
      Priority.LOWER, VisualAlert.none, AudibleAlert.none, .2, creation_delay=1.),
    #ET.NO_ENTRY: NoEntryAlert("No Data from Device Sensors"),
    ET.NO_ENTRY: NoEntryAlert("장치 센서 오류"),
  },

  EventName.noGps: {
    ET.PERMANENT: no_gps_alert,
  },

  EventName.soundsUnavailable: {
    #ET.PERMANENT: NormalPermanentAlert("Speaker not found", "Reboot your Device"),
    #ET.NO_ENTRY: NoEntryAlert("Speaker not found"),
    ET.PERMANENT: NormalPermanentAlert("스피커 장치를 찾을 수 없습니다", "시스템을 재부팅하세요"),
    ET.NO_ENTRY: NoEntryAlert("스피커 장치를 찾을 수 없습니다"),
  },

  EventName.tooDistracted: {
    #ET.NO_ENTRY: NoEntryAlert("Distraction Level Too High"),
    ET.NO_ENTRY: NoEntryAlert("주의산만: 휴식이 필요합니다"),
  },

  EventName.overheat: {
    #ET.PERMANENT: NormalPermanentAlert("System Overheated"),
    #ET.SOFT_DISABLE: soft_disable_alert("System Overheated"),
    #ET.NO_ENTRY: NoEntryAlert("System Overheated"),
    ET.PERMANENT: NormalPermanentAlert("시스템 과열"),
    ET.SOFT_DISABLE: soft_disable_alert("시스템 과열"),
    ET.NO_ENTRY: NoEntryAlert("시스템 과열"),
  },

  EventName.wrongGear: {
    #ET.SOFT_DISABLE: user_soft_disable_alert("Gear not D"),
    #ET.NO_ENTRY: NoEntryAlert("Gear not D"),
    ET.SOFT_DISABLE: user_soft_disable_alert("기어가 D에 위치하지 않았습니다"),
    ET.NO_ENTRY: NoEntryAlert("기어가 D에 위치하지 않았습니다"),
  },

  # This alert is thrown when the calibration angles are outside of the acceptable range.
  # For example if the device is pointed too much to the left or the right.
  # Usually this can only be solved by removing the mount from the windshield completely,
  # and attaching while making sure the device is pointed straight forward and is level.
  # See https://comma.ai/setup for more information
  EventName.calibrationInvalid: {
    #ET.PERMANENT: NormalPermanentAlert("Calibration Invalid", "Remount Device and Recalibrate"),
    #ET.SOFT_DISABLE: soft_disable_alert("Calibration Invalid: Remount Device & Recalibrate"),
    #ET.NO_ENTRY: NoEntryAlert("Calibration Invalid: Remount Device & Recalibrate"),
    ET.PERMANENT: NormalPermanentAlert("캘리브레이션 오류", "장치를 정확히 부착 후 캘리브레이션을 다시 하세요"),
    ET.SOFT_DISABLE: soft_disable_alert("캘리브레이션 오류: 장치를 정확히 부착 후 캘리브레이션을 다시 하세요"),
    ET.NO_ENTRY: NoEntryAlert("캘리브레이션 오류: 장치를 정확히 부착 후 캘리브레이션을 다시 하세요"),
  },

  EventName.calibrationIncomplete: {
    ET.PERMANENT: calibration_incomplete_alert,
    #ET.SOFT_DISABLE: soft_disable_alert("Calibration in Progress"),
    #ET.NO_ENTRY: NoEntryAlert("Calibration in Progress"),
    ET.SOFT_DISABLE: soft_disable_alert("캘리브레이션을 진행하고 있습니다"),
    ET.NO_ENTRY: NoEntryAlert("캘리브레이션을 진행하고 있습니다"),
  },

  EventName.doorOpen: {
    #ET.SOFT_DISABLE: user_soft_disable_alert("Door Open"),
    #ET.NO_ENTRY: NoEntryAlert("Door Open"),
    ET.SOFT_DISABLE: user_soft_disable_alert("문이 열렸습니다"),
    ET.NO_ENTRY: NoEntryAlert("문이 열렸습니다"),
  },

  EventName.seatbeltNotLatched: {
    #ET.SOFT_DISABLE: user_soft_disable_alert("Seatbelt Unlatched"),
    #ET.NO_ENTRY: NoEntryAlert("Seatbelt Unlatched"),
    ET.SOFT_DISABLE: user_soft_disable_alert("안전벨트를 착용하세요"),
    ET.NO_ENTRY: NoEntryAlert("안전벨트를 착용하세요"),
  },

  EventName.espDisabled: {
    #ET.SOFT_DISABLE: soft_disable_alert("ESP Off"),
    #ET.NO_ENTRY: NoEntryAlert("ESP Off"),
    ET.SOFT_DISABLE: soft_disable_alert("차체 자세 제어장치(ESP)가 꺼져있습니다"),
    ET.NO_ENTRY: NoEntryAlert("차체 자세 제어장치(ESP)가 꺼져있습니다"),
  },

  EventName.lowBattery: {
    ET.SOFT_DISABLE: soft_disable_alert("배터리가 부족합니다"),
    ET.NO_ENTRY: NoEntryAlert("배터리가 부족합니다"),
  },

  # Different openpilot services communicate between each other at a certain
  # interval. If communication does not follow the regular schedule this alert
  # is thrown. This can mean a service crashed, did not broadcast a message for
  # ten times the regular interval, or the average interval is more than 10% too high.
  EventName.commIssue: {
    #ET.SOFT_DISABLE: soft_disable_alert("Communication Issue between Processes"),
    #ET.NO_ENTRY: NoEntryAlert("Communication Issue between Processes"),
    ET.SOFT_DISABLE: soft_disable_alert("장치에서 프로세서 오류가 발생했습니다"),
    ET.NO_ENTRY: NoEntryAlert("장치에서 프로세서 오류가 발생했습니다"),
  },
  EventName.commIssueAvgFreq: {
    #ET.SOFT_DISABLE: soft_disable_alert("Low Communication Rate between Processes"),
    #ET.NO_ENTRY: NoEntryAlert("Low Communication Rate between Processes"),
    ET.SOFT_DISABLE: soft_disable_alert("장치에서 프로세서 통신속도가 느립니다"),
    ET.NO_ENTRY: NoEntryAlert("장치에서 프로세서 통신속도가 느립니다"),
  },

  # Thrown when manager detects a service exited unexpectedly while driving
  EventName.processNotRunning: {
    #ET.NO_ENTRY: NoEntryAlert("System Malfunction: Reboot Your Device"),
    ET.NO_ENTRY: NoEntryAlert("시스템 작동 불가: 시스템을 재부팅하세요"),
  },

  EventName.radarFault: {
    #ET.SOFT_DISABLE: soft_disable_alert("Radar Error: Restart the Car"),
    #ET.NO_ENTRY: NoEntryAlert("Radar Error: Restart the Car"),
    ET.SOFT_DISABLE: soft_disable_alert("레이더 오류: 시동을 다시 걸어주세요"),
    ET.NO_ENTRY: NoEntryAlert("레이더 오류: 시동을 다시 걸어주세요"),
  },

  # Every frame from the camera should be processed by the model. If modeld
  # is not processing frames fast enough they have to be dropped. This alert is
  # thrown when over 20% of frames are dropped.
  EventName.modeldLagging: {
    #ET.SOFT_DISABLE: soft_disable_alert("Driving model lagging"),
    #ET.NO_ENTRY: NoEntryAlert("Driving model lagging"),
    ET.SOFT_DISABLE: soft_disable_alert("주행 모델이 지연되었습니다"),
    ET.NO_ENTRY: NoEntryAlert("주행 모델이 지연되었습니다"),
  },

  # Besides predicting the path, lane lines and lead car data the model also
  # predicts the current velocity and rotation speed of the car. If the model is
  # very uncertain about the current velocity while the car is moving, this
  # usually means the model has trouble understanding the scene. This is used
  # as a heuristic to warn the driver.
  EventName.posenetInvalid: {
    #ET.SOFT_DISABLE: soft_disable_alert("Model Output Uncertain"),
    #ET.NO_ENTRY: NoEntryAlert("Model Output Uncertain"),
    ET.SOFT_DISABLE: soft_disable_alert("모델 출력이 불확실합니다"),
    ET.NO_ENTRY: NoEntryAlert("모델 출력이 불확실합니다"),
  },

  # When the localizer detects an acceleration of more than 40 m/s^2 (~4G) we
  # alert the driver the device might have fallen from the windshield.
  EventName.deviceFalling: {
    #ET.SOFT_DISABLE: soft_disable_alert("Device Fell Off Mount"),
    #ET.NO_ENTRY: NoEntryAlert("Device Fell Off Mount"),
    ET.SOFT_DISABLE: soft_disable_alert("장치가 마운트에서 떨어졌습니다"),
    ET.NO_ENTRY: NoEntryAlert("장치가 마운트에서 떨어졌습니다"),
  },

  EventName.lowMemory: {
    #ET.SOFT_DISABLE: soft_disable_alert("Low Memory: Reboot Your Device"),
    #ET.PERMANENT: NormalPermanentAlert("Low Memory", "Reboot your Device"),
    #ET.NO_ENTRY: NoEntryAlert("Low Memory: Reboot Your Device"),
    ET.SOFT_DISABLE: soft_disable_alert("메모리 부족: 시스템을 재부팅하세요"),
    ET.PERMANENT: NormalPermanentAlert("메모리 부족: 시스템을 재부팅하세요"),
    ET.NO_ENTRY: NoEntryAlert("메모리 부족: 시스템을 재부팅하세요"),
  },

  EventName.highCpuUsage: {
    #ET.SOFT_DISABLE: soft_disable_alert("System Malfunction: Reboot Your Device"),
    #ET.PERMANENT: NormalPermanentAlert("System Malfunction", "Reboot your Device"),

    #ET.NO_ENTRY: NoEntryAlert("System Malfunction: Reboot Your Device"),
    ET.NO_ENTRY: NoEntryAlert("시스템 작동 불가: 시스템을 재부팅하세요"),
  },

  EventName.accFaulted: {
    #ET.IMMEDIATE_DISABLE: ImmediateDisableAlert("Cruise Faulted"),
    #ET.PERMANENT: NormalPermanentAlert("Cruise Faulted", ""),
    #ET.NO_ENTRY: NoEntryAlert("Cruise Faulted"),
    ET.IMMEDIATE_DISABLE: ImmediateDisableAlert("크루즈 오류"),
    ET.PERMANENT: NormalPermanentAlert("크루즈 오류", ""),
    ET.NO_ENTRY: NoEntryAlert("크루즈 오류"),
  },

  EventName.controlsMismatch: {
    #ET.IMMEDIATE_DISABLE: ImmediateDisableAlert("Controls Mismatch"),
    ET.IMMEDIATE_DISABLE: ImmediateDisableAlert("컨트롤 불일치"),
  },

  EventName.roadCameraError: {
    #ET.PERMANENT: NormalPermanentAlert("Camera CRC Error - Road",
    ET.PERMANENT: NormalPermanentAlert("전방 차메라 오류",
                                       duration=1.,
                                       creation_delay=30.),
  },

  EventName.wideRoadCameraError: {
    #ET.PERMANENT: NormalPermanentAlert("와이드 주행 카메라 오류",
    ET.PERMANENT: NormalPermanentAlert("",
                                       duration=1.,
                                       creation_delay=30.),
  },

  EventName.driverCameraError: {
    #ET.PERMANENT: NormalPermanentAlert("Camera CRC Error - Driver",
    ET.PERMANENT: NormalPermanentAlert("운전자 카메라 오류",
                                       duration=1.,
                                       creation_delay=30.),
  },

  # Sometimes the USB stack on the device can get into a bad state
  # causing the connection to the panda to be lost
  EventName.usbError: {
    #ET.SOFT_DISABLE: soft_disable_alert("USB Error: Reboot Your Device"),
    #ET.PERMANENT: NormalPermanentAlert("USB Error: Reboot Your Device", ""),
    #ET.NO_ENTRY: NoEntryAlert("USB Error: Reboot Your Device"),
    ET.SOFT_DISABLE: soft_disable_alert("USB 오류: 장치를 재부팅하세요"),
    ET.PERMANENT: NormalPermanentAlert("USB 오류: 장치를 재부팅하세요", ""),
    ET.NO_ENTRY: NoEntryAlert("USB 오류: 장치를 재부팅하세요"),
  },

  # This alert can be thrown for the following reasons:
  # - No CAN data received at all
  # - CAN data is received, but some message are not received at the right frequency
  # If you're not writing a new car port, this is usually cause by faulty wiring
  EventName.canError: {
    #ET.IMMEDIATE_DISABLE: ImmediateDisableAlert("CAN Error"),
    ET.IMMEDIATE_DISABLE: ImmediateDisableAlert("CAN 오류"),
    ET.PERMANENT: Alert(
      "CAN 오류: 장치를 점검하세요",
      "",
      AlertStatus.normal, AlertSize.small,
      Priority.LOW, VisualAlert.none, AudibleAlert.none, 1., creation_delay=1.),
    ET.NO_ENTRY: NoEntryAlert("CAN 오류: 장치를 점검하세요"),
  },

  EventName.canBusMissing: {
    #ET.IMMEDIATE_DISABLE: ImmediateDisableAlert("CAN Bus Disconnected"),
    ET.IMMEDIATE_DISABLE: ImmediateDisableAlert("CAN Bus 연결 끊김"),
    ET.PERMANENT: Alert(
      #"CAN Bus Disconnected: Likely Faulty Cable",
      #"",
      "CAN Bus 연결 끊김: 하네스를 점검하세요",
      "",
      AlertStatus.normal, AlertSize.small,
      Priority.LOW, VisualAlert.none, AudibleAlert.none, 1., creation_delay=1.),
    #ET.NO_ENTRY: NoEntryAlert("CAN Bus Disconnected: Check Connections"),
    ET.NO_ENTRY: NoEntryAlert("CAN Bus 연결 끊김: 하네스를 점검하세요"),
  },

  EventName.steerUnavailable: {
    #ET.IMMEDIATE_DISABLE: ImmediateDisableAlert("LKAS Fault: Restart the Car"),
    #ET.PERMANENT: NormalPermanentAlert("LKAS Fault: Restart the car to engage"),
    #ET.NO_ENTRY: NoEntryAlert("LKAS Fault: Restart the Car"),
    ET.IMMEDIATE_DISABLE: ImmediateDisableAlert("LKAS 오류: 시동을 다시 걸어주세요"),
    ET.PERMANENT: NormalPermanentAlert("LKAS 오류: 시동을 다시 걸어주세요"),
    ET.NO_ENTRY: NoEntryAlert("LKAS 오류: 시동을 다시 걸어주세요"),
  },

  EventName.brakeUnavailable: {
    #ET.IMMEDIATE_DISABLE: ImmediateDisableAlert("Cruise Fault: Restart the Car"),
    #ET.PERMANENT: NormalPermanentAlert("Cruise Fault: Restart the car to engage"),
    #ET.NO_ENTRY: NoEntryAlert("Cruise Fault: Restart the Car"),
    ET.IMMEDIATE_DISABLE: ImmediateDisableAlert("크루즈 오류: 시동을 다시 걸어주세요"),
    ET.PERMANENT: NormalPermanentAlert("크루즈 오류: 시동을 다시 걸어주세요"),
    ET.NO_ENTRY: NoEntryAlert("크루즈 오류: 시동을 다시 걸어주세요"),
  },

  EventName.reverseGear: {
    ET.PERMANENT: Alert(
      #"Reverse\nGear",
      #"",
      "후진중\n주의하세요",
      "",
      AlertStatus.normal, AlertSize.full,
      Priority.LOWEST, VisualAlert.none, AudibleAlert.none, .2, creation_delay=0.5),
    #ET.SOFT_DISABLE: SoftDisableAlert("Reverse Gear"),
    #ET.NO_ENTRY: NoEntryAlert("Reverse Gear"),
    ET.SOFT_DISABLE: SoftDisableAlert("후진기어"),
    ET.NO_ENTRY: NoEntryAlert("후진기어"),
  },

  # On cars that use stock ACC the car can decide to cancel ACC for various reasons.
  # When this happens we can no long control the car so the user needs to be warned immediately.
  EventName.cruiseDisabled: {
    #ET.IMMEDIATE_DISABLE: ImmediateDisableAlert("Cruise Is Off"),
    ET.IMMEDIATE_DISABLE: ImmediateDisableAlert("크루즈가 꺼져 있습니다"),
  },

  # For planning the trajectory Model Predictive Control (MPC) is used. This is
  # an optimization algorithm that is not guaranteed to find a feasible solution.
  # If no solution is found or the solution has a very high cost this alert is thrown.
  EventName.plannerError: {
    #ET.SOFT_DISABLE: SoftDisableAlert("Planner Solution Error"),
    #ET.NO_ENTRY: NoEntryAlert("Planner Solution Error"),
    ET.SOFT_DISABLE: SoftDisableAlert("플래너 솔루션 오류입니다"),
    ET.NO_ENTRY: NoEntryAlert("플래너 솔루션 오류입니다"),
  },

  # When the relay in the harness box opens the CAN bus between the LKAS camera
  # and the rest of the car is separated. When messages from the LKAS camera
  # are received on the car side this usually means the relay hasn't opened correctly
  # and this alert is thrown.
  EventName.relayMalfunction: {
    #ET.IMMEDIATE_DISABLE: ImmediateDisableAlert("Harness Malfunction"),
    #ET.PERMANENT: NormalPermanentAlert("Harness Malfunction", "Check Hardware"),
    #ET.NO_ENTRY: NoEntryAlert("Harness Malfunction"),
    ET.IMMEDIATE_DISABLE: ImmediateDisableAlert("하네스 오작동"),
    ET.PERMANENT: NormalPermanentAlert("하네스 오작동", "장치를 점검하세요"),
    ET.NO_ENTRY: NoEntryAlert("하네스 오작동"),
  },

  EventName.noTarget: {
    ET.IMMEDIATE_DISABLE: Alert(
      #"openpilot Canceled",
      #"No close lead car",
      "오픈파일럿 사용 불가",
      "전방에 차량이 없습니다",
      AlertStatus.normal, AlertSize.mid,
      Priority.HIGH, VisualAlert.none, AudibleAlert.disengage, 3.),
    ET.NO_ENTRY: NoEntryAlert("전방에 차량이 없습니다"),
  },

  EventName.speedTooLow: {
    ET.IMMEDIATE_DISABLE: Alert(
      #"openpilot Canceled",
      #"Speed too low",
      "오픈파일럿 사용 불가",
      "속도가 너무 낮습니다",
      AlertStatus.normal, AlertSize.mid,
      Priority.HIGH, VisualAlert.none, AudibleAlert.disengage, 3.),
  },

  # When the car is driving faster than most cars in the training data, the model outputs can be unpredictable.
  EventName.speedTooHigh: {
    ET.WARNING: Alert(
      #"Speed Too High",
      #"Model uncertain at this speed",
      "속도가 높습니다",
      "속도를 줄여주세요",
      AlertStatus.userPrompt, AlertSize.mid,
      Priority.HIGH, VisualAlert.steerRequired, AudibleAlert.promptRepeat, 4.),
    #ET.NO_ENTRY: NoEntryAlert("Slow down to engage"),
    ET.NO_ENTRY: NoEntryAlert("속도를 줄이고 오픈파일럿을 활성화하세요"),
  },

  EventName.lowSpeedLockout: {
    #ET.PERMANENT: NormalPermanentAlert("Cruise Fault: Restart the car to engage"),
    #ET.NO_ENTRY: NoEntryAlert("Cruise Fault: Restart the Car"),
    ET.PERMANENT: NormalPermanentAlert("크루즈 오류: 시동을 다시 걸어주세요"),
    ET.NO_ENTRY: NoEntryAlert("크루즈 오류: 시동을 다시 걸어주세요"),
  },

  EventName.lkasDisabled: {
    #ET.PERMANENT: NormalPermanentAlert("LKAS Disabled: Enable LKAS to engage"),
    #ET.NO_ENTRY: NoEntryAlert("LKAS Disabled"),
    ET.PERMANENT: NormalPermanentAlert("LKAS 비활성화: LKAS를 활성화하고 오픈파일럿을 활성화하세요 "),
    ET.NO_ENTRY: NoEntryAlert("LKAS 비활성화"),
  },

  EventName.turningIndicatorOn: {
    ET.WARNING: Alert(
      #"TAKE CONTROL",
      #"Steer Unavailable while Turning",
      "핸들을 즉시 잡아주세요",
      "방향지시등 작동 중에는 핸들을 잡아주세요",
      AlertStatus.userPrompt, AlertSize.small,
      Priority.LOW, VisualAlert.none, AudibleAlert.none, .2),
  },

  EventName.autoLaneChange: {
    ET.WARNING: auto_lane_change_alert,
  },

  EventName.slowingDownSpeed: {
    #ET.PERMANENT: Alert("Slowing down","", AlertStatus.normal, AlertSize.small,
    ET.PERMANENT: Alert("속도를 줄이고 있습니다","", AlertStatus.normal, AlertSize.small,
      Priority.MID, VisualAlert.none, AudibleAlert.none, .1),
  },

  EventName.slowingDownSpeedSound: {
    #ET.PERMANENT: Alert("Slowing down","", AlertStatus.normal, AlertSize.small,
    ET.PERMANENT: Alert("속도를 줄이고 있습니다","", AlertStatus.normal, AlertSize.small,
      Priority.HIGH, VisualAlert.none, AudibleAlert.slowingDownSpeed, 2.),
  },

}
