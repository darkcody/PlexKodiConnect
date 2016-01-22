# -*- coding: utf-8 -*-
import threading
import traceback
import socket
import requests

import xbmc

import clientinfo
import utils
from plexbmchelper import listener, plexgdm, subscribers
from plexbmchelper.settings import settings


class PlexCompanion(threading.Thread):
    def __init__(self):
        self._shouldStop = threading.Event()
        self.port = int(utils.settings('companionPort'))
        ci = clientinfo.ClientInfo()
        self.addonName = ci.getAddonName()
        self.clientId = ci.getDeviceId()
        self.deviceName = ci.getDeviceName()
        self.logMsg("----===## Starting PlexBMC Helper ##===----", 1)

        # Start GDM for server/client discovery
        self.client = plexgdm.plexgdm(debug=settings['gdm_debug'])
        self.client.clientDetails(self.clientId,      # UUID
                                  self.deviceName,    # clientName
                                  self.port,
                                  self.addonName,
                                  '1.0')    # Version
        self.logMsg("Registration string is: %s "
                    % self.client.getClientDetails(), 1)

        threading.Thread.__init__(self)

    def logMsg(self, msg, lvl=1):
        className = self.__class__.__name__
        utils.logMsg("%s %s" % (self.addonName, className), msg, lvl)

    def stopClient(self):
        # When emby for kodi terminates
        self._shouldStop.set()

    def stopped(self):
        return self._shouldStop.isSet()

    def run(self):
        start_count = 0
        while True:
            try:
                httpd = listener.ThreadedHTTPServer(
                    ('', self.port),
                    listener.MyHandler)
                httpd.timeout = 0.95
                break
            except:
                self.logMsg("Unable to start PlexCompanion. Traceback:", -1)
                self.logMsg(traceback.print_exc(), -1)

            xbmc.sleep(3000)

            if start_count == 3:
                self.logMsg("Error: Unable to start web helper.", -1)
                httpd = False
                break

            start_count += 1

        if not httpd:
            return

        self.client.start_all()
        message_count = 0
        is_running = False
        while not self.stopped():
            try:

                httpd.handle_request()
                message_count += 1

                if message_count > 30:
                    if self.stopped():
                        break
                    if self.client.check_client_registration():
                        self.logMsg("Client is still registered", 1)
                    else:
                        self.logMsg("Client is no longer registered",
                                    1)
                        self.logMsg("PlexBMC Helper still running on "
                                    "port %s" % self.port, 1)
                    message_count = 0

                if not is_running:
                    self.logMsg("PleXBMC Helper has started", 0)

                is_running = True
                if message_count % 1 == 0:
                    subscribers.subMgr.notify()
                settings['serverList'] = self.client.getServerList()
            except:
                self.logMsg("Error in loop, continuing anyway", 1)
                self.logMsg(traceback.print_exc(), 1)

        self.client.stop_all()
        try:
            httpd.socket.shutdown(socket.SHUT_RDWR)
        finally:
            httpd.socket.close()
        requests.dumpConnections()
        self.logMsg("----===## STOP PlexBMC Helper ##===----", 0)
