import random

import numpy as np
from common.numpy_fast import clip, interp
from cereal import car
from common.conversions import Conversions as CV
from selfdrive.controls.lib.drive_helpers import V_CRUISE_MIN, V_CRUISE_MAX
from selfdrive.controls.lib.longcontrol import LongCtrlState
from selfdrive.controls.lib.longitudinal_mpc_lib.long_mpc import AUTO_TR_CRUISE_GAP
from selfdrive.controls.neokii.cruise_state_manager import CruiseStateManager
from selfdrive.car.hyundai.values import Buttons
from common.params import Params
from selfdrive.controls.lib.lateral_planner import TRAJECTORY_SIZE
from selfdrive.controls.neokii.navi_controller import SpeedLimiter
from selfdrive.controls.ntune import ntune_common_get

SYNC_MARGIN = 3.
CREEP_SPEED = 2.3



MIN_CURVE_SPEED = 32. * CV.KPH_TO_MS

EventName = car.CarEvent.EventName


class SpeedController:

  def __init__(self, CP, CI):

    self.CP = CP
    self.CI = CI

    self.long_control = CP.openpilotLongitudinalControl

    self.params = Params()
    self.read_param()

    self.target_speed = 0.

    self.wait_timer = 0
    self.alive_timer = 0
    self.btn = Buttons.NONE

    self.alive_index = 0
    self.wait_index = 0
    self.alive_count = 0

    self.wait_count_list, self.alive_count_list = CI.get_params_adjust_set_speed()
    random.shuffle(self.wait_count_list)
    random.shuffle(self.alive_count_list)

    self.slowing_down = False
    self.slowing_down_alert = False
    self.slowing_down_sound_alert = False
    self.active_cam = False

    self.max_speed_clu = 0.
    self.curve_speed_ms = 0.

    self.cruise_speed_kph = 0.
    self.real_set_speed_kph = 0.

    self.prev_cruise_enabled = False

  def kph_to_clu(self, kph):
    return int(kph * CV.KPH_TO_MS * self.speed_conv_to_clu)

  def get_alive_count(self):
    count = self.alive_count_list[self.alive_index]
    self.alive_index += 1
    if self.alive_index >= len(self.alive_count_list):
      self.alive_index = 0
    return count

  def get_wait_count(self):
    count = self.wait_count_list[self.wait_index]
    self.wait_index += 1
    if self.wait_index >= len(self.wait_count_list):
      self.wait_index = 0
    return count

  def read_param(self):
    self.slow_on_curves = True #self.params.get_bool('SlowOnCurves')
    self.sync_set_speed_while_gas_pressed = True #self.params.get_bool('SyncGasPressed')
    self.is_metric = self.params.get_bool('IsMetric')

    self.speed_conv_to_ms = CV.KPH_TO_MS if self.is_metric else CV.MPH_TO_MS
    self.speed_conv_to_clu = CV.MS_TO_KPH if self.is_metric else CV.MS_TO_MPH
    self.min_set_speed_clu = self.kph_to_clu(V_CRUISE_MIN) # TODO - neokii
    self.max_set_speed_clu = self.kph_to_clu(V_CRUISE_MAX)

  def reset(self):

    self.wait_timer = 0
    self.alive_timer = 0
    self.btn = Buttons.NONE
    self.target_speed = 0.

    self.max_speed_clu = 0.
    self.curve_speed_ms = 0.

    self.slowing_down = False
    self.slowing_down_alert = False
    self.slowing_down_sound_alert = False

    self.gapAdjust = 4

  def inject_events(self, CS, events):

    if CS.cruiseState.enabled:
      if self.slowing_down_sound_alert:
        self.slowing_down_sound_alert = False
        events.add(EventName.slowingDownSpeedSound)
      elif self.slowing_down_alert:
        events.add(EventName.slowingDownSpeed)

  def cal_max_speed(self, CS, sm, clu_speed, v_cruise_kph):

    # kph
    apply_limit_speed, road_limit_speed, left_dist, first_started, max_speed_log = \
      SpeedLimiter.instance().get_max_speed(clu_speed, self.is_metric)

    curv_limit = 0
    self.cal_curve_speed(sm, CS.vEgo, sm.frame)
    if self.slow_on_curves and self.curve_speed_ms >= MIN_CURVE_SPEED:
      max_speed_clu = min(v_cruise_kph * CV.KPH_TO_MS, self.curve_speed_ms) * self.speed_conv_to_clu
      curv_limit = int(max_speed_clu)
    else:
      max_speed_clu = self.kph_to_clu(v_cruise_kph)

    self.active_cam = road_limit_speed > 0 and left_dist > 0

    if apply_limit_speed >= self.kph_to_clu(10):

      if first_started:
        self.max_speed_clu = clu_speed

      max_speed_clu = min(max_speed_clu, apply_limit_speed)

      if clu_speed > apply_limit_speed:

        if not self.slowing_down_alert and not self.slowing_down:
          self.slowing_down_sound_alert = True
          self.slowing_down = True

        self.slowing_down_alert = True

      else:
        self.slowing_down_alert = False

    else:
      self.slowing_down_alert = False
      self.slowing_down = False

    self.update_max_speed(int(round(max_speed_clu, 1)), curv_limit != 0 and curv_limit == int(max_speed_clu))
    return max_speed_clu

  def get_lead(self, sm):

    radar = sm['radarState']
    if radar.leadOne.status:
      return radar.leadOne

    return None

  def cal_curve_speed(self, sm, v_ego, frame):

    if frame % 20 == 0:
      md = sm['modelV2']
      if len(md.position.x) == TRAJECTORY_SIZE and len(md.position.y) == TRAJECTORY_SIZE:
        x = md.position.x
        y = md.position.y
        dy = np.gradient(y, x)
        d2y = np.gradient(dy, x)
        curv = d2y / (1 + dy ** 2) ** 1.5

        start = int(interp(v_ego, [10., 27.], [10, TRAJECTORY_SIZE-10]))
        curv = curv[start:min(start+10, TRAJECTORY_SIZE)]
        a_y_max = 2.975 - v_ego * 0.0375  # ~1.85 @ 75mph, ~2.6 @ 25mph
        v_curvature = np.sqrt(a_y_max / np.clip(np.abs(curv), 1e-4, None))
        model_speed = np.mean(v_curvature) * 0.85

        if model_speed < v_ego:
          self.curve_speed_ms = float(max(model_speed, MIN_CURVE_SPEED))
        else:
          self.curve_speed_ms = 255.

        if np.isnan(self.curve_speed_ms):
          self.curve_speed_ms = 255.
      else:
        self.curve_speed_ms = 255.

  def cal_target_speed(self, CS, clu_speed, v_cruise_kph, cruise_btn_pressed):

    override_speed = 0.

    if not self.long_control:
      if CS.gasPressed and self.sync_set_speed_while_gas_pressed and not cruise_btn_pressed:
        if clu_speed + SYNC_MARGIN > self.kph_to_clu(v_cruise_kph):
          set_speed = clip(clu_speed + SYNC_MARGIN, self.min_set_speed_clu, self.max_set_speed_clu)
          v_cruise_kph = set_speed * self.speed_conv_to_ms * CV.MS_TO_KPH
          override_speed = v_cruise_kph

      self.target_speed = self.kph_to_clu(v_cruise_kph)
      if self.max_speed_clu > self.min_set_speed_clu:
        self.target_speed = clip(self.target_speed, self.min_set_speed_clu, self.max_speed_clu)

    elif CS.cruiseState.enabled:
      if CS.gasPressed and self.sync_set_speed_while_gas_pressed and not cruise_btn_pressed:
        if clu_speed + SYNC_MARGIN > self.kph_to_clu(v_cruise_kph):
          set_speed = clip(clu_speed + SYNC_MARGIN, self.min_set_speed_clu, self.max_set_speed_clu)
          self.target_speed = set_speed
          CruiseStateManager.instance().speed = set_speed * self.speed_conv_to_ms

    return override_speed

  def update_max_speed(self, max_speed, limited_curv):

    if not self.long_control or self.max_speed_clu <= 0:
      self.max_speed_clu = max_speed
    else:
      kp = 0.01 #if limited_curv else 0.01
      error = max_speed - self.max_speed_clu
      self.max_speed_clu = self.max_speed_clu + error * kp

  def get_button(self, current_set_speed):
    if self.target_speed < self.min_set_speed_clu:
      return Buttons.NONE
    error = self.target_speed - current_set_speed
    if abs(error) < 0.9:
      return Buttons.NONE
    return Buttons.RES_ACCEL if error > 0 else Buttons.SET_DECEL


  def update_v_cruise(self, controls, CS):  # called by controlds's state_transition

    v_cruise_kph = controls.v_cruise_kph
    sm = controls.sm

    self.real_set_speed_kph = v_cruise_kph

    # mph or kph
    clu_speed = CS.vEgoCluster * self.speed_conv_to_clu

    self.cal_max_speed(CS, sm, clu_speed, v_cruise_kph)
    self.cruise_speed_kph = float(clip(v_cruise_kph, V_CRUISE_MIN,
                                       self.max_speed_clu * self.speed_conv_to_ms * CV.MS_TO_KPH))

    """v_cruise_kph = self.cruise_speed_kph
    if self.prev_cruise_enabled != CS.cruiseState.enabled:
      self.prev_cruise_enabled = CS.cruiseState.enabled

      if not CS.cruiseState.enabled:
        v_cruise_kph = 0"""

    if not CS.cruiseState.enabled:
      controls.LoC.reset(v_pid=CS.vEgo)
    else:
      v_cruise_kph = self.cruise_speed_kph

    return v_cruise_kph, self.real_set_speed_kph

  def update_can(self, enabled, CC, CS, sm, can_sends):

    new_v_cruise_kph = -1

    clu_speed = CS.vEgoCluster * self.speed_conv_to_clu
    ascc_enabled = enabled and CS.cruiseState.enabled and 1 < CS.cruiseState.speed < 255 and not CS.brakePressed

    btn_pressed = self.CI.CS.cruise_buttons[-1] != Buttons.NONE

    if not self.long_control:
      if not ascc_enabled or CS.cruiseState.standstill or btn_pressed:
        self.reset()
        self.wait_timer = max(self.alive_count_list) + max(self.wait_count_list)
        return new_v_cruise_kph

    if not ascc_enabled:
      self.reset()

    override_speed = self.cal_target_speed(CS, clu_speed, self.real_set_speed_kph, btn_pressed)
    if override_speed > 0:
      new_v_cruise_kph = override_speed

    if self.wait_timer > 0:
      self.wait_timer -= 1
    elif ascc_enabled and CS.vEgo > 0.1 and CruiseStateManager.instance().is_set_speed_spam_allowed(self.CP):
      if self.alive_timer == 0:
        current_set_speed_clu = int(round(CS.cruiseState.speed * self.speed_conv_to_clu, 1))
        self.btn = self.get_button(current_set_speed_clu)
        self.alive_count = self.get_alive_count()

      if self.btn != Buttons.NONE:
        can = self.CI.create_buttons(self.btn)
        if can is not None:
          can_sends.append(can)

        self.alive_timer += 1

        if self.alive_timer >= self.alive_count:
          self.alive_timer = 0
          self.wait_timer = self.get_wait_count()
          self.btn = Buttons.NONE
      else:
        if self.long_control and self.target_speed >= self.min_set_speed_clu:
          self.target_speed = 0.
    else:
      if self.long_control:
        self.target_speed = 0.

    return new_v_cruise_kph

  def update_message(self, c, CC, CS):

    CC.cruiseMaxSpeed = CS.cruiseState.speed * (CV.MS_TO_KPH if c.is_metric else CV.MS_TO_MPH)
    CC.applyMaxSpeed = c.v_cruise_kph
    CC.autoTrGap = AUTO_TR_CRUISE_GAP
    CC.sccBus = c.CP.sccBus
    CC.steerRatio = c.VM.sR
    CC.steerActuatorDelay = ntune_common_get('steerActuatorDelay')

    if True:
      actuators = c.last_actuators
      loc = c.LoC

      debug_text  = "Standstill: {}\n".format(CS.cruiseState.standstill)
      debug_text += "Long State: {}\n".format(actuators.longControlState)
      debug_text += "vEgo: {:.2f}/{:.2f}\n".format(CS.vEgo, CS.vEgo*3.6)

      debug_text += "vPid: {:.2f}/{:.2f}\n".format(loc.v_pid, loc.v_pid*3.6)
      debug_text += "PID: {:.2f}/{:.2f}/{:.2f}\n".format(loc.pid.p, loc.pid.i, loc.pid.f)

      debug_text += "Actuator Accel: {:.2f}\n".format(actuators.accel)
      debug_text += "Apply Accel: {:.2f}\n".format(CC.applyAccel)
      debug_text += "Stock Accel: {:.2f}\n".format(CC.aReqValue)

      lead_radar = c.sm['radarState'].leadOne
      lead_model = c.sm['modelV2'].leadsV3[0]

      radar_dist = lead_radar.dRel if lead_radar.status and lead_radar.radar else 0
      vision_dist = lead_model.x[0] if lead_model.prob > .5 else 0

      debug_text += "Lead: {:.1f}/{:.1f}/{:.1f}".format(radar_dist, vision_dist, (radar_dist - vision_dist))

      CC.debugText = debug_text