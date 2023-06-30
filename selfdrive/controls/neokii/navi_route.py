#!/usr/bin/env python3
import socketserver
import struct
import threading
from threading import Thread

from cereal import messaging
from common.realtime import Ratekeeper
from selfdrive.navd.helpers import Coordinate
from common.params import Params

ROUTE_RECEIVE_PORT = 2844

class NaviRoute():
  def __init__(self):
    self.sm = messaging.SubMaster(['managerState'])
    self.pm = messaging.PubMaster(['navInstruction', 'navRoute'])
    self.last_routes = None
    self.ui_pid = None

    route_thread = Thread(target=self.route_thread, args=[])
    route_thread.daemon = True
    route_thread.start()

  def update(self):
    self.sm.update(0)

    if self.sm.updated["managerState"]:
      ui_pid = [p.pid for p in self.sm["managerState"].processes if p.name == "ui" and p.running]
      if ui_pid:
        if self.ui_pid and self.ui_pid != ui_pid[0]:
          threading.Timer(5.0, self.send_route).start()
        self.ui_pid = ui_pid[0]

  def route_thread(self):
    route_server = self.RouteTCPServer(('0.0.0.0', ROUTE_RECEIVE_PORT), self.RouteTCPHandler, self)
    route_server.serve_forever()

  def send_route(self):
    msg = messaging.new_message('navRoute')
    if self.last_routes is not None:
      msg.navRoute.coordinates = self.last_routes
    self.pm.send('navRoute', msg)

  def dispatch_route(self, routes):
    self.last_routes = routes
    self.send_route()

  class RouteTCPServer(socketserver.TCPServer):
    def __init__(self, server_address, RequestHandlerClass, navi_route):
      self.navi_route = navi_route
      super().__init__(server_address, RequestHandlerClass)

  class RouteTCPHandler(socketserver.BaseRequestHandler):
    def recv(self, length):
      data = b''
      while len(data) < length:
        chunk = self.request.recv(length - len(data))
        if not chunk:
          break
        data += chunk

      return data

    def handle(self):

      length_bytes = self.recv(4)
      if len(length_bytes) == 4:
        try:
          length = struct.unpack(">I", length_bytes)[0]
          if length > 0:

            data = self.recv(length)

            routes = []
            count = int(len(data) / 8)
            for i in range(count):
              lat = struct.unpack(">f", data[i * 8:i * 8 + 4])[0]
              lon = struct.unpack(">f", data[i * 8 + 4:i * 8 + 8])[0]

              coord = Coordinate.from_mapbox_tuple((lon, lat))
              routes.append(coord)

            coords = [c.as_dict() for c in routes]
            self.server.navi_route.dispatch_route(coords)
          else:
            self.server.navi_route.dispatch_route(None)

        except Exception as e:
          print(e)
          pass

      self.request.close()

def main():
  rk = Ratekeeper(1.0)
  navi_route = NaviRoute()
  while True:
    navi_route.update()
    rk.keep_time()


if __name__ == "__main__":
  main()