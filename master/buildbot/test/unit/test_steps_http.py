# This file is part of Buildbot.  Buildbot is free software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, version 2.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Copyright Buildbot Team Members

from twisted.internet import reactor
from twisted.trial import unittest
from twisted.web.server import Site
from twisted.web.resource import Resource
from buildbot.test.util import steps
from buildbot.status.results import SUCCESS, FAILURE
from buildbot.steps import http
try:
    import txrequests
    assert txrequests
    import requests
    assert requests
except ImportError:
    txrequests = requests = None

# We use twisted's internal webserver instead of mocking requests
# to be sure we use the correct requests interfaces
class TestPage(Resource):
    isLeaf = True
    def render_GET(self, request):
        if request.uri == "/404":
            request.setResponseCode(404)
            return "404"
        elif request.uri == "/header":
            return "".join(request.requestHeaders.getRawHeaders("X-Test"))
        return "OK"

class TestHTTPStep(steps.BuildStepMixin, unittest.TestCase):

    timeout = 3 # those tests should not run long
    def setUp(self):
        if txrequests is None:
            raise unittest.SkipTest("Need to install txrequests to test http steps")

        # port 0 means random unused port
        self.listener = reactor.listenTCP(0, Site(TestPage()))
        self.port = self.listener.getHost().port
        return self.setUpBuildStep()

    def tearDown(self):
        http.closeSession()
        d = self.listener.stopListening()
        d.addBoth(lambda x:self.tearDownBuildStep())
        return d

    def getURL(self, path=""):
        return "http://127.0.0.1:%d/%s" % (self.port, path)

    def test_basic(self):
        url = self.getURL()
        self.setupStep(http.GET(url))
        self.expectLogfile('log', "URL: %s\nStatus: 200\n ------ Content ------\nOK" % (url, ))
        self.expectOutcome(result=SUCCESS, status_text=["Requested"])
        return self.runStep()

    def test_404(self):
        url = self.getURL("404")
        self.setupStep(http.GET(url))
        self.expectLogfile('log', "URL: %s\n ------ Content ------\n404" % (url, ))
        self.expectOutcome(result=FAILURE, status_text=["Requested"])
        return self.runStep()

    def test_POST(self):
        url = self.getURL("POST")
        self.setupStep(http.POST(url))
        self.expectLogfile('log', "URL: %s\n ------ Content ------\n\n<html>\n"
                           "  <head><title>405 - Method Not Allowed</title></head>\n"
                           "  <body>\n    <h1>Method Not Allowed</h1>\n    <p>Your browser "
                           "approached me (at /POST) with the method \"POST\".  I only allow the "
                           "methods HEAD, GET here.</p>\n  </body>\n</html>\n" % (url, ))
        self.expectOutcome(result=FAILURE, status_text=["Requested"])
        return self.runStep()

    def test_header(self):
        url = self.getURL("header")
        self.setupStep(http.GET(url, headers={"X-Test": "True"}))
        self.expectLogfile('log', "URL: %s\nStatus: 200\n ------ Content ------\nTrue" % (url, ))
        self.expectOutcome(result=SUCCESS, status_text=["Requested"])
        return self.runStep()
