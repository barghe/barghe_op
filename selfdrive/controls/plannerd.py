#!/usr/bin/env python3
from cereal import car
from openpilot.common.params import Params
from openpilot.common.realtime import Priority, config_realtime_process
from openpilot.common.swaglog import cloudlog
from openpilot.selfdrive.controls.lib.longitudinal_planner import LongitudinalPlanner
import cereal.messaging as messaging
from openpilot.selfdrive.controls.neokii.lateral_lane_planner import LateralLanePlanner


def publish_ui_plan(sm, pm, longitudinal_planner):
  ui_send = messaging.new_message('uiPlan')
  ui_send.valid = sm.all_checks(service_list=['carState', 'controlsState', 'modelV2'])
  uiPlan = ui_send.uiPlan
  uiPlan.frameId = sm['modelV2'].frameId
  uiPlan.position.x = list(sm['modelV2'].position.x)
  uiPlan.position.y = list(sm['modelV2'].position.y)
  uiPlan.position.z = list(sm['modelV2'].position.z)
  uiPlan.accel = longitudinal_planner.a_desired_trajectory_full.tolist()
  pm.send('uiPlan', ui_send)

def plannerd_thread():
  config_realtime_process(5, Priority.CTRL_LOW)

  cloudlog.info("plannerd is waiting for CarParams")
  params = Params()
  with car.CarParams.from_bytes(params.get("CarParams", block=True)) as msg:
    CP = msg
  cloudlog.info("plannerd got CarParams: %s", CP.carName)

  lateral_planner = None
  if Params().get_bool('UseLanelines'):
    lateral_planner = LateralLanePlanner(CP)

  longitudinal_planner = LongitudinalPlanner(CP)
  pm = messaging.PubMaster(['longitudinalPlan', 'uiPlan', 'lateralLanePlan'])
  sm = messaging.SubMaster(['carControl', 'carState', 'controlsState', 'radarState', 'modelV2'],
                           poll=['radarState', 'modelV2'], ignore_avg_freq=['radarState'])

  while True:
    sm.update()

    if sm.updated['modelV2']:
      if lateral_planner is not None:
        lateral_planner.update(sm)
        lateral_planner.publish(sm, pm)
      longitudinal_planner.update(sm)
      longitudinal_planner.publish(sm, pm)
      publish_ui_plan(sm, pm, longitudinal_planner)

def main():
  plannerd_thread()


if __name__ == "__main__":
  main()
